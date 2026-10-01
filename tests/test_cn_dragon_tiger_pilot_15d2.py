import pytest

from service.market.cn_dragon_tiger_pilot_15d2 import (
    compare,
    is_cn_a_equity_code,
    parse_szse_page,
    sanitize_vendor,
)


def test_szse_parser_requires_correct_date_and_catalog() -> None:
    response = [{"metadata": {"catalogid": "1842_xxpl_after", "pageno": 1,
                              "pagecount": 1, "recordcount": 1},
                 "data": [{"dqrq": "2024-01-31", "zqdm": "000037",
                           "plyy": "日价格振幅达到22.31%"}]}]
    rows, meta = parse_szse_page(response, "2024-01-31", 1)
    assert rows[0]["code"] == "000037"
    assert meta["reported_rows"] == 1
    with pytest.raises(RuntimeError, match="date mismatch"):
        parse_szse_page(response, "2024-02-01", 1)
    response[0]["metadata"]["catalogid"] = "1842_xxpl"
    assert parse_szse_page(response, "2024-01-31", 1)[0][0]["code"] == "000037"
    response[0]["metadata"]["catalogid"] = "1265"
    with pytest.raises(RuntimeError, match="catalog or page mismatch"):
        parse_szse_page(response, "2024-01-31", 1)


def test_eastmoney_sanitizer_never_persists_future_returns_or_success_text() -> None:
    row = {"TRADE_DATE": "2024-01-31 00:00:00",
           "SECURITY_CODE": "600629", "MARKET": "SH",
           "EXPLANATION": "涨幅偏离", "CHANGE_TYPE": "137",
           "D1_CLOSE_ADJCHRATE": 50.0, "EXPLAIN": "成功率99%",
           "FREE_MARKET_CAP": 123}
    safe = sanitize_vendor(row, "2024-01-31")
    assert safe == {"change_type": "137", "explanation": "涨幅偏离",
                    "market": "SH", "security_code": "600629",
                    "trade_date": "2024-01-31 00:00:00"}
    assert sanitize_vendor({**row, "MARKET": "BJ"}, "2024-01-31") is None
    assert sanitize_vendor({**row, "EXPLANATION": "当日融资买入数量达到50%"}, "2024-01-31") is None
    assert sanitize_vendor({**row, "SECURITY_CODE": "900903"}, "2024-01-31") is None
    assert sanitize_vendor({**row, "SECURITY_CODE": "118062"}, "2024-01-31") is None
    assert is_cn_a_equity_code("SH", "688787")
    assert is_cn_a_equity_code("SZ", "301141")
    with pytest.raises(RuntimeError, match="date mismatch"):
        sanitize_vendor(row, "2024-02-01")


def test_compare_uses_market_and_code_not_unverified_reason() -> None:
    sse = [{"exchange": "SSE", "code": "600629", "date": "2024-01-31",
            "reason_code": "1"}]
    szse = [{"exchange": "SZSE", "code": "000037", "date": "2024-01-31",
             "reason": "振幅"}]
    vendor = [{"market": "SH", "security_code": "600629"},
              {"market": "SZ", "security_code": "300117"}]
    result = compare("2024-01-31", sse, szse, vendor)
    assert result["matched_symbol_exchanges"] == 1
    assert result["official_only"] == [["SZ", "000037"]]
    assert result["vendor_only"] == [["SZ", "300117"]]
    assert result["reason_level_comparable"] is False
