import io
import json
import time

import fitz
from fastapi.testclient import TestClient

from app.agents import application_writer_agent, cover_letter_agent, skill_gap_agent
from app.agents.application_writer_agent import generate_application_answer, generate_rule_based_answer
from app.agents.cover_letter_agent import generate_cover_letter, generate_rule_based_cover_letter
from app.agents.jd_analyzer import analyze_jd_text
from app.agents.match_scorer import calculate_match_score
from app.agents.resume_analyzer import analyze_resume_text
from app.agents.skill_gap_agent import analyze_skill_gap
from app.main import app
from app.services import llm_service
from app.services.llm_service import LLMService
from app.services.orchestrator_service import run_full_application_analysis
from app.services.pdf_service import clean_extracted_text, extract_text_from_pdf


client = TestClient(app)


def test_pdf_artifacts_are_cleaned_without_losing_resume_lines() -> None:
    raw_text = "Jane Doe\u200b\n● Skills: Python, React\uf0b7\nProjects\u2028["

    cleaned = clean_extracted_text(raw_text)

    assert "\u200b" not in cleaned
    assert "●" not in cleaned
    assert "\uf0b7" not in cleaned
    assert "Jane Doe" in cleaned
    assert "Skills: Python, React" in cleaned
    assert "Projects" in cleaned


def test_resume_projects_keep_titles_with_their_own_descriptions() -> None:
    resume_text = """
Jane Doe
Skills
Python, React, SQL
Projects
Phishing Detection System
Built URL and email classification workflow using Python.
Restaurant Growth Analysis
Analyzed restaurant demand trends with SQL dashboards.
"""

    profile = analyze_resume_text(resume_text)
    projects = {project["name"]: project["description"] for project in profile["projects"]}

    assert "Phishing Detection System" in projects
    assert "Restaurant Growth Analysis" in projects
    assert "URL and email classification" in projects["Phishing Detection System"]
    assert "restaurant demand trends" in projects["Restaurant Growth Analysis"]
    assert "restaurant demand trends" not in projects["Phishing Detection System"]


def test_application_answer_uses_grounded_clean_project_text_and_word_limit() -> None:
    resume_profile = {
        "education": ["B.Tech in Computer Science"],
        "skills": ["Python", "Python", "React", "SQL"],
        "projects": [
            {
                "name": "Phishing Detection System",
                "description": "Jan 2024 - Mar 2024 ● Built URL and email classification workflow using Python and React.",
                "technologies": ["Python", "React"],
            }
        ],
    }
    job_profile = {"role_title": "Software Engineering Intern", "company_name": "Acme Labs"}
    match_result = {"matched_skills": ["Python", "React"], "missing_skills": ["Docker"]}
    skill_gap_result = {"priority_skills": [{"skill": "Docker", "priority": "High"}]}

    result = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        tone="professional",
        word_limit=80,
    )
    answer = result["generated_answer"]

    assert result["word_count"] <= 80
    assert "●" not in answer
    assert "[" not in answer and "]" not in answer
    assert "Jan 2024" not in answer
    assert "Python, Python" not in answer
    assert "Phishing Detection System" in answer
    assert "URL and email classification" in answer
    assert "Docker" not in answer


def test_cover_letter_is_structured_and_avoids_invented_project_details() -> None:
    resume_profile = {
        "name": "Jane Doe",
        "education": ["B.Tech in Computer Science"],
        "skills": ["Python"],
        "projects": [{"name": "Inventory Dashboard", "description": "", "technologies": []}],
    }
    job_profile = {"role_title": "Data Intern", "company_name": "Acme Labs"}
    match_result = {"matched_skills": ["Python"], "missing_skills": []}

    result = generate_rule_based_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result={},
        tone="professional",
        length="short",
    )
    cover_letter = result["cover_letter"]

    assert cover_letter.startswith("Dear Hiring Team,")
    assert "Inventory Dashboard" in cover_letter
    assert "clear technical implementation" not in cover_letter
    assert "[date]" not in cover_letter.lower()
    assert "Sincerely,\nJane Doe" in cover_letter


def test_education_unmatched_parenthesis_is_normalized_in_writing() -> None:
    resume_profile = {
        "education": ["B.Tech, Artificial Intelligence & Data Science ("],
        "skills": ["Python"],
        "projects": [],
    }
    job_profile = {"role_title": "AI Intern", "company_name": "Acme Labs"}
    match_result = {"matched_skills": ["Python"], "missing_skills": []}

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result={},
        application_question="Why should we hire you?",
        word_limit=90,
    )["generated_answer"]

    assert "Data Science ( background" not in answer
    assert "a B.Tech in Artificial Intelligence and Data Science" in answer


def test_currently_pursuing_education_is_preserved_through_writers() -> None:
    resume_text = """
Jane Doe
Education
B.Tech, Artificial Intelligence & Data Science (Currently pursuing)
Skills
Python, SQL
Projects
SQL Analytics Dashboard
Built SQL dashboards for reporting.
"""
    profile = analyze_resume_text(resume_text)
    job_profile = {"role_title": "Data Intern", "company_name": "Acme Labs"}
    match_result = {"matched_skills": ["SQL"], "missing_skills": []}

    answer = generate_rule_based_answer(
        profile,
        job_profile,
        match_result,
        skill_gap_result={},
        application_question="Tell me about yourself.",
        word_limit=120,
    )["generated_answer"]
    letter = generate_rule_based_cover_letter(
        profile,
        job_profile,
        match_result,
        skill_gap_result={},
        length="short",
    )["cover_letter"]

    assert profile["education"] == ["B.Tech, Artificial Intelligence & Data Science (Currently pursuing)"]
    assert "currently pursuing a B.Tech in Artificial Intelligence and Data Science" in answer
    assert "currently pursuing a B.Tech in Artificial Intelligence and Data Science" in letter
    assert "Data Science (" not in answer
    assert "Data Science (" not in letter


def test_project_notes_heading_preserves_project_evidence() -> None:
    profile = analyze_resume_text(
        """
Nisha Rao
Academic Profile
B.Tech Computer Science, 2022-2026
Capability Snapshot
Python / SQL / Pandas
Project Notes
Inventory Analytics Dashboard
Built SQL queries and Pandas reports to identify stock movement patterns.
Stack used locally: Python, SQL, Pandas
Links
GitHub: github.example/nisha
"""
    )

    projects = {project["name"]: project for project in profile["projects"]}

    assert "Inventory Analytics Dashboard" in projects
    assert "stock movement patterns" in projects["Inventory Analytics Dashboard"]["description"]
    assert projects["Inventory Analytics Dashboard"]["technologies"] == ["Python", "SQL", "Pandas"]
    assert "github" not in projects["Inventory Analytics Dashboard"]["description"].lower()


