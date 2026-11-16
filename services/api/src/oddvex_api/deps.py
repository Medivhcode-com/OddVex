"""FastAPI dependencies shared by all routers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .auth.security import decode_access_token
from .board import Board
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


def sync_admin_role(db: Session, request: Request | None, user: User, settings: Settings) -> bool:
    """Make ``user.role`` agree with ``ODDVEX_ADMIN_EMAILS``. Returns whether it changed.

    The allowlist is the single source of the admin role. An address on it gets the role
    (audited as ``role.granted``); an address no longer on it loses the role (audited as
    ``role.removed``). While the ``email_flows`` flag is on, the role is only granted
    once the email address has been confirmed, so registering a listed address first
    proves nothing. Called at registration, at login and on every token use. Nothing is
    committed here.
    """
    listed = user.email in settings.admin_email_set
    if user.role == "admin" and not listed:
        user.role = "user"
        write_audit(
            db,
            request,
            "role.removed",
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            details={"role": "admin", "reason": "not_in_admin_emails"},
        )
        return True
    if user.role != "admin" and listed:
        from .flags import service as flags  # imported here: flags.service imports this module

        if flags.is_enabled(db, "email_flows", settings) and not user.email_verified:
            return False
        user.role = "admin"
        write_audit(
            db,
            request,
            "role.granted",
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            details={"role": "admin", "source": "admin_emails"},
        )
        return True
    return False


def _authenticate(
    request: Request,
    db: Session,
    settings: Settings,
    credentials: HTTPAuthorizationCredentials | None,
    *,
    allow_suspended: bool,
) -> User | None:
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
    # A password change or a logout bumps ``token_version``; tokens issued before it carry
    # the old value.
    if user is None or not user.is_active or claims.get("ver", 0) != user.token_version:
        raise ApiError(
            401,
            "invalid_token",
            "The access token is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status == "suspended" and not allow_suspended:
        raise ApiError(
            401,
            "account_suspended",
            "This account is suspended",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if sync_admin_role(db, request, user, settings):
        db.commit()
    return user


def get_optional_user(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """The authenticated user, or ``None`` when no token was sent.

    A token that is present but invalid is always rejected.
    """
    return _authenticate(request, db, settings, credentials, allow_suspended=False)


OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]


def _not_authenticated() -> ApiError:
    return ApiError(
        401,
        "not_authenticated",
        "Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(user: OptionalUserDep) -> User:
    if user is None:
        raise _not_authenticated()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_data_rights_user(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """The authenticated user, **including a suspended one**.

    Only for the two data-rights routes, ``GET /v1/me/export`` and ``DELETE /v1/me``: a
    suspension must not stop someone from getting or erasing their data. Every other
    route uses :func:`get_current_user`, which rejects a suspended account.
    """
    user = _authenticate(request, db, settings, credentials, allow_suspended=True)
    if user is None:
        raise _not_authenticated()
    return user


DataRightsUserDep = Annotated[User, Depends(get_data_rights_user)]


def require_admin(user: CurrentUserDep) -> User:
    if user.role != "admin":
        raise ApiError(403, "forbidden", "Administrator role required")
    return user


AdminDep = Annotated[User, Depends(require_admin)]


def get_board(provider: ProviderDep, settings: SettingsDep, cache: CacheDep) -> Board:
    return Board(provider, settings, cache)


BoardDep = Annotated[Board, Depends(get_board)]


def get_now(provider: ProviderDep) -> datetime:
    """The application's clock: the data provider's ``now()`` (wall-clock time in
    production, a fixed instant in tests)."""
    return provider.now()


NowDep = Annotated[datetime, Depends(get_now)]
