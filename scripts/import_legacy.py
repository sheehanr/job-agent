"""
One-off: copy recent alerts from the old SQLite tracker into Supabase, so
roles it already sent you aren't sent again by the new tracker.

    python scripts/import_legacy.py path/to/internship_agent.db
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")

from tracker import config, db  # noqa: E402
from tracker.sources.simplify import normalize  # noqa: E402
from tracker.text import title_key  # noqa: E402


def main(path):

    cfg = config.load()
    old = sqlite3.connect(path)
    old.row_factory = sqlite3.Row
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = old.execute("select * from alerts where timestamp >= ?", (since,)).fetchall()

    added = 0
    with db.connect() as conn:
        for r in rows:
            key = f"legacy:{r['id']}"
            if db.existing_keys(conn, [key]):
                continue
            name = cfg.display_name(r["company"])
            seen = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=timezone.utc)
            pid = db.insert_posting(conn, {
                "source": "legacy", "source_key": key, "company": name,
                "company_key": normalize(name), "title": r["title"],
                "title_key": title_key(r["title"]),
                "locations": [r["location"]] if r["location"] else [],
                "url": r["application_url"] or "", "baseline": True, "active": False,
            })
            db.update(conn, pid, status="judged", verdict="alert", notified_at=seen,
                      first_seen=seen, skip_reason="sent by the old tracker")
            added += 1

    print(f"Imported {added} alerts from the old tracker (last 30 days).")


if __name__ == "__main__":
    main(sys.argv[1])
