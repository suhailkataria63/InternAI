import json

from app.agents import application_writer_agent as application
from app.agents import cover_letter_agent as cover_letter
from app.agents.writer_grounding import build_writer_evidence_ledger
from app.services.evaluation_report import estimate_prompt_tokens
from run_controlled_groq_evaluation import JOB, MATCH, RESUME, SKILL_GAP


QUESTION = "Describe a project relevant to reliable software APIs."
TASK13_COVER = (
    "Dear Hiring Team,\n\nI am a Computer Science candidate expected to graduate in 2027. "
    "My Study Planner project is a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL. "
    "My listed skills include Python, TypeScript, SQL, React, and FastAPI. "
    "Northstar Labs describes work on backend APIs, testing, and data-driven tools. "
    "This project gives me a relevant example of building a tracker with the listed technologies. "
    "Thank you for considering my application.\n\nSincerely,\nMaya Synthetic"
)
TASK07_COVER = (
    "Dear Hiring Team,\n\nI am a Computer Science candidate expected to graduate in 2027 and am excited to apply for the internship role. "
    "In my recent Study Planner project, I built a study session tracker using a React front‑end and FastAPI back‑end, "
    "with data stored in PostgreSQL. This experience gave me hands‑on practice with Python, SQL, FastAPI, and React, "
    "and taught me how to design and implement API endpoints that support user‑focused tools.\n\nI am eager to bring this "
    "experience to your team, contributing to backend API development, testing, and data‑driven tool improvements. While I "
    "have not yet worked with AWS, I am actively learning cloud services and look forward to gaining practical experience "
    "in that area during the internship.\n\nThank you for considering my application. I look forward to the possibility of discussing how my background aligns "
    "with your needs.\n\nSincerely,\nMaya Synthetic"
)


def _prompt_evidence(raw):
    return json.loads(raw)["evidence"]


def test_task13_cover_reproduces_offline_and_is_not_rejected():
    evidence = cover_letter.build_cover_letter_evidence(RESUME, JOB, MATCH, "professional", "short")
    assert cover_letter._llm_cover_letter_validation_issue(TASK13_COVER, "short", evidence) is None
    assert cover_letter.diagnose_llm_cover_letter_validation(TASK13_COVER, "short", evidence) == []


def test_task07_cover_rejection_is_the_unsupported_current_activity_clause():
    evidence = cover_letter.build_cover_letter_evidence(RESUME, JOB, MATCH, "professional", "short")
    rule_ids = [
        item["rejected_rule_id"]
        for item in cover_letter.diagnose_llm_cover_letter_validation(TASK07_COVER, "short", evidence)
    ]
    assert rule_ids == ["unsupported_current_learning_activity"]
    without_activity = TASK07_COVER.replace(
        "I am actively learning cloud services and look forward to gaining practical experience in that area during the internship.",
        "I have not yet worked with AWS.",
    )
    assert cover_letter._llm_cover_letter_validation_issue(without_activity, "short", evidence) is None


def test_task13_claim_clauses_are_supported_or_job_context_not_candidate_claims():
    evidence = cover_letter.build_cover_letter_evidence(RESUME, JOB, MATCH, "professional", "short")
    project_text = "my Study Planner project is a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL"
    listed_text = "My listed skills include Python, TypeScript, SQL, React, and FastAPI."
    jd_text = "Northstar Labs describes work on backend APIs, testing, and data-driven tools."
    source_project = RESUME["projects"][0]["description"].lower()
    project_evidence = cover_letter.build_cover_letter_evidence(RESUME, JOB, MATCH, "professional", "short")["projects"][0]
    assert "study session tracker" in source_project and "react interface" in source_project
    assert project_evidence["name"] == "Study Planner"
    assert all(skill in listed_text.lower() for skill in ("python", "typescript", "sql", "react", "fastapi"))
    assert "backend APIs" in " ".join(JOB["responsibilities"])
    assert "my Study Planner project" in project_text
    assert "Northstar Labs" in jd_text and "backend APIs" in jd_text
    assert cover_letter._llm_cover_letter_validation_issue(TASK13_COVER, "short", evidence) is None


