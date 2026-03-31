from __future__ import annotations

from app.store.db import get_db


def main() -> None:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE scored_events")
        cur.execute("TRUNCATE normalized_events")
        conn.commit()
    print("Cleared normalized_events and scored_events.")


if __name__ == "__main__":
    main()
