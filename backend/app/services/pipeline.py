"""Document processing pipeline: load -> segment -> extract -> ground -> validate -> embed."""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import engine
from app.llm import LLMError, ProviderConfig, active_config, embed, extract_invoices
from app.models import Document, DocumentPage, Invoice, InvoiceRevision, ProcessingEvent
from app.processing.normalize import norm_invoice_number, parse_amount, parse_currency, parse_date
from app.processing.loaders import Content, ProcessingError, load
from app.processing.segment import chunk_ref, chunk_text, segment_pages
from app.processing.sheets import map_sheet
from app.services.validation import ground, validate

log = logging.getLogger(__name__)
FIELDS = ("invoice_number", "invoice_date", "supplier_name", "customer_name", "subtotal", "tax", "total", "currency")


def snapshot(inv: Invoice) -> dict:
    """JSON-safe copy of the invoice's extracted fields, used for revisions and API output."""
    data = {f: getattr(inv, f) for f in FIELDS}
    data["invoice_date"] = inv.invoice_date.isoformat() if inv.invoice_date else None
    for f in ("subtotal", "tax", "total"):
        data[f] = str(data[f]) if data[f] is not None else None
    data["line_items"] = inv.line_items or []
    return data


def _json_line_items(items) -> list[dict]:
    out = []
    for li in items or []:
        get = li.get if isinstance(li, dict) else lambda k, li=li: getattr(li, k)
        row = {k: parse_amount(get(k)) for k in ("quantity", "unit_price", "amount")}
        out.append({"description": (get("description") or None), **{k: (str(v) if v is not None else None) for k, v in row.items()}})
    return out


def build_invoice(raw: dict, source_text: str, source_ref: str, extracted_by: str, from_llm: bool) -> Invoice:
    d, ambiguous = parse_date(raw.get("invoice_date"))
    conf = {f: float(raw.get("confidence", {}).get(f, 0.0)) for f in FIELDS}
    if ambiguous:
        conf["invoice_date"] = min(conf["invoice_date"], 0.6)
    fields = {
        "invoice_number": (str(raw["invoice_number"]).strip()[:100] or None) if raw.get("invoice_number") else None,
        "invoice_date": d,
        "supplier_name": (str(raw["supplier_name"]).strip()[:255] or None) if raw.get("supplier_name") else None,
        "customer_name": (str(raw["customer_name"]).strip()[:255] or None) if raw.get("customer_name") else None,
        "subtotal": parse_amount(raw.get("subtotal")),
        "tax": parse_amount(raw.get("tax")),
        "total": parse_amount(raw.get("total")),
        "currency": parse_currency(raw.get("currency")),
    }
    if from_llm:
        ground(fields, conf, source_text)
    for f in FIELDS:
        if fields[f] is None:
            conf[f] = 0.0
    return Invoice(
        **fields,
        invoice_number_norm=norm_invoice_number(fields["invoice_number"]),
        line_items=_json_line_items(raw.get("line_items")),
        confidence=conf,
        source_text=source_text,
        source_ref=source_ref,
        extracted_by=extracted_by,
    )


class Run:
    """One processing attempt; records events and progress on the document."""

    def __init__(self, db: Session, doc: Document):
        self.db, self.doc = db, doc
        self.t0 = time.monotonic()

    def event(self, stage: str, status: str, message: str | None = None, started: float | None = None):
        ms = int((time.monotonic() - started) * 1000) if started else None
        self.db.add(ProcessingEvent(document_id=self.doc.id, stage=stage, status=status, message=message, duration_ms=ms))
        self.db.commit()

    def progress(self, pct: int):
        if pct - self.doc.progress >= 5 or pct == 100:
            self.doc.progress = pct
            self.db.commit()


