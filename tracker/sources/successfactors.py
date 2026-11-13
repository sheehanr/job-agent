"""SAP SuccessFactors "Career Site Builder" sites, read from the search page."""

import re

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship

_ANCHOR_RE = re.compile(r'<a\b[^>]*class="jobTitle-link[^"]*"[^>]*>.*?</a>', re.S | re.I)
_HREF_RE = re.compile(r'href="([^"]*/job/[^"]+/(\d+)/)"')


def fetch(company, site, s):

    found = {}

    for term in SEARCH_TERMS:
        for startrow in range(0, 250, 25):
            r = s.get(f"https://{site['host']}/search/",
                      params={"q": term, "startrow": startrow}, timeout=30)
            r.raise_for_status()
            anchors = _ANCHOR_RE.findall(r.text)

            for a in anchors:
                m = _HREF_RE.search(a)
                title = html_to_text(a).strip()
                if not m or m.group(2) in found or not is_internship(title):
                    continue
                found[m.group(2)] = {
                    "source": "successfactors",
                    "source_key": f"successfactors:{site['host']}:{m.group(2)}",
                    "company": company.name,
                    "title": title,
                    "locations": [""],
                    "url": f"https://{site['host']}{m.group(1)}",
                }

            if len(anchors) < 25:
                break

    return list(found.values())


def describe(url, s):

    r = s.get(url, timeout=30)
    r.raise_for_status()
    page = r.text
    m = re.search(r'<span class="jobdescription">(.*?)</span>\s*</div>', page, re.S)
    loc = re.search(r'jobGeoLocation"[^>]*>([^<]+)<', page) or re.search(
        r'data-careersite-propertyid="(?:city|location)"[^>]*>\s*<span[^>]*>([^<]+)<', page)

    return html_to_text(m.group(1) if m else page), [loc.group(1).strip()] if loc else []
