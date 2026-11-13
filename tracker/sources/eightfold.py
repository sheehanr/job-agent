"""Eightfold career sites (*.eightfold.ai and custom domains on it)."""

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship


def fetch(company, site, s):

    found = {}

    for term in SEARCH_TERMS:
        for start in range(0, 300, 10):
            r = s.get(f"https://{site['host']}/api/pcsx/search",
                      params={"domain": site["domain"], "query": term, "start": start},
                      timeout=30)
            r.raise_for_status()
            data = r.json().get("data") or {}
            positions = data.get("positions") or []

            for p in positions:
                title = p.get("name") or ""
                if p["id"] in found or not is_internship(title):
                    continue
                found[p["id"]] = {
                    "source": "eightfold",
                    "source_key": f"eightfold:{site['domain']}:{p['id']}",
                    "company": company.name,
                    "title": title,
                    "locations": p.get("standardizedLocations") or p.get("locations") or [],
                    "url": f"https://{site['host']}/careers/job/{p['id']}",
                    "site": site,
                    "job_id": p["id"],
                    "posted": p.get("postedTs"),
                }

            if start + 10 >= (data.get("count") or 0) or not positions:
                break

    return list(found.values())


def describe(site, job_id, s):

    r = s.get(f"https://{site['host']}/api/pcsx/position_details",
              params={"position_id": job_id, "domain": site["domain"], "hl": "en"}, timeout=30)
    r.raise_for_status()
    p = r.json().get("data") or {}

    return html_to_text(p.get("jobDescription")), p.get("standardizedLocations") or p.get("locations") or []
