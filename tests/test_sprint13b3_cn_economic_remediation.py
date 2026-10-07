"""B3 ne promeut que le transfert sz.002112 déjà réconcilié."""

from datetime import date

import pytest

from modelFactory.cn_economic_remediation_13b3 import promote


def _event() -> dict:
    return {
        "corporate_action_id": 14811,
        "instrument_id": 3815,
        "provider_symbol": "sz.002112",
        "ex_date": date(2022, 9, 23),
        "previous_close": "9.650000",
        "previous_factor_value": "2.5841640000",
        "factor_value": "3.3608060000",
        "source_payload_hash": "e28a49832f8922a523ac7b43f02b877054af585ecfcdf6d926fc664770457985",
    }


def _row() -> dict:
    return {
        "code": "sz.002112",
        "dividOperateDate": "2022-09-23",
        "dividPlanDate": "2022-09-16",
        "dividRegistDate": "2022-09-22",
        "dividPayDate": "",
        "dividCashPsBeforeTax": "",
        "dividStocksPs": "0.000000",
        "dividReserveToStockPs": "0.300000",
        "dividCashStock": "10转3",
    }


def _previous() -> dict:
    return {
        "corporate_action_id": 14811,
        "status": "UNRESOLVED",
        "reason": "invalid_economic_terms",
        "source_payload_hash": _event()["source_payload_hash"],
    }


def test_promotes_only_exact_share_transfer():
    result = promote(_event(), [_row()], _previous())
    assert result["status"] == "EVIDENCED_DISTRIBUTION"
    assert result["cash_per_share_before_tax"] == "0"
    assert result["share_ratio"] == "0.300000"
    assert result["remediation_kind"] == "EXPLICIT_SHARE_ONLY_BLANK_CASH_RECLASSIFIED"


@pytest.mark.parametrize("mutation", [
    {"dividCashStock": "10转3派1元"},
    {"dividReserveToStockPs": ""},
    {"dividOperateDate": "2022-09-24"},
])
def test_rejects_ambiguous_terms(mutation):
    with pytest.raises(RuntimeError):
        promote(_event(), [dict(_row(), **mutation)], _previous())


def test_rejects_another_event_or_modified_parent():
    with pytest.raises(RuntimeError):
        promote(dict(_event(), corporate_action_id=14812), [_row()], _previous())
    with pytest.raises(RuntimeError):
        promote(_event(), [_row()], dict(_previous(), reason="factor_terms_mismatch"))
