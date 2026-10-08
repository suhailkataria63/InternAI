from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.agents.resume_analyzer import analyze_resume_text
from app.config import settings
from app.schemas.resume import ResumeAnalyzeRequest, ResumeAnalyzeResponse
from app.services.pdf_service import extract_text_from_pdf


router = APIRouter(prefix="/api/resume", tags=["Resume"])
READ_CHUNK_SIZE = 1024 * 1024


def is_pdf_file(file: UploadFile) -> bool:
    filename = file.filename or ""
    return file.content_type == "application/pdf" and filename.lower().endswith(".pdf")


async def read_limited_upload(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_bytes = 0

    while True:
        chunk = await file.read(READ_CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            max_mb = max_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Resume PDF is too large. Please upload a file up to {max_mb:.0f} MB.",
            )
        chunks.append(chunk)

    return b"".join(chunks)


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)) -> dict[str, object]:
    if not is_pdf_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF resume uploads are supported.",
        )

    pdf_bytes = await read_limited_upload(file, settings.max_pdf_upload_bytes)

    try:
        extracted_text = extract_text_from_pdf(
            pdf_bytes,
            max_pages=settings.max_pdf_pages,
        )
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
