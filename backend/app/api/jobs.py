from fastapi import APIRouter

from app.agents.jd_analyzer import analyze_jd_text
from app.schemas.job import JobAnalyzeRequest, JobAnalyzeResponse


router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/analyze", response_model=JobAnalyzeResponse)
def analyze_job_description(request: JobAnalyzeRequest) -> JobAnalyzeResponse:
    job_profile = analyze_jd_text(request.job_description)
    return JobAnalyzeResponse(job_profile=job_profile)
