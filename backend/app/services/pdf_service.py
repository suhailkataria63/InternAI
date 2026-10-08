import fitz


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int | None = None) -> str:
    """Extract raw text from a PDF file represented as bytes."""
    if not pdf_bytes:
        raise ValueError("Uploaded PDF is empty.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Uploaded file could not be read as a PDF.") from exc

    text_parts: list[str] = []

    try:
        page_count = document.page_count
        if max_pages is not None and page_count > max_pages:
            raise ValueError(
                f"PDF has {page_count} pages. Please upload a resume with {max_pages} pages or fewer."
            )

        for page in document:
            text_parts.append(page.get_text())
    finally:
        document.close()

    extracted_text = "\n".join(text_parts).strip()
    if not extracted_text:
        raise ValueError(
            "No readable text could be extracted from this PDF. Please paste the resume text manually."
        )
    return extracted_text
