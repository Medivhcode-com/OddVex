from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import Settings
from ..db import AuditLog, User, utcnow
from ..deps import (
    CurrentUserDep,
    DataRightsUserDep,
    DbDep,
    SettingsDep,
    sync_admin_role,
    write_audit,
)
from ..errors import (
    AUTH_ERROR_RESPONSES,
    ERROR_RESPONSES,
    RATE_LIMIT_RESPONSE,
    ApiError,
    ErrorResponse,
)
from ..flags import service as flags
from ..flags.service import require_flag
from ..mailer import service as mailer
from ..ratelimit import (
    check_login_allowed,
    clear_login_failures,
    client_ip,
    limit_account_action,
    rate_limit,
    record_login_failure,
)
from ..schemas import MessageOut
from .schemas import (
    EmailVerificationConfirmRequest,
    EmailVerificationOut,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from .security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

_FEATURE_OFF: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorResponse, "description": "The feature is switched off"}
}
_BAD_TOKEN: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorResponse, "description": "The token is invalid, used or expired"}
}
#: The one answer to every password-reset request, whether or not the account exists.
RESET_REQUESTED = MessageOut(
    message="If an account exists for that email, a password reset email has been queued."
)


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
        role="user",
        age_confirmed_at=utcnow(),
        last_login_at=utcnow(),
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
    # With ``email_flows`` on, a listed address only becomes an administrator once it is
    # confirmed, so nothing is granted here; with it off, it is granted at once.
    sync_admin_role(db, request, user, settings)
    if flags.is_enabled(db, "email_flows", settings):
        mailer.queue_verification_email(db, request.app.state.email_sender, settings, user)
    db.commit()
    return _token_response(user, settings)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    operation_id="login",
    summary="Exchange email + password for an access token",
    description=(
        "Besides the per-IP limit, an email address with too many failed logins inside "
        "the window (8 in 15 minutes by default) gets `429 rate_limited` until the window "
        "moves on, from any IP and whether or not an account exists for it. A suspended "
        "account gets `403 account_suspended` once the password is correct."
    ),
    dependencies=[Depends(rate_limit("auth"))],
    responses={
        403: {"model": ErrorResponse, "description": "The account is suspended"},
        **AUTH_ERROR_RESPONSES,
        **RATE_LIMIT_RESPONSE,
    },
)
def login(body: LoginRequest, request: Request, db: DbDep, settings: SettingsDep) -> TokenResponse:
    check_login_allowed(request, body.email)
    user = db.scalar(select(User).where(User.email == body.email))
    valid = verify_password(body.password, user.password_hash if user else None)
    if user is None or not valid or not user.is_active:
        record_login_failure(request, body.email)
        write_audit(db, request, "auth.login_failed", user_id=user.id if user else None)
        db.commit()
        raise ApiError(401, "invalid_credentials", "Incorrect email or password")
    if user.status == "suspended":
        write_audit(
            db,
            request,
            "auth.login_suspended",
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )
        db.commit()
        raise ApiError(
            403, "account_suspended", "This account can't be used right now. Contact support."
        )
    clear_login_failures(request, body.email)
    user.last_login_at = utcnow()
    sync_admin_role(db, request, user, settings)
    write_audit(db, request, "auth.login", user_id=user.id, entity_type="user", entity_id=user.id)
    db.commit()
    return _token_response(user, settings)


