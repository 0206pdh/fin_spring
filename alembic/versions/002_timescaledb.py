"""002 — TimescaleDB hypertable for scored_events.

Why TimescaleDB?
Benchmark (internal, see docs/load-tests/phase3-cache-timescale.md):

    Query: SELECT * FROM scored_events WHERE created_at > NOW() - INTERVAL '24h'
    Plain PostgreSQL, 10k rows:   ~180ms (sequential scan)
    TimescaleDB hypertable:        ~12ms  (chunk pruning, 93% faster)

TimescaleDB works by automatically partitioning time-series data into "chunks"
by time range. Queries with WHERE created_at > ... only scan relevant chunks
instead of the full table — this is "chunk exclusion" (automatic partition pruning).

We keep PostgreSQL as the base engine — TimescaleDB is an extension, not a
separate database, so existing psycopg3 code works unchanged.

Revision: 002
"""
from __future__ import annotations

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Convert scored_events to a hypertable partitioned by created_at
    # chunk_time_interval = 1 day (appropriate for financial news: ~100-500 events/day)
    op.execute(
        """
        SELECT create_hypertable(
            'scored_events',
            'created_at',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE,
            migrate_data => TRUE
        )
        """
    )

    # TimescaleDB continuous aggregate for hourly heatmap (Phase 3 cache optimization)
    # This pre-computes sector_scores aggregation per hour, replacing the full-scan
    # in sector_heatmap() with a materialized view query.
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_sector_scores
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', created_at) AS bucket,
            risk_signal,
            COUNT(*) AS event_count
        FROM scored_events
        GROUP BY bucket, risk_signal
        WITH NO DATA
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS hourly_sector_scores")
    # Note: dropping a hypertable reverts it to a regular table
    # TimescaleDB does not support direct hypertable → regular table conversion
    # Best practice: restore from backup when rolling back this migration
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
