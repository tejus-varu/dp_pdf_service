import io
import re
from typing import Any, Dict, List

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image
import platform


# On Windows we must point pytesseract to the installed exe.
# In Docker/Render (Linux) the system tesseract is picked up automatically.
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Users\TejusReddy\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    )


def _clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _ocr_page_image(pix: fitz.Pixmap) -> str:
    """
    Takes a PyMuPDF pixmap and returns OCR text using PIL + Tesseract.
    No OpenCV or numpy required.
    """
    png_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(png_bytes))
    text = pytesseract.image_to_string(img, lang="eng")
    return _clean_text(text)


def extract_text_and_tables(pdf_bytes: bytes, ocr_threshold_chars: int = 1000) -> Dict[str, Any]:
    """
    For each page:
      - Get native text from PDF.
      - If there is too little text, OCR a rendered image of the page.

    Also extracts tables with pdfplumber (best effort).

    Returns:
      {
        "pages": [
          { "page_no": int, "text": str }
        ],
        "tables": [
          {
            "page_no": int,
            "rows": [[...]],
            "cols": int,
            "bbox": [x0, y0, x1, y1]
          }
        ]
      }
    """
    result: Dict[str, Any] = {"pages": [], "tables": []}

    # -------- TEXT + OCR FALLBACK --------
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("text") or ""
        text = _clean_text(text)

        # If the text is very short, treat it as scanned and OCR the page image
        if len(text) < ocr_threshold_chars:
            mat = fitz.Matrix(2, 2)  # slight zoom helps OCR
            pix = page.get_pixmap(matrix=mat, alpha=False)
            ocr_text = _ocr_page_image(pix)
            if len(ocr_text) > len(text):
                text = ocr_text

        result["pages"].append(
            {
                "page_no": i + 1,
                "text": text,
            }
        )

    # -------- TABLES (best effort) --------
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_no, p in enumerate(pdf.pages, start=1):
            try:
                tables = p.extract_tables()
            except Exception:
                # if pdfplumber chokes on a page, just skip its tables
                continue

            for t in tables or []:
                rows: List[List[str]] = []
                for row in t:
                    clean_row = [(c or "").strip() for c in row]
                    if any(clean_row):
                        rows.append(clean_row)

                if rows:
                    result["tables"].append(
                        {
                            "page_no": page_no,
                            "rows": rows,
                            "cols": len(rows[0]) if rows else 0,
                            "bbox": list(p.bbox),
                        }
                    )

    return result
