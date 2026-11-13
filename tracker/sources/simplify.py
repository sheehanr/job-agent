"""
Simplify's community-maintained internship list (all seasons). The
GitHub repo's READMEs - including the Off-Season one - are generated from
this one listings.json, so a single download covers everything.
"""

import re
from datetime import datetime, timezone

import requests

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/"
    "dev/.github/scripts/listings.json"
)

UA = {"User-Agent": "job-agent (personal job tracker)"}

_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|llc|ltd|plc|"
    r"holdings|technologies|technology)\b\.?$"
)


def normalize(name):
    """Company name -> comparison key ("Insulet Corporation" -> "insulet")."""

    text = re.sub(r"[^a-z0-9& ]", " ", (name or "").lower())
    text = re.sub(r"\s+", " ", text).strip()

    previous = None
    while previous != text:
        previous = text
        text = _SUFFIX_RE.sub("", text).strip()

    return text


def fetch_listings(url=LISTINGS_URL):

    response = requests.get(url, headers=UA, timeout=60)
    response.raise_for_status()

    return response.json()


def to_posting(listing):
    """A Simplify listing in the tracker's common posting shape."""

    posted = listing.get("date_posted")

    return {
        "source": "simplify",
        "source_key": f"simplify:{listing['id']}",
        "company": (listing.get("company_name") or "").strip(),
        "title": (listing.get("title") or "").strip(),
        "locations": [l for l in listing.get("locations") or [] if l],
        "url": listing.get("url") or "",
        "terms": listing.get("terms") or [],
        "degrees": listing.get("degrees") or [],
        "category": listing.get("category") or "",
        "posted_at": (
            datetime.fromtimestamp(posted, tz=timezone.utc) if posted else None
        ),
        "active": bool(listing.get("active") and listing.get("is_visible")),
    }
