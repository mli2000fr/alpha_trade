import json
from datetime import date, datetime
from decimal import InvalidOperation

import pytest

from service.market.cn_margin_lending_pilot import SZSE_FIELDS
from service.market.cn_szse_margin_dataset import (
    build_rows,
    dated_equities,
    integer_value,
    reference_snapshot,
)


@pytest.mark.parametrize("value", ["-1", "0.5", "NaN", "Infinity", ""])
def test_nonwhole_and_missing_values_rejected(value):
    with pytest.raises((ValueError, InvalidOperation)):
        integer_value(value)


def test_dated_reference_excludes_future_and_delisted():
    items = [{"instrument_id": 1, "local_symbol": "000001", "listing_date": date(2010, 1, 1),
              "delisting_date": None},
             {"instrument_id": 2, "local_symbol": "000002", "listing_date": date(2025, 1, 1),
              "delisting_date": None},
             {"instrument_id": 3, "local_symbol": "000003", "listing_date": date(2010, 1, 1),
              "delisting_date": date(2017, 1, 1)}]
    assert dated_equities(items, date(2018, 1, 1)) == {"000001": 1}


def test_snapshot_serializes_sql_row_values_as_pairs_not_repr():
    snapshot = reference_snapshot(
        [{"listing_date": date(2010, 1, 1), "delisting_date": None}],
        [(date(2018, 1, 1), datetime(2018, 1, 1, 7))])
    loaded = json.loads(json.dumps(snapshot))
    assert loaded["sessions"] == [["2018-01-01", "2018-01-01T07:00:00"]]
    assert loaded["instruments"][0]["listing_date"] == "2010-01-01"


def test_missing_not_zero_and_non_equity_excluded(monkeypatch):
    flags = {"000001": {"融资标的": True, "融券标的": True},
             "159001": {"融资标的": True, "融券标的": True}}
    monkeypatch.setattr("service.market.cn_szse_margin_dataset.eligibility_rows", lambda raw: flags)
    monkeypatch.setattr("service.market.cn_szse_margin_dataset.read_xlsx_rows", lambda raw: [])
    rows, stats = build_rows(date(2018, 1, 1), b"", b"", {"000001": 1}, {}, None)
    assert len(rows) == 1
    assert rows[0]["measures"] is None
    assert rows[0]["financing_buy_to_amount"] is None
    assert "CALENDAR_PROXY_UNAVAILABLE" in rows[0]["quality_reasons"]
    assert stats["non_equity_or_outside_reference"] == 1


def test_ratio_uses_same_day_cny_and_zero_is_observed(monkeypatch):
    flags = {"000001": {"融资标的": True, "融券标的": True}}
    row = {"证券代码": "000001", **dict.fromkeys(SZSE_FIELDS, "0")}
    row["融资买入额"] = "10"
    monkeypatch.setattr("service.market.cn_szse_margin_dataset.eligibility_rows", lambda raw: flags)
    monkeypatch.setattr("service.market.cn_szse_margin_dataset.read_xlsx_rows", lambda raw: [row])
    bar = {"amount": 100, "trading_status": "TRADE", "observed_at": None, "available_at": None}
    rows, _ = build_rows(date(2018, 1, 1), b"", b"", {"000001": 1}, {1: bar}, "2018-01-03T07:00:00Z")
    assert rows[0]["financing_buy_to_amount"] == 0.1
    assert rows[0]["strict_ml_allowed"] is False
    row["融资买入额"] = "0"
    rows, _ = build_rows(date(2018, 1, 1), b"", b"", {"000001": 1}, {1: bar}, "proxy")
    assert rows[0]["observation_status"] == "OBSERVED_ZERO"
