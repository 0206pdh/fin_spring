"""003 — pgvector extension + event_embeddings table.

Why pgvector?
- Duplicate event detection: same news under different headlines
  is caught by cosine similarity on title embeddings (threshold 0.92)
- Future RAG: retrieve N most similar past events to provide context to LLM
  ("In the last 30 days, similar events caused risk_off with avg confidence 0.81")
- Runs inside existing PostgreSQL — no separate vector DB service needed

HNSW index choice over IVFFlat:
- HNSW: O(log n) query time, no training phase, better recall at high throughput
- IVFFlat: requires pre-training (needs data), better for static large datasets
- At portfolio scale (<100k events) HNSW is the correct choice

Revision: 003
"""
from __future__ import annotations

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS event_embeddings (
            raw_event_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # HNSW index for approximate nearest neighbor search
    # m=16: connections per node (higher = better recall, more memory)
    # ef_construction=64: search depth during build (quality vs build time)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS event_embeddings_hnsw
        ON event_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # LLM evaluation log (from Phase 2 evaluator.py)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_eval_log (
            id SERIAL PRIMARY KEY,
            raw_event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            risk_signal TEXT NOT NULL,
            expected_risk_signal TEXT,
            confidence FLOAT NOT NULL,
            is_consistent BOOLEAN NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_eval_log_event_type ON llm_eval_log (event_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_eval_log_evaluated_at ON llm_eval_log (evaluated_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_eval_log")
    op.execute("DROP TABLE IF EXISTS event_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
