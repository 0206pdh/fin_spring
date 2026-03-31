"""004 — seed_events table for live demo replay.

Why seed_events?
- Live demo URL must show data immediately, even with no fresh AP News articles.
- seed_replay_job (cron, every 8min) picks seed rows with replayed_count < 3
  and re-runs them through normalize → score → WS broadcast.
- replayed_count cap = 3: prevents infinite replay churn while ensuring the
  demo stays alive across a recruiter's entire review session (~20-30 min).
- FOR UPDATE SKIP LOCKED in the worker prevents duplicate processing if
  multiple worker instances run concurrently.

Revision: 004
"""
from __future__ import annotations

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS seed_events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            sector TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'seed',
            payload JSONB NOT NULL,
            replayed_count INT NOT NULL DEFAULT 0,
            last_replayed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_seed_events_replay ON seed_events (replayed_count ASC, last_replayed_at ASC NULLS FIRST)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS seed_events")
