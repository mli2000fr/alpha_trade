"""Issuer-adjusted factor evidence must not relax the general A2 tolerance."""

from decimal import Decimal

import pytest

from modelFactory.cn_economic_remediation_13b4 import SPECS, promote

PRICES = {
    19014: ("15.81", "1.399114601175261535218319323"),
    19015: ("71.69", "1.396377562231220767806133660"),
    24005: ("35.39", "1.033888310409182017579725710"),
}


def _fixture(action_id):
    spec = SPECS[action_id]
    prior, observed = PRICES[action_id]
    event = {
        "corporate_action_id": action_id,
        "instrument_id": spec["instrument_id"],
        "provider_symbol": spec["symbol"],
        "ex_date": spec["ex_date"],
        "previous_close": prior,
        "previous_factor_value": "1",
        "factor_value": observed,
        "source_payload_hash": "a" * 64,
    }
    row = {
        "code": spec["symbol"],
        "dividOperateDate": spec["ex_date"].isoformat(),
        "dividPlanDate": spec["record_date"],
        "dividRegistDate": spec["record_date"],
        "dividPayDate": spec["ex_date"].isoformat(),
        "dividCashPsBeforeTax": spec["cash"],
        "dividStocksPs": "0.000000",
        "dividReserveToStockPs": spec["shares"] if Decimal(spec["shares"]) else "",
        "dividCashStock": "10转4派现" if Decimal(spec["shares"]) else "10派现元",
    }
    previous = {
        "corporate_action_id": action_id,
        "status": "UNRESOLVED",
        "reason": "factor_terms_mismatch",
        "source_payload_hash": "a" * 64,
    }
    return event, row, previous, spec


@pytest.mark.parametrize("action_id", sorted(SPECS))
def test_exact_issuer_dilution_reconciles_factor(action_id):
    event, row, previous, spec = _fixture(action_id)
    result = promote(event, [row], previous, spec)
    assert result["status"] == "EVIDENCED_DISTRIBUTION"
    assert result["reason"] == "official_issuer_buyback_dilution_reconciles_factor"
    assert result["original_factor_mismatch_retained"] is True
    assert Decimal(result["issuer_adjusted_factor_relative_error"]) < Decimal("0.001")


def test_wrong_source_terms_or_issuer_cap_table_remain_blocked():
    event, row, previous, spec = _fixture(19014)
    with pytest.raises(RuntimeError):
        promote(event, [dict(row, dividCashPsBeforeTax="0.4")], previous, spec)
    with pytest.raises(RuntimeError):
        promote(event, [row], previous, dict(spec, eligible_shares=spec["total_shares"]))
    with pytest.raises(RuntimeError):
        promote(event, [row], previous, dict(spec, issued_shares=1))


def test_wrong_factor_and_parent_remain_blocked():
    event, row, previous, spec = _fixture(24005)
    with pytest.raises(RuntimeError):
        promote(dict(event, factor_value="2.0"), [row], previous, spec)
    with pytest.raises(RuntimeError):
        promote(event, [row], dict(previous, reason="no_exact_ex_date"), spec)