def test_project_title_cleanup_does_not_break_project_description_grammar() -> None:
    resume_profile = {
        "education": ["Diploma in Computer Engineering"],
        "skills": ["Next.js", "SQL"],
        "projects": [
            {
                "name": "Student Portal",
                "description": "Built a Next.js student portal with login screens and SQL-backed student record views.",
                "technologies": ["Next.js", "SQL"],
            }
        ],
    }
    job_profile = {"role_title": "AI/ML Developer Intern", "company_name": "Ocode Technologies"}
    match_result = {"matched_skills": ["SQL"], "missing_skills": ["Python"]}

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result={},
        application_question="Why should we hire you?",
        word_limit=120,
    )["generated_answer"]

    assert "built a Next.js student portal" in answer
    assert "built a Next.js with" not in answer


def test_skill_gap_remains_deterministic_for_ollama(monkeypatch) -> None:
    class _NoCallOllamaService:
        def get_status(self) -> dict:
            return {"provider": "ollama", "model": "qwen3:4b", "configured": True, "available": True}

        def generate_text(self, **kwargs) -> dict:
            raise AssertionError("skill gap should not call Ollama")

    monkeypatch.setattr(skill_gap_agent, "LLMService", _NoCallOllamaService)

    result = analyze_skill_gap(
        resume_profile={"skills": ["SQL"], "projects": []},
        job_profile={
            "role_title": "AI/ML Developer Intern",
            "required_skills": ["Python", "LangChain"],
            "preferred_skills": [],
        },
        match_result={
            "matched_skills": ["SQL"],
            "missing_skills": ["Python", "LangChain"],
            "match_score": 50,
        },
    )

    assert result["generation_source"] == "rule_based"
    assert result["llm_provider"] == "ollama"
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "deterministic_for_ollama"
    assert [item["skill"] for item in result["priority_skills"]]


def test_application_answers_are_question_aware_for_same_inputs() -> None:
    resume_profile = {
        "education": ["B.Tech, Artificial Intelligence & Data Science (Currently pursuing)"],
        "skills": ["Python", "SQL", "LangChain", "RAG"],
        "strengths": ["Has practical project experience", "Has database exposure"],
        "projects": [
            {
                "name": "Resume Job Matching Platform",
                "description": "Developed a RAG-based chatbot for matching resumes to job descriptions.",
                "technologies": ["Python", "LangChain", "RAG", "React"],
            }
        ],
    }
    job_profile = {
        "role_title": "AI/ML Developer",
        "company_name": "Ocode Technologies",
        "required_skills": ["Python", "LangChain", "RAG"],
        "responsibilities": ["Build generative AI workflows."],
    }
    match_result = {"matched_skills": ["Python", "LangChain", "RAG"], "missing_skills": []}

    questions = [
        "Why should we hire you?",
        "Tell me about yourself.",
        "Describe your relevant project experience.",
        "Which technical skills fit this role?",
        "What are your compensation expectations?",
        "What is your availability?",
    ]
    answers = [
        generate_rule_based_answer(
            resume_profile,
            job_profile,
            match_result,
            skill_gap_result={},
            application_question=question,
            word_limit=130,
        )["generated_answer"]
        for question in questions
    ]

    assert len(set(answers)) == len(answers)
    assert "Draft requiring input" in answers[4]
    assert "compensation expectation is not provided" in answers[4]
    assert "Draft requiring input" in answers[5]
    assert "availability or notice period is not provided" in answers[5]
    assert "relevant experience comes from project work" in answers[2]
    assert "most relevant technical skills" in answers[3]


def test_project_technologies_are_filtered_to_question_and_role_context() -> None:
    resume_profile = {
        "education": ["B.Tech in Computer Science"],
        "skills": ["Python", "SQL", "React", "Docker"],
        "projects": [
            {
                "name": "Analytics Dashboard",
                "description": "Built reporting dashboards for business metrics.",
                "technologies": ["Python", "SQL", "React", "Docker"],
            }
        ],
    }
    job_profile = {
        "role_title": "SQL Analyst Intern",
        "company_name": "Acme Labs",
        "required_skills": ["SQL"],
        "responsibilities": ["Create SQL reports."],
    }
    match_result = {"matched_skills": ["SQL"], "missing_skills": []}

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result={},
        application_question="Describe your relevant SQL project experience.",
        word_limit=90,
    )["generated_answer"]

    assert "using SQL" in answer
    assert "React" not in answer
    assert "Docker" not in answer


def test_sparse_incomplete_jd_does_not_inflate_to_strong_fit() -> None:
    resume_profile = {
        "education": ["B.Tech, Artificial Intelligence & Data Science (Currently pursuing)"],
        "skills": ["Python", "SQL"],
        "projects": [
            {
                "name": "SQL Analytics Dashboard",
                "description": "Built SQL dashboards for reporting.",
                "technologies": ["SQL"],
            }
        ],
        "experience": [],
        "certifications": [],
    }
    job_profile = analyze_jd_text("Skills required\nSQL")

    result = calculate_match_score(resume_profile, job_profile)

    assert result["matched_required_skills"] == ["SQL"]
    assert result["match_score"] <= 50
    assert result["match_level"] != "Strong Fit"
    assert result["assessment_confidence"] == "low"


def test_evidencematch_rewards_project_evidence_over_keyword_stuffing() -> None:
    job_profile = analyze_jd_text(
        """AI/ML Developer Intern
Ocode Technologies
Skills required
Python
LangChain
RAG
SQL
Preferred skills
FastAPI
Responsibilities
Build small generative AI workflows, evaluate chatbot responses, and prepare SQL-backed analysis reports.
Who can apply
B.Tech or Computer Science students with hands-on project experience can apply.
"""
    )
    demonstrated_profile = {
        "education": ["B.Tech Computer Science"],
        "skills": ["Python", "SQL"],
        "projects": [
            {
                "name": "Resume Matching RAG Platform",
                "description": "Developed a RAG chatbot using LangChain and Python to match resumes with job descriptions and store SQL reports.",
                "technologies": ["Python", "LangChain", "RAG", "SQL"],
            }
        ],
        "experience": [],
        "certifications": [],
    }
    keyword_profile = {
        "education": ["B.Tech Computer Science"],
        "skills": ["Python", "LangChain", "RAG", "SQL", "FastAPI"],
        "projects": [],
        "experience": [],
        "certifications": [],
    }

    demonstrated = calculate_match_score(demonstrated_profile, job_profile)
    keyword_only = calculate_match_score(keyword_profile, job_profile)

    assert job_profile["required_skills"] == ["Python", "LangChain", "RAG", "SQL"]
    assert job_profile["preferred_skills"] == ["FastAPI"]
    assert demonstrated["match_score"] > keyword_only["match_score"]
    assert demonstrated["score_breakdown"]["project_relevance"] > keyword_only["score_breakdown"]["project_relevance"]
    assert demonstrated["evidence_summary"]["required_skills"][1]["source"].startswith("project:")


