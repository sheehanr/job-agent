"""
One tracker run:

  1. collect postings from Simplify and every company site in companies.yaml
  2. store the new ones (anything already stored is just marked as seen)
  3. cheap rules -> skip the obviously irrelevant
  4. dedupe against roles already judged (any source, last N days)
  5. fetch descriptions and have the AI judge the rest
  6. notify (or, in shadow mode, just record) the new matches
  7. record which postings Simplify also listed, and how much later

The first time a source is seen, everything it already lists is marked
"baseline": judged for the dashboard but never notified.
"""

import concurrent.futures as cf
import time
import traceback
from datetime import datetime, timedelta, timezone

from tracker import db, notify, rules
from tracker.ai import Judge
from tracker.config import env
from tracker.describe import describe
from tracker.location import UNKNOWN, classify_location
from tracker.sources import fetch_company, simplify
from tracker.sources.http import session
from tracker.text import same_link, same_role, title_key

# Baseline postings with no term are only judged if posted this recently;
# older ones are almost always stale listings.
BASELINE_UNKNOWN_TERM_DAYS = 120

WORKERS = 8


def _now():
    return datetime.now(timezone.utc)


def _source_id(company):
    site = company.site
    return f"{site['type']}:{company.name}"


def collect(cfg, log):
    """All postings from every source: {source_id: [postings]}, errors."""

    found, errors = {}, {}

    t = time.time()
    try:
        found["simplify"] = [simplify.to_posting(l) for l in simplify.fetch_listings()]
    except Exception as e:
        errors["simplify"] = f"{type(e).__name__}: {e}"
    log(f"Simplify: {len(found.get('simplify', []))} listings ({time.time() - t:.0f}s)")

    direct = [c for c in cfg.companies if c.site]

    def run(company):
        try:
            return company, fetch_company(company, session()), None
        except Exception as e:
            return company, [], f"{type(e).__name__}: {str(e)[:200]}"

    t = time.time()
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for company, postings, err in ex.map(run, direct):
            if err:
                errors[company.name] = err
            else:
                found[_source_id(company)] = postings
    log(f"Company sites: {sum(len(v) for k, v in found.items() if k != 'simplify')} "
        f"intern postings from {len(direct) - len(errors)}/{len(direct)} companies "
        f"({time.time() - t:.0f}s)")

    return found, errors


def store(conn, cfg, found, log):
    """Insert new postings; mark existing ones seen. Returns new posting ids."""

    tracked = set(db.get_meta(conn, "tracked_sources", []) or [])
    new_ids = []

    for source_id, postings in found.items():

        baseline = source_id not in tracked
        keys = {p["source_key"] for p in postings}
        existing = db.existing_keys(conn, keys)

        db.touch(conn, [existing[k] for k in keys if k in existing])

        # Fill in posting dates for postings stored before dates were read.
        dated = [p for p in postings if p.get("posted_at") and p["source_key"] in existing]
        if dated:
            conn.execute("""
                update postings p set posted_at = x.d, posted_approx = x.a
                from unnest(%s::text[], %s::timestamptz[], %s::bool[]) as x(k, d, a)
                where p.source_key = x.k and p.posted_at is null""",
                ([q["source_key"] for q in dated], [q["posted_at"] for q in dated],
                 [bool(q.get("posted_approx")) for q in dated]))

        for p in postings:
            if p["source_key"] in existing or not p.get("active", True):
                continue
            existing[p["source_key"]] = None  # same key twice in one listing
            name = cfg.display_name(p["company"])
            p.update(company=name, company_key=simplify.normalize(name),
                     title_key=title_key(p["title"]), baseline=baseline)
            new_ids.append(db.insert_posting(conn, p))

        tracked.add(source_id)

    # Postings a source no longer lists (or lists as closed) are closed.
    for source_id, postings in found.items():
        open_keys = [p["source_key"] for p in postings if p.get("active", True)]
        if source_id == "simplify":
            where, args = "source = 'simplify'", ()
        else:
            where, args = "source <> 'simplify' and source <> 'legacy' and company = %s", (
                cfg.display_name(source_id.split(":", 1)[1]),)
        conn.execute(f"update postings set active = false where {where} and active "
                     f"and not (source_key = any(%s))", (*args, open_keys))

    db.set_meta(conn, "tracked_sources", sorted(tracked))
    log(f"New postings stored: {len(new_ids)}")

    return new_ids


def company_tiers(conn, cfg, judge, names, log):
    """
    {normalised company name: tier 1-3 or None} for these companies. One
    tier per company: your pin in companies.yaml if there is one, else the
    AI's rating, which is made once and cached in meta.company_tiers.
    """

    cache = {k: v for k, v in (db.get_meta(conn, "company_tiers", {}) or {}).items()
             if v in (1, 2, 3)}
    missing = sorted({n for n in names
                      if cfg.pinned_tier(n) is None and simplify.normalize(n) not in cache})

    if missing:
        log(f"Rating {len(missing)} companies")
        for name, tier in judge.company_tiers(missing).items():
            cache[simplify.normalize(name)] = tier
        db.set_meta(conn, "company_tiers", cache)

    return {simplify.normalize(n): cfg.pinned_tier(n) or cache.get(simplify.normalize(n))
            for n in names}


