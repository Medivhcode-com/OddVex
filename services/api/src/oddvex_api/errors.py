"""Consistent error envelope: ``{"error": {"code", "message", "details"?}}``."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth.security import PasswordHashBusy
from .quant import QuantError

logger = logging.getLogger("oddvex.errors")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def not_found(what: str, identifier: str | None = None) -> ApiError:
    suffix = f" '{identifier}'" if identifier else ""
    return ApiError(404, "not_found", f"{what}{suffix} was not found")


def envelope(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
}

#: Reusable OpenAPI response declarations.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"},
}
AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing or invalid credentials"},
    **ERROR_RESPONSES,
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Resource not found"},
}
RATE_LIMIT_RESPONSE: dict[int | str, dict[str, Any]] = {
    429: {"model": ErrorResponse, "description": "Too many requests"},
}


def _clean_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for err in errors:
        cleaned.append(
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "message": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
        )
    return cleaned


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            envelope(exc.code, exc.message, exc.details),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(PasswordHashBusy)
    async def _password_hash_busy(request: Request, exc: PasswordHashBusy) -> JSONResponse:
        # Same status, code, details and header as a rate-limited request, so clients
        # need no new case. Imported here because ratelimit.py imports this module.
        from .ratelimit import too_many_requests

        logger.warning("password_hash_busy", extra={"path": request.url.path})
        shed = too_many_requests(exc.retry_after_seconds)
        return JSONResponse(
            envelope(shed.code, shed.message, shed.details),
            status_code=shed.status_code,
            headers=shed.headers,
        )

    @app.exception_handler(QuantError)
    async def _quant_error(_: Request, exc: QuantError) -> JSONResponse:
        return JSONResponse(envelope(exc.code, exc.message), status_code=422)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            envelope(
                "validation_error",
                "Request validation failed",
                _clean_validation_errors(list(exc.errors())),
            ),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
        return JSONResponse(
            envelope(code, message),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )
