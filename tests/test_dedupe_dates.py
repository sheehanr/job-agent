from datetime import datetime, timezone

from tracker.pipeline import _same_posting
from tracker.sources.http import plausible_posted
from tracker.text import same_link


def test_same_link_needs_an_id():
    assert same_link("https://wd5.myworkdayjobs.com/X/job/Austin/SWE-Intern_JR123456",
                     "https://wd5.myworkdayjobs.com/en-US/X/job/Austin/SWE-Intern_JR123456?src=simplify")
    assert not same_link("https://a.com/jobs/apply", "https://b.com/careers/apply")
    assert not same_link("https://a.com/job/111111", "https://a.com/job/222222")


def test_cross_source_duplicates():
    # LinkedIn: company site vs Simplify, same job link, different titles.
    linkedin = {"title": "Software Engineer Intern (First Play) - Summer 2027 (Mountain View, CA)",
                "url": "https://jobs.smartrecruiters.com/LinkedIn3/744000123456789"}
    simplify = {"title": "Software Engineer Intern - First Play",
                "url": "https://jobs.smartrecruiters.com/LinkedIn3/744000123456789"}
    assert _same_posting(linkedin, simplify)


def test_different_roles_stay_separate():
    a = {"title": "Embedded Engineering Internship - Summer 2027", "url": "https://q.com/job/3001234"}
    b = {"title": "Machine Learning & Artificial Intelligence Engineering Internship",
         "url": "https://q.com/job/3001299"}
    c = {"title": "Security (Product, Systems, Cyber) Engineering Internship",
         "url": "https://q.com/job/3001300"}
    assert not _same_posting(a, b) and not _same_posting(a, c) and not _same_posting(b, c)


def test_evergreen_dates_are_unknown():
    old = datetime(2023, 8, 4, tzinfo=timezone.utc)
    assert plausible_posted(old, "Software Engineering Intern (2027)") is None
    recent = datetime(2026, 9, 15, tzinfo=timezone.utc)
    assert plausible_posted(recent, "Software Engineering Intern (2027)") == recent
    # Ramp-style: early but plausible for a 2027 role.
    spring = datetime(2026, 4, 9, tzinfo=timezone.utc)
    assert plausible_posted(spring, "Software Engineering Intern, Backend") == spring
