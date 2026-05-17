from pydantic import BaseModel, Field

from app.schemas.job import JobProfile
from app.schemas.resume import ResumeProfile


class MatchScoreRequest(BaseModel):
    resume_profile: ResumeProfile
    job_profile: JobProfile


class MatchScoreResponse(BaseModel):
    match_score: int
    match_level: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    project_relevance_notes: list[str] = Field(default_factory=list)
    recommendation: str = ""
