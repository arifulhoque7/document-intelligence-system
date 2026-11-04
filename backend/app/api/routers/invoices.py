import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.serializers import invoice_out
from app.core.db import get_db
from app.models import Invoice, User
from app.processing.normalize import ISO_CURRENCIES
from app.services.invoices import apply_correction, approve, cross_checks

router = APIRouter(prefix="/api", tags=["invoices"])


class LineItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = Field(None, max_length=500)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class CorrectionIn(BaseModel):
    """Only the fields sent are changed; send null to clear a value."""
    model_config = ConfigDict(extra="forbid")
    invoice_number: str | None = Field(None, max_length=100)
    invoice_date: date | None = None
    supplier_name: str | None = Field(None, max_length=255)
    customer_name: str | None = Field(None, max_length=255)
    subtotal: Decimal | None = Field(None, max_digits=16, decimal_places=2)
    tax: Decimal | None = Field(None, max_digits=16, decimal_places=2)
    total: Decimal | None = Field(None, max_digits=16, decimal_places=2)
    currency: str | None = None
    line_items: list[LineItemIn] | None = Field(None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def iso(cls, v):
        if v is not None and v.upper() not in ISO_CURRENCIES:
            raise ValueError("Unknown ISO 4217 currency code")
        return v.upper() if v else v


def _get(db: Session, inv_id: uuid.UUID) -> Invoice:
    inv = db.get(Invoice, inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return inv


@router.get("/invoices")
def list_invoices(
    q: str | None = Query(None, description="Keywords across number, parties and document text"),
    supplier: str | None = None,
    customer: str | None = None,
    invoice_number: str | None = None,
    currency: str | None = None,
    status: str | None = None,
    needs_review: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_total: Decimal | None = None,
    max_total: Decimal | None = None,
    document_id: uuid.UUID | None = None,
    sort: str = Query("-created_at", pattern="^-?(created_at|invoice_date|total|supplier_name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Invoice)
    if q:
        stmt = stmt.where(Invoice.search_tsv.op("@@")(func.websearch_to_tsquery("simple", q)))
    for col, val in ((Invoice.supplier_name, supplier), (Invoice.customer_name, customer), (Invoice.invoice_number, invoice_number)):
        if val:
            stmt = stmt.where(col.ilike(f"%{val}%"))
    if currency:
        stmt = stmt.where(Invoice.currency == currency.upper())
    if status:
        stmt = stmt.where(Invoice.status == status)
    if needs_review is not None:
        stmt = stmt.where(Invoice.needs_review.is_(needs_review))
    if date_from:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.invoice_date <= date_to)
    if min_total is not None:
        stmt = stmt.where(Invoice.total >= min_total)
    if max_total is not None:
        stmt = stmt.where(Invoice.total <= max_total)
    if document_id:
        stmt = stmt.where(Invoice.document_id == document_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = getattr(Invoice, sort.lstrip("-"))
    rows = db.scalars(
        stmt.options(selectinload(Invoice.document), selectinload(Invoice.issues))
        .order_by(col.desc().nulls_last() if sort.startswith("-") else col.asc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"total": total, "page": page, "items": [invoice_out(i) for i in rows]}


@router.get("/invoices/{inv_id}")
def get_invoice(inv_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return invoice_out(_get(db, inv_id), detail=True)


@router.patch("/invoices/{inv_id}")
def correct_invoice(inv_id: uuid.UUID, body: CorrectionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = _get(db, inv_id)
    changes = body.model_dump(exclude_unset=True)
    if "line_items" in changes:
        changes["line_items"] = [
            {k: (str(v) if isinstance(v, Decimal) else v) for k, v in li.items()} for li in changes["line_items"] or []
        ]
    diff = apply_correction(db, inv, changes, user)
    return {"changed": diff, "invoice": invoice_out(inv, detail=True)}


@router.post("/invoices/{inv_id}/approve")
def approve_invoice(inv_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = _get(db, inv_id)
    approve(db, inv, user)
    return invoice_out(inv)


@router.get("/invoices/{inv_id}/history")
def history(inv_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = _get(db, inv_id)
    return [
        {"version": r.version, "source": r.source, "changes": r.changes, "data": r.data, "user_id": r.user_id, "at": r.created_at.isoformat()}
        for r in inv.revisions
    ]


@router.get("/cross-checks")
def list_cross_checks(only_mismatches: bool = False, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return cross_checks(db, only_mismatches)
