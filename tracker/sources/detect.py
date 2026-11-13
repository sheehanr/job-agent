"""Recognise which job site (ATS) an apply link belongs to."""

import re
from urllib.parse import parse_qs, urlparse


def ats_from_url(url):
    """Return (type, params) for a recognised ATS apply link, else None."""

    if not url:
        return None

    u = urlparse(url)
    host = u.netloc.lower()
    parts = [p for p in u.path.split("/") if p]

    if host.endswith("myworkdayjobs.com"):
        # https://nvidia.wd5.myworkdayjobs.com/[en-US/]NVIDIAExternalCareerSite/job/...
        tenant = host.split(".")[0]
        if parts and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]):
            parts = parts[1:]
        if parts:
            return "workday", {"host": host, "tenant": tenant, "site": parts[0]}

    if "greenhouse.io" in host:
        # job-boards.greenhouse.io/<token>/jobs/<id>, boards.greenhouse.io/<token>
        if parts and parts[0] not in ("embed",):
            return "greenhouse", {"board": parts[0]}
        m = re.search(r"for=([\w-]+)", u.query)
        if m:
            return "greenhouse", {"board": m.group(1)}

    if host == "jobs.lever.co" and parts:
        return "lever", {"site": parts[0]}

    if host == "jobs.ashbyhq.com" and parts:
        return "ashby", {"org": parts[0]}

    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and parts:
        return "smartrecruiters", {"company": parts[0]}

    if host.endswith(".icims.com"):
        return "icims", {"host": host, "url": url}

    if "oraclecloud.com" in host and "CandidateExperience" in u.path:
        m = re.search(r"/sites/([^/]+)", u.path)
        return "oracle", {"host": host, "site": m.group(1) if m else ""}

    return None


def job_ref(url):
    """
    Everything needed to fetch one posting's description from its apply
    link: (type, params) with the job id included, or None.
    """

    found = ats_from_url(url)
    if not found:
        return None

    kind, params = found
    u = urlparse(url)
    parts = [p for p in u.path.split("/") if p]

    if kind == "workday":
        i = parts.index("job") if "job" in parts else -1
        if i < 0:
            return None
        return kind, {**params, "path": "/" + "/".join(parts[i:])}

    if kind == "greenhouse":
        m = re.search(r"/jobs/(\d+)", u.path) or re.search(r"gh_jid=(\d+)", u.query)
        return (kind, {**params, "job_id": m.group(1)}) if m else None

    if kind in ("lever", "ashby", "smartrecruiters") and len(parts) >= 2:
        return kind, {**params, "job_id": parts[1]}

    if kind == "oracle":
        m = re.search(r"/job/(\d+)", u.path)
        return (kind, {**params, "job_id": m.group(1)}) if m else None

    if kind == "icims":
        return kind, params

    return None
