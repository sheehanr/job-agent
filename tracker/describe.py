"""
Fetch a posting's full job description so the AI can read it.

Postings found directly on a company's site carry a `detail` reference
for their adapter. Simplify postings are matched to an adapter from their
apply link; anything else falls back to reading the page itself (the
schema.org JobPosting data most career sites embed, else the page text).
Bot-protected pages just come back as "unavailable" - the AI then judges
from the title and marks the result unverified.
"""

import json
import re

from bs4 import BeautifulSoup

from tracker.sources import (ashby, eightfold, greenhouse, icims, lever, oracle,
                             smartrecruiters, successfactors, workday)
from tracker.sources.detect import job_ref
from tracker.sources.http import html_to_text

MIN_CHARS = 300

_JOBBY_RE = re.compile(r"responsibilit|qualification|requirement|experience|"
                       r"you will|you'll|degree|skills|apply|internship|intern\b", re.I)

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def _by_ref(kind, p, s):

    if kind == "workday":
        return workday.describe(p, p["path"], s)
    if kind == "greenhouse":
        return greenhouse.describe(p["board"], p["job_id"], s)
    if kind == "lever":
        return lever.describe(p["site"], p["job_id"], s)
    if kind == "ashby":
        return ashby.describe(p["org"], p["job_id"], s)
    if kind == "smartrecruiters":
        return smartrecruiters.describe(p["company"], p["job_id"], s)
    if kind == "oracle":
        return oracle.describe(p, p["job_id"], s)
    if kind == "eightfold":
        return eightfold.describe(p, p["job_id"], s)
    if kind == "icims":
        return icims.describe(p["url"], s)
    if kind == "successfactors":
        return successfactors.describe(p["url"], s)

    return None


def _json_ld_postings(soup):

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                yield item


def _generic(url, s):

    r = s.get(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    for item in _json_ld_postings(soup):
        text = html_to_text(item.get("description"))
        extra = []
        labels = {"title": "Posting page title", "employmentType": "Employment type",
                  "datePosted": "Date posted"}
        for key, label in labels.items():
            if item.get(key):
                extra.append(f"{label}: {item[key]}")
        locs = item.get("jobLocation") or []
        locs = locs if isinstance(locs, list) else [locs]
        places = []
        for loc in locs:
            a = (loc or {}).get("address") or {}
            if isinstance(a, dict):
                places.append(", ".join(str(x) for x in (a.get("addressLocality"),
                              a.get("addressRegion"), a.get("addressCountry")) if x))
        if text:
            return "\n".join(extra + [text]), [p for p in places if p]

    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = re.sub(r"\n\s*\n+", "\n\n", main.get_text("\n")).strip()[:15000]

    # Without structured data, only trust page text that reads like a job
    # description (not a cookie wall, bot check or empty app shell).
    if len(_JOBBY_RE.findall(text)) < 3:
        return "", []

    return text, []


def describe(posting, s):
    """
    Returns (text, locations, status) where status is "ok" or
    "unavailable". Never raises.
    """

    if posting.get("description") and len(posting["description"]) >= MIN_CHARS:
        return posting["description"], [], "ok"

    detail = posting.get("detail") or {}
    ref = (detail["type"], detail) if detail.get("type") else job_ref(posting.get("url"))

    try:
        result = _by_ref(*ref, s) if ref else None
        if not result or len(result[0] or "") < MIN_CHARS:
            result = _generic(posting["url"], s) if posting.get("url") else None
    except Exception:
        try:
            result = _generic(posting["url"], s) if posting.get("url") else None
        except Exception:
            result = None

    if not result or len(result[0] or "") < MIN_CHARS:
        return "", [], "unavailable"

    return result[0], result[1], "ok"
