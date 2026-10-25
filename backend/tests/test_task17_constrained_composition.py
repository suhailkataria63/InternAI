import json

from app.agents.application_writer_agent import (
    _llm_answer_validation_issue,
    build_application_answer_prompt,
    build_application_evidence,
    diagnose_llm_answer_validation,
)
from app.agents.cover_letter_agent import (
    _llm_cover_letter_validation_issue,
    build_cover_letter_evidence,
)
from app.agents.writer_grounding import build_writer_evidence_ledger
from app.services.evaluation_report import estimate_prompt_tokens
from prototypes.task17_constrained_composition import (
    CHOICES,
    build_choice_prompt,
    classify_question,
    compose_locked_writing,
    mock_model_response,
    parse_choice_response,
)
from run_controlled_groq_evaluation import (
    APPLICATION_QUESTION,
    JOB,
    MATCH,
    RESUME,
    SKILL_GAP,
)


TASK16_ANSWER = (
    "In my recent Study Planner project, I created a study-session tracker that combines a React front-end with FastAPI endpoints for the back-end. "
    "The API layer, written in Python using FastAPI, handles requests to store and retrieve session data in a PostgreSQL database, leveraging SQL for data operations. "
    "This architecture gave me practical experience designing and implementing reliable, data-driven APIs, as well as ensuring they integrate smoothly with a client interface. "
    "Working on this project reinforced my understanding of API design principles, request handling, and database interactions—skills directly aligned with the responsibilities of building backend APIs and improving data-driven tools at Northstar Labs."
)


def _evidence(writer="application_answer"):
    if writer == "application_answer":
        evidence = build_application_evidence(
            RESUME, JOB, MATCH, APPLICATION_QUESTION, "professional", 180,
        )
    else:
        evidence = build_cover_letter_evidence(RESUME, JOB, MATCH, "professional", "short")
    anchors = build_writer_evidence_ledger(evidence, RESUME)["candidate_factual_anchors"]
    return evidence, anchors, evidence["job_context"]


def test_task16_saved_answer_reproduces_with_clause_level_diagnosis():
    evidence, _, _ = _evidence()
    assert [item["rejected_rule_id"] for item in diagnose_llm_answer_validation(TASK16_ANSWER, 180, evidence)] == [
        "unsupported_project_detail_claim"
    ]

    supported_paraphrase = (
        "In my recent Study Planner project, I created a study-session tracker with a React interface and FastAPI endpoints."
    )
    unsupported_operations = (
        "The API layer handles requests to store and retrieve session data in PostgreSQL, leveraging SQL for data operations."
    )
    assert [item["rejected_rule_id"] for item in diagnose_llm_answer_validation(supported_paraphrase, 180, evidence)] == [
        "unsupported_project_detail_claim"
    ]
    assert [item["rejected_rule_id"] for item in diagnose_llm_answer_validation(unsupported_operations, 180, evidence)] == [
        "unsupported_project_detail_claim"
    ]


def test_existing_fact_first_approach_sends_facts_but_leaves_prose_open():
    system, user = build_application_answer_prompt(
        RESUME, JOB, MATCH, SKILL_GAP, APPLICATION_QUESTION, "professional", 180,
    )
    evidence = json.loads(user)["evidence"]
    assert "candidate_factual_anchors" in system
    assert "CRUD operations" not in user
    assert estimate_prompt_tokens(system, user)["value"] == 357
    assert _llm_answer_validation_issue(TASK16_ANSWER, 180, _evidence()[0]) == "unsupported_claims"


def test_locked_composition_excludes_unapproved_model_content_and_keeps_facts_verbatim():
    evidence, anchors, job_context = _evidence()
    answer_system, answer_user = build_choice_prompt(
        "application_answer", APPLICATION_QUESTION, anchors, job_context,
    )
    valid, accepted = parse_choice_response(mock_model_response())
    assert accepted
    answer = compose_locked_writing(
        "application_answer", anchors, job_context, APPLICATION_QUESTION, valid,
    )
    assert "I built a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL." in answer
    assert answer.startswith("In my Study Planner project, I built")
    assert "CRUD operations" not in answer and "unit tests" not in answer
    assert _llm_answer_validation_issue(answer, 180, evidence) is None

    invalid, accepted = parse_choice_response(mock_model_response(invalid=True))
    assert not accepted
    safe_after_invalid = compose_locked_writing(
        "application_answer", anchors, job_context, APPLICATION_QUESTION, invalid,
    )
    assert safe_after_invalid == answer
    assert "project_detail" not in answer_system + answer_user


