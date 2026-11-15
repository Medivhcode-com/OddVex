"""Application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import admin, data, quant_routes
from .assistant import router as assistant_router
from .auth import router as auth_router
from .bets import router as bets_router
from .cache import InMemoryTTLCache
from .config import Settings, get_settings
from .db import Base, make_engine, make_session_factory
from .errors import ErrorResponse, install_error_handlers
from .logging_config import configure_logging
from .middleware import RequestContextMiddleware
from .providers import SportsDataProvider, SyntheticProvider
from .ratelimit import SlidingWindowRateLimiter
from .sync import SyncRegistry, default_registry
from .sync import router as sync_router

logger = logging.getLogger("oddvex.app")

DESCRIPTION = """\
OddVex is a sports-betting **intelligence** API: odds comparison, player-prop research,
betting math and bet tracking. It never accepts, places or facilitates wagers.

**All sports data served by this build is synthetic.** Teams, players, sportsbooks, prices
and statistics are fictional and generated deterministically. Responses carry
`data_mode: "synthetic"`.

Conventions: JSON, snake_case, ISO-8601 UTC timestamps, string ids. Probabilities, holds, ROI
and CLV are fractions (0.05 = 5%) unless the field name ends in `_percent`. Errors use the
envelope `{"error": {"code", "message", "details"?}}`.
"""

TAGS = [
    {"name": "meta", "description": "Service and reference data."},
    {"name": "events", "description": "Events, odds comparison and line history (synthetic)."},
    {"name": "players", "description": "Players and prop research (synthetic)."},
    {"name": "quant", "description": "Calculators. Each response shows its working in `steps`."},
    {"name": "auth", "description": "Accounts. Registration requires a 21+ attestation."},
    {"name": "bets", "description": "Bet tracker. Records bets placed elsewhere; owner-scoped."},
    {"name": "sync", "description": "Sportsbook account import. Mock provider only."},
    {"name": "assistant", "description": "Rule-based assistant. No language model."},
    {"name": "admin", "description": "Administrator overview."},
]


def _custom_openapi(app: FastAPI) -> dict[str, Any]:
    """OpenAPI schema with the real error envelope instead of FastAPI's default 422 model."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=TAGS,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.setdefault("ErrorBody", ErrorResponse.model_json_schema()["$defs"]["ErrorBody"])
    components.setdefault(
        "ErrorResponse",
        {
            "type": "object",
            "title": "ErrorResponse",
            "required": ["error"],
            "properties": {"error": {"$ref": "#/components/schemas/ErrorBody"}},
        },
    )
    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for status, response in operation.get("responses", {}).items():
                if status == "422":
                    response["description"] = "Validation error"
                    response["content"] = {"application/json": {"schema": error_ref}}
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    app.openapi_schema = schema
    return schema


def create_app(
    settings: Settings | None = None,
    provider: SportsDataProvider | None = None,
    sync_registry: SyncRegistry | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_for_startup()
    configure_logging(settings.log_level)

    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.should_auto_create_tables:
            Base.metadata.create_all(engine)
        if settings.auto_seed_demo and not settings.is_production:
            from .seed import seed_demo

            with app.state.session_factory() as session:
                created = seed_demo(session, settings.demo_password, app.state.provider.now())
            logger.info("demo_seed", extra={"created_bets": created})
        logger.info("startup", extra={"env": settings.env, "provider": app.state.provider.name})
        yield
        engine.dispose()

    app = FastAPI(
        title="OddVex API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.provider = provider or SyntheticProvider(seed=settings.synthetic_seed)
    app.state.cache = InMemoryTTLCache()
    app.state.rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_window_seconds)
    app.state.sync_registry = sync_registry or default_registry()

    # Added last = outermost, so CORS headers are present on error responses too.
    app.add_middleware(RequestContextMiddleware, production=settings.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    install_error_handlers(app)

    app.include_router(data.health_router)
    app.include_router(data.router, prefix="/v1")
    app.include_router(quant_routes.router, prefix="/v1")
    app.include_router(auth_router.router, prefix="/v1")
    app.include_router(bets_router.router, prefix="/v1")
    app.include_router(sync_router.router, prefix="/v1")
    app.include_router(assistant_router.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")

    app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]
    return app


def __getattr__(name: str) -> Any:
    """Build ``app`` on first access (``uvicorn oddvex_api.main:app``).

    Lazy so that importing this module, for example to export the OpenAPI
    schema or to call :func:`create_app` in tests, never reads the environment
    or touches a database.
    """
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
