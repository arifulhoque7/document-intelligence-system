import base64
import os
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int, role: str) -> str:
    cfg = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=cfg.jwt_ttl_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, cfg.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _aes() -> AESGCM:
    key = base64.urlsafe_b64decode(get_settings().encryption_key)
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must be 32 bytes, base64 encoded")
    return AESGCM(key)


def encrypt_secret(plain: str) -> str:
    nonce = os.urandom(12)
    return base64.urlsafe_b64encode(nonce + _aes().encrypt(nonce, plain.encode(), None)).decode()


def decrypt_secret(token: str) -> str:
    raw = base64.urlsafe_b64decode(token)
    return _aes().decrypt(raw[:12], raw[12:], None).decode()


def mask_secret(plain: str | None) -> str | None:
    if not plain:
        return None
    return f"{plain[:3]}…{plain[-4:]}" if len(plain) > 10 else "…" + plain[-2:]