def test_cover_letter_composes_locked_project_fact_without_repeated_skill_list():
    evidence, anchors, job_context = _evidence("cover_letter")
    choices = {"opening_id": "education_first", "relevance_id": "api_alignment", "closing_id": "warm"}
    letter = compose_locked_writing("cover_letter", anchors, job_context, "", choices)
    assert letter.startswith("Dear Hiring Team,")
    assert "Computer Science candidate expecting to graduate in 2027" in letter
    assert "I built a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL." in letter
    assert "Python, SQL, and FastAPI" not in letter
    assert "CRUD operations" not in letter
    assert _llm_cover_letter_validation_issue(letter, "short", evidence) is None


def test_revised_output_is_less_formulaic_than_task17_baseline():
    _, anchors, job_context = _evidence()
    decision, _ = parse_choice_response(mock_model_response(decision={
        "opening_id": "education_first",
        "relevance_id": "api_alignment",
        "closing_id": "warm",
    }))
    current_app = compose_locked_writing(
        "application_answer", anchors, job_context, APPLICATION_QUESTION, decision,
    )
    current_letter = compose_locked_writing("cover_letter", anchors, job_context, "", decision)
    task17_app = (
        "For a project example relevant to this question, I would use Study Planner. "
        "In my Study Planner project, I built a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL. "
        "The project's documented API and database work is relevant to the backend API work described by Northstar Labs."
    )
    task17_letter_intro = "I am a Computer Science candidate, expected 2027, applying for the Software Engineering Intern role"
    assert current_app != task17_app
    assert "For a project example" not in current_app
    assert "documented API" not in current_app
    assert task17_letter_intro not in current_letter
    assert "I am a Computer Science candidate expecting to graduate in 2027" in current_letter


def test_application_answer_changes_composition_for_project_skills_and_outcome_questions():
    evidence, anchors, job_context = _evidence()
    decision, valid = parse_choice_response(mock_model_response())
    assert valid
    project_answer = compose_locked_writing(
        "application_answer", anchors, job_context,
        "Describe a project relevant to reliable software APIs.", decision,
    )
    skill_answer = compose_locked_writing(
        "application_answer", anchors, job_context,
        "Which technical skills would you bring?", decision,
    )
    outcome_answer = compose_locked_writing(
        "application_answer", anchors, job_context,
        "What measurable impact did you achieve?", decision,
    )
    assert classify_question("Describe a project relevant to APIs") == "project_example"
    assert classify_question("Which technical skills would you bring?") == "skills"
    assert classify_question("What measurable impact did you achieve?") == "challenge_result"
    assert project_answer != skill_answer != outcome_answer
    assert "My relevant skills include" not in project_answer
    assert "Relevant skills I have listed include Python, SQL, FastAPI." in skill_answer
    assert "does not specify a particular challenge or outcome" in outcome_answer
    assert _llm_answer_validation_issue(project_answer, 180, evidence) is None


def test_partial_and_weak_synthetic_profiles_stay_short_and_fact_limited():
    partial = {
        "name": "Synthetic Partial",
        "education": "Diploma in Computing",
        "skills": ["SQL", "Excel"],
        "projects": [{
            "name": "Student Portal",
            "description": "Built SQL-backed student record views.",
            "technologies": ["SQL"],
        }],
        "experience": [],
    }
    partial_match = {"matched_skills": ["SQL"], "missing_skills": ["AWS"]}
    weak = {"name": "Synthetic Weak", "education": [], "skills": [], "projects": [], "experience": []}
    weak_match = {"matched_skills": [], "missing_skills": ["AWS"]}
    profiles = [(partial, partial_match), (weak, weak_match)]
    for resume, match in profiles:
        app_evidence = build_application_evidence(
            resume, JOB, match, APPLICATION_QUESTION, "professional", 180,
        )
        app_anchors = build_writer_evidence_ledger(app_evidence, resume)["candidate_factual_anchors"]
        cover_evidence = build_cover_letter_evidence(resume, JOB, match, "professional", "short")
        cover_anchors = build_writer_evidence_ledger(cover_evidence, resume)["candidate_factual_anchors"]
        decision, valid = parse_choice_response(mock_model_response(decision={"opening_id": "education_first"}))
        assert valid
        app_text = compose_locked_writing(
            "application_answer", app_anchors, app_evidence["job_context"], APPLICATION_QUESTION, decision,
        )
        letter_text = compose_locked_writing(
            "cover_letter", cover_anchors, cover_evidence["job_context"], "", decision,
        )
        assert "unit tests" not in app_text.lower() + letter_text.lower()
        assert "CRUD" not in app_text + letter_text
        if resume is partial:
            assert "Student Portal" in app_text and "SQL-backed student record views" in app_text
            assert "Student Portal" in letter_text
            assert "As a Diploma" not in letter_text
        else:
            assert len(app_text.split()) < 20
            assert "Study Planner" not in app_text + letter_text