def test_evidencematch_missing_mandatory_skills_and_related_tech_are_not_identical() -> None:
    job_profile = analyze_jd_text(
        """AI/ML Developer Intern
Skills required
Python
LangChain
RAG
SQL
Responsibilities
Build generative AI workflows and SQL-backed reports.
"""
    )
    related_profile = {
        "education": ["Diploma Computer Engineering"],
        "skills": ["React", "Next.js", "SQL"],
        "projects": [
            {
                "name": "Student Portal",
                "description": "Built a Next.js portal with SQL-backed student record views and REST API integration.",
                "technologies": ["React", "Next.js", "SQL", "REST API"],
            }
        ],
        "experience": ["Web Development Intern - connected forms to API endpoints."],
        "certifications": [],
    }

    result = calculate_match_score(related_profile, job_profile)

    assert result["matched_required_skills"] == ["SQL"]
    assert {"Python", "LangChain", "RAG"}.issubset(set(result["missing_required_skills"]))
    assert result["match_score"] < 50
    assert any(
        item["status"] == "missing" and item["requirement"] == "LangChain"
        for item in result["evidence_summary"]["required_skills"]
    )


def test_evidencematch_aliases_match_and_results_are_deterministic() -> None:
    resume_profile = {
        "education": ["B.Tech Computer Science"],
        "skills": ["Retrieval Augmented Generation", "Lang Chain", "Postgres"],
        "projects": [
            {
                "name": "Search Assistant",
                "description": "Built retrieval augmented generation flows with Lang Chain and PostgreSQL.",
                "technologies": ["Lang Chain", "PostgreSQL", "Retrieval Augmented Generation"],
            }
        ],
        "experience": [],
        "certifications": [],
    }
    job_profile = {
        "role_title": "AI Intern",
        "required_skills": ["RAG", "LangChain", "PostgreSQL"],
        "preferred_skills": [],
        "responsibilities": ["Build retrieval workflows."],
        "eligibility": [],
    }

    first = calculate_match_score(resume_profile, job_profile)
    second = calculate_match_score(resume_profile, job_profile)

    assert first == second
    assert first["matched_required_skills"] == ["RAG", "LangChain", "PostgreSQL"]
    assert first["missing_required_skills"] == []


def test_uncertain_project_description_is_not_attached_to_wrong_title() -> None:
    resume_text = """
Jane Doe
Skills
Python, React, RAG
Projects
Hybrid Phishing Detection System
Resume Job Matching Platform
May 2026 Developed a resume/job-matching platform with RAG-based chatbot support.
"""

    profile = analyze_resume_text(resume_text)
    projects = {project["name"]: project["description"] for project in profile["projects"]}

    assert "Hybrid Phishing Detection System" in projects
    assert "Resume Job Matching Platform" in projects
    assert "resume/job-matching platform" not in projects["Hybrid Phishing Detection System"].lower()
    assert "May 2026" not in projects["Resume Job Matching Platform"]
    assert "Developed a resume/job-matching platform" in projects["Resume Job Matching Platform"]


def test_project_dates_and_repeated_technologies_do_not_leak_into_outputs() -> None:
    resume_profile = {
        "education": ["B.Tech in Computer Science"],
        "skills": ["Python", "React"],
        "projects": [
            {
                "name": "Resume Job Matching Platform",
                "description": "May 2026 Developed a RAG-based chatbot for resume and job matching using Python, Python, React.",
                "technologies": ["Python", "python", "React", "React"],
            }
        ],
    }
    job_profile = {"role_title": "AI Intern", "company_name": "Acme Labs"}
    match_result = {"matched_skills": ["Python", "React"], "missing_skills": []}

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result={},
        application_question="Describe your relevant project experience.",
        word_limit=90,
    )["generated_answer"]
    letter = generate_rule_based_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result={},
        length="short",
    )["cover_letter"]

    combined = f"{answer}\n{letter}"
    assert "May 2026" not in combined
    assert "project involving May 2026" not in combined
    assert "Python, Python" not in combined
    assert "React, React" not in combined
    assert "RAG-based chatbot" in combined


def test_jd_header_company_is_detected_without_using_location() -> None:
    jd_text = """
AI/ML Developer - Generative AI & AI Agents
Ocode Technologies
•
Mohali, Punjab

Skills required
Python, LangChain, AI Agents
"""

    profile = analyze_jd_text(jd_text)

    assert profile["role_title"] == "AI/ML Developer"
    assert profile["company_name"] == "Ocode Technologies"
    assert profile["company_name"] != "Mohali, Punjab"


def test_project_technologies_are_not_inherited_from_general_skills() -> None:
    resume_text = """
Jane Doe
Skills
Python, React, SQL
Projects
Hybrid Phishing Detection System
Built URL classification workflow.
Resume Job Matching Platform
Developed a matching platform using React.
"""

    profile = analyze_resume_text(resume_text)
    projects = {project["name"]: project for project in profile["projects"]}

    assert projects["Hybrid Phishing Detection System"]["technologies"] == []
    assert projects["Resume Job Matching Platform"]["technologies"] == ["React"]


def test_project_section_stops_at_unmapped_resume_headers() -> None:
    resume_text = """
Jane Doe
Skills
Python, SQL, React
Projects
Inventory Dashboard
Built reporting dashboards for stock movement.
Technologies: Python, SQL, React
Achievements
Winner of college hackathon.
Coursework
DBMS, Operating Systems
Experience
Data Intern at Acme Labs
Worked on SQL reports.
"""

    profile = analyze_resume_text(resume_text)
    project = profile["projects"][0]

    assert project["name"] == "Inventory Dashboard"
    assert "Winner of college hackathon" not in project["description"]
    assert "DBMS" not in project["description"]
    assert "Technologies:" not in project["description"]
    assert project["technologies"] == ["Python", "React", "SQL"]
    assert "Data Intern at Acme Labs" in profile["experience"]


def test_project_metadata_labels_are_not_extracted_as_projects_or_prose() -> None:
    resume_text = """
Alex Parker
alex@example.com
Projects
Remote Developer Project Overview
Built a responsive React dashboard for remote developer collaboration.
Tech Stack: React, Next.js, Tailwind CSS, Git
Experience
Frontend Intern at Example Co
"""

    profile = analyze_resume_text(resume_text)
    project_text = " ".join(
        project["name"] + " " + project["description"]
        for project in profile["projects"]
    )

    assert "Remote Developer Project Overview" not in project_text
    assert "Tech Stack:" not in project_text
    assert all(not project["name"].lower().startswith("tech stack") for project in profile["projects"])


def test_biomedical_resume_name_is_normalized_from_titled_uppercase_header() -> None:
    resume_text = """
DR. MAYA IYER | Biomedical Engineering Student
maya@example.com
Education
B.Tech Biomedical Engineering
Projects
ECG Signal Classifier
Built a model for classifying ECG signals.
Tech Stack: Python, TensorFlow
"""

    profile = analyze_resume_text(resume_text)

    assert profile["name"] == "Maya Iyer"
    assert all(not project["name"].lower().startswith("tech stack") for project in profile["projects"])