def _recent_feedback(conn, limit=25):
    return db.rows(conn, """
        select company, title, feedback_kind, feedback_reason from postings
        where user_status = 'not_fit' order by feedback_at desc limit %s""", (limit,))


def _recent_positive(conn, limit=25):
    """Postings you applied to or marked "It fits" - examples of what you want."""
    return db.rows(conn, """
        select company, title from postings
        where user_status in ('applied', 'good_fit') and source <> 'legacy'
        order by coalesce(applied_at, feedback_at) desc nulls last limit %s""", (limit,))


def _find_duplicate(conn, p, days):
    since = _now() - timedelta(days=days)
    for other in db.rows(conn, """
            select id, title, url from postings
            where company_key = %s and status = 'judged' and id <> %s and first_seen >= %s
              and source <> 'legacy'
            order by first_seen""", (p["company_key"], p["id"], since)):
        if _same_posting(p, other):
            return other["id"]
    return None


def _same_posting(a, b):
    """
    Same job: identical apply link (a company-site posting and its Simplify
    listing usually share it, even when the titles are worded differently),
    or near-identical titles. Titles are deliberately strict, so different
    roles at one company (e.g. Qualcomm's Embedded vs ML internships) stay
    separate.
    """

    return same_link(a.get("url"), b.get("url")) or same_role(a["title"], b["title"])


def screen(conn, cfg, judge, log):
    """Rules, dedupe and AI for every posting still in status 'new'."""

    pending = db.rows(conn, "select * from postings where status = 'new' order by "
                            "(source = 'simplify'), first_seen, id")
    if not pending:
        return {"screened": 0}

    to_judge, skipped = [], 0
    tier_check = []

    for p in pending:
        reason = rules.pre_ai(p, cfg)
        if reason:
            db.update(conn, p["id"], status="skipped", skip_reason=reason)
            skipped += 1
            continue

        status = rules.term_status(rules.all_terms(p), cfg.settings)
        if p["baseline"] and status == "unknown" and p["posted_at"] and \
                p["posted_at"] < _now() - timedelta(days=BASELINE_UNKNOWN_TERM_DAYS):
            db.update(conn, p["id"], status="skipped", skip_reason="old listing, no term")
            skipped += 1
            continue

        if status == "top_only":
            tier_check.append(p)
        else:
            to_judge.append(p)

    # One tier per company, used for the Summer gate and stored on every
    # posting the AI judges.
    tiers = company_tiers(conn, cfg, judge, [p["company"] for p in tier_check + to_judge], log)
    for p in tier_check + to_judge:
        p["tier"] = tiers.get(simplify.normalize(p["company"]))

    for p in tier_check:
        if p["tier"] in (1, 2):
            to_judge.append(p)
        else:
            db.update(conn, p["id"], status="skipped", tier=p["tier"],
                      skip_reason="top-tier-only term at a Tier 3 company")
            skipped += 1

    # Dedupe in order (company sites first), so a role found on both a
    # company's site and Simplify is judged once.
    unique, duplicates = [], 0
    dedupe_days = cfg.settings.get("dedupe_days", 21)
    seen_in_batch = []
    for p in to_judge:
        dup = _find_duplicate(conn, p, dedupe_days)
        if not dup:
            for q in seen_in_batch:
                if q["company_key"] == p["company_key"] and _same_posting(p, q):
                    dup = q["id"]
                    break
        if dup:
            db.update(conn, p["id"], status="duplicate", duplicate_of=dup)
            duplicates += 1
        else:
            unique.append(p)
            seen_in_batch.append(p)

    log(f"Screening {len(pending)}: {skipped} skipped by rules, {duplicates} duplicates, "
        f"{len(unique)} to the AI")

    def work(p):
        s = session()
        try:
            text, locations, status = describe(p, s)
            p = {**p, "description": text, "description_status": status}
            known = [l for l in p.get("locations") or [] if classify_location(l) != UNKNOWN]
            if locations and not known:
                p["locations"] = locations
            judgment = judge.judge(p)
            return p, judgment, None
        except Exception as e:
            return p, None, f"{type(e).__name__}: {str(e)[:300]}"

    judged, errors = 0, 0
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for p, judgment, err in ex.map(work, unique):
            if err:
                errors += 1
                db.update(conn, p["id"], skip_reason=f"error: {err}")
                continue
            verdict, reason = rules.final_verdict(p, judgment, cfg)
            judgment["final_reason"] = reason
            db.update(conn, p["id"], status="judged", description=p["description"],
                      description_status=p["description_status"], locations=p["locations"],
                      judgment=judgment, verdict=verdict, tier=p["tier"],
                      ai_model=judge.model, judged_at=_now())
            judged += 1
            # Keep the connection's transaction short-ish on big batches.
            if judged % 50 == 0:
                conn.commit()

    log(f"AI judged {judged} ({errors} errors)")
    return {"screened": len(pending), "skipped": skipped, "duplicates": duplicates,
            "judged": judged, "ai_errors": errors}


