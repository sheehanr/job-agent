from tracker import notify


def p(i, company, title, loc="Austin, TX", **kw):
    d = {"id": i, "company": company, "title": title, "url": f"https://x/{i}",
         "locations": [loc], "judgment": {"reason": "Backend SWE", "pay": None}}
    d.update(kw)
    return d


def test_single_role():
    [n] = notify.build([p(1, "Stripe", "SWE Intern")], "https://dash.example", "s3cret")
    assert n["title"] == "Stripe - SWE Intern"
    assert n["message"].startswith("https://x/1\n(Austin, TX)")
    assert n["click"] == "https://x/1"
    labels = [a["label"] for a in n["actions"]]
    assert labels == ["Not a fit: role", "Not a fit: company"]
    assert "ids=1&kind=role&sig=" in n["actions"][0]["url"]


def test_same_role_several_locations():
    [n] = notify.build([p(1, "Lockheed", "Embedded Intern"),
                        p(2, "Lockheed", "Embedded Intern", "Denver, CO")])
    assert n["title"] == "Lockheed - Embedded Intern"
    assert "https://x/1\n(Austin, TX)\n\nhttps://x/2\n(Denver, CO)" in n["message"]
    assert n["click"] is None


def test_company_with_two_roles():
    [n] = notify.build([p(1, "Meta", "ML Intern"), p(2, "Meta", "SWE Intern")])
    assert n["title"] == "Meta - 2 new roles"
    assert n["message"] == "ML Intern: https://x/1\n(Austin, TX)\n\nSWE Intern: https://x/2\n(Austin, TX)"


def test_no_buttons_without_dashboard():
    [n] = notify.build([p(1, "Stripe", "SWE Intern")])
    assert n["actions"] == []


def test_signature_is_order_independent():
    assert notify.sign([2, 1], "role", "k") == notify.sign([1, 2], "role", "k")
    assert notify.sign([1], "role", "k") != notify.sign([1], "company", "k")
