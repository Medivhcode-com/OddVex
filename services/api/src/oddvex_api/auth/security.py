"""Password hashing (argon2id) and JWT access tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_hasher = PasswordHasher()
# Verified against when the account does not exist, to keep login timing uniform.
_DUMMY_HASH = _hasher.hash("oddvex-timing-equaliser")

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "oddvex-api"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (Argon2Error, InvalidHashError):
        return False


def create_access_token(
    user_id: str, role: str, secret: str, ttl_minutes: int, now: datetime | None = None
) -> tuple[str, int]:
    issued = now or datetime.now(UTC)
    ttl_seconds = ttl_minutes * 60
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iss": JWT_ISSUER,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM), ttl_seconds


def decode_access_token(token: str, secret: str) -> dict[str, Any] | None:
    """Return the claims, or ``None`` if the token is invalid or expired."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    return claims
