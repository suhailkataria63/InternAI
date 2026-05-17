from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class OrchestratorRequest(BaseModel):
    resume_text: str
    job_description: str
    application_question: Optional[str] = "Why should we hire you for this internship?"
    tone: Optional[str] = "professional"
    word_limit: Optional[int] = 180
    cover_letter_length: Optional[str] = "short"


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
