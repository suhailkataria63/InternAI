import json

import pytest

from app.agents import application_writer_agent as application
from app.agents import cover_letter_agent as cover_letter
from app.agents.writer_grounding import build_writer_evidence_ledger, evidence_ledger_ids
from app.services.evaluation_report import estimate_prompt_tokens


RESUME = {
    "name": "Maya Synthetic",
    "education": "B.S. Computer Science candidate, expected 2027",
    "skills": ["Python", "TypeScript", "SQL", "React", "FastAPI"],
    "projects": [{
        "name": "Study Planner",
        "description": "Built a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL.",
        "technologies": ["React", "FastAPI", "PostgreSQL", "Python"],
    }],
    "experience": [],
}
JOB = {
    "role_title": "Software Engineering Intern",
    "company_name": "Northstar Labs",
    "description": "Build backend APIs, write tests, and improve data-driven tools.",
    "responsibilities": ["Build backend APIs", "Write tests", "Improve data-driven tools"],
    "required_skills": ["Python", "SQL", "FastAPI"],
}
MATCH = {"matched_skills": ["Python", "SQL", "FastAPI", "React"], "missing_skills": ["AWS"]}
GAP = {"missing_skills": ["AWS"]}
QUESTION = "Describe a project relevant to reliable software APIs."

TASK07_ANSWER = (
    "In my Study Planner project I designed and implemented a backend API using FastAPI and Python. The service exposed "
    "endpoints for creating, updating, and retrieving study sessions, persisting data in a PostgreSQL database via SQL queries. "
    "I wrote unit tests for each endpoint to verify correct behavior and error handling, ensuring reliable API responses. "
    "The React front‑end consumed these endpoints, allowing users to track study progress in real time. This experience gave me "
    "hands‑on practice building, testing, and documenting a production‑grade API stack. I have not yet worked with AWS, but I am eager to "
    "learn cloud deployment and integrate it into future API projects."
)
TASK09_ANSWER = (
    "In my Study Planner project I designed and implemented a set of FastAPI endpoints that record and retrieve study sessions stored "
    "in a PostgreSQL database. Using Python I structured the API routes to validate input, handle errors, and return consistent JSON "
    "responses, which helped ensure reliable client interactions. The backend was tested manually during development to confirm correct "
    "data handling and response formats. This experience gave me practical exposure to building and maintaining backend APIs with FastAPI "
    "and SQL. I have not yet worked with AWS, but I am eager to learn cloud services to support scalable API deployments."
)


class FakeLLM:
    text = ""
    last_user_prompt = ""
    call_count = 0

    def get_status(self):
        return {"provider": "groq"}

    def generate_text(self, *, system_prompt, user_prompt, **_kwargs):
        type(self).call_count += 1
        type(self).last_user_prompt = user_prompt
        return {
            "provider": "groq", "model": "mock-groq", "text": type(self).text,
            "used_fallback": False, "generation_time_ms": 5.0,
        }


def _payload(raw_prompt):
    return json.loads(raw_prompt)["evidence"]


def _write_application(monkeypatch, text, resume=RESUME, job=JOB, match=MATCH):
    FakeLLM.text = json.dumps({"answer": text})
    FakeLLM.last_user_prompt = ""
    FakeLLM.call_count = 0
    monkeypatch.setattr(application, "LLMService", FakeLLM)
    result = application.generate_application_answer(
        resume, job, match, GAP, QUESTION, word_limit=180,
    )
    return result, _payload(FakeLLM.last_user_prompt), FakeLLM.call_count


@pytest.mark.parametrize("writer", ["application", "cover_letter"])
def test_evidence_ledger_separates_candidate_facts_skills_goals_and_jd(writer):
    if writer == "application":
        _system, raw = application.build_application_answer_prompt(RESUME, JOB, MATCH, GAP, QUESTION, "professional", 180)
    else:
        _system, raw = cover_letter.build_cover_letter_prompt(RESUME, JOB, MATCH, GAP, "professional", "short")
    payload = _payload(raw)
    anchors = payload["candidate_factual_anchors"]
    project = anchors["project_work"][0]
    assert project["project"] == "Study Planner"
    assert set(project["technologies"]).issubset(set(RESUME["projects"][0]["technologies"]))
    assert project["technologies"]
    selected_skills = set(anchors["listed_skills"])
    assert selected_skills and selected_skills.issubset(set(RESUME["skills"]))
    assert "stated_goals" not in anchors
    assert "AWS" not in json.dumps(anchors)
    assert "AWS" in payload["job_context"]["missing_requirements"]
    assert "Write tests" in payload["job_context"]["responsibilities"]


