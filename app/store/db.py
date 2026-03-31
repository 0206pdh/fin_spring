from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg_pool import ConnectionPool

from app.config import settings

logger = logging.getLogger("app.store.db")

_pool: ConnectionPool | None = None


def _database_url() -> str:
    return os.getenv("DATABASE_URL") or settings.database_url


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        url = _database_url()
        if not url:
            raise ValueError("DATABASE_URL is missing. Set DATABASE_URL in .env.")
        _pool = ConnectionPool(url, min_size=2, max_size=10, open=True)
        logger.info("psycopg3 ConnectionPool initialized min=2 max=10")
    return _pool


@contextmanager
def get_db() -> Generator[psycopg.Connection, None, None]:
    """Context manager: yields a pooled psycopg3 connection.

    Auto-commits on clean exit, rolls back on exception, returns connection
    to pool on exit. Replaces the old per-call psycopg.connect() pattern.
    """
    with get_pool().connection() as conn:
        yield conn


def init_db() -> None:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                published_at TIMESTAMPTZ NOT NULL,
                sector TEXT NOT NULL,
                source TEXT NOT NULL,
                payload JSONB NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS normalized_events (
                raw_event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                policy_domain TEXT NOT NULL,
                risk_signal TEXT NOT NULL,
                rate_signal TEXT NOT NULL,
                geo_signal TEXT NOT NULL,
                sector_impacts JSONB NOT NULL,
                sentiment TEXT NOT NULL,
                rationale TEXT NOT NULL,
                channels JSONB NOT NULL,
                confidence DOUBLE PRECISION NOT NULL,
                regime JSONB NOT NULL,
                baseline JSONB NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scored_events (
                raw_event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                policy_domain TEXT NOT NULL,
                risk_signal TEXT NOT NULL,
                rate_signal TEXT NOT NULL,
                geo_signal TEXT NOT NULL,
                sector_impacts JSONB NOT NULL,
                sentiment TEXT NOT NULL,
                rationale TEXT NOT NULL,
                fx_state TEXT NOT NULL,
                sector_scores JSONB NOT NULL,
                total_score DOUBLE PRECISION NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                channels JSONB NOT NULL,
                confidence DOUBLE PRECISION NOT NULL,
                regime JSONB NOT NULL,
                baseline JSONB NOT NULL
            )
            """
        )

        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS policy_domain TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS risk_signal TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS rate_signal TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS geo_signal TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS channels JSONB NOT NULL DEFAULT '[]'")
        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6")
        cur.execute(
            "ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS regime JSONB NOT NULL DEFAULT '{\"risk_sentiment\":\"neutral\",\"volatility\":\"elevated\",\"liquidity\":\"neutral\"}'"
        )
        cur.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS baseline JSONB NOT NULL DEFAULT '{}'")

        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS policy_domain TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS risk_signal TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS rate_signal TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS geo_signal TEXT NOT NULL DEFAULT ''")
        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS channels JSONB NOT NULL DEFAULT '[]'")
        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6")
        cur.execute(
            "ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS regime JSONB NOT NULL DEFAULT '{\"risk_sentiment\":\"neutral\",\"volatility\":\"elevated\",\"liquidity\":\"neutral\"}'"
        )
        cur.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS baseline JSONB NOT NULL DEFAULT '{}'")
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE scored_events ALTER COLUMN total_score TYPE DOUBLE PRECISION USING total_score::double precision;
            EXCEPTION
                WHEN undefined_column THEN NULL;
                WHEN datatype_mismatch THEN NULL;
            END $$;
            """
        )

        # Backward compatibility for older schema columns.
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE normalized_events ALTER COLUMN region DROP NOT NULL;
            EXCEPTION
                WHEN undefined_column THEN NULL;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE normalized_events ALTER COLUMN country DROP NOT NULL;
            EXCEPTION
                WHEN undefined_column THEN NULL;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE normalized_events ALTER COLUMN fx_theme DROP NOT NULL;
            EXCEPTION
                WHEN undefined_column THEN NULL;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE scored_events ALTER COLUMN region DROP NOT NULL;
            EXCEPTION
                WHEN undefined_column THEN NULL;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE scored_events ALTER COLUMN country DROP NOT NULL;
            EXCEPTION
                WHEN undefined_column THEN NULL;
            END $$;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE scored_events ALTER COLUMN fx_theme DROP NOT NULL;
            EXCEPTION
                WHEN undefined_column THEN NULL;
            END $$;
            """
        )

        conn.commit()
