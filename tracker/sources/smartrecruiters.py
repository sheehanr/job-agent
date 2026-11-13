"""SmartRecruiters job boards, via the public postings API."""

from tracker.sources.http import html_to_text
from tracker.text import is_internship

API = "https://api.smartrecruiters.com/v1/companies"


def _location(loc):

    loc = loc or {}
    if loc.get("fullLocation"):
        return loc["fullLocation"]
    parts = [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()]
    text = ", ".join(p for p in parts if p)
    return f"{text} (remote)" if loc.get("remote") else text


def fetch(company, site, s):

    out = []

    for offset in range(0, 2000, 100):
        r = s.get(f"{API}/{site['company']}/postings",
                  params={"limit": 100, "offset": offset}, timeout=30)
        r.raise_for_status()
        data = r.json()
        content = data.get("content") or []

        for job in content:
            title = job.get("name") or ""
            kind = ((job.get("typeOfEmployment") or {}).get("label") or "")
            if not (is_internship(title) or kind.lower() == "intern"):
                continue
            out.append({
                "source": "smartrecruiters",
                "source_key": f"smartrecruiters:{site['company']}:{job['id']}",
                "company": company.name,
                "title": title,
                "locations": [_location(job.get("location"))],
                "url": f"https://jobs.smartrecruiters.com/{site['company']}/{job['id']}",
                "site": site,
                "job_id": job["id"],
            })

        if offset + 100 >= (data.get("totalFound") or 0) or not content:
            break

    return out


def describe(company_id, job_id, s):

    r = s.get(f"{API}/{company_id}/postings/{job_id}", timeout=30)
    r.raise_for_status()
    job = r.json()
    sections = (job.get("jobAd") or {}).get("sections") or {}
    text = "\n\n".join(html_to_text((sections.get(k) or {}).get("text"))
                       for k in ("jobDescription", "qualifications", "additionalInformation"))
    kind = (job.get("typeOfEmployment") or {}).get("label")

    return (f"Employment type: {kind}\n\n{text}" if kind else text), [_location(job.get("location"))]
