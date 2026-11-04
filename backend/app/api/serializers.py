from app.models import Document, Invoice
from app.services.pipeline import snapshot


def document_out(d: Document, detail: bool = False) -> dict:
    out = {
        "id": str(d.id),
        "filename": d.filename,
        "file_type": d.file_type,
        "size_bytes": d.size_bytes,
        "status": d.status,
        "progress": d.progress,
        "page_count": d.page_count,
        "error": d.error,
        "attempts": d.attempts,
        "processing_ms": d.processing_ms,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        "invoice_count": len(d.invoices),
        "review_count": sum(i.needs_review for i in d.invoices),
    }
    if detail:
        out["events"] = [
            {"stage": e.stage, "status": e.status, "message": e.message, "duration_ms": e.duration_ms, "at": e.created_at.isoformat()}
            for e in d.events
        ]
        out["pages"] = [
            {"page_no": p.page_no, "sheet_name": p.sheet_name, "method": p.method, "ocr_confidence": p.ocr_confidence, "chars": len(p.text)}
            for p in d.pages
        ]
        out["invoices"] = [invoice_out(i) for i in sorted(d.invoices, key=lambda i: i.seq)]
    return out


def invoice_out(inv: Invoice, detail: bool = False) -> dict:
    out = {
        "id": str(inv.id),
        "document_id": str(inv.document_id),
        "filename": inv.document.filename if inv.document else None,
        "seq": inv.seq,
        "source_ref": inv.source_ref,
        **snapshot(inv),
        "confidence": inv.confidence or {},
        "status": inv.status,
        "needs_review": inv.needs_review,
        "extracted_by": inv.extracted_by,
        "has_embedding": inv.embedding is not None,
        "issues": [{"code": i.code, "field": i.field, "severity": i.severity, "message": i.message} for i in inv.issues],
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
    }
    if detail:
        out["source_text"] = inv.source_text
    return out
