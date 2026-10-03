from datetime import date
from pathlib import Path

from service.fr import esma_firds_full_reconcile as module


def _history():
    return {"symbols": [{"isin": "FR0000000001", "market_reference": [{"mic": "XPAR", "versions": [
        {"asof_from": "2018-01-06", "asof_to": None, "event": "Full", "currency": "EUR",
         "cfi": "ESXXXX", "first_trade_reported": "2017-01-01", "termination_reported": None}]}]}]}


def test_full_reconciliation_matching(monkeypatch):
    monkeypatch.setattr(module, "archive_records", lambda *_: iter([{
        "isin": "FR0000000001", "mic": "XPAR", "currency": "EUR", "cfi": "ESXXXX",
        "first_trade_reported": "2017-01-01", "termination_reported": None}]))
    result = module.reconcile(_history(), [Path("FULINS_E_20181229_01of01.zip")], date(2018, 12, 29))
    assert result["candidate_pairs_reconciled"] is True
    assert result["canonical_go"] is False


def test_full_reconciliation_detects_field_difference(monkeypatch):
    monkeypatch.setattr(module, "archive_records", lambda *_: iter([{
        "isin": "FR0000000001", "mic": "XPAR", "currency": "USD", "cfi": "ESXXXX",
        "first_trade_reported": "2017-01-01", "termination_reported": None}]))
    result = module.reconcile(_history(), [Path("FULINS_E_20181229_01of01.zip")], date(2018, 12, 29))
    assert result["mismatch_types"] == {"field_difference": 1}
    assert result["candidate_pairs_reconciled"] is False


def test_full_reconciliation_normalizes_equivalent_utc_timestamps(monkeypatch):
    history = _history()
    version = history["symbols"][0]["market_reference"][0]["versions"][0]
    version["first_trade_reported"] = "2015-07-28T00:01:00"
    monkeypatch.setattr(module, "archive_records", lambda *_: iter([{
        "isin": "FR0000000001", "mic": "XPAR", "currency": "EUR", "cfi": "ESXXXX",
        "first_trade_reported": "2015-07-28T00:01:00Z", "termination_reported": None}]))
    result = module.reconcile(history, [Path("FULINS_E_20211225_01of01.zip")],
                              date(2021, 12, 25))
    assert result["mismatches"] == []
    assert result["candidate_pairs_reconciled"] is True


def test_full_reconciliation_keeps_real_timestamp_difference(monkeypatch):
    history = _history()
    version = history["symbols"][0]["market_reference"][0]["versions"][0]
    version["first_trade_reported"] = "2015-07-28T00:01:00"
    monkeypatch.setattr(module, "archive_records", lambda *_: iter([{
        "isin": "FR0000000001", "mic": "XPAR", "currency": "EUR", "cfi": "ESXXXX",
        "first_trade_reported": "2015-07-28T00:02:00Z", "termination_reported": None}]))
    result = module.reconcile(history, [Path("FULINS_E_20211225_01of01.zip")],
                              date(2021, 12, 25))
    assert result["mismatch_types"] == {"field_difference": 1}


def test_full_reconciliation_quarantines_overlapping_versions(monkeypatch):
    history = _history()
    versions = history["symbols"][0]["market_reference"][0]["versions"]
    versions[0]["source_file"] = "full.zip"
    versions.append({**versions[0], "source_file": "delta.zip"})
    monkeypatch.setattr(module, "archive_records", lambda *_: iter([{
        "isin": "FR0000000001", "mic": "XPAR", "currency": "EUR", "cfi": "ESXXXX",
        "first_trade_reported": "2017-01-01", "termination_reported": None}]))
    result = module.reconcile(history, [Path("FULINS_E_20181229_01of01.zip")], date(2018, 12, 29))
    assert len(result["overlapping_replay_versions"]) == 1
    assert result["candidate_pairs_reconciled"] is False
    assert result["mismatches"] == []
