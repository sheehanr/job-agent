"""Lever job boards, via the public postings API."""

import re

from tracker.location import country_name
from tracker.text import is_internship


def _posting_text(job):

    parts = [job.get("descriptionPlain") or ""]
    for section in job.get("lists") or []:
        parts.append(section.get("text") or "")
        parts.append(" ".join(
            re.sub(r"<[^>]+>", " ", section.get("content") or "").split()
        ))
    parts.append(job.get("additionalPlain") or "")

    return "\n".join(p for p in parts if p)[:15000]


def _locations(job):

    cats = job.get("categories") or {}
    locs = cats.get("allLocations") or [cats.get("location") or ""]
    country = country_name(job.get("country"))

    return [f"{l}, {country}" if country and country not in l else l for l in locs if l]


def fetch(company, site, s):

    r = s.get(f"https://api.lever.co/v0/postings/{site['site']}?mode=json", timeout=30)
    r.raise_for_status()

    out = []

    for job in r.json() or []:
        title = job.get("text") or ""
        commitment = (job.get("categories") or {}).get("commitment") or ""
        if not (is_internship(title) or is_internship(commitment)):
            continue
        out.append({
            "source": "lever",
            "source_key": f"lever:{site['site']}:{job['id']}",
            "company": company.name,
            "title": title,
            "locations": _locations(job),
            "url": job.get("hostedUrl") or "",
            "description": _posting_text(job),
            "posted": job.get("createdAt"),
        })

    return out


def describe(site_name, job_id, s):

    r = s.get(f"https://api.lever.co/v0/postings/{site_name}/{job_id}?mode=json", timeout=30)
    r.raise_for_status()
    job = r.json()

    return _posting_text(job), _locations(job)
