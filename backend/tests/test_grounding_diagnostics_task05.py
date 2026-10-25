import json

import pytest

from app.agents.application_writer_agent import (
    _llm_answer_validation_issue,
    diagnose_llm_answer_validation,
)
from app.agents.cover_letter_agent import (
    _llm_cover_letter_validation_issue,
    diagnose_llm_cover_letter_validation,
)
from app.services.evaluation_report import EvaluationReportStore, estimate_prompt_tokens
from app.services.llm_service import LLMService
from app.config import settings


BASE_EVIDENCE = {
    "candidate": {"experience": []},
    "projects": [],
    "matched_skills": [],
    "listed_skills": [],
    "unsupported_skills": [],
    "job_context": {"responsibilities": []},
}


def _cover(body: str) -> str:
    filler = "I value thoughtful collaboration and careful problem solving while learning from experienced teammates."
    return f"Dear Hiring Team,\n\n{body} {filler}\n\nSincerely,\nSynthetic Candidate"


@pytest.mark.parametrize("writer", ["application_answer", "cover_letter"])
@pytest.mark.parametrize(
    ("text", "evidence", "rule"),
    [
        (
            "I have experience with Docker and enjoy building reliable tools.",
            {**BASE_EVIDENCE, "unsupported_skills": ["Docker"]},
            "missing_skill_claimed_as_expertise",
        ),
        (
            "I have experience with Python and enjoy building reliable tools.",
            {**BASE_EVIDENCE, "listed_skills": ["Python"]},
            "listed_skill_upgraded_to_expertise",
        ),
        (
            "I improved service reliability by 23% through careful work.",
            BASE_EVIDENCE,
            "unsupported_numeric_claim",
        ),
        (
            "I learn new tools quickly and look forward to this opportunity.",
            BASE_EVIDENCE,
            "unsupported_claim_marker",
        ),
        (
            "In my Inventory Dashboard, I developed an autonomous trading prediction engine for investment teams.",
            {**BASE_EVIDENCE, "projects": [{"name": "Inventory Dashboard", "description": "Monitored stock levels for a small shop", "technologies": []}]},
            "project_claim_low_evidence_overlap",
        ),
        (
            "My experience includes Python, and I would welcome the chance to contribute.",
            BASE_EVIDENCE,
            "unverified_known_skill",
        ),
        (
            "In my Northstar Analytics Platform, I built thoughtful solutions for users.",
            BASE_EVIDENCE,
            "unrecognized_named_project",
        ),
        (
            "My experience includes building generative AI workflows for teams.",
            {**BASE_EVIDENCE, "job_context": {"responsibilities": ["Build generative AI workflows for internal teams"]}},
            "unsupported_job_responsibility_claim",
        ),
    ],
)
def test_skill_and_numeric_rejections_have_rule_diagnostics(writer, text, evidence, rule):
    if writer == "application_answer":
        diagnostic = diagnose_llm_answer_validation(text, 180, evidence)
        issue = _llm_answer_validation_issue(text, 180, evidence)
    else:
        text = _cover(text)
        diagnostic = diagnose_llm_cover_letter_validation(text, "short", evidence)
        issue = _llm_cover_letter_validation_issue(text, "short", evidence)
    assert issue == "unsupported_claims"
    assert diagnostic[0]["rejected_rule_id"] == rule
    assert diagnostic[0]["writer"] == writer
    assert diagnostic[0]["evidence_category"]
    assert diagnostic[0]["safe_explanation"]


@pytest.mark.parametrize("writer", ["application_answer", "cover_letter"])
def test_learning_goal_and_plain_listed_skill_remain_accepted(writer):
    evidence = {**BASE_EVIDENCE, "unsupported_skills": ["Docker"], "listed_skills": ["Python"]}
    text = "I am learning Docker and have listed Python among my skills. I look forward to developing through practical work."
    if writer == "cover_letter":
        text = _cover(text)
        issue = _llm_cover_letter_validation_issue(text, "short", evidence)
        diagnostics = diagnose_llm_cover_letter_validation(text, "short", evidence)
    else:
        issue = _llm_answer_validation_issue(text, 180, evidence)
        diagnostics = diagnose_llm_answer_validation(text, 180, evidence)
    assert issue is None
    assert diagnostics == []


@pytest.mark.parametrize("writer", ["application_answer", "cover_letter"])
def test_rule_specific_format_rejections(writer):
    if writer == "application_answer":
        cases = [("too short", 180, "minimum_output_length"), ("I can help [your name] with this internship and learn from the team.", 180, "blocked_or_malformed_text")]
        for text, limit, expected in cases:
            assert diagnose_llm_answer_validation(text, limit)[0]["rejected_rule_id"] == expected
        long = "word " * 260
        assert diagnose_llm_answer_validation(long, 100)[0]["rejected_rule_id"] == "output_word_limit"
    else:
        assert diagnose_llm_cover_letter_validation("x" * 10, "short")[0]["rejected_rule_id"] == "minimum_output_length"
        assert diagnose_llm_cover_letter_validation("Dear Hiring Team,\n\n" + "word " * 30, "short")[0]["rejected_rule_id"] == "missing_cover_letter_signature"
        placeholder = _cover("I am interested in contributing to your team.").replace("Synthetic Candidate", "Candidate")
        assert diagnose_llm_cover_letter_validation(placeholder, "short")[0]["rejected_rule_id"] == "placeholder_signature"
        assert diagnose_llm_cover_letter_validation("Hello,\n\n" + _cover("I am interested in contributing to your team.").split("\n\n", 1)[1], "short")[0]["rejected_rule_id"] == "missing_cover_letter_opening"


