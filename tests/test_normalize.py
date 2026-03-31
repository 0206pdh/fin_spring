"""Tests for app/llm/normalize.py — event classification + rationale validation.

Run: pytest tests/test_normalize.py -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.llm.normalize import (
    ALLOWED_EVENT_TYPES,
    _FALLBACK_NUMERIC_PHRASE,
    _validate_rationale,
    normalize_event,
)
from app.models import RawEvent


def _make_raw_event(**kwargs) -> RawEvent:
    defaults = dict(
        id="test-001",
        title="Test headline",
        url="https://example.com/article",
        published_at="2024-01-01T00:00:00Z",
        sector="Finance",
        source="bbc",
        payload={"details": {"summary": "Test article body text."}},
    )
    defaults.update(kwargs)
    return RawEvent(**defaults)


def _mock_llm_response(data: dict) -> dict:
    import json
    return {
        "choices": [
            {"message": {"content": json.dumps(data)}}
        ]
    }


# ---------------------------------------------------------------------------
# event_type fallback
# ---------------------------------------------------------------------------

def test_event_type_fallback():
    """Unknown event_type from LLM → falls back to policy_stability."""
    llm_data = {
        "event_type": "alien_invasion",  # not in ALLOWED_EVENT_TYPES
        "policy_domain": "geopolitics",
        "risk_signal": "risk_off",
        "rate_signal": "none",
        "geo_signal": "none",
        "channels": ["risk_off"],
        "confidence": 0.7,
        "regime": {"risk_sentiment": "risk_off", "volatility": "elevated", "liquidity": "neutral"},
        "keywords": ["test"],
        "rationale": "Alien invasion detected in 2024, causing $500B economic disruption.",
    }
    with patch("app.llm.normalize.LLMClient") as MockClient:
        MockClient.return_value.chat.return_value = _mock_llm_response(llm_data)
        result = normalize_event(_make_raw_event())

    assert result.event_type == "policy_stability"
    assert result.event_type in ALLOWED_EVENT_TYPES


def test_known_event_type_preserved():
    """Known event_type is kept as-is."""
    llm_data = {
        "event_type": "monetary_tightening",
        "policy_domain": "monetary",
        "risk_signal": "risk_off",
        "rate_signal": "tightening",
        "geo_signal": "none",
        "channels": ["rate_tightening"],
        "confidence": 0.85,
        "regime": {"risk_sentiment": "risk_off", "volatility": "elevated", "liquidity": "tight"},
        "keywords": ["Fed", "rate hike", "25bps"],
        "rationale": "Fed hiked 25bps to 5.50%, dot-plot median for 2024 revised to 4.6%.",
    }
    with patch("app.llm.normalize.LLMClient") as MockClient:
        MockClient.return_value.chat.return_value = _mock_llm_response(llm_data)
        result = normalize_event(_make_raw_event())

    assert result.event_type == "monetary_tightening"


# ---------------------------------------------------------------------------
# Rationale number validator
# ---------------------------------------------------------------------------

def test_rationale_number_validator():
    """Rationale with no numeric token → fallback phrase appended."""
    rationale_no_numbers = "Sector pressure detected. Market uncertainty may increase."
    result = _validate_rationale(rationale_no_numbers)
    assert _FALLBACK_NUMERIC_PHRASE in result


def test_rationale_with_number_passes():
    """Rationale containing '$240M' → no fallback phrase added."""
    rationale_with_number = "Regulator levied $240M fine on the platform for antitrust violations."
    result = _validate_rationale(rationale_with_number)
    assert _FALLBACK_NUMERIC_PHRASE not in result
    assert result == rationale_with_number


def test_rationale_with_percentage_passes():
    """Rationale containing a percentage → passes without fallback."""
    rationale = "CPI rose 3.4% YoY, above consensus of 3.2%, pushing yields higher."
    result = _validate_rationale(rationale)
    assert _FALLBACK_NUMERIC_PHRASE not in result


def test_rationale_with_year_passes():
    """Rationale containing a 4-digit year → passes (year counts as numeric token)."""
    rationale = "Policy implemented in 2024 signals tighter regulatory environment ahead."
    result = _validate_rationale(rationale)
    assert _FALLBACK_NUMERIC_PHRASE not in result


def test_rationale_empty_unchanged():
    """Empty rationale → no fallback appended (nothing to validate)."""
    result = _validate_rationale("")
    assert result == ""


# ---------------------------------------------------------------------------
# End-to-end normalize_event smoke test (no LLM call)
# ---------------------------------------------------------------------------

def test_normalize_event_returns_normalized_event():
    """normalize_event() returns a NormalizedEvent with required fields."""
    from app.models import NormalizedEvent

    llm_data = {
        "event_type": "inflation_hot",
        "policy_domain": "monetary",
        "risk_signal": "risk_off",
        "rate_signal": "tightening",
        "geo_signal": "none",
        "channels": ["rate_tightening", "risk_off"],
        "confidence": 0.8,
        "regime": {"risk_sentiment": "risk_off", "volatility": "elevated", "liquidity": "tight"},
        "keywords": ["CPI", "inflation", "3.4%"],
        "rationale": "CPI printed at 3.4%, above the 3.2% consensus estimate for January 2024.",
    }
    with patch("app.llm.normalize.LLMClient") as MockClient:
        MockClient.return_value.chat.return_value = _mock_llm_response(llm_data)
        result = normalize_event(_make_raw_event())

    assert isinstance(result, NormalizedEvent)
    assert result.raw_event_id == "test-001"
    assert result.event_type in ALLOWED_EVENT_TYPES
    assert 0.0 <= result.confidence <= 1.0
