from __future__ import annotations

import argparse

from app.store.db import get_db, init_db


def drop_tables() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS scored_events")
    cur.execute("DROP TABLE IF EXISTS normalized_events")
    cur.execute("DROP TABLE IF EXISTS raw_events")
    conn.commit()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Postgres schema.")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing tables before creating schema.",
    )
    args = parser.parse_args()

    if args.drop:
        drop_tables()

    init_db()


if __name__ == "__main__":
    main()
