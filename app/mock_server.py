"""Standalone mock server — no PostgreSQL, no Redis, no Docker needed.

Serves realistic fake data so the frontend can be tested locally.

Usage:
    uvicorn app.mock_server:app --port 8000 --reload

Endpoints:
    GET  /heatmap          → sector pressure scores
    GET  /timeline         → recent scored events
    POST /pipeline/run     → pretend to run pipeline
    WS   /ws/pipeline      → push heatmap_updated every 10s
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FinTech Mock Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SECTORS = [
    "Technology", "Financials", "Energy", "Defense",
    "Consumer Discretionary", "Industrials", "Materials",
    "Utilities", "Autos", "Growth",
]

MOCK_EVENTS = [
    {
        "title": "Fed hikes rates 75bp in largest move since 1994",
        "url": "https://www.bbc.com/news/business/fed-hike-2022",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "sector": "macro",
        "risk_signal": "risk_off",
        "rate_signal": "tightening",
        "geo_signal": "none",
        "fx_state": "USD:+1.24 JPY:-0.38 EUR:-0.26 EM:-0.97",
        "sentiment": "bearish",
        "total_score": -3.21,
    },
    {
        "title": "SVB collapses in largest US bank failure since 2008",
        "url": "https://www.bbc.com/news/business/svb-2023",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        "sector": "corporate",
        "risk_signal": "risk_off",
        "rate_signal": "none",
        "geo_signal": "none",
        "fx_state": "USD:+1.12 JPY:+0.73 EUR:-0.82 EM:-1.64",
        "sentiment": "bearish",
        "total_score": -4.87,
    },
    {
        "title": "China ends zero-COVID, reopens borders after 3 years",
        "url": "https://www.bbc.com/news/world/china-reopens-2023",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "sector": "geopolitics",
        "risk_signal": "risk_on",
        "rate_signal": "none",
        "geo_signal": "none",
        "fx_state": "USD:-0.87 JPY:-0.61 EUR:+0.54 EM:+1.38",
        "sentiment": "bullish",
        "total_score": 3.44,
    },
    {
        "title": "Nvidia posts record revenue on AI chip demand",
        "url": "https://www.bbc.com/news/technology/nvidia-2023",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(),
        "sector": "technology",
        "risk_signal": "risk_on",
        "rate_signal": "none",
        "geo_signal": "none",
        "fx_state": "USD:-0.71 JPY:-0.52 EUR:+0.41 EM:+1.18",
        "sentiment": "bullish",
        "total_score": 4.12,
    },
    {
        "title": "Hamas attacks Israel — Middle East conflict escalates",
        "url": "https://www.bbc.com/news/world/hamas-2023",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),
        "sector": "geopolitics",
        "risk_signal": "risk_off",
        "rate_signal": "none",
        "geo_signal": "escalation",
        "fx_state": "USD:+0.68 JPY:+0.45 EUR:-0.91 EM:-1.21",
        "sentiment": "bearish",
        "total_score": -2.93,
    },
    {
        "title": "Fed cuts rates 50bp — signals easing cycle has begun",
        "url": "https://www.bbc.com/news/business/fed-cut-2024",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        "sector": "macro",
        "risk_signal": "risk_on",
        "rate_signal": "easing",
        "geo_signal": "none",
        "fx_state": "USD:-1.08 JPY:+0.22 EUR:+0.19 EM:+0.84",
        "sentiment": "bullish",
        "total_score": 2.67,
    },
    {
        "title": "US tariffs on China raised to 145% sparking trade war fears",
        "url": "https://www.bbc.com/news/business/tariffs-2025",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
        "sector": "geopolitics",
        "risk_signal": "risk_off",
        "rate_signal": "none",
        "geo_signal": "escalation",
        "fx_state": "USD:+0.68 JPY:+0.45 EUR:-0.91 EM:-1.21",
        "sentiment": "bearish",
        "total_score": -3.58,
    },
    {
        "title": "DeepSeek R1 released — AI cost shock hits tech stocks",
        "url": "https://www.bbc.com/news/technology/deepseek-2025",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=36)).isoformat(),
        "sector": "technology",
        "risk_signal": "risk_off",
        "rate_signal": "none",
        "geo_signal": "none",
        "fx_state": "USD:+1.12 JPY:+0.73 EUR:-0.82 EM:-1.64",
        "sentiment": "bearish",
        "total_score": -2.14,
    },
    {
        "title": "Bank of Japan abandons yield curve control policy",
        "url": "https://www.bbc.com/news/business/boj-2024",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        "sector": "macro",
        "risk_signal": "risk_off",
        "rate_signal": "tightening",
        "geo_signal": "none",
        "fx_state": "USD:+1.24 JPY:-0.38 EUR:-0.26 EM:-0.97",
        "sentiment": "neutral",
        "total_score": -1.42,
    },
    {
        "title": "OPEC+ cuts oil output by 1 million barrels per day",
        "url": "https://www.bbc.com/news/business/opec-2023",
        "published_at": (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat(),
        "sector": "macro",
        "risk_signal": "risk_off",
        "rate_signal": "none",
        "geo_signal": "none",
        "fx_state": "USD:+1.12 JPY:+0.73 EUR:-0.82 EM:-1.64",
        "sentiment": "bearish",
        "total_score": -1.88,
    },
]

def _mock_heatmap() -> dict[str, float]:
    """Deterministic sector scores derived from mock events."""
    base = {
        "Technology":             2.31,
        "Financials":            -1.84,
        "Energy":                 1.12,
        "Defense":               -2.43,
        "Consumer Discretionary": 1.67,
        "Industrials":            0.45,
        "Materials":              0.83,
        "Utilities":             -0.62,
        "Autos":                  1.24,
        "Growth":                 2.05,
    }
    # Add tiny jitter so the treemap feels "live" on each refresh
    return {k: round(v + random.uniform(-0.05, 0.05), 2) for k, v in base.items()}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/heatmap")
def heatmap():
    return _mock_heatmap()


@app.get("/timeline")
def timeline(limit: int = 20):
    return MOCK_EVENTS[:limit]


@app.post("/pipeline/run")
def pipeline_run():
    return {"status": "ok", "message": "mock pipeline — no-op", "events_processed": len(MOCK_EVENTS)}


@app.get("/healthz")
def health():
    return {"status": "ok", "mode": "mock"}


# ---------------------------------------------------------------------------
# WebSocket — push heatmap_updated every 10s so the UI shows LIVE
# ---------------------------------------------------------------------------

@app.websocket("/ws/pipeline")
async def ws_pipeline(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(10)
            await websocket.send_json({"type": "heatmap_updated"})
    except WebSocketDisconnect:
        pass
