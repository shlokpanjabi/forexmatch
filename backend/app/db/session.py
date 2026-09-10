"""Async engine and session management."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings


def _is_serverless() -> bool:
    """True when running as a Vercel Function."""
    return bool(os.environ.get("VERCEL"))


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Build the engine, adapting to where it is running.

    A long-lived server wants a connection pool. A serverless function does not:
    instances come and go, and holding pooled sockets across invocations
    exhausts the database's connection limit. There we use NullPool and let the
    provider's own pooler (PgBouncer, in Neon's case) do the pooling.

    PgBouncer in transaction mode also cannot support asyncpg's implicit
    prepared statements, so those are disabled — without this every query fails
    with "prepared statement already exists" once connections are reused.
    """
    settings = get_settings()

    # asyncpg does not read libpq's sslmode, and those parameters were stripped
    # from the URL during validation — so TLS is requested explicitly here.
    connect_args: dict[str, object] = {}
    if settings.database_requires_tls:
        connect_args["ssl"] = "require"

    if _is_serverless():
        connect_args |= {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            # Names must be unique per connection behind a transaction pooler.
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        }
        return create_async_engine(
            settings.database_url, echo=False, poolclass=NullPool, connect_args=connect_args
        )

    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope for code outside the request lifecycle (tools, scripts)."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Commits on success, rolls back on error."""
    async with session_scope() as session:
        yield session


async def dispose_engine() -> None:
    await get_engine().dispose()
