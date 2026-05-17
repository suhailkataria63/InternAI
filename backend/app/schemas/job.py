from pydantic import BaseModel, Field


class JobAnalyzeRequest(BaseModel):
    job_description: str = Field(..., min_length=1)


class JobProfile(BaseModel):
    role_title: str = ""
    company_name: str = ""
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    eligibility: list[str] = []
    stipend: str = ""
    duration: str = ""
    location: str = ""
    work_mode: str = ""
    keywords: list[str] = []


class JobAnalyzeResponse(BaseModel):
    job_profile: JobProfile
