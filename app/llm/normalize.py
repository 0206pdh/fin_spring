from __future__ import annotations

from app.config import settings
import logging

from app.llm.mistral_client import MistralClient, _safe_json
from app.models import NormalizedEvent, RawEvent

SYSTEM_PROMPT = (
    "You are an event normalizer for macro, geopolitics, and policy news. "
    "Read the full input as one document and return a single JSON object "
    "covering the overall event. Return a single valid JSON object with the "
    "schema exactly as requested. Do not include any extra text before or "
    "after the JSON. Always end the response with a closing brace }."
)

USER_TEMPLATE = """
Raw event title: {title}
Sector tag: {sector}
Published at: {published_at}
Category url: {category_url}
Details: {details_text}

Extract a normalized event JSON with this schema:
{{
  "event_type": "string",
  "policy_domain": "monetary|fiscal|geopolitics|industry",
  "risk_signal": "risk_on|risk_off|neutral",
  "rate_signal": "tightening|easing|none",
  "geo_signal": "escalation|deescalation|none",
  "channels": ["string"],
  "confidence": 0.0,
  "regime": {{
    "risk_sentiment": "risk_on|risk_off|neutral",
    "volatility": "low|elevated|high",
    "liquidity": "loose|neutral|tight"
  }},
  "keywords": ["string"],
  "rationale": "string"
}}

Constraints:
- Do not include extra keys beyond the schema.
- Read the full input once (not per sentence or per paragraph).
- Return exactly one JSON object for the overall event. Do not repeat keys.
- Always end the response with a closing brace }}.
- policy_domain must be one of: monetary, fiscal, geopolitics, industry.
 - risk_signal must be one of: risk_on, risk_off, neutral.
 - rate_signal must be one of: tightening, easing, none.
 - geo_signal must be one of: escalation, deescalation, none.
 - channels must be selected from: risk_off, risk_on, rate_tightening, rate_easing, geo_escalation, geo_deescalation.
 - confidence must be between 0 and 1.
 - regime must include risk_sentiment, volatility, and liquidity with the allowed values above.
 - keywords must be a short list of salient terms from the article.
- rationale must explicitly justify why risk_signal and geo_signal are chosen based on concrete evidence.

Risk assessment rules:
- risk_signal is NOT determined only by event_type.
- regulation_update can be risk_off if:
  * legal enforcement, investigation, fines, or bans are mentioned
  * strong public backlash or reputational damage is described
  * multiple countries or regulators are involved
- regulation_update is neutral ONLY if it is a routine or clarifying policy change.

Geo assessment rules:
- geo_signal is escalation if:
  * multiple countries, regions, or global regulators are involved
  * cross-border enforcement, bans, or coordinated actions are mentioned
- geo_signal is none ONLY if the event is confined to a single country or company.

Before producing the final JSON, internally evaluate:
1. Is this event likely to increase uncertainty or regulatory pressure?
2. Does it introduce downside risk to a sector or platform?
3. Is the impact localized or global?
- event_type must be one of:
  geopolitics_conflict, war_escalation, terror_attack, monetary_tightening,
  inflation_hot, banking_stress, trade_sanction, recession_signal,
  monetary_easing, stimulus, inflation_cooling, earnings_positive, ceasefire,
  policy_stability, regulation_update.
- event_type implies risk_signal (use these pairs):
  geopolitics_conflict=risk_off, war_escalation=risk_off, terror_attack=risk_off,
  monetary_tightening=risk_off, inflation_hot=risk_off, banking_stress=risk_off,
  trade_sanction=risk_off, recession_signal=risk_off, monetary_easing=risk_on,
  stimulus=risk_on, inflation_cooling=risk_on, earnings_positive=risk_on,
  ceasefire=risk_on, policy_stability=neutral, regulation_update=neutral.
- If unsure, choose policy_stability and neutral signals.

Example output (format only, values must be from allowed lists):
{{
  "event_type": "policy_stability",
  "policy_domain": "industry",
  "risk_signal": "neutral",
  "rate_signal": "none",
  "geo_signal": "none",
  "channels": ["risk_off"],
  "confidence": 0.6,
  "regime": {{
    "risk_sentiment": "neutral",
    "volatility": "elevated",
    "liquidity": "neutral"
  }},
  "keywords": ["policy", "markets"],
  "rationale": "Article lacks clear macro shocks, so defaults to policy stability."
}}
"""

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

logger = logging.getLogger("app.llm")

def _normalize_event_type(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_event(raw_event: RawEvent) -> NormalizedEvent:
    details_text, category_url = _details_summary(raw_event.payload)
    user_prompt = USER_TEMPLATE.format(
        title=raw_event.title,
        sector=raw_event.sector,
        published_at=raw_event.published_at,
        category_url=category_url,
        details_text=details_text,
    )
    provider = (settings.llm_provider or "local").strip().lower()
    client = MistralClient()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    response = client.chat(messages)
    choices = response.get("choices", [])
    content = ""
    if choices:
        content = choices[0].get("message", {}).get("content", "") or ""
    logger.info("LLM raw output: %s", content)
    data = _safe_json(content)
    event_type = _normalize_event_type(str(data.get("event_type", "policy_stability")))
    policy_domain = _normalize_event_type(str(data.get("policy_domain", "industry")))
    risk_signal = _normalize_event_type(str(data.get("risk_signal", "neutral")))
    rate_signal = _normalize_event_type(str(data.get("rate_signal", "none")))
    geo_signal = _normalize_event_type(str(data.get("geo_signal", "none")))

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

    mapped_risk = EVENT_TYPE_RISK_SIGNAL.get(event_type)
    if risk_signal == "neutral" and mapped_risk:
        risk_signal = mapped_risk
    keywords = data.get("keywords") or []
    rationale = str(data.get("rationale", "")).strip()
    channels = data.get("channels") or []
    confidence = data.get("confidence", 0.6)
    regime = data.get("regime") or {}
    logger.info("LLM keywords: %s", keywords)
    logger.info("LLM rationale: %s", rationale if rationale else "(none)")
    logger.info("LLM channels: %s", channels)
    logger.info("LLM confidence: %s", confidence)
    logger.info("LLM regime: %s", regime)
    try:
        confidence_value = float(confidence) if confidence is not None else 0.6
    except (TypeError, ValueError):
        confidence_value = 0.6
    return NormalizedEvent(
        raw_event_id=raw_event.id,
        event_type=event_type,
        policy_domain=policy_domain,
        risk_signal=risk_signal,
        rate_signal=rate_signal,
        geo_signal=geo_signal,
        sector_impacts={k: int(v) for k, v in (data.get("sector_impacts") or {}).items()},
        sentiment=str(data.get("sentiment", "neutral")),
        rationale=rationale,
        channels=[str(ch) for ch in channels if ch],
        confidence=confidence_value,
        regime={str(k): str(v) for k, v in regime.items()} if isinstance(regime, dict) else {},
    )


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
