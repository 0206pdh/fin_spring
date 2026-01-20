from __future__ import annotations

from datetime import datetime

from app.models import NormalizedEvent, ScoredEvent
from app.rules.weights import (
    FX_TRANSMISSION_CHANNELS,
    apply_risk_sector_rules,
    combine_baseline_delta,
    compute_fx_delta,
    compute_sector_delta_from_fx,
)


def score_event(event: NormalizedEvent) -> ScoredEvent:
    channels = _normalize_channels(event)
    confidence = _normalize_confidence(event.confidence)
    regime = _normalize_regime(event.regime)
    baseline = event.baseline or {}

    fx_delta = compute_fx_delta(channels, confidence)
    fx_state = _format_fx_state(fx_delta)
    sector_delta = compute_sector_delta_from_fx(fx_delta)
    sector_delta = apply_risk_sector_rules(sector_delta, channels, confidence)
    sector_delta = _apply_event_impacts(sector_delta, event.sector_impacts, confidence)
    sector_scores = combine_baseline_delta(baseline, sector_delta, regime)
    total_score = sum(sector_scores.values())

    return ScoredEvent(
        raw_event_id=event.raw_event_id,
        event_type=event.event_type,
        policy_domain=event.policy_domain,
        risk_signal=event.risk_signal,
        rate_signal=event.rate_signal,
        geo_signal=event.geo_signal,
        sector_impacts=event.sector_impacts,
        sentiment=event.sentiment,
        rationale=event.rationale,
        fx_state=fx_state,
        sector_scores=sector_scores,
        total_score=total_score,
        created_at=datetime.utcnow(),
    )


def _normalize_channels(event: NormalizedEvent) -> list[str]:
    channels = [ch for ch in (event.channels or []) if ch in FX_TRANSMISSION_CHANNELS]
    channels = list(dict.fromkeys(channels))
    for ch in _signal_channels(event):
        if ch in FX_TRANSMISSION_CHANNELS and ch not in channels:
            channels.append(ch)
    return channels


def _signal_channels(event: NormalizedEvent) -> list[str]:
    channels: list[str] = []
    if event.risk_signal:
        channels.append(event.risk_signal.lower())
    if event.rate_signal == "tightening":
        channels.append("rate_tightening")
    if event.rate_signal == "easing":
        channels.append("rate_easing")
    if event.geo_signal == "escalation":
        channels.append("geo_escalation")
    if event.geo_signal == "deescalation":
        channels.append("geo_deescalation")
    return channels


def _normalize_confidence(value: float | int | None) -> float:
    if value is None:
        return 0.6
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(1.0, confidence))


def _normalize_regime(value: dict[str, str] | None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"risk_sentiment": "neutral", "volatility": "elevated", "liquidity": "neutral"}
    return {
        "risk_sentiment": value.get("risk_sentiment", "neutral"),
        "volatility": value.get("volatility", "elevated"),
        "liquidity": value.get("liquidity", "neutral"),
    }


def _apply_event_impacts(
    sector_delta: dict[str, float],
    impacts: dict[str, int],
    confidence: float,
) -> dict[str, float]:
    for sector, score in impacts.items():
        try:
            delta = float(score) * confidence
        except (TypeError, ValueError):
            continue
        sector_delta[sector] = sector_delta.get(sector, 0.0) + delta
    return sector_delta


def _format_fx_state(bias: dict[str, float]) -> str:
    return " ".join(
        [
            f"USD:{bias.get('USD', 0.0):+0.2f}",
            f"JPY:{bias.get('JPY', 0.0):+0.2f}",
            f"EUR:{bias.get('EUR', 0.0):+0.2f}",
            f"EM:{bias.get('EM', 0.0):+0.2f}",
        ]
    )
