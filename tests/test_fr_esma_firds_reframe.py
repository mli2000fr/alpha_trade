from service.fr.esma_firds_reframe import reframe


def test_reframe_preserves_raw_publication_but_removes_observation_overlap():
    raw = {"counts": {"version_records": 2}, "anomalies": [], "canonical_go": False,
           "symbols": [{"isin": "FR0000000001", "symbol": "TEST.PA", "market_reference": [
               {"mic": "XPAR", "versions": [
                   {"isin": "FR0000000001", "mic": "XPAR", "event": "Full", "currency": "EUR",
                    "cfi": "ESXXXX", "name": "Test", "first_trade_reported": "2017-01-01",
                    "termination_reported": None, "publication_from_reported": "2017-01-01",
                    "archive_date": "2018-01-06", "source_file": "full.zip",
                    "asof_from": "2018-01-06", "asof_to": "2018-01-07"},
                   {"isin": "FR0000000001", "mic": "XPAR", "event": "ModfdRcrd", "currency": "EUR",
                    "cfi": "ESXXXX", "name": "Test", "first_trade_reported": "2017-01-01",
                    "termination_reported": None, "publication_from_reported": "2018-01-07",
                    "archive_date": "2018-01-08", "source_file": "delta.zip",
                    "asof_from": "2018-01-07", "asof_to": None}]}]}]}
    revised = reframe(raw, "source-hash")
    versions = revised["symbols"][0]["market_reference"][0]["versions"]
    assert versions[0]["asof_to"] == "2018-01-07"
    assert versions[1]["asof_from"] == "2018-01-08"
    assert versions[1]["publication_from_reported"] == "2018-01-07"
    assert raw["symbols"][0]["market_reference"][0]["versions"][1]["asof_from"] == "2018-01-07"
    assert revised["derived_from_sha256"] == "source-hash"
    assert revised["canonical_go"] is False
