from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
import re
from typing import Any

import requests
from dateutil import parser as date_parser

from app.config import settings
from app.models import RawEvent

logger = logging.getLogger("app.ingest")

DEFAULT_ENDPOINTS = [
    {
        "sector": "Financials",
        "path": "/category",
        "params": {"url": "https://www.reuters.com/business/finance/"},
        "details": True,
        "details_limit": 10,
        "source": "rapidapi",
        "title_path": "articles[].title",
        "url_path": "articles[].url",
        "time_path": "articles[].published_at",
    },
    {
        "sector": "Aerospace&Defense",
        "path": "/category",
        "params": {"url": "https://www.reuters.com/business/aerospace-defense/"},
        "details": True,
        "details_limit": 10,
        "source": "rapidapi",
        "title_path": "articles[].title",
        "url_path": "articles[].url",
        "time_path": "articles[].published_at",
    },
    {
        "sector": "Transportation",
        "path": "/category",
        "params": {"url": "https://www.reuters.com/business/autos-transportation/"},
        "details": True,
        "details_limit": 10,
        "source": "rapidapi",
        "title_path": "articles[].title",
        "url_path": "articles[].url",
        "time_path": "articles[].published_at",
    },
    {
        "sector": "Healthcare",
        "path": "/category",
        "params": {"url": "https://www.reuters.com/business/healthcare-pharmaceuticals/"},
        "details": True,
        "details_limit": 10,
        "source": "rapidapi",
        "title_path": "articles[].title",
        "url_path": "articles[].url",
        "time_path": "articles[].published_at",
    },
]


def _load_endpoints() -> list[dict[str, Any]]:
    if settings.rapidapi_endpoints_json:
        return json.loads(settings.rapidapi_endpoints_json)
    return DEFAULT_ENDPOINTS


def _dig(obj: Any, path: str) -> list[Any]:
    # Path format: "items[].field" or "items[].nested.field"
    if not path:
        return []
    parts = path.split(".")
    current = [obj]
    for part in parts:
        if part.endswith("[]"):
            key = part[:-2]
            next_level = []
            for item in current:
                if isinstance(item, dict) and key in item and isinstance(item[key], list):
                    next_level.extend(item[key])
            current = next_level
        else:
            next_level = []
            for item in current:
                if isinstance(item, dict) and part in item:
                    next_level.append(item[part])
            current = next_level
    return current


def _zip_fields(payload: dict[str, Any], title_path: str, url_path: str, time_path: str) -> list[dict[str, Any]]:
    titles = _dig(payload, title_path)
    urls = _dig(payload, url_path)
    times = _dig(payload, time_path)

    size = min(len(titles), len(urls), len(times))
    items = []
    for i in range(size):
        items.append({
            "title": titles[i],
            "url": urls[i],
            "published_at": times[i],
        })
    return items


def fetch_raw_events(category: str | None = None, limit_per_category: int = 10) -> list[RawEvent]:
    if not settings.rapidapi_key or not settings.rapidapi_host or not settings.rapidapi_base_url:
        raise ValueError("RapidAPI settings are missing. Set FIM_RAPIDAPI_KEY/HOST/BASE_URL.")

    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": settings.rapidapi_host,
    }

    events: list[RawEvent] = []
    for endpoint in _filtered_endpoints(category):
        url = f"{settings.rapidapi_base_url}{endpoint['path']}"
        params = endpoint.get("params")
        logger.info("RapidAPI request: %s params=%s", url, params)
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=settings.rapidapi_timeout_sec,
        )
        logger.info("RapidAPI status: %s %s", response.status_code, response.reason)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            snippet = response.text[:500] if response.text else ""
            logger.error("RapidAPI non-JSON response (first 500 chars): %s", snippet)
            raise ValueError("RapidAPI returned non-JSON response.")

        items = _extract_items(payload, endpoint)[:limit_per_category]
        _log_payload_summary(endpoint.get("sector", "unknown"), payload, items)
        details_count = 0
        for item in items:
            details: dict[str, Any] = {}
            if endpoint.get("details") and details_count < int(endpoint.get("details_limit", 0) or 0):
                details = _fetch_details(headers, item.get("url"))
                item = _merge_details(item, details)
                details_count += 1
            published = _parse_datetime(item.get("published_at"))
            if not published:
                published = datetime.utcnow()
                logger.warning("Missing published_at, using ingest time for %s", item.get("url"))
            event_id = _stable_id(item.get("title", ""), item.get("url", ""), published)
            raw_payload = {
                "category_url": (params or {}).get("url", ""),
                "item": item,
                "details": details,
                "published_at_fallback": not bool(item.get("published_at")),
            }
            events.append(
                RawEvent(
                    id=event_id,
                    title=str(item.get("title", "")).strip(),
                    url=str(item.get("url", "")).strip(),
                    published_at=published,
                    sector=endpoint["sector"],
                    source=endpoint.get("source", "rapidapi"),
                    payload=raw_payload,
                )
            )
    return events


