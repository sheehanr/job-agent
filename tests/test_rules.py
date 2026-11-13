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
                         profile="")


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
         "us_location": True, "company_tier": "strong", "blocked_category": False,
         "verdict": "alert", "reason": "Backend SWE; strong fit"}
    j.update(kw)
    return j


def test_final_verdict(cfg):
    p = simplify(terms=[])
    assert rules.final_verdict(p, judgment(), cfg) == ("alert", "Backend SWE; strong fit")
    assert rules.final_verdict(p, judgment(is_internship=False), cfg)[0] == "skip"
    assert rules.final_verdict(p, judgment(undergrad_eligible=False), cfg)[0] == "skip"
    assert rules.final_verdict(p, judgment(blocked_category=True), cfg)[0] == "skip"
    # Summer 2027 only counts at top-tier companies.
    assert rules.final_verdict(p, judgment(term="Summer 2027"), cfg)[0] == "skip"
    assert rules.final_verdict(p, judgment(term="Summer 2027", company_tier="top"), cfg)[0] == "alert"
    # ...or wherever the AI says it beats the current offer (e.g. Florida).
    assert rules.final_verdict(p, judgment(term="Summer 2027", beats_current_offer=True), cfg)[0] == "alert"
    assert rules.final_verdict(p, judgment(term="Summer 2027", company_tier="top",
                                           beats_current_offer=False), cfg)[0] == "skip"
    # A co-op spanning summer and fall counts.
    assert rules.final_verdict(p, judgment(term="Summer 2027, Fall 2027"), cfg)[0] == "alert"
    assert rules.final_verdict(p, judgment(term="Spring 2027"), cfg)[0] == "skip"


def test_in_florida():
    assert rules.in_florida({"locations": ["Weston, FL"]})
    assert rules.in_florida({"locations": ["Juno Beach, Florida"]})
    assert not rules.in_florida({"locations": ["Flint, MI"]})
