"""APScheduler — automatic pipeline scheduling.

Why APScheduler over Celery Beat?
- In-process scheduler: no additional service to run
- asyncio-native BackgroundScheduler integrates with FastAPI lifespan
- For portfolio scale (1 schedule job) Celery Beat is overkill

Schedule:
  - Every 15 minutes: enqueue pipeline_batch_job → ARQ worker
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("app.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _enqueue_pipeline() -> None:
    """Enqueue a full pipeline batch job into the ARQ queue."""
    try:
        from app.config import settings
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job("pipeline_batch_job", None, 10)
        await pool.aclose()
        logger.info("Scheduled pipeline_batch_job enqueued")
    except Exception as exc:
        logger.error("Scheduler enqueue failed: %s", exc)


def start_scheduler(interval_minutes: int = 15) -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _enqueue_pipeline,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="pipeline_batch",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started interval=%dm", interval_minutes)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
