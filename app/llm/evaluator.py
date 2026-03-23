"""LLM output quality evaluator.

Tracks confidence score distributions and classification consistency
per event_type over time, stored in PostgreSQL.

Why track this?
- Without evaluation, we can't tell if LLM quality is drifting
- confidence score alone is not meaningful if the model always says 0.65
- Consistency check: same event_type should map to a stable risk_signal
  (e.g., war_escalation should always be risk_off)
- Portfolio value: shows awareness of LLM observability, not just usage
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.store.db import get_db

logger = logging.getLogger("app.llm.evaluator")

# Expected risk_signal per event_type (ground truth from domain knowledge)
EXPECTED_RISK_SIGNAL: dict[str, str] = {
    "geopolitics_conflict": "risk_off",
    "war_escalation": "risk_off",
    "terror_attack": "risk_off",
    "monetary_tightening": "risk_off",
    "inflation_hot": "risk_off",
    "banking_stress": "risk_off",
    "trade_sanction": "risk_off",
    "recession_signal": "risk_off",
    "monetary_easing": "risk_on",
    "stimulus": "risk_on",
    "inflation_cooling": "risk_on",
    "earnings_positive": "risk_on",
    "ceasefire": "risk_on",
    "policy_stability": "neutral",
    "regulation_update": "neutral",
}


def ensure_eval_table() -> None:
    """Create llm_eval_log table if not exists."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
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
    conn.commit()
    conn.close()


def log_eval(
    raw_event_id: str,
    event_type: str,
    risk_signal: str,
    confidence: float,
    provider: str,
    model: str,
) -> None:
    """Record one LLM output evaluation entry."""
    expected = EXPECTED_RISK_SIGNAL.get(event_type)
    is_consistent = (expected is None) or (risk_signal == expected)

    if not is_consistent:
        logger.warning(
            "LLM inconsistency raw_event_id=%s event_type=%s got=%s expected=%s confidence=%.2f",
            raw_event_id, event_type, risk_signal, expected, confidence,
        )

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO llm_eval_log
            (raw_event_id, event_type, risk_signal, expected_risk_signal, confidence, is_consistent, provider, model)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (raw_event_id, event_type, risk_signal, expected, confidence, is_consistent, provider, model),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.error("eval log write failed: %s", exc)


def get_consistency_report() -> list[dict]:
    """Return consistency rate per event_type over the last 100 evals."""
    try:
        from psycopg.rows import dict_row
        conn = get_db()
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """
            SELECT
                event_type,
                COUNT(*) AS total,
                SUM(CASE WHEN is_consistent THEN 1 ELSE 0 END) AS consistent,
                ROUND(AVG(confidence)::numeric, 3) AS avg_confidence
            FROM llm_eval_log
            WHERE evaluated_at > NOW() - INTERVAL '7 days'
            GROUP BY event_type
            ORDER BY total DESC
            """
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "event_type": r["event_type"],
                "total": r["total"],
                "consistency_rate": round(r["consistent"] / r["total"], 3) if r["total"] else 0,
                "avg_confidence": float(r["avg_confidence"] or 0),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("consistency report failed: %s", exc)
        return []
