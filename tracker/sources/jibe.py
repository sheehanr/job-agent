"""Jibe career sites (e.g. careers.garmin.com), via their JSON API."""

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship


def fetch(company, site, s):

    found = {}

    for term in SEARCH_TERMS:
        for page in range(1, 6):
            r = s.get(f"https://{site['host']}/api/jobs",
                      params={"keywords": term, "page": page, "limit": 100}, timeout=30)
            r.raise_for_status()
            jobs = r.json().get("jobs") or []

            for job in jobs:
                d = job.get("data") or {}
                title = d.get("title") or ""
                if d.get("req_id") in found or not is_internship(title):
                    continue
                found[d["req_id"]] = {
                    "source": "jibe",
                    "source_key": f"jibe:{site['host']}:{d['req_id']}",
                    "company": company.name,
                    "title": title,
                    "locations": [", ".join(x for x in (d.get("full_location"), d.get("country")) if x)],
                    "url": f"https://{site['host']}/jobs/{d.get('slug') or d['req_id']}",
                    "description": html_to_text(d.get("description")),
                    "posted": d.get("posted_date"),
                }

            if len(jobs) < 100:
                break

    return list(found.values())
