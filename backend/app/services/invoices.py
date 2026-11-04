"""Manual corrections, approval and cross-document verification."""

from datetime import date
from decimal import Decimal
from itertools import combinations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invoice, InvoiceRevision, User
from app.processing.normalize import norm_invoice_number
from app.services.pipeline import FIELDS, embed_invoices, snapshot
from app.services.validation import compare, validate


def _revalidate(db: Session, inv: Invoice) -> None:
    for other in validate(db, inv):
        validate(db, other)


def apply_correction(db: Session, inv: Invoice, changes: dict, user: User) -> dict:
    """Apply reviewer edits (already type-checked), mark them certain, re-validate, record a revision."""
    before = snapshot(inv)
    for field, value in changes.items():
        setattr(inv, field, value)
        if field in FIELDS:
            inv.confidence = {**(inv.confidence or {}), field: 1.0 if value not in (None, "") else 0.0}
    if "invoice_number" in changes:
        inv.invoice_number_norm = norm_invoice_number(inv.invoice_number)
    after = snapshot(inv)
    diff = {k: [before[k], after[k]] for k in after if before[k] != after[k]}
    if not diff:
        return {}
    if inv.status == "approved":
        inv.status = "extracted"  # an edit after approval needs a fresh sign-off
    version = (db.scalar(select(func.max(InvoiceRevision.version)).where(InvoiceRevision.invoice_id == inv.id)) or 0) + 1
    inv.revisions.append(InvoiceRevision(version=version, source="manual", data=after, changes=diff, user_id=user.id))
    _revalidate(db, inv)
    embed_invoices(db, [inv])  # best effort; a failure leaves the old vector
    _refresh_document_status(inv)
    db.commit()
    return diff


def approve(db: Session, inv: Invoice, user: User) -> None:
    inv.status, inv.needs_review = "approved", False
    version = (db.scalar(select(func.max(InvoiceRevision.version)).where(InvoiceRevision.invoice_id == inv.id)) or 0) + 1
    inv.revisions.append(InvoiceRevision(version=version, source="approval", data=snapshot(inv), user_id=user.id))
    _refresh_document_status(inv)
    db.commit()


def _refresh_document_status(inv: Invoice) -> None:
    doc = inv.document
    if doc.status in ("completed", "needs_review") and doc.invoices:
        doc.status = "needs_review" if any(i.needs_review for i in doc.invoices) else "completed"
        if doc.status == "completed":
            doc.error = None


def _kind(file_type: str) -> str:
    return "excel" if file_type in ("xlsx", "xls", "csv") else file_type


def cross_checks(db: Session, only_mismatches: bool = False) -> list[dict]:
    """Invoices that appear in more than one document, compared field by field (PDF-PDF, PDF-Excel, ...)."""
    keys = db.scalars(
        select(Invoice.invoice_number_norm)
        .where(Invoice.invoice_number_norm.is_not(None))
        .group_by(Invoice.invoice_number_norm)
        .having(func.count(func.distinct(Invoice.document_id)) > 1)
    ).all()
    out = []
    for key in keys:
        group = db.scalars(select(Invoice).where(Invoice.invoice_number_norm == key).order_by(Invoice.created_at)).all()
        for a, b in combinations(group, 2):
            if a.document_id == b.document_id:
                continue
            diffs = compare(a, b)
            if only_mismatches and not diffs:
                continue
            out.append(
                {
                    "invoice_number": a.invoice_number,
                    "kind": "-".join(sorted([_kind(a.document.file_type), _kind(b.document.file_type)])),  # pdf-pdf, excel-pdf
                    "status": "mismatch" if diffs else "match",
                    "differences": diffs,
                    "a": {"invoice_id": str(a.id), "document_id": str(a.document_id), "filename": a.document.filename},
                    "b": {"invoice_id": str(b.id), "document_id": str(b.document_id), "filename": b.document.filename},
                }
            )
    return out


def to_decimal(v) -> Decimal | None:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))


def to_date(v) -> date | None:
    return v if v is None or isinstance(v, date) else date.fromisoformat(str(v))
