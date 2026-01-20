from __future__ import annotations

import os

import psycopg

from app.config import settings


def main() -> None:
    database_url = os.getenv("DATABASE_URL") or settings.database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is missing. Set DATABASE_URL or FIM_DATABASE_URL.")
    conn = psycopg.connect(database_url)
    cur = conn.cursor()
    cur.execute("TRUNCATE scored_events")
    cur.execute("TRUNCATE normalized_events")
    conn.commit()
    conn.close()
    print("Cleared normalized_events and scored_events.")


if __name__ == "__main__":
    main()