def _log_payload_summary(sector: str, payload: Any, items: list[dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        keys = list(payload.keys())
        logger.debug("RapidAPI payload keys (%s): %s", sector, keys)
    else:
        logger.debug("RapidAPI payload type (%s): %s", sector, type(payload))

    logger.info("RapidAPI response: %s items=%s", sector, len(items))
    if items:
        sample = items[0]
        logger.debug(
            "RapidAPI sample item (%s): title=%s url=%s published_at=%s",
            sector,
            sample.get("title"),
            sample.get("url"),
            sample.get("published_at"),
        )


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


def _extract_items(payload: Any, endpoint: dict[str, Any]) -> list[dict[str, Any]]:
    category_url = str((endpoint.get("params") or {}).get("url") or "")
    if isinstance(payload, list):
        items = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            url = entry.get("link") or entry.get("url")
            if not url:
                continue
            if category_url and not str(url).startswith(category_url):
                continue
            title = entry.get("title") or entry.get("headline") or _title_from_url(str(url))
            published = entry.get("published_at") or entry.get("publishedAt") or _date_from_url(str(url))
            items.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": published,
                }
            )
        return items

    title_path = endpoint.get("title_path", "")
    url_path = endpoint.get("url_path", "")
    time_path = endpoint.get("time_path", "")
    items = _zip_fields(payload, title_path, url_path, time_path)
    if category_url:
        items = [item for item in items if str(item.get("url", "")).startswith(category_url)]
    for item in items:
        if not item.get("title"):
            item["title"] = _title_from_url(str(item.get("url", "")))
        if not item.get("published_at"):
            item["published_at"] = _date_from_url(str(item.get("url", "")))
    return items


def _fetch_details(headers: dict[str, str], link: str | None) -> dict[str, Any]:
    if not link:
        return {}
    url = f"{settings.rapidapi_base_url}/details"
    logger.info("RapidAPI details: %s params=%s", url, {"url": link})
    try:
        response = requests.get(
            url,
            headers=headers,
            params={"url": link},
            timeout=settings.rapidapi_details_timeout_sec,
        )
        logger.info("RapidAPI details status: %s %s", response.status_code, response.reason)
        try:
            return response.json()
        except ValueError:
            snippet = response.text[:300] if response.text else ""
            logger.error("RapidAPI details non-JSON response (first 300 chars): %s", snippet)
            return {}
    except requests.RequestException as exc:
        logger.warning("RapidAPI details request failed: %s", exc)
        return {}


def _merge_details(item: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    if not details:
        return item

    title = item.get("title") or _extract_first(details, ["title", "headline", "storyTitle"])
    published = item.get("published_at") or _extract_first(
        details,
        ["published_at", "publishedAt", "published_time", "publishedTime", "date"],
    )
    if isinstance(published, dict) and "value" in published:
        published = published.get("value")

    merged = dict(item)
    if title:
        merged["title"] = title
    if published:
        merged["published_at"] = published
    return merged


def _extract_first(payload: Any, keys: list[str]) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    for container_key in ["article", "data", "result"]:
        container = payload.get(container_key)
        if isinstance(container, dict):
            for key in keys:
                value = container.get(key)
                if value:
                    return value
    return None


def _date_from_url(url: str) -> str:
    match = re.search(r"(\\d{4})-(\\d{2})-(\\d{2})", url)
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def _title_from_url(url: str) -> str:
    if not url:
        return ""
    slug = url.rstrip("/").split("/")[-1]
    if not slug:
        return ""
    slug = re.sub(r"-\\d{4}-\\d{2}-\\d{2}$", "", slug)
    title = slug.replace("-", " ").strip()
    return title.title()


def get_categories() -> list[dict[str, str]]:
    categories = []
    for endpoint in _load_endpoints():
        params = endpoint.get("params") or {}
        categories.append(
            {
                "sector": str(endpoint.get("sector", "")),
                "url": str(params.get("url", "")),
            }
        )
    return categories


def _filtered_endpoints(category: str | None) -> list[dict[str, Any]]:
    endpoints = _load_endpoints()
    if not category:
        return endpoints
    needle = _normalize_token(category)
    filtered = []
    for ep in endpoints:
        sector = _normalize_token(str(ep.get("sector", "")))
        if not sector:
            continue
        if sector == needle or sector.startswith(needle) or needle.startswith(sector):
            filtered.append(ep)
    return filtered


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())
