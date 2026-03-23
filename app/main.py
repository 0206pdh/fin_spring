from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.ingest.raw_store import fetch_raw_event, fetch_unprocessed_raw_events, save_raw_events
from app.ingest.apnews import fetch_article_details, fetch_raw_events, get_categories
from app.llm.normalize import normalize_event
from app.llm.insight import (
    build_analysis_reason,
    build_fx_reason,
    build_heatmap_reason,
    generate_analysis_ko,
    generate_fx_ko,
    generate_heatmap_ko,
    summarize_news_ko,
)
from app.rules.engine import score_event
from app.store.db import init_db
from app.store.event_store import (
    fetch_unscored_events,
    fetch_normalized_event,
    fetch_scored_event,
    graph_edges,
    list_timeline,
    reset_scored_data,
    save_normalized,
    save_scored,
    sector_heatmap,
)
from app.ws_manager import manager as ws_manager

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app.api")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup: init DB + scheduler. Shutdown: stop scheduler."""
    init_db()
    if settings.scheduler_enabled:
        from app.scheduler import start_scheduler
        start_scheduler(interval_minutes=settings.scheduler_interval_minutes)
        logger.info("Scheduler enabled interval=%dm", settings.scheduler_interval_minutes)
    logger.info("Server running at http://localhost:8000")
    yield
    if settings.scheduler_enabled:
        from app.scheduler import stop_scheduler
        stop_scheduler()


app = FastAPI(title="Event-FX-Sector Intelligence", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/ui"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/ui/index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "ws_connections": ws_manager.connection_count}


# ---------------------------------------------------------------------------
# WebSocket — real-time pipeline events
# ---------------------------------------------------------------------------

@app.websocket("/ws/pipeline")
async def pipeline_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint: clients receive scored event notifications in real-time.

    Message format:
        {"type": "event_scored", "data": {"raw_event_id": "...", "event_type": "...", ...}}
        {"type": "heatmap_updated", "data": {"Energy": 1.2, ...}}
        {"type": "ping", "data": {}}
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive: client may send "ping"
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text('{"type":"pong","data":{}}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Async pipeline enqueue (non-blocking)
# ---------------------------------------------------------------------------

@app.post("/pipeline/enqueue")
async def pipeline_enqueue(
    category: str | None = None,
    limit_per_category: int = 10,
) -> dict:
    """Enqueue a pipeline batch into ARQ worker queue (returns immediately).

    Phase 1 key endpoint: replaces blocking /pipeline/run.
    Load test shows P95 latency drops from ~45s → ~12ms after this change.
    See docs/load-tests/phase1-sync-vs-async.md
    """
    try:
        from app.config import settings as _s
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(_s.redis_url))
        job = await pool.enqueue_job("pipeline_batch_job", category, limit_per_category)
        await pool.aclose()
        return {"status": "enqueued", "job_id": job.job_id if job else None}
    except Exception as exc:
        logger.exception("Enqueue failed")
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {exc}")


@app.post("/events/enqueue_one")
async def enqueue_one(raw_event_id: str) -> dict:
    """Enqueue normalization for a single raw event (non-blocking)."""
    try:
        from app.config import settings as _s
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(_s.redis_url))
        job = await pool.enqueue_job("normalize_job", raw_event_id)
        await pool.aclose()
        return {"status": "enqueued", "job_id": job.job_id if job else None}
    except Exception as exc:
        logger.exception("Enqueue one failed")
        raise HTTPException(status_code=503, detail=f"Queue unavailable: {exc}")


@app.get("/categories")
def categories() -> list[dict[str, str]]:
    return get_categories()


@app.get("/news")
def news(category: str, limit: int = 10) -> list[dict[str, str]]:
    try:
        events = fetch_raw_events(category=category, limit_per_category=limit)
    except Exception as exc:
        logger.exception("News fetch failed")
        raise HTTPException(status_code=500, detail=str(exc))
    save_raw_events(events)
    response = []
    for event in events:
        summary = _news_summary(event.payload)
        response.append(
            {
                "id": event.id,
                "title": event.title,
                "url": event.url,
                "published_at": event.published_at.isoformat()
                if hasattr(event.published_at, "isoformat")
                else event.published_at,
                "sector": event.sector,
                "summary": summary,
            }
        )
    return response


@app.post("/ingest/run")
def ingest_run(category: str | None = None, limit_per_category: int = 10) -> dict[str, int]:
    try:
        events = fetch_raw_events(category=category, limit_per_category=limit_per_category)
    except Exception as exc:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc))
    inserted = save_raw_events(events)
    logger.info("Ingestion complete fetched=%s inserted=%s", len(events), inserted)
    return {"fetched": len(events), "inserted": inserted}


@app.post("/events/normalize")
def normalize_events(limit: int = 50) -> dict[str, int]:
    raw_events = fetch_unprocessed_raw_events(limit=limit)
    count = 0
    for raw in raw_events:
        normalized = normalize_event(raw)
        save_normalized(normalized)
        count += 1
    logger.info("Normalization complete normalized=%s", count)
    return {"normalized": count}


@app.post("/events/score")
def score_events(limit: int = 50) -> dict[str, int]:
    normalized_events = fetch_unscored_events(limit=limit)
    count = 0
    for normalized in normalized_events:
        scored = score_event(normalized)
        save_scored(scored)
        count += 1
    logger.info("Scoring complete scored=%s", count)
    return {"scored": count}