def test_diagnostic_logs_do_not_include_candidate_or_output_text(caplog):
    from app.agents.application_writer_agent import _log_validation_diagnostics
    from app.agents.writer_grounding import validation_diagnostic

    _log_validation_diagnostics([validation_diagnostic("application_answer", "missing_skill_claimed_as_expertise")])
    message = caplog.text
    assert "missing_skill_claimed_as_expertise" in message
    assert "missing_requirement" in message
    assert "Docker" not in message
    assert "I have experience" not in message


def test_report_writes_immediately_separates_usage_and_redacts_synthetic_text(tmp_path):
    store = EvaluationReportStore(tmp_path)
    metadata = {
        "fixture_id": "synthetic-strong-01",
        "is_synthetic": True,
        "writer": "application_answer",
        "request_count": 1,
        "response_status": 200,
        "latency_ms": 42.5,
        "generation_source": "mock_provider",
        "fallback_reason": "validation_unsupported_claims",
        "rejected_rule_ids": ["unsupported_numeric_claim"],
        "provider_token_usage": {"input_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        "token_estimate": estimate_prompt_tokens("sys", "user"),
        "resume_text": "must not persist",
        "secret": "must not persist",
    }
    paths = store.append_result(metadata, {"accepted": False, "text": "Synthetic contact test@example.com +1 415 555 0100", "rejected_rule_ids": ["unsupported_numeric_claim"]})
    event = json.loads((tmp_path / "evaluation-events.jsonl").read_text().splitlines()[0])
    writing = json.loads((tmp_path / "synthetic-writing.jsonl").read_text().splitlines()[0])
    assert event["provider_token_usage"]["total_tokens"] == 20
    assert event["token_estimate"]["method"] == "regex_word_punct_v1"
    assert "resume_text" not in event and "secret" not in event
    assert "test@example.com" not in writing["text"]
    assert "+1 415 555 0100" not in writing["text"]
    assert paths["metadata"].endswith("evaluation-events.jsonl")
    assert paths["synthetic_writing"].endswith("synthetic-writing.jsonl")


def test_report_rejects_full_writing_for_non_synthetic_fixture(tmp_path):
    with pytest.raises(ValueError):
        EvaluationReportStore(tmp_path).append_result({"fixture_id": "real-user-1", "is_synthetic": False}, {"text": "private"})


def test_report_keeps_first_result_after_interruption_and_records_exception(tmp_path, monkeypatch):
    store = EvaluationReportStore(tmp_path)
    store.append_result({"request_id": "first", "request_count": 1, "response_status": 200})
    def interrupt(*_args, **_kwargs):
        raise RuntimeError("simulated interruption")
    monkeypatch.setattr(store, "_append_jsonl", interrupt)
    with pytest.raises(RuntimeError):
        store.append_result({"request_id": "interrupted", "request_count": 1, "response_status": "exception", "fallback_reason": "provider_exception"})
    lines = (tmp_path / "evaluation-events.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["request_id"] == "first"
    resumed = EvaluationReportStore(tmp_path)
    resumed.append_result({"request_id": "after", "request_count": 1, "response_status": "exception", "latency_ms": 7.0, "fallback_reason": "provider_exception"})
    assert len((tmp_path / "evaluation-events.jsonl").read_text().splitlines()) == 2


def test_mocked_provider_request_usage_and_exception_are_reportable(tmp_path, monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {}

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "Synthetic response for testing."}}], "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16}}

    calls = []
    def fake_post(*_args, **_kwargs):
        calls.append(1)
        return FakeResponse()

    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "synthetic-test-key")
    monkeypatch.setattr(settings, "groq_max_retries", 0)
    monkeypatch.setattr("httpx.post", fake_post)
    result = LLMService().generate_text("synthetic system", "synthetic user")
    assert len(calls) == 1
    assert result["usage"] == {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16}

    store = EvaluationReportStore(tmp_path)
    store.append_result({
        "fixture_id": "synthetic-provider-01", "is_synthetic": True, "writer": "application_answer",
        "request_count": len(calls), "response_status": 200,
        "latency_ms": result["generation_time_ms"], "generation_source": result["provider"],
        "fallback_reason": None, "provider_token_usage": {
            "input_tokens": result["usage"]["prompt_tokens"],
            "completion_tokens": result["usage"]["completion_tokens"],
            "total_tokens": result["usage"]["total_tokens"],
        }, "token_estimate": estimate_prompt_tokens("synthetic system", "synthetic user"),
    })

    def raising_post(*_args, **_kwargs):
        calls.append(1)
        raise RuntimeError("mock transport exception")
    monkeypatch.setattr("httpx.post", raising_post)
    failed = LLMService().generate_text("synthetic system", "synthetic user")
    assert len(calls) == 2
    assert failed["used_fallback"] is True
    store.append_result({
        "fixture_id": "synthetic-provider-exception", "is_synthetic": True, "writer": "application_answer",
        "request_count": 1, "response_status": "exception", "latency_ms": failed["generation_time_ms"],
        "generation_source": "rule_based", "fallback_reason": failed["error"]["fallback_reason"],
        "provider_token_usage": None, "token_estimate": estimate_prompt_tokens("synthetic system", "synthetic user"),
    })
    reports = [json.loads(line) for line in (tmp_path / "evaluation-events.jsonl").read_text().splitlines()]
    assert reports[0]["provider_token_usage"]["input_tokens"] == 11
    assert reports[1]["provider_token_usage"] == {"completion_tokens": None, "input_tokens": None, "total_tokens": None}
