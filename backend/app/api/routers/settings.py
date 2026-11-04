from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import admin_user, current_user
from app.core.db import get_db
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.llm import DEFAULTS, EMBEDDING_PROVIDERS, PROVIDERS, build_config, embed, extract_invoices
from app.models import ProviderSetting, User
from app.worker import reembed_all_task

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ProviderIn(BaseModel):
    """api_key: omit to keep the stored key, empty string to remove it."""
    model_config = ConfigDict(extra="forbid")
    api_key: str | None = Field(None, max_length=500)
    model: str | None = Field(None, max_length=100)
    embedding_model: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)


class ActiveIn(BaseModel):
    llm: str | None = None
    embedding: str | None = None


def _row(db: Session, provider: str) -> ProviderSetting:
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    row = db.get(ProviderSetting, provider)
    if not row:
        row = ProviderSetting(provider=provider)
        db.add(row)
    return row


def _out(row: ProviderSetting | None, provider: str) -> dict:
    d = DEFAULTS[provider]
    key = decrypt_secret(row.api_key_enc) if row and row.api_key_enc else None
    return {
        "provider": provider,
        "api_key_masked": mask_secret(key),  # the key itself never leaves the server
        "has_key": bool(key),
        "model": (row.model if row else None) or d["model"],
        "embedding_model": (row.embedding_model if row else None) or d["embedding_model"],
        "base_url": (row.base_url if row else None) or d["base_url"],
        "supports_embeddings": provider in EMBEDDING_PROVIDERS,
        "needs_key": provider != "ollama",
        "active_llm": bool(row and row.active_llm),
        "active_embedding": bool(row and row.active_embedding),
    }


@router.get("/providers")
def list_providers(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = {r.provider: r for r in db.scalars(select(ProviderSetting))}
    return [_out(rows.get(p), p) for p in PROVIDERS]


@router.put("/providers/{provider}")
def save_provider(provider: str, body: ProviderIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    row = _row(db, provider)
    fields = body.model_dump(exclude_unset=True)
    if "api_key" in fields:
        key = (fields.pop("api_key") or "").strip()
        row.api_key_enc = encrypt_secret(key) if key else None
    if fields.get("base_url"):
        u = urlparse(fields["base_url"])
        if u.scheme not in ("http", "https") or not u.netloc:
            raise HTTPException(422, "base_url must be an http(s) URL")
    embedding_changed = row.active_embedding and fields.get("embedding_model") not in (None, row.embedding_model)
    for k, v in fields.items():
        setattr(row, k, (v or "").strip() or None)
    db.commit()
    if embedding_changed:
        reembed_all_task.delay()
    return _out(row, provider)


@router.put("/active")
def set_active(body: ActiveIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    if body.llm is not None:
        _row(db, body.llm)
        db.flush()
        db.execute(update(ProviderSetting).values(active_llm=ProviderSetting.provider == body.llm))
    if body.embedding is not None:
        if body.embedding not in EMBEDDING_PROVIDERS:
            raise HTTPException(422, "Embeddings need OpenAI, Gemini or Ollama")
        _row(db, body.embedding)
        db.flush()
        current = db.scalar(select(ProviderSetting.provider).where(ProviderSetting.active_embedding.is_(True)))
        db.execute(update(ProviderSetting).values(active_embedding=ProviderSetting.provider == body.embedding))
        if current != body.embedding:
            db.commit()
            reembed_all_task.delay()  # vectors from different models are not comparable
    db.commit()
    return list_providers(_, db)


@router.post("/providers/{provider}/test")
def test_provider(provider: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Live check with the stored key: a tiny extraction, plus an embedding where supported."""
    row = db.get(ProviderSetting, provider)
    if not row:
        raise HTTPException(404, "Save the provider first")
    cfg = build_config(row)
    out = {"provider": provider, "llm": None, "embedding": None}
    try:
        res = extract_invoices(cfg, "INVOICE No: T-1\nDate: 2025-01-05\nFrom: Acme Ltd\nTotal: USD 10.00")
        out["llm"] = {"ok": True, "invoices": len(res.invoices)}
    except Exception as e:  # report any provider/SDK failure to the admin instead of a bare 500
        out["llm"] = {"ok": False, "error": str(e)[:500]}
    if provider in EMBEDDING_PROVIDERS:
        try:
            out["embedding"] = {"ok": True, "dims": len(embed(cfg, ["test"])[0])}
        except Exception as e:
            out["embedding"] = {"ok": False, "error": str(e)[:500]}
    return out
