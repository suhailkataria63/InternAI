from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field

from app.schemas.job import JobProfile
from app.schemas.match import MatchScoreResponse


class ProjectItem(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)


class SkillGapResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    education: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[Union[str, ProjectItem]] = Field(default_factory=list)
    experience: List[Any] = Field(default_factory=list)
    certifications: List[Any] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    improvement_areas: List[str] = Field(default_factory=list)


class SkillGapRequest(BaseModel):
    resume_profile: SkillGapResumeProfile
    job_profile: JobProfile
    match_result: MatchScoreResponse


class PrioritySkill(BaseModel):
    skill: str
    priority: str
    reason: str
    estimated_learning_time: str
    learning_tasks: list[str] = Field(default_factory=list)


class RoadmapWeek(BaseModel):
    week: int
    focus: str
    skills: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    outcome: str


class RecommendedProject(BaseModel):
    title: str
    description: str
    skills_practiced: list[str] = Field(default_factory=list)
    expected_outcome: str


class SkillGapResponse(BaseModel):
    target_role: str = ""
    priority_skills: list[PrioritySkill] = Field(default_factory=list)
    learning_roadmap: list[RoadmapWeek] = Field(default_factory=list)
    resume_improvement_suggestions: list[str] = Field(default_factory=list)
    recommended_projects: list[RecommendedProject] = Field(default_factory=list)
    overall_advice: str = ""
    generation_source: Optional[str] = None
    llm_provider: Optional[str] = None
    used_fallback: Optional[bool] = None
    fallback_reason: Optional[str] = None
    llm_raw_preview: Optional[str] = None
    repair_note: Optional[str] = None
