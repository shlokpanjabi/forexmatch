"""Test configuration.

Integration tests run against a real PostgreSQL database — the engine's
behaviour around NULLs, CHECK constraints and JSONB is part of what we are
testing, so an in-memory substitute would not prove much. The database is
created and seeded once per session and is separate from the development one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB = os.environ.get("FOREXMATCH_TEST_DB", "forexmatch_test")

# Must be set before app.config is imported anywhere, since settings are cached.
os.environ["DATABASE_URL"] = f"postgresql+asyncpg://localhost:5432/{TEST_DB}"
os.environ.setdefault("MODEL_PROVIDER", "mock")
os.environ.setdefault("FX_PROVIDER", "static")
os.environ.setdefault("RESEARCH_PROVIDER", "none")
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

PSQL_BIN = os.environ.get("PSQL_BIN", "/opt/homebrew/opt/postgresql@17/bin")


def _ensure_database() -> None:
    createdb = Path(PSQL_BIN) / "createdb"
    binary = str(createdb) if createdb.exists() else "createdb"
    subprocess.run([binary, TEST_DB], capture_output=True, check=False)


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Create the schema and load the real catalogue once per test session."""
    _ensure_database()

    import asyncio

    from app.db.models import Base
    from app.db.session import dispose_engine, get_engine

    async def build() -> None:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await dispose_engine()

    asyncio.run(build())

    # Load the same sourced catalogue the application uses.
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "seed_cards.py")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(BACKEND_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"seeding the test database failed:\n{result.stdout}\n{result.stderr}")


@pytest_asyncio.fixture
async def db_session():
    """A session on its own engine.

    pytest-asyncio gives each test a fresh event loop, and a pooled asyncpg
    connection cannot outlive the loop it was opened on — so each test gets an
    unpooled engine that is disposed with it.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import get_settings

    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
def static_fx(monkeypatch):
    """Fixed rates so cost assertions do not move with the market."""
    from decimal import Decimal

    from app.fx import provider as provider_module

    rates = {
        ("GBP", "INR"): Decimal("112.50"),
        ("USD", "INR"): Decimal("88.00"),
        ("EUR", "INR"): Decimal("95.00"),
    }
    original = provider_module.build_provider
    monkeypatch.setattr(
        provider_module, "build_provider", lambda *a, **k: provider_module.StaticProvider(rates)
    )
    yield rates
    monkeypatch.setattr(provider_module, "build_provider", original)