def test_repeated_experience_lines_do_not_cause_parser_runaway() -> None:
    repeated_experience = "\n".join(
        "AI Intern at Acme Labs\nWorked on SQL reporting."
        for _ in range(80)
    )
    resume_text = f"""
Jane Doe
Education
B.Tech, Artificial Intelligence & Data Science (Currently pursuing)
Skills
Python, SQL
Experience
{repeated_experience}
Projects
SQL Analytics Dashboard
Built SQL dashboards for reporting.
"""

    start = time.perf_counter()
    profile = analyze_resume_text(resume_text)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 500
    assert profile["experience"]
    assert len(profile["experience"]) <= 3


def test_pipeline_summary_includes_stage_timings_without_content() -> None:
    result = run_full_application_analysis(
        resume_text="""Jane Doe
Education
B.Tech, Artificial Intelligence & Data Science (Currently pursuing)
Skills
Python, SQL
Projects
SQL Analytics Dashboard
Built SQL dashboards for reporting.
""",
        job_description="""Data Intern
Skills required
SQL
Responsibilities
Create SQL reports.
""",
        application_question="Describe your relevant project experience.",
        word_limit=90,
    )

    timings = result["pipeline_summary"]["stage_timings_ms"]

    assert set(timings) >= {
        "resume_analyzer",
        "jd_analyzer",
        "match_scorer",
        "skill_gap",
    }
    assert "application_writer" not in timings
    assert "cover_letter" not in timings
    assert all(isinstance(value, float) and value >= 0 for value in timings.values())
    assert "Jane Doe" not in json.dumps(timings)


def test_generated_writing_uses_company_but_not_missing_skills_or_bad_signature() -> None:
    resume_profile = {
        "name": "jane doe (",
        "education": ["B.Tech, Artificial Intelligence & Data Science ("],
        "skills": ["Python", "LangChain"],
        "projects": [
            {
                "name": "Resume Job Matching Platform",
                "description": "Developed a RAG-based chatbot for matching resumes to job descriptions.",
                "technologies": ["LangChain"],
            }
        ],
    }
    job_profile = {"role_title": "AI/ML Developer", "company_name": "Ocode Technologies"}
    match_result = {
        "matched_skills": ["Python", "LangChain"],
        "missing_skills": ["Docker", "Kubernetes"],
    }
    skill_gap_result = {"priority_skills": [{"skill": "Docker", "priority": "High"}]}

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=100,
    )["generated_answer"]
    letter = generate_rule_based_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        length="short",
    )["cover_letter"]

    combined = f"{answer}\n{letter}"
    assert "Ocode Technologies" in combined
    assert "Docker" not in answer
    assert "Kubernetes" not in answer
    assert "Docker" not in letter
    assert "Kubernetes" not in letter
    assert "Data Science ( background" not in combined
    assert "Sincerely,\nJane Doe" in letter


def _llm_context() -> tuple[dict, dict, dict, dict]:
    resume_profile = {
        "name": "Jane Doe",
        "education": ["B.Tech in Artificial Intelligence & Data Science"],
        "skills": ["Python", "LangChain", "RAG", "React"],
        "projects": [
            {
                "name": "Resume Job Matching Platform",
                "description": "Developed a RAG-based chatbot for matching resumes to job descriptions.",
                "technologies": ["LangChain", "RAG", "React"],
            }
        ],
    }
    job_profile = {
        "role_title": "AI/ML Developer",
        "company_name": "Ocode Technologies",
        "responsibilities": ["Build generative AI workflows and agent prototypes."],
    }
    match_result = {
        "matched_skills": ["Python", "LangChain", "RAG"],
        "missing_skills": ["Docker"],
    }
    skill_gap_result = {"priority_skills": [{"skill": "Docker", "priority": "High"}]}
    return resume_profile, job_profile, match_result, skill_gap_result


class _FakeLLMService:
    text = ""
    raise_error = False
    last_user_prompt = ""

    def get_status(self) -> dict:
        return {"provider": "openai", "model": "fake-model", "configured": True, "available": True}

    def generate_text(self, **kwargs) -> dict:
        self.__class__.last_user_prompt = kwargs.get("user_prompt", "")
        if self.raise_error:
            raise TimeoutError("provider timed out")
        return {"provider": "openai", "model": "fake-model", "text": self.text, "used_fallback": False}


class _FakeOllamaResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_ollama_provider_uses_chat_api_with_thinking_disabled(monkeypatch) -> None:
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["timeout"] = kwargs["timeout"]
        return _FakeOllamaResponse(
            payload={
                "message": {
                    "content": '<think>private reasoning</think>{"answer":"I match the role through verified Python project work."}'
                }
            }
        )

    monkeypatch.setattr(llm_service.settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm_service.settings, "llm_model", "qwen3:4b")
    monkeypatch.setattr(llm_service.settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr("httpx.post", fake_post)

    result = LLMService().generate_text(
        system_prompt='Return strict JSON only: {"answer":"..."}',
        user_prompt='{"task":"application_answer"}',
        temperature=0.25,
        max_tokens=300,
    )

    assert result["provider"] == "ollama"
    assert result["model"] == "qwen3:4b"
    assert result["used_fallback"] is False
    assert result["generation_time_ms"] >= 0
    assert "<think>" not in result["text"]
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["think"] is False
    assert captured["json"]["stream"] is False
    assert captured["json"]["format"]["required"] == ["answer"]
    assert captured["json"]["options"]["num_ctx"] == 4096
    assert captured["json"]["options"]["num_predict"] <= 700
    assert captured["timeout"] == 45


def test_ollama_provider_falls_back_when_unavailable(monkeypatch) -> None:
    def fake_post(url, **kwargs):
        raise TimeoutError("ollama timed out")

    monkeypatch.setattr(llm_service.settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm_service.settings, "llm_model", "qwen3:4b")
    monkeypatch.setattr(llm_service.settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr("httpx.post", fake_post)

    result = LLMService().generate_text("system", "user", max_tokens=200)

    assert result["provider"] == "ollama"
    assert result["used_fallback"] is True
    assert result["generation_time_ms"] >= 0
    assert "ollama timed out" in result["error"]["message"]


def test_groq_writer_uses_strict_schema_and_bounded_completion(monkeypatch) -> None:
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _FakeOllamaResponse(
            payload={
                "choices": [{"message": {"content": '{"answer":"A grounded answer from verified project evidence."}'}}],
                "usage": {"prompt_tokens": 121, "completion_tokens": 22, "total_tokens": 143},
            }
        )

    monkeypatch.setattr(llm_service.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm_service.settings, "llm_model", "openai/gpt-oss-120b")
    monkeypatch.setattr(llm_service.settings, "groq_api_key", "test-secret")
    monkeypatch.setattr("httpx.post", fake_post)

    result = LLMService().generate_text(
        'Return strict JSON only with exactly one key: {"answer":"..."}.',
        '{"evidence":"verified project"}',
        temperature=0.25,
        max_tokens=500,
    )

    body = captured["json"]
    assert result["provider"] == "groq"
    assert result["model"] == "openai/gpt-oss-120b"
    assert result["used_fallback"] is False
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "internai_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
        },
    }
    assert body["max_completion_tokens"] == 500
    assert body["reasoning_effort"] == "low"
    assert result["usage"] == {"prompt_tokens": 121, "completion_tokens": 22, "total_tokens": 143}
    assert "test-secret" not in str(result)