def _extract_text_chunks(run: Run, cfg: ProviderConfig, chunks: list[tuple[str, str]]) -> list[Invoice]:
    """LLM extraction for (source_ref, text) chunks with bounded concurrency."""
    invoices: list[Invoice] = []
    label = f"{cfg.provider}/{cfg.model}"
    with ThreadPoolExecutor(get_settings().llm_concurrency) as pool:
        futures = [(ref, text, pool.submit(extract_invoices, cfg, text)) for ref, text in chunks]
        for i, (ref, text, fut) in enumerate(futures, start=1):
            result = fut.result()  # LLMError propagates: job layer retries transient ones
            for raw in result.invoices:
                invoices.append(build_invoice(raw.model_dump(), text, ref, label, from_llm=True))
            run.progress(40 + int(45 * i / len(futures)))
    return invoices


def _invoices_from_content(run: Run, db: Session, content: Content, file_type: str) -> list[Invoice]:
    invoices: list[Invoice] = []
    llm_chunks: list[tuple[str, str]] = []
    if content.tables:
        for page in content.pages:
            mapped = map_sheet(content.tables[page.sheet_name], page.sheet_name)
            if mapped:
                for raw in mapped:
                    invoices.append(build_invoice(raw, page.text, raw["source_ref"], "spreadsheet", from_llm=False))
            else:
                llm_chunks.append((f"sheet {page.sheet_name}", page.text))
        run.event("parse", "ok", f"{len(invoices)} invoice(s) mapped from columns; {len(llm_chunks)} sheet(s) need the LLM")
    else:
        chunks = segment_pages(content.pages)
        llm_chunks = [(chunk_ref(c), chunk_text(c)) for c in chunks]
        run.event("segment", "ok", f"{len(content.pages)} page(s) grouped into {len(chunks)} chunk(s)")

    if llm_chunks:
        cfg = active_config(db, "llm")
        if not cfg:
            raise LLMError("No active LLM provider. An admin must configure one in Settings.")
        t = time.monotonic()
        run.event("extract", "started", f"{len(llm_chunks)} LLM request(s) via {cfg.provider}/{cfg.model}")
        found = _extract_text_chunks(run, cfg, llm_chunks)
        run.event("extract", "ok", f"{len(found)} invoice(s) extracted", t)
        invoices += found
    return invoices


def embed_invoices(db: Session, invoices: list[Invoice]) -> str | None:
    """Store embeddings; returns a warning message instead of failing the document."""
    cfg = active_config(db, "embedding")
    if not cfg or not invoices:
        return "No embedding provider active; semantic search unavailable for this document" if invoices else None
    texts = [embedding_text(inv) for inv in invoices]
    try:
        vectors = []
        for i in range(0, len(texts), 64):
            vectors += embed(cfg, texts[i : i + 64])
    except LLMError as e:
        return f"Embedding failed: {e}"
    for inv, vec in zip(invoices, vectors, strict=True):
        inv.embedding, inv.embedding_model = vec, f"{cfg.provider}/{cfg.embedding_model}"
    return None


def embedding_text(inv: Invoice) -> str:
    items = ", ".join(li.get("description") or "" for li in (inv.line_items or [])[:30])
    head = (
        f"Invoice {inv.invoice_number or ''} from {inv.supplier_name or 'unknown supplier'} to "
        f"{inv.customer_name or 'unknown customer'} dated {inv.invoice_date or ''}, total {inv.total or ''} "
        f"{inv.currency or ''}. Items: {items}."
    )
    return f"{head}\n{(inv.source_text or '')[:2000]}"


def process_document(db: Session, doc_id: uuid.UUID) -> None:
    """Run the pipeline for one document, at most one run per document at a time.

    A Postgres advisory lock on a dedicated connection guards the whole run: a duplicate job (broker
    redelivery, or a slow job requeued as stuck) skips instead of processing the document twice in
    parallel. The lock is released when the run ends, or by Postgres when a crashed worker's connection
    drops, so crash recovery still works."""
    key = doc_id.int % (2**63)
    with engine.connect() as lock_conn:
        if not lock_conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}):
            log.info("Document %s is already being processed by another worker; skipping", doc_id)
            return
        try:
            _run_pipeline(db, doc_id)
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})


