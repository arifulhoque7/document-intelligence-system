import logging
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.api.routers import auth, documents, invoices, search, settings, stats
from app.core.config import get_settings
from app.core.db import SessionLocal, engine, init_db
from app.core.security import hash_password
from app.models import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
cfg = get_settings()



@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        if not db.scalar(select(User).limit(1)):
            db.add(User(email=cfg.admin_email.lower(), password_hash=hash_password(cfg.admin_password), role="admin"))
            db.commit()
    yield


app = FastAPI(title="Document Intelligence API", version="1.0.0", lifespan=lifespan)
if cfg.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins.split(","), allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger UI needs its own scripts
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


for r in (auth, documents, invoices, search, settings, stats):
    app.include_router(r.router)


@app.get("/health", tags=["ops"])
def health():
    checks = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # report, do not crash
        checks["database"] = f"error: {type(e).__name__}"
    try:
        redis.Redis.from_url(cfg.redis_url, socket_timeout=1).ping()
        checks["redis"] = "ok"
    except redis.RedisError as e:
        checks["redis"] = f"error: {type(e).__name__}"
    return {"status": "ok" if all(v == "ok" for v in checks.values()) else "degraded", **checks}
