"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import AnalyticsClient, get_analytics
from app.config import Settings, get_settings
from app.db.session import get_db_session
from app.errors import UnauthorizedError


async def db_dependency() -> AsyncIterator[AsyncSession]:
    async for session in get_db_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(db_dependency)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Analytics = Annotated[AnalyticsClient, Depends(get_analytics)]


async def require_admin(
    settings: AppSettings,
    x_admin_secret: Annotated[str | None, Header(alias="X-Admin-Secret")] = None,
) -> None:
    """Guard the /admin routes with a shared secret (BUILD.md section 44).

    An unset ADMIN_SECRET locks the routes rather than opening them — a missing
    configuration value must never be the thing that grants access.
    """
    import secrets

    if not settings.admin_secret:
        raise UnauthorizedError("Admin endpoints are disabled because ADMIN_SECRET is not configured.")
    if not x_admin_secret or not secrets.compare_digest(x_admin_secret, settings.admin_secret):
        raise UnauthorizedError("A valid X-Admin-Secret header is required.")


AdminGuard = Annotated[None, Depends(require_admin)]
