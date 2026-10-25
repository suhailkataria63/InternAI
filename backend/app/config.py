from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    project_name: str = "InternAI"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(default="sqlite:///./internai.db", alias="DATABASE_URL")
    frontend_url: Optional[str] = Field(default=None, alias="FRONTEND_URL")
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_model: str = Field(default="mock-model", alias="LLM_MODEL")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_max_retries: int = Field(default=1, alias="GROQ_MAX_RETRIES")
    groq_evaluation_mode: bool = Field(default=False, alias="GROQ_EVALUATION_MODE")
    groq_evaluation_request_budget: int = Field(default=6, alias="GROQ_EVALUATION_REQUEST_BUDGET")
    groq_evaluation_token_budget: int = Field(default=12000, alias="GROQ_EVALUATION_TOKEN_BUDGET")
    groq_evaluation_report_dir: Optional[str] = Field(default=None, alias="GROQ_EVALUATION_REPORT_DIR")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="OPENAI_BASE_URL",
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        alias="OLLAMA_BASE_URL",
    )
    llm_temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=600, alias="LLM_MAX_TOKENS")
    max_pdf_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_PDF_UPLOAD_BYTES")
    max_pdf_pages: int = Field(default=12, alias="MAX_PDF_PAGES")
    max_text_input_chars: int = Field(default=20_000, alias="MAX_TEXT_INPUT_CHARS")
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://intern-0aruas79l-suhailkataria63s-projects.vercel.app",
        "https://intern-3tuycqr4-suhailkataria63s-projects.vercel.app",
        "https://intern-ai-seven.vercel.app",
    ]

    @property
    def allowed_cors_origins(self) -> list[str]:
        origins = [
            origin.strip().rstrip("/")
            for origin in self.cors_origins
            if origin and origin.strip()
        ]
        if self.frontend_url and self.frontend_url.strip():
            origins.append(self.frontend_url.strip().rstrip("/"))
        return list(dict.fromkeys(origins))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
