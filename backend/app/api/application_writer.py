from fastapi import APIRouter

from app.agents.application_writer_agent import generate_application_answer
from app.schemas.application_writer import (
    ApplicationWriterRequest,
    ApplicationWriterResponse,
)


router = APIRouter(prefix="/api/application", tags=["Application Writer"])


@router.post("/write", response_model=ApplicationWriterResponse)
def write_application_answer(
    request: ApplicationWriterRequest,
) -> ApplicationWriterResponse:
    result = generate_application_answer(
        resume_profile=request.resume_profile,
        job_profile=request.job_profile,
        match_result=request.match_result,
        skill_gap_result=request.skill_gap_result,
        application_question=request.application_question,
        tone=request.tone or "professional",
        word_limit=request.word_limit or 180,
    )
    return ApplicationWriterResponse(**result)
