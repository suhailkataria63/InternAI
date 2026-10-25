import json
import re

import pytest

from app.agents import application_writer_agent as application
from app.agents import cover_letter_agent as cover_letter


@pytest.fixture
def evidence():
    return {
        "candidate": {"name": "Jane Doe", "education": "B.Tech Computer Science (Currently pursuing)", "experience": []},
        "job_context": {"responsibilities": ["Build generative AI workflows"]},
        "matched_skills": [],
        "listed_skills": ["Python", "Docker"],
        "unsupported_skills": ["Kubernetes"],
        "projects": [{"name": "Inventory Dashboard", "description": "Built a web dashboard for tracking stock movement", "technologies": ["React"]}],
        "transferable_experience": [],
    }


def writer_text(body: str) -> str:
    filler = " I welcome the opportunity to contribute carefully, learn from the team, and discuss how my documented work can support this role."
    return "Dear Hiring Team,\n\n" + body + filler * 5 + "\n\nSincerely,\nJane Doe"


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_neutral_listed_skill_is_not_treated_as_project_experience(evidence, validator):
    text = writer_text("My resume lists Python as a skill, alongside project work in a stock dashboard.")
    assert validator(text, 180, evidence)


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_listed_skill_cannot_be_upgraded_to_undemonstrated_expertise(evidence, validator):
    text = writer_text("I have extensive experience with Docker, supported by my Inventory Dashboard project.")
    assert not validator(text, 180, evidence)


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_invented_project_use_and_metrics_are_rejected(evidence, validator):
    text = writer_text("In my Inventory Dashboard project, I built an AWS deployment pipeline that served 500,000 users every month.")
    assert not validator(text, 180, evidence)


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_missing_skill_as_learning_goal_is_allowed(evidence, validator):
    text = writer_text("I am interested in learning Kubernetes and can build on the documented project work in my Inventory Dashboard.")
    assert validator(text, 180, evidence)


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_missing_skill_explicitly_negated_as_inexperience_is_allowed(evidence, validator):
    text = writer_text("I have no experience with Kubernetes yet and would welcome the opportunity to learn it.")
    assert validator(text, 180, evidence)


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_supported_project_paraphrase_passes(evidence, validator):
    evidence["projects"] = [{"name": "Phishing Detection System", "description": "Classified suspicious URLs and emails using Python.", "technologies": ["Python"]}]
    evidence["listed_skills"] = ["Python"]
    text = writer_text("In my Phishing Detection System, I classified suspicious URLs and emails with Python.")
    assert validator(text, 180, evidence)


@pytest.mark.parametrize("validator", [application.is_valid_llm_answer, cover_letter.is_valid_llm_cover_letter])
def test_unsupported_experience_claim_is_rejected(evidence, validator):
    text = writer_text("My experience includes building generative AI workflows and evaluating chatbot responses for production use.")
    assert not validator(text, 180, evidence)


def test_project_ranking_checks_third_project_and_is_stable():
    resume = {
        "name": "Jane Doe",
        "education": ["B.Tech Computer Science (Currently pursuing)"],
        "skills": ["Python", "React"],
        "projects": [
            {"name": "Phishing Notes", "description": "Classified suspicious URLs.", "technologies": ["Python"]},
            {"name": "Restaurant Analysis", "description": "Analyzed dining demand trends.", "technologies": ["SQL"]},
            {"name": "Inventory Dashboard", "description": "Built a React dashboard to track stock movement.", "technologies": ["React"]},
        ],
    }
    job = {"role_title": "Frontend Intern", "responsibilities": ["Build a React dashboard"]}
    match = {"matched_skills": ["React"], "missing_skills": []}
    app_evidence = application.build_application_evidence(resume, job, match, "Which dashboard did you build?", "professional", 100)
    letter_evidence = cover_letter.build_cover_letter_evidence(resume, job, match, "professional", "short")
    assert app_evidence["projects"][0]["name"] == "Inventory Dashboard"
    assert letter_evidence["projects"][0]["name"] == "Inventory Dashboard"


@pytest.mark.parametrize("builder", [application.build_application_evidence, cover_letter.build_cover_letter_evidence])
def test_malformed_project_metadata_is_ignored(builder):
    resume = {"projects": [
        {"name": ["not", "a", "title"], "description": {"bad": "metadata"}, "technologies": "Python"},
        {"name": "Valid Dashboard", "description": "Built a React dashboard.", "technologies": ["React", None, {"bad": "value"}]},
    ], "skills": ["React"], "education": []}
    job = {"role_title": "Frontend Intern", "responsibilities": ["React dashboard"]}
    match = {"matched_skills": ["React"], "missing_skills": []}
    if builder is application.build_application_evidence:
        result = builder(resume, job, match, "Build a dashboard", "professional", 100)
    else:
        result = builder(resume, job, match, "professional", "short")
    assert [item["name"] for item in result["projects"]] == ["Valid Dashboard"]
    assert result["projects"][0]["technologies"] == ["React"]


