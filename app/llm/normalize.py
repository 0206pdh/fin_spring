from __future__ import annotations

import logging
import re

from app.llm.chain import run_norm_chain
from app.llm.client import LLMClient
from app.models import NormalizedEvent, RawEvent

EVENT_TYPE_RISK_SIGNAL = {
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

ALLOWED_EVENT_TYPES = set(EVENT_TYPE_RISK_SIGNAL.keys())
ALLOWED_POLICY_DOMAINS = {"monetary", "fiscal", "geopolitics", "industry"}
ALLOWED_RISK_SIGNALS = {"risk_on", "risk_off", "neutral"}
ALLOWED_RATE_SIGNALS = {"tightening", "easing", "none"}
ALLOWED_GEO_SIGNALS = {"escalation", "deescalation", "none"}
ALLOWED_SENTIMENTS = {"positive", "negative", "neutral"}

_FALLBACK_NUMERIC_PHRASE = " (quantitative data unavailable for this event)"
_NUMBER_PATTERN = re.compile(r"\d+")

logger = logging.getLogger("app.llm")


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _validate_rationale(rationale: str) -> str:
    if not rationale:
        return rationale
    if not _NUMBER_PATTERN.search(rationale):
        logger.warning("rationale missing numeric token; appending fallback phrase")
        return rationale + _FALLBACK_NUMERIC_PHRASE
    return rationale


def normalize_event(raw_event: RawEvent, client: LLMClient | None = None) -> NormalizedEvent:
    client = client or LLMClient()
    duplicate = _reuse_duplicate_normalization(raw_event, client)
    if duplicate is not None:
        _log_eval(client, duplicate)
        return duplicate

    details_text, category_url = _details_summary(raw_event.payload)
    graph_result = run_norm_chain(
        title=raw_event.title,
        sector=raw_event.sector,
        published_at=str(raw_event.published_at),
        details_text=details_text or raw_event.title,
        client=client,
    )

    event_type = _normalize_token(graph_result.event_type or "policy_stability")
    policy_domain = _normalize_token(graph_result.policy_domain or "industry")
    risk_signal = _normalize_token(graph_result.risk_signal or "neutral")
    rate_signal = _normalize_token(graph_result.rate_signal or "none")
    geo_signal = _normalize_token(graph_result.geo_signal or "none")
    sentiment = _normalize_token(graph_result.sentiment or "neutral")

    if event_type not in ALLOWED_EVENT_TYPES:
        event_type = "policy_stability"
    if policy_domain not in ALLOWED_POLICY_DOMAINS:
        policy_domain = "industry"
    if risk_signal not in ALLOWED_RISK_SIGNALS:
        risk_signal = "neutral"
    if rate_signal not in ALLOWED_RATE_SIGNALS:
        rate_signal = "none"
    if geo_signal not in ALLOWED_GEO_SIGNALS:
        geo_signal = "none"
    if sentiment not in ALLOWED_SENTIMENTS:
        sentiment = "neutral"

    mapped_risk = EVENT_TYPE_RISK_SIGNAL.get(event_type)
    if mapped_risk:
        risk_signal = mapped_risk

    normalized = NormalizedEvent(
        raw_event_id=raw_event.id,
        event_type=event_type,
        policy_domain=policy_domain,
        risk_signal=risk_signal,
        rate_signal=rate_signal,
        geo_signal=geo_signal,
        sector_impacts=_normalize_sector_impacts(graph_result.sector_impacts),
        sentiment=sentiment,
        rationale=_validate_rationale(graph_result.rationale.strip()),
        channels=_normalize_channels(graph_result.channels, risk_signal, rate_signal, geo_signal),
        confidence=_normalize_confidence(graph_result.confidence),
        regime=_normalize_regime(graph_result.regime.model_dump()),
    )

    _persist_embedding(raw_event, details_text, client)
    _log_eval(client, normalized)
    logger.info(
        "normalized raw_event_id=%s event_type=%s channels=%s confidence=%.2f category_url=%s",
        raw_event.id,
        normalized.event_type,
        normalized.channels,
        normalized.confidence,
        category_url,
    )
    return normalized


def _reuse_duplicate_normalization(raw_event: RawEvent, client: LLMClient) -> NormalizedEvent | None:
    try:
        from app.store.event_store import fetch_normalized_event
        from app.store.vector_store import check_duplicate, save_embedding
    except Exception:
        return None

    embedding_text = _embedding_text(raw_event)
    if not embedding_text:
        return None

    try:
        embedding = client.embedding(embedding_text)
        is_duplicate, existing_id = check_duplicate(embedding)
    except Exception as exc:
        logger.warning("duplicate detection failed raw_event_id=%s: %s", raw_event.id, exc)
        return None

    if not is_duplicate or not existing_id:
        return None

    existing = fetch_normalized_event(existing_id)
    if existing is None:
        return None

    try:
        save_embedding(raw_event.id, raw_event.title, embedding)
    except Exception as exc:
        logger.warning("duplicate embedding persistence failed raw_event_id=%s: %s", raw_event.id, exc)

    logger.info(
        "semantic duplicate raw_event_id=%s existing_raw_event_id=%s; reusing normalization",
        raw_event.id,
        existing_id,
    )
    return existing.model_copy(update={"raw_event_id": raw_event.id})


def _persist_embedding(raw_event: RawEvent, details_text: str, client: LLMClient) -> None:
    try:
        from app.store.vector_store import save_embedding
    except Exception:
        return

    embedding_text = _embedding_text(raw_event, details_text)
    if not embedding_text:
        return

    try:
        embedding = client.embedding(embedding_text)
        save_embedding(raw_event.id, raw_event.title, embedding)
    except Exception as exc:
        logger.warning("embedding persistence failed raw_event_id=%s: %s", raw_event.id, exc)


def _log_eval(client: LLMClient, normalized: NormalizedEvent) -> None:
    try:
        from app.llm.evaluator import log_eval

        log_eval(
            raw_event_id=normalized.raw_event_id,
            event_type=normalized.event_type,
            risk_signal=normalized.risk_signal,
            confidence=normalized.confidence,
            provider=client.provider_name,
            model=client.model,
        )
    except Exception as exc:
        logger.warning("eval logging failed raw_event_id=%s: %s", normalized.raw_event_id, exc)


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
        value = {}
    return {
        "risk_sentiment": str(value.get("risk_sentiment", "neutral")),
        "volatility": str(value.get("volatility", "elevated")),
        "liquidity": str(value.get("liquidity", "neutral")),
    }


def _normalize_channels(
    channels: list[str] | None,
    risk_signal: str,
    rate_signal: str,
    geo_signal: str,
) -> list[str]:
    normalized = [_normalize_token(ch) for ch in (channels or []) if ch]
    for implied in (risk_signal,):
        if implied in {"risk_on", "risk_off"} and implied not in normalized:
            normalized.append(implied)
    if rate_signal == "tightening" and "rate_tightening" not in normalized:
        normalized.append("rate_tightening")
    if rate_signal == "easing" and "rate_easing" not in normalized:
        normalized.append("rate_easing")
    if geo_signal == "escalation" and "geo_escalation" not in normalized:
        normalized.append("geo_escalation")
    if geo_signal == "deescalation" and "geo_deescalation" not in normalized:
        normalized.append("geo_deescalation")
    return list(dict.fromkeys(normalized))


def _normalize_sector_impacts(value: dict[str, int] | None) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for sector, score in value.items():
        if not sector:
            continue
        try:
            normalized[str(sector)] = max(-3, min(3, int(score)))
        except (TypeError, ValueError):
            continue
    return normalized


def _details_summary(payload: dict) -> tuple[str, str]:
    if not isinstance(payload, dict):
        return ("", "")
    category_url = str(payload.get("category_url") or "")
    details = payload.get("details")
    if not isinstance(details, dict):
        return ("", category_url)

    fields = [
        "title",
        "headline",
        "description",
        "summary",
        "body",
        "content",
        "text",
    ]
    parts = []
    for key in fields:
        value = details.get(key)
        if value:
            parts.append(str(value))
    for container_key in ["article", "data", "result"]:
        container = details.get(container_key)
        if isinstance(container, dict):
            for key in fields:
                value = container.get(key)
                if value:
                    parts.append(str(value))
    if not parts:
        return ("", category_url)
    trimmed = []
    for part in parts[:3]:
        text = str(part).strip()
        if len(text) > 350:
            text = text[:350]
        trimmed.append(text)
    summary = " | ".join(trimmed)
    if len(summary) > 900:
        summary = summary[:900]
    return (summary, category_url)


def extract_details_text(payload: dict) -> str:
    summary, _ = _details_summary(payload)
    return summary


def _embedding_text(raw_event: RawEvent, details_text: str | None = None) -> str:
    details = details_text if details_text is not None else extract_details_text(raw_event.payload)
    parts = [raw_event.title or "", details or ""]
    return " ".join(part.strip() for part in parts if part).strip()