def test_only_explicit_candidate_goals_enter_goal_ledger():
    resume = {**RESUME, "career_objective": "Explore data visualization internships."}
    evidence = application.build_application_evidence(resume, JOB, MATCH, QUESTION, "professional", 180)
    ledger = build_writer_evidence_ledger(evidence, resume)
    goals = ledger["candidate_evidence"]["candidate_stated_goals"]
    assert goals == [{"id": "G1", "goal": "Explore data visualization internships."}]
    assert "AWS" not in " ".join(item["goal"] for item in goals)


@pytest.mark.parametrize("profile", [
    {"name": "Partial Candidate", "education": "Diploma in Computing", "skills": ["SQL"], "projects": [{"name": "Student Portal", "description": "Built SQL-backed student record views.", "technologies": ["SQL"]}], "experience": []},
    {"name": "Weak Candidate", "education": [], "skills": [], "projects": [], "experience": []},
])
def test_partial_and_weak_profiles_keep_empty_evidence_empty(profile):
    evidence = application.build_application_evidence(profile, JOB, {"matched_skills": [], "missing_skills": ["AWS"]}, QUESTION, "professional", 120)
    ledger = build_writer_evidence_ledger(evidence, profile)["candidate_evidence"]
    if profile["name"] == "Partial Candidate":
        assert ledger["projects"][0]["name"] == "Student Portal"
        assert ledger["listed_skills"] == ["SQL"]
    else:
        assert ledger["candidate"]["education"] == ""
        assert ledger["projects"] == []
        assert ledger["listed_skills"] == []
    assert ledger["candidate_stated_goals"] == []


@pytest.mark.parametrize("text", [TASK07_ANSWER, TASK09_ANSWER])
def test_task07_and_task09_unsupported_project_claims_still_fall_back(monkeypatch, text):
    result, _payload_value, calls = _write_application(monkeypatch, text)
    assert calls == 1
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "validation_unsupported_claims"


@pytest.mark.parametrize("writer", ["application", "cover_letter"])
def test_supported_project_paraphrase_uses_one_mocked_call_without_fallback(monkeypatch, writer):
    paraphrase = "In my Study Planner project, I built a study-session tracker with a React interface, FastAPI endpoints, and PostgreSQL storage."
    FakeLLM.text = json.dumps({"answer": paraphrase})
    FakeLLM.call_count = 0
    monkeypatch.setattr(application, "LLMService", FakeLLM)
    monkeypatch.setattr(cover_letter, "LLMService", FakeLLM)
    if writer == "application":
        result = application.generate_application_answer(RESUME, JOB, MATCH, GAP, QUESTION, word_limit=180)
    else:
        letter = f"Dear Hiring Team,\n\n{paraphrase} I would welcome the chance to contribute to the team.\n\nSincerely,\nMaya Synthetic"
        FakeLLM.text = json.dumps({"cover_letter": letter})
        result = cover_letter.generate_cover_letter(RESUME, JOB, MATCH, GAP, length="short")
    assert FakeLLM.call_count == 1
    assert result["generation_source"] == "llm"
    assert result["used_fallback"] is False


def test_empty_goal_ledger_and_prompt_forbid_invented_future_plans():
    system, raw = cover_letter.build_cover_letter_prompt(RESUME, JOB, MATCH, GAP, "professional", "short")
    payload = _payload(raw)
    assert "stated_goals" not in payload["candidate_factual_anchors"]
    assert "With no stated_goals" in system
    assert "future projects" in system
    assert "coursework" in system


def test_hallucinated_evidence_refs_cannot_rescue_unsupported_claim(monkeypatch):
    unsupported = "I wrote unit tests and implemented detailed error handling in my Study Planner project."
    FakeLLM.text = json.dumps({"answer": unsupported, "evidence_refs": ["P999", "JOB-CLAIM-1"]})
    FakeLLM.call_count = 0
    monkeypatch.setattr(application, "LLMService", FakeLLM)
    result = application.generate_application_answer(RESUME, JOB, MATCH, GAP, QUESTION, word_limit=180)
    ledger = build_writer_evidence_ledger(
        application.build_application_evidence(RESUME, JOB, MATCH, QUESTION, "professional", 180), RESUME,
    )
    valid_ids = evidence_ledger_ids(ledger)
    assert "P999" not in valid_ids and "JOB-CLAIM-1" not in valid_ids
    assert FakeLLM.call_count == 1
    assert result["used_fallback"] is True
    assert result["fallback_reason"] == "validation_unsupported_claims"


def test_prompt_size_estimate_same_fixture_after_ledger_change():
    app_prompt = application.build_application_answer_prompt(RESUME, JOB, MATCH, GAP, QUESTION, "professional", 120)
    cover_prompt = cover_letter.build_cover_letter_prompt(RESUME, JOB, MATCH, GAP, "professional", "short")
    counts = [estimate_prompt_tokens(*prompt)["value"] for prompt in (app_prompt, cover_prompt)]
    assert all(count > 0 for count in counts)
