"""ARQ async worker — non-blocking LLM pipeline processing.

Why ARQ over Celery?
- ARQ is asyncio-native: no threading overhead, no greenlets
- FastAPI uses asyncio → worker shares same concurrency model
- Celery requires separate broker config, serializer setup, result backend
- For a portfolio-scale service ARQ is the minimal viable async queue

Job flow:
  enqueue_normalize(raw_event_id)
    → normalize_job(ctx, raw_event_id)
      → score_job(ctx, raw_event_id)   (auto-enqueued after normalize)
        → broadcast "event_scored" via WebSocket manager

Seed replay:
  seed_replay_job (cron, every 8 minutes)
    → picks one seed event with replayed_count < 3
    → re-runs it through normalize → score
    → increments replayed_count
    → ensures the live demo always has recent scored data
"""
from __future__ import annotations

import logging

from arq import ArqRedis
from arq.cron import cron

from app.ingest.raw_store import fetch_raw_event
from app.llm.normalize import normalize_event
from app.rules.engine import score_event
from app.store.event_store import save_normalized, save_scored, fetch_unscored_events

logger = logging.getLogger("app.worker")


# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

async def normalize_job(ctx: dict, raw_event_id: str) -> str:
    """Normalize a single raw event via LLM (runs in worker process)."""
    logger.info("normalize_job start raw_event_id=%s", raw_event_id)
    raw = fetch_raw_event(raw_event_id)
    if raw is None:
        logger.warning("normalize_job raw event not found raw_event_id=%s", raw_event_id)
        return "not_found"
    normalized = normalize_event(raw)
    save_normalized(normalized)
    # auto-enqueue scoring
    redis: ArqRedis = ctx["redis"]
    await redis.enqueue_job("score_job", raw_event_id)
    logger.info("normalize_job done, score_job enqueued raw_event_id=%s", raw_event_id)
    return "normalized"


async def score_job(ctx: dict, raw_event_id: str) -> str:
    """Score a normalized event via rule engine and broadcast result."""
    logger.info("score_job start raw_event_id=%s", raw_event_id)
    unscored = fetch_unscored_events(limit=1)
    # filter to the specific event we want
    target = next((e for e in unscored if e.raw_event_id == raw_event_id), None)
    if target is None:
        logger.warning("score_job normalized event not found raw_event_id=%s", raw_event_id)
        return "not_found"
    scored = score_event(target)
    save_scored(scored)
    # broadcast to WebSocket clients
    try:
        from app.ws_manager import manager
        await manager.broadcast(
            "event_scored",
            {
                "raw_event_id": scored.raw_event_id,
                "event_type": scored.event_type,
                "risk_signal": scored.risk_signal,
                "fx_state": scored.fx_state,
                "total_score": scored.total_score,
            },
        )
    except Exception as exc:
        logger.warning("WS broadcast failed: %s", exc)
    # Invalidate heatmap + timeline caches so next read reflects new event
    try:
        from app.store.cache import invalidate_pipeline_caches
        invalidate_pipeline_caches()
    except Exception as exc:
        logger.debug("Cache invalidation skipped: %s", exc)

    logger.info("score_job done raw_event_id=%s total_score=%.2f", raw_event_id, scored.total_score)
    return "scored"


async def pipeline_batch_job(ctx: dict, category: str | None = None, limit: int = 10) -> dict:
    """Full pipeline batch: ingest → normalize → score (called by scheduler)."""
    from app.ingest.bbc import fetch_raw_events
    from app.ingest.raw_store import save_raw_events

    logger.info("pipeline_batch_job start category=%s limit=%d", category, limit)
    try:
        events = fetch_raw_events(category=category, limit_per_category=limit)
    except Exception as exc:
        logger.error("pipeline_batch_job ingest failed: %s", exc)
        return {"error": str(exc)}

    inserted = save_raw_events(events)
    redis: ArqRedis = ctx["redis"]
    enqueued = 0
    for event in events:
        await redis.enqueue_job("normalize_job", event.id)
        enqueued += 1

    logger.info(
        "pipeline_batch_job done fetched=%d inserted=%d enqueued=%d",
        len(events), inserted, enqueued,
    )
    return {"fetched": len(events), "inserted": inserted, "enqueued": enqueued}


async def seed_replay_job(ctx: dict) -> dict:
    """Replay one seed event through the pipeline every 8 minutes.

    Picks the seed event with the lowest replayed_count (up to cap=3) and
    re-runs it through normalize → score → WS broadcast. This keeps the live
    demo populated even when no fresh AP News articles are available.

    replayed_count cap = 3: prevents infinite churn while ensuring every seed
    event gets at least 3 passes (different LLM runs → slightly different
    rationales, which demonstrates the system is live).
    """
    logger.info("seed_replay_job start")
    try:
        from app.store.db import get_db
        from psycopg.rows import dict_row

        with get_db() as conn:
            cur = conn.cursor(row_factory=dict_row)
            cur.execute(
                """
                SELECT id FROM seed_events
                WHERE replayed_count < 3
                ORDER BY replayed_count ASC, last_replayed_at ASC NULLS FIRST
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            row = cur.fetchone()
            if not row:
                logger.info("seed_replay_job no eligible seed events (all at cap)")
                return {"status": "no_eligible_seeds"}

            seed_id = row["id"]
            cur.execute(
                """
                UPDATE seed_events
                SET replayed_count = replayed_count + 1,
                    last_replayed_at = NOW()
                WHERE id = %s
                """,
                (seed_id,),
            )
            conn.commit()

        # Fetch the seed event as a raw_event and run through pipeline
        raw = fetch_raw_event(seed_id)
        if raw is None:
            logger.warning("seed_replay_job seed not in raw_events id=%s", seed_id)
            return {"status": "not_found", "id": seed_id}

        normalized = normalize_event(raw)
        save_normalized(normalized)
        scored = score_event(normalized)
        save_scored(scored)

        # Broadcast update
        try:
            from app.ws_manager import manager
            await manager.broadcast(
                "event_scored",
                {
                    "raw_event_id": scored.raw_event_id,
                    "event_type": scored.event_type,
                    "risk_signal": scored.risk_signal,
                    "fx_state": scored.fx_state,
                    "total_score": scored.total_score,
                },
            )
        except Exception as exc:
            logger.warning("seed_replay WS broadcast failed: %s", exc)

        try:
            from app.store.cache import invalidate_pipeline_caches
            invalidate_pipeline_caches()
        except Exception as exc:
            logger.debug("seed_replay cache invalidation skipped: %s", exc)

        logger.info("seed_replay_job done id=%s total_score=%.2f", seed_id, scored.total_score)
        return {"status": "replayed", "id": seed_id, "total_score": scored.total_score}

    except Exception as exc:
        logger.error("seed_replay_job failed: %s", exc)
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# ARQ WorkerSettings
# ---------------------------------------------------------------------------

class WorkerSettings:
    """ARQ worker configuration.

    Run with: arq app.worker.WorkerSettings
    """
    functions = [normalize_job, score_job, pipeline_batch_job, seed_replay_job]
    cron_jobs = [
        cron(seed_replay_job, minute={0, 8, 16, 24, 32, 40, 48, 56}),
    ]
    redis_settings = None  # set at runtime from app.config

    @classmethod
    def build(cls) -> type:
        from app.config import settings
        from arq.connections import RedisSettings

        cls.redis_settings = RedisSettings.from_dsn(settings.redis_url)
        return cls
