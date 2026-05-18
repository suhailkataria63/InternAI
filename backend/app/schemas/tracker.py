from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


ALLOWED_APPLICATION_STATUSES = {"Saved", "Applied", "Interview", "Rejected", "Selected"}


class ApplicationCreate(BaseModel):
    resume_text: Optional[str] = None
    job_description: Optional[str] = None
    resume_profile: Dict[str, Any] = Field(default_factory=dict)
    job_profile: Dict[str, Any] = Field(default_factory=dict)
    match_result: Dict[str, Any] = Field(default_factory=dict)
    skill_gap_result: Dict[str, Any] = Field(default_factory=dict)
    application_answer: Dict[str, Any] = Field(default_factory=dict)
    cover_letter: Dict[str, Any] = Field(default_factory=dict)
    pipeline_summary: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = "Saved"
    notes: Optional[str] = ""


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    status: str


class ApplicationNotesUpdate(BaseModel):
    notes: str = ""


class ApplicationListItem(BaseModel):
    id: int
    candidate_name: Optional[str] = None
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    match_score: Optional[int] = None
    match_level: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationOut(ApplicationListItem):
    resume_text: Optional[str] = None
    job_description: Optional[str] = None
    resume_profile: Dict[str, Any] = Field(default_factory=dict)
    job_profile: Dict[str, Any] = Field(default_factory=dict)
    match_result: Dict[str, Any] = Field(default_factory=dict)
    skill_gap_result: Dict[str, Any] = Field(default_factory=dict)
    application_answer: Dict[str, Any] = Field(default_factory=dict)
    cover_letter: Dict[str, Any] = Field(default_factory=dict)
    pipeline_summary: Dict[str, Any] = Field(default_factory=dict)
