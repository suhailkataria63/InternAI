from pydantic import BaseModel, Field


class ResumeAnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=1)


class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    education: list[str] = []
    skills: list[str] = []
    projects: list[str] = []
    experience: list[str] = []
    certifications: list[str] = []
    strengths: list[str] = []
    improvement_areas: list[str] = []


class ResumeAnalyzeResponse(BaseModel):
    profile: ResumeProfile
