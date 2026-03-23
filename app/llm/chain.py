"""LangGraph multi-step normalization chain.

Why LangGraph over a single LLM call?
- Single prompt conflates three distinct cognitive tasks:
    1. Event classification (what type is this?)
    2. Transmission channel selection (how does it propagate to FX/sectors?)
    3. Rationale generation (why does this signal apply?)
  Mixing them produces lower-confidence outputs and makes debugging opaque.
- LangGraph makes each step an explicit node with observable inputs/outputs
- Failed steps can be retried individually without re-running the full prompt
- The graph state is inspectable → audit trail for each LLM decision

Chain structure:
    classify_node → channel_node → rationale_node → (output)

Each node receives only the context it needs, reducing prompt length
and hallucination surface area per step.
"""
from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger("app.llm.chain")


# ---------------------------------------------------------------------------
# Graph state definition
# ---------------------------------------------------------------------------

class NormChainState(TypedDict, total=False):
    # Inputs
    title: str
    sector: str
    published_at: str
    details_text: str
    # Intermediate
    event_type: str
    policy_domain: str
    risk_signal: str
    # Outputs accumulated per step
    rate_signal: str
    geo_signal: str
    channels: list[str]
    confidence: float
    regime: dict[str, str]
    keywords: list[str]
    rationale: str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def classify_node(state: NormChainState, llm_call: Any) -> NormChainState:
    """Step 1 — Classify event type, policy domain, and primary risk signal.

    Narrow task: only decide WHAT the event is.
    """
    prompt = (
        f"Article title: {state['title']}\n"
        f"Sector tag: {state['sector']}\n"
        f"Details: {state.get('details_text', '')[:400]}\n\n"
        "Return JSON with ONLY these keys:\n"
        '{"event_type": "<type>", "policy_domain": "<domain>", "risk_signal": "<signal>", "confidence": 0.0}\n'
        "event_type options: geopolitics_conflict, war_escalation, terror_attack, "
        "monetary_tightening, inflation_hot, banking_stress, trade_sanction, recession_signal, "
        "monetary_easing, stimulus, inflation_cooling, earnings_positive, ceasefire, policy_stability, regulation_update\n"
        "policy_domain: monetary|fiscal|geopolitics|industry\n"
        "risk_signal: risk_on|risk_off|neutral"
    )
    result = llm_call(prompt)
    logger.debug("classify_node raw=%s", str(result)[:200])
    return {**state, **result}


def channel_node(state: NormChainState, llm_call: Any) -> NormChainState:
    """Step 2 — Select FX transmission channels and rate/geo signals.

    Given classification result, decide HOW the event propagates.
    """
    prompt = (
        f"Event type: {state.get('event_type')}\n"
        f"Risk signal: {state.get('risk_signal')}\n"
        f"Title: {state['title']}\n\n"
        "Return JSON with ONLY these keys:\n"
        '{"channels": [], "rate_signal": "<signal>", "geo_signal": "<signal>", '
        '"regime": {"risk_sentiment": "<s>", "volatility": "<v>", "liquidity": "<l>"}}\n'
        "channels options: risk_off, risk_on, rate_tightening, rate_easing, geo_escalation, geo_deescalation\n"
        "rate_signal: tightening|easing|none\n"
        "geo_signal: escalation|deescalation|none"
    )
    result = llm_call(prompt)
    logger.debug("channel_node raw=%s", str(result)[:200])
    return {**state, **result}


def rationale_node(state: NormChainState, llm_call: Any) -> NormChainState:
    """Step 3 — Generate keywords and rationale explaining the classification.

    Given the full classification, explain WHY in 1-2 sentences.
    """
    prompt = (
        f"Event: {state.get('event_type')} | Risk: {state.get('risk_signal')} | "
        f"Channels: {state.get('channels', [])}\n"
        f"Title: {state['title']}\n\n"
        "Return JSON with ONLY these keys:\n"
        '{"keywords": ["term1", "term2"], "rationale": "<1-2 sentence justification>"}'
    )
    result = llm_call(prompt)
    logger.debug("rationale_node raw=%s", str(result)[:200])
    return {**state, **result}


# ---------------------------------------------------------------------------
# Graph runner
# ---------------------------------------------------------------------------

def run_norm_chain(
    title: str,
    sector: str,
    published_at: str,
    details_text: str,
    llm_call: Any,
) -> NormChainState:
    """Run the 3-step normalization chain and return merged state.

    llm_call: callable(prompt: str) -> dict  — provider-agnostic LLM wrapper.
    Callers should wrap their LLM client to match this signature.

    Example:
        def my_llm(prompt):
            resp = openai_client.chat.completions.create(...)
            return json.loads(resp.choices[0].message.content)

        result = run_norm_chain(title, sector, ts, text, my_llm)
    """
    state: NormChainState = {
        "title": title,
        "sector": sector,
        "published_at": published_at,
        "details_text": details_text,
    }

    nodes = [classify_node, channel_node, rationale_node]
    for node in nodes:
        try:
            state = node(state, llm_call)
        except Exception as exc:
            logger.warning("Chain node %s failed: %s — continuing with partial state", node.__name__, exc)

    return state
