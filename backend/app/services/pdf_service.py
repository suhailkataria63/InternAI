import fitz


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from a PDF file represented as bytes."""
    if not pdf_bytes:
        raise ValueError("Uploaded PDF is empty.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Uploaded file could not be read as a PDF.") from exc

    text_parts: list[str] = []

    try:
        for page in document:
            text_parts.append(page.get_text())
    finally:
        document.close()

    return "\n".join(text_parts).strip()