def test_groq_retries_rate_limit_once_and_keeps_reason_safe(monkeypatch) -> None:
    attempts = []

    class Response(_FakeOllamaResponse):
        headers = {"retry-after": "0"}

    def fake_post(url, **kwargs):
        attempts.append(url)
        if len(attempts) == 1:
            return Response(status_code=429, text="contains private server details")
        return Response(payload={"choices": [{"message": {"content": '{"answer":"Supported project evidence makes this candidate relevant."}'}}]})

    monkeypatch.setattr(llm_service.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm_service.settings, "llm_model", "openai/gpt-oss-120b")
    monkeypatch.setattr(llm_service.settings, "groq_api_key", "test-secret")
    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr(llm_service.time, "sleep", lambda _: None)

    result = LLMService().generate_text('Return {"answer":"..."}', "evidence")

    assert len(attempts) == 2
    assert result["used_fallback"] is False


def test_groq_max_retries_zero_performs_one_request(monkeypatch) -> None:
    attempts = []

    class Response(_FakeOllamaResponse):
        headers = {"retry-after": "0"}

    def fake_post(url, **kwargs):
        attempts.append(url)
        return Response(status_code=429)

    monkeypatch.setattr(llm_service.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm_service.settings, "groq_api_key", "test-secret")
    monkeypatch.setattr(llm_service.settings, "groq_max_retries", 0)
    monkeypatch.setattr("httpx.post", fake_post)

    result = LLMService().generate_text("system", "user")

    assert len(attempts) == 1
    assert result["error"]["fallback_reason"] == "provider_rate_limited"


def test_groq_auth_and_malformed_responses_fall_back_without_retry(monkeypatch) -> None:
    attempts = []

    def fake_post(url, **kwargs):
        attempts.append(url)
        return _FakeOllamaResponse(status_code=401, text="test-secret invalid")

    monkeypatch.setattr(llm_service.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm_service.settings, "llm_model", "openai/gpt-oss-120b")
    monkeypatch.setattr(llm_service.settings, "groq_api_key", "test-secret")
    monkeypatch.setattr("httpx.post", fake_post)

    result = LLMService().generate_text('Return {"cover_letter":"..."}', "evidence")

    assert len(attempts) == 1
    assert result["used_fallback"] is True
    assert result["error"]["fallback_reason"] == "provider_authentication"
    assert "test-secret" not in str(result)


def test_groq_timeout_retries_once_and_malformed_payload_falls_back(monkeypatch) -> None:
    attempts = []

    def timeout_post(url, **kwargs):
        attempts.append(url)
        import httpx
        raise httpx.ReadTimeout("upstream timed out")

    monkeypatch.setattr(llm_service.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm_service.settings, "llm_model", "openai/gpt-oss-120b")
    monkeypatch.setattr(llm_service.settings, "groq_api_key", "test-secret")
    monkeypatch.setattr("httpx.post", timeout_post)
    monkeypatch.setattr(llm_service.time, "sleep", lambda _: None)

    timeout_result = LLMService().generate_text("system", "user")
    assert len(attempts) == 2
    assert timeout_result["error"]["fallback_reason"] == "provider_timeout"

    def malformed_post(url, **kwargs):
        return _FakeOllamaResponse(payload={"unexpected": "shape"})

    monkeypatch.setattr("httpx.post", malformed_post)
    malformed_result = LLMService().generate_text('Return {"answer":"..."}', "evidence")
    assert malformed_result["used_fallback"] is True
    assert malformed_result["error"]["fallback_reason"] == "provider_malformed_response"


def test_groq_generic_prompt_does_not_force_writer_schema(monkeypatch) -> None:
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _FakeOllamaResponse(payload={"choices": [{"message": {"content": "Plain response"}}]})

    monkeypatch.setattr(llm_service.settings, "llm_provider", "groq")
    monkeypatch.setattr(llm_service.settings, "groq_api_key", "test-secret")
    monkeypatch.setattr("httpx.post", fake_post)

    result = LLMService().generate_text("Be concise.", "hello")

    assert result["text"] == "Plain response"
    assert "response_format" not in captured["json"]


def test_groq_provider_keeps_skill_gap_and_roadmap_deterministic(monkeypatch) -> None:
    class MustNotCallLLM:
        def __init__(self):
            pass

        def get_status(self):
            return {"provider": "groq", "model": "openai/gpt-oss-120b"}

        def generate_text(self, **kwargs):
            raise AssertionError("Groq must not be called by skill-gap analysis")

    monkeypatch.setattr(skill_gap_agent, "LLMService", MustNotCallLLM)
    result = analyze_skill_gap(
        resume_profile={"skills": ["Python"]},
        job_profile={"required_skills": ["Python", "SQL"]},
        match_result={"matched_skills": ["Python"], "missing_skills": ["SQL"]},
    )

    assert result["generation_source"] == "rule_based"
    assert result["fallback_reason"] == "deterministic_for_groq"
    assert result["learning_roadmap"]


def test_writers_reject_unverified_project_outcomes_and_education_status() -> None:
    resume_profile = {
        "name": "Maya Iyer",
        "education": ["BSc Biomedical Sciences"],
        "skills": ["MATLAB", "Excel", "microscopy"],
        "projects": [
            {
                "name": "Cell Morphology Analysis",
                "description": "Used MATLAB to quantify microscopy images for cell morphology observations.",
                "technologies": ["MATLAB"],
            }
        ],
        "experience": ["Laboratory Assistant - prepared samples and maintained laboratory records."],
    }
    job_profile = {"role_title": "Web Development Intern", "company_name": "BrightStack Labs"}
    match_result = {"matched_skills": [], "missing_skills": ["React", "JavaScript"]}
    application_evidence = application_writer_agent.build_application_evidence(
        resume_profile, job_profile, match_result, "Why this internship?", "professional", 120
    )
    letter_evidence = cover_letter_agent.build_cover_letter_evidence(
        resume_profile, job_profile, match_result, "professional", "medium"
    )
    unsupported_letter = (
        "Dear Hiring Team,\n\nI am applying for the internship. In my Cell Morphology Analysis project, "
        "I designed data processing pipelines that automated image classification, resulting in faster and more reliable analysis. "
        "My laboratory work also involved clear communication with the research team. I would welcome the opportunity to contribute.\n\n"
        "Sincerely,\nMaya Iyer"
    )
    unsupported_education_status = (
        "I recently completed a BSc Biomedical Sciences degree and am interested in applying my documented MATLAB project work."
    )

    assert cover_letter_agent._llm_cover_letter_validation_issue(
        unsupported_letter, "medium", letter_evidence
    ) == "unsupported_claims"
    assert application_writer_agent._llm_answer_validation_issue(
        unsupported_education_status, 120, application_evidence
    ) == "unsupported_claims"


