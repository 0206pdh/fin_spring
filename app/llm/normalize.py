from __future__ import annotations

import re
from app.config import settings
import logging

from app.llm.client import LLMClient, _safe_json
from app.models import NormalizedEvent, RawEvent

# ---------------------------------------------------------------------------
# Analyst-grade system prompt (FinGPT-style)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a macro analyst at a Tier-1 investment bank covering cross-asset markets. "
    "Your job is to classify economic and geopolitical events and assess their market impact "
    "with the precision of a sell-side research note.\n\n"
    "RATIONALE STANDARDS — every rationale MUST:\n"
    "1. Cite at least one concrete data point: a percentage, basis-point move, dollar amount, "
    "date, or named entity (e.g., 'Fed funds rate at 5.25-5.50%', '$2.1B fine', '25bps hike').\n"
    "2. Name the transmission mechanism: how this event flows through to FX and equities "
    "(e.g., 'higher CPI → hawkish Fed repricing → USD strength → EM currency pressure').\n"
    "3. State a directional bias with a magnitude estimate where possible "
    "(e.g., 'Energy sector faces 5-8% earnings headwind', 'USD/JPY likely to test 155').\n\n"
    "FORBIDDEN phrases: 'sector pressure detected', 'market impact expected', "
    "'uncertainty increases', 'could affect markets', 'may lead to volatility'.\n\n"
    "Return a single valid JSON object with the schema exactly as requested. "
    "Do not include any extra text before or after the JSON. "
    "Always end the response with a closing brace }."
)

# ---------------------------------------------------------------------------
# User prompt template with 3-sub-question CoT
# ---------------------------------------------------------------------------

USER_TEMPLATE = """
Raw event title: {title}
Sector tag: {sector}
Published at: {published_at}
Category url: {category_url}
Details: {details_text}

Before writing the rationale, reason through these 3 questions internally:
Q1 (Data): What concrete numbers, names, or dates appear in this article?
           (e.g., specific percentages, dollar figures, named countries/companies, deadlines)
Q2 (Mechanism): What is the step-by-step transmission channel from this event to markets?
           (e.g., tariff → input cost rise → margin compression → sector rotation out of industrials)
Q3 (Magnitude): How large is the likely impact? Is this a 1-2% move or a structural regime shift?
           Reference historical comparables if relevant.

Now extract a normalized event JSON with this schema:
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

Rationale format: Write 2-3 sentences in the voice of a Bloomberg sell-side note.
Lead with the specific data point from Q1, trace the mechanism from Q2, conclude
with the directional impact from Q3. Include at least one number (%, $, bps, or date).

Example of a GOOD rationale:
"The Fed's 25bps rate hold at 5.25-5.50% alongside revised 2024 dot-plot median of 4.6%
(down from 5.1%) signals a pivot within 2 quarters. Transmission: lower terminal rate
expectations → DXY weakness → EM local currency bonds become attractive. Energy and
Financials face 3-5% multiple contraction as the risk-free rate anchor shifts lower."

Example of a BAD rationale (forbidden):
"The event may lead to market uncertainty. Sector pressure detected. Impact could be significant."

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
- rationale must contain at least one numeric token (%, $, bps, or a 4-digit year) and name the transmission channel.

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
"""

# ---------------------------------------------------------------------------
# Signal mappings and allowed values
# ---------------------------------------------------------------------------

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

# Rationale fallback phrase appended when LLM produces no numeric tokens.
# Triggers the tests/test_normalize.py::test_rationale_number_validator assertion.
_FALLBACK_NUMERIC_PHRASE = " (quantitative data unavailable for this event)"

_NUMBER_PATTERN = re.compile(r"\d+")

logger = logging.getLogger("app.llm")


def _normalize_event_type(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _validate_rationale(rationale: str) -> str:
    """Ensure rationale contains at least one numeric token.

    If not, appends a fallback phrase so downstream consumers can detect
    low-quality rationales without crashing (they fail a regex check, not an exception).
    """
    if not rationale:
        return rationale
    if not _NUMBER_PATTERN.search(rationale):
        logger.warning("rationale missing numeric token — appending fallback phrase")
        return rationale + _FALLBACK_NUMERIC_PHRASE
    return rationale


def normalize_event(raw_event: RawEvent) -> NormalizedEvent:
    details_text, category_url = _details_summary(raw_event.payload)
    user_prompt = USER_TEMPLATE.format(
        title=raw_event.title,
        sector=raw_event.sector,
        published_at=raw_event.published_at,
        category_url=category_url,
        details_text=details_text,
    )
    client = LLMClient()
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
    rationale = _validate_rationale(str(data.get("rationale", "")).strip())
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
