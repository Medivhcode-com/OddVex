"""Request-id, access logging and security headers."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .errors import envelope

logger = logging.getLogger("oddvex.access")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Resource-Policy": "same-site",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, logs one JSON line per request, adds security headers."""

    def __init__(self, app, production: bool = False) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._production = production

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inbound = request.headers.get("x-request-id", "")
        request_id = inbound if _REQUEST_ID_RE.match(inbound) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled_error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            response = JSONResponse(
                envelope("internal_error", "An unexpected error occurred"), status_code=500
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        path = request.url.path
        if not path.startswith(_DOCS_PATHS):
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if path.startswith(("/v1/auth", "/v1/me", "/v1/bets", "/v1/sync", "/v1/admin")):
            response.headers.setdefault("Cache-Control", "no-store")
        if self._production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
            },
        )
        return response
