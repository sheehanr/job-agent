from tracker.text import is_internship, looks_non_tech, same_role, terms_in, title_key


def test_internship_words():
    assert is_internship("Software Engineering Intern")
    assert is_internship("Co-op, DevOps Engineer: January - June 2027")
    assert is_internship("Embedded Software Coop")
    assert is_internship("Summer Internship - Data")
    assert not is_internship("Internal Audit Manager")
    assert not is_internship("International Sales Lead")


def test_terms_in_titles():
    assert terms_in("Software Intern (Fall 2027)") == ["Fall 2027"]
    assert terms_in("Summer 2027 / Fall 2027 Co-op") == ["Summer 2027", "Fall 2027"]
    assert terms_in("Intern, Autumn '27") == ["Fall 2027"]
    assert terms_in("Software Intern") == []


def test_non_tech_needs_no_tech_words():
    assert looks_non_tech("Marketing Intern")
    assert looks_non_tech("Tax Intern")
    assert not looks_non_tech("Marketing Data Engineering Intern")
    assert not looks_non_tech("Software Quality Engineer Intern")
    assert not looks_non_tech("Software Engineering Intern")


def test_same_role_ignores_noise():
    assert same_role("Software Engineer Intern (Summer 2027)", "Software Engineer Intern - Summer")
    assert same_role("2027 - Software Engineering Intern, AMER", "Software Engineering Intern AMER")
    assert not same_role("Software Engineer Intern", "Data Scientist Intern")
    assert title_key("Software Engineer Intern (Fall 2027)") == "engineer software"
