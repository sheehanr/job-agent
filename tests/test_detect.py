from tracker.sources.detect import ats_from_url, job_ref
from tracker.sources.simplify import normalize


def test_job_refs():
    assert job_ref("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/X/Intern_JR1") == (
        "workday", {"host": "nvidia.wd5.myworkdayjobs.com", "tenant": "nvidia",
                    "site": "NVIDIAExternalCareerSite", "path": "/job/X/Intern_JR1"})
    assert job_ref("https://job-boards.greenhouse.io/anthropic/jobs/123") == (
        "greenhouse", {"board": "anthropic", "job_id": "123"})
    assert job_ref("https://jobs.ashbyhq.com/notion/abc") == ("ashby", {"org": "notion", "job_id": "abc"})
    assert job_ref("https://www.metacareers.com/jobs/1") is None


def test_ats_from_url():
    assert ats_from_url("https://jobs.lever.co/veeva/x") == ("lever", {"site": "veeva"})
    assert ats_from_url("https://example.com/careers") is None


def test_normalize_company():
    assert normalize("Insulet Corporation") == "insulet"
    assert normalize("Micron Technology, Inc.") == "micron"
    assert normalize("Johnson & Johnson") == "johnson & johnson"


def test_posted_dates():
    from datetime import datetime, timezone
    from tracker.sources.http import posted_date
    d, approx = posted_date("Posted 30+ Days Ago")
    assert approx and (datetime.now(timezone.utc) - d).days == 30
    d, approx = posted_date("Posted Today")
    assert not approx and (datetime.now(timezone.utc) - d).days == 0
    assert posted_date("2026-10-07T05:33:51-04:00")[0].year == 2026
    assert posted_date(1764950728481)[0].year == 2025
    assert posted_date(1794260791)[0].year == 2026
    assert posted_date(None) == (None, False)
