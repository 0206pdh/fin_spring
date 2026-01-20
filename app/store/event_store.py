from __future__ import annotations

import json
from datetime import datetime

from psycopg.rows import dict_row

from app.models import NormalizedEvent, ScoredEvent
from app.rules.weights import ALL_SECTORS
from app.store.db import get_db


def reset_scored_data() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("TRUNCATE scored_events")
    cur.execute("TRUNCATE normalized_events")
    conn.commit()
    conn.close()


def save_normalized(event: NormalizedEvent) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO normalized_events
        (raw_event_id, event_type, policy_domain, risk_signal, rate_signal, geo_signal, sector_impacts, sentiment, rationale, channels, confidence, regime, baseline)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raw_event_id) DO UPDATE SET
            event_type = EXCLUDED.event_type,
            policy_domain = EXCLUDED.policy_domain,
            risk_signal = EXCLUDED.risk_signal,
            rate_signal = EXCLUDED.rate_signal,
            geo_signal = EXCLUDED.geo_signal,
            sector_impacts = EXCLUDED.sector_impacts,
            sentiment = EXCLUDED.sentiment,
            rationale = EXCLUDED.rationale,
            channels = EXCLUDED.channels,
            confidence = EXCLUDED.confidence,
            regime = EXCLUDED.regime,
            baseline = EXCLUDED.baseline
        """,
        (
            event.raw_event_id,
            event.event_type,
            event.policy_domain,
            event.risk_signal,
            event.rate_signal,
            event.geo_signal,
            json.dumps(event.sector_impacts, ensure_ascii=True),
            event.sentiment,
            event.rationale,
            json.dumps(event.channels, ensure_ascii=True),
            event.confidence,
            json.dumps(event.regime, ensure_ascii=True),
            json.dumps(event.baseline, ensure_ascii=True),
        ),
    )
    conn.commit()
    conn.close()


def fetch_unscored_events(limit: int = 200) -> list[NormalizedEvent]:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute(
        """
        SELECT n.* FROM normalized_events n
        LEFT JOIN scored_events s ON s.raw_event_id::text = n.raw_event_id::text
        WHERE s.raw_event_id IS NULL
        ORDER BY n.raw_event_id DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    events: list[NormalizedEvent] = []
    for row in rows:
        events.append(
            NormalizedEvent(
                raw_event_id=row["raw_event_id"],
                event_type=row["event_type"],
                policy_domain=row["policy_domain"],
                risk_signal=row["risk_signal"],
                rate_signal=row["rate_signal"],
                geo_signal=row["geo_signal"],
                sector_impacts=row["sector_impacts"],
                sentiment=row["sentiment"],
                rationale=row["rationale"],
                channels=row.get("channels") or [],
                confidence=row.get("confidence", 0.6),
                regime=row.get("regime") or {},
                baseline=row.get("baseline") or {},
            )
        )
    return events


def fetch_normalized_event(raw_event_id: str) -> NormalizedEvent | None:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM normalized_events WHERE raw_event_id = %s", (raw_event_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return NormalizedEvent(
        raw_event_id=row["raw_event_id"],
        event_type=row["event_type"],
        policy_domain=row["policy_domain"],
        risk_signal=row["risk_signal"],
        rate_signal=row["rate_signal"],
        geo_signal=row["geo_signal"],
        sector_impacts=row["sector_impacts"],
        sentiment=row["sentiment"],
        rationale=row["rationale"],
        channels=row.get("channels") or [],
        confidence=row.get("confidence", 0.6),
        regime=row.get("regime") or {},
        baseline=row.get("baseline") or {},
    )


