"""Tests for app/llm/normalize.py and the LangGraph-backed normalization path."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.llm.structured import NormalizationOutput, RegimeModel
from app.llm.normalize import (
    ALLOWED_EVENT_TYPES,
    _FALLBACK_NUMERIC_PHRASE,
    _validate_rationale,
    normalize_event,
)
from app.models import NormalizedEvent, RawEvent


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


def _graph_output(**overrides) -> NormalizationOutput:
    data = dict(
        event_type="monetary_tightening",
        policy_domain="monetary",
        risk_signal="risk_off",
        rate_signal="tightening",
        geo_signal="none",
        channels=["risk_off", "rate_tightening"],
        confidence=0.85,
        regime=RegimeModel(
            risk_sentiment="risk_off",
            volatility="elevated",
            liquidity="tight",
        ),
        keywords=["Fed", "25bps", "rates"],
        rationale="Fed held rates at 5.25% in 2024, reinforcing restrictive policy transmission.",
        sentiment="negative",
        sector_impacts={"Finance": -1},
    )
    data.update(overrides)
    return NormalizationOutput.model_validate(data)


def test_event_type_fallback():
    with patch("app.llm.normalize.run_norm_chain", return_value=_graph_output(event_type="alien_invasion")):
        with patch("app.llm.normalize._reuse_duplicate_normalization", return_value=None):
            with patch("app.llm.normalize._persist_embedding"):
                with patch("app.llm.normalize._log_eval"):
                    result = normalize_event(_make_raw_event(), client=MagicMock())

    assert result.event_type == "policy_stability"
    assert result.event_type in ALLOWED_EVENT_TYPES


def test_known_event_type_preserved():
    with patch("app.llm.normalize.run_norm_chain", return_value=_graph_output()):
        with patch("app.llm.normalize._reuse_duplicate_normalization", return_value=None):
            with patch("app.llm.normalize._persist_embedding"):
                with patch("app.llm.normalize._log_eval"):
                    result = normalize_event(_make_raw_event(), client=MagicMock())

    assert result.event_type == "monetary_tightening"
    assert result.rate_signal == "tightening"
    assert "rate_tightening" in result.channels


def test_rationale_number_validator():
    rationale_no_numbers = "Sector pressure detected. Market uncertainty may increase."
    result = _validate_rationale(rationale_no_numbers)
    assert _FALLBACK_NUMERIC_PHRASE in result


def test_rationale_with_number_passes():
    rationale_with_number = "Regulator levied $240M fine on the platform for antitrust violations."
    result = _validate_rationale(rationale_with_number)
    assert _FALLBACK_NUMERIC_PHRASE not in result
    assert result == rationale_with_number


def test_rationale_with_percentage_passes():
    rationale = "CPI rose 3.4% YoY, above consensus of 3.2%, pushing yields higher."
    result = _validate_rationale(rationale)
    assert _FALLBACK_NUMERIC_PHRASE not in result


def test_rationale_with_year_passes():
    rationale = "Policy implemented in 2024 signals tighter regulatory environment ahead."
    result = _validate_rationale(rationale)
    assert _FALLBACK_NUMERIC_PHRASE not in result


def test_rationale_empty_unchanged():
    result = _validate_rationale("")
    assert result == ""


def test_normalize_event_returns_normalized_event():
    with patch("app.llm.normalize.run_norm_chain", return_value=_graph_output(confidence=0.8)):
        with patch("app.llm.normalize._reuse_duplicate_normalization", return_value=None):
            with patch("app.llm.normalize._persist_embedding"):
                with patch("app.llm.normalize._log_eval"):
                    result = normalize_event(_make_raw_event(), client=MagicMock())

    from app.models import NormalizedEvent

    assert isinstance(result, NormalizedEvent)
    assert result.raw_event_id == "test-001"
    assert result.event_type in ALLOWED_EVENT_TYPES
    assert 0.0 <= result.confidence <= 1.0


def test_duplicate_reuses_existing_normalized_event():
    reused = NormalizedEvent(
        raw_event_id="test-001",
        event_type="monetary_tightening",
        policy_domain="monetary",
        risk_signal="risk_off",
        rate_signal="tightening",
        geo_signal="none",
        sector_impacts={"Finance": -1},
        sentiment="negative",
        rationale="Fed held rates at 5.25% in 2024, reinforcing restrictive policy transmission.",
        channels=["risk_off", "rate_tightening"],
        confidence=0.85,
        regime={"risk_sentiment": "risk_off", "volatility": "elevated", "liquidity": "tight"},
        baseline={},
    )

    with patch("app.llm.normalize._reuse_duplicate_normalization", return_value=reused):
        with patch("app.llm.normalize._log_eval"):
            result = normalize_event(_make_raw_event(), client=MagicMock())

    assert result.raw_event_id == "test-001"
    assert result.event_type == "monetary_tightening"
