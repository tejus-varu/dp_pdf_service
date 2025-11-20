from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import Any, Dict

from .extract_all import extract_text_and_tables
from .signature_check import analyze_signatures

import traceback

app = FastAPI(title="DP PDF Service")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze_pdf")
async def analyze_pdf(
    file: UploadFile = File(...),
    ocr_threshold_chars: int = Form(1000),
) -> JSONResponse:
    """
    Accepts a PDF file, performs:
      - text + table extraction (with OCR fallback)
      - lightweight signature analysis

    Returns a combined JSON payload.
    """
    try:
        if file.content_type not in ("application/pdf", "application/octet-stream"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": f"Expected a PDF file, got content_type={file.content_type}",
                },
            )

        pdf_bytes = await file.read()

        extraction = extract_text_and_tables(pdf_bytes, ocr_threshold_chars)
        signatures = analyze_signatures(pdf_bytes)

        # optional: build a flat full_text string for downstream Now Assist skill
        full_text_parts = [p.get("text", "") for p in extraction.get("pages", [])]
        full_text = "\n\n".join(t for t in full_text_parts if t)

        response: Dict[str, Any] = {
            "status": "ok",
            "file_name": file.filename,
            "file_size_bytes": len(pdf_bytes),
            "file_hash": None,  # you can add SHA256 if you want
            "extraction": extraction,
            "signatures": signatures,
            "full_text": full_text,
        }

        return JSONResponse(status_code=200, content=response)

    except Exception as e:
        # Log full traceback to Render logs
        tb = traceback.format_exc()
        print("ERROR in /analyze_pdf:", tb)

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Internal error while analyzing PDF: {str(e)}",
            },
        )
