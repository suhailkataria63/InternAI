import io

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.application_writer import ApplicationWriterResponse
from app.schemas.cover_letter import CoverLetterResponse
from app.services.pdf_service import extract_text_from_pdf


client = TestClient(app)


def test_writer_responses_keep_existing_fields_and_expose_fallback_reason() -> None:
    application = ApplicationWriterResponse(
        question="Why this role?",
        generated_answer="Verified evidence supports this application.",
        tone="professional",
        word_count=6,
        improvement_note="",
        generation_source="rule_based",
        llm_provider="groq",
        used_fallback=True,
        fallback_reason="provider_rate_limited",
    ).model_dump()
    letter = CoverLetterResponse(
        cover_letter="Dear Hiring Team, verified project evidence supports this application. Sincerely, Jane",
        subject_line="Application",
        opening_summary="Evidence grounded letter",
        key_points_used=[],
        tone="professional",
        word_count=12,
        generation_source="rule_based",
        llm_provider="groq",
        used_fallback=True,
        fallback_reason="provider_authentication",
    ).model_dump()

    assert application["generation_source"] == "rule_based"
    assert application["fallback_reason"] == "provider_rate_limited"
    assert letter["llm_provider"] == "groq"
    assert letter["fallback_reason"] == "provider_authentication"


def test_orchestrator_rejects_oversized_text() -> None:
    response = client.post(
        "/api/orchestrator/analyze-application",
        json={
            "resume_text": "x" * 20_001,
            "job_description": "Role: Intern\nSkills: Python",
            "application_question": "Why should we hire you?",
            "tone": "professional",
            "word_limit": 180,
            "cover_letter_length": "short",
        },
    )

    assert response.status_code == 422
    assert "too long" in response.text


def test_orchestrator_rejects_invalid_options() -> None:
    response = client.post(
        "/api/orchestrator/analyze-application",
        json={
            "resume_text": "Jane Doe\nSkills: Python",
            "job_description": "Role: Intern\nSkills: Python",
            "tone": "casual",
            "word_limit": 10,
            "cover_letter_length": "tiny",
        },
    )

    assert response.status_code == 422
    assert "tone" in response.text
    assert "word_limit" in response.text
    assert "cover_letter_length" in response.text


def test_orchestrator_returns_analysis_for_valid_request() -> None:
    response = client.post(
        "/api/orchestrator/analyze-application",
        json={
            "resume_text": "Jane Doe\nEducation\nB.S. Computer Science\nSkills\nPython, FastAPI, React\nProjects\nInternship tracker app",
            "job_description": "Role: Software Engineering Intern\nCompany: Acme Labs\nRequired Skills\nPython, FastAPI, SQL",
            "application_question": "Why should we hire you?",
            "tone": "friendly",
            "word_limit": 140,
            "cover_letter_length": "long",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["match_result"]["match_score"] >= 0
    assert payload["application_answer"] == {}
    assert payload["cover_letter"] == {}
    assert payload["pipeline_summary"]["target_role"]


def test_resume_upload_rejects_non_pdf() -> None:
    response = client.post(
        "/api/resume/upload",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF resume uploads are supported."


def test_pdf_extraction_rejects_empty_text_pdf() -> None:
    document = fitz.open()
    document.new_page()
    pdf_bytes = document.tobytes()
    document.close()

    try:
        extract_text_from_pdf(pdf_bytes)
    except ValueError as exc:
        assert "No readable text" in str(exc)
    else:
        raise AssertionError("Expected empty-text PDF to be rejected")


def test_resume_upload_accepts_text_pdf() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Jane Doe\nSkills: Python, FastAPI")
    pdf_bytes = document.tobytes()
    document.close()

    response = client.post(
        "/api/resume/upload",
        files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "resume.pdf"
    assert "Jane Doe" in payload["extracted_text"]