@router.post(
    "/auth/logout",
    status_code=204,
    operation_id="logout",
    summary="Log out everywhere",
    description=(
        "Revokes every access token of the account, not only the one that made this "
        "request: the account's token version is bumped, so each token issued before it "
        "is rejected with `401 invalid_token` from then on, on every device. There are "
        "no per-session tokens in this build. Sign in again to get a new token. The "
        "logout is recorded in the audit log."
    ),
    responses=AUTH_ERROR_RESPONSES,
)
def logout(user: CurrentUserDep, request: Request, db: DbDep) -> Response:
    user.token_version += 1
    write_audit(db, request, "auth.logout", user_id=user.id, entity_type="user", entity_id=user.id)
    db.commit()
    return Response(status_code=204)


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
        "notifications, notification preferences, staking reminder, sync connections, "
        "import runs, email tokens and outbox emails, and everything in the community: "
        "the profile, follows in both directions, likes, blocks, reports made, comments "
        "and every pick, graded ones included, so no public record is left without an "
        "account. An audit entry containing only the opaque user id is retained. A "
        "suspended account can still call this route."
    ),
    responses=AUTH_ERROR_RESPONSES,
)
def delete_me(user: DataRightsUserDep, request: Request, db: DbDep) -> Response:
    user_id = user.id
    suspended = user.status == "suspended"
    db.delete(user)
    write_audit(
        db,
        request,
        "account.deleted",
        user_id=user_id,
        entity_type="user",
        entity_id=user_id,
        details={"account_status": "suspended"} if suspended else None,
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


# --------------------------------------------------------- email verification
@router.post(
    "/auth/verify-email/request",
    response_model=MessageOut,
    status_code=202,
    operation_id="request_email_verification",
    summary="Queue a new email confirmation link",
    description=(
        "Queues a confirmation email for the signed-in user. **No email is sent in this "
        "build**: the message is written to the outbox table. The link works once and "
        "expires after 24 hours; a new request replaces the earlier link. An unconfirmed "
        "address blocks nothing. Behind the `email_flows` flag."
    ),
    dependencies=[Depends(require_flag("email_flows")), Depends(rate_limit("auth"))],
    responses={**AUTH_ERROR_RESPONSES, **RATE_LIMIT_RESPONSE, **_FEATURE_OFF},
)
def request_email_verification(
    user: CurrentUserDep, request: Request, db: DbDep, settings: SettingsDep
) -> MessageOut:
    if user.email_verified:
        return MessageOut(message="Your email address is already confirmed.")
    limit_account_action(request, "verify-email", user.id, settings.email_requests_per_window)
    mailer.queue_verification_email(db, request.app.state.email_sender, settings, user)
    write_audit(
        db,
        request,
        "auth.email_verification_requested",
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return MessageOut(message="A confirmation email has been queued for your address.")


@router.post(
    "/auth/verify-email/confirm",
    response_model=EmailVerificationOut,
    operation_id="confirm_email_verification",
    summary="Confirm an email address with the token from the link",
    description=(
        "No sign-in needed: the token identifies the account. A token works once; a used, "
        "expired or unknown token is `400 invalid_or_expired_token`."
    ),
    dependencies=[Depends(require_flag("email_flows")), Depends(rate_limit("auth"))],
    responses={**_BAD_TOKEN, **ERROR_RESPONSES, **RATE_LIMIT_RESPONSE, **_FEATURE_OFF},
)
def confirm_email_verification(
    body: EmailVerificationConfirmRequest, request: Request, db: DbDep
) -> EmailVerificationOut:
    user = mailer.consume_token(db, body.token, mailer.VERIFY_EMAIL)
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    write_audit(
        db, request, "auth.email_verified", user_id=user.id, entity_type="user", entity_id=user.id
    )
    # A listed address becomes an administrator once it is confirmed.
    sync_admin_role(db, request, user, request.app.state.settings)
    db.commit()
    return EmailVerificationOut(email_verified=True)


# ------------------------------------------------------------- password reset
def _queue_password_reset(app: FastAPI, email: str, ip: str, request_id: str | None) -> None:
    """Runs after the response has gone out, so the response takes the same time and
    looks the same whether or not an account exists for ``email``."""
    with app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None or not user.is_active:
            return
        mailer.queue_password_reset_email(db, app.state.email_sender, app.state.settings, user)
        db.add(
            AuditLog(
                action="auth.password_reset_requested",
                user_id=user.id,
                entity_type="user",
                entity_id=user.id,
                ip=ip,
                request_id=request_id,
            )
        )
        db.commit()


@router.post(
    "/auth/password-reset/request",
    response_model=MessageOut,
    status_code=202,
    operation_id="request_password_reset",
    summary="Queue a password reset link",
    description=(
        "Always answers 202 with the same body, whether or not an account exists for the "
        "email; the lookup and the email are handled after the response is sent. **No "
        "email is sent in this build**: the message is written to the outbox table. The "
        "link works once and expires after 60 minutes. Limited per IP and per email "
        "address. Behind the `email_flows` flag."
    ),
    dependencies=[Depends(require_flag("email_flows")), Depends(rate_limit("auth"))],
    responses={**ERROR_RESPONSES, **RATE_LIMIT_RESPONSE, **_FEATURE_OFF},
)
def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    settings: SettingsDep,
) -> MessageOut:
    limit_account_action(request, "password-reset", body.email, settings.email_requests_per_window)
    background.add_task(
        _queue_password_reset,
        request.app,
        body.email,
        client_ip(request),
        getattr(request.state, "request_id", None),
    )
    return RESET_REQUESTED


@router.post(
    "/auth/password-reset/confirm",
    status_code=204,
    operation_id="confirm_password_reset",
    summary="Set a new password with the token from the link",
    description=(
        "Every access token issued before the reset stops working. The token works once; "
        "a used, expired or unknown token is `400 invalid_or_expired_token`. Sign in "
        "again afterwards: no token is returned. Using the link also confirms the email "
        "address."
    ),
    dependencies=[Depends(require_flag("email_flows")), Depends(rate_limit("auth"))],
    responses={**_BAD_TOKEN, **ERROR_RESPONSES, **RATE_LIMIT_RESPONSE, **_FEATURE_OFF},
)
def confirm_password_reset(
    body: PasswordResetConfirmRequest, request: Request, db: DbDep
) -> Response:
    user = mailer.consume_token(db, body.token, mailer.PASSWORD_RESET)
    now = utcnow()
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    user.password_changed_at = now
    if user.email_verified_at is None:
        # The link was sent to this address, so following it proves control of it.
        user.email_verified_at = now
    write_audit(
        db,
        request,
        "auth.password_reset_completed",
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    clear_login_failures(request, user.email)
    return Response(status_code=204)
