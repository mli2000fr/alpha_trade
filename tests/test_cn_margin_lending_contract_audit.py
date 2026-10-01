from datetime import UTC, date, datetime

import pytest

from service.market.cn_margin_lending_contract_audit import (
    classify_presence,
    eligibility_rows,
    proxy_available_at,
    reconcile_eligibility,
)


def test_no_unknown_to_zero():
    assert classify_presence(observed=False, eligible=None) == "UNKNOWN_ELIGIBILITY"
    assert classify_presence(observed=False, eligible=True) == "MISSING_SOURCE"
    assert classify_presence(observed=False, eligible=False) == "INELIGIBLE"
    assert classify_presence(observed=True, eligible=True, all_values_zero=True) == "OBSERVED_ZERO"
    assert classify_presence(observed=True, eligible=False) == "OBSERVED_OUTSIDE_ELIGIBLE_LIST"


def test_proxy_uses_sessions_not_calendar_days():
    sessions = [(date(2025, 6, 27), datetime(2025, 6, 27, 7)),
                (date(2025, 6, 30), datetime(2025, 6, 30, 7)),
                (date(2025, 7, 1), datetime(2025, 7, 1, 7))]
    assert proxy_available_at(date(2025, 6, 27), sessions) == datetime(2025, 7, 1, 7, tzinfo=UTC)
    with pytest.raises(ValueError, match="Calendar"):
        proxy_available_at(date(2025, 6, 30), sessions)


def test_coverage_denominator_is_eligible_not_all_equities():
    eligible = {"000001": {"融资标的": True, "融券标的": False,
                          "当日可融资": True, "当日可融券": False}}
    result = reconcile_eligibility(eligible, [{"证券代码": "000001"}], {"000001", "000002"})
    assert result["eligible_active"] == result["eligible_active_with_detail"] == 1
    assert not result["eligible_without_detail"]


@pytest.mark.parametrize("invalid", ["?", None])
def test_unknown_eligibility_is_rejected(monkeypatch, invalid):
    row = {"证券代码": "000001", "融资标的": invalid, "融券标的": "Y",
           "当日可融资": "Y", "当日可融券": "Y"}
    monkeypatch.setattr(
        "service.market.cn_margin_lending_contract_audit.read_xlsx_rows",
        lambda raw: [row],
    )
    with pytest.raises(ValueError, match="Unknown eligibility"):
        eligibility_rows(b"fixture")


def test_missing_close_fails_closed():
    with pytest.raises(ValueError, match="close missing"):
        proxy_available_at(date(2025, 6, 27), [
            (date(2025, 6, 30), datetime(2025, 6, 30, 7)),
            (date(2025, 7, 1), None),
        ])