def match_coverage(conn):
    """Link postings found on company sites with the same role on Simplify."""

    direct = db.rows(conn, """
        select id, company_key, title, first_seen from postings
        where source <> 'simplify' and simplify_match_id is null and not baseline
          and status in ('judged', 'duplicate')""")
    matched = 0
    for d in direct:
        for s_ in db.rows(conn, """
                select id, title, first_seen from postings
                where source = 'simplify' and company_key = %s and not baseline""",
                          (d["company_key"],)):
            if same_role(d["title"], s_["title"]):
                lag = (s_["first_seen"] - d["first_seen"]).total_seconds() / 3600
                db.update(conn, d["id"], simplify_match_id=s_["id"], simplify_lag_hours=lag)
                matched += 1
                break
    return matched


def fill_dates_from_simplify(conn):
    """
    Company-site postings with no date (some job sites don't give one, or
    only "30+ days ago") borrow the date of the same role on Simplify,
    which records when it listed it - usually within hours of the company.
    """

    undated = db.rows(conn, """
        select id, company_key, title, url from postings
        where source not in ('simplify', 'legacy') and (posted_at is null or posted_approx)""")
    if not undated:
        return 0

    keys = list({u["company_key"] for u in undated})
    listed = {}
    for r in db.rows(conn, """
            select company_key, title, url, posted_at from postings
            where source = 'simplify' and posted_at is not null and company_key = any(%s)""",
                     (keys,)):
        listed.setdefault(r["company_key"], []).append(r)

    filled = 0
    for u in undated:
        for r in listed.get(u["company_key"], []):
            if same_link(u["url"], r["url"]) or same_role(u["title"], r["title"]):
                db.update(conn, u["id"], posted_at=r["posted_at"], posted_approx=False)
                filled += 1
                break
    return filled


def notify_new(conn, cfg, log):
    """Push (or in shadow mode, just record) new matches."""

    ncfg = cfg.settings.get("notifications") or {}
    verdicts = ncfg.get("verdicts") or ["alert"]
    pending = db.rows(conn, """
        select * from postings
        where status = 'judged' and verdict = any(%s) and notified_at is null
          and not baseline and user_status is null
        order by first_seen""", (verdicts,))

    # Roles the old tracker already sent you aren't sent again.
    since = _now() - timedelta(days=cfg.settings.get("dedupe_days", 21))
    legacy = db.rows(conn, "select company_key, title from postings "
                           "where source = 'legacy' and notified_at >= %s", (since,))
    already = [p for p in pending if any(
        l["company_key"] == p["company_key"] and same_role(l["title"], p["title"]) for l in legacy)]
    if already:
        conn.execute("update postings set notified_at = now() where id = any(%s)",
                     ([p["id"] for p in already],))
        pending = [p for p in pending if p not in already]

    if not pending:
        return 0

    if not ncfg.get("enabled"):
        conn.execute("update postings set notified_at = now() where id = any(%s)",
                     ([p["id"] for p in pending],))
        log(f"Shadow mode: {len(pending)} new matches recorded, not pushed")
        return 0

    notes = notify.build(pending, ncfg.get("dashboard_url") or "",
                         env("FEEDBACK_SECRET", "") or "")
    sent = 0
    for note in notes:
        if notify.send(note):
            conn.execute("update postings set notified_at = now() where id = any(%s)",
                         (note["ids"],))
            sent += 1
    log(f"Notifications sent: {sent}/{len(notes)}")
    return sent


def run(cfg, log=print):

    started = _now()
    summary = {}

    with db.connect() as conn:
        run_id = conn.execute("insert into runs default values returning id").fetchone()["id"]
        conn.commit()

        try:
            found, source_errors = collect(cfg, log)
            summary["source_errors"] = source_errors
            summary["new_postings"] = len(store(conn, cfg, found, log))
            conn.commit()

            judge = Judge(cfg, _recent_feedback(conn), _recent_positive(conn))
            summary.update(screen(conn, cfg, judge, log))
            summary["ai_usage"] = judge.usage
            conn.commit()

            summary["coverage_matches"] = match_coverage(conn)
            summary["dates_from_simplify"] = fill_dates_from_simplify(conn)
            summary["notifications"] = notify_new(conn, cfg, log)
            summary["seconds"] = round((_now() - started).total_seconds())

            conn.execute("update runs set finished_at = now(), summary = %s where id = %s",
                         (db.Jsonb(summary), run_id))
        except Exception:
            conn.rollback()
            conn.execute("update runs set finished_at = now(), summary = %s, error = %s "
                         "where id = %s", (db.Jsonb(db.jsonable(summary)),
                                           traceback.format_exc()[-4000:], run_id))
            conn.commit()
            raise

    return summary
