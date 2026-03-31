from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from html import unescape
from typing import Any
from xml.etree import ElementTree

import requests
from dateutil import parser as date_parser

from app.models import RawEvent

logger = logging.getLogger("app.ingest")

BBC_FEEDS = {
    "top_stories": "http://feeds.bbci.co.uk/news/rss.xml",
    "business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "world": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "uk": "http://feeds.bbci.co.uk/news/uk/rss.xml",
    "politics": "http://feeds.bbci.co.uk/news/politics/rss.xml",
    "health": "http://feeds.bbci.co.uk/news/health/rss.xml",
    "science_environment": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
}

SECTOR_MAP = {
    "top_stories": "macro",
    "business": "corporate",
    "technology": "technology",
    "world": "geopolitics",
    "uk": "policy",
    "politics": "policy",
    "health": "healthcare",
    "science_environment": "industrials",
}


def get_categories() -> list[dict[str, str]]:
    return [{"sector": key, "url": url} for key, url in BBC_FEEDS.items()]


def fetch_raw_events(category: str | None = None, limit_per_category: int = 10) -> list[RawEvent]:
    events: list[RawEvent] = []
    feeds = _filtered_feeds(category)
    for key, feed_url in feeds.items():
        try:
            rss_xml = _fetch_text(feed_url)
        except requests.RequestException as exc:
            logger.warning("BBC feed fetch failed %s error=%s", feed_url, exc)
            continue
        items = _parse_rss_items(rss_xml)[:limit_per_category]
        logger.info("BBC feed %s items=%s", key, len(items))
        for item in items:
            url = item.get("url", "")
            title = item.get("title", "")
            published_at = item.get("published_at", "")
            summary = item.get("summary", "")
            if not url:
                continue
            published = _parse_datetime(published_at) or datetime.utcnow()
            event_id = _stable_id(title or "", url, published)
            raw_payload = {
                "category_url": feed_url,
                "item": {"title": title, "url": url, "published_at": published_at},
                "details": {"title": title, "summary": summary, "text": ""},
            }
            events.append(
                RawEvent(
                    id=event_id,
                    title=(title or _title_from_url(url)).strip(),
                    url=url,
                    published_at=published,
                    sector=SECTOR_MAP.get(key, key),
                    source="bbc",
                    payload=raw_payload,
                )
            )
    return events


def fetch_article_details(url: str) -> dict[str, str]:
    article_html = _fetch_text(url)
    title, published_at, body, summary = _extract_article(article_html)
    return {
        "title": title,
        "published_at": published_at,
        "summary": summary,
        "text": body,
    }


def _filtered_feeds(category: str | None) -> dict[str, str]:
    if not category:
        return BBC_FEEDS
    needle = _normalize_token(category)
    for key, url in BBC_FEEDS.items():
        if _normalize_token(key) == needle:
            return {key: url}
    return {}


def _fetch_text(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    return response.text


def _parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return items
    for item in root.findall(".//item"):
        title = _text_or_empty(item.find("title"))
        link = _text_or_empty(item.find("link"))
        pub_date = _text_or_empty(item.find("pubDate"))
        description = _text_or_empty(item.find("description"))
        summary = _strip_html(description)
        if link:
            items.append(
                {
                    "title": title,
                    "url": link,
                    "published_at": pub_date,
                    "summary": summary,
                }
            )
    return items


def _text_or_empty(node: ElementTree.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _extract_article(html: str) -> tuple[str, str, str, str]:
    title = _extract_meta(html, "property", "og:title") or _extract_title(html)
    summary = _extract_meta(html, "property", "og:description") or ""
    published = (
        _extract_meta(html, "property", "article:published_time")
        or _extract_meta(html, "name", "pubdate")
        or ""
    )
    body = _extract_paragraphs(html)
    if not body:
        body = summary
    return title, published, body, summary


def _extract_meta(html: str, attr: str, value: str) -> str:
    pattern = rf'<meta[^>]+{attr}="{re.escape(value)}"[^>]+content="([^"]+)"'
    match = re.search(pattern, html, flags=re.IGNORECASE)
    return unescape(match.group(1)).strip() if match else ""


def _extract_title(html: str) -> str:
    match = re.search(r"<title>([^<]+)</title>", html, flags=re.IGNORECASE)
    return unescape(match.group(1)).strip() if match else ""


def _extract_paragraphs(html: str) -> str:
    texts = []
    for match in re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL):
        cleaned = _strip_html(match)
        if cleaned:
            texts.append(cleaned)
    return " ".join(texts)[:4000]


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return unescape(text)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.parse(str(value))
    except Exception:
        return None


def _stable_id(title: str, url: str, published: datetime) -> str:
    raw = f"{title}|{url}|{published.isoformat()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _title_from_url(url: str) -> str:
    if not url:
        return ""
    slug = url.rstrip("/").split("/")[-1]
    if not slug:
        return ""
    slug = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", slug)
    return slug.replace("-", " ").strip().title()
