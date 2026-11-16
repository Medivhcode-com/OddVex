from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import Settings
from ..db import User, utcnow
from ..deps import CurrentUserDep, DbDep, SettingsDep, write_audit
from ..errors import (
    AUTH_ERROR_RESPONSES,
    ERROR_RESPONSES,
    RATE_LIMIT_RESPONSE,
    ApiError,
    ErrorResponse,
)
from ..ratelimit import rate_limit
from .schemas import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from .security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


def _token_response(user: User, settings: Settings) -> TokenResponse:
    token, ttl = create_access_token(
        user.id,
        user.role,
        settings.jwt_secret,
        settings.jwt_ttl_minutes,
        token_version=user.token_version,
    )
    return TokenResponse(access_token=token, expires_in=ttl, user=UserOut.model_validate(user))


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=201,
    operation_id="register",
    summary="Create an account (21+ attestation required)",
    dependencies=[Depends(rate_limit("auth"))],
    responses={
        409: {"model": ErrorResponse, "description": "Email already registered"},
        **ERROR_RESPONSES,
        **RATE_LIMIT_RESPONSE,
    },
)
def register(
    body: RegisterRequest, request: Request, db: DbDep, settings: SettingsDep
) -> TokenResponse:
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise ApiError(409, "email_taken", "An account with this email already exists")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role="admin" if body.email in settings.admin_email_set else "user",
        age_confirmed_at=utcnow(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists") from exc
    write_audit(
        db, request, "auth.register", user_id=user.id, entity_type="user", entity_id=user.id
    )
    db.commit()
    return _token_response(user, settings)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    operation_id="login",
    summary="Exchange email + password for an access token",
    dependencies=[Depends(rate_limit("auth"))],
    responses={**AUTH_ERROR_RESPONSES, **RATE_LIMIT_RESPONSE},
)
def login(body: LoginRequest, request: Request, db: DbDep, settings: SettingsDep) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    valid = verify_password(body.password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        write_audit(db, request, "auth.login_failed", user_id=user.id if user else None)
        db.commit()
        raise ApiError(401, "invalid_credentials", "Incorrect email or password")
    if user.role != "admin" and user.email in settings.admin_email_set:
        user.role = "admin"
    write_audit(db, request, "auth.login", user_id=user.id, entity_type="user", entity_id=user.id)
    db.commit()
    return _token_response(user, settings)


@router.get(
    "/me",
    response_model=UserOut,
    operation_id="get_me",
    summary="Current user",
    responses=AUTH_ERROR_RESPONSES,
)
def me(user: CurrentUserDep) -> UserOut:
    return UserOut.model_validate(user)


@router.delete(
    "/me",
    status_code=204,
    operation_id="delete_me",
    summary="Delete the account and all of its data",
    description=(
        "Permanently deletes the user, their bets, bet legs, watchlist, alert rules, "
        "notifications, notification preferences, staking reminder, sync connections and "
        "import runs. "
        "An audit entry containing only the opaque user id is retained."
    ),
    responses=AUTH_ERROR_RESPONSES,
)
def delete_me(user: CurrentUserDep, request: Request, db: DbDep) -> Response:
    user_id = user.id
    db.delete(user)
    write_audit(
        db, request, "account.deleted", user_id=user_id, entity_type="user", entity_id=user_id
    )
    db.commit()
    return Response(status_code=204)


@router.post(
    "/me/password",
    response_model=TokenResponse,
    operation_id="change_password",
    summary="Change the password and get a fresh access token",
    description=(
        "Every access token issued before the change stops working immediately, including "
        "the one used for this request. The response carries a replacement token."
    ),
    dependencies=[Depends(rate_limit("auth"))],
    responses={
        400: {"model": ErrorResponse, "description": "The current password is not correct"},
        **AUTH_ERROR_RESPONSES,
        **RATE_LIMIT_RESPONSE,
    },
)
def change_password(
    body: PasswordChangeRequest,
    user: CurrentUserDep,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
) -> TokenResponse:
    if not verify_password(body.current_password, user.password_hash):
        write_audit(
            db,
            request,
            "auth.password_change_failed",
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )
        db.commit()
        raise ApiError(
            400, "invalid_credentials", "The password was not changed. Check the details."
        )
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    user.password_changed_at = utcnow()
    write_audit(
        db, request, "auth.password_changed", user_id=user.id, entity_type="user", entity_id=user.id
    )
    db.commit()
    return _token_response(user, settings)
