from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.serializers import invoice_out
from app.core.db import get_db
from app.llm import LLMError
from app.models import User
from app.services.search import MODES

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=500),
    mode: str = Query("hybrid", pattern="^(keyword|semantic|hybrid)$"),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        results = MODES[mode](db, q, limit)
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    return {"mode": mode, "items": [{**invoice_out(inv), "score": score, "snippet": snip} for inv, score, snip in results]}
