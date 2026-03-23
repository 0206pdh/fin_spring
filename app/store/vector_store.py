"""pgvector-based semantic duplicate detection.

Why pgvector over string hashing?
- Same news event often appears under different headlines across categories
  e.g. "Fed raises rates 25bp" vs "Federal Reserve hikes benchmark rate"
  String hash: different. Cosine similarity on embeddings: ~0.95
- pgvector runs inside existing PostgreSQL instance → no extra service
- Once embeddings exist, enables future RAG (retrieve similar past events)

Usage:
    is_dup, similar_id = check_duplicate(title, embedding)
    if not is_dup:
        save_embedding(raw_event_id, title, embedding)

Embedding strategy:
- title + first 200 chars of details → embed with OpenAI text-embedding-3-small
- 1536-dimension vector, cosine similarity threshold: 0.92
"""
from __future__ import annotations

import logging

logger = logging.getLogger("app.store.vector_store")

SIMILARITY_THRESHOLD = 0.92
EMBEDDING_DIM = 1536  # text-embedding-3-small


def ensure_vector_extension() -> None:
    """Enable pgvector extension and create embeddings table."""
    from app.store.db import get_db
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS event_embeddings (
                raw_event_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS event_embeddings_hnsw ON event_embeddings "
            "USING hnsw (embedding vector_cosine_ops)"
        )
        conn.commit()
        logger.info("pgvector extension and embeddings table ready")
    except Exception as exc:
        conn.rollback()
        logger.warning("pgvector setup failed (extension may not be installed): %s", exc)
    finally:
        conn.close()


def get_embedding(text: str, openai_client: object) -> list[float]:
    """Get text embedding via OpenAI text-embedding-3-small."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:2000],
    )
    return response.data[0].embedding


def save_embedding(raw_event_id: str, title: str, embedding: list[float]) -> None:
    """Store embedding for a raw event."""
    from app.store.db import get_db
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO event_embeddings (raw_event_id, title, embedding)
            VALUES (%s, %s, %s::vector)
            ON CONFLICT (raw_event_id) DO NOTHING
            """,
            (raw_event_id, title, str(embedding)),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("save_embedding failed raw_event_id=%s: %s", raw_event_id, exc)
    finally:
        conn.close()


def check_duplicate(
    embedding: list[float],
    threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[bool, str | None]:
    """Check if a similar event already exists.

    Returns:
        (is_duplicate, existing_raw_event_id)
    """
    from app.store.db import get_db
    from psycopg.rows import dict_row

    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    try:
        cur.execute(
            """
            SELECT raw_event_id,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM event_embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT 1
            """,
            (str(embedding), str(embedding)),
        )
        row = cur.fetchone()
        if row and row["similarity"] >= threshold:
            logger.info(
                "Duplicate detected similarity=%.3f existing=%s",
                row["similarity"],
                row["raw_event_id"],
            )
            return True, row["raw_event_id"]
        return False, None
    except Exception as exc:
        logger.warning("check_duplicate failed: %s", exc)
        return False, None
    finally:
        conn.close()