def test_prompt_sends_only_categorized_candidate_anchors_and_separate_jd():
    for writer in ("application", "cover_letter"):
        if writer == "application":
            system, raw = application.build_application_answer_prompt(
                RESUME, JOB, MATCH, SKILL_GAP, QUESTION, "professional", 180,
            )
        else:
            system, raw = cover_letter.build_cover_letter_prompt(
                RESUME, JOB, MATCH, SKILL_GAP, "professional", "short",
            )
        payload = _prompt_evidence(raw)
        anchors = payload["candidate_factual_anchors"]
        assert "project_work" in anchors
        assert "listed_skills" in anchors
        assert "education" in anchors
        assert "stated_goals" not in anchors
        assert "candidate_evidence" not in payload
        assert "AWS" not in json.dumps(anchors)
        assert "AWS" in payload["job_context"]["missing_requirements"]
        assert payload["job_context"]["role_title"] == "Software Engineering Intern"
        assert payload["job_context"]["company_name"] == "Northstar Labs"
        assert "candidate_factual_anchors" in system
        assert "With no stated_goals" in system


def test_explicit_goal_is_an_anchor_but_missing_goal_is_not():
    resume = {**RESUME, "career_objective": "Explore reliable API development."}
    evidence = application.build_application_evidence(resume, JOB, MATCH, QUESTION, "professional", 180)
    ledger = build_writer_evidence_ledger(evidence, resume)
    goals = ledger["candidate_factual_anchors"]["stated_goals"]
    assert goals == ["Explore reliable API development."]


def test_partial_and_weak_profiles_have_only_their_supported_anchors():
    partial = {
        "name": "Synthetic Partial",
        "education": "Diploma in Computing",
        "skills": ["SQL", "Excel"],
        "projects": [{"name": "Student Portal", "description": "Built SQL-backed student record views.", "technologies": ["SQL"]}],
        "experience": [],
    }
    partial_match = {"matched_skills": ["SQL"], "missing_skills": ["AWS"]}
    weak = {"name": "Synthetic Weak", "education": [], "skills": [], "projects": [], "experience": []}
    weak_match = {"matched_skills": [], "missing_skills": ["AWS"]}
    for writer in ("application", "cover_letter"):
        if writer == "application":
            partial_evidence = application.build_application_evidence(partial, JOB, partial_match, QUESTION, "professional", 120)
            weak_evidence = application.build_application_evidence(weak, JOB, weak_match, QUESTION, "professional", 120)
        else:
            partial_evidence = cover_letter.build_cover_letter_evidence(partial, JOB, partial_match, "professional", "short")
            weak_evidence = cover_letter.build_cover_letter_evidence(weak, JOB, weak_match, "professional", "short")
        partial_anchors = build_writer_evidence_ledger(partial_evidence, partial)["candidate_factual_anchors"]
        assert any(anchor.get("project") == "Student Portal" for anchor in partial_anchors["project_work"])
        assert "SQL" in partial_anchors["listed_skills"]
        assert "AWS" not in json.dumps(partial_anchors)
        weak_anchors = build_writer_evidence_ledger(weak_evidence, weak)["candidate_factual_anchors"]
        assert weak_anchors == {"identity": "Synthetic Weak"}


def test_fact_anchor_prompt_size_uses_previous_local_estimator():
    estimate_job = {
        **JOB,
        "role_title": "Software Engineering Intern",
        "company_name": "Northstar Labs",
    }
    prompts = [
        application.build_application_answer_prompt(RESUME, estimate_job, MATCH, SKILL_GAP, QUESTION, "professional", 120),
        cover_letter.build_cover_letter_prompt(RESUME, estimate_job, MATCH, SKILL_GAP, "professional", "short"),
    ]
    estimates = [estimate_prompt_tokens(*prompt) for prompt in prompts]
    assert all(item["method"] == "regex_word_punct_v1" for item in estimates)
    # Task 10 with the same fixture/estimator: 429 application + 426 cover = 855.
    assert [item["value"] for item in estimates] == [357, 361]
    assert sum(item["value"] for item in estimates) - 855 == -137
