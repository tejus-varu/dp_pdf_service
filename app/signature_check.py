# app/signature_check.py

import io
import re
from typing import Any, Dict

import cv2
import numpy as np
import pytesseract
from pypdf import PdfReader


def _clean_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _detect_digital_signatures(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Lightweight detection of digital signatures.

    We do two things:
      1) Use pypdf to look for /Sig fields in the AcroForm.
      2) Fallback: scan the raw bytes for common signature markers.
    """

    details = []
    has_sig = False

    # --- 1. pypdf-based check ---
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        root = reader.trailer.get("/Root", {})
        acro_form = root.get("/AcroForm")
        if acro_form:
            fields = acro_form.get("/Fields", [])
            for field in fields:
                try:
                    f = field.get_object()
                except Exception:
                    continue

                field_type = f.get("/FT")
                if field_type == "/Sig":
                    has_sig = True
                    name = f.get("/T")
                    sig_dict = f.get("/V")
                    sig_info = {}

                    if sig_dict:
                        sig_obj = sig_dict.get_object()
                        for key in ["/Name", "/Reason", "/Location", "/M", "/Filter", "/SubFilter"]:
                            if key in sig_obj:
                                sig_info[key.strip("/")] = str(sig_obj.get(key))
                    details.append(
                        {
                            "field_name": str(name) if name else None,
                            "info": sig_info,
                        }
                    )
    except Exception:
        # We don't want signature parsing to kill the service
        pass

    # --- 2. Raw-bytes heuristic ---
    raw_text = pdf_bytes.decode("latin-1", errors="ignore")
    if not has_sig:
        if re.search(r"/Type\s*/Sig", raw_text) or "Adobe.PPKLite" in raw_text:
            has_sig = True
            details.append(
                {
                    "field_name": None,
                    "info": {"note": "Signature markers found in raw PDF bytes"},
                }
            )

    return {
        "digital_signatures_detected": 1 if has_sig else 0,
        "details": details,
    }


def _detect_wet_signatures(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    VERY simple wet-signature heuristic:
    - Render pages to images via pypdf's built-in extraction (if any).
    - Use OpenCV to look for dark, ink-like strokes in bottom part of the page.

    This is *not* robust or production-grade, but it gives you a placeholder
    structure you can extend later.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return {"wet_signatures_detected": 0, "details": []}

    detected = []
    page_index = 0

    for page in reader.pages:
        page_index += 1

        # pypdf cannot render pages; this is just a stub.
        # In a real setup you would:
        #   - use PyMuPDF to render each page to an image
        #   - run OpenCV analysis on that image
        #
        # Since PyMuPDF is already in your project for OCR, it's better
        # to reuse that path instead of trying to get images from pypdf.
        #
        # For now we return zero and keep the structure ready.
        pass

    return {
        "wet_signatures_detected": len(detected),
        "details": detected,
    }


def analyze_signatures(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Public entry point used by main.py.

    Returns:
      {
        "digital_signatures": { ... },
        "wet_signature": { ... }
      }
    """
    digital = _detect_digital_signatures(pdf_bytes)
    wet = _detect_wet_signatures(pdf_bytes)

    return {
        "digital_signatures": digital,
        "wet_signature": wet,
    }
