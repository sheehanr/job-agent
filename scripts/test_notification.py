"""
Send one real notification for your current top match, with working
"Not a fit" buttons, to check the phone side end to end. Anything you tap
can be undone on the dashboard.

    python scripts/test_notification.py
"""

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")

from tracker import config, db, notify  # noqa: E402
from tracker.config import env  # noqa: E402


def main():
    cfg = config.load()
    with db.connect() as conn:
        row = conn.execute("""
            select * from postings where status = 'judged' and verdict = 'alert'
              and user_status is null and active and source <> 'legacy'
            order by tier nulls last, first_seen desc limit 1""").fetchone()
    if not row:
        print("No matches yet.")
        return
    url = (cfg.settings.get("notifications") or {}).get("dashboard_url") or ""
    [note] = notify.build([row], url, env("FEEDBACK_SECRET", "") or "")
    note["title"] = "Test: " + note["title"]
    print("Sent." if notify.send(note) else "Send failed.")


if __name__ == "__main__":
    main()
