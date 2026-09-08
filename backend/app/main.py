"""FastAPI application."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.analytics import get_analytics
from app.api import admin, analytics, cards, chat, recommendations
from app.config import get_settings
from app.db.session import dispose_engine
from app.errors import register_error_handlers
from app.logging import configure_logging, new_request_id, request_id_var

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)

    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)
            logger.info("sentry.enabled")
        except Exception as exc:  # noqa: BLE001 — monitoring must not block startup
            logger.warning("sentry.init_failed", error=str(exc))

    logger.info(
        "app.startup",
        environment=settings.environment,
        model_provider=settings.model_provider,
        fx_provider=settings.fx_provider,
        analytics=settings.analytics_enabled,
    )
    yield
    get_analytics().shutdown()
    await dispose_engine()
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ForexMatch API",
        description=(
            "An agent that researches and recommends forex cards for Indian students. "
            "Recommendations are informational, not financial advice."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Secret"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Any:
        token = request_id_var.set(new_request_id())
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration = int((time.perf_counter() - started) * 1000)
            request_id_var.reset(token)
        # Streaming responses report their setup time, not their full duration.
        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=getattr(response, "status_code", None),
            duration_ms=duration,
        )
        return response

    register_error_handlers(app)

    app.include_router(chat.router)
    app.include_router(cards.router)
    app.include_router(recommendations.router)
    app.include_router(analytics.router)
    app.include_router(admin.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "environment": settings.environment,
            "model_provider": settings.model_provider,
            "fx_provider": settings.fx_provider,
        }

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, Any]:
        return {
            "name": "ForexMatch",
            "description": "Forex-card research and recommendation agent for Indian students.",
            "docs": "/docs",
            "disclaimer": (
                "This is an informational comparison, not financial advice. Card fees and "
                "terms can change. Check the provider's current terms before applying."
            ),
        }

    return app


app = create_app()
