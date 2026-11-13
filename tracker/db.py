"""Postgres (Supabase) access for the tracker."""

import json
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tracker.config import ROOT, env

SCHEMA = ROOT / "db" / "schema.sql"

POSTING_FIELDS = ("source", "source_key", "company", "company_key", "title", "title_key",
                  "locations", "url", "terms", "degrees", "category", "detail",
                  "posted_at", "posted_approx", "active", "baseline", "description")


@contextmanager
def connect(url=None):

    conn = psycopg.connect(url or env("SUPABASE_DB_URL", required=True),
                           row_factory=dict_row, autocommit=False, connect_timeout=20,
                           prepare_threshold=None)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def setup(conn):
    conn.execute(Path(SCHEMA).read_text())


def get_meta(conn, key, default=None):
    row = conn.execute("select value from meta where key = %s", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "insert into meta (key, value) values (%s, %s) "
        "on conflict (key) do update set value = excluded.value",
        (key, Jsonb(value)),
    )


def existing_keys(conn, keys):
    """{source_key: id} for postings already stored."""

    if not keys:
        return {}
    rows = conn.execute(
        "select id, source_key from postings where source_key = any(%s)", (list(keys),)
    ).fetchall()
    return {r["source_key"]: r["id"] for r in rows}


def insert_posting(conn, p):
    """Insert a posting; fields it doesn't have take the table defaults."""

    fields = [f for f in POSTING_FIELDS if p.get(f) is not None]
    values = [Jsonb(p[f]) if f == "detail" else p[f] for f in fields]
    row = conn.execute(
        f"insert into postings ({', '.join(fields)}) "
        f"values ({', '.join(['%s'] * len(fields))}) returning id",
        values,
    ).fetchone()
    return row["id"]


def touch(conn, ids, active=True):
    """Mark postings as still listed."""

    if ids:
        conn.execute("update postings set last_seen = now(), active = %s where id = any(%s)",
                     (active, list(ids)))


def update(conn, posting_id, **fields):

    if not fields:
        return
    cols = []
    values = []
    for k, v in fields.items():
        cols.append(f"{k} = %s")
        values.append(Jsonb(v) if k in ("judgment", "detail") and v is not None else v)
    values.append(posting_id)
    conn.execute(f"update postings set {', '.join(cols)} where id = %s", values)


def rows(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def jsonable(value):
    return json.loads(json.dumps(value, default=str))
