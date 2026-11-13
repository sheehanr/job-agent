"""Job-site adapters, keyed by the `site.type` used in companies.yaml."""

from tracker.sources import (ashby, eightfold, greenhouse, icims, jibe, lever, oracle,
                             radancy, smartrecruiters, successfactors, workday)

ADAPTERS = {
    "workday": workday,
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "icims": icims,
    "oracle": oracle,
    "eightfold": eightfold,
    "successfactors": successfactors,
    "jibe": jibe,
    "radancy": radancy,
}

# Fields an adapter puts on a posting that describe() needs later.
_REF_FIELDS = ("path", "job_id")


def fetch_company(company, s):
    """Internship postings from one company's own careers site."""

    site = company.site
    adapter = ADAPTERS[site["type"]]
    postings = adapter.fetch(company, site, s)

    for p in postings:
        detail = {k: v for k, v in site.items()}
        for field in _REF_FIELDS:
            if field in p:
                detail[field] = p.pop(field)
        detail["url"] = p.get("url")
        p.pop("site", None)
        p["detail"] = detail

    return postings
