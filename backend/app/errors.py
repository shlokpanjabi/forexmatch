"""Structured API errors (BUILD.md section 64).

Clients get a stable machine-readable code and a sentence safe to show a user.
Stack traces, SQL, credentials and internal identifiers never cross this
boundary.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """An error we intend the client to see."""

    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ProfileIncompleteError(AppError):
    status_code = 422
    code = "PROFILE_INCOMPLETE"


class FXUnavailableError(AppError):
    status_code = 503
    code = "FX_PROVIDER_UNAVAILABLE"


class RecommendationFailedError(AppError):
    status_code = 503
    code = "RECOMMENDATION_FAILED"


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if extra:
        payload["error"].update(extra)
    return payload


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info("api.error", code=exc.code, path=request.url.path)
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                "INVALID_REQUEST",
                "The request could not be understood.",
                details=[
                    {"field": ".".join(str(p) for p in e.get("loc", [])), "problem": e.get("msg")}
                    for e in exc.errors()[:10]
                ],
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "NOT_FOUND", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(codes.get(exc.status_code, "REQUEST_FAILED"), str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the detail server-side; return nothing that leaks internals.
        logger.exception("api.unhandled", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "Something went wrong. Please try again."),
        )
