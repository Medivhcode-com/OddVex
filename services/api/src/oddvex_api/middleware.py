"""Request-id, access logging and security headers."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class BodySizeLimitMiddleware:
    """Reject request bodies larger than ``max_bytes`` with 413 in the error envelope.

    A declared ``Content-Length`` over the limit is refused before the body is read.
    Bodies without a usable length (chunked uploads) are counted while they are read and
    refused as soon as they pass the limit, so an oversized body is never buffered.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def _message(self) -> str:
        return f"Request body is larger than the {self.max_bytes} byte limit"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared: int | None = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None
        if declared is not None and declared > self.max_bytes:
            response = JSONResponse(
                envelope("payload_too_large", self._message(), {"max_body_bytes": self.max_bytes}),
                status_code=413,
                headers={"Connection": "close"},
            )
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Raised inside the route's body read; FastAPI re-raises HTTP
                    # exceptions from there and the error handler renders the envelope.
                    raise StarletteHTTPException(status_code=413, detail=self._message())
            return message

        await self.app(scope, limited_receive, send)


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
        if path.startswith(
            ("/v1/auth", "/v1/me", "/v1/bets", "/v1/sync", "/v1/admin", "/v1/watchlist", "/v1/dev")
        ):
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
