from typing import Optional

from app.config import settings


MOCK_LLM_TEXT = "Mock LLM response: provider is not configured yet."
GEMINI_FALLBACK_TEXT = (
    "Mock LLM response: Gemini request failed or provider is unavailable."
)
SUPPORTED_PROVIDERS = {"mock", "groq", "gemini", "openai", "openai-compatible"}


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
    ) -> dict:
        active_temperature = (
            settings.llm_temperature if temperature is None else temperature
        )
        active_max_tokens = settings.llm_max_tokens if max_tokens is None else max_tokens

        if not self._build_prompt(system_prompt, user_prompt):
            return self._fallback_response()

        if self.provider == "groq" and settings.groq_api_key:
            return self._generate_with_groq(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=active_temperature,
                max_tokens=active_max_tokens,
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

        return self._fallback_response()

    def _has_required_key(self) -> bool:
        if self.provider == "groq":
            return bool(settings.groq_api_key)
        if self.provider == "gemini":
            return bool(settings.gemini_api_key)
        if self.provider in {"openai", "openai-compatible"}:
            return bool(settings.openai_api_key)
        return self.provider == "mock"

    def _generate_with_groq(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        try:
            import httpx

            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
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
            response.raise_for_status()
            payload = response.json()
            text = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                return self._fallback_response()

            return {
                "provider": "groq",
                "model": self.model,
                "text": text,
                "used_fallback": False,
            }
        except Exception:
            return self._fallback_response()

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

    def _fallback_response(self, text: str = MOCK_LLM_TEXT, error: dict | None = None) -> dict:
        response = {
            "provider": self.provider or "mock",
            "model": self.model or "mock-model",
            "text": text,
            "used_fallback": True,
        }
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
