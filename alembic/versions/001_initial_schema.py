"""001 — Initial schema migration.

Migrates existing init_db() DDL into Alembic version control.

Why this matters:
- The previous init_db() had 17 ALTER TABLE statements to patch schema drift.
  This migration captures the canonical final state cleanly.
- Future schema changes will be a new migration file, not another ALTER hack.

Revision: 001
"""
from __future__ import annotations

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
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

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS normalized_events (
            raw_event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL DEFAULT '',
            policy_domain TEXT NOT NULL DEFAULT '',
            risk_signal TEXT NOT NULL DEFAULT '',
            rate_signal TEXT NOT NULL DEFAULT '',
            geo_signal TEXT NOT NULL DEFAULT '',
            sector_impacts JSONB NOT NULL DEFAULT '{}',
            sentiment TEXT NOT NULL DEFAULT 'neutral',
            rationale TEXT NOT NULL DEFAULT '',
            channels JSONB NOT NULL DEFAULT '[]',
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6,
            regime JSONB NOT NULL DEFAULT '{"risk_sentiment":"neutral","volatility":"elevated","liquidity":"neutral"}',
            baseline JSONB NOT NULL DEFAULT '{}'
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scored_events (
            raw_event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL DEFAULT '',
            policy_domain TEXT NOT NULL DEFAULT '',
            risk_signal TEXT NOT NULL DEFAULT '',
            rate_signal TEXT NOT NULL DEFAULT '',
            geo_signal TEXT NOT NULL DEFAULT '',
            sector_impacts JSONB NOT NULL DEFAULT '{}',
            sentiment TEXT NOT NULL DEFAULT 'neutral',
            rationale TEXT NOT NULL DEFAULT '',
            fx_state TEXT NOT NULL DEFAULT '',
            sector_scores JSONB NOT NULL DEFAULT '{}',
            total_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            created_at TIMESTAMPTZ NOT NULL,
            channels JSONB NOT NULL DEFAULT '[]',
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6,
            regime JSONB NOT NULL DEFAULT '{"risk_sentiment":"neutral","volatility":"elevated","liquidity":"neutral"}',
            baseline JSONB NOT NULL DEFAULT '{}'
        )
        """
    )

    # Indexes for common query patterns
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_events_published_at ON raw_events (published_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scored_events_created_at ON scored_events (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scored_events_risk_signal ON scored_events (risk_signal)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scored_events")
    op.execute("DROP TABLE IF EXISTS normalized_events")
    op.execute("DROP TABLE IF EXISTS raw_events")
