from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from app.llm.client import LLMClient

logger = logging.getLogger("app.llm.structured")

StructuredModelT = TypeVar("StructuredModelT", bound=BaseModel)


class RegimeModel(BaseModel):
    risk_sentiment: str = Field(description="risk_on | risk_off | neutral")
    volatility: str = Field(description="low | elevated | high")
    liquidity: str = Field(description="loose | neutral | tight")


class ClassificationOutput(BaseModel):
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
    confidence: float = Field(ge=0.0, le=1.0)


class ChannelOutput(BaseModel):
    rate_signal: str = Field(description="tightening | easing | none")
    geo_signal: str = Field(description="escalation | deescalation | none")
    channels: list[str] = Field(
        description="Subset of: risk_off, risk_on, rate_tightening, rate_easing, geo_escalation, geo_deescalation"
    )
    regime: RegimeModel


class RationaleOutput(BaseModel):
    keywords: list[str] = Field(description="3 to 6 salient terms from the article")
    rationale: str = Field(description="2 to 3 sentence market rationale with at least one number")
    sentiment: str = Field(description="positive | negative | neutral")
    sector_impacts: dict[str, int] = Field(
        default_factory=dict,
        description="Optional direct sector tilt from -3 to +3, keyed by sector name",
    )


class NormalizationOutput(BaseModel):
    event_type: str
    policy_domain: str
    risk_signal: str
    rate_signal: str
    geo_signal: str
    channels: list[str]
    confidence: float
    regime: RegimeModel
    keywords: list[str]
    rationale: str
    sentiment: str = "neutral"
    sector_impacts: dict[str, int] = Field(default_factory=dict)


def call_schema(
    client: LLMClient,
    *,
    schema_model: type[StructuredModelT],
    messages: list[dict[str, str]],
    schema_name: str,
    description: str,
) -> StructuredModelT:
    """Call the model with a strict JSON schema and validate the result."""
    data = client.structured_chat(
        messages,
        schema_name=schema_name,
        schema=_strict_json_schema(schema_model),
        description=description,
    )
    result = schema_model.model_validate(data)
    logger.debug("Structured %s output=%s", schema_name, result.model_dump())
    return result


def merge_normalization_outputs(
    classify: ClassificationOutput,
    channel: ChannelOutput,
    rationale: RationaleOutput,
) -> NormalizationOutput:
    return NormalizationOutput(
        event_type=classify.event_type,
        policy_domain=classify.policy_domain,
        risk_signal=classify.risk_signal,
        rate_signal=channel.rate_signal,
        geo_signal=channel.geo_signal,
        channels=channel.channels,
        confidence=classify.confidence,
        regime=channel.regime,
        keywords=rationale.keywords,
        rationale=rationale.rationale,
        sentiment=rationale.sentiment,
        sector_impacts=rationale.sector_impacts,
    )


def _strict_json_schema(schema_model: type[BaseModel]) -> dict[str, Any]:
    schema = schema_model.model_json_schema()
    schema["additionalProperties"] = False
    return schema
