"""Append-only local reports for synthetic writing evaluations.

This module never accepts resume or prompt fields. Metadata uses an allowlist,
and full writing is only accepted for explicitly named synthetic fixtures.
"""

import json
import os
import re
import fcntl
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


DEFAULT_REPORT_DIR = Path(__file__).resolve().parents[2] / ".local-evaluation"
METADATA_FIELDS = {
    "run_id",
    "request_id",
    "fixture_id",
    "is_synthetic",
    "writer",
    "request_count",
    "response_status",
    "latency_ms",
    "generation_source",
    "fallback_reason",
    "rejected_rule_ids",
    "provider_token_usage",
    "token_estimate",
    "event_type",
    "profile_label",
    "provider",
    "model",
    "attempt_index",
    "reserved_tokens",
    "actual_usage_known",
}
TOKEN_FIELDS = {"input_tokens", "completion_tokens", "total_tokens"}


class EvaluationBudgetError(RuntimeError):
    """Raised when an evaluation cannot safely reserve another provider call."""


def _normalize_provider_usage(usage: dict[str, Any] | None) -> dict[str, int | None]:
    usage = usage if isinstance(usage, dict) else {}
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    completion_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    total_tokens = usage.get("total_tokens")
    normalized = {
        "input_tokens": input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None,
        "completion_tokens": completion_tokens if isinstance(completion_tokens, int) and completion_tokens >= 0 else None,
        "total_tokens": total_tokens if isinstance(total_tokens, int) and total_tokens >= 0 else None,
    }
    if normalized["total_tokens"] is None and normalized["input_tokens"] is not None and normalized["completion_tokens"] is not None:
        normalized["total_tokens"] = normalized["input_tokens"] + normalized["completion_tokens"]
    return normalized


def prepare_evaluation_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if context is None:
        return None
    if not isinstance(context, dict):
        raise ValueError("Evaluation context must be a mapping.")
    prepared = dict(context)
    prepared.setdefault("run_id", str(uuid.uuid4()))
    prepared.setdefault("request_id", str(uuid.uuid4()))
    # Validate before any prompt is sent or report is written.
    EvaluationReportStore()._validate_evaluation_context(prepared)
    return prepared


