import io
from typing import Any, Dict, List

from PyPDF2 import PdfReader


def analyze_signatures(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Very lightweight digital-signature detection using PyPDF2.

    We look for annotation fields of type /Sig. This is not a full
    cryptographic validation (that would require heavier libraries),
    but it tells us whether the PDF contains signature fields.
    """
    result: Dict[str, Any] = {
        "digital_signatures": [],
        "wet_signature": {
            "wet_signatures_detected": 0,
            "details": [],
        },
    }

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        # If PDF is malformed, just return empty signature info
        result["error"] = f"Failed to parse PDF in signature check: {e}"
        return result

    digital_sigs: List[Dict[str, Any]] = []

    for page_index, page in enumerate(reader.pages, start=1):
        annots = page.get("/Annots")
        if not annots:
            continue

        for annot_ref in annots:
            try:
                annot = annot_ref.get_object()
            except Exception:
                continue

            subtype = annot.get("/Subtype")
            field_type = annot.get("/FT")

            # Typical pattern for signature fields
            if str(subtype) == "/Widget" and str(field_type) == "/Sig":
                sig_dict = annot.get("/V")
                sig_info = {
                    "page_no": page_index,
                    "field_name": str(annot.get("/T", "")),
                }

                if sig_dict:
                    sig_info["reason"] = str(sig_dict.get("/Reason", ""))
                    sig_info["location"] = str(sig_dict.get("/Location", ""))
                    sig_info["contact_info"] = str(sig_dict.get("/ContactInfo", ""))
                    sig_info["signer"] = str(sig_dict.get("/Name", ""))

                digital_sigs.append(sig_info)

    result["digital_signatures"] = digital_sigs

    # Wet signatures (handwritten) would require image analysis.
    # For now we just return zero.
    result["wet_signature"]["wet_signatures_detected"] = 0
    result["wet_signature"]["details"] = []

    return result
