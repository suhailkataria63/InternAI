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
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    llm_temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=600, alias="LLM_MAX_TOKENS")
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://intern-0aruas79l-suhailkataria63s-projects.vercel.app",
        "https://intern-3tuycqr4-suhailkataria63s-projects.vercel.app",
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