def test_valid_llm_application_answer_is_used(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    _FakeLLMService.text = (
        '{"answer":"I am a strong fit for the AI/ML Developer role at Ocode Technologies because '
        'my Resume Job Matching Platform used LangChain and RAG to connect resumes with job descriptions. '
        'That project evidence, along with Python, aligns with the team needs for generative AI workflows."}'
    )
    _FakeLLMService.raise_error = False
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=90,
    )

    assert result["generation_source"] == "llm"
    assert result["used_fallback"] is False
    assert "Ocode Technologies" in result["generated_answer"]
    assert "Docker" not in result["generated_answer"]


def test_ollama_application_answer_metadata_and_reasoning_cleanup(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()

    class _FakeOllamaLLMService:
        def get_status(self) -> dict:
            return {"provider": "ollama", "model": "qwen3:4b", "configured": True, "available": True}

        def generate_text(self, **kwargs) -> dict:
            return {
                "provider": "ollama",
                "model": "qwen3:4b",
                "text": (
                    '{"answer":"<think>hidden reasoning</think>I am a strong fit for the AI/ML Developer role at '
                    'Ocode Technologies because my Resume Job Matching Platform used LangChain and RAG for resume matching. '
                    'That verified project work and Python experience align with generative AI workflow responsibilities."}'
                ),
                "used_fallback": False,
                "generation_time_ms": 1234.5,
            }

    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeOllamaLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=100,
    )

    assert result["generation_source"] == "llm"
    assert result["llm_provider"] == "ollama"
    assert result["generation_time_ms"] == 1234.5
    assert "<think>" not in result["generated_answer"]
    assert "hidden reasoning" not in result["generated_answer"]
    assert "Docker" not in result["generated_answer"]


def test_simulated_llm_receives_question_aware_filtered_evidence(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    resume_profile["projects"][0]["technologies"] = ["Python", "LangChain", "RAG", "React"]
    _FakeLLMService.text = (
        '{"answer":"My relevant project experience includes the Resume Job Matching Platform, '
        'where I used LangChain and RAG for resume-to-job matching work relevant to Ocode Technologies."}'
    )
    _FakeLLMService.raise_error = False
    _FakeLLMService.last_user_prompt = ""
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Describe your relevant project experience.",
        word_limit=90,
    )

    assert result["generation_source"] == "llm"
    assert '"question_type":"project_experience"' in _FakeLLMService.last_user_prompt
    evidence = json.loads(_FakeLLMService.last_user_prompt)["evidence"]
    candidate_anchors = evidence["candidate_factual_anchors"]
    project_anchor = candidate_anchors["project_work"][0]
    assert project_anchor["technologies"] == ["Python", "LangChain", "RAG"]
    assert "experience" not in candidate_anchors
    assert "missing_requirements" in evidence["job_context"]


def test_grounded_prompt_separates_transferable_and_missing_evidence(monkeypatch) -> None:
    resume_profile = {
        "name": "Kabir Singh",
        "education": ["Diploma in Computer Engineering"],
        "skills": ["React", "Next.js", "SQL"],
        "projects": [
            {
                "name": "Student Portal",
                "description": "Built a Next.js student portal with SQL-backed student record views.",
                "technologies": ["React", "Next.js", "SQL"],
            }
        ],
        "experience": ["Web Development Intern - connected forms to existing API endpoints."],
    }
    job_profile = {
        "role_title": "AI/ML Developer Intern",
        "company_name": "Ocode Technologies",
        "responsibilities": [
            "Build generative AI workflows and prepare SQL-backed analysis reports."
        ],
    }
    match_result = {
        "matched_skills": ["SQL"],
        "missing_skills": ["Python", "LangChain", "RAG"],
        "evidence_summary": {
            "required_skills": [
                {"requirement": "SQL", "status": "direct"},
                {"requirement": "Python", "status": "missing"},
                {"requirement": "LangChain", "status": "missing"},
                {"requirement": "RAG", "status": "missing"},
            ],
            "preferred_skills": [
                {"requirement": "REST API", "status": "related"},
            ],
        },
    }
    skill_gap_result = {"priority_skills": [{"skill": "Python", "priority": "High"}]}
    _FakeLLMService.text = (
        '{"answer":"My strongest direct evidence is SQL-backed project work from the Student Portal, '
        'where I built student record views. My web development internship and API work are transferable preparation '
        'for structured backend collaboration and generative AI workflows at Ocode Technologies."}'
    )
    _FakeLLMService.raise_error = False
    _FakeLLMService.last_user_prompt = ""
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=100,
    )
    evidence = json.loads(_FakeLLMService.last_user_prompt)["evidence"]

    assert result["generation_source"] == "llm"
    assert result["used_fallback"] is False
    assert any(item.get("project") == "Student Portal" for item in evidence["candidate_factual_anchors"]["project_work"])
    assert any("API endpoints" in fact for fact in evidence["candidate_factual_anchors"]["experience"])
    assert {"Python", "LangChain", "RAG"}.issubset(set(evidence["job_context"]["missing_requirements"]))
    assert "REST API" in evidence["job_context"]["related_requirements"]
    assert "transferable preparation" in result["generated_answer"]


def test_grounded_cover_prompt_accepts_honest_transferable_profile(monkeypatch) -> None:
    resume_profile = {
        "name": "Kabir Singh",
        "education": ["Diploma in Computer Engineering"],
        "skills": ["React", "Next.js", "SQL"],
        "projects": [
            {
                "name": "Student Portal",
                "description": "Built a Next.js student portal with SQL-backed student record views.",
                "technologies": ["React", "Next.js", "SQL"],
            }
        ],
        "experience": ["Web Development Intern - connected forms to existing API endpoints."],
    }
    job_profile = {
        "role_title": "AI/ML Developer Intern",
        "company_name": "Ocode Technologies",
        "responsibilities": [
            "Build generative AI workflows and prepare SQL-backed analysis reports."
        ],
    }
    match_result = {
        "matched_skills": ["SQL"],
        "missing_skills": ["Python", "LangChain", "RAG"],
        "evidence_summary": {
            "required_skills": [
                {"requirement": "SQL", "status": "direct"},
                {"requirement": "Python", "status": "missing"},
                {"requirement": "LangChain", "status": "missing"},
                {"requirement": "RAG", "status": "missing"},
            ],
            "preferred_skills": [],
        },
    }
    skill_gap_result = {"priority_skills": [{"skill": "Python", "priority": "High"}]}
    _FakeLLMService.text = (
        '{"cover_letter":"Dear Hiring Team,\\n\\nI am writing to apply for the AI/ML Developer Intern role at '
        'Ocode Technologies. My direct evidence includes a Student Portal project with SQL-backed student record views, '
        'and my web development internship gave me transferable experience connecting forms to API endpoints. I would bring '
        'careful execution while continuing to grow into the role requirements.\\n\\nSincerely,\\nKabir Singh"}'
    )
    _FakeLLMService.raise_error = False
    _FakeLLMService.last_user_prompt = ""
    monkeypatch.setattr(cover_letter_agent, "LLMService", _FakeLLMService)

    result = generate_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        length="short",
    )
    evidence = json.loads(_FakeLLMService.last_user_prompt)["evidence"]

    assert result["generation_source"] == "llm"
    assert result["used_fallback"] is False
    assert any(item.get("project") == "Student Portal" for item in evidence["candidate_factual_anchors"]["project_work"])
    assert {"Python", "LangChain", "RAG"}.issubset(set(evidence["job_context"]["missing_requirements"]))


