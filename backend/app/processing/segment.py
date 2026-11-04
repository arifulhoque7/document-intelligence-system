"""Group pages into chunks that each hold one invoice (or a few). Keeps every LLM request bounded
on very large PDFs; the LLM may still return 0..n invoices per chunk."""

import re

from app.processing.loaders import Page

INVOICE_NO = re.compile(
    r"(?:invoice|inv|bill)\s*(?:no\.?|number|num|#|id)\s*[:#.\-]?\s*([A-Z0-9][A-Z0-9\-/_.]{1,30})", re.I
)
MAX_CHUNK_CHARS = 60_000


def first_invoice_number(text: str) -> str | None:
    m = INVOICE_NO.search(text)
    return m.group(1).upper().rstrip(".") if m else None


def segment_pages(pages: list[Page]) -> list[list[Page]]:
    """A page starts a new chunk when it shows a different invoice number; pages without one
    (continuations, terms pages) join the current chunk."""
    chunks: list[list[Page]] = []
    current_no = None
    for page in pages:
        no = first_invoice_number(page.text)
        size = sum(len(p.text) for p in chunks[-1]) if chunks else 0
        if not chunks or (no and no != current_no) or size + len(page.text) > MAX_CHUNK_CHARS:
            chunks.append([page])
        else:
            chunks[-1].append(page)
        if no:
            current_no = no
    return chunks


def chunk_ref(chunk: list[Page]) -> str:
    first, last = chunk[0], chunk[-1]
    if first.sheet_name:
        return f"sheet {first.sheet_name}"
    return f"page {first.page_no}" if first is last else f"pages {first.page_no}-{last.page_no}"


def chunk_text(chunk: list[Page]) -> str:
    return "\n\n".join(f"--- page {p.page_no} ---\n{p.text}" for p in chunk)
