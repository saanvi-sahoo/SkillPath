"""
Uploaded-document check (E38, review 3 §7: "User uploads an image-only PDF -> detect missing text and request a readable
document"). A scanned CV has pages but no text layer; analysing it would produce an empty profile (ATS 0, no skills)
that looks like a real result.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

MIN_CHARS = 120  # a real CV / JD has far more; a scanned page has ~0


def extracted_chars(path: str) -> int:
    p = Path(path)
    suf = p.suffix.lower()
    try:
        if suf == ".pdf":
            import fitz
            with fitz.open(str(p)) as doc:
                return sum(len(page.get_text().strip()) for page in doc)
        if suf == ".docx":
            import docx  # python-docx
            return sum(len(par.text.strip()) for par in docx.Document(str(p)).paragraphs)
        return len(p.read_text(encoding="utf-8", errors="ignore").strip())
    except Exception:  # noqa: BLE001 - unreadable/corrupt file
        return 0


def unreadable_reason(path: str, what: str) -> Optional[str]:
    """None if the document has readable text, else a message for the student."""
    n = extracted_chars(path)
    if n >= MIN_CHARS:
        return None
    if Path(path).suffix.lower() == ".pdf":
        return (f"Your {what} PDF has almost no readable text ({n} characters). It is probably a scanned image. "
                "Please upload a text-based PDF or a DOCX (export it from Word or Google Docs), or paste the text in the box below.")
    return f"Your {what} file has almost no readable text ({n} characters). Please upload another file or paste the text."
