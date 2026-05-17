from fastapi import APIRouter, HTTPException, status

from app.schemas.orchestrator import OrchestratorRequest, OrchestratorResponse
from app.services.orchestrator_service import (
    OrchestratorStepError,
    run_full_application_analysis,
)


router = APIRouter(prefix="/api/orchestrator", tags=["Orchestrator"])


@router.post("/analyze-application", response_model=OrchestratorResponse)
def analyze_application(request: OrchestratorRequest) -> OrchestratorResponse:
    try:
        result = run_full_application_analysis(
            resume_text=request.resume_text,
            job_description=request.job_description,
            application_question=request.application_question
            or "Why should we hire you for this internship?",
            tone=request.tone or "professional",
            word_limit=request.word_limit or 180,
            cover_letter_length=request.cover_letter_length or "short",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except OrchestratorStepError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Multi-agent analysis failed.",
                "failed_step": exc.step_name,
                "error": str(exc.original_error),
            },
        ) from exc

    return OrchestratorResponse(**result)
