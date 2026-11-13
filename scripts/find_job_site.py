"""
Work out which job site (ATS) a company uses, so it can be added to
config/companies.yaml for direct tracking.

    python scripts/find_job_site.py "Stripe" "Epic Systems" "Arm"

For each name it:
  1. looks at the company's Simplify listings and reads the ATS out of the
     apply links (most reliable - these are real postings), then
  2. if Simplify has nothing, probes the public Greenhouse, Lever, Ashby
     and SmartRecruiters APIs with guessed board names.

It prints a suggested companies.yaml entry, or "not found" (custom career
sites have to be added by hand, or left to Simplify).
"""

import collections
import re
import sys
from urllib.parse import urlparse

import requests

sys.path.insert(0, __import__("os").path.dirname(__file__) + "/..")

from tracker.sources import simplify  # noqa: E402
from tracker.sources.detect import ats_from_url  # noqa: E402

UA = {"User-Agent": "job-agent (personal job tracker)"}


def from_simplify(name, listings):

    key = simplify.normalize(name)
    found = collections.Counter()
    hosts = collections.Counter()

    for listing in listings:
        if simplify.normalize(listing.get("company_name")) != key:
            continue
        hosts[urlparse(listing.get("url") or "").netloc.lower()] += 1
        ats = ats_from_url(listing.get("url"))
        if ats:
            found[(ats[0], tuple(sorted(ats[1].items())))] += 1

    return found, hosts


def _slugs(name):

    base = re.sub(r"[^a-z0-9 ]", "", name.lower())
    words = base.split()
    out = {"".join(words), "-".join(words)}
    if words:
        out.add(words[0])
    return [s for s in out if s]


def probe(name):

    for slug in _slugs(name):

        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            headers=UA, timeout=15,
        )
        if r.ok and r.json().get("jobs") is not None:
            return "greenhouse", {"board": slug}, len(r.json()["jobs"])

        r = requests.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            headers=UA, timeout=15,
        )
        if r.ok and isinstance(r.json(), list) and r.json():
            return "lever", {"site": slug}, len(r.json())

        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            headers=UA, timeout=15,
        )
        if r.ok and r.json().get("jobs"):
            return "ashby", {"org": slug}, len(r.json()["jobs"])

        r = requests.get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
            headers=UA, timeout=15,
        )
        if r.ok and r.json().get("totalFound"):
            return "smartrecruiters", {"company": slug}, r.json()["totalFound"]

    return None


def main(names):

    listings = simplify.fetch_listings()

    for name in names:

        found, hosts = from_simplify(name, listings)

        if found:
            (ats, params), n = found.most_common(1)[0]
            print(f"{name}: {ats} {dict(params)}  ({n} Simplify links)")
            continue

        hit = probe(name)

        if hit:
            print(f"{name}: {hit[0]} {hit[1]}  (probe, {hit[2]} open jobs)")
        else:
            top = ", ".join(h for h, _ in hosts.most_common(2)) or "no Simplify links"
            print(f"{name}: not found ({top})")


if __name__ == "__main__":
    main(sys.argv[1:])
