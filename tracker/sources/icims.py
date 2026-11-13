"""iCIMS career portals (*.icims.com), read from the server-rendered pages."""

import json
import re

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship

_LINK_RE = re.compile(
    r'<a[^>]+href="(https://[^"]+/jobs/(\d+)/[^"/]+/job)[^"]*"[^>]*>(.*?)</a>', re.S | re.I
)


def fetch(company, site, s):

    found = {}
    seen = set()

    for term in SEARCH_TERMS:
        for page in range(0, 10):
            r = s.get(f"https://{site['host']}/jobs/search",
                      params={"ss": 1, "searchKeyword": term, "in_iframe": 1, "pr": page},
                      timeout=30)
            r.raise_for_status()
            links = _LINK_RE.findall(r.text)
            new = [l for l in links if l[1] not in seen]
            seen.update(l[1] for l in links)
            for url, job_id, inner in new:
                title = re.sub(r"^\s*Title\s*", "", html_to_text(inner)).strip()
                if job_id in found or not is_internship(title):
                    continue
                found[job_id] = {
                    "source": "icims",
                    "source_key": f"icims:{site['host']}:{job_id}",
                    "company": company.name,
                    "title": title,
                    "locations": [""],
                    "url": url,
                }
            if not links or not new:
                break

    return list(found.values())


def describe(url, s):

    r = s.get(url, params={"in_iframe": 1}, timeout=30)
    r.raise_for_status()
    page = r.text

    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            locs = data.get("jobLocation") or []
            locs = locs if isinstance(locs, list) else [locs]
            places = []
            for loc in locs:
                a = (loc or {}).get("address") or {}
                places.append(", ".join(x for x in (a.get("addressLocality"), a.get("addressRegion"),
                                                    a.get("addressCountry")) if x))
            return html_to_text(data.get("description")), [p for p in places if p]

    m = re.search(r'class="iCIMS_JobContent.*?>(.*)</div>', page, re.S)
    return html_to_text(m.group(1) if m else page), []