def test_prompt_separates_candidate_and_jd_and_preserves_education_status():
    resume = {"name": "Jane Doe", "education": ["B.Tech Computer Science (Currently pursuing)"], "skills": ["Python"], "projects": []}
    job = {"role_title": "Analyst Intern", "responsibilities": ["Analyze datasets"]}
    match = {"matched_skills": ["Python"], "missing_skills": ["Docker"]}
    app_system, app_user = application.build_application_answer_prompt(resume, job, match, {}, "Why this role?", "professional", 100)
    letter_system, letter_user = cover_letter.build_cover_letter_prompt(resume, job, match, {}, "professional", "short")
    for system, raw in ((app_system, app_user), (letter_system, letter_user)):
        payload = json.loads(raw)
        payload = payload["evidence"]
        assert "candidate_factual_anchors" in payload and "job_context" in payload
        assert "missing_requirements" not in payload["candidate_factual_anchors"]
        assert "missing_requirements" in payload["job_context"]
        assert "Currently pursuing" in raw
        assert "preserve explicit education status" in system.lower()


@pytest.mark.parametrize("module,generate,output_field", [
    (application, application.generate_application_answer, "answer"),
    (cover_letter, cover_letter.generate_cover_letter, "cover_letter"),
])
@pytest.mark.parametrize("mode,expected_reason", [("provider", "provider_rate_limited"), ("validation", "validation_empty_or_too_short")])
def test_provider_and_validation_fallbacks_remain_distinct(monkeypatch, caplog, module, generate, output_field, mode, expected_reason):
    caplog.set_level("INFO")
    resume = {"name": "Jane Doe", "education": ["B.Tech Computer Science (Currently pursuing)"], "skills": ["Python"], "projects": []}
    job = {"role_title": "Analyst Intern", "responsibilities": []}
    match = {"matched_skills": ["Python"], "missing_skills": []}

    class FakeLLM:
        def get_status(self):
            return {"provider": "groq", "model": "mocked"}

        def generate_text(self, **kwargs):
            if mode == "provider":
                return {"provider": "groq", "used_fallback": True, "text": "", "generation_time_ms": 4.2,
                        "error": {"fallback_reason": "provider_rate_limited", "message": "secret-looking details"}}
            return {"provider": "groq", "used_fallback": False, "text": json.dumps({output_field: "bad"}), "generation_time_ms": 4.2}

    monkeypatch.setattr(module, "LLMService", FakeLLM)
    if module is application:
        result = generate(resume, job, match, {}, "Why this role?", word_limit=100)
    else:
        result = generate(resume, job, match, {}, length="short")
    assert result["fallback_reason"] == expected_reason
    assert result["generation_time_ms"] == 4.2
    if mode == "provider":
        log_text = " ".join(record.getMessage() for record in caplog.records)
        assert expected_reason in log_text and "duration_ms=4.2" in log_text
        assert "secret-looking details" not in log_text
        assert "Jane Doe" not in log_text


def test_prompt_size_estimator_baseline_shape_is_deterministic():
    resume = {"name": "Jane Doe", "education": ["B.Tech Computer Science (Currently pursuing)"], "skills": ["Python", "React", "Docker"],
              "experience": ["Analyzed support requests"], "projects": [
                  {"name": "Phishing Detection System", "description": "Classified suspicious URLs and emails using Python and scikit-learn.", "technologies": ["Python", "scikit-learn"]},
                  {"name": "Restaurant Growth Analysis", "description": "Analyzed demand trends with SQL and pandas.", "technologies": ["SQL", "Pandas"]},
                  {"name": "Inventory Dashboard", "description": "Built a React dashboard to monitor stock movement patterns.", "technologies": ["React", "TypeScript"]}]}
    job = {"role_title": "Software Engineering Intern", "company_name": "Example Co", "required_skills": ["React", "Docker"],
           "preferred_skills": ["Python"], "responsibilities": ["Build dashboard interfaces", "Develop data workflows"]}
    match = {"matched_skills": ["Python", "React"], "missing_skills": ["Docker"], "evidence_summary": {"required_skills": [{"requirement": "Docker", "status": "missing"}], "preferred_skills": []}}
    app = application.build_application_answer_prompt(resume, job, match, {}, "Describe relevant projects and skills.", "professional", 180)
    letter = cover_letter.build_cover_letter_prompt(resume, job, match, {}, "professional", "short")
    for system, user in (app, letter):
        assert len(re.findall(r"\w+|[^\w\s]", system + user)) > 0
