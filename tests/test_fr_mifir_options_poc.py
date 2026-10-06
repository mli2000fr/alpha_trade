import csv
import io
import json
import zipfile

import pytest

from service.fr import mifir_options_poc as poc

OBSERVED = "2026-10-06T10:00:00+00:00"


def reference(**updates):
    result = {"id": "record-1", "isin": "FREX03807457", "mic": "XMON",
              "gnr_cfi_code": "OCASPS", "drv_underlng_isin": "FR0000120321",
              "drv_option_type": "CALL", "drv_sp_prc_value_amount": "410",
              "drv_sp_prc_value_sign_flag": "No", "drv_price_multiplier": "100",
              "drv_sp_prc_value_curr_code": "EUR", "gnr_notional_curr_code": "EUR",
              "drv_expiry_date": "2026-11-20T00:00:00Z", "publication_date": "2026-10-04T08:00:00Z",
              "mrkt_trdng_start_date": "2026-08-24T00:00:00Z"}
    result.update(updates)
    return result


def trade(**updates):
    row = {k: "" for k in poc.REQUIRED}
    row.update(TradingDateTime="2026-10-05T12:00:00Z", PublicationDateTime="2026-10-05T12:00:01Z",
               MifidInstrumentID="FREX03807457", MifidPrice="3.24", MifidQuantity="2",
               MifidPriceNotation="MONE", MifidCurrency="EUR", Venue="XMON", VenueOfPublication="XMON",
               TradeUniqueIdentifier="T1", MmtModificationIndicator="-", MmtPostTradeDeferral="-")
    row.update(updates)
    return row


def zipped(rows):
    stream = io.StringIO()
    stream.write("Copyright, with commas, not a header\n")
    fields = ["TradingDateTime"] + sorted(poc.REQUIRED - {"TradingDateTime"})
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("trades.csv", stream.getvalue())
    return result.getvalue()


def analyze(rows, docs=None):
    return poc.analyze(rows, docs if docs is not None else [reference()], OBSERVED)


def test_preamble_not_header_and_zip_decoded():
    rows, disclaimer = poc.read_trades(zipped([trade()]))
    assert len(rows) == 1
    assert rows[0]["MifidPrice"] == "3.24"
    assert disclaimer.startswith("Copyright")


def test_contract_join_has_underlying_strike_side_expiry_and_no_old_pit():
    result = analyze([trade()])
    contract = result["accepted"][0]["contract"]
    assert contract["symbol"] == "OR.PA"
    assert contract["strike"] == "410"
    assert contract["expiry"] == "2026-11-20"
    assert contract["side"] == "CALL"
    assert contract["historical_reference_pit_qualified"] is False


def test_exact_duplicate_not_double_counted():
    result = analyze([trade(), trade()])
    assert result["coverage"]["OR.PA"]["accepted_trade_rows"] == 1
    assert result["exclusion_counts"]["EXACT_DUPLICATES_REMOVED"] == 1


def test_cancel_removes_original_regardless_of_order():
    for rows in [[trade(), trade(MmtModificationIndicator="CANC")],
                 [trade(MmtModificationIndicator="CANC"), trade()]]:
        result = analyze(rows)
        assert result["accepted"] == []
        assert result["exclusion_counts"]["CANCELLED_ID"] == 2


def test_amendment_is_quarantined_not_added():
    assert analyze([trade(MmtModificationIndicator="AMND")])["accepted"] == []


def test_conflicting_identifier_is_not_arbitrarily_resolved():
    result = analyze([trade(), trade(MifidPrice="9")])
    assert result["accepted"] == []
    assert result["exclusion_counts"]["CONFLICTING_TRADE_ID"] == 2


@pytest.mark.parametrize("updates", [
    {"MifidQuantity": "NaN"}, {"MifidPrice": "0"}, {"MifidQuantity": "-1"},
    {"PublicationDateTime": "2026-10-04T12:00:00Z"},
    {"TradingDateTime": "2026-10-05T12:00:00"},
    {"NumberOfTransactions": "5"}, {"MissingPrice": "NIL"},
    {"MmtPostTradeDeferral": "LIS"}, {"MifidCurrency": "USD"}])
