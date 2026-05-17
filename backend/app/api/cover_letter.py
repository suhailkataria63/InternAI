from fastapi import APIRouter

from app.agents.cover_letter_agent import generate_cover_letter
from app.schemas.cover_letter import CoverLetterRequest, CoverLetterResponse


router = APIRouter(prefix="/api/cover-letter", tags=["Cover Letter"])


@router.post("/generate", response_model=CoverLetterResponse)
def generate_cover_letter_endpoint(
    request: CoverLetterRequest,
) -> CoverLetterResponse:
    result = generate_cover_letter(
        resume_profile=request.resume_profile,
        job_profile=request.job_profile,
        match_result=request.match_result,
        skill_gap_result=request.skill_gap_result,
        tone=request.tone or "professional",
        length=request.length or "short",
    )
    return CoverLetterResponse(**result)