def _run_pipeline(db: Session, doc_id: uuid.UUID) -> None:
    """Run the full pipeline. Expected failures mark the document failed; transient LLM errors propagate
    (as LLMError with transient=True) so the job layer can retry."""
    doc = db.get(Document, doc_id)
    # A redelivered message (broker restart, late ack) must not reprocess a finished document and wipe
    # reviewer corrections. Real reprocess requests set "queued" first; "processing" means a crashed run.
    if not doc or doc.status not in ("queued", "processing"):
        log.info("Skipping job for document %s (status %s)", doc_id, doc.status if doc else "missing")
        return
    doc.status, doc.progress, doc.error = "processing", 0, None
    doc.attempts += 1
    doc.pages.clear()
    doc.invoices.clear()  # reprocessing replaces earlier results
    db.commit()
    run = Run(db, doc)
    run.event("processing", "started", f"Attempt {doc.attempts}")

    try:
        t = time.monotonic()
        content = load(Path(doc.storage_path), doc.file_type, lambda done, n: run.progress(int(40 * done / n)))
        methods = {p.method for p in content.pages}
        ocr_pages = [p for p in content.pages if p.method == "ocr"]
        msg = f"{len(content.pages)} page(s)/sheet(s); methods: {', '.join(sorted(methods))}"
        if ocr_pages:
            avg = sum(p.ocr_confidence or 0 for p in ocr_pages) / len(ocr_pages)
            msg += f"; OCR on {len(ocr_pages)} page(s), mean confidence {avg:.0f}%"
        run.event("text", "ok", msg, t)
        doc.page_count = len(content.pages)
        doc.pages = [
            DocumentPage(page_no=p.page_no, sheet_name=p.sheet_name, text=p.text.replace("\x00", ""), method=p.method, ocr_confidence=p.ocr_confidence)
            for p in content.pages
        ]
        db.commit()

        invoices = _invoices_from_content(run, db, content, doc.file_type)
        for i, inv in enumerate(invoices, start=1):
            inv.seq = i
            doc.invoices.append(inv)
        db.flush()

        t = time.monotonic()
        for inv in invoices:
            inv.revisions.append(InvoiceRevision(version=1, source="extraction", data=snapshot(inv)))
            for other in validate(db, inv):
                validate(db, other)  # the earlier record now has a cross-document match too
        flagged = sum(inv.needs_review for inv in invoices)
        run.event("validate", "warning" if flagged else "ok", f"{flagged} of {len(invoices)} invoice(s) need review", t)
        run.progress(90)

        t = time.monotonic()
        warning = embed_invoices(db, invoices)
        run.event("embed", "warning" if warning else "ok", warning or f"{len(invoices)} embedding(s) stored", t)

        if not invoices:
            doc.status, doc.error = "needs_review", "No invoice found in this document"
        else:
            doc.status = "needs_review" if flagged else "completed"
        doc.progress = 100
        doc.processing_ms = int((time.monotonic() - run.t0) * 1000)
        db.commit()
        run.event("done", "ok", f"Finished in {doc.processing_ms} ms")
    except LLMError as e:
        db.rollback()
        if e.transient:
            run.event("extract", "warning", f"{e}; will retry")
            raise
        _fail(run, str(e))
    except ProcessingError as e:
        db.rollback()
        _fail(run, str(e))
    except Exception:
        db.rollback()
        log.exception("Unexpected failure processing %s", doc_id)
        _fail(run, "Internal error while processing; see server logs")


def _fail(run: Run, message: str) -> None:
    doc = run.doc
    doc.status, doc.error = "failed", message
    doc.processing_ms = int((time.monotonic() - run.t0) * 1000)
    run.db.commit()
    run.event("error", "failed", message)


def mark_failed(db: Session, doc_id: uuid.UUID, message: str) -> None:
    doc = db.get(Document, doc_id)
    if doc:
        _fail(Run(db, doc), message)
