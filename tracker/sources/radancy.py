"""Radancy (TMP) career sites such as careers.arm.com, via their results endpoint."""

import re

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship

_ITEM_RE = re.compile(
    r'<a[^>]*href="(/job/[^"]+/(\d+))"[^>]*>(.*?)</a>.*?<span class="location">(.*?)</span>',
    re.S,
)


def fetch(company, site, s):

    found = {}

    for term in SEARCH_TERMS:
        for page in range(1, 6):
            r = s.get(f"https://{site['host']}/search-jobs/results",
                      params={"ActiveFacetID": 0, "CurrentPage": page, "RecordsPerPage": 100,
                              "Keywords": term, "SearchType": 5,
                              "SearchResultsModuleName": "Search Results"},
                      headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30)
            r.raise_for_status()
            items = _ITEM_RE.findall(r.json().get("results") or "")

            for path, job_id, title, location in items:
                title = html_to_text(title)
                if job_id in found or not is_internship(title):
                    continue
                found[job_id] = {
                    "source": "radancy",
                    "source_key": f"radancy:{site['host']}:{job_id}",
                    "company": company.name,
                    "title": title,
                    "locations": [html_to_text(location)],
                    "url": f"https://{site['host']}{path}",
                }

            if len(items) < 100:
                break

    return list(found.values())
