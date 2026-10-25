import re
import time
from time import perf_counter
from typing import Optional

from app.config import settings
from app.services.evaluation_report import EvaluationBudgetError, EvaluationReportStore, estimate_prompt_tokens


MOCK_LLM_TEXT = "Mock LLM response: provider is not configured yet."
GEMINI_FALLBACK_TEXT = (
    "Mock LLM response: Gemini request failed or provider is unavailable."
)
SUPPORTED_PROVIDERS = {"mock", "groq", "gemini", "openai", "openai-compatible", "ollama"}
OLLAMA_FALLBACK_TEXT = "Mock LLM response: Ollama request failed or provider is unavailable."


class LLMService:
    """Small provider layer for future LLM-powered agents.

    The service defaults to mock mode so local development and existing
    rule-based agents keep working without API keys.
    """

    def __init__(self) -> None:
        self.provider = (settings.llm_provider or "mock").strip().lower()
        self.model = settings.llm_model or "mock-model"

    def get_status(self) -> dict:
        configured = self.provider == "mock" or self._has_required_key()
        return {
            "provider": self.provider,
            "model": self.model,
            "configured": configured,
            "available": self.provider in SUPPORTED_PROVIDERS,
        }

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        evaluation_context: dict | None = None,
    ) -> dict:
        active_temperature = (
            settings.llm_temperature if temperature is None else temperature
        )
        active_max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens

        if self.provider == "groq" and settings.groq_evaluation_mode and evaluation_context is None:
            return self._fallback_response(error={"type": "EvaluationContextError", "fallback_reason": "synthetic_evaluation_context_required", "message": "Groq evaluation mode requires an explicit synthetic fixture context."})

        if not self._build_prompt(system_prompt, user_prompt):
            return self._fallback_response()

        if self.provider == "groq" and settings.groq_api_key:
            return self._generate_with_groq(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=active_temperature,
                max_tokens=active_max_tokens,
                evaluation_context=(evaluation_context if settings.groq_evaluation_mode else None),
            )
        if self.provider == "groq":
            return self._fallback_response(
                error={
                    "type": "ConfigurationError",
                    "fallback_reason": "missing_api_key",
                    "message": "GROQ_API_KEY is not configured.",
                }
            )

        if self.provider == "gemini":
            if not settings.gemini_api_key:
                return self._fallback_response(GEMINI_FALLBACK_TEXT)
            return self._generate_with_gemini(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=active_temperature,
                max_tokens=active_max_tokens,
            )

        if self.provider in {"openai", "openai-compatible"} and settings.openai_api_key:
            return self._generate_with_openai_compatible(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=active_temperature,
                max_tokens=active_max_tokens,
            )

        if self.provider == "ollama":
            return self._generate_with_ollama(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=min(active_temperature, 0.25),
                max_tokens=min(active_max_tokens, 700),
            )

        return self._fallback_response()

    def _has_required_key(self) -> bool:
        if self.provider == "groq":
            return bool(settings.groq_api_key)
        if self.provider == "gemini":
            return bool(settings.gemini_api_key)
        if self.provider in {"openai", "openai-compatible"}:
            return bool(settings.openai_api_key)
        if self.provider == "ollama":
            return bool(settings.ollama_base_url)
        return self.provider == "mock"

    def _generate_with_groq(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        evaluation_context: dict | None = None,
    ) -> dict:
        start = perf_counter()
        evaluation_store = EvaluationReportStore() if evaluation_context is not None else None
        reservation = None
        try:
            import httpx

            request_body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": max(0.1, min(float(temperature), 1.0)),
                "max_completion_tokens": max(128, min(int(max_tokens or 550), 1200)),
            }
            if self.model == "openai/gpt-oss-120b":
                request_body["reasoning_effort"] = "low"
            schema = (
                self._groq_writer_schema(system_prompt)
                if self.model == "openai/gpt-oss-120b"
                else None
            )
            if schema:
                request_body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema["name"],
                        "strict": True,
                        "schema": schema["schema"],
                    },
                }

            max_attempts = 1 if evaluation_context is not None else 1 + min(max(int(settings.groq_max_retries), 0), 1)
            for attempt in range(max_attempts):
                try:
                    if evaluation_store is not None:
                        try:
                            reservation = evaluation_store.reserve_groq_attempt(
                                evaluation_context,
                                system_prompt,
                                user_prompt,
                                max_tokens,
                                settings.groq_evaluation_request_budget,
                                settings.groq_evaluation_token_budget,
                                self.provider,
                                self.model,
                            )
                        except (EvaluationBudgetError, ValueError) as exc:
                            return self._fallback_response(error={"type": "EvaluationBudgetError", "fallback_reason": "evaluation_budget_or_recovery_stop", "message": str(exc)})
                    response = httpx.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.groq_api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_body,
                        timeout=30,
                    )
                    if evaluation_store is not None and reservation is not None:
                        usage_payload = None
                        outcome_reason = (
                            "provider_rate_limited" if response.status_code == 429 else
                            "provider_http_transient" if response.status_code == 408 or response.status_code >= 500 else
                            "provider_authentication" if response.status_code in {401, 403} else
                            "provider_http_error" if response.status_code >= 400 else None
                        )
                        try:
                            response_payload = response.json()
                            usage_payload = self._groq_usage(response_payload.get("usage"))
                            if response.status_code < 400:
                                content = response_payload.get("choices", [{}])[0].get("message", {}).get("content")
                                if not isinstance(content, str):
                                    outcome_reason = "provider_malformed_response"
                                elif not content.strip():
                                    outcome_reason = "provider_empty_response"
                        except Exception:
                            if response.status_code < 400:
                                outcome_reason = "provider_malformed_response"
                        evaluation_store.append_groq_outcome(
                            evaluation_context,
                            reservation,
                            provider=self.provider,
                            model=self.model,
                            response_status=response.status_code,
                            latency_ms=round((perf_counter() - start) * 1000, 3),
                            usage=usage_payload,
                            fallback_reason=outcome_reason,
                        )
                        reservation = None
                except httpx.TransportError as exc:
                    if evaluation_store is not None and reservation is not None:
                        evaluation_store.append_groq_outcome(
                            evaluation_context, reservation, provider=self.provider, model=self.model,
                            response_status="transport_exception", latency_ms=round((perf_counter() - start) * 1000, 3),
                            usage=None, fallback_reason="provider_timeout" if isinstance(exc, httpx.TimeoutException) else "provider_connection_error",
                        )
                        reservation = None
                    if attempt + 1 < max_attempts:
                        time.sleep(0.2)
                        continue
                    reason = "provider_timeout" if isinstance(exc, httpx.TimeoutException) else "provider_connection_error"
                    return self._groq_fallback(reason, type(exc).__name__, start)

                status = response.status_code
                if status in {408, 429} or status >= 500:
                    if attempt + 1 < max_attempts:
                        time.sleep(self._groq_retry_delay(response))
                        continue
                    reason = "provider_rate_limited" if status == 429 else "provider_http_transient"
                    return self._groq_fallback(reason, "HTTPError", start, status)
                if status in {401, 403}:
                    return self._groq_fallback("provider_authentication", "HTTPError", start, status)
                if status >= 400:
                    return self._groq_fallback("provider_http_error", "HTTPError", start, status)

                try:
                    payload = response.json()
                    text = payload["choices"][0]["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError):
                    return self._groq_fallback("provider_malformed_response", "InvalidResponse", start)
                if not isinstance(text, str) or not text.strip():
                    return self._groq_fallback("provider_empty_response", "EmptyResponse", start)
                return {
                    "provider": "groq",
                    "model": self.model,
                    "text": text.strip(),
                    "used_fallback": False,
                    "generation_time_ms": round((perf_counter() - start) * 1000, 3),
                    "usage": self._groq_usage(payload.get("usage")),
                }
        except Exception as exc:
            if evaluation_store is not None and reservation is not None:
                evaluation_store.append_groq_outcome(
                    evaluation_context, reservation, provider=self.provider, model=self.model,
                    response_status="exception", latency_ms=round((perf_counter() - start) * 1000, 3),
                    usage=None, fallback_reason="provider_error",
                )
            return self._groq_fallback("provider_error", type(exc).__name__, start)

    def _groq_writer_schema(self, system_prompt: str) -> dict | None:
        prompt = str(system_prompt or "")
        field = "cover_letter" if '"cover_letter"' in prompt else (
            "answer" if '"answer"' in prompt else None
        )
        if not field:
            return None
        return {
            "name": f"internai_{field}",
            "schema": {
                "type": "object",
                "properties": {field: {"type": "string"}},
                "required": [field],
                "additionalProperties": False,
            },
        }

    def _groq_retry_delay(self, response) -> float:
        try:
            requested = float(response.headers.get("retry-after", 0.2))
        except (AttributeError, TypeError, ValueError):
            requested = 0.2
        return max(0.05, min(requested, 1.0))

    def _groq_usage(self, usage) -> dict | None:
        if not isinstance(usage, dict):
            return None
        fields = {
            "prompt_tokens": usage.get("prompt_tokens", usage.get("input_tokens")),
            "completion_tokens": usage.get("completion_tokens", usage.get("output_tokens")),
            "total_tokens": usage.get("total_tokens"),
        }
        normalized = {key: int(value) for key, value in fields.items() if isinstance(value, (int, float))}
        return normalized or None

    def _groq_fallback(
        self,
        reason: str,
        error_type: str,
        started_at: float,
        status_code: int | None = None,
    ) -> dict:
        error = {"type": error_type, "fallback_reason": reason, "message": reason.replace("_", " ")}
        if status_code is not None:
            error["status_code"] = status_code
        return self._fallback_response(error=error, started_at=started_at)

    def _generate_with_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        prompt = self._build_prompt(system_prompt, user_prompt)
        if not prompt:
            return self._fallback_response(GEMINI_FALLBACK_TEXT)

        try:
            import httpx

            response = httpx.post(
                (
                    "https://generativelanguage.googleapis.com/v1beta/"
                    f"models/{self.model}:generateContent"
                ),
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": prompt,
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                },
                timeout=30,
            )
            if response.status_code >= 400:
                return self._fallback_response(
                    GEMINI_FALLBACK_TEXT,
                    error={
                        "status_code": response.status_code,
                        "message": self._sanitize_error_message(response.text),
                    },
                )

            payload = response.json()
            text = self._extract_gemini_text(payload)
            if not text:
                return self._fallback_response(
                    GEMINI_FALLBACK_TEXT,
                    error={
                        "type": "EmptyResponse",
                        "message": "Gemini returned a successful response without text content.",
                    },
                )

            return {
                "provider": "gemini",
                "model": self.model,
                "text": text,
                "used_fallback": False,
            }
        except Exception as exc:
            return self._fallback_response(
                GEMINI_FALLBACK_TEXT,
                error={
                    "type": type(exc).__name__,
                    "message": self._sanitize_error_message(str(exc)),
                },
            )

    def _generate_with_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        try:
            import httpx

            base_url = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
            response = httpx.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            if response.status_code >= 400:
                return self._fallback_response(
                    error={
                        "status_code": response.status_code,
                        "message": self._sanitize_error_message(response.text),
                    },
                )

            payload = response.json()
            text = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                return self._fallback_response(
                    error={
                        "type": "EmptyResponse",
                        "message": "OpenAI-compatible provider returned no text content.",
                    },
                )

            return {
                "provider": self.provider,
                "model": self.model,
                "text": text,
                "used_fallback": False,
            }
        except Exception as exc:
            return self._fallback_response(
                error={
                    "type": type(exc).__name__,
                    "message": self._sanitize_error_message(str(exc)),
                },
            )

    def _generate_with_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        start = perf_counter()
        try:
            import httpx

            base_url = (settings.ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
            response = httpx.post(
                f"{base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{system_prompt}\n\n"
                                "Do not think step by step. Do not include reasoning, analysis, "
                                "<think> tags, markdown fences, or commentary. Return only strict JSON."
                            ),
                        },
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "think": False,
                    "format": self._ollama_json_schema(system_prompt),
                    "options": {
                        "temperature": temperature,
                        "num_ctx": 4096,
                        "num_predict": max(128, min(int(max_tokens or 550), 700)),
                    },
                },
                timeout=45,
            )
            if response.status_code >= 400:
                return self._fallback_response(
                    OLLAMA_FALLBACK_TEXT,
                    error={
                        "status_code": response.status_code,
                        "message": self._sanitize_error_message(response.text),
                    },
                    started_at=start,
                )

            payload = response.json()
            text = self._strip_reasoning_text(
                str((payload.get("message") or {}).get("content") or "").strip()
            )
            if not text:
                return self._fallback_response(
                    OLLAMA_FALLBACK_TEXT,
                    error={
                        "type": "EmptyResponse",
                        "message": "Ollama returned a successful response without text content.",
                    },
                    started_at=start,
                )

            return {
                "provider": "ollama",
                "model": self.model,
                "text": text,
                "used_fallback": False,
                "generation_time_ms": round((perf_counter() - start) * 1000, 3),
            }
        except Exception as exc:
            return self._fallback_response(
                OLLAMA_FALLBACK_TEXT,
                error={
                    "type": type(exc).__name__,
                    "message": self._sanitize_error_message(str(exc)),
                },
                started_at=start,
            )

    def _build_prompt(self, system_prompt: str, user_prompt: str) -> str:
        system_text = (system_prompt or "").strip()
        user_text = (user_prompt or "").strip()
        if not system_text and not user_text:
            return ""
        if system_text and user_text:
            return f"System:\n{system_text}\n\nUser:\n{user_text}"
        return system_text or user_text

    def _extract_gemini_text(self, payload: dict) -> str:
        candidates = payload.get("candidates") or []
        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
            if candidates
            else []
        )
        text_parts = [
            str(part.get("text", "")).strip()
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ]
        return "\n".join(text_parts).strip()

    def _fallback_response(
        self,
        text: str = MOCK_LLM_TEXT,
        error: dict | None = None,
        started_at: float | None = None,
    ) -> dict:
        response = {
            "provider": self.provider or "mock",
            "model": self.model or "mock-model",
            "text": text,
            "used_fallback": True,
        }
        if started_at is not None:
            response["generation_time_ms"] = round((perf_counter() - started_at) * 1000, 3)
        if error:
            response["error"] = error
        return response

    def _sanitize_error_message(self, message: str) -> str:
        safe_message = str(message or "")
        secrets = [
            settings.gemini_api_key,
            settings.groq_api_key,
            settings.openai_api_key,
        ]
        for secret in secrets:
            if secret:
                safe_message = safe_message.replace(secret, "[REDACTED]")
        safe_message = safe_message.replace("\n", " ").replace("\r", " ").strip()
        safe_message = " ".join(safe_message.split())
        return safe_message[:500]

    def _strip_reasoning_text(self, text: str) -> str:
        cleaned = str(text or "")
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"^\s*(?:thinking|reasoning|analysis)\s*:\s*.*?(?=\{)", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned.strip()

    def _ollama_json_schema(self, system_prompt: str) -> dict:
        field_name = "cover_letter" if "cover_letter" in str(system_prompt or "") else "answer"
        return {
            "type": "object",
            "properties": {
                field_name: {
                    "type": "string",
                    "minLength": 20,
                }
            },
            "required": [field_name],
            "additionalProperties": False,
        }
