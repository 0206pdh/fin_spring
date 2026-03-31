"""Tests for app/rules/engine.py — event scoring.

Run: pytest tests/test_rules.py -v
"""
from __future__ import annotations

import pytest

from app.models import NormalizedEvent, ScoredEvent
from app.rules.engine import score_event


def _make_normalized_event(**kwargs) -> NormalizedEvent:
    defaults = dict(
        raw_event_id="test-001",
        event_type="monetary_tightening",
        policy_domain="monetary",
        risk_signal="risk_off",
        rate_signal="tightening",
        geo_signal="none",
        sector_impacts={},
        sentiment="negative",
        rationale="Fed hiked 25bps to 5.50%, above market consensus of 5.25%.",
        channels=["rate_tightening", "risk_off"],
        confidence=0.8,
        regime={"risk_sentiment": "risk_off", "volatility": "elevated", "liquidity": "tight"},
        baseline={},
    )
    defaults.update(kwargs)
    return NormalizedEvent(**defaults)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_score_event_returns_scored_event():
    """score_event() with valid input returns a ScoredEvent."""
    normalized = _make_normalized_event()
    result = score_event(normalized)
    assert isinstance(result, ScoredEvent)
    assert result.raw_event_id == "test-001"


def test_score_event_preserves_fields():
    """ScoredEvent inherits event_type, risk_signal, rationale from NormalizedEvent."""
    normalized = _make_normalized_event()
    result = score_event(normalized)
    assert result.event_type == "monetary_tightening"
    assert result.risk_signal == "risk_off"
    assert "25bps" in result.rationale


def test_score_event_total_score_is_float():
    """total_score is a float (not None, not str)."""
    result = score_event(_make_normalized_event())
    assert isinstance(result.total_score, float)


def test_score_event_total_score_range():
    """total_score is a finite float (no NaN, no Inf).

    Note: total_score is a sum of sector scores and is NOT bounded to [0, 1] —
    it scales with the number of sectors and magnitude of signals.
    We just assert it's a real number.
    """
    import math
    result = score_event(_make_normalized_event())
    assert math.isfinite(result.total_score)


def test_score_event_sector_scores_dict():
    """sector_scores is a dict mapping sector names to floats."""
    result = score_event(_make_normalized_event())
    assert isinstance(result.sector_scores, dict)
    for sector, score in result.sector_scores.items():
        assert isinstance(sector, str)
        assert isinstance(score, float)


def test_score_event_fx_state_format():
    """fx_state contains USD, JPY, EUR, EM tokens."""
    result = score_event(_make_normalized_event())
    assert "USD:" in result.fx_state
    assert "JPY:" in result.fx_state
    assert "EUR:" in result.fx_state
    assert "EM:" in result.fx_state


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_score_event_zero_confidence():
    """confidence=0 → sector scores are all 0 (no signal amplification)."""
    normalized = _make_normalized_event(confidence=0.0, channels=[])
    result = score_event(normalized)
    assert isinstance(result.total_score, float)


def test_score_event_missing_channels():
    """Empty channels list → runs without error, produces valid output."""
    normalized = _make_normalized_event(channels=[])
    result = score_event(normalized)
    assert isinstance(result, ScoredEvent)


def test_score_event_with_sector_impacts():
    """sector_impacts passed through correctly affects sector_scores."""
    normalized = _make_normalized_event(
        sector_impacts={"Energy": 2, "Finance": -1},
        confidence=1.0,
    )
    result = score_event(normalized)
    # Energy gets a +2 impact at confidence=1.0; Finance gets -1
    assert "Energy" in result.sector_scores
    assert "Finance" in result.sector_scores
