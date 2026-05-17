from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.agents.resume_analyzer import analyze_resume_text
from app.schemas.resume import ResumeAnalyzeRequest, ResumeAnalyzeResponse
from app.services.pdf_service import extract_text_from_pdf


router = APIRouter(prefix="/api/resume", tags=["Resume"])


def is_pdf_file(file: UploadFile) -> bool:
    filename = file.filename or ""
    return file.content_type == "application/pdf" and filename.lower().endswith(".pdf")


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)) -> dict[str, object]:
    if not is_pdf_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF resume uploads are supported.",
        )

    pdf_bytes = await file.read()

    try:
        extracted_text = extract_text_from_pdf(pdf_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "filename": file.filename,
        "text_length": len(extracted_text),
        "extracted_text": extracted_text,
    }


@router.post("/analyze", response_model=ResumeAnalyzeResponse)
def analyze_resume(request: ResumeAnalyzeRequest) -> ResumeAnalyzeResponse:
    profile = analyze_resume_text(request.resume_text)
    return ResumeAnalyzeResponse(profile=profile)
