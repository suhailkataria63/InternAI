from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import settings


ALLOWED_TONES = {"professional", "confident", "friendly", "concise"}
ALLOWED_COVER_LETTER_LENGTHS = {"short", "medium", "long"}


class OrchestratorRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    application_question: Optional[str] = "Why should we hire you for this internship?"
    tone: Optional[str] = "professional"
    word_limit: Optional[int] = Field(default=180, ge=40, le=500)
    cover_letter_length: Optional[str] = "short"

    @field_validator("resume_text", "job_description")
    @classmethod
    def validate_text_input(cls, value: str, info) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError(f"{info.field_name} cannot be empty.")
        if len(cleaned_value) > settings.max_text_input_chars:
            raise ValueError(
                f"{info.field_name} is too long. Please keep it under {settings.max_text_input_chars} characters."
            )
        return cleaned_value

    @field_validator("application_question")
    @classmethod
    def validate_application_question(cls, value: Optional[str]) -> str:
        cleaned_value = (value or "Why should we hire you for this internship?").strip()
        if len(cleaned_value) > 500:
            raise ValueError("application_question must be 500 characters or fewer.")
        return cleaned_value

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, value: Optional[str]) -> str:
        normalized_value = (value or "professional").strip().lower()
        if normalized_value not in ALLOWED_TONES:
            allowed = ", ".join(sorted(ALLOWED_TONES))
            raise ValueError(f"tone must be one of: {allowed}.")
        return normalized_value

    @field_validator("cover_letter_length")
    @classmethod
    def validate_cover_letter_length(cls, value: Optional[str]) -> str:
        normalized_value = (value or "short").strip().lower()
        if normalized_value not in ALLOWED_COVER_LETTER_LENGTHS:
            allowed = ", ".join(sorted(ALLOWED_COVER_LETTER_LENGTHS))
            raise ValueError(f"cover_letter_length must be one of: {allowed}.")
        return normalized_value


class PipelineSummary(BaseModel):
    candidate_name: str = ""
    target_role: str = ""
    company_name: str = ""
    match_score: int = 0
    match_level: str = ""
    top_matched_skills: list[str] = Field(default_factory=list)
    top_missing_skills: list[str] = Field(default_factory=list)
    highest_priority_skills: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""


class OrchestratorResponse(BaseModel):
    resume_profile: Dict[str, Any]
    job_profile: Dict[str, Any]
    match_result: Dict[str, Any]
    skill_gap_result: Dict[str, Any]
    application_answer: Dict[str, Any]
    cover_letter: Dict[str, Any]
    pipeline_summary: Dict[str, Any]
