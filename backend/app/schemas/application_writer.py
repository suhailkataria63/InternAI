from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApplicationWriterRequest(BaseModel):
    resume_profile: Dict[str, Any]
    job_profile: Dict[str, Any]
    match_result: Dict[str, Any]
    skill_gap_result: Dict[str, Any]
    application_question: str = Field(..., min_length=1)
    tone: Optional[str] = "professional"
    word_limit: Optional[int] = 180


class ApplicationWriterResponse(BaseModel):
    question: str
    generated_answer: str
    key_points_used: List[str] = Field(default_factory=list)
    tone: str
    word_count: int
    improvement_note: str
    generation_source: Optional[str] = None
    llm_provider: Optional[str] = None
    used_fallback: Optional[bool] = None
