"""EVAL tests — LLM rationale quality checks (requires OPENAI_API_KEY).

These tests call the real LLM and verify the rationale reads like analyst prose.
Skip automatically when no API key is set.

Run: pytest tests/test_rationale_quality.py -v -m eval
     or: OPENAI_API_KEY=sk-... pytest tests/test_rationale_quality.py -v
"""
from __future__ import annotations

import os
import re

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping LLM eval tests",
)

ANALYST_VOCABULARY = {
    "headwind", "tailwind", "pressure", "revision", "guidance",
    "magnitude", "elevated", "uncertainty", "repricing", "hawkish",
    "dovish", "tightening", "easing", "transmission", "spread",
    "contraction", "expansion", "consensus", "print", "overshoot",
}

FORBIDDEN_PHRASES = [
    "sector pressure detected",
    "market impact expected",
    "could affect markets",
    "may lead to volatility",
    "uncertainty increases",
]


def _get_sample_events():
    """Return a small list of realistic event inputs for eval."""
    return [
        {
            "title": "Federal Reserve holds rates at 5.25-5.50%, signals two cuts in 2024",
            "sector": "Finance",
            "published_at": "2024-03-20T18:00:00Z",
            "details": "The Federal Open Market Committee voted unanimously to maintain the target range "
                       "for the federal funds rate at 5.25-5.50%. Updated dot-plot projections show "
                       "the median Fed funds rate falling to 4.6% by end-2024, down from 5.1% in December.",
        },
        {
            "title": "EU announces $1.2B fine on Apple for App Store antitrust violations",
            "sector": "Technology",
            "published_at": "2024-03-04T10:30:00Z",
            "details": "European regulators imposed a record 1.84 billion euro fine on Apple Inc "
                       "for abusing its dominant position in the market for the distribution of "
                       "music streaming apps to iPhone and iPad users.",
        },
        {
            "title": "US CPI rises 3.4% in January, above 3.2% consensus forecast",
            "sector": "Economics",
            "published_at": "2024-02-13T13:30:00Z",
            "details": "The Consumer Price Index rose 3.4% year-over-year in January 2024, "
                       "exceeding the 3.2% consensus estimate. Core CPI ex-food and energy "
                       "was 3.9%, also above forecast. Markets repriced Fed rate cut expectations.",
        },
    ]


@pytest.fixture(scope="module")
def rationales():
    """Run normalize_event() on sample events and collect rationales."""
    from unittest.mock import patch
    from app.models import RawEvent
    from app.llm.normalize import normalize_event

    results = []
    for sample in _get_sample_events():
        raw = RawEvent(
            id=f"eval-{hash(sample['title']) % 10000:04d}",
            title=sample["title"],
            url="https://example.com",
            published_at=sample["published_at"],
            sector=sample["sector"],
            source="eval",
            payload={"details": {"summary": sample["details"]}},
        )
        try:
            event = normalize_event(raw)
            results.append(event.rationale)
        except Exception as exc:
            results.append(f"ERROR: {exc}")
    return results


def test_rationale_contains_number(rationales):
    """Every rationale must contain at least one numeric token (%, $, bps, or year)."""
    number_pattern = re.compile(r"\d+")
    for rationale in rationales:
        if rationale.startswith("ERROR"):
            pytest.skip(f"LLM call failed: {rationale}")
        assert number_pattern.search(rationale), (
            f"Rationale missing numeric token: {rationale!r}"
        )


def test_rationale_not_generic(rationales):
    """Rationale must not contain any forbidden generic phrases."""
    for rationale in rationales:
        if rationale.startswith("ERROR"):
            pytest.skip(f"LLM call failed: {rationale}")
        for phrase in FORBIDDEN_PHRASES:
            assert phrase.lower() not in rationale.lower(), (
                f"Forbidden phrase '{phrase}' found in rationale: {rationale!r}"
            )


def test_rationale_analyst_vocabulary(rationales):
    """Each rationale should contain at least one analyst-vocabulary term."""
    for rationale in rationales:
        if rationale.startswith("ERROR"):
            pytest.skip(f"LLM call failed: {rationale}")
        rationale_lower = rationale.lower()
        matched = [term for term in ANALYST_VOCABULARY if term in rationale_lower]
        assert len(matched) >= 1, (
            f"Rationale lacks analyst vocabulary. Got: {rationale!r}\n"
            f"Expected one of: {sorted(ANALYST_VOCABULARY)}"
        )
