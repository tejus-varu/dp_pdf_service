# app/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import base64
import hashlib

from .extract_all import extract_all_text_and_tables
from .signature_check import analyze_signatures


class SignatureResult(BaseModel):
    digital_signatures: list
    wet_signature: dict


class ExtractionResult(BaseModel):
    pages: list
    tables: list


class AnalyzePdfResponse(BaseModel):
    status: str
    file_hash: str
    extraction: ExtractionResult
    signatures: SignatureResult


# 1️⃣  Define the FastAPI app FIRST
app = FastAPI(title="DP PDF Service")

# 2️⃣  Then attach middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@app.post("/analyze_pdf", response_model=AnalyzePdfResponse)
async def analyze_pdf(
    file: UploadFile = File(None),
    pdf_base64: str = Form(None),
    ocr_threshold_chars: int = Form(800),
):
    # Basic validation
    if not file and not pdf_base64:
        raise HTTPException(
            status_code=400,
            detail="No PDF provided (file or pdf_base64 is required).",
        )

    if file:
        pdf_bytes = await file.read()
    else:
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 PDF data.")

    file_hash = _hash_bytes(pdf_bytes)

    # Extraction
    extraction = extract_all_text_and_tables(
        pdf_bytes, ocr_threshold_chars=ocr_threshold_chars
    )

    # Signature analysis
    signatures = analyze_signatures(pdf_bytes)

    return {
        "status": "ok",
        "file_hash": file_hash,
        "extraction": extraction,
        "signatures": signatures,
    }
