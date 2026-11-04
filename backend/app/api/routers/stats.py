from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.models import Document, Invoice, User

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def stats(_: User = Depends(current_user), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all())
    finished = sum(v for k, v in by_status.items() if k in ("completed", "needs_review", "failed"))
    return {
        "documents": sum(by_status.values()),
        "documents_by_status": by_status,
        "invoices": db.scalar(select(func.count(Invoice.id))),
        "invoices_needing_review": db.scalar(select(func.count(Invoice.id)).where(Invoice.needs_review.is_(True))),
        "failure_rate": round(by_status.get("failed", 0) / finished, 4) if finished else None,
        "avg_processing_ms": db.scalar(select(func.avg(Document.processing_ms)).where(Document.status != "failed")),
    }
