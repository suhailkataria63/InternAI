"""Run one bounded, synthetic application-answer evaluation from a local terminal.

This entry point performs report-storage, DNS, and unauthenticated HTTPS
preflight checks before making exactly one application-answer call. It is
intended for manual execution on a host with authorized Groq access.
"""

from __future__ import annotations

import argparse
import json
import socket
import tempfile
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.agents.application_writer_agent import (
    build_application_answer_prompt,
    generate_application_answer,
)
from app.config import settings
from app.services.evaluation_report import EvaluationReportStore


GROQ_API_HOST = "api.groq.com"
GROQ_CONNECTIVITY_URL = f"https://{GROQ_API_HOST}/"
MAX_REQUESTS = 1
MAX_PROVIDER_TOKENS = 2000
MAX_RETRIES = 0
RESERVATION_SAFETY_MARGIN = 100
SUPPORTED_WRITERS = ("application_answer",)

# Exact synthetic fixture used by the Task 07/09 grounding evaluation.
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
    # Writer evidence builders consume these normalized keys. Keep the source
    # fixture's original fields while passing the same values through explicitly.
    "role_title": "Software Engineering Intern",
    "company_name": "Northstar Labs",
    "description": "Build backend APIs, write tests, and improve data-driven tools.",
    "responsibilities": ["Build backend APIs", "Write tests", "Improve data-driven tools"],
    "required_skills": ["Python", "SQL", "FastAPI"],
}
MATCH = {"matched_skills": ["Python", "SQL", "FastAPI", "React"], "missing_skills": ["AWS"]}
SKILL_GAP = {"missing_skills": ["AWS"]}
APPLICATION_QUESTION = "Describe a project relevant to reliable software APIs."


class EvaluationStopped(RuntimeError):
    """The run cannot safely proceed under its request or token limits."""


def configure_controlled_mode() -> None:
    if (settings.llm_provider or "").strip().lower() != "groq":
        raise EvaluationStopped("LLM_PROVIDER must be groq in the local .env configuration.")
    if not settings.groq_api_key:
        raise EvaluationStopped("GROQ_API_KEY is not configured.")
    # Restrict this process only; do not edit .env or persist these settings.
    settings.groq_evaluation_mode = True
    settings.groq_max_retries = MAX_RETRIES
    settings.groq_evaluation_request_budget = MAX_REQUESTS
    settings.groq_evaluation_token_budget = MAX_PROVIDER_TOKENS


def verify_report_storage(report_store: EvaluationReportStore) -> None:
    """Exercise create/append/fsync/readback in a disposable child directory."""
    report_store.report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".groq-preflight-", dir=report_store.report_dir) as temp_dir:
        check_store = EvaluationReportStore(temp_dir)
        run_id = f"synthetic-storage-check-{uuid.uuid4()}"
        common = {
            "run_id": run_id,
            "fixture_id": "synthetic-preflight-check",
            "profile_label": "mock",
            "is_synthetic": True,
        }
        check_store.append_result(
            {**common, "request_id": str(uuid.uuid4()), "event_type": "mock_preflight_attempt"}
        )
        check_store.append_result(
            {**common, "request_id": str(uuid.uuid4()), "event_type": "mock_preflight_result"},
            {"text": "Synthetic storage preflight only.", "accepted": True, "rejected_rule_ids": []},
        )
        events_path = Path(temp_dir) / "evaluation-events.jsonl"
        writing_path = Path(temp_dir) / "synthetic-writing.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        writings = [json.loads(line) for line in writing_path.read_text(encoding="utf-8").splitlines()]
        matching_events = [row for row in events if row.get("run_id") == run_id]
        matching_writings = [row for row in writings if row.get("run_id") == run_id]
        if len(matching_events) != 2 or len(matching_writings) != 1:
            raise EvaluationStopped("Report storage preflight did not read back all synthetic records.")
        if matching_writings[0].get("text") != "Synthetic storage preflight only.":
            raise EvaluationStopped("Report storage preflight text did not round-trip.")


