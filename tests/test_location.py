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
