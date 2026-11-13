"""Greenhouse job boards, via the public boards API."""

from tracker.sources.http import html_to_text
from tracker.text import is_internship

API = "https://boards-api.greenhouse.io/v1/boards"


def fetch(company, site, s):

    r = s.get(f"{API}/{site['board']}/jobs", timeout=30)
    r.raise_for_status()

    out = []

    for job in r.json().get("jobs") or []:
        title = job.get("title") or ""
        if not is_internship(title):
            continue
        out.append({
            "source": "greenhouse",
            "source_key": f"greenhouse:{site['board']}:{job['id']}",
            "company": company.name,
            "title": title,
            "locations": [(job.get("location") or {}).get("name") or ""],
            "url": job.get("absolute_url") or "",
            "site": site,
            "job_id": job["id"],
        })

    return out


def describe(board, job_id, s):

    r = s.get(f"{API}/{board}/jobs/{job_id}", timeout=30)
    r.raise_for_status()
    job = r.json()

    return html_to_text(job.get("content")), [(job.get("location") or {}).get("name") or ""]
