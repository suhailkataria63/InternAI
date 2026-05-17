from fastapi import APIRouter

from app.agents.skill_gap_agent import analyze_skill_gap
from app.schemas.skill_gap import SkillGapRequest, SkillGapResponse


router = APIRouter(prefix="/api/skill-gap", tags=["Skill Gap"])


@router.post("/analyze", response_model=SkillGapResponse)
def analyze_skill_gaps(request: SkillGapRequest) -> SkillGapResponse:
    result = analyze_skill_gap(
        resume_profile=request.resume_profile.model_dump(),
        job_profile=request.job_profile.model_dump(),
        match_result=request.match_result.model_dump(),
    )
    return SkillGapResponse(**result)
