"""
The AI filter: reads a posting (full description when available) against
config/profile.md and returns a structured judgment.

Provider: Gemini on Vertex AI (Google Cloud billing). The model and
thinking level are set in config/settings.yaml.
"""

import json
import os
import tempfile
from typing import Literal, Optional

from pydantic import BaseModel, Field

from tracker.config import env

DESCRIPTION_CHARS = 7000


class Judgment(BaseModel):
    internship_evidence: str = Field(description="Quote the words in the DESCRIPTION (not the "
                                     "listing title) showing this is an internship or co-op for "
                                     "students, e.g. 'currently pursuing a degree', 'summer intern "
                                     "program'. Empty string if the description has none.")
    is_internship: bool = Field(description="An internship or co-op for current students "
                                "(not full-time, new-grad, contract or apprenticeship). If a "
                                "description is provided and internship_evidence is empty, "
                                "this is false.")
    term: str = Field(description='Season and year the role runs, e.g. "Fall 2027", '
                      '"Summer 2027", "Spring 2027". For a co-op spanning several seasons, '
                      'list each, e.g. "Summer 2027, Fall 2027". "Unspecified" if not stated.')
    undergrad_eligible: bool = Field(description="Open to undergraduate (Bachelor's) students. "
                                     "False if it requires being in a Master's, PhD or MBA program.")
    us_location: bool = Field(description="Can be done from at least one US location "
                              "(or remote in the US).")
    role_fit: Literal["strong", "partial", "none"] = Field(
        description="How well the actual work matches the roles in the profile.")
    company_tier: Literal["top", "strong", "standard"] = Field(
        description="Using the profile's definition of top tier.")
    beats_current_offer: bool = Field(description="Would this internship beat the person's "
                                      "current Summer offer, by the profile's rules (pay, resume "
                                      "name, Florida, full-time conversion over $100k)?")
    blocked_category: bool = Field(description="The company falls into one of the excluded "
                                   "kinds of company.")
    pay: Optional[str] = Field(default=None, description='Pay if the posting states it, '
                               'e.g. "$45-55/hr". Null if not stated.')
    verdict: Literal["alert", "maybe", "skip"] = Field(
        description="alert = a good match worth a phone notification; maybe = borderline; "
        "skip = not a fit.")
    reason: str = Field(description="One short line (max ~15 words) on what the role is and "
                        "why it fits or doesn't, e.g. 'Backend SWE on payments infra; strong fit'.")


class CompanyTier(BaseModel):
    company: str
    tier: Literal["top", "strong", "standard"]


class CompanyTiers(BaseModel):
    companies: list[CompanyTier]


def _system_prompt(cfg, feedback):

    liked = ", ".join(c.name for c in cfg.companies)
    blocked = "\n".join(f"- {c}" for c in cfg.blocked_categories)
    lines = [
        "You screen job postings for one person, using their profile below. Read the "
        "posting carefully and fill in every field from what it actually says. Postings "
        "from aggregators are sometimes mislabeled (e.g. a full-time role listed as an "
        "internship) - trust the description over the listing's title or tags. The "
        "description may begin with the posting page's own title: if that title has no "
        "intern/co-op/student wording and the text reads like a regular job (no mention "
        "of students, graduation dates or an internship program), set is_internship=false "
        "even when the listing calls it an internship. An employment type of FULL_TIME "
        "alone doesn't decide it - many internships are full-time hours.",
        "",
        "# Profile",
        cfg.profile.strip(),
        "",
        "# Companies on their radar (they like these; others can still be good)",
        liked,
        "",
        "# Excluded kinds of company (set blocked_category=true)",
        blocked,
    ]

    if feedback:
        lines += ["", "# Postings they marked as not a fit recently (learn from these)"]
        for f in feedback:
            why = f" - {f['feedback_reason']}" if f.get("feedback_reason") else ""
            what = "the company" if f.get("feedback_kind") == "company" else "the role"
            lines.append(f"- {f['company']}: {f['title']} (didn't like {what}){why}")

    lines += ["", "If no description is provided, judge from the title and company only, "
              "and prefer 'maybe' over 'alert' when unsure."]

    return "\n".join(lines)


def _posting_prompt(p):

    parts = [
        f"Company: {p['company']}",
        f"Title: {p['title']}",
        f"Locations: {'; '.join(p.get('locations') or []) or 'not listed'}",
    ]
    if p.get("terms"):
        parts.append(f"Terms listed: {', '.join(p['terms'])}")
    if p.get("degrees"):
        parts.append(f"Degrees listed: {', '.join(p['degrees'])}")
    if p.get("url"):
        parts.append(f"Link: {p['url']}")

    desc = (p.get("description") or "").strip()
    parts.append("")
    parts.append("Description:" if desc else "Description: UNAVAILABLE (judge from the title)")
    if desc:
        parts.append(desc[:DESCRIPTION_CHARS])

    return "\n".join(parts)


class GeminiVertex:

    def __init__(self, ai_settings):

        from google import genai
        from google.genai import types

        self.types = types
        self.model = ai_settings.get("model", "gemini-3.8-flash")
        self.thinking = str(ai_settings.get("thinking", "low")).upper()

        # In GitHub Actions the service-account key arrives as a secret string.
        key_json = os.environ.get("GCP_SA_KEY")
        if key_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
            f.write(key_json)
            f.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
        elif not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            local = os.path.join(os.path.dirname(__file__), "..", "gcp-key.json")
            if os.path.exists(local):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(local)

        self.client = genai.Client(
            vertexai=True,
            project=env("GCP_PROJECT_ID", required=True),
            location=ai_settings.get("location", "global"),
        )

    def _ask(self, system, prompt, schema, max_tokens):

        t = self.types
        config = t.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
            thinking_config=t.ThinkingConfig(thinking_level=getattr(t.ThinkingLevel, self.thinking)),
        )
        response = self.client.models.generate_content(
            model=self.model, contents=prompt, config=config)

        return schema.model_validate_json(response.text), response.usage_metadata

    def judge(self, system, posting):
        return self._ask(system, _posting_prompt(posting), Judgment, 4000)

    def tiers(self, system, names):
        prompt = ("Rate each company's tier using the profile's definition of top tier. "
                  "Return every company exactly as written.\n\n" + "\n".join(names))
        return self._ask(system, prompt, CompanyTiers, 8000)


PROVIDERS = {"gemini-vertex": GeminiVertex}


class Judge:
    """Judges postings and rates companies, with token usage tracked."""

    def __init__(self, cfg, feedback=()):

        ai_settings = cfg.settings.get("ai") or {}
        provider = ai_settings.get("provider", "gemini-vertex")
        self.backend = PROVIDERS[provider](ai_settings)
        self.model = f"{provider}:{ai_settings.get('model')}"
        self.system = _system_prompt(cfg, list(feedback))
        self.usage = {"calls": 0, "input": 0, "output": 0, "thinking": 0}

    def _count(self, usage):
        self.usage["calls"] += 1
        self.usage["input"] += getattr(usage, "prompt_token_count", 0) or 0
        self.usage["output"] += getattr(usage, "candidates_token_count", 0) or 0
        self.usage["thinking"] += getattr(usage, "thoughts_token_count", 0) or 0

    def judge(self, posting):
        judgment, usage = self.backend.judge(self.system, posting)
        self._count(usage)
        return judgment.model_dump()

    def company_tiers(self, names, batch=80):
        out = {}
        names = sorted(set(names))
        for i in range(0, len(names), batch):
            result, usage = self.backend.tiers(self.system, names[i:i + batch])
            self._count(usage)
            for item in result.companies:
                out[item.company] = item.tier
        return out


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)
