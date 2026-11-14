"""Shared HTTP session and HTML-to-text helper for the job-site adapters."""

import html as htmllib
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "Mozilla/5.0 (compatible; job-agent/1.0; personal job tracker)"


def session():

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"})
    retry = Retry(total=2, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET", "POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def html_to_text(markup, limit=15000):
    """Readable plain text from a job description's HTML."""

    if not markup:
        return ""

    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
    text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmllib.unescape(htmllib.unescape(text))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()[:limit]


def posted_date(value):
    """
    A posting date from whatever a job site gives: ISO text, epoch seconds
    or milliseconds, or Workday's "Posted 3 Days Ago" / "Posted 30+ Days
    Ago". Returns (datetime or None, approximate). "30+" dates are a
    lower bound, so they're flagged approximate.
    """

    from datetime import datetime, timedelta, timezone

    if value in (None, ""):
        return None, False

    now = datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc), False

    text = str(value).strip()

    m = re.search(r"posted\s+(today|yesterday|(\d+)(\+)?\s+days?\s+ago)", text, re.I)
    if m:
        if m.group(1).lower() == "today":
            return now, False
        if m.group(1).lower() == "yesterday":
            return now - timedelta(days=1), False
        return now - timedelta(days=int(m.group(2))), bool(m.group(3))

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, False

    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)), False



def plausible_posted(posted_at, title, terms=()):
    """
    None if a company site's posting date can't be trusted, else the date.

    Some companies keep one evergreen posting open for years and just
    rename it each cycle (Databricks' "Software Engineering Intern (2027)"
    was first published in 2023), so the "published" date says nothing
    about this year's role. A date more than a year before the earliest
    year the posting mentions, or more than two years old, is treated as
    unknown rather than shown as a misleading age.
    """

    from datetime import datetime, timedelta, timezone

    if posted_at is None:
        return None
    if posted_at < datetime.now(timezone.utc) - timedelta(days=730):
        return None
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", " ".join([title or "", *terms]))]
    if years and posted_at.year < min(years) - 1:
        return None
    return posted_at
