from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.session import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_name = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    role_title = Column(String, nullable=True)
    match_score = Column(Integer, nullable=True)
    match_level = Column(String, nullable=True)
    status = Column(String, default="Saved")
    resume_text = Column(Text, nullable=True)
    job_description = Column(Text, nullable=True)
    resume_profile_json = Column(Text, nullable=True)
    job_profile_json = Column(Text, nullable=True)
    match_result_json = Column(Text, nullable=True)
    skill_gap_result_json = Column(Text, nullable=True)
    application_answer_json = Column(Text, nullable=True)
    cover_letter_json = Column(Text, nullable=True)
    pipeline_summary_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
