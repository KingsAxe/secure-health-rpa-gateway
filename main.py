"""PDF text extraction and PII scrubbing endpoint for health reports."""

import logging
import re
from functools import lru_cache

import pymupdf
import spacy
from fastapi import FastAPI, File, HTTPException, UploadFile


app = FastAPI(title="Health Report Gateway")
logger = logging.getLogger(__name__)

# Matches common Nigerian and North American phone formats, including the fake
# numbers used by generate_mock_pdfs.py.
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:(?:\+?234[\s.\-]?[789]\d{2}|0[789]\d{2})"
    r"[\s.\-]?\d{3}[\s.\-]?\d{4}|"
    r"(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})"
    r"[\s.\-]?\d{3}[\s.\-]?\d{4})"
    r"(?:\s*(?:x|ext\.?)\s*\d{1,5})?(?!\w)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _person_model():
    """Load the spaCy model once, on the first report request."""
    return spacy.load("en_core_web_sm")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Return text from every page of a PDF, in page order."""
    if not file_bytes:
        raise ValueError("The uploaded PDF is empty.")

    try:
        with pymupdf.open(stream=file_bytes, filetype="pdf") as document:
            if document.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            if document.page_count == 0:
                raise ValueError("The PDF has no pages.")
            return "\n".join(page.get_text() for page in document)
    except pymupdf.FileDataError as exc:
        raise ValueError("The uploaded file is not a valid PDF.") from exc


def scrub_pii(text: str) -> str:
    """Replace spaCy PERSON entities and phone numbers with redaction markers."""
    document = _person_model()(text)
    person_spans = [(entity.start_char, entity.end_char) for entity in document.ents if entity.label_ == "PERSON"]

    for start, end in reversed(person_spans):
        text = text[:start] + "[REDACTED_NAME]" + text[end:]

    return PHONE_PATTERN.sub("[REDACTED_PHONE]", text)


@app.post("/process-report")
async def process_report(file: UploadFile = File(...)) -> dict[str, str]:
    """Extract PDF text and return a version with names and phones redacted."""
    try:
        file_bytes = await file.read()
        extracted_text = extract_text_from_pdf(file_bytes)
        scrubbed_text = scrub_pii(extracted_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Unable to load the PII detection model")
        raise HTTPException(status_code=503, detail="PII detection model is unavailable.") from exc
    except Exception as exc:
        logger.exception("Failed to process uploaded report")
        raise HTTPException(status_code=500, detail="Unable to process the report.") from exc
    finally:
        await file.close()

    return {"status": "success", "scrubbed_text": scrubbed_text}