def test_locked_choice_prompt_hides_project_details_and_invalid_refs_fall_back():
    _, anchors, job_context = _evidence()
    _, user = build_choice_prompt("application_answer", APPLICATION_QUESTION, anchors, job_context)
    assert "React interface" not in user
    assert "PostgreSQL" not in user
    invalid_reference = json.dumps({
        "opening_id": "P999",
        "relevance_id": "api_alignment",
        "closing_id": "brief",
    })
    decision, valid = parse_choice_response(invalid_reference)
    assert not valid
    assert decision == {"opening_id": "question_first", "relevance_id": "api_alignment", "closing_id": "brief"}


def test_every_model_selected_phrase_is_local_and_cannot_add_claims_or_commitments():
    _, anchors, job_context = _evidence()
    forbidden = (
        "I implemented CRUD",
        "I wrote unit tests",
        "I deployed",
        "I led",
        "I plan to",
        "I will",
        "I achieved",
    )
    for opening_id in CHOICES["opening_id"]:
        for relevance_id in CHOICES["relevance_id"]:
            for closing_id in CHOICES["closing_id"]:
                decision = {
                    "opening_id": opening_id,
                    "relevance_id": relevance_id,
                    "closing_id": closing_id,
                }
                for writer in ("application_answer", "cover_letter"):
                    output = compose_locked_writing(
                        writer, anchors, job_context, APPLICATION_QUESTION, decision,
                    )
                    assert all(claim not in output for claim in forbidden)
                    assert "study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL" in output
                    assert "Study Planner" in output


def test_constrained_choice_prompt_size_uses_same_estimator():
    _, anchors, job_context = _evidence()
    system, user = build_choice_prompt("application_answer", APPLICATION_QUESTION, anchors, job_context)
    estimate = estimate_prompt_tokens(system, user)
    assert estimate["method"] == "regex_word_punct_v1"
    assert estimate["value"] > 0
    output_estimate = estimate_prompt_tokens("", mock_model_response())
    assert output_estimate["method"] == estimate["method"]
    assert output_estimate["value"] > 0
    legacy_system, legacy_user = build_application_answer_prompt(
        RESUME, JOB, MATCH, SKILL_GAP, APPLICATION_QUESTION, "professional", 180,
    )
    assert estimate["value"] < estimate_prompt_tokens(legacy_system, legacy_user)["value"]


def test_explicit_goal_is_composed_verbatim_without_extra_future_commitments():
    resume = {**RESUME, "career_objective": "Explore reliable API development."}
    evidence = build_cover_letter_evidence(resume, JOB, MATCH, "professional", "short")
    anchors = build_writer_evidence_ledger(evidence, resume)["candidate_factual_anchors"]
    output = compose_locked_writing(
        "cover_letter", anchors, evidence["job_context"], "",
        {"opening_id": "education_first", "relevance_id": "api_alignment", "closing_id": "brief"},
    )
    assert "One goal I have stated is: “Explore reliable API development.”" in output
    assert "coursework" not in output.lower()
    assert "future project" not in output.lower()
    app_evidence = build_application_evidence(
        resume, JOB, MATCH, "What career goal would you bring?", "professional", 180,
    )
    app_anchors = build_writer_evidence_ledger(app_evidence, resume)["candidate_factual_anchors"]
    app_goal = compose_locked_writing(
        "application_answer", app_anchors, app_evidence["job_context"],
        "What career goal would you bring?", parse_choice_response(mock_model_response())[0],
    )
    assert app_goal == "One goal I have stated is: “Explore reliable API development.”"
    assert "I will" not in app_goal and "I plan to" not in app_goal
