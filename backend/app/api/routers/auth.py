import logging

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.api.deps import COOKIE, admin_user, current_user
from app.models import User
from app.core.security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger(__name__)
_redis = redis.Redis.from_url(get_settings().redis_url, socket_timeout=1)
MAX_ATTEMPTS = 10  # per IP+email per 15 minutes


class LoginIn(BaseModel):
    email: str
    password: str


def _rate_limited(key: str) -> bool:
    try:
        n = _redis.incr(key)
        if n == 1:
            _redis.expire(key, 900)
        return n > MAX_ATTEMPTS
    except redis.RedisError:
        log.warning("Login rate limiter unavailable (Redis down)")
        return False


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if _rate_limited(f"login:{request.client.host if request.client else '-'}:{email}"):
        raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user.id, user.role)
    cfg = get_settings()
    response.set_cookie(
        COOKIE, token, httponly=True, samesite="strict", secure=cfg.cookie_secure, max_age=cfg.jwt_ttl_minutes * 60, path="/"
    )
    return {"id": user.id, "email": user.email, "role": user.role, "token": token}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


class UserIn(BaseModel):
    email: EmailStr
    password: str
    role: str = "reviewer"


@router.get("/users")
def list_users(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [{"id": u.id, "email": u.email, "role": u.role} for u in db.scalars(select(User).order_by(User.id))]


@router.post("/users", status_code=201)
def create_user(body: UserIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    if body.role not in ("admin", "reviewer"):
        raise HTTPException(422, "role must be admin or reviewer")
    if len(body.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "User already exists")
    u = User(email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    db.commit()
    return {"id": u.id, "email": u.email, "role": u.role}
