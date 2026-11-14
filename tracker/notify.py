"""
Phone notifications through ntfy (https://ntfy.sh).

One notification per role ("Company - Role"); the same role in several
locations shares one; a company with 2+ new roles in a run gets a single
"Company - N new roles" notification. Tapping a single-role notification
opens the apply link. Buttons send "not a fit" feedback to the dashboard,
which records it (and can be undone there).
"""

import hashlib
import hmac
import time

import requests

from tracker.config import env

NTFY_MAX_BYTES = 3900


def sign(ids, kind, secret):
    msg = f"{','.join(str(i) for i in sorted(ids))}:{kind}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]


def _feedback_action(label, ids, kind, dashboard_url, secret):
    ids_text = ",".join(str(i) for i in sorted(ids))
    return {
        "action": "http",
        "label": label,
        "url": (f"{dashboard_url.rstrip('/')}/api/feedback?ids={ids_text}&kind={kind}"
                f"&sig={sign(ids, kind, secret)}"),
        "method": "POST",
        "clear": True,
    }


def _location_line(p):
    locs = [l for l in p.get("locations") or [] if l]
    if not locs:
        return "(location unknown)"
    text = "; ".join(locs[:3]) + (f" +{len(locs) - 3} more" if len(locs) > 3 else "")
    return f"({text})"


def _extras(p):
    j = p.get("judgment") or {}
    bits = []
    if j.get("reason"):
        bits.append(j["reason"])
    if j.get("pay"):
        bits.append(f"Pay: {j['pay']}")
    if p.get("description_status") == "unavailable":
        bits.append("Unverified: couldn't read the description")
    return bits


def build(postings, dashboard_url="", secret=""):
    """Notifications for a batch of new matches (list of dicts)."""

    by_company = {}
    for p in postings:
        by_company.setdefault(p["company"], []).append(p)

    notes = []

    for company, items in by_company.items():

        roles = {}
        for p in items:
            roles.setdefault(p["title"], []).append(p)

        if len(roles) >= 2:
            blocks = []
            for title, ps in roles.items():
                for p in ps:
                    blocks.append(f"{title}: {p['url']}\n{_location_line(p)}")
            ids = [p["id"] for p in items]
            note = {"title": f"{company} - {len(roles)} new roles",
                    "message": "\n\n".join(blocks), "ids": ids, "click": None, "actions": []}
            if dashboard_url and secret:
                note["click"] = f"{dashboard_url.rstrip('/')}/?company={requests.utils.quote(company)}"
                note["actions"] = [_feedback_action("Not interested: company", ids, "company",
                                                    dashboard_url, secret)]
            notes.append(note)
            continue

        for title, ps in roles.items():
            blocks = [f"{p['url']}\n{_location_line(p)}" for p in ps]
            extras = _extras(ps[0])
            message = "\n\n".join(blocks + (["\n".join(extras)] if extras else []))
            ids = [p["id"] for p in ps]
            note = {"title": f"{company} - {title}", "message": message, "ids": ids,
                    "click": ps[0]["url"] if len(ps) == 1 else None, "actions": []}
            if dashboard_url and secret:
                note["actions"] = [
                    _feedback_action("Not interested: role", ids, "role", dashboard_url, secret),
                    _feedback_action("Not interested: company", ids, "company", dashboard_url, secret),
                ]
            notes.append(note)

    return notes


def _split(message, limit=NTFY_MAX_BYTES):
    if len(message.encode()) <= limit:
        return [message]
    chunks, current = [], ""
    for block in message.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if current and len(candidate.encode()) > limit:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def send(note):
    """Push one notification. Returns True when ntfy accepted every part."""

    topic = env("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC not set; not sending.")
        return False

    server = (env("NTFY_SERVER", "") or "https://ntfy.sh").rstrip("/")
    headers = {}
    token = env("NTFY_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    parts = _split(note["message"])

    for i, part in enumerate(parts, 1):
        body = {"topic": topic, "message": part,
                "title": note["title"] + (f" ({i}/{len(parts)})" if len(parts) > 1 else "")}
        if note.get("click"):
            body["click"] = note["click"]
        if note.get("actions") and i == len(parts):
            body["actions"] = note["actions"]
        try:
            r = requests.post(server, json=body, headers=headers, timeout=15)
            r.raise_for_status()
        except Exception as e:
            # Never print the topic: the repo's Actions logs are public.
            print(f"ntfy send failed: {type(e).__name__}")
            return False
        time.sleep(0.5)

    return True
