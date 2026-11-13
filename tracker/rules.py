"""
Cheap, deterministic rules. They run before the AI (to avoid paying it to
read obviously irrelevant postings) and after it (to apply your settings
to what the AI found in the description, e.g. the actual term).
"""

import re

from tracker.location import NON_US, classify_location
from tracker.text import is_internship, looks_non_tech, terms_in

_UNDERGRAD_DEGREES = {"bachelor's", "associate's"}

_GRAD_TITLE_RE = re.compile(
    r"\bph\.?\s?d\b|\bdoctoral\b|\bdoctorate\b|\bpost-?doc|\bmaster'?s\b|\bmasters\b|"
    r"\bmba\b|\bm\.?s\.? students?\b|\bgraduate (student|research)", re.I)
_UNDERGRAD_RE = re.compile(r"\bundergrad|\bbachelor", re.I)
_RESEARCH_SCIENTIST_RE = re.compile(r"\bresearch scientist", re.I)
_NOT_COLLEGE_RE = re.compile(r"\bskill\s?bridge\b|\bhigh school\b|\bapprentice", re.I)

_HARDWARE_OK_RE = re.compile(
    r"embedded|firmware|robot|software|autonom|controls|perception|fpga|"
    r"verification|validation|test automation|machine learning|\bml\b|\bai\b", re.I)


def grad_only(title, degrees):
    """Open only to Master's/PhD/MBA students (from Simplify's degrees or the title)."""

    undergrad_listed = False
    if degrees:
        undergrad_listed = any(str(d).lower() in _UNDERGRAD_DEGREES for d in degrees)
        if not undergrad_listed:
            return True

    title = title or ""
    if _UNDERGRAD_RE.search(title):
        return False
    if _GRAD_TITLE_RE.search(title):
        return True

    # "Research Scientist Intern" is a PhD program unless Simplify says
    # Bachelor's students can apply.
    return bool(_RESEARCH_SCIENTIST_RE.search(title)) and not undergrad_listed


def term_status(terms, settings):
    """
    "target"    - a term you're applying for
    "top_only"  - a term that only counts for top-tier companies
    "unknown"   - no term listed (the AI will look in the description)
    "other"     - only terms you're not applying for
    """

    terms = [t for t in terms or [] if t and t.upper() != "N/A"]
    target = set(settings.get("target_terms") or [])
    top_only = set(settings.get("top_tier_only_terms") or [])

    if not terms:
        return "unknown"
    if any(t in target for t in terms):
        return "target"
    if any(t in top_only for t in terms):
        return "top_only"
    return "other"


def all_terms(posting):
    return list(dict.fromkeys([*(posting.get("terms") or []), *terms_in(posting.get("title"))]))


def pre_ai(posting, cfg):
    """None if the posting should go to the AI, else the reason to skip it."""

    settings = cfg.settings
    title = posting.get("title") or ""

    if cfg.is_blocked(posting.get("company")):
        return "blocked company"
    if not posting.get("active", True):
        return "no longer listed"
    if posting["source"] != "simplify" and not is_internship(title):
        return "not an internship"
    if _NOT_COLLEGE_RE.search(title):
        return "not for college students"

    locations = [l for l in posting.get("locations") or [] if l]
    if locations and all(classify_location(l) == NON_US for l in locations):
        return "outside the US"

    if posting["source"] == "simplify":
        category = posting.get("category") or ""
        allowed = settings.get("simplify_categories") or []
        if category not in allowed:
            return f"category: {category or 'none'}"
        if category == "Hardware" and not _HARDWARE_OK_RE.search(title):
            return "hardware role without software"
    elif looks_non_tech(title):
        return "not a tech role"

    if grad_only(title, posting.get("degrees")):
        return "graduate students only"

    status = term_status(all_terms(posting), settings)
    if status == "other":
        return f"term: {', '.join(all_terms(posting))}"
    if status == "unknown" and not settings.get("include_unspecified_terms", True):
        return "no term listed"

    return None


def final_verdict(posting, judgment, cfg):
    """
    Apply your settings to the AI's reading of the posting. Returns
    (verdict, reason) where verdict is alert | maybe | skip.
    """

    settings = cfg.settings
    j = judgment

    if j.get("blocked_category"):
        return "skip", "excluded kind of company"
    if not j.get("is_internship", True):
        return "skip", "not an internship or co-op"
    if j.get("undergrad_eligible") is False:
        return "skip", "not open to undergrads"
    if j.get("us_location") is False:
        return "skip", "not in the US"

    terms = all_terms(posting)
    ai_term = (j.get("term") or "").strip()
    if ai_term and ai_term.lower() not in ("unspecified", "unknown"):
        terms = list(dict.fromkeys(terms + (terms_in(ai_term) or [ai_term])))
    status = term_status(terms, settings)

    if status == "other":
        return "skip", f"term: {', '.join(terms)}"
    if status == "top_only" and j.get("company_tier") != "top":
        return "skip", f"{ai_term or terms[0]} at a company that isn't top tier"

    return j.get("verdict") or "skip", j.get("reason") or ""
