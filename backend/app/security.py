"""Пароли (bcrypt, cost 12) и JWT (ТЗ 6.1, 8.4)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings
from app.errors import ApiError

BCRYPT_COST = 12
MAX_PASSWORD_BYTES = 72  # ограничение bcrypt; более длинные пароли отклоняются, а не усекаются
ALGORITHM = "HS256"


def password_acceptable(password: str) -> bool:
    return 0 < len(password.encode("utf-8")) <= MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    if not password_acceptable(password):
        raise ValueError("password must be 1..72 bytes")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or not password_acceptable(password):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def temp_password() -> str:
    return secrets.token_urlsafe(12)


def _secret() -> str:
    secret = get_settings().jwt_secret
    if len(secret) < 16:
        # Без секрета токены подделываются тривиально — лучше 503, чем молчаливая небезопасность.
        raise ApiError(503, "Service unavailable", "JWT secret is not configured")
    return secret


def create_access_token(user_id: int, organization_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "organization_id": organization_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=get_settings().jwt_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM], options={"require": ["exp", "user_id"]})
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "Token expired", "Access token has expired, please log in again")
    except jwt.PyJWTError:
        raise ApiError(401, "Invalid token", "Could not validate credentials")
