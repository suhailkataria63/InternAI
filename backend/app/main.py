from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.application_writer import router as application_writer_router
from app.api.cover_letter import router as cover_letter_router
from app.api.jobs import router as jobs_router
from app.api.llm import router as llm_router
from app.api.match import router as match_router
from app.api.orchestrator import router as orchestrator_router
from app.api.resume import router as resume_router
from app.api.skill_gap import router as skill_gap_router
from app.api.tracker import router as tracker_router
from app.config import settings
from app.database import models
from app.database.session import Base, engine


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.project_name,
    description="Backend API for the InternAI multi-agent internship assistant.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(match_router)
app.include_router(skill_gap_router)
app.include_router(application_writer_router)
app.include_router(cover_letter_router)
app.include_router(orchestrator_router)
app.include_router(tracker_router)
app.include_router(llm_router)


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "project": "InternAI",
        "message": "Backend is running",
    }