def test_partial_web_profile_fallback_uses_matched_evidence_without_skill_dump() -> None:
    resume_profile = {
        "name": "Nisha Rao",
        "education": ["B.Tech Information Technology, 2022-2026"],
        "skills": ["HTML", "CSS", "JavaScript", "SQL", "Python"],
        "projects": [
            {
                "name": "Inventory Analytics Dashboard",
                "description": "Built a dashboard with HTML, CSS, JavaScript, and SQL-backed reports to summarize stock movement patterns.",
                "technologies": ["HTML", "CSS", "JavaScript", "SQL"],
            }
        ],
        "experience": ["Data Intern - cleaned CSV data and prepared simple internal dashboards."],
    }
    job_profile = {
        "role_title": "Web Development Intern",
        "company_name": "BrightStack Labs",
        "required_skills": ["React", "JavaScript", "HTML", "CSS", "REST API", "Git"],
        "preferred_skills": ["Next.js", "Tailwind CSS"],
    }
    match_result = {
        "matched_skills": ["JavaScript", "HTML", "CSS"],
        "missing_skills": ["React", "REST API", "Git", "Next.js", "Tailwind CSS"],
    }

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        {"missing_skills": match_result["missing_skills"]},
        "Why should we hire you?",
        word_limit=90,
    )

    text = answer["generated_answer"]
    assert "JavaScript" in text
    assert "HTML" in text
    assert "CSS" in text
    assert "using JavaScript, SQL, HTML" not in text
    assert "Python" not in text
    assert "React" not in text
    assert text.count("Web Development Intern role at BrightStack Labs") <= 1


def test_weak_web_profile_fallback_does_not_overstate_unrelated_education() -> None:
    resume_profile = {
        "name": "Kabir Singh",
        "education": ["Currently pursuing B.Com"],
        "skills": ["Excel", "Canva", "Communication", "Content Writing"],
        "projects": [
            {
                "name": "Campus Event Poster Series",
                "description": "Designed posters and wrote promotional copy for college events.",
                "technologies": ["Canva"],
            }
        ],
        "experience": [
            "Marketing Volunteer - created social media captions, organized campaign schedules, and coordinated event updates."
        ],
    }
    job_profile = {
        "role_title": "Web Development Intern",
        "company_name": "BrightStack Labs",
        "required_skills": ["React", "JavaScript", "HTML", "CSS", "REST API", "Git"],
    }
    match_result = {
        "matched_skills": [],
        "missing_skills": ["React", "JavaScript", "HTML", "CSS", "REST API", "Git"],
    }

    answer = generate_rule_based_answer(
        resume_profile,
        job_profile,
        match_result,
        {"missing_skills": match_result["missing_skills"]},
        "Why are you interested in this role?",
        word_limit=90,
    )
    letter = generate_rule_based_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        {"missing_skills": match_result["missing_skills"]},
        length="short",
    )

    combined = answer["generated_answer"] + "\n" + letter["cover_letter"]
    assert "aligns with the Web Development Intern role" not in combined
    assert "relevant preparation for the role" not in combined
    assert "I designed posters" in combined
    assert "React" not in answer["generated_answer"]
    assert "REST API" not in answer["generated_answer"]


def test_cover_letter_unknown_name_does_not_use_candidate_signature() -> None:
    resume_profile = {
        "name": "",
        "education": ["B.Tech Computer Science"],
        "skills": ["React"],
        "projects": [
            {
                "name": "Portfolio Dashboard",
                "description": "Built a responsive React dashboard.",
                "technologies": ["React"],
            }
        ],
        "experience": [],
    }
    job_profile = {"role_title": "Web Development Intern", "company_name": "BrightStack Labs"}

    letter = generate_rule_based_cover_letter(
        resume_profile,
        job_profile,
        {"matched_skills": ["React"], "missing_skills": []},
        {"missing_skills": []},
        length="short",
    )["cover_letter"]

    assert "Sincerely," in letter
    assert "Sincerely,\nCandidate" not in letter


def test_invalid_llm_application_output_falls_back(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    _FakeLLMService.text = "Here is a non-json answer with no structure."
    _FakeLLMService.raise_error = False
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=90,
    )

    assert result["generation_source"] == "rule_based"
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "validation_empty_or_too_short"


def test_provider_failure_falls_back(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    _FakeLLMService.text = ""
    _FakeLLMService.raise_error = True
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=90,
    )

    assert result["generation_source"] == "rule_based"
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "provider_exception"


def test_unsupported_llm_claim_is_rejected(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    _FakeLLMService.text = (
        '{"answer":"I built a Fraud Detection Dashboard with Docker and Kubernetes, '
        'which makes me ideal for Ocode Technologies."}'
    )
    _FakeLLMService.raise_error = False
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Why should we hire you?",
        word_limit=90,
    )

    assert result["generation_source"] == "rule_based"
    assert result["fallback_reason"] == "validation_unsupported_claims"
    assert "Fraud Detection Dashboard" not in result["generated_answer"]


def test_unverified_general_performance_claims_are_rejected() -> None:
    candidate_evidence = "Biomedical science degree; laboratory data entry; Excel."
    claims = (
        "I use systematic problem-solving to deliver results.",
        "I learn new technologies quickly.",
        "I communicate findings clearly with teams.",
    )

    for claim in claims:
        assert application_writer_agent._has_unverified_claim_markers(claim, candidate_evidence)
        assert cover_letter_agent._has_unverified_claim_markers(claim, candidate_evidence)

    assert not application_writer_agent._has_unverified_claim_markers(
        "I am interested in learning React.", candidate_evidence
    )


def test_valid_llm_cover_letter_is_used(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    _FakeLLMService.text = (
        '{"cover_letter":"Dear Hiring Team,\\n\\nI am writing to apply for the AI/ML Developer role at '
        'Ocode Technologies. My B.Tech background and Resume Job Matching Platform show relevant work with '
        'LangChain and RAG for resume-to-job matching. I would bring careful execution and clear communication '
        'to generative AI workflow responsibilities.\\n\\nThank you for your consideration.\\n\\nSincerely,\\nJane Doe"}'
    )
    _FakeLLMService.raise_error = False
    monkeypatch.setattr(cover_letter_agent, "LLMService", _FakeLLMService)

    result = generate_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        length="short",
    )

    assert result["generation_source"] == "llm"
    assert result["cover_letter"].startswith("Dear Hiring Team,")
    assert "Sincerely,\nJane Doe" in result["cover_letter"]
    assert "Docker" not in result["cover_letter"]


