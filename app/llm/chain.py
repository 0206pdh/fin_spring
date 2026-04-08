"""LangGraph-driven multi-step normalization chain.

This replaces the old "single prompt then _safe_json()" path with an explicit
three-node graph:

classify -> channel -> rationale

Each node produces a validated Pydantic object via strict JSON schema output.
The graph itself is intentionally linear today, but using LangGraph gives us a
real orchestration layer for retries, branching, and observability later.
"""
from __future__ import annotations

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.llm.client import LLMClient
from app.llm.structured import (
    ChannelOutput,
    ClassificationOutput,
    NormalizationOutput,
    RationaleOutput,
    call_schema,
    merge_normalization_outputs,
)

logger = logging.getLogger("app.llm.chain")


CLASSIFY_SYSTEM_PROMPT = (
    "You are the classification node in a financial-event normalization graph. "
    "Your only job is to classify the event type, policy domain, and primary risk signal. "
    "Do not write rationales. Do not infer channels yet. Return only schema-compliant JSON."
)

CHANNEL_SYSTEM_PROMPT = (
    "You are the transmission-channel node in a financial-event normalization graph. "
    "Given an already classified event, determine how the event propagates into FX and sector risk. "
    "Return only schema-compliant JSON."
)

RATIONALE_SYSTEM_PROMPT = (
    "You are the rationale node in a financial-event normalization graph. "
    "Write analyst-grade justification for the already classified event and channel selection. "
    "The rationale must include at least one numeric token such as %, $, bps, or a 4-digit year. "
    "Return only schema-compliant JSON."
)


class NormChainState(TypedDict, total=False):
    title: str
    sector: str
    published_at: str
    details_text: str
    event_type: str
    policy_domain: str
    risk_signal: str
    confidence: float
    rate_signal: str
    geo_signal: str
    channels: list[str]
    regime: dict[str, str]
    keywords: list[str]
    rationale: str
    sentiment: str
    sector_impacts: dict[str, int]


class NormalizationChain:
    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()
        self._graph = self._build_graph()

    def run(
        self,
        *,
        title: str,
        sector: str,
        published_at: str,
        details_text: str,
    ) -> NormalizationOutput:
        state: NormChainState = {
            "title": title,
            "sector": sector,
            "published_at": published_at,
            "details_text": details_text,
        }
        result = self._graph.invoke(state)
        classify = ClassificationOutput(
            event_type=result["event_type"],
            policy_domain=result["policy_domain"],
            risk_signal=result["risk_signal"],
            confidence=result["confidence"],
        )
        channel = ChannelOutput(
            rate_signal=result["rate_signal"],
            geo_signal=result["geo_signal"],
            channels=result.get("channels", []),
            regime=result.get("regime", {}),
        )
        rationale = RationaleOutput(
            keywords=result.get("keywords", []),
            rationale=result.get("rationale", ""),
            sentiment=result.get("sentiment", "neutral"),
            sector_impacts=result.get("sector_impacts", {}),
        )
        return merge_normalization_outputs(classify, channel, rationale)

    def _build_graph(self):
        workflow = StateGraph(NormChainState)
        workflow.add_node("classify", self._classify_node)
        workflow.add_node("channel", self._channel_node)
        workflow.add_node("rationale", self._rationale_node)
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", "channel")
        workflow.add_edge("channel", "rationale")
        workflow.add_edge("rationale", END)
        return workflow.compile()

    def _classify_node(self, state: NormChainState) -> NormChainState:
        details = state.get("details_text", "")[:1000]
        result = call_schema(
            self.client,
            schema_model=ClassificationOutput,
            schema_name="classification_output",
            description="Classify a financial news event before any market-channel reasoning.",
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Title: {state['title']}\n"
                        f"Sector tag: {state['sector']}\n"
                        f"Published at: {state['published_at']}\n"
                        f"Details:\n{details}\n\n"
                        "Allowed event_type values:\n"
                        "- geopolitics_conflict\n- war_escalation\n- terror_attack\n"
                        "- monetary_tightening\n- inflation_hot\n- banking_stress\n"
                        "- trade_sanction\n- recession_signal\n- monetary_easing\n"
                        "- stimulus\n- inflation_cooling\n- earnings_positive\n"
                        "- ceasefire\n- policy_stability\n- regulation_update\n\n"
                        "Map event type to the dominant immediate risk signal."
                    ),
                },
            ],
        )
        logger.debug("classify node=%s", result.model_dump())
        return result.model_dump()

    def _channel_node(self, state: NormChainState) -> NormChainState:
        result = call_schema(
            self.client,
            schema_model=ChannelOutput,
            schema_name="channel_output",
            description="Determine transmission channels from a classified financial event.",
            messages=[
                {"role": "system", "content": CHANNEL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Title: {state['title']}\n"
                        f"Classified event_type: {state.get('event_type', 'policy_stability')}\n"
                        f"Policy domain: {state.get('policy_domain', 'industry')}\n"
                        f"Risk signal: {state.get('risk_signal', 'neutral')}\n"
                        f"Details: {state.get('details_text', '')[:1000]}\n\n"
                        "Choose the channels that best explain the FX and cross-asset transmission. "
                        "channels must be selected from risk_off, risk_on, rate_tightening, "
                        "rate_easing, geo_escalation, geo_deescalation."
                    ),
                },
            ],
        )
        logger.debug("channel node=%s", result.model_dump())
        return result.model_dump()

    def _rationale_node(self, state: NormChainState) -> NormChainState:
        result = call_schema(
            self.client,
            schema_model=RationaleOutput,
            schema_name="rationale_output",
            description="Write a numeric, analyst-style rationale for the normalized event.",
            messages=[
                {"role": "system", "content": RATIONALE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Title: {state['title']}\n"
                        f"Sector tag: {state['sector']}\n"
                        f"Published at: {state['published_at']}\n"
                        f"Details: {state.get('details_text', '')[:1200]}\n"
                        f"event_type: {state.get('event_type', 'policy_stability')}\n"
                        f"policy_domain: {state.get('policy_domain', 'industry')}\n"
                        f"risk_signal: {state.get('risk_signal', 'neutral')}\n"
                        f"rate_signal: {state.get('rate_signal', 'none')}\n"
                        f"geo_signal: {state.get('geo_signal', 'none')}\n"
                        f"channels: {', '.join(state.get('channels', [])) or 'none'}\n"
                        f"confidence: {state.get('confidence', 0.6)}\n\n"
                        "Write in the tone of a sell-side macro note. "
                        "Mention the mechanism from the event to markets. "
                        "Include direct sector impacts only when the article justifies them."
                    ),
                },
            ],
        )
        logger.debug("rationale node=%s", result.model_dump())
        return result.model_dump()


def run_norm_chain(
    *,
    title: str,
    sector: str,
    published_at: str,
    details_text: str,
    client: LLMClient | None = None,
) -> NormalizationOutput:
    return NormalizationChain(client=client).run(
        title=title,
        sector=sector,
        published_at=published_at,
        details_text=details_text,
    )
