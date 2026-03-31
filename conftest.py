"""Pytest configuration — allows unit tests to run without a live backend.

Sets required env vars so pydantic_settings doesn't fail on missing DATABASE_URL,
and resets the module-level connection pool singletons between test sessions
so tests don't bleed state into each other.
"""
import os

import pytest

# Provide dummy env vars before any app module is imported.
# Real values are only needed for integration tests.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_dummy")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "")


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset DB + Redis pool singletons between tests to prevent state leakage."""
    import app.store.cache as cache_mod
    import app.store.db as db_mod

    cache_mod._redis_pool = None
    db_mod._pool = None
    yield
    cache_mod._redis_pool = None
    db_mod._pool = None
