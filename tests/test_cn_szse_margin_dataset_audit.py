import copy

import pytest

from service.market.cn_szse_margin_dataset_audit import validate_row


def sample():
    return {"source_session": "2020-01-02", "market_code": "CN_A",
            "exchange_mic": "XSHE", "strict_ml_allowed": False,
            "historical_vintage_proven": False, "instrument_id": 1,
            "local_symbol": "000001", "research_available_at_proxy": "2020-01-06T07:00:00Z",
            "measures": {"融资余额": 20, "融券余额": 5, "融资融券余额": 25, "融资买入额": 10},
            "observation_status": "OBSERVED", "amount_cny": 100,
            "financing_buy_to_amount": 0.1, "quality_reasons": []}


REFERENCE = {1: {"local_symbol": "000001", "listing_date": "2010-01-01", "delisting_date": None}}
PROXY = "2020-01-06T07:00:00+00:00"


def test_valid_row_and_timezone_equivalence():
    validate_row(sample(), "2020-01-02", PROXY, REFERENCE)


@pytest.mark.parametrize("field,value", [
    ("source_session", "2020-01-03"), ("exchange_mic", "XSHG"),
    ("strict_ml_allowed", True), ("historical_vintage_proven", True),
    ("research_available_at_proxy", None), ("financing_buy_to_amount", 0.2),
    ("quality_reasons", ["INVALID"]), ("local_symbol", "000002")])
def test_corrupted_contract_rejected(field, value):
    row = sample()
    row[field] = value
    with pytest.raises(ValueError):
        validate_row(row, "2020-01-02", PROXY, REFERENCE)


def test_future_listing_rejected():
    reference = copy.deepcopy(REFERENCE)
    reference[1]["listing_date"] = "2021-01-01"
    with pytest.raises(ValueError):
        validate_row(sample(), "2020-01-02", PROXY, reference)


def test_missing_observation_not_imputed():
    row = sample()
    row.update(measures=None, financing_buy_to_amount=None,
               observation_status="ELIGIBLE_WITHOUT_OBSERVATION", quality_reasons=["MISSING"])
    validate_row(row, "2020-01-02", PROXY, REFERENCE)
    row["observation_status"] = "OBSERVED_ZERO"
    with pytest.raises(ValueError):
        validate_row(row, "2020-01-02", PROXY, REFERENCE)
