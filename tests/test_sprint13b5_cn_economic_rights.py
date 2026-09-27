"""B5 evidence must be exact and must never fabricate a ticker-change right."""

from datetime import date
from decimal import Decimal

import pytest

from modelFactory.cn_economic_remediation_13b5 import SPECS, promote
from modelFactory.cn_portfolio_replay import convert_verified_actions

PRICES = {
    316: ("68.01", "68.00"),
    16255: ("8.94", "8.55"),
    23221: ("24.56", "23.52"),
}


def _fixture(action_id):
    spec = SPECS[action_id]
    close, opening = PRICES[action_id]
    event = {
        "corporate_action_id": action_id,
        "instrument_id": spec["instrument_id"],
        "provider_symbol": spec["symbol"],
        "ex_date": spec["ex_date"],
        "previous_close": close,
        "event_open": opening,
        "factor_value": Decimal(spec["factor"]),
        "previous_factor_value": Decimal(spec["previous_factor"]),
        "source_payload_hash": "a" * 64,
    }
    previous = {
        "corporate_action_id": action_id,
        "instrument_id": spec["instrument_id"],
        "ex_date": spec["ex_date"].isoformat(),
        "status": "UNRESOLVED",
        "reason": spec["old_reason"],
        "source_payload_hash": "a" * 64,
    }
    if action_id == 316:
        rows = [{"code": spec["symbol"], "dividOperateDate": "2025-06-24"}]
    else:
        rows = [{
            "code": spec["symbol"],
            "dividOperateDate": spec["ex_date"].isoformat(),
            "dividPlanDate": spec["record"],
            "dividRegistDate": spec["record"],
            "dividPayDate": spec["ex_date"].isoformat(),
            "dividCashPsBeforeTax": spec["cash"],
            "dividStocksPs": "0.000000",
            "dividReserveToStockPs": "",
            "dividCashStock": "10派现元",
        }]
    return event, rows, previous, spec


@pytest.mark.parametrize("action_id", sorted(SPECS))
def test_exact_b5_event_only(action_id):
    event, rows, previous, spec = _fixture(action_id)
    result = promote(event, rows, previous, spec)
    assert result["original_factor_mismatch_retained"] is True
    assert result["official_issuer_url"] == spec["issuer_url"]
    assert result["status"] == (
        "EVIDENCED_NON_DISTRIBUTION" if action_id == 316
        else "EVIDENCED_DISTRIBUTION"
    )


def test_ticker_change_does_not_generate_right_or_unresolved_bar():
    event, rows, previous, spec = _fixture(316)
    item = promote(event, rows, previous, spec)
    action_row = {
        "corporate_action_id": 316, "instrument_id": 82,
        "ex_date": date(2025, 2, 18), "source_payload_hash": "a" * 64,
    }
    actions, unresolved = convert_verified_actions([action_row], {316: item})
    assert actions == []
    assert unresolved == set()
    actions, unresolved = convert_verified_actions([action_row], {316: previous})
    assert len(actions) == 1
    assert unresolved == {(date(2025, 2, 18), 82)}


def test_wrong_factor_terms_or_raw_price_remains_blocked():
    event, rows, previous, spec = _fixture(16255)
    with pytest.raises(RuntimeError):
        promote(dict(event, factor_value=Decimal("2")), rows, previous, spec)
    with pytest.raises(RuntimeError):
        promote(event, [dict(rows[0], dividCashPsBeforeTax="0.5")], previous, spec)
    with pytest.raises(RuntimeError):
        promote(dict(event, event_open="4.00"), rows, previous, spec)


def test_ambiguous_ticker_date_remains_blocked():
    event, rows, previous, spec = _fixture(316)
    with pytest.raises(RuntimeError):
        promote(event, rows + [{"dividOperateDate": "2025-02-18"}], previous, spec)