def verify_network_preflight() -> dict[str, Any]:
    """Check DNS and HTTPS without sending credentials or using a model API."""
    addresses = socket.getaddrinfo(GROQ_API_HOST, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise EvaluationStopped(f"DNS returned no addresses for {GROQ_API_HOST}.")
    try:
        # The root URL is only an unauthenticated TLS/HTTPS reachability check.
        # It is not a chat-completions endpoint and sends no Groq API key.
        response = httpx.get(
            GROQ_CONNECTIVITY_URL,
            headers={"Authorization": ""},
            timeout=8.0,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise EvaluationStopped(f"Unauthenticated Groq-host HTTPS preflight failed: {type(exc).__name__}.") from None
    return {"dns_addresses": len(addresses), "https_status": response.status_code}


def conservative_reservation(system_prompt: str, user_prompt: str, max_tokens: int) -> int:
    prompt_bytes = len(system_prompt.encode("utf-8")) + len(user_prompt.encode("utf-8"))
    return prompt_bytes + max_tokens + RESERVATION_SAFETY_MARGIN


def assert_budget_reservation(system_prompt: str, user_prompt: str, max_tokens: int, consumed: int) -> int:
    reserved = conservative_reservation(system_prompt, user_prompt, max_tokens)
    if consumed + reserved > MAX_PROVIDER_TOKENS:
        raise EvaluationStopped(
            f"Next request cannot be conservatively reserved: {consumed} actual + {reserved} reserved > {MAX_PROVIDER_TOKENS}."
        )
    return reserved


def records_for_run(report_store: EvaluationReportStore, run_id: str) -> tuple[list[dict], list[dict]]:
    events_path = report_store.report_dir / "evaluation-events.jsonl"
    writing_path = report_store.report_dir / "synthetic-writing.jsonl"
    events = report_store._read_events(events_path)
    writings = []
    if writing_path.exists():
        writings = [json.loads(line) for line in writing_path.read_text(encoding="utf-8").splitlines()]
    return (
        [row for row in events if row.get("run_id") == run_id],
        [row for row in writings if row.get("run_id") == run_id],
    )


def complete_usage(provider_result: dict) -> dict[str, int]:
    usage = provider_result.get("provider_token_usage")
    if not provider_result.get("actual_usage_known") or not isinstance(usage, dict):
        raise EvaluationStopped("Provider token usage is unknown; stopping before another request.")
    fields = ("input_tokens", "completion_tokens", "total_tokens")
    if any(not isinstance(usage.get(field), int) or usage[field] < 0 for field in fields):
        raise EvaluationStopped("Provider input/completion/total usage is incomplete; stopping before another request.")
    return {field: usage[field] for field in fields}


def report_writer_result(report_store: EvaluationReportStore, run_id: str, request_id: str, label: str) -> tuple[dict, dict, dict]:
    events, writings = records_for_run(report_store, run_id)
    attempt = next((row for row in events if row.get("request_id") == request_id and row.get("event_type") == "attempt"), None)
    provider = next((row for row in events if row.get("request_id") == request_id and row.get("event_type") == "provider_result"), None)
    writer = next((row for row in events if row.get("request_id") == request_id and row.get("event_type") == "writer_result"), None)
    writing = next((row for row in writings if row.get("request_id") == request_id), None)
    if not attempt or not provider or not writer or not writing:
        raise EvaluationStopped(f"{label}: one or more durable evaluation records are missing.")
    return provider, writer, writing


def usage_for_display(provider_result: dict) -> dict[str, int | None]:
    raw = provider_result.get("provider_token_usage") or {}
    return {
        field: raw.get(field) if isinstance(raw.get(field), int) else None
        for field in ("input_tokens", "completion_tokens", "total_tokens")
    }


def print_writer_report(
    label: str,
    provider: dict,
    writer: dict,
    writing: dict,
    usage: dict[str, int | None],
) -> None:
    summary = {
        "writer": label,
        "http_status": provider.get("response_status"),
        "latency_ms": provider.get("latency_ms"),
        "provider_tokens": usage,
        "generation_source": writer.get("generation_source"),
        "fallback_reason": writer.get("fallback_reason"),
        "rejected_rule_ids": writer.get("rejected_rule_ids", []),
        "accepted": writing.get("accepted"),
        "writing": writing.get("text"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def run_evaluation(writer: str = "application_answer") -> int:
    if writer not in SUPPORTED_WRITERS:
        raise EvaluationStopped(f"Unsupported writer selection: {writer}.")
    configure_controlled_mode()
    report_store = EvaluationReportStore()
    verify_report_storage(report_store)
    connectivity = verify_network_preflight()
    print(json.dumps({
        "preflight": "passed",
        "report_directory": str(report_store.report_dir),
        "report_storage": "create/append/fsync/readback passed; temporary mock records removed",
        "dns_addresses": connectivity["dns_addresses"],
        "unauthenticated_https_status": connectivity["https_status"],
        "model": settings.llm_model,
        "api_key_loaded": True,
        "request_limit": MAX_REQUESTS,
        "token_limit": MAX_PROVIDER_TOKENS,
        "retries": MAX_RETRIES,
    }, ensure_ascii=False, indent=2))

    run_id = f"task16-{uuid.uuid4()}"
    request_id = str(uuid.uuid4())

    app_system, app_user = build_application_answer_prompt(
        RESUME, JOB, MATCH, SKILL_GAP, APPLICATION_QUESTION, "professional", 180,
    )
    # The writer caps this request at 350 completion tokens for the 180-word
    # answer. The UTF-8 prompt-byte bound plus this cap and margin must fit.
    assert_budget_reservation(app_system, app_user, 350, consumed=0)
    app_context = {
        "run_id": run_id,
        "request_id": request_id,
        "fixture_id": "synthetic-task07-strong",
        "profile_label": "strong",
        "is_synthetic": True,
    }
    generate_application_answer(
        RESUME, JOB, MATCH, SKILL_GAP, APPLICATION_QUESTION,
        tone="professional", word_limit=180, evaluation_context=app_context,
    )
    provider, writer_result, writing = report_writer_result(report_store, run_id, request_id, writer)
    print_writer_report(writer, provider, writer_result, writing, usage_for_display(provider))
    usage = complete_usage(provider)
    if usage["total_tokens"] > MAX_PROVIDER_TOKENS:
        raise EvaluationStopped("Application request exceeded the total provider-token limit.")
    if provider.get("response_status") != 200 or writer_result.get("fallback_reason"):
        raise EvaluationStopped("Application provider response failed or validation used fallback; stopping after this request.")
    print(json.dumps({
        "run_id": run_id,
        "requests": 1,
        "provider_tokens_total": usage["total_tokens"],
        "report_directory": str(report_store.report_dir),
        "events_file": str(report_store.report_dir / "evaluation-events.jsonl"),
        "synthetic_writing_file": str(report_store.report_dir / "synthetic-writing.jsonl"),
        "records_read_back": True,
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer", choices=SUPPORTED_WRITERS, default="application_answer")
    args = parser.parse_args()
    try:
        return run_evaluation(writer=args.writer)
    except (EvaluationStopped, OSError, ValueError) as exc:
        print(f"Evaluation stopped safely: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
