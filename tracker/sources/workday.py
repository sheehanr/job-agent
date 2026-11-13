"""Workday career sites (*.myworkdayjobs.com), via their public JSON API."""

import time

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship

PAGE = 20
MAX_PER_TERM = 200


def _base(site):
    return f"https://{site['host']}/wday/cxs/{site['tenant']}/{site['site']}"


def _search(site, term, offset, s):

    for attempt in range(3):
        r = s.post(
            f"{_base(site)}/jobs",
            json={"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": term},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            # Workday sometimes answers a burst of requests with an HTML page.
            time.sleep(2 + 3 * attempt)

    raise RuntimeError(f"Workday {site['host']} kept returning non-JSON")


def fetch(company, site, s):

    seen = {}

    for term in SEARCH_TERMS:
        for offset in range(0, MAX_PER_TERM, PAGE):

            data = _search(site, term, offset, s)
            postings = data.get("jobPostings") or []

            for job in postings:
                path = job.get("externalPath") or ""
                title = job.get("title") or ""
                if not path or path in seen or not is_internship(title):
                    continue
                seen[path] = {
                    "source": "workday",
                    "source_key": f"workday:{site['tenant']}:{path.rsplit('_', 1)[-1]}",
                    "company": company.name,
                    "title": title,
                    "locations": [job.get("locationsText") or ""],
                    "url": f"https://{site['host']}/{site['site']}{path}",
                    "site": site,
                    "path": path,
                }

            if offset + PAGE >= (data.get("total") or 0) or not postings:
                break

    return list(seen.values())


def describe(site, path, s):
    """(description text, [locations]) for one posting."""

    r = s.get(f"{_base(site)}{path}", timeout=30)
    r.raise_for_status()
    info = r.json().get("jobPostingInfo") or {}

    locations = [info.get("location")] + list(info.get("additionalLocations") or [])
    text = html_to_text(info.get("jobDescription"))

    extra = [f"Time type: {info['timeType']}"] if info.get("timeType") else []
    if info.get("startDate"):
        extra.append(f"Posted: {info['startDate']}")

    return "\n".join(extra + [text]), [l for l in locations if l]
