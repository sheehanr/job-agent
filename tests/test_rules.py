import pytest

from tracker import config, rules

SETTINGS = {
    "target_terms": ["Fall 2027"],
    "top_tier_only_terms": ["Summer 2027"],
    "include_unspecified_terms": True,
    "simplify_categories": ["Software", "AI/ML/Data", "Hardware"],
}


@pytest.fixture
def cfg():
    return config.Config(settings=SETTINGS, companies=[config.Company("Stripe")],
                         blocked_companies={"palantir"}, blocked_categories=["defense"],
                         profile="", blocked_titles=["Government Technologies"])


def simplify(**kw):
    p = {"source": "simplify", "company": "Stripe", "title": "Software Engineer Intern",
         "locations": ["San Francisco, CA"], "terms": ["Fall 2027"], "degrees": [],
         "category": "Software", "active": True}
    p.update(kw)
    return p


def test_passes_good_posting(cfg):
    assert rules.pre_ai(simplify(), cfg) is None


@pytest.mark.parametrize("kw,reason", [
    ({"company": "Palantir"}, "blocked company"),
    ({"title": "Qualcomm Government Technologies Engineering Intern"}, "blocked title"),
    ({"locations": ["Toronto, Canada"]}, "outside the US"),
    ({"category": "Quant"}, "category: Quant"),
    ({"category": "Hardware", "title": "Analog Design Intern"}, "hardware role without software"),
    ({"degrees": ["PhD"]}, "graduate students only"),
    ({"title": "Research Scientist Intern"}, "graduate students only"),
    ({"terms": ["Spring 2027"]}, "term: Spring 2027"),
    ({"title": "High School Software Intern"}, "not for college students"),
    ({"active": False}, "no longer listed"),
])
def test_skips(cfg, kw, reason):
    assert rules.pre_ai(simplify(**kw), cfg) == reason


def test_hardware_with_software_passes(cfg):
    assert rules.pre_ai(simplify(category="Hardware", title="Embedded Firmware Intern"), cfg) is None


def test_research_scientist_ok_when_bachelors_listed(cfg):
    p = simplify(title="Research Scientist Intern", degrees=["Bachelor's"])
    assert rules.pre_ai(p, cfg) is None


def test_term_status():
    assert rules.term_status(["Fall 2027"], SETTINGS) == "target"
    assert rules.term_status(["Summer 2027"], SETTINGS) == "top_only"
    assert rules.term_status(["N/A"], SETTINGS) == "unknown"
    assert rules.term_status([], SETTINGS) == "unknown"
    assert rules.term_status(["Summer 2026"], SETTINGS) == "other"


def test_company_site_non_tech_skipped(cfg):
    p = simplify(source="workday", title="Marketing Intern", terms=[])
    assert rules.pre_ai(p, cfg) == "not a tech role"


def judgment(**kw):
    j = {"is_internship": True, "term": "Fall 2027", "undergrad_eligible": True,
         "us_location": True, "blocked_category": False,
         "verdict": "alert", "reason": "Backend SWE; strong fit"}
    j.update(kw)
    return j


def test_final_verdict(cfg):
    p = simplify(terms=[])
    assert rules.final_verdict(p, judgment(), cfg) == ("alert", "Backend SWE; strong fit")
    # An intern title overrules the AI's "not an internship" (no page title says otherwise).
    assert rules.final_verdict(p, judgment(is_internship=False), cfg)[0] == "alert"
    assert rules.final_verdict({**p, "title": "Data Scientist"}, judgment(is_internship=False), cfg)[0] == "skip"
    assert rules.final_verdict(p, judgment(undergrad_eligible=False), cfg)[0] == "skip"
    assert rules.final_verdict(p, judgment(blocked_category=True), cfg)[0] == "skip"
    # Summer 2027 only counts when it beats the current offer...
    assert rules.final_verdict(p, judgment(term="Summer 2027", beats_current_offer=True), cfg)[0] == "alert"
    assert rules.final_verdict(p, judgment(term="Summer 2027", beats_current_offer=False), cfg)[0] == "skip"
    # ...falling back to the company tier when the AI didn't say.
    assert rules.final_verdict({**p, "tier": 2}, judgment(term="Summer 2027"), cfg)[0] == "alert"
    assert rules.final_verdict({**p, "tier": 3}, judgment(term="Summer 2027"), cfg)[0] == "skip"
    # A co-op spanning summer and fall counts.
    assert rules.final_verdict(p, judgment(term="Summer 2027, Fall 2027"), cfg)[0] == "alert"
    assert rules.final_verdict(p, judgment(term="Spring 2027"), cfg)[0] == "skip"


def test_intern_title_beats_ai_not_internship(cfg):
    # Company-site posting titled "Intern": the AI's "not an internship"
    # is overruled, and its own verdict/reason decide.
    p = simplify(source="workday", title="Failure Analysis Technician - 6 Month Intern 2027", terms=[])
    j = judgment(is_internship=False, verdict="skip", reason="Lab work, no software")
    assert rules.final_verdict(p, j, cfg) == ("skip", "Lab work, no software")
    # Simplify listing whose company page title isn't an internship: AI stands.
    ms = simplify(title="Data Scientist Intern - CoreAI", terms=[],
                  description="Posting page title: Data Scientist, CoreAI\nEmployment type: FULL_TIME")
    assert rules.final_verdict(ms, judgment(is_internship=False), cfg)[0] == "skip"


def test_year_only_term_is_unknown(cfg):
    p = simplify(terms=["N/A"])
    assert rules.final_verdict(p, judgment(term="2027", verdict="maybe"), cfg)[0] == "maybe"
    assert rules.final_verdict(p, judgment(term="Spring 2027, Summer 2027, Fall 2027"), cfg)[0] == "alert"
    reason = rules.final_verdict(p, judgment(term="Spring 2027"), cfg)[1]
    assert "N/A" not in reason and "Spring 2027" in reason
