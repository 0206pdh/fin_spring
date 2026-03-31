from __future__ import annotations

import json
from typing import Iterable

from psycopg.rows import dict_row

from app.models import RawEvent
from app.store.db import get_db


def save_raw_events(events: Iterable[RawEvent]) -> int:
    count = 0
    with get_db() as conn:
        cur = conn.cursor()
        for event in events:
            cur.execute(
                """
                INSERT INTO raw_events
                (id, title, url, published_at, sector, source, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    event.id,
                    event.title,
                    event.url,
                    event.published_at,
                    event.sector,
                    event.source,
                    json.dumps(event.payload, ensure_ascii=True),
                ),
            )
            if cur.rowcount:
                count += 1
        conn.commit()
    return count


def fetch_unprocessed_raw_events(limit: int = 200) -> list[RawEvent]:
    with get_db() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """
            SELECT r.* FROM raw_events r
            LEFT JOIN normalized_events n ON n.raw_event_id::text = r.id
            WHERE n.raw_event_id IS NULL
            ORDER BY r.published_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    events: list[RawEvent] = []
    for row in rows:
        events.append(
            RawEvent(
                id=row["id"],
                title=row["title"],
                url=row["url"],
                published_at=row["published_at"],
                sector=row["sector"],
                source=row["source"],
                payload=row["payload"],
            )
        )
    return events


def fetch_raw_event(raw_event_id: str) -> RawEvent | None:
    with get_db() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT * FROM raw_events WHERE id = %s", (raw_event_id,))
        row = cur.fetchone()
    if not row:
        return None
    return RawEvent(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        published_at=row["published_at"],
        sector=row["sector"],
        source=row["source"],
        payload=row["payload"],
    )