def test_unqualified_rows_excluded(updates):
    assert analyze([trade(**updates)])["accepted"] == []


def test_different_reference_versions_are_ambiguous():
    result = analyze([trade()], [reference(), reference(id="record-2", drv_sp_prc_value_amount="400")])
    assert result["accepted"] == []
    assert result["ambiguous_reference_isins"] == ["FREX03807457"]


def test_option_underlying_must_be_one_of_pilot_isins():
    assert analyze([trade()], [reference(drv_underlng_isin="US0000000000")])["accepted"] == []


def test_futures_not_misclassified_as_options():
    assert analyze([trade()], [reference(gnr_cfi_code="FFXXXX")])["accepted"] == []


def test_multiplier_is_not_hardcoded_100():
    assert analyze([trade()], [reference(drv_price_multiplier="10")])["contracts"][0]["multiplier"] == "10"


def test_firds_puto_enum_normalized_and_cfi_checked():
    result = analyze([trade()], [reference(drv_option_type="PUTO", gnr_cfi_code="OPASPS")])
    assert result["contracts"][0]["side"] == "PUT"
    assert result["contracts"][0]["source_option_type"] == "PUTO"
    assert analyze([trade()], [reference(drv_option_type="PUTO")])["accepted"] == []


def test_missing_required_reference_fields_reported():
    doc = reference()
    del doc["drv_expiry_date"]
    result = analyze([trade()], [doc])
    assert result["accepted"] == []
    assert "FREX03807457" in result["contract_errors"]


def test_numeric_source_ids_not_fabricated_as_isins():
    result = analyze([trade(MifidInstrumentID="3884799986")])
    assert result["non_isin_trade_rows"] == 1
    assert result["accepted"] == []
    assert poc.valid_isin("FR0000120321")
    assert not poc.valid_isin("FR0000120322")


def test_quantity_is_reported_not_certified_contract_volume():
    result = analyze([trade(), trade(TradeUniqueIdentifier="T2", MifidQuantity="3")])
    summary = result["coverage"]["OR.PA"]
    assert summary["reported_call_quantity_sum"] == "5"
    assert summary["quantity_unit_qualified"] is False
    assert summary["put_call_contract_volume_ratio"] is None


def test_query_budget_and_injection_refused():
    with pytest.raises(ValueError):
        poc.query_url(["foo OR *:*"])
    with pytest.raises(ValueError):
        poc.query_url(["FREX03807457"] * 81)


def test_network_not_implicit(tmp_path):
    with pytest.raises(ValueError):
        poc.run(tmp_path)


def test_offline_run_persists_quarantine_without_network(tmp_path, monkeypatch):
    def forbidden(*args):
        raise AssertionError("network must not be called")
    monkeypatch.setattr(poc, "fetch", forbidden)
    trades = tmp_path / "source.zip"
    trades.write_bytes(zipped([trade()]))
    refs = tmp_path / "source.json"
    refs.write_text(json.dumps([reference()]), encoding="utf-8")
    root = poc.run(tmp_path / "outputs", trades_zip=trades, reference_json=refs)
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert not report["ml_eligible"] and not report["scheduled"]
    assert not report["historical_pit_qualified"]
    assert report["status"] == "PARTIAL_OR_EMPTY_PILOT_COVERAGE"
    assert report["available_at"] == report["observed_at"]


def test_failed_run_keeps_error_report(tmp_path):
    trades = tmp_path / "bad.zip"
    trades.write_bytes(b"bad")
    refs = tmp_path / "source.json"
    refs.write_text("[]")
    with pytest.raises(zipfile.BadZipFile):
        poc.run(tmp_path / "outputs", trades_zip=trades, reference_json=refs)
    report_file = next((tmp_path / "outputs").glob("*/report.json"))
    assert json.loads(report_file.read_text(encoding="utf-8"))["status"] == "FAILED"
