import io
import re
from typing import Any, Dict

import fitz  # PyMuPDF
import pdfplumber
import numpy as np
import cv2
import pytesseract
import platform


# --- POINT pytesseract to your Windows install ----
# Adjust this path if your Tesseract is somewhere else.
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Users\TejusReddy\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    )
# ---------------------------------------------------


def _clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)          # collapse spaces
    s = re.sub(r"\n{3,}", "\n\n", s)       # collapse multiple blank lines
    return s.strip()


def _ocr_page_image(pix) -> str:
    """
    Takes a PyMuPDF pixmap and returns OCR text.
    """
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.h, pix.w, pix.n))
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    text = pytesseract.image_to_string(gray, lang="eng")
    return _clean_text(text)


def extract_text_and_tables(pdf_bytes: bytes, ocr_threshold_chars: int = 1000) -> Dict[str, Any]:
    """
    For each page:
      - Try native text (vector).
      - If too little text, OCR the page image.
    Tables:
      - Use pdfplumber.extract_tables() (best effort).
    Returns:
      {
        "pages": [ { "page_no": int, "text": str } ],
        "tables": [ { "page_no": int, "rows": [[...]], "cols": int, "bbox": [x0,y0,x1,y1] } ]
      }
    """
    out: Dict[str, Any] = {"pages": [], "tables": []}

    # ---- TEXT + OCR FALLBACK ----
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("text") or ""
        text = _clean_text(text)

        # If very little text, assume scanned → OCR
        if len(text) < ocr_threshold_chars:
            mat = fitz.Matrix(2, 2)  # zoom a bit for OCR
            pix = page.get_pixmap(matrix=mat, alpha=False)
            ocr_text = _ocr_page_image(pix)
            if len(ocr_text) > len(text):
                text = ocr_text

        out["pages"].append({"page_no": i + 1, "text": text})

    # ---- TABLES ----
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pageno, p in enumerate(pdf.pages, start=1):
            try:
                tables = p.extract_tables()
                for t in tables or []:
                    rows = []
                    for row in t:
                        row = [(c or "").strip() for c in row]
                        if any(cell for cell in row):
                            rows.append(row)
                    if rows:
                        out["tables"].append({
                            "page_no": pageno,
                            "rows": rows,
                            "cols": len(rows[0]) if rows else 0,
                            "bbox": list(p.bbox)
                        })
            except Exception:
                continue

    return out
