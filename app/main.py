from typing import Optional, List, Dict, Any

import base64
from fastapi import FastAPI, UploadFile, File, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from .signature_check import detect_digital_signatures, detect_wet_signatures, sha256_hex
from .extract_all import extract_text_and_tables


app = FastAPI(title="DP PDF Analysis Service", version="0.2.0")

# CORS – open for now; you can tighten later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze_pdf")
async def analyze_pdf(
    file: Optional[UploadFile] = File(None),
    pdf_base64: Optional[str] = Body(default=None),
    required_signers: Optional[List[str]] = Body(default=None),
    ocr_threshold_chars: int = Body(default=1000)
):
    """
    Combined endpoint:
      - Extracts full text + tables (OCR fallback).
      - Detects digital signatures.
      - Detects wet-ink signatures.

    Accepts either:
      - multipart/form-data with "file" field, OR
      - JSON: { "pdf_base64": "...", "required_signers": [...], "ocr_threshold_chars": 800 }

    Returns:
      {
        "status": "ok",
        "file_hash": "...",
        "extraction": { pages:[...], tables:[...] },
        "signatures": { digital_signatures:[...], wet_signature:{...} },
        "required_signers_eval": [...]
      }
    """
    try:
        if file and file.filename:
            pdf_bytes = await file.read()
        elif pdf_base64:
            pdf_bytes = base64.b64decode(pdf_base64)
        else:
            return JSONResponse(
                {"status": "error", "message": "No PDF provided (file or pdf_base64 is required)."},
                status_code=400
            )

        digest = sha256_hex(pdf_bytes)

        # 1) Extraction
        extraction = extract_text_and_tables(pdf_bytes, ocr_threshold_chars=ocr_threshold_chars)

        # 2) Signatures
        digital = detect_digital_signatures(pdf_bytes)
        wet = detect_wet_signatures(pdf_bytes)

        result: Dict[str, Any] = {
            "status": "ok",
            "file_hash": digest,
            "extraction": extraction,
            "signatures": {
                "digital_signatures": digital,
                "wet_signature": wet
            }
        }

        # 3) Simple "did we get any signature at all?" check per required role
        if required_signers:
            any_sig = (
                (len(digital) > 0 and any(d.get("signed") for d in digital))
                or (wet.get("wet_signatures_detected", 0) > 0)
            )
            result["required_signers_eval"] = [
                {"signer_role": r, "present": any_sig}
                for r in required_signers
            ]

        return result

    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )
