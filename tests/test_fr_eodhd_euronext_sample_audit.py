from modelFactory.fr_eodhd_euronext_sample_audit import compare_rows, parse_reference


def test_header_mapping_separates_last_close_and_volume():
    html = '''<table id="AwlHistoricalPriceTable"><thead><tr>
    <th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Last</th><th>Close</th>
    <th>Number of shares</th></tr></thead><tbody><tr>
    <td>02/01/2025</td><td>10</td><td>1,297.00</td><td>9</td><td>10.4</td><td>10.5</td>
    <td>1,234,567</td></tr></tbody></table>'''
    rows = parse_reference(html)
    assert rows["2025-01-02"]["close"] == 10.5
    assert rows["2025-01-02"]["volume"] == 1234567
    assert rows["2025-01-02"]["high"] == 1297.


def test_missing_not_counted_as_wrong_price():
    ref = {"2025-01-02": {"open": None, "high": 10, "low": 9, "close": 10, "volume": 0}}
    got = {"2025-01-02": {"open": 10, "high": 10, "low": 9, "close": 10, "volume": 0}}
    result, differences = compare_rows(ref, got)
    assert result["counts"]["unpaired_price_rows"] == 1
    assert result["counts"].get("paired_price_rows", 0) == 0
    assert differences[0]["kind"] == "MISSING_OR_INVALID_PRICE"


def test_exact_and_practical_tolerances_distinct():
    ref = {"2025-01-02": {"open": 10, "high": 10, "low": 10, "close": 10, "volume": None}}
    got = {"2025-01-02": {"open": 10.001, "high": 10, "low": 10, "close": 10, "volume": 0}}
    result, differences = compare_rows(ref, got)
    assert result["counts"]["paired_price_rows"] == 1
    assert result["counts"]["ohlc_match_0001eur"] == 0
    assert result["counts"]["ohlc_match_10bps"] == 1
    assert result["counts"].get("volume_compared", 0) == 0
    assert differences[0]["field"] == "open"
