# Architecture Context
1. RPA Orchestrator (Activepieces): Listens for email PDFs, POSTs to FastAPI.
2. Secure AI Gateway (FastAPI): Extracts PDF text (PyMuPDF), scrubs PII via spaCy/regex, applies prompt injection defenses, and calls OpenAI.
3. LLM Extraction: Forces structured JSON output via Pydantic (facility_name, disease_type, case_count, reporting_week).
4. Output (Activepieces): Appends JSON to Google Sheets, alerts if case_count > 10.
# Tech Stack
Python 3, FastAPI, Pydantic, PyMuPDF, spaCy (en_core_web_sm), OpenAI API.
