from modelFactory.fr_fold7_price_evidence_review import comparison


def test_all_prices_required_for_corroboration():
    prices = {"open": 10., "high": 11., "low": 9., "close": 10.5}
    assert comparison(prices, prices) == "CORROBORATED_OHLC"
    assert comparison(prices, {**prices, "open": 10.2}) == "DIFFERENT_UNRESOLVED"
    assert comparison({**prices, "open": None}, prices) == "MISSING_PRICE_EVIDENCE"
    assert comparison(None, prices) == "MISSING_PRICE_EVIDENCE"
