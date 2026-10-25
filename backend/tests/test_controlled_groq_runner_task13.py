import json as json_lib

import pytest
import httpx

import run_controlled_groq_evaluation as runner
from app.config import settings
from app.services.evaluation_report import EvaluationReportStore


def test_report_storage_preflight_uses_disposable_synthetic_records(tmp_path):
    runner.verify_report_storage(EvaluationReportStore(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_network_preflight_checks_dns_and_unauthenticated_https(monkeypatch):
    calls = []
    monkeypatch.setattr(runner.socket, "getaddrinfo", lambda host, port, **kwargs: [(host, port)])

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return type("Response", (), {"status_code": 401})()

    monkeypatch.setattr(runner.httpx, "get", fake_get)
    result = runner.verify_network_preflight()
    assert result == {"dns_addresses": 1, "https_status": 401}
    assert calls == [("https://api.groq.com/", {
        "headers": {"Authorization": ""}, "timeout": 8.0, "follow_redirects": False,
    })]


def test_network_preflight_stops_on_dns_failure(monkeypatch):
    calls = []

    def fail_dns(*_args, **_kwargs):
        raise OSError("synthetic DNS failure")

    monkeypatch.setattr(runner.socket, "getaddrinfo", fail_dns)
    monkeypatch.setattr(runner.httpx, "get", lambda *_args, **_kwargs: calls.append(1))
    with pytest.raises(OSError, match="synthetic DNS failure"):
        runner.verify_network_preflight()
    assert calls == []


def test_request_reservations_and_unknown_usage_stop_safely():
    assert runner.assert_budget_reservation("s", "u", 100, consumed=0) == 202
    with pytest.raises(runner.EvaluationStopped, match="cannot be conservatively reserved"):
        runner.assert_budget_reservation("s", "u", 4000, consumed=1)
    with pytest.raises(runner.EvaluationStopped, match="usage is unknown"):
        runner.complete_usage({"actual_usage_known": False, "provider_token_usage": None})


def test_application_prompt_reservation_fits_task16_cap():
    system, user = runner.build_application_answer_prompt(
        runner.RESUME, runner.JOB, runner.MATCH, runner.SKILL_GAP,
        runner.APPLICATION_QUESTION, "professional", 180,
    )
    reserved = runner.assert_budget_reservation(system, user, 350, consumed=0)
    assert runner.MAX_REQUESTS == 1
    assert runner.MAX_PROVIDER_TOKENS == 2000
    assert reserved <= runner.MAX_PROVIDER_TOKENS


def test_process_settings_enforce_zero_retries_and_budgets(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "synthetic-test-key")
    monkeypatch.setattr(settings, "groq_evaluation_mode", False)
    monkeypatch.setattr(settings, "groq_max_retries", 1)
    monkeypatch.setattr(settings, "groq_evaluation_request_budget", 6)
    monkeypatch.setattr(settings, "groq_evaluation_token_budget", 12000)
    runner.configure_controlled_mode()
    assert settings.groq_evaluation_mode is True
    assert settings.groq_max_retries == 0
    assert settings.groq_evaluation_request_budget == 1
    assert settings.groq_evaluation_token_budget == 2000


def test_report_readback_selects_only_the_unique_run(tmp_path):
    store = EvaluationReportStore(tmp_path)
    first = {"run_id": "task13-run-a", "request_id": "task13-req-a", "fixture_id": "synthetic-task13-a", "profile_label": "strong", "is_synthetic": True}
    second = {"run_id": "task13-run-b", "request_id": "task13-req-b", "fixture_id": "synthetic-task13-b", "profile_label": "strong", "is_synthetic": True}
    store.append_result({**first, "event_type": "attempt"})
    store.append_result({**second, "event_type": "attempt"}, {"text": "Synthetic B only.", "accepted": True})
    events, writings = runner.records_for_run(store, "task13-run-b")
    assert [row["request_id"] for row in events] == ["task13-req-b"]
    assert writings[0]["text"] == "Synthetic B only."


def test_full_runner_uses_one_application_mock_and_persists_reports(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "configured-reports"
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "llm_model", "mock-groq-model")
    monkeypatch.setattr(settings, "groq_api_key", "synthetic-no-network-key")
    monkeypatch.setattr(settings, "groq_evaluation_report_dir", str(report_dir))
    monkeypatch.setattr(settings, "groq_evaluation_mode", False)
    monkeypatch.setattr(settings, "groq_max_retries", 1)
    monkeypatch.setattr(settings, "groq_evaluation_request_budget", 6)
    monkeypatch.setattr(settings, "groq_evaluation_token_budget", 12000)
    monkeypatch.setattr(runner, "verify_network_preflight", lambda: {"dns_addresses": 1, "https_status": 401})
    answer = "In my Study Planner project, I built a study session tracker with a React interface and FastAPI endpoints backed by PostgreSQL. Python, SQL, and FastAPI are listed skills."
    calls = []

    def mocked_post(url, *, headers, json, timeout):
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        assert headers["Authorization"] == "Bearer synthetic-no-network-key"
        assert timeout == 30
        assert "role_title" in json["messages"][1]["content"]
        assert "Software Engineering Intern" in json["messages"][1]["content"]
        assert "Northstar Labs" in json["messages"][1]["content"]
        calls.append("application_answer")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json_lib.dumps({"answer": answer})}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 50, "total_tokens": 90},
        })

    monkeypatch.setattr(runner.httpx, "post", mocked_post)
    assert runner.run_evaluation(writer="application_answer") == 0
    captured = capsys.readouterr().out
    assert calls == ["application_answer"]
    assert '"provider_tokens_total": 90' in captured
    events = [json_lib.loads(line) for line in (report_dir / "evaluation-events.jsonl").read_text().splitlines()]
    writings = [json_lib.loads(line) for line in (report_dir / "synthetic-writing.jsonl").read_text().splitlines()]
    assert sum(event["event_type"] == "attempt" for event in events) == 1
    assert sum(event["event_type"] == "provider_result" for event in events) == 1
    assert sum(event["event_type"] == "writer_result" for event in events) == 1
    assert len(writings) == 1
    assert writings[0]["text"] == answer


def test_runner_rejects_unselected_writer_before_any_preflight_or_request():
    with pytest.raises(runner.EvaluationStopped, match="Unsupported writer selection"):
        runner.run_evaluation(writer="cover_letter")
