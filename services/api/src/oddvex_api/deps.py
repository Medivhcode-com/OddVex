"""FastAPI dependencies shared by all routers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .auth.security import decode_access_token
from .cache import Cache
from .config import Settings
from .db import AuditLog, User
from .errors import ApiError
from .providers import SportsDataProvider
from .ratelimit import client_ip

_bearer = HTTPBearer(auto_error=False, description="JWT access token from /v1/auth/login")


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_provider(request: Request) -> SportsDataProvider:
    return request.app.state.provider  # type: ignore[no-any-return]


def get_cache(request: Request) -> Cache:
    return request.app.state.cache  # type: ignore[no-any-return]


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ProviderDep = Annotated[SportsDataProvider, Depends(get_provider)]
CacheDep = Annotated[Cache, Depends(get_cache)]
DbDep = Annotated[Session, Depends(get_db)]


def get_optional_user(
    db: DbDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """The authenticated user, or ``None`` when no token was sent.

    A token that is present but invalid is always rejected.
    """
    if credentials is None:
        return None
    claims = decode_access_token(credentials.credentials, settings.jwt_secret)
    if claims is None:
        raise ApiError(
            401,
            "invalid_token",
            "The access token is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, str(claims["sub"]))
    if user is None or not user.is_active:
        raise ApiError(
            401,
            "invalid_token",
            "The access token is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(user: OptionalUserDep) -> User:
    if user is None:
        raise ApiError(
            401,
            "not_authenticated",
            "Authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUserDep) -> User:
    if user.role != "admin":
        raise ApiError(403, "forbidden", "Administrator role required")
    return user


AdminDep = Annotated[User, Depends(require_admin)]


def write_audit(
    db: Session,
    request: Request | None,
    action: str,
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add an audit row to the session (committed with the caller's transaction)."""
    db.add(
        AuditLog(
            action=action,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            ip=client_ip(request) if request is not None else None,
            request_id=getattr(request.state, "request_id", None) if request is not None else None,
            details=details,
        )
    )
