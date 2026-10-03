from modelFactory.fr_official_close_audit import verdict


def test_independent_close_verdict():
    assert verdict(10., 10., 10.000001) == "BOTH_MATCH"
    assert verdict(10., 10., 11.) == "EODHD_ONLY"
    assert verdict(10., 11., 10.) == "YAHOO_ONLY"
    assert verdict(10., 11., 12.) == "NEITHER_MATCH"
    assert verdict(None, 10., 10.) == "OFFICIAL_MISSING"
