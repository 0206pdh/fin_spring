"""Alembic migration environment.

Why Alembic over init_db()?
- init_db() runs DDL on every startup: no version history, no rollback,
  ALTER TABLE hacks accumulate and become unmaintainable (see db.py lines 83-176)
- Alembic gives each schema change a versioned file with upgrade() + downgrade()
- CI/CD can run `alembic upgrade head` before app start → safe, reproducible deploys
- Reviewers can see exactly what changed between versions via git history

This env.py uses offline mode (no SQLAlchemy ORM models needed).
We work directly with raw SQL DDL to stay consistent with the existing psycopg3 codebase.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_url() -> str:
    """Resolve database URL from environment or app config."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        try:
            from app.config import settings
            url = settings.database_url
        except Exception:
            pass
    if not url:
        raise ValueError(
            "DATABASE_URL not set. "
            "Set DATABASE_URL env var or FIM_DATABASE_URL in .env before running migrations."
        )
    # Alembic uses SQLAlchemy URL format; psycopg3 uses postgresql+psycopg://
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL scripts)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    from sqlalchemy import create_engine

    url = get_url()
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
