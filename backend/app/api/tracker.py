from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.tracker import (
    ApplicationCreate,
    ApplicationListItem,
    ApplicationNotesUpdate,
    ApplicationOut,
    ApplicationStatusUpdate,
)
from app.services.tracker_service import (
    application_to_list_item,
    application_to_out,
    create_application,
    delete_application,
    get_application,
    list_applications,
    update_application_notes,
    update_application_status,
)


router = APIRouter(prefix="/api/tracker", tags=["Application Tracker"])


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def save_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    try:
        application = create_application(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApplicationOut(**application_to_out(application))


@router.get("/applications", response_model=list[ApplicationListItem])
def get_saved_applications(db: Session = Depends(get_db)) -> list[ApplicationListItem]:
    return [
        ApplicationListItem(**application_to_list_item(application))
        for application in list_applications(db)
    ]


@router.get("/applications/{application_id}", response_model=ApplicationOut)
def get_saved_application(
    application_id: int,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    application = get_application(db, application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    return ApplicationOut(**application_to_out(application))


@router.patch("/applications/{application_id}/status", response_model=ApplicationOut)
def patch_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    try:
        application = update_application_status(db, application_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return ApplicationOut(**application_to_out(application))


@router.patch("/applications/{application_id}/notes", response_model=ApplicationOut)
def patch_application_notes(
    application_id: int,
    payload: ApplicationNotesUpdate,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    application = update_application_notes(db, application_id, payload.notes)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return ApplicationOut(**application_to_out(application))


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_application(
    application_id: int,
    db: Session = Depends(get_db),
) -> Response:
    deleted = delete_application(db, application_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
