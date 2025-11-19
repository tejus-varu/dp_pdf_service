import io
import hashlib
import datetime as dt
from typing import List, Dict, Any

import pikepdf
import fitz  # PyMuPDF
import numpy as np
import cv2


# -------- DIGITAL SIGNATURE DETECTION (AcroForm / Sig) --------

def detect_digital_signatures(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Looks for AcroForm fields of type /Sig.
    If signed, tries to pull signer, location, reason, and time.
    Returns list of signature metadata dicts.
    """
    results: List[Dict[str, Any]] = []
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            root = pdf.root
            acroform = root.get("/AcroForm", None)
            if not acroform:
                return results

            fields = acroform.get("/Fields", [])
            for f in fields:
                try:
                    field = f.get_object()
                    ft = field.get("/FT", None)
                    if ft and ft.name == "Sig":
                        name = field.get("/T", "")

                        v = field.get("/V", None)  # signature dictionary if signed
                        if v:
                            sig_dict = v.get_object()
                            signer = sig_dict.get("/Name", "")
                            location = sig_dict.get("/Location", "")
                            reason = sig_dict.get("/Reason", "")
                            m = sig_dict.get("/M", "")  # "D:YYYYMMDDHHmmSS..."

                            results.append({
                                "field_name": str(name),
                                "signed": True,
                                "signer_name": str(signer),
                                "location": str(location),
                                "reason": str(reason),
                                "signed_on": _parse_pdf_date(m),
                                "raw_time": str(m)
                            })
                        else:
                            # signature field present but not signed
                            results.append({
                                "field_name": str(name),
                                "signed": False
                            })
                except Exception:
                    # skip bad field, continue
                    continue
    except Exception:
        # invalid or encrypted PDF – return what we found (probably nothing)
        pass

    return results


def _parse_pdf_date(pdf_date: str) -> str:
    """
    PDF date string like "D:20250101120000+05'30'".
    Returns ISO string or empty.
    """
    if not pdf_date or not isinstance(pdf_date, str) or not pdf_date.startswith("D:"):
        return ""
    s = pdf_date[2:]
    try:
        year = int(s[0:4])
        month = int(s[4:6])
        day = int(s[6:8])
        hour = int(s[8:10] or 0)
        minute = int(s[10:12] or 0)
        sec = int(s[12:14] or 0)
        return dt.datetime(year, month, day, hour, minute, sec).isoformat()
    except Exception:
        return ""


# -------- WET-INK HEURISTIC (label → crop → ink density) --------

LABELS = [
    "signature",
    "signatory",
    "authorised signatory",
    "authorized signatory",
    "approved by",
    "signed by"
]


def detect_wet_signatures(pdf_bytes: bytes, density_threshold: float = 0.02) -> Dict[str, Any]:
    """
    Strategy:
      1) Find label words on each page (case-insensitive).
      2) For each label, crop a region to the right/below (expected signature box).
      3) Render crop to image; compute % of dark pixels (ink density).
      4) If density >= threshold → treat as wet signature present.

    Returns:
      {
        "wet_signatures_detected": int,
        "details": [
          {
            "page": int,
            "label": str,
            "bbox": [x0,y0,x1,y1],
            "ink_density": float,
            "present": bool
          }, ...
        ]
      }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    details: List[Dict[str, Any]] = []
    count = 0

    for pgno in range(len(doc)):
        page = doc[pgno]

        text_instances = []
        for label in LABELS:
            for inst in page.search_for(label):
                text_instances.append((label, inst))

        for label, rect in text_instances:
            # heuristic: signature usually to the right of label
            expand_w = 200  # tune if needed
            expand_h = 60
            crop = fitz.Rect(
                rect.x1 + 10,
                rect.y0 - 10,
                rect.x1 + 10 + expand_w,
                rect.y0 - 10 + expand_h
            )
            crop = crop & page.rect
            if crop.is_empty:
                continue

            mat = fitz.Matrix(2, 2)  # 2x zoom
            pix = page.get_pixmap(matrix=mat, clip=crop, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))

            if img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

            _, bw = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            ink_ratio = float(np.count_nonzero(bw)) / bw.size

            present = ink_ratio >= density_threshold
            if present:
                count += 1

            details.append({
                "page": pgno + 1,
                "label": label,
                "bbox": [float(crop.x0), float(crop.y0), float(crop.x1), float(crop.y1)],
                "ink_density": round(ink_ratio, 4),
                "present": present
            })

    return {"wet_signatures_detected": count, "details": details}


# -------- UTIL --------

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
