from service.fr.euronext_delisted_reference import _number, audit_rows, parse_historical_html


def test_number_accepts_repeated_thousands_separator():
    assert _number("1.180.00") == 1180.0


def test_parse_historical_html_and_audit_exact_dates():
    html = """
    <table id="AwlHistoricalPriceTable"><tbody>
      <tr><td>03/02/2025</td><td>259,80</td><td>277,40</td><td>259,40</td><td>277,40</td><td>2 718</td></tr>
      <tr><td>04/02/2025</td><td>277,40</td><td>278,00</td><td>277,00</td><td>277,80</td><td>1 000</td></tr>
    </tbody></table>
    """
    reference = parse_historical_html(html)
    provider = {
        "2025-02-03": {"open": 259.8, "high": 277.4, "low": 259.4, "close": 277.4},
        "2025-02-04": {"open": 277.4, "high": 278.0, "low": 277.0, "close": 280.0},
    }
    report = audit_rows(reference, provider)
    assert report["corroborated_dates"] == ["2025-02-03"]
    assert report["difference_days"] == 1
