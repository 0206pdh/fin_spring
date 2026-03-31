"""Seed 25 historical macro events into raw_events + seed_events.

Usage:
    python -m app.scripts.seed

Both tables are populated so:
- raw_events → pipeline can normalize + score them
- seed_events → seed_replay_job can replay them for the demo
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.store.db import get_db

logger = logging.getLogger("app.scripts.seed")

# ---------------------------------------------------------------------------
# Historical macro events
# ---------------------------------------------------------------------------

EVENTS: list[dict] = [
    {
        "title": "Fed hikes rates 75bp in largest move since 1994",
        "url": "https://www.bbc.com/news/business/fed-hike-75bp-2022",
        "published_at": "2022-06-15T18:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Federal Reserve raises benchmark rate by 75 basis points to combat inflation."}},
    },
    {
        "title": "Russia invades Ukraine — global markets plunge",
        "url": "https://www.bbc.com/news/world/ukraine-invasion-2022",
        "published_at": "2022-02-24T06:00:00Z",
        "sector": "geopolitics",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "details": {"summary": "Russia launches full-scale invasion of Ukraine triggering oil spike and market panic."}},
    },
    {
        "title": "SVB collapses in largest US bank failure since 2008",
        "url": "https://www.bbc.com/news/business/svb-collapse-2023",
        "published_at": "2023-03-10T20:00:00Z",
        "sector": "corporate",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Silicon Valley Bank fails after run on deposits, FDIC takes over."}},
    },
    {
        "title": "China locks down Shanghai for COVID — supply chains disrupted",
        "url": "https://www.bbc.com/news/world/shanghai-lockdown-2022",
        "published_at": "2022-04-01T10:00:00Z",
        "sector": "geopolitics",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "details": {"summary": "Shanghai enters strict lockdown affecting factories and global supply chains."}},
    },
    {
        "title": "UK mini-budget triggers pound to record low against dollar",
        "url": "https://www.bbc.com/news/business/uk-mini-budget-2022",
        "published_at": "2022-09-23T12:00:00Z",
        "sector": "policy",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/politics/rss.xml",
                    "details": {"summary": "Chancellor Kwarteng unveils unfunded tax cuts, pound falls to all-time low vs USD."}},
    },
    {
        "title": "Fed pauses rate hikes as inflation cools toward 3%",
        "url": "https://www.bbc.com/news/business/fed-pause-2023",
        "published_at": "2023-06-14T18:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Federal Reserve skips rate increase for first time in over a year as inflation declines."}},
    },
    {
        "title": "OPEC+ cuts oil output by 1 million barrels per day",
        "url": "https://www.bbc.com/news/business/opec-cut-2023",
        "published_at": "2023-04-02T14:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Saudi Arabia leads surprise OPEC+ production cut, crude oil jumps 6%."}},
    },
    {
        "title": "US CPI hits 9.1% — highest inflation in 40 years",
        "url": "https://www.bbc.com/news/business/us-cpi-9pct-2022",
        "published_at": "2022-07-13T12:30:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "US consumer prices rise 9.1% year-on-year, stoking fears of further aggressive Fed tightening."}},
    },
    {
        "title": "Credit Suisse rescued by UBS in emergency takeover",
        "url": "https://www.bbc.com/news/business/credit-suisse-ubs-2023",
        "published_at": "2023-03-19T08:00:00Z",
        "sector": "corporate",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Swiss authorities broker emergency buyout of Credit Suisse by UBS for CHF 3bn."}},
    },
    {
        "title": "ECB raises rates 50bp — first hike in 11 years",
        "url": "https://www.bbc.com/news/business/ecb-hike-2022",
        "published_at": "2022-07-21T12:15:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "European Central Bank raises rates for the first time since 2011 to fight record eurozone inflation."}},
    },
    {
        "title": "China ends zero-COVID, reopens borders after 3 years",
        "url": "https://www.bbc.com/news/world/china-reopens-2023",
        "published_at": "2023-01-08T06:00:00Z",
        "sector": "geopolitics",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "details": {"summary": "China scraps quarantine requirements and reopens international borders boosting global growth outlook."}},
    },
    {
        "title": "US debt ceiling deal reached, default averted",
        "url": "https://www.bbc.com/news/world/us-debt-ceiling-2023",
        "published_at": "2023-06-01T22:00:00Z",
        "sector": "policy",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/politics/rss.xml",
                    "details": {"summary": "Biden signs Fiscal Responsibility Act suspending US debt limit and avoiding historic default."}},
    },
    {
        "title": "ChatGPT reaches 100 million users — AI tech stocks surge",
        "url": "https://www.bbc.com/news/technology/chatgpt-100m-2023",
        "published_at": "2023-02-01T14:00:00Z",
        "sector": "technology",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
                    "details": {"summary": "OpenAI's ChatGPT becomes fastest-growing consumer app ever, sparking rally in AI-related stocks."}},
    },
    {
        "title": "Nvidia posts record revenue on AI chip demand",
        "url": "https://www.bbc.com/news/technology/nvidia-record-2023",
        "published_at": "2023-08-23T20:00:00Z",
        "sector": "technology",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
                    "details": {"summary": "Nvidia Q2 revenue triples year-on-year to $13.5bn, driven by data center GPU demand."}},
    },
    {
        "title": "Hamas attacks Israel — Middle East conflict escalates",
        "url": "https://www.bbc.com/news/world/hamas-attack-israel-2023",
        "published_at": "2023-10-07T08:00:00Z",
        "sector": "geopolitics",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "details": {"summary": "Hamas launches large-scale attack on Israel, killing hundreds. Oil prices and safe-haven assets rise."}},
    },
    {
        "title": "Bank of Japan abandons yield curve control policy",
        "url": "https://www.bbc.com/news/business/boj-ycc-2024",
        "published_at": "2024-03-19T03:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "BOJ ends negative interest rate era and scraps yield curve control, yen strengthens sharply."}},
    },
    {
        "title": "Fed cuts rates 50bp — signals easing cycle has begun",
        "url": "https://www.bbc.com/news/business/fed-cut-50bp-2024",
        "published_at": "2024-09-18T18:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Federal Reserve cuts rates by 50 basis points, largest single cut since 2020 pandemic emergency."}},
    },
    {
        "title": "Trump wins 2024 US election — dollar and yields spike",
        "url": "https://www.bbc.com/news/world/us-election-trump-2024",
        "published_at": "2024-11-06T07:00:00Z",
        "sector": "policy",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/politics/rss.xml",
                    "details": {"summary": "Donald Trump wins US presidential election, markets price in tariffs and higher-for-longer rates."}},
    },
    {
        "title": "US tariffs on China raised to 145% sparking trade war fears",
        "url": "https://www.bbc.com/news/business/us-china-tariffs-145-2025",
        "published_at": "2025-04-09T14:00:00Z",
        "sector": "geopolitics",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "details": {"summary": "White House announces 145% tariff rate on Chinese imports, China retaliates with 84% on US goods."}},
    },
    {
        "title": "UK enters recession — GDP contracts two consecutive quarters",
        "url": "https://www.bbc.com/news/business/uk-recession-2023",
        "published_at": "2024-02-15T09:30:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "UK officially in recession after GDP shrinks in Q3 and Q4 2023, pound weakens."}},
    },
    {
        "title": "TSMC Arizona fab opens — chip reshoring milestone",
        "url": "https://www.bbc.com/news/technology/tsmc-arizona-2024",
        "published_at": "2024-04-26T16:00:00Z",
        "sector": "technology",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
                    "details": {"summary": "TSMC officially opens N4 fab in Phoenix backed by $6.6bn CHIPS Act grants."}},
    },
    {
        "title": "Oil falls below $70 on weakening demand outlook",
        "url": "https://www.bbc.com/news/business/oil-below-70-2023",
        "published_at": "2023-11-15T12:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Brent crude slips under $70 for first time since 2023 on weak Chinese demand and rising US inventories."}},
    },
    {
        "title": "ECB cuts rates for first time since 2019",
        "url": "https://www.bbc.com/news/business/ecb-cut-2024",
        "published_at": "2024-06-06T12:15:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "European Central Bank cuts deposit rate 25bp to 3.75%, beginning its easing cycle as inflation falls."}},
    },
    {
        "title": "DeepSeek R1 released — AI cost shock hits tech stocks",
        "url": "https://www.bbc.com/news/technology/deepseek-r1-2025",
        "published_at": "2025-01-27T10:00:00Z",
        "sector": "technology",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
                    "details": {"summary": "Chinese startup DeepSeek releases R1 model matching GPT-4o at fraction of cost, Nvidia drops 17%."}},
    },
    {
        "title": "Japan yen hits 160 vs dollar — BOJ intervenes",
        "url": "https://www.bbc.com/news/business/yen-160-boj-2024",
        "published_at": "2024-04-29T02:00:00Z",
        "sector": "macro",
        "payload": {"category_url": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "details": {"summary": "Japanese yen weakens to 160 per dollar, triggering suspected BOJ intervention buying yen."}},
    },
]


# ---------------------------------------------------------------------------
# Stable ID (same algorithm as bbc.py)
# ---------------------------------------------------------------------------

def _stable_id(title: str, url: str, published: datetime) -> str:
    raw = f"{title}|{url}|{published.isoformat()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

def _insert_raw_event(conn, event: dict) -> str:
    published = datetime.fromisoformat(event["published_at"].replace("Z", "+00:00"))
    event_id = _stable_id(event["title"], event["url"], published)
    conn.execute(
        """
        INSERT INTO raw_events (id, title, url, published_at, sector, source, payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            event_id,
            event["title"],
            event["url"],
            published,
            event["sector"],
            "seed",
            json.dumps(event["payload"]),
        ),
    )
    return event_id


def _insert_seed_event(conn, event: dict, event_id: str) -> None:
    published = datetime.fromisoformat(event["published_at"].replace("Z", "+00:00"))
    conn.execute(
        """
        INSERT INTO seed_events (id, title, url, published_at, sector, source, payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            event_id,
            event["title"],
            event["url"],
            published,
            event["sector"],
            "seed",
            json.dumps(event["payload"]),
        ),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    inserted_raw = 0
    inserted_seed = 0

    with get_db() as conn:
        for event in EVENTS:
            event_id = _insert_raw_event(conn, event)
            inserted_raw += 1
            _insert_seed_event(conn, event, event_id)
            inserted_seed += 1
        conn.commit()

    logger.info("Seeded %d raw_events, %d seed_events", inserted_raw, inserted_seed)
    logger.info("Run the pipeline to normalize + score: POST /pipeline/run")


if __name__ == "__main__":
    run()
