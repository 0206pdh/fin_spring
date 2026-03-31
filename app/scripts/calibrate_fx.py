"""Calibrate FX_BIAS_RULES weights from real Yahoo Finance market data.

Methodology
-----------
For each of the 25 historical seed events:
1. Identify the event date and its expected transmission channels.
2. Fetch OHLCV from Yahoo Finance for USD/JPY, EUR/USD, and three EM proxies.
3. Compute the ±3 trading-day % change centred on the event date.
   - "pre" = mean of 3 trading days before
   - "post" = mean of 3 trading days after
   - delta = (post - pre) / pre * 100
4. Normalise all deltas to the same convention:
   positive = currency STRENGTHENS vs USD.
5. Group events by channel, average the FX deltas per channel.
6. Print the calibrated FX_BIAS_RULES dict ready to paste into weights.py.

Usage
-----
    pip install yfinance
    python -m app.scripts.calibrate_fx

Note: Yahoo Finance rate-limits aggressive requests.
      The script caches data in memory; a full run takes ~30 seconds.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# ---------------------------------------------------------------------------
# Seed events with channel annotations
# ---------------------------------------------------------------------------
# Each entry: (iso_date, [channels])
# Channels must match FX_TRANSMISSION_CHANNELS in weights.py.

SEED_EVENTS: list[tuple[str, list[str]]] = [
    ("2022-06-15", ["rate_tightening"]),                    # Fed +75bp
    ("2022-02-24", ["risk_off", "geo_escalation"]),         # Russia invades Ukraine
    ("2023-03-10", ["risk_off"]),                           # SVB collapse
    ("2022-04-01", ["risk_off"]),                           # Shanghai lockdown
    ("2022-09-23", ["risk_off"]),                           # UK mini-budget
    ("2023-06-14", ["rate_easing"]),                        # Fed pauses
    ("2023-04-02", ["risk_off"]),                           # OPEC+ cut
    ("2022-07-13", ["rate_tightening"]),                    # US CPI 9.1%
    ("2023-03-19", ["risk_off"]),                           # Credit Suisse → UBS
    ("2022-07-21", ["rate_tightening"]),                    # ECB +50bp
    ("2023-01-08", ["risk_on"]),                            # China reopens
    ("2023-06-01", ["risk_on"]),                            # US debt ceiling resolved
    ("2023-02-01", ["risk_on"]),                            # ChatGPT 100M users
    ("2023-08-23", ["risk_on"]),                            # Nvidia record revenue
    ("2023-10-07", ["risk_off", "geo_escalation"]),         # Hamas attacks Israel
    ("2024-03-19", ["rate_tightening"]),                    # BOJ abandons YCC
    ("2024-09-18", ["rate_easing"]),                        # Fed cuts 50bp
    ("2024-11-06", ["risk_off", "geo_escalation"]),         # Trump wins
    ("2025-04-09", ["risk_off", "geo_escalation"]),         # US tariffs 145%
    ("2024-02-15", ["risk_off"]),                           # UK recession
    ("2024-04-26", ["risk_on"]),                            # TSMC Arizona opens
    ("2023-11-15", ["risk_on"]),                            # Oil below $70
    ("2024-06-06", ["rate_easing"]),                        # ECB cuts
    ("2025-01-27", ["risk_off"]),                           # DeepSeek shock
    ("2024-04-29", ["geo_escalation"]),                     # Yen 160 / BOJ intervenes
]

# ---------------------------------------------------------------------------
# Yahoo Finance tickers
# Convention: all tickers quoted as units of foreign currency per 1 USD.
# % change positive = USD strengthened (foreign currency weakened).
# We flip signs at the end so positive = foreign currency strengthened.
# ---------------------------------------------------------------------------

TICKERS = {
    "JPY": "USDJPY=X",      # USD per JPY in Yahoo → actually JPY per USD
    "EUR": "EURUSD=X",      # EUR per USD → need to invert
    "EM_BRL": "USDBRL=X",
    "EM_INR": "USDINR=X",
    "EM_MXN": "USDMXN=X",
}


def _fetch_close(ticker: str, start: str, end: str) -> dict[str, float]:
    """Return {date_str: close_price} for the given ticker and date range."""
    data = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if data.empty:
        return {}
    close = data["Close"]
    # yfinance ≥ 0.2.x returns a DataFrame even for single tickers — flatten to Series
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    result: dict[str, float] = {}
    for ts, val in close.items():
        result[str(ts.date())] = float(val)
    return result


def _mean_close(prices: dict[str, float], anchor: datetime, direction: int) -> float | None:
    """Average close price over `direction` * 3 trading days relative to anchor.

    direction = -1 → 3 days before anchor
    direction = +1 → 3 days after anchor
    """
    collected: list[float] = []
    day = anchor
    while len(collected) < 3:
        day += timedelta(days=direction)
        key = str(day.date())
        if key in prices:
            collected.append(prices[key])
        if abs((day - anchor).days) > 15:
            break
    return sum(collected) / len(collected) if collected else None


def _fx_delta(event_date: str, prices: dict[str, float]) -> float | None:
    """Return % change (post - pre) / pre for the event, in USD-strengthens = positive convention."""
    anchor = datetime.fromisoformat(event_date).replace(tzinfo=timezone.utc)
    pre = _mean_close(prices, anchor, -1)
    post = _mean_close(prices, anchor, +1)
    if pre is None or post is None or pre == 0:
        return None
    return (post - pre) / pre * 100.0


def _load_all_prices() -> dict[str, dict[str, float]]:
    """Bulk-download price history for all tickers at once."""
    dates = [datetime.fromisoformat(d) for d, _ in SEED_EVENTS]
    global_start = (min(dates) - timedelta(days=30)).strftime("%Y-%m-%d")
    global_end   = (max(dates) + timedelta(days=30)).strftime("%Y-%m-%d")

    prices: dict[str, dict[str, float]] = {}
    for name, ticker in TICKERS.items():
        logger.info("  downloading %s (%s) …", name, ticker)
        prices[name] = _fetch_close(ticker, global_start, global_end)
    return prices


def _compute_event_fx(prices: dict[str, dict[str, float]]) -> list[dict]:
    """For every seed event, return {channels, JPY, EUR, EM} deltas."""
    records = []
    for date_str, channels in SEED_EVENTS:
        jpy_raw   = _fx_delta(date_str, prices["JPY"])
        eur_raw   = _fx_delta(date_str, prices["EUR"])
        brl_raw   = _fx_delta(date_str, prices["EM_BRL"])
        inr_raw   = _fx_delta(date_str, prices["EM_INR"])
        mxn_raw   = _fx_delta(date_str, prices["EM_MXN"])

        em_vals = [v for v in [brl_raw, inr_raw, mxn_raw] if v is not None]
        em_raw  = sum(em_vals) / len(em_vals) if em_vals else None

        if jpy_raw is None or eur_raw is None or em_raw is None:
            logger.warning("  incomplete data for %s — skipping", date_str)
            continue

        # Flip signs: positive now means foreign currency STRENGTHENS vs USD.
        # USDJPY=X: higher price = JPY weakens → flip sign for JPY
        # EURUSD=X: higher price = EUR strengthens → keep sign but note it's already inverted
        #   (Yahoo EURUSD=X gives EUR per USD? Actually Yahoo gives it as EUR per 1 USD...
        #    No: EURUSD=X = how many USD per 1 EUR = EUR strengthening means price rises.)
        #    So EURUSD % change positive = EUR strengthens = already correct direction.
        # USD direction: if JPY weakens (jpy_raw > 0), USD strengthened.
        #   USD_delta = average of jpy_raw, -eur_raw, em_raw  (all in "USD strengthens" = positive)
        #   But for FX_BIAS_RULES we want USD in "USD strengthens = positive", others in "foreign strengthens = positive"

        jpy_delta = -jpy_raw                    # flip: positive = JPY strengthens
        eur_delta = eur_raw                     # EUR/USD already: positive = EUR strengthens
        em_delta  = -em_raw                     # flip: positive = EM strengthens

        # USD proxy: use DXY-equivalent = average of (-jpy_delta, -eur_delta, -em_delta)
        # i.e. when other currencies weaken, USD strengthened
        usd_delta = (-jpy_delta + (-eur_delta) + (-em_delta)) / 3.0

        records.append({
            "date": date_str,
            "channels": channels,
            "USD": round(usd_delta, 4),
            "JPY": round(jpy_delta, 4),
            "EUR": round(eur_delta, 4),
            "EM":  round(em_delta, 4),
        })
        logger.info(
            "  %s  USD:%+.2f  JPY:%+.2f  EUR:%+.2f  EM:%+.2f  channels=%s",
            date_str, usd_delta, jpy_delta, eur_delta, em_delta, channels,
        )
    return records


def _calibrate(records: list[dict]) -> dict[str, dict[str, float]]:
    """Average FX deltas per channel, weighted by number of events."""
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        for ch in rec["channels"]:
            for ccy in ("USD", "JPY", "EUR", "EM"):
                buckets[ch][ccy].append(rec[ccy])

    calibrated: dict[str, dict[str, float]] = {}
    for ch, ccy_lists in buckets.items():
        calibrated[ch] = {
            ccy: round(sum(vals) / len(vals), 4)
            for ccy, vals in ccy_lists.items()
        }
    return calibrated


def _print_weights(calibrated: dict[str, dict[str, float]]) -> None:
    CHANNEL_ORDER = [
        "risk_off", "risk_on",
        "rate_tightening", "rate_easing",
        "geo_escalation", "geo_deescalation",
    ]
    print("\n" + "=" * 60)
    print("CALIBRATED FX_BIAS_RULES — paste into app/rules/weights.py")
    print("=" * 60)
    print("FX_BIAS_RULES: Dict[str, Dict[str, float]] = {")
    for ch in CHANNEL_ORDER:
        if ch not in calibrated:
            print(f"    # {ch}: no data")
            continue
        w = calibrated[ch]
        print(
            f'    "{ch}": '
            f'{{"USD": {w.get("USD", 0.0):+.4f}, '
            f'"JPY": {w.get("JPY", 0.0):+.4f}, '
            f'"EUR": {w.get("EUR", 0.0):+.4f}, '
            f'"EM": {w.get("EM", 0.0):+.4f}}},'
        )
    print("}")
    print("\nNote: units = average % FX move per event in this channel (confidence=1.0)")
    print("Multiply by confidence at runtime → realistic magnitude even for weak signals.")


def run() -> None:
    logger.info("Downloading FX history from Yahoo Finance …")
    prices = _load_all_prices()

    logger.info("\nComputing per-event FX deltas (±3 trading days) …")
    records = _compute_event_fx(prices)
    logger.info("\n%d / %d events have complete FX data.", len(records), len(SEED_EVENTS))

    calibrated = _calibrate(records)
    _print_weights(calibrated)


if __name__ == "__main__":
    run()
