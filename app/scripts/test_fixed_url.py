from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import requests

from app.config import settings

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.llm.normalize import normalize_event
from app.models import RawEvent

TEST_URL = "https://apnews.com/article/banks-trump-jamie-dimon-jpmorgan-credit-cards-bny-b4f31993a64c31687c91f17beab0a98a"


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return unescape(text)


def _fetch_url_text(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    return _strip_html(response.text)


def main() -> None:
    text = _fetch_url_text(TEST_URL)
    published = datetime.now(tz=timezone.utc)
    event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{TEST_URL}|{published.isoformat()}"))
    raw = RawEvent(
        id=event_id,
        title="Jpmorgan CFO warns credit card rate cap could hurt US consumers economy",
        url=TEST_URL,
        published_at=published,
        sector="Financials",
        source="test",
        payload={
            "category_url": "https://www.reuters.com/business/finance/",
            "details": {"text": text},
        },
    )
    normalized = normalize_event(raw)
    print(normalized.model_dump())


if __name__ == "__main__":
    main()
