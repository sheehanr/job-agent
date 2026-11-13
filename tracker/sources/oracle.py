"""Oracle Cloud HCM career sites (*.oraclecloud.com), via the public REST API."""

from tracker.sources.http import html_to_text
from tracker.text import SEARCH_TERMS, is_internship


def _api(site):
    return f"https://{site['host']}/hcmRestApi/resources/latest"


def fetch(company, site, s):

    found = {}

    for term in SEARCH_TERMS:
        for offset in range(0, 500, 50):
            finder = (f"findReqs;siteNumber={site['site']},keyword={term},"
                      f"limit=50,offset={offset},sortBy=POSTING_DATES_DESC")
            r = s.get(f"{_api(site)}/recruitingCEJobRequisitions",
                      params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                              "finder": finder}, timeout=30)
            r.raise_for_status()
            items = r.json().get("items") or [{}]
            reqs = items[0].get("requisitionList") or []

            for req in reqs:
                title = req.get("Title") or ""
                if req["Id"] in found or not is_internship(title):
                    continue
                locs = [req.get("PrimaryLocation") or ""]
                locs += [l.get("Name") or "" for l in req.get("secondaryLocations") or []]
                found[req["Id"]] = {
                    "source": "oracle",
                    "source_key": f"oracle:{site['host']}:{req['Id']}",
                    "company": company.name,
                    "title": title,
                    "locations": [l for l in locs if l],
                    "url": (f"https://{site['host']}/hcmUI/CandidateExperience/en/sites/"
                            f"{site['site']}/job/{req['Id']}"),
                    "site": site,
                    "job_id": req["Id"],
                }

            if len(reqs) < 50:
                break

    return list(found.values())


def describe(site, job_id, s):

    r = s.get(f"{_api(site)}/recruitingCEJobRequisitionDetails",
              params={"expand": "all", "onlyData": "true",
                      "finder": f'ById;Id="{job_id}",siteNumber={site["site"]}'},
              timeout=30)
    r.raise_for_status()
    items = r.json().get("items") or [{}]
    job = items[0]
    text = "\n\n".join(html_to_text(job.get(k)) for k in (
        "ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")
        if job.get(k))
    locs = [job.get("PrimaryLocation") or ""]

    return text, [l for l in locs if l]
