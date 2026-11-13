"""Create (or update) the database tables in Supabase.  python scripts/setup_db.py"""

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")

from tracker import db  # noqa: E402

with db.connect() as conn:
    db.setup(conn)

print("Database tables are ready.")
