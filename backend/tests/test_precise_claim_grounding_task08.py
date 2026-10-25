import pytest

from app.agents.application_writer_agent import (
    _llm_answer_validation_issue,
    build_application_answer_prompt,
    build_application_evidence,
    diagnose_llm_answer_validation,
)
from app.agents.cover_letter_agent import (
    _llm_cover_letter_validation_issue,
    build_cover_letter_prompt,
    build_cover_letter_evidence,
    diagnose_llm_cover_letter_validation,
)
from app.agents.writer_grounding import has_unsupported_project_detail_claims
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
    "title": "Software Engineering Intern",
    "company": "Northstar Labs",
    "description": "Build backend APIs, write tests, and improve data-driven tools.",
    "responsibilities": ["Build backend APIs", "Write tests", "Improve data-driven tools"],
    "required_skills": ["Python", "SQL", "FastAPI"],
}
MATCH = {"matched_skills": ["Python", "SQL", "FastAPI", "React"], "missing_skills": ["AWS"]}
GAP = {"missing_skills": ["AWS"]}
APPLICATION_QUESTION = "Describe a project relevant to reliable software APIs."

# Exact rejected outputs persisted by Task 07's synthetic run.
TASK07_APPLICATION = (
    "In my Study Planner project I designed and implemented a backend API using FastAPI and Python. "
    "The service exposed endpoints for creating, updating, and retrieving study sessions, persisting data "
    "in a PostgreSQL database via SQL queries. I wrote unit tests for each endpoint to verify correct behavior "
    "and error handling, ensuring reliable API responses. The React front‑end consumed these endpoints, "
    "allowing users to track study progress in real time. This experience gave me hands‑on practice building, "
    "testing, and documenting a production‑grade API stack. I have not yet worked with AWS, but I am eager to "
    "learn cloud deployment and integrate it into future API projects."
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


def _app_evidence():
    return build_application_evidence(RESUME, JOB, MATCH, APPLICATION_QUESTION, "professional", 180)


def _cover_evidence():
    return build_cover_letter_evidence(RESUME, JOB, MATCH, "professional", "short")


def _app_ids(text):
    return [item["rejected_rule_id"] for item in diagnose_llm_answer_validation(text, 180, _app_evidence())]


def _cover_ids(text):
    return [item["rejected_rule_id"] for item in diagnose_llm_cover_letter_validation(text, "short", _cover_evidence())]


def _cover(body):
    return f"Dear Hiring Team,\n\n{body} I would welcome the opportunity to contribute to your team and learn from its engineers.\n\nSincerely,\nMaya Synthetic"


def test_task07_saved_outputs_reproduce_with_precise_rule_ids():
    app_issue = _llm_answer_validation_issue(TASK07_APPLICATION, 180, _app_evidence())
    app_ids = _app_ids(TASK07_APPLICATION)
    cover_issue = _llm_cover_letter_validation_issue(TASK07_COVER, "short", _cover_evidence())
    cover_ids = _cover_ids(TASK07_COVER)

    assert app_issue == "unsupported_claims"
    assert app_ids == ["unsupported_project_detail_claim"]
    assert cover_issue == "unsupported_claims"
    assert cover_ids == ["unsupported_current_learning_activity"]


@pytest.mark.parametrize("writer", ["application_answer", "cover_letter"])
@pytest.mark.parametrize(
    ("claim", "expected_issue", "expected_rule"),
    [
        ("I have not yet worked with AWS.", None, None),
        ("I would like to learn AWS.", None, None),
        ("I have experience with AWS.", "unsupported_claims", "missing_skill_claimed_as_expertise"),
        ("I am actively learning AWS.", "unsupported_claims", "unsupported_current_learning_activity"),
    ],
)
def test_missing_skill_negation_future_goal_and_current_activity(writer, claim, expected_issue, expected_rule):
    body = f"{claim} My Study Planner project used a React interface and FastAPI endpoints backed by PostgreSQL."
    if writer == "cover_letter":
        text = _cover(body)
        issue = _llm_cover_letter_validation_issue(text, "short", _cover_evidence())
        ids = _cover_ids(text)
    else:
        text = body + " I value building useful software with a careful team."
        issue = _llm_answer_validation_issue(text, 180, _app_evidence())
        ids = _app_ids(text)
    assert issue == expected_issue
    if expected_rule:
        assert expected_rule in ids
    else:
        assert ids == []


@pytest.mark.parametrize("writer", ["application_answer", "cover_letter"])
def test_supported_study_planner_paraphrase_remains_accepted(writer):
    body = "In my Study Planner project, I built a study-session tracker with a React interface, FastAPI endpoints, and PostgreSQL storage."
    if writer == "cover_letter":
        text = _cover(body)
        issue = _llm_cover_letter_validation_issue(text, "short", _cover_evidence())
        diagnostics = _cover_ids(text)
    else:
        text = body + " I enjoyed building a useful tool for organizing study sessions."
        issue = _llm_answer_validation_issue(text, 180, _app_evidence())
        diagnostics = _app_ids(text)
    assert issue is None
    assert diagnostics == []


@pytest.mark.parametrize("writer", ["application_answer", "cover_letter"])
@pytest.mark.parametrize(
    "detail",
    [
        "In my Study Planner project, I wrote unit tests for every endpoint.",
        "In my Study Planner project, I implemented detailed error handling.",
        "My Study Planner exposed endpoints for creating, updating, and retrieving sessions.",
        "The Study Planner let users track progress in real time.",
        "I used the Study Planner as a production-grade service.",
        "I deployed the Study Planner to AWS.",
        "I documented every Study Planner endpoint.",
        "I improved Study Planner performance by 30%.",
    ],
)
def test_unsupported_project_implementation_details_rejected(writer, detail):
    if writer == "cover_letter":
        text = _cover(detail)
        issue = _llm_cover_letter_validation_issue(text, "short", _cover_evidence())
        ids = _cover_ids(text)
    else:
        text = detail + " I enjoyed building the study session tracker."
        issue = _llm_answer_validation_issue(text, 180, _app_evidence())
        ids = _app_ids(text)
    assert issue == "unsupported_claims"
    assert "unsupported_project_detail_claim" in ids


def test_diagnostics_return_all_applicable_rule_ids():
    text = (
        "I have experience with AWS. I improved project performance by 30%. "
        "In my Study Planner project, I wrote unit tests for every endpoint."
    )
    ids = _app_ids(text)
    assert "missing_skill_claimed_as_expertise" in ids
    assert "unsupported_numeric_claim" in ids
    assert "unsupported_project_detail_claim" in ids


def test_implementation_details_do_not_leak_from_another_project():
    evidence = {
        "projects": [
            {"name": "Study Planner", "description": "Built a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL.", "technologies": ["React", "FastAPI", "PostgreSQL"]},
            {"name": "Test Harness", "description": "Wrote unit tests with detailed error handling.", "technologies": ["Python"]},
        ]
    }
    claim = "In my Study Planner project, I wrote unit tests for every endpoint."
    assert has_unsupported_project_detail_claims(claim, evidence)


def test_prompt_size_delta_uses_same_local_estimator():
    app = build_application_answer_prompt(RESUME, JOB, MATCH, GAP, APPLICATION_QUESTION, "professional", 120)
    cover = build_cover_letter_prompt(RESUME, JOB, MATCH, GAP, "professional", "short")
    sizes = [estimate_prompt_tokens(*prompt)["value"] for prompt in (app, cover)]
    # Task 07 baseline with this exact fixture and estimator was 413 + 449 = 862.
    assert all(size > 0 for size in sizes)
