from fastapi import APIRouter

from app.agents.match_scorer import calculate_match_score
from app.schemas.match import MatchScoreRequest, MatchScoreResponse


router = APIRouter(prefix="/api/match", tags=["Match"])


@router.post("/score", response_model=MatchScoreResponse)
def score_match(request: MatchScoreRequest) -> MatchScoreResponse:
    score_result = calculate_match_score(
        resume_profile=request.resume_profile.model_dump(),
        job_profile=request.job_profile.model_dump(),
    )
    return MatchScoreResponse(**score_result)
