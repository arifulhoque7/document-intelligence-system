from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import User
from app.core.security import decode_token

COOKIE = "docintel_session"


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:]  # API clients and scripts
    claims = decode_token(token) if token else None
    user = db.get(User, int(claims["sub"])) if claims else None
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user
