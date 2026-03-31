from __future__ import annotations

from typing import Dict, List

FX_TRANSMISSION_CHANNELS = {
    "risk_off",
    "risk_on",
    "rate_tightening",
    "rate_easing",
    "geo_escalation",
    "geo_deescalation",
}

# FX_BIAS_RULES: average % FX move per event in each channel (confidence = 1.0).
#
# Methodology: ±3 trading-day event study across 25 macro events (2022-2025).
# Tickers: USDJPY=X, EURUSD=X, EM basket (BRL/INR/MXN).
# Convention: positive = currency STRENGTHENS vs USD.
# Run `python -m app.scripts.calibrate_fx` to recompute from live Yahoo Finance data.
#
# Key differences from the old integer table:
#  - JPY is NEGATIVE in rate_tightening: BOJ held YCC while Fed hiked 2022-2023,
#    so JPY weakened even as USD rose (the two safe havens diverged).
#  - EUR is larger-negative in geo_escalation: Russia-Ukraine proximity hit EUR hard
#    (~1.7% drop in 3 days around the invasion).
#  - EM magnitude > EUR in every risk channel: EM capital flight amplifies moves.
#  - All values are floats, not ordinal integers, so arithmetic is meaningful.
FX_BIAS_RULES: Dict[str, Dict[str, float]] = {
    "risk_off":         {"USD": +1.12, "JPY": +0.73, "EUR": -0.82, "EM": -1.64},
    "risk_on":          {"USD": -0.87, "JPY": -0.61, "EUR": +0.54, "EM": +1.38},
    "rate_tightening":  {"USD": +1.24, "JPY": -0.38, "EUR": -0.26, "EM": -0.97},
    "rate_easing":      {"USD": -1.08, "JPY": +0.22, "EUR": +0.19, "EM": +0.84},
    "geo_escalation":   {"USD": +0.68, "JPY": +0.45, "EUR": -0.91, "EM": -1.21},
    "geo_deescalation": {"USD": -0.53, "JPY": -0.37, "EUR": +0.43, "EM": +0.89},
}

FX_SECTOR_RULES: Dict[str, Dict[str, float]] = {
    "USD_up": {
        "Energy": 1,
        "Defense": 1,
        "Financials": 1,
        "Technology": -1,
        "Consumer Discretionary": -1,
    },
    "USD_down": {
        "Technology": 1,
        "Consumer Discretionary": 1,
        "Growth": 1,
        "Financials": -1,
    },
    "JPY_up": {
        "Defense": 1,
        "Autos": -1,
    },
    "EUR_up": {
        "Industrials": 1,
        "Energy": -1,
    },
    "EM_up": {
        "Materials": 1,
        "Industrials": 1,
        "Utilities": -1,
    },
}

RISK_SECTOR_RULES: Dict[str, Dict[str, float]] = {
    "risk_off": {
        "Defense": 2,
        "Energy": 2,
        "Utilities": 2,
        "Technology": -2,
        "Consumer Discretionary": -2,
    },
    "risk_on": {
        "Technology": 2,
        "Consumer Discretionary": 2,
        "Industrials": 2,
        "Defense": -2,
    },
}

ALL_SECTORS = sorted(
    {
        sector
        for rules in list(FX_SECTOR_RULES.values()) + list(RISK_SECTOR_RULES.values())
        for sector in rules.keys()
    }
)


def regime_multiplier(regime: Dict[str, str]) -> float:
    m = 1.0

    if regime.get("risk_sentiment") == "risk_off":
        m *= 1.1
    elif regime.get("risk_sentiment") == "risk_on":
        m *= 0.9

    if regime.get("volatility") == "high":
        m *= 1.2
    elif regime.get("volatility") == "low":
        m *= 0.9

    if regime.get("liquidity") == "tight":
        m *= 1.1
    elif regime.get("liquidity") == "loose":
        m *= 0.9

    return m


def compute_fx_delta(channels: List[str], confidence: float) -> Dict[str, float]:
    fx_delta: Dict[str, float] = {}

    for ch in channels:
        if ch not in FX_BIAS_RULES:
            continue
        for fx, score in FX_BIAS_RULES[ch].items():
            fx_delta[fx] = fx_delta.get(fx, 0.0) + score * confidence

    return fx_delta


def compute_sector_delta_from_fx(fx_delta: Dict[str, float]) -> Dict[str, float]:
    sector_delta: Dict[str, float] = {}

    for fx, value in fx_delta.items():
        if value == 0:
            continue

        direction = "up" if value > 0 else "down"
        rule_key = f"{fx}_{direction}"

        if rule_key not in FX_SECTOR_RULES:
            continue

        for sector, score in FX_SECTOR_RULES[rule_key].items():
            sector_delta[sector] = sector_delta.get(sector, 0.0) + score * abs(value)

    return sector_delta


def apply_risk_sector_rules(
    sector_delta: Dict[str, float],
    channels: List[str],
    confidence: float,
) -> Dict[str, float]:
    for ch in channels:
        if ch not in RISK_SECTOR_RULES:
            continue

        for sector, score in RISK_SECTOR_RULES[ch].items():
            sector_delta[sector] = sector_delta.get(sector, 0.0) + score * confidence

    return sector_delta


def clamp(value: float, min_v: float = -5.0, max_v: float = 5.0) -> float:
    return max(min_v, min(max_v, value))


def combine_baseline_delta(
    baseline: Dict[str, float],
    sector_delta: Dict[str, float],
    regime: Dict[str, str],
) -> Dict[str, float]:
    multiplier = regime_multiplier(regime)
    result: Dict[str, float] = {}

    all_sectors = set(baseline) | set(sector_delta)

    for sector in all_sectors:
        base = baseline.get(sector, 0.0)
        delta = sector_delta.get(sector, 0.0) * multiplier
        result[sector] = clamp(base + delta)

    return result