class EvaluationReportStore:
    """Persist one JSONL event at a time, fsyncing each result before returning."""

    def __init__(self, report_dir: str | Path | None = None) -> None:
        configured_dir = report_dir if report_dir is not None else settings.groq_evaluation_report_dir
        self.report_dir = Path(configured_dir).expanduser() if configured_dir else DEFAULT_REPORT_DIR
        if not self.report_dir.is_absolute():
            raise ValueError("Evaluation report directory must be an absolute path.")
        if self.report_dir.exists() and not self.report_dir.is_dir():
            raise ValueError("Evaluation report path exists and is not a directory.")

    def reserve_groq_attempt(
        self,
        context: dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        request_budget: int,
        token_budget: int,
        provider: str,
        model: str,
    ) -> dict[str, Any]:
        """Durably reserve one request and conservative tokens before HTTP starts."""
        self._validate_evaluation_context(context)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.report_dir / ".budget.lock"
        events_path = self.report_dir / "evaluation-events.jsonl"
        estimate = estimate_prompt_tokens(system_prompt, user_prompt)
        # UTF-8 byte count upper-bounds ordinary tokenizer pieces for these text
        # prompts; reserve that bound plus the full completion cap.
        prompt_byte_bound = len((system_prompt or "").encode("utf-8")) + len((user_prompt or "").encode("utf-8"))
        reserved = prompt_byte_bound + max(0, int(max_tokens))
        with lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            prior = self._read_events(events_path)
            run_id = str(context["run_id"])
            attempts = [row for row in prior if row.get("event_type") == "attempt" and row.get("run_id") == run_id]
            outcomes = {
                row.get("request_id"): row
                for row in prior
                if row.get("event_type") == "provider_result" and row.get("run_id") == run_id
            }
            consumed = 0
            for attempt in attempts:
                outcome = outcomes.get(attempt.get("request_id"))
                if outcome is None:
                    raise EvaluationBudgetError("A prior provider attempt has no recorded outcome; run stopped for recovery.")
                usage = outcome.get("provider_token_usage") or {}
                total = usage.get("total_tokens")
                if not outcome.get("actual_usage_known") or not isinstance(total, int):
                    raise EvaluationBudgetError("Prior provider usage is unknown; run stopped conservatively.")
                consumed += total
            if len(attempts) >= max(0, int(request_budget)):
                raise EvaluationBudgetError("Evaluation request budget exhausted.")
            if consumed + reserved > max(0, int(token_budget)):
                raise EvaluationBudgetError("Evaluation token budget reservation would exceed the configured budget.")
            request_id = str(context.get("request_id") or uuid.uuid4())
            if any(row.get("request_id") == request_id for row in prior):
                raise EvaluationBudgetError("Evaluation request ID was already used.")
            event = self._event_base(context, "attempt")
            event.update({
                "request_id": request_id,
                "provider": provider,
                "model": model,
                "attempt_index": len(attempts) + 1,
                "request_count": 1,
                "response_status": "pending",
                "latency_ms": None,
                "generation_source": "groq",
                "fallback_reason": None,
                "rejected_rule_ids": [],
                "provider_token_usage": {"input_tokens": None, "completion_tokens": None, "total_tokens": None},
                "actual_usage_known": False,
                "reserved_tokens": reserved,
                "token_estimate": estimate,
            })
            self._append_jsonl(events_path, event)
            return {"request_id": request_id, "reserved_tokens": reserved, "attempt_index": len(attempts) + 1}

    def append_groq_outcome(
        self,
        context: dict[str, Any],
        reservation: dict[str, Any],
        *,
        provider: str,
        model: str,
        response_status: Any,
        latency_ms: float | None,
        usage: dict[str, Any] | None,
        fallback_reason: str | None,
    ) -> None:
        normalized = _normalize_provider_usage(usage)
        known = isinstance(normalized.get("total_tokens"), int)
        event = self._event_base({**context, "request_id": reservation["request_id"]}, "provider_result")
        event.update({
            "request_id": reservation["request_id"],
            "provider": provider,
            "model": model,
            "attempt_index": reservation["attempt_index"],
            "request_count": 1,
            "response_status": response_status,
            "latency_ms": latency_ms,
            "generation_source": provider if fallback_reason is None else "rule_based",
            "fallback_reason": fallback_reason,
            "rejected_rule_ids": [],
            "provider_token_usage": normalized,
            "actual_usage_known": known,
            "reserved_tokens": reservation["reserved_tokens"],
                "token_estimate": {"method": "utf8_bytes_upper_bound_plus_output_cap_v1", "scope": "prompt_plus_max_completion", "value": reservation["reserved_tokens"]},
        })
        self._append_jsonl(self.report_dir / "evaluation-events.jsonl", event)

    def append_writer_result(
        self,
        context: dict[str, Any],
        *,
        writer: str,
        provider: str,
        model: str,
        latency_ms: float | None,
        generation_source: str,
        fallback_reason: str | None,
        rejected_rule_ids: list[str],
        synthetic_text: str,
        accepted: bool,
    ) -> None:
        self._validate_evaluation_context(context)
        metadata = {
            **context,
            "writer": writer,
            "provider": provider,
            "model": model,
            "request_count": 0,
            "response_status": "writer_result",
            "latency_ms": latency_ms,
            "generation_source": generation_source,
            "fallback_reason": fallback_reason,
            "rejected_rule_ids": rejected_rule_ids,
            "provider_token_usage": None,
            "token_estimate": None,
        }
        event = self._event_base(metadata, "writer_result")
        event.update({key: self._safe_metadata(metadata)[key] for key in ("writer", "request_count", "response_status", "latency_ms", "generation_source", "fallback_reason", "rejected_rule_ids", "provider_token_usage", "token_estimate")})
        event["provider"] = provider
        event["model"] = model
        self._append_jsonl(self.report_dir / "evaluation-events.jsonl", event)
        self._append_jsonl(
            self.report_dir / "synthetic-writing.jsonl",
            self._safe_synthetic_writing(metadata, {"text": synthetic_text, "accepted": accepted, "rejected_rule_ids": rejected_rule_ids}),
        )

    def _event_base(self, context: dict[str, Any], event_type: str) -> dict[str, Any]:
        self._validate_evaluation_context(context)
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "run_id": str(context["run_id"]),
            "request_id": str(context.get("request_id") or ""),
            "fixture_id": str(context["fixture_id"]),
            "is_synthetic": True,
            "profile_label": str(context["profile_label"]),
        }

    def _validate_evaluation_context(self, context: dict[str, Any]) -> None:
        if not isinstance(context, dict) or context.get("is_synthetic") is not True:
            raise ValueError("Evaluation reports require an explicitly synthetic fixture.")
        if not str(context.get("fixture_id") or "").startswith("synthetic-"):
            raise ValueError("Evaluation fixture ID must start with 'synthetic-'.")
        if not context.get("run_id") or not context.get("profile_label"):
            raise ValueError("Evaluation run ID and synthetic profile label are required.")

    def _read_events(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                # A torn final append makes the run uncertain and is never ignored.
                raise EvaluationBudgetError("Report file has a malformed row; run stopped for recovery.")
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def append_result(self, metadata: dict[str, Any], synthetic_writing: dict[str, Any] | None = None) -> dict[str, str]:
        if synthetic_writing is not None:
            fixture_id = str(metadata.get("fixture_id") or "")
            if metadata.get("is_synthetic") is not True or not fixture_id.startswith("synthetic-"):
                raise ValueError("Full writing may only be saved for explicitly synthetic fixtures.")

        event = self._safe_metadata(metadata)
        event.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
        event_path = self.report_dir / "evaluation-events.jsonl"
        self._append_jsonl(event_path, event)

        paths = {"metadata": str(event_path)}
        if synthetic_writing is not None:
            output = self._safe_synthetic_writing(metadata, synthetic_writing)
            writing_path = self.report_dir / "synthetic-writing.jsonl"
            self._append_jsonl(writing_path, output)
            paths["synthetic_writing"] = str(writing_path)
        return paths

    def _safe_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        record = {key: metadata[key] for key in METADATA_FIELDS if key in metadata}
        usage = record.get("provider_token_usage")
        record["provider_token_usage"] = (
            {key: value for key, value in usage.items() if key in TOKEN_FIELDS and (value is None or isinstance(value, int))}
            if isinstance(usage, dict)
            else {key: None for key in sorted(TOKEN_FIELDS)}
        )
        estimate = record.get("token_estimate")
        if isinstance(estimate, dict):
            record["token_estimate"] = {
                "method": str(estimate.get("method") or "unspecified"),
                "scope": str(estimate.get("scope") or "unspecified"),
                "value": estimate.get("value") if isinstance(estimate.get("value"), int) else None,
            }
        else:
            record["token_estimate"] = {"method": "unspecified", "scope": "unspecified", "value": None}
        record.setdefault("request_count", 0)
        record.setdefault("response_status", "not_sent")
        record.setdefault("latency_ms", None)
        record.setdefault("generation_source", "validator_test")
        record.setdefault("fallback_reason", None)
        record.setdefault("rejected_rule_ids", [])
        return record

    def _safe_synthetic_writing(self, metadata: dict[str, Any], writing: dict[str, Any]) -> dict[str, Any]:
        text = str(writing.get("text") or "")
        text = re.sub(r"(?i)\b(?:authorization|api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+", "[credential redacted]", text)
        text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [credential redacted]", text)
        text = re.sub(r"(?i)\b(?:gsk_|sk-|sk_live_)[A-Za-z0-9_-]{12,}\b", "[secret redacted]", text)
        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[email redacted]", text)
        text = re.sub(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)", "[phone redacted]", text)
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": str(metadata.get("run_id") or ""),
            "request_id": str(metadata.get("request_id") or ""),
            "fixture_id": str(metadata["fixture_id"]),
            "profile_label": str(metadata.get("profile_label") or ""),
            "writer": str(metadata.get("writer") or "unknown"),
            "accepted": bool(writing.get("accepted")),
            "text": text,
            "rejected_rule_ids": [str(value) for value in writing.get("rejected_rule_ids", [])],
        }

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())


def estimate_prompt_tokens(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Return an explicitly approximate local estimate; never label it provider usage."""
    count = len(re.findall(r"\w+|[^\w\s]", f"{system_prompt or ''}{user_prompt or ''}"))
    return {"method": "regex_word_punct_v1", "scope": "system_plus_user_prompt", "value": count}
