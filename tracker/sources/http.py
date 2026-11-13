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
