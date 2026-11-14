from tracker.location import NON_US, UNKNOWN, US, classify_location


def test_locations():
    assert classify_location("Boca Raton, FL") == US
    assert classify_location("USA - California - Irvine") == US
    assert classify_location("Suzhou, China") == NON_US
    assert classify_location("Toronto, ON, CA") == NON_US
    assert classify_location("London, KY") == US
    assert classify_location("NLD - North Brabant - Boxmeer") == NON_US
    assert classify_location("4 Locations") == UNKNOWN
    assert classify_location("Boston, MA; Toronto, Canada") == US


def test_country_codes_that_look_like_states():
    assert classify_location("Haifa, Haifa District, IL") == NON_US
    assert classify_location("Haifa, IL") == NON_US
    assert classify_location("Hyderabad, TS, IN") == NON_US
    assert classify_location("Toronto, CA") == NON_US
    # ...while real US places with the same codes stay US.
    assert classify_location("Chicago, IL") == US
    assert classify_location("Carmel, IN") == US
    assert classify_location("Hunt Valley, Cockeysville, MD") == US
    assert classify_location("Newark, DE") == US
    assert classify_location("Irvine, CA") == US