def save_scored(event: ScoredEvent) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO scored_events
        (raw_event_id, event_type, policy_domain, risk_signal, rate_signal, geo_signal, sector_impacts, sentiment, rationale,
         fx_state, sector_scores, total_score, created_at, channels, confidence, regime, baseline)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raw_event_id) DO UPDATE SET
            event_type = EXCLUDED.event_type,
            policy_domain = EXCLUDED.policy_domain,
            risk_signal = EXCLUDED.risk_signal,
            rate_signal = EXCLUDED.rate_signal,
            geo_signal = EXCLUDED.geo_signal,
            sector_impacts = EXCLUDED.sector_impacts,
            sentiment = EXCLUDED.sentiment,
            rationale = EXCLUDED.rationale,
            fx_state = EXCLUDED.fx_state,
            sector_scores = EXCLUDED.sector_scores,
            total_score = EXCLUDED.total_score,
            created_at = EXCLUDED.created_at,
            channels = EXCLUDED.channels,
            confidence = EXCLUDED.confidence,
            regime = EXCLUDED.regime,
            baseline = EXCLUDED.baseline
        """,
        (
            event.raw_event_id,
            event.event_type,
            event.policy_domain,
            event.risk_signal,
            event.rate_signal,
            event.geo_signal,
            json.dumps(event.sector_impacts, ensure_ascii=True),
            event.sentiment,
            event.rationale,
            event.fx_state,
            json.dumps(event.sector_scores, ensure_ascii=True),
            event.total_score,
            event.created_at,
            json.dumps(event.channels, ensure_ascii=True),
            event.confidence,
            json.dumps(event.regime, ensure_ascii=True),
            json.dumps(event.baseline, ensure_ascii=True),
        ),
    )
    conn.commit()
    conn.close()


def fetch_scored_event(raw_event_id: str) -> ScoredEvent | None:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM scored_events WHERE raw_event_id = %s", (raw_event_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return ScoredEvent(
        raw_event_id=row["raw_event_id"],
        event_type=row["event_type"],
        policy_domain=row["policy_domain"],
        risk_signal=row["risk_signal"],
        rate_signal=row["rate_signal"],
        geo_signal=row["geo_signal"],
        sector_impacts=row["sector_impacts"],
        sentiment=row["sentiment"],
        rationale=row["rationale"],
        fx_state=row["fx_state"],
        sector_scores=row["sector_scores"],
        total_score=row["total_score"],
        created_at=row["created_at"],
        channels=row.get("channels") or [],
        confidence=row.get("confidence", 0.6),
        regime=row.get("regime") or {},
        baseline=row.get("baseline") or {},
    )


def list_timeline(limit: int = 50) -> list[dict[str, object]]:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute(
        """
        SELECT r.title, r.url, r.published_at, r.sector, s.risk_signal, s.rate_signal, s.geo_signal, s.fx_state, s.sentiment, s.total_score
        FROM raw_events r
        JOIN scored_events s ON s.raw_event_id::text = r.id
        ORDER BY r.published_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "title": row["title"],
            "url": row["url"],
            "published_at": row["published_at"].isoformat()
            if hasattr(row["published_at"], "isoformat")
            else row["published_at"],
            "sector": row["sector"],
            "risk_signal": row["risk_signal"],
            "rate_signal": row["rate_signal"],
            "geo_signal": row["geo_signal"],
            "fx_state": row["fx_state"],
            "sentiment": row["sentiment"],
            "total_score": row["total_score"],
        }
        for row in rows
    ]


def sector_heatmap() -> dict[str, float]:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT sector_scores FROM scored_events")
    rows = cur.fetchall()
    conn.close()

    totals: dict[str, float] = {}
    for row in rows:
        scores = row["sector_scores"]
        for sector, score in scores.items():
            totals[sector] = totals.get(sector, 0.0) + float(score)
    for sector in ALL_SECTORS:
        totals.setdefault(sector, 0.0)
    return {sector: round(value, 3) for sector, value in totals.items()}


def graph_edges(limit: int = 100) -> list[dict[str, object]]:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute(
        """
        SELECT r.title, s.fx_state, s.risk_signal, s.rate_signal, s.geo_signal, s.sector_scores
        FROM raw_events r
        JOIN scored_events s ON s.raw_event_id::text = r.id
        ORDER BY r.published_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    edges = []
    for row in rows:
        scores = row["sector_scores"]
        for sector, score in scores.items():
            edges.append(
                {
                    "event": row["title"],
                    "fx": row["fx_state"],
                    "risk_signal": row["risk_signal"],
                    "rate_signal": row["rate_signal"],
                    "geo_signal": row["geo_signal"],
                    "sector": sector,
                    "weight": float(score),
                    "fx_theme": row["fx_state"],
                }
            )
    if not edges:
        return [
            {
                "event": "Sample event (default)",
                "fx": "USD:+0 JPY:+0 EUR:+0 EM:+0",
                "risk_signal": "neutral",
                "rate_signal": "none",
                "geo_signal": "none",
                "sector": "Energy",
                "weight": 1,
                "fx_theme": "neutral",
            }
        ]
    return edges


def latest_created_at() -> datetime | None:
    conn = get_db()
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT created_at FROM scored_events ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    created_at = row["created_at"]
    return created_at if isinstance(created_at, datetime) else datetime.fromisoformat(created_at)
