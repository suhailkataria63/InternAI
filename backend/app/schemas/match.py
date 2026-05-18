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
    score_breakdown: dict = Field(default_factory=dict)
    required_skill_match_percentage: int = 0
    preferred_skill_match_percentage: int = 0
    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
