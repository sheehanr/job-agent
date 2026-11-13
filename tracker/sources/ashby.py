"""Ashby job boards, via the public posting API."""

from tracker.text import is_internship

API = "https://api.ashbyhq.com/posting-api/job-board"


def _locations(job):

    locs = [job.get("location") or ""]
    locs += [l.get("location") or "" for l in job.get("secondaryLocations") or []]
    country = (((job.get("address") or {}).get("postalAddress") or {})
               .get("addressCountry") or "")

    return [f"{l}, {country}" if country and country not in l else l for l in locs if l]


def _text(job):

    text = job.get("descriptionPlain") or ""
    comp = (job.get("compensation") or {}).get("compensationTierSummary")
    if comp:
        text = f"Compensation: {comp}\n\n{text}"

    return text[:15000]


def board(org, s):

    r = s.get(f"{API}/{org}?includeCompensation=true", timeout=30)
    r.raise_for_status()

    return r.json().get("jobs") or []


def fetch(company, site, s):

    out = []

    for job in board(site["org"], s):
        title = job.get("title") or ""
        if not job.get("isListed", True):
            continue
        if not (is_internship(title) or (job.get("employmentType") or "") == "Intern"):
            continue
        out.append({
            "source": "ashby",
            "source_key": f"ashby:{site['org']}:{job['id']}",
            "company": company.name,
            "title": title,
            "locations": _locations(job),
            "url": job.get("jobUrl") or "",
            "description": _text(job),
            "posted": job.get("publishedAt"),
        })

    return out


def describe(org, job_id, s):

    for job in board(org, s):
        if job.get("id") == job_id:
            return _text(job), _locations(job)

    return "", []
