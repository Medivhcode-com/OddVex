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


# ------------------------------------------------------------- NUL characters
_NUL = "\x00"
#: Methods whose body is looked at. The others carry none that a route reads.
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _nul_error(*loc: str) -> ApiError:
    """The 422 of the validation handler, naming where the character was found."""
    return ApiError(
        422,
        "validation_error",
        "Request validation failed",
        details=[
            {
                # A name with the character in it is shown with the escape as text.
                "loc": [part.replace(_NUL, "\\u0000") for part in loc],
                "message": "Text cannot contain the NUL character",
                "type": "nul_character",
            }
        ],
    )


def _nul_in_document(document: Any) -> tuple[str, ...] | None:
    """Where a parsed JSON document has a NUL character, in a value or in a key; None
    when it has none. Walks without recursion: a body can be nested deeply."""
    pending: list[tuple[tuple[str, ...], Any]] = [((), document)]
    while pending:
        loc, value = pending.pop()
        if isinstance(value, str):
            if _NUL in value:
                return loc
        elif isinstance(value, dict):
            for key, item in value.items():
                if _NUL in key:
                    return (*loc, key)
                pending.append(((*loc, key), item))
        elif isinstance(value, list):
            pending.extend(((*loc, str(index)), item) for index, item in enumerate(value))
    return None


async def reject_nul_characters(request: Request) -> None:
    """422 when any text the client sent contains a NUL character (U+0000).

    PostgreSQL cannot store the character in a text column and the driver refuses to
    send it, so before this check it ended as a failed statement and a 500. No field of
    this API has a use for it. This runs for every route (it is a dependency of the
    application itself, see ``main.py``) and before the route's own dependencies, so the
    answer is the same whether or not the caller is signed in and whatever the text was
    meant for: path values, query values and names, and every string and key of a JSON
    body, in whatever encoding the body was sent.
    """
    for name, value in request.path_params.items():
        if isinstance(value, str) and _NUL in value:
            raise _nul_error("path", name)
    for name, value in request.query_params.multi_items():
        if _NUL in name or _NUL in value:
            raise _nul_error("query", name)
    if request.method not in _BODY_METHODS:
        return
    body = await request.body()
    # A body without a zero byte and without the escape cannot decode to the character:
    # in UTF-8 it is one of those two, and UTF-16 and UTF-32 text is full of zero bytes.
    if b"\x00" not in body and b"\\u0000" not in body:
        return
    try:
        # The same parser, and the same parsed document, the route's body is read with.
        document = await request.json()
    except (ValueError, RecursionError):
        return  # not JSON: nothing in it is read as text
    found = _nul_in_document(document)
    if found is not None:
        raise _nul_error("body", *found)


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


def sync_admin_role(
    db: Session,
    request: Request | None,
    user: User,
    settings: Settings,
    source: str = "admin_emails",
) -> bool:
    """Make ``user.role`` agree with the rule for the admin role. Returns whether it changed.

    The rule: an account is an administrator exactly when its address is in
    ``ODDVEX_ADMIN_EMAILS`` **and** its email address is verified. That holds in every
    environment and whatever the ``email_flows`` flag says: the list alone gives nobody
    the role, so having registered a listed address first gains nothing. Where no
    confirmation email can be followed (production today), the address is verified by
    the operator command ``scripts/bootstrap_admin.py``.

    An account that meets the rule gets the role (audited as ``role.granted`` with
    ``source``); an account that holds the role without meeting it loses it (audited as
    ``role.removed`` with the reason: the address left the list, or it is not
    verified). Called at login, when an address is confirmed and on every token use.
    Nothing is committed here.
    """
    listed = user.email in settings.admin_email_set
    entitled = listed and user.email_verified
    if user.role == "admin" and not entitled:
        user.role = "user"
        write_audit(
            db,
            request,
            "role.removed",
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            details={
                "role": "admin",
                "reason": "email_not_verified" if listed else "not_in_admin_emails",
            },
        )
        return True
    if user.role != "admin" and entitled:
        user.role = "admin"
        write_audit(
            db,
            request,
            "role.granted",
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            details={"role": "admin", "source": source},
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
