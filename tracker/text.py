"""
Small text helpers shared by the rules, the sources and the dedupe:
spotting internships, reading terms out of titles, normalising titles
for comparison, and a cheap "is this obviously not a tech role" check.

The AI filter makes the real decision; these only throw out postings
that are clearly irrelevant, so the AI isn't paid to read them.
"""

import difflib
import re

# "intern", "internship", "co-op" and its spellings, "cooperative
# education", "student" programs. Word-bounded so "internal" and
# "international" don't match.
INTERN_RE = re.compile(
    r"\bintern(s|ship|ships)?\b|\bco-?\s?op\b|\bcoop\b|"
    r"\bcooperative education\b|\bstudent (researcher|worker|program)\b|"
    r"\bsummer (analyst|associate)\b",
    re.IGNORECASE,
)

COOP_RE = re.compile(r"\bco-?\s?op\b|\bcoop\b|\bcooperative education\b", re.I)

TERM_RE = re.compile(r"\b(spring|summer|fall|autumn|winter)\s*'?(20\d\d|\d\d)\b", re.I)

# Search words for job sites that need a query.
SEARCH_TERMS = ["intern", "co-op", "coop"]

_TECH_RE = re.compile(
    r"software|developer|\bsde\b|\bswe\b|devops|\bsre\b|reliability|platform|"
    r"backend|back-end|frontend|front-end|full[- ]?stack|mobile|\bios\b|android|"
    r"data|machine learning|\bml\b|\bai\b|artificial intelligence|deep learning|"
    r"computer vision|\bnlp\b|\bllm|analytics|scientist|research|"
    r"embedded|firmware|robot|autonom|controls?\b|perception|"
    r"\bit\b|information technology|information systems|cyber|security|"
    r"cloud|infrastructure|systems|network|database|web|application|"
    r"computer|computing|computational|bioinformatic|informatics|digital|"
    r"automation|test|verification|validation|fpga|asic|hardware|electrical|"
    r"technology|technical|engineer|engineering|product|programm|code|coding",
    re.IGNORECASE,
)

# Roles that are clearly not technical. Only used to drop postings that
# have none of the tech words above.
_NON_TECH_RE = re.compile(
    r"marketing|sales|account(ing|ant)|finance|financial|tax|audit|"
    r"human resources|\bhr\b|talent|recruit|legal|paralegal|counsel|"
    r"communications|public relations|events?\b|brand|"
    r"supply chain|procurement|purchasing|logistics|warehouse|"
    r"regulatory|clinical|medical affairs|pharmac|nurs|"
    r"quality (assurance|control)?|manufacturing|production|operations|"
    r"mechanical|chemical|chemistry|biolog|lab(oratory)?\b|"
    r"facilities|environmental|safety|design intern|graphic|"
    r"business development|strategy|consult|treasury|real estate",
    re.IGNORECASE,
)


def is_internship(title):

    return bool(INTERN_RE.search(title or ""))


def is_coop(text):

    return bool(COOP_RE.search(text or ""))


def terms_in(text):
    """['Fall 2027', ...] for every season + year mentioned in text."""

    found = []

    for season, year in TERM_RE.findall(text or ""):
        season = "Fall" if season.lower() == "autumn" else season.capitalize()
        year = year if len(year) == 4 else f"20{year}"
        term = f"{season} {year}"
        if term not in found:
            found.append(term)

    return found


def looks_non_tech(title):
    """True only when a title has non-tech words and no tech words."""

    title = title or ""

    return bool(_NON_TECH_RE.search(title)) and not _TECH_RE.search(
        _NON_TECH_RE.sub(" ", title)
    )


_TITLE_NOISE_RE = re.compile(
    r"\(.*?\)|\[.*?\]|\b(spring|summer|fall|autumn|winter)\b|\b20\d\d\b|"
    r"\b(intern(ship)?s?|co-?\s?op|coop|student|program|undergraduate|"
    r"undergrad|university|early careers?)\b|\bjr\d+\b|\br\d{4,}\b",
    re.IGNORECASE,
)


def title_key(title):
    """Title reduced to its meaningful words, sorted, for comparisons."""

    text = _TITLE_NOISE_RE.sub(" ", (title or "").lower())
    words = re.sub(r"[^a-z0-9+#]", " ", text).split()

    return " ".join(sorted(set(words)))


def same_role(title_a, title_b, threshold=0.85):
    """Whether two titles at the same company are the same role."""

    a, b = title_key(title_a), title_key(title_b)

    if not a or not b:
        return False

    if a == b:
        return True

    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold
