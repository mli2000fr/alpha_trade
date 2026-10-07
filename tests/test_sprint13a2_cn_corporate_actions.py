"""La classification A2 ne doit jamais inventer une action depuis un facteur."""

from datetime import date

from modelFactory.cn_corporate_action_a2 import classify


def _event() -> dict:
    return {
        "corporate_action_id": 7,
        "instrument_id": 3,
        "provider_symbol": "sh.600000",
        "ex_date": date(2024, 1, 8),
        "previous_close": "13.73",
        "previous_factor_value": "1.225926",
        "factor_value": "1.242211",
        "source_payload_hash": "a" * 64,
    }


def _dividend() -> dict:
    return {
        "code": "sh.600000",
        "dividOperateDate": "2024-01-08",
        "dividPlanDate": "2023-12-29",
        "dividRegistDate": "2024-01-05",
        "dividPayDate": "2024-01-08",
        "dividCashPsBeforeTax": "0.18",
        "dividStocksPs": "0.000000",
        "dividReserveToStockPs": "",
        "dividCashStock": "10派1.8元",
    }


def test_exact_cash_distribution_and_factor_reconcile():
    result = classify(_event(), [_dividend()])
    assert result["status"] == "EVIDENCED_DISTRIBUTION"
    assert result["kind"] == "CASH_DIVIDEND"
    assert result["cash_per_share_before_tax"] == "0.18"


def test_missing_or_ambiguous_ex_date_stays_unresolved():
    dividend = _dividend()
    assert classify(_event(), [dict(dividend, dividOperateDate="2024-01-09")])["status"] == "UNRESOLVED"
    assert classify(_event(), [dividend, dividend])["reason"] == "ambiguous_ex_date"


def test_factor_mismatch_and_unknown_share_terms_stay_unresolved():
    event = _event()
    event["factor_value"] = "2.0"
    assert classify(event, [_dividend()])["reason"] == "factor_terms_mismatch"
    dividend = dict(_dividend(), dividCashStock="10派1.8元转2股")
    assert classify(_event(), [dividend])["reason"] == "reserve_ratio_missing"


def test_invalid_dates_or_missing_prior_price_stay_unresolved():
    assert classify(_event(), [dict(_dividend(), dividPlanDate="2024-01-10")])["reason"] == "invalid_event_dates"
    event = dict(_event(), previous_close=None)
    assert classify(event, [_dividend()])["reason"] == "missing_or_invalid_price_factor"


def test_share_only_distribution_can_have_blank_cash_when_terms_reconcile():
    event = dict(_event(), previous_close="46.33", previous_factor_value="2.168884",
                 factor_value="2.817846")
    dividend = dict(_dividend(), dividCashPsBeforeTax="", dividStocksPs="0",
                    dividReserveToStockPs="0.3", dividCashStock="10转3",
                    dividPayDate="")
    result = classify(event, [dividend])
    assert result["status"] == "EVIDENCED_DISTRIBUTION"
    assert result["kind"] == "BONUS_OR_TRANSFER_SHARES"
    assert result["cash_per_share_before_tax"] == "0"
    assert result["share_ratio"] == "0.3"
    assert classify(event, [dict(dividend, dividCashStock="10转3派1元")])["status"] == "UNRESOLVED"
    assert classify(event, [dict(dividend, dividReserveToStockPs="")])["status"] == "UNRESOLVED"