def test_llm_cover_letter_rejects_jd_responsibility_as_candidate_claim(monkeypatch) -> None:
    resume_profile = {
        "name": "Kabir Singh",
        "education": ["Diploma in Computer Engineering"],
        "skills": ["React", "Next.js", "SQL"],
        "projects": [
            {
                "name": "Student Portal",
                "description": "Built a Next.js student portal with SQL-backed student record views.",
                "technologies": ["React", "Next.js", "SQL"],
            }
        ],
    }
    job_profile = {
        "role_title": "AI/ML Developer Intern",
        "company_name": "Ocode Technologies",
        "responsibilities": [
            "Build small generative AI workflows, evaluate chatbot responses, and prepare SQL-backed analysis reports."
        ],
    }
    match_result = {
        "matched_skills": ["SQL"],
        "missing_skills": ["Python", "LangChain", "RAG"],
    }
    skill_gap_result = {"priority_skills": [{"skill": "Python", "priority": "High"}]}
    _FakeLLMService.text = (
        '{"cover_letter":"Dear Hiring Team,\\n\\nI am writing to apply for the AI/ML Developer Intern role at '
        'Ocode Technologies. With a Diploma in Computer Engineering, I have practical experience in building '
        'small generative AI workflows, evaluating chatbot responses, and preparing SQL-backed analysis reports. '
        'My Student Portal project used React, Next.js, and SQL for student record views.\\n\\nSincerely,\\nKabir Singh"}'
    )
    _FakeLLMService.raise_error = False
    monkeypatch.setattr(cover_letter_agent, "LLMService", _FakeLLMService)

    result = generate_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        length="short",
    )

    assert result["generation_source"] == "rule_based"
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "validation_unsupported_claims"
    assert "practical experience in building small generative AI workflows" not in result["cover_letter"]
    assert "Student Portal" in result["cover_letter"]


def test_writer_evidence_removes_project_date_suffix_from_llm_prompt(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()
    resume_profile["projects"][0]["name"] = "Resume Job Matching Platform | May 2026"
    _FakeLLMService.text = (
        '{"answer":"My Resume Job Matching Platform project used LangChain and RAG for resume-to-job matching."}'
    )
    _FakeLLMService.raise_error = False
    _FakeLLMService.last_user_prompt = ""
    monkeypatch.setattr(application_writer_agent, "LLMService", _FakeLLMService)

    result = generate_application_answer(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        "Describe your relevant project experience.",
        word_limit=90,
    )

    assert result["generation_source"] == "llm"
    assert "May 2026" not in _FakeLLMService.last_user_prompt
    assert "| May" not in _FakeLLMService.last_user_prompt


def test_ollama_cover_letter_metadata_and_reasoning_cleanup(monkeypatch) -> None:
    resume_profile, job_profile, match_result, skill_gap_result = _llm_context()

    class _FakeOllamaLLMService:
        def get_status(self) -> dict:
            return {"provider": "ollama", "model": "qwen3:4b", "configured": True, "available": True}

        def generate_text(self, **kwargs) -> dict:
            return {
                "provider": "ollama",
                "model": "qwen3:4b",
                "text": (
                    '{"cover_letter":"Dear Hiring Team,\\n\\n<think>private plan</think>I am writing to apply for the '
                    'AI/ML Developer role at Ocode Technologies. My Resume Job Matching Platform used LangChain and RAG '
                    'for resume-to-job matching, and my Python experience aligns with generative AI workflow responsibilities.\\n\\n'
                    'Thank you for your consideration.\\n\\nSincerely,\\nJane Doe"}'
                ),
                "used_fallback": False,
                "generation_time_ms": 1500.0,
            }

    monkeypatch.setattr(cover_letter_agent, "LLMService", _FakeOllamaLLMService)

    result = generate_cover_letter(
        resume_profile,
        job_profile,
        match_result,
        skill_gap_result,
        length="short",
    )

    assert result["generation_source"] == "llm"
    assert result["llm_provider"] == "ollama"
    assert result["generation_time_ms"] == 1500.0
    assert "<think>" not in result["cover_letter"]
    assert "private plan" not in result["cover_letter"]
    assert result["cover_letter"].startswith("Dear Hiring Team,")


def test_pdf_to_full_pipeline_preserves_grounded_facts_with_mock_llm() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        """Jane Doe
Education
B.Tech, Artificial Intelligence & Data Science (
Skills
Python, React, LangChain, RAG, Python
Projects
Hybrid Phishing Detection System
Built URL and email classification workflow.
Resume Job Matching Platform
May 2026 Developed a RAG-based chatbot for matching resumes to job descriptions.
Used LangChain, RAG, and React.
""",
    )
    pdf_bytes = document.tobytes()
    document.close()

    resume_text = extract_text_from_pdf(pdf_bytes)
    jd_text = """AI/ML Developer - Generative AI & AI Agents
Ocode Technologies
•
Mohali, Punjab

Skills required
Python, LangChain, RAG, AI Agents, Docker
Responsibilities
Build generative AI workflows and agent prototypes.
"""

    result = run_full_application_analysis(
        resume_text=resume_text,
        job_description=jd_text,
        application_question="Why should we hire you?",
        tone="professional",
        word_limit=130,
        cover_letter_length="short",
    )

    assert result["resume_profile"]["education"] == ["B.Tech, Artificial Intelligence & Data Science"]
    projects = {project["name"]: project for project in result["resume_profile"]["projects"]}
    assert "resume" not in projects["Hybrid Phishing Detection System"]["description"].lower()
    assert projects["Resume Job Matching Platform"]["technologies"] == ["React", "LangChain", "RAG"]
    assert result["job_profile"]["company_name"] == "Ocode Technologies"
    assert result["job_profile"]["role_title"] == "AI/ML Developer"
    assert 0 <= result["match_result"]["match_score"] <= 100
    assert "Docker" in result["match_result"]["missing_skills"]
    assert "Docker" in [item["skill"] for item in result["skill_gap_result"]["priority_skills"]]
    assert result["application_answer"] == {}
    assert result["cover_letter"] == {}


def test_orchestrator_api_e2e_contract_with_ocode_jd() -> None:
    response = client.post(
        "/api/orchestrator/analyze-application",
        json={
            "resume_text": """Jane Doe
Education
B.Tech, Artificial Intelligence & Data Science (
Skills
Python, React, LangChain, RAG, Python
Projects
Hybrid Phishing Detection System
Built URL and email classification workflow.
Resume Job Matching Platform
May 2026 Developed a RAG-based chatbot for matching resumes to job descriptions.
Used LangChain, RAG, and React.
""",
            "job_description": """AI/ML Developer - Generative AI & AI Agents
Ocode Technologies
•
Mohali, Punjab

Skills required
Python, LangChain, RAG, AI Agents, Docker
Responsibilities
Build generative AI workflows and agent prototypes.
""",
            "application_question": "Why should we hire you?",
            "tone": "professional",
            "word_limit": 130,
            "cover_letter_length": "short",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_profile"]["company_name"] == "Ocode Technologies"
    assert payload["pipeline_summary"]["company_name"] == "Ocode Technologies"
    assert payload["application_answer"] == {}
    assert payload["cover_letter"] == {}
    assert payload["application_answer"]["used_fallback"] is True
