"""Configuration handling, especially URLs from managed database providers."""

from __future__ import annotations

import pytest

from app.config import Settings

NEON = (
    "postgres://user:pw@ep-cool-bird-123-pooler.eu-central-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)


def test_provider_url_is_converted_to_the_async_driver():
    """Neon and friends issue libpq-style URLs; asyncpg understands neither the
    scheme nor the query parameters."""
    settings = Settings(database_url=NEON)

    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in settings.database_url
    assert "channel_binding" not in settings.database_url
    # The parts that matter must survive intact.
    assert "user:pw@" in settings.database_url
    assert "ep-cool-bird-123-pooler.eu-central-1.aws.neon.tech" in settings.database_url
    assert settings.database_url.endswith("/neondb")


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@host:5432/db",
        "postgresql://u:p@host:5432/db",
        "postgresql+asyncpg://u:p@host:5432/db",
    ],
)
def test_every_postgres_scheme_is_accepted(url):
    assert Settings(database_url=url).database_url.startswith("postgresql+asyncpg://")


def test_a_non_postgres_url_is_rejected():
    with pytest.raises(ValueError):
        Settings(database_url="mysql://u:p@host/db")


def test_useful_query_parameters_are_kept():
    settings = Settings(database_url="postgres://u:p@host/db?application_name=forexmatch&sslmode=require")
    assert "application_name=forexmatch" in settings.database_url
    assert "sslmode" not in settings.database_url


@pytest.mark.parametrize(
    "url,expected_host,tls",
    [
        (NEON, "ep-cool-bird-123-pooler.eu-central-1.aws.neon.tech", True),
        ("postgresql+asyncpg://localhost:5432/forexmatch", "localhost", False),
        ("postgresql+asyncpg://127.0.0.1:5432/forexmatch", "127.0.0.1", False),
        ("postgresql+asyncpg://u:p@db.internal:5432/x", "db.internal", True),
    ],
)
def test_tls_is_required_for_remote_hosts_only(url, expected_host, tls):
    settings = Settings(database_url=url)
    assert settings.database_host == expected_host
    assert settings.database_requires_tls is tls


def test_alembic_gets_a_sync_driver():
    settings = Settings(database_url=NEON)
    assert settings.sync_database_url.startswith("postgresql+psycopg://")
    assert "asyncpg" not in settings.sync_database_url
