import json

from sqlalchemy.orm import Session

from app.database.models import Application
from app.schemas.tracker import ALLOWED_APPLICATION_STATUSES, ApplicationCreate


def create_application(db: Session, payload: ApplicationCreate) -> Application:
    status = _validate_status(payload.status or "Saved")
    pipeline_summary = payload.pipeline_summary or {}
    match_result = payload.match_result or {}
    job_profile = payload.job_profile or {}

    application = Application(
        candidate_name=pipeline_summary.get("candidate_name")
        or payload.resume_profile.get("name"),
        company_name=pipeline_summary.get("company_name")
        or job_profile.get("company_name"),
        role_title=pipeline_summary.get("target_role") or job_profile.get("role_title"),
        match_score=pipeline_summary.get("match_score") or match_result.get("match_score"),
        match_level=pipeline_summary.get("match_level") or match_result.get("match_level"),
        status=status,
        resume_text=payload.resume_text,
        job_description=payload.job_description,
        resume_profile_json=_to_json(payload.resume_profile),
        job_profile_json=_to_json(payload.job_profile),
        match_result_json=_to_json(payload.match_result),
        skill_gap_result_json=_to_json(payload.skill_gap_result),
        application_answer_json=_to_json(payload.application_answer),
        cover_letter_json=_to_json(payload.cover_letter),
        pipeline_summary_json=_to_json(payload.pipeline_summary),
        notes=payload.notes or "",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def list_applications(db: Session) -> list[Application]:
    return db.query(Application).order_by(Application.created_at.desc()).all()


def get_application(db: Session, application_id: int) -> Application | None:
    return db.query(Application).filter(Application.id == application_id).first()


def update_application_status(
    db: Session,
    application_id: int,
    status: str,
) -> Application | None:
    application = get_application(db, application_id)
    if not application:
        return None
    application.status = _validate_status(status)
    db.commit()
    db.refresh(application)
    return application


def update_application_notes(
    db: Session,
    application_id: int,
    notes: str,
) -> Application | None:
    application = get_application(db, application_id)
    if not application:
        return None
    application.notes = notes
    db.commit()
    db.refresh(application)
    return application


def delete_application(db: Session, application_id: int) -> bool:
    application = get_application(db, application_id)
    if not application:
        return False
    db.delete(application)
    db.commit()
    return True


def application_to_out(application: Application) -> dict:
    return {
        "id": application.id,
        "candidate_name": application.candidate_name,
        "company_name": application.company_name,
        "role_title": application.role_title,
        "match_score": application.match_score,
        "match_level": application.match_level,
        "status": application.status,
        "resume_text": application.resume_text,
        "job_description": application.job_description,
        "resume_profile": _from_json(application.resume_profile_json),
        "job_profile": _from_json(application.job_profile_json),
        "match_result": _from_json(application.match_result_json),
        "skill_gap_result": _from_json(application.skill_gap_result_json),
        "application_answer": _from_json(application.application_answer_json),
        "cover_letter": _from_json(application.cover_letter_json),
        "pipeline_summary": _from_json(application.pipeline_summary_json),
        "notes": application.notes,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


def application_to_list_item(application: Application) -> dict:
    return {
        "id": application.id,
        "candidate_name": application.candidate_name,
        "company_name": application.company_name,
        "role_title": application.role_title,
        "match_score": application.match_score,
        "match_level": application.match_level,
        "status": application.status,
        "notes": application.notes,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


def _validate_status(status: str) -> str:
    if status not in ALLOWED_APPLICATION_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_APPLICATION_STATUSES))
        raise ValueError(f"Invalid status '{status}'. Allowed statuses: {allowed}.")
    return status


def _to_json(value: dict) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _from_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}