@app.post("/pipeline/run")
def pipeline_run(category: str | None = None, limit_per_category: int = 10, limit: int = 50) -> dict[str, int]:
    try:
        events = fetch_raw_events(category=category, limit_per_category=limit_per_category)
    except Exception as exc:
        logger.exception("Pipeline ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc))
    inserted = save_raw_events(events)

    raw_events = fetch_unprocessed_raw_events(limit=limit)
    normalized_count = 0
    for raw in raw_events:
        normalized = normalize_event(raw)
        save_normalized(normalized)
        normalized_count += 1

    normalized_events = fetch_unscored_events(limit=limit)
    scored_count = 0
    for normalized in normalized_events:
        scored = score_event(normalized)
        save_scored(scored)
        scored_count += 1

    logger.info(
        "Pipeline complete fetched=%s inserted=%s normalized=%s scored=%s",
        len(events),
        inserted,
        normalized_count,
        scored_count,
    )
    return {
        "fetched": len(events),
        "inserted": inserted,
        "normalized": normalized_count,
        "scored": scored_count,
    }


@app.post("/pipeline/run_one")
def pipeline_run_one(raw_event_id: str) -> dict[str, int]:
    raw_event = fetch_raw_event(raw_event_id)
    if not raw_event:
        raise HTTPException(status_code=404, detail="Raw event not found")
    reset_scored_data()
    try:
        details = fetch_article_details(raw_event.url)
    except Exception as exc:
        logger.warning("AP article details fetch failed: %s", exc)
        details = {}
    if details:
        raw_event.payload["details"] = {
            "title": details.get("title", ""),
            "summary": details.get("summary", ""),
            "text": details.get("text", ""),
        }
        if details.get("published_at"):
            raw_event.payload["item"]["published_at"] = details.get("published_at", "")
        if details.get("title"):
            raw_event.title = details.get("title", raw_event.title)
    normalized = normalize_event(raw_event)
    save_normalized(normalized)
    scored = score_event(normalized)
    save_scored(scored)
    logger.info("Pipeline single complete raw_event_id=%s", raw_event_id)
    return {"normalized": 1, "scored": 1}


@app.get("/timeline")
def timeline(limit: int = 50) -> list[dict[str, object]]:
    from app.store.cache import get_cached
    return get_cached(
        key=f"timeline:v1:{limit}",
        ttl=settings.cache_timeline_ttl,
        db_fn=lambda: list_timeline(limit=limit),
    )


@app.get("/heatmap")
def heatmap() -> dict[str, float]:
    from app.store.cache import get_cached
    return get_cached(
        key="heatmap:v1",
        ttl=settings.cache_heatmap_ttl,
        db_fn=sector_heatmap,
    )


@app.get("/graph")
def graph(limit: int = 100) -> list[dict[str, object]]:
    return graph_edges(limit=limit)


@app.get("/events/insight")
def event_insight(raw_event_id: str) -> dict[str, str]:
    import time

    start = time.perf_counter()
    logger.info("Insight request raw_event_id=%s", raw_event_id)
    raw_event = fetch_raw_event(raw_event_id)
    if not raw_event:
        logger.warning("Insight missing raw_event_id=%s", raw_event_id)
        raise HTTPException(status_code=404, detail="Raw event not found")

    normalized = fetch_normalized_event(raw_event_id)
    scored = fetch_scored_event(raw_event_id)
    logger.info(
        "Insight data raw_event_id=%s normalized=%s scored=%s",
        raw_event_id,
        bool(normalized),
        bool(scored),
    )

    summary_ko = summarize_news_ko(raw_event)
    if not summary_ko:
        summary_ko = _news_summary(raw_event.payload) or raw_event.title or "요약 정보가 없습니다."

    analysis_reason = generate_analysis_ko(normalized, scored)
    if not analysis_reason:
        analysis_reason = build_analysis_reason(normalized, scored)

    fx_reason = generate_fx_ko(normalized, scored)
    if not fx_reason:
        fx_reason = build_fx_reason(normalized, scored)

    heatmap_reason = generate_heatmap_ko(scored, normalized)
    if not heatmap_reason:
        heatmap_reason = build_heatmap_reason(scored, normalized)

    elapsed_sec = time.perf_counter() - start
    logger.info("Insight response raw_event_id=%s latency_s=%.2f", raw_event_id, elapsed_sec)

    return {
        "id": raw_event.id,
        "title": raw_event.title,
        "url": raw_event.url,
        "summary_ko": summary_ko,
        "analysis_reason": analysis_reason,
        "fx_reason": fx_reason,
        "heatmap_reason": heatmap_reason,
    }


@app.get("/events/eval/report")
def eval_report() -> list[dict]:
    """Return LLM consistency report per event_type (Phase 2).

    Shows: classification consistency rate + avg confidence per event_type.
    Low consistency rate flags event_types where LLM is unreliable.
    """
    from app.llm.evaluator import get_consistency_report
    return get_consistency_report()


def _news_summary(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    details = payload.get("details")
    item = payload.get("item")
    fields = ["summary", "description", "headline", "title", "body", "content", "text"]
    for source in (details, item):
        if isinstance(source, dict):
            for key in fields:
                value = source.get(key)
                if value:
                    return str(value)[:240]
    return ""
