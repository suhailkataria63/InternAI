from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.llm_service import LLMService


router = APIRouter(prefix="/api/llm", tags=["LLM"])


class LLMTestRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


@router.get("/status")
def get_llm_status() -> dict[str, Any]:
    service = LLMService()
    return service.get_status()


@router.post("/test")
def test_llm_generation(request: LLMTestRequest) -> dict[str, Any]:
    service = LLMService()
    return service.generate_text(
        system_prompt="You are InternAI, a concise internship assistant.",
        user_prompt=request.prompt,
    )
