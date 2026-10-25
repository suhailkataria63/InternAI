import json

import pytest

from app.agents.application_writer_agent import generate_application_answer
from app.agents.cover_letter_agent import generate_cover_letter
from app.config import Settings, settings
from app.services import evaluation_report
from app.services.llm_service import LLMService


def _context(run="synthetic-run-01", request="synthetic-request-01", fixture="synthetic-strong-01"):
    return {"run_id": run, "request_id": request, "fixture_id": fixture, "is_synthetic": True, "profile_label": "strong"}


def _configure(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "llm_model", "mock-groq-model")
    monkeypatch.setattr(settings, "groq_api_key", "synthetic-no-network-key")
    monkeypatch.setattr(settings, "groq_evaluation_mode", True)
    monkeypatch.setattr(settings, "groq_evaluation_request_budget", 6)
    monkeypatch.setattr(settings, "groq_evaluation_token_budget", 12000)
    monkeypatch.setattr(settings, "groq_max_retries", 1)
    monkeypatch.setattr(evaluation_report, "DEFAULT_REPORT_DIR", tmp_path)


class _Response:
    def __init__(self, content, status=200, usage=None):
        self.status_code = status
        self.headers = {}
        self.content = content
        self.usage = usage

    def json(self):
        payload = {"choices": [{"message": {"content": self.content}}]}
        if self.usage is not None:
            payload["usage"] = self.usage
        return payload


def _events(path):
    target = path / "evaluation-events.jsonl"
    return [json.loads(line) for line in target.read_text().splitlines()]


@pytest.mark.parametrize(
    ("writer", "content", "response_field"),
    [
        ("application_answer", '{"answer":"I am interested in contributing to thoughtful team projects. I value careful work, clear communication, and learning from experienced colleagues."}', "generated_answer"),
        ("cover_letter", '{"cover_letter":"Dear Hiring Team,\\n\\nI am interested in contributing to thoughtful team projects. I value careful work, clear communication, and learning from experienced colleagues. I would welcome the chance to learn from the team and support its goals.\\n\\nSincerely,\\nSynthetic Candidate"}', "cover_letter"),
    ],
)
def test_writer_paths_persist_attempt_before_call_and_synthetic_result(monkeypatch, tmp_path, writer, content, response_field):
    _configure(monkeypatch, tmp_path)
    calls = []

    def fake_post(*_args, **_kwargs):
        rows = _events(tmp_path)
        assert rows[-1]["event_type"] == "attempt"
        assert rows[-1]["response_status"] == "pending"
        calls.append(1)
        return _Response(content, usage={"prompt_tokens": 40, "completion_tokens": 25, "total_tokens": 65})

    monkeypatch.setattr("httpx.post", fake_post)
    common = {
        "resume_profile": {}, "job_profile": {}, "match_result": {}, "skill_gap_result": {},
    }
    if writer == "application_answer":
        result = generate_application_answer(**common, application_question="Why are you interested?", evaluation_context=_context())
    else:
        result = generate_cover_letter(**common, evaluation_context=_context())
    assert len(calls) == 1
    assert result["generation_source"] == "llm"
    assert result[response_field]
    rows = _events(tmp_path)
    assert [row["event_type"] for row in rows] == ["attempt", "provider_result", "writer_result"]
    assert rows[0]["request_id"] == rows[1]["request_id"] == rows[2]["request_id"] == "synthetic-request-01"
    assert rows[1]["provider_token_usage"]["total_tokens"] == 65
    assert rows[1]["provider"] == "groq" and rows[1]["model"] == "mock-groq-model"
    assert rows[2]["rejected_rule_ids"] == []
    saved = json.loads((tmp_path / "synthetic-writing.jsonl").read_text().splitlines()[0])
    assert saved["accepted"] is True and len(saved["text"]) > 50
    if writer == "cover_letter":
        assert "Synthetic Candidate" in saved["text"]


