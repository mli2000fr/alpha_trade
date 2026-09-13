from __future__ import annotations

from datetime import date

from service.forward_pit.options_delayed import (
    parse_occ_rss,
    select_atm_contracts,
    trade_bar_comparison,
)


def test_occ_rss_keeps_only_contract_adjustment_memos() -> None:
    xml = b"""<?xml version="1.0"?>
    <rss><channel>
      <item><title>OCC Information Memo #60001</title>
        <description>Reverse split - Option Symbol: ABC - New Option Symbol: ABC1</description>
        <link>https://example.test/60001</link>
        <pubDate>Fri, 11 Sep 2026 14:00:00 GMT</pubDate>
        <category>Contract Adjustments</category></item>
      <item><title>OCC Information Memo #60002</title>
        <description>Unrelated notice</description>
        <category>Market Data</category></item>
    </channel></rss>"""
    rows = parse_occ_rss(xml)
    assert len(rows) == 1
    assert rows[0]["memo"] == "60001"
    assert rows[0]["adjustment_type"] == "REVERSE_SPLIT"
    assert rows[0]["old_root"] == "ABC"
    assert rows[0]["new_root"] == "ABC1"
    assert rows[0]["published"].isoformat() == "2026-09-11T14:00:00"


def test_atm_selection_is_one_call_and_put_per_target_expiry() -> None:
    contracts = [
        {"symbol": "C99", "expiration_date": "2026-09-18", "strike_price": "99", "type": "call"},
        {"symbol": "C101", "expiration_date": "2026-09-18", "strike_price": "101", "type": "call"},
        {"symbol": "P99", "expiration_date": "2026-09-18", "strike_price": "99", "type": "put"},
        {"symbol": "P101", "expiration_date": "2026-09-18", "strike_price": "101", "type": "put"},
        {"symbol": "C120", "expiration_date": "2026-10-02", "strike_price": "120", "type": "call"},
    ]
    selected = select_atm_contracts(
        contracts, spot=100.0, as_of=date(2026, 9, 11),
        target_dtes=(7,), tolerance_days=1,
    )
    assert {row["symbol"] for row in selected} == {"C99", "P99"}


def test_trade_bar_comparison_exposes_volume_count_and_vwap_consistency() -> None:
    result = trade_bar_comparison(
        [{"p": 2.0, "s": 2}, {"p": 4.0, "s": 1}],
        [{"v": 3, "n": 2, "vw": 8 / 3}],
    )
    assert result["volume_ratio_raw_vs_bars"] == 1.0
    assert result["trade_count_ratio_raw_vs_bars"] == 1.0
    assert result["raw_vwap"] == 8 / 3
    assert result["vwap_relative_error"] == 0.0

