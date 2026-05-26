from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CoverLetterRequest(BaseModel):
    resume_profile: Dict[str, Any]
    job_profile: Dict[str, Any]
    match_result: Dict[str, Any]
    skill_gap_result: Dict[str, Any]
    tone: Optional[str] = "professional"
    length: Optional[str] = "short"


class CoverLetterResponse(BaseModel):
    cover_letter: str
    subject_line: str
    opening_summary: str
    key_points_used: List[str]
    tone: str
    word_count: int
    generation_source: Optional[str] = None
    llm_provider: Optional[str] = None
    used_fallback: Optional[bool] = None