def test_validator_rejection_is_logged_with_rule_and_synthetic_output(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr("httpx.post", lambda *_a, **_k: _Response(
        '{"answer":"I improved team productivity by 87%. I am interested in contributing to thoughtful projects and learning from colleagues."}',
        usage={"prompt_tokens": 20, "completion_tokens": 18, "total_tokens": 38},
    ))
    result = generate_application_answer(
        resume_profile={}, job_profile={}, match_result={}, skill_gap_result={},
        application_question="Why are you interested?", evaluation_context=_context(request="synthetic-reject"),
    )
    assert result["used_fallback"] is True
    writer_event = _events(tmp_path)[-1]
    assert writer_event["rejected_rule_ids"] == ["unsupported_numeric_claim"]
    saved = json.loads((tmp_path / "synthetic-writing.jsonl").read_text().splitlines()[0])
    assert saved["accepted"] is False and "87%" in saved["text"]


def test_provider_error_is_recorded_without_retry(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr("httpx.post", lambda *_a, **_k: (calls.append(1) or _Response("", status=503)))
    result = LLMService().generate_text("synthetic system", "synthetic user", evaluation_context=_context())
    assert result["used_fallback"] is True
    assert len(calls) == 1
    rows = _events(tmp_path)
    assert rows[0]["event_type"] == "attempt" and rows[1]["event_type"] == "provider_result"
    assert rows[1]["response_status"] == 503
    assert rows[1]["fallback_reason"] == "provider_http_transient"
    assert rows[1]["provider_token_usage"]["total_tokens"] is None


def test_interrupted_call_leaves_pending_reservation_and_stops_recovery(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    calls = []
    def interrupt(*_args, **_kwargs):
        calls.append(1)
        raise KeyboardInterrupt()
    monkeypatch.setattr("httpx.post", interrupt)
    with pytest.raises(KeyboardInterrupt):
        LLMService().generate_text("synthetic system", "synthetic user", evaluation_context=_context())
    assert _events(tmp_path)[0]["response_status"] == "pending"
    monkeypatch.setattr("httpx.post", lambda *_a, **_k: (calls.append(1) or _Response("{}", usage={"total_tokens": 1})))
    stopped = LLMService().generate_text("synthetic system", "synthetic user", evaluation_context=_context(request="synthetic-next"))
    assert stopped["used_fallback"] is True
    assert len(calls) == 1


def test_missing_usage_is_unknown_and_stops_next_request(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr("httpx.post", lambda *_a, **_k: (calls.append(1) or _Response("ok", usage=None)))
    first = LLMService().generate_text("synthetic system", "synthetic user", evaluation_context=_context())
    assert first["used_fallback"] is False
    rows = _events(tmp_path)
    assert rows[1]["actual_usage_known"] is False
    assert rows[1]["provider_token_usage"]["total_tokens"] is None
    second = LLMService().generate_text("synthetic system", "synthetic user", evaluation_context=_context(request="synthetic-next"))
    assert second["used_fallback"] is True
    assert len(calls) == 1


def test_synthetic_output_redacts_credentials(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    store = evaluation_report.EvaluationReportStore(tmp_path)
    store.append_result({"fixture_id": "synthetic-redaction", "is_synthetic": True, "writer": "application_answer"}, {
        "accepted": True,
        "text": "Authorization: Bearer abc.def-secret API_KEY=supersecretvalue",
    })
    saved = (tmp_path / "synthetic-writing.jsonl").read_text()
    assert "abc.def-secret" not in saved
    assert "supersecretvalue" not in saved


@pytest.mark.parametrize(("request_budget", "token_budget"), [(0, 12000), (6, 1)])
def test_preflight_budget_denial_makes_no_provider_call(monkeypatch, tmp_path, request_budget, token_budget):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "groq_evaluation_request_budget", request_budget)
    monkeypatch.setattr(settings, "groq_evaluation_token_budget", token_budget)
    calls = []
    monkeypatch.setattr("httpx.post", lambda *_a, **_k: (calls.append(1) or _Response("ok", usage={"total_tokens": 1})))
    result = LLMService().generate_text("synthetic system", "synthetic user", evaluation_context=_context())
    assert result["used_fallback"] is True
    assert calls == []
    assert not (tmp_path / "evaluation-events.jsonl").exists()


def test_configured_report_directory_round_trips_synthetic_events(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    configured = tmp_path / "authorized-evaluation-reports"
    monkeypatch.setattr(settings, "groq_evaluation_report_dir", str(configured))
    store = evaluation_report.EvaluationReportStore()
    calls = []
    monkeypatch.setattr(
        "httpx.post",
        lambda *_args, **_kwargs: (calls.append(1) or _Response(
            '{"answer":"Synthetic mock output is sufficiently long for a persistence check."}',
            usage={"prompt_tokens": 12, "completion_tokens": 9, "total_tokens": 21},
        )),
    )
    context = _context(run="synthetic-configured-dir-run", request="synthetic-configured-dir-request")
    result = LLMService().generate_text(
        'Return JSON with exactly one key: {"answer":"..."}.',
        "Synthetic fixture only.",
        evaluation_context=context,
    )
    store.append_writer_result(
        context,
        writer="application_answer",
        provider="groq",
        model="mock-groq-model",
        latency_ms=1.5,
        generation_source="groq",
        fallback_reason=None,
        rejected_rule_ids=[],
        synthetic_text="Synthetic fixture output only.",
        accepted=True,
    )

    events_path = configured / "evaluation-events.jsonl"
    writing_path = configured / "synthetic-writing.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    writing = [json.loads(line) for line in writing_path.read_text().splitlines()]
    assert calls == [1]
    assert result["usage"]["total_tokens"] == 21
    assert [event["event_type"] for event in events] == ["attempt", "provider_result", "writer_result"]
    assert all(event["run_id"] == "synthetic-configured-dir-run" for event in events)
    assert events[1]["provider_token_usage"]["total_tokens"] == 21
    assert writing[0]["text"] == "Synthetic fixture output only."
    assert not (tmp_path / "evaluation-events.jsonl").exists()


def test_configured_report_directory_rejects_relative_path(monkeypatch):
    monkeypatch.setattr(settings, "groq_evaluation_report_dir", "relative/reports")
    with pytest.raises(ValueError, match="absolute path"):
        evaluation_report.EvaluationReportStore()


def test_report_directory_setting_reads_environment_alias(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_EVALUATION_REPORT_DIR", str(tmp_path / "authorized"))
    configured = Settings(_env_file=None)
    assert configured.groq_evaluation_report_dir == str(tmp_path / "authorized")
