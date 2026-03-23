"""Structured LLM output using OpenAI function calling.

Why structured output over _safe_json()?
- _safe_json() is a best-effort JSON parser on free-text LLM output
  → brittle, fails on truncated responses, produces silently wrong values
- OpenAI function calling enforces the schema at the API level
  → guaranteed valid JSON that matches our Pydantic model
  → no regex/string hacks, no fallback guessing

This module provides get_structured_normalization() which replaces
the raw normalize_event() call when provider == "openai".
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("app.llm.structured")

# ---------------------------------------------------------------------------
# Pydantic schema — the single source of truth for LLM output structure
# ---------------------------------------------------------------------------

class RegimeModel(BaseModel):
    risk_sentiment: str = Field(description="risk_on | risk_off | neutral")
    volatility: str = Field(description="low | elevated | high")
    liquidity: str = Field(description="loose | neutral | tight")


class NormalizationOutput(BaseModel):
    event_type: str = Field(
        description=(
            "One of: geopolitics_conflict, war_escalation, terror_attack, "
            "monetary_tightening, inflation_hot, banking_stress, trade_sanction, "
            "recession_signal, monetary_easing, stimulus, inflation_cooling, "
            "earnings_positive, ceasefire, policy_stability, regulation_update"
        )
    )
    policy_domain: str = Field(description="monetary | fiscal | geopolitics | industry")
    risk_signal: str = Field(description="risk_on | risk_off | neutral")
    rate_signal: str = Field(description="tightening | easing | none")
    geo_signal: str = Field(description="escalation | deescalation | none")
    channels: list[str] = Field(
        description="Subset of: risk_off, risk_on, rate_tightening, rate_easing, geo_escalation, geo_deescalation"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence 0.0–1.0")
    regime: RegimeModel
    keywords: list[str] = Field(description="3–7 salient terms from the article")
    rationale: str = Field(description="1-2 sentence justification for risk_signal and geo_signal choice")


# ---------------------------------------------------------------------------
# Function calling definition (sent to OpenAI)
# ---------------------------------------------------------------------------

NORMALIZATION_FUNCTION: dict[str, Any] = {
    "name": "normalize_financial_event",
    "description": "Extract a structured financial event from a news article",
    "parameters": {
        "type": "object",
        "properties": {
            "event_type": {
                "type": "string",
                "enum": [
                    "geopolitics_conflict", "war_escalation", "terror_attack",
                    "monetary_tightening", "inflation_hot", "banking_stress",
                    "trade_sanction", "recession_signal", "monetary_easing",
                    "stimulus", "inflation_cooling", "earnings_positive",
                    "ceasefire", "policy_stability", "regulation_update",
                ],
            },
            "policy_domain": {"type": "string", "enum": ["monetary", "fiscal", "geopolitics", "industry"]},
            "risk_signal": {"type": "string", "enum": ["risk_on", "risk_off", "neutral"]},
            "rate_signal": {"type": "string", "enum": ["tightening", "easing", "none"]},
            "geo_signal": {"type": "string", "enum": ["escalation", "deescalation", "none"]},
            "channels": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["risk_off", "risk_on", "rate_tightening", "rate_easing", "geo_escalation", "geo_deescalation"],
                },
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "regime": {
                "type": "object",
                "properties": {
                    "risk_sentiment": {"type": "string", "enum": ["risk_on", "risk_off", "neutral"]},
                    "volatility": {"type": "string", "enum": ["low", "elevated", "high"]},
                    "liquidity": {"type": "string", "enum": ["loose", "neutral", "tight"]},
                },
                "required": ["risk_sentiment", "volatility", "liquidity"],
            },
            "keywords": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
        },
        "required": [
            "event_type", "policy_domain", "risk_signal", "rate_signal",
            "geo_signal", "channels", "confidence", "regime", "keywords", "rationale",
        ],
    },
}


def call_structured_normalization(
    title: str,
    sector: str,
    published_at: str,
    details_text: str,
    openai_client: Any,
    model: str = "gpt-4o-mini",
) -> NormalizationOutput:
    """Call OpenAI with function calling and return a validated NormalizationOutput.

    Raises ValueError if the API doesn't return a valid function call.
    """
    system_msg = (
        "You are an event normalizer for macro, geopolitics, and policy news. "
        "Call the normalize_financial_event function with values extracted from the article."
    )
    user_msg = (
        f"Title: {title}\nSector: {sector}\nPublished: {published_at}\n\n{details_text}"
    )

    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        tools=[{"type": "function", "function": NORMALIZATION_FUNCTION}],
        tool_choice={"type": "function", "function": {"name": "normalize_financial_event"}},
        temperature=0.0,
    )

    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        raise ValueError("OpenAI did not return a function call")

    raw_args = tool_calls[0].function.arguments
    logger.debug("Structured output raw_args=%s", raw_args[:200])

    data = json.loads(raw_args)
    return NormalizationOutput.model_validate(data)
