from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from jwt.exceptions import PyJWTError

from app.config import settings


def _build_payload(
    *,
    business_id: str,
    token_type: str,
    expires_delta: timedelta,
    token_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    jti = token_id or uuid4().hex
    payload: dict[str, Any] = {
        "sub": business_id,
        "business_id": business_id,
        "token_type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return payload


def create_access_token(*, business_id: str, expires_delta: timedelta | None = None) -> tuple[str, str, int]:
    expires = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = _build_payload(business_id=business_id, token_type="access", expires_delta=expires)
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, payload["jti"], int(expires.total_seconds())


def create_refresh_token(*, business_id: str, expires_delta: timedelta | None = None, token_id: str | None = None) -> tuple[str, str, int]:
    expires = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = _build_payload(
        business_id=business_id,
        token_type="refresh",
        expires_delta=expires,
        token_id=token_id,
    )
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, payload["jti"], int(expires.total_seconds())


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_token_type(payload: dict[str, Any]) -> str:
    return str(payload.get("token_type", ""))


def get_token_jti(payload: dict[str, Any]) -> str:
    return str(payload.get("jti", ""))


def get_business_id(payload: dict[str, Any]) -> str:
    return str(payload.get("business_id", payload.get("sub", "")))


def is_token_expired_error(error: Exception) -> bool:
    return isinstance(error, PyJWTError)
