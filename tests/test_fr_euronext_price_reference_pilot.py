import gzip
import json

from service.fr.euronext_price_reference_pilot import audit, read_euronext


def test_audit_matches_raw_ohlc_and_reports_difference(tmp_path):
    ref = tmp_path / "reference.csv"
    ref.write_text('"Historical Data"\n"From 01/01/2025 to 02/01/2025"\nFR0000000000\n'
                   'Date;Open;High;Low;Last;Close;"Number of Shares";"Number of Trades";Turnover;vwap\n'
                   '02/01/2025;10;12;9;11;11;100;5;1100;11\n', encoding="utf-8-sig")
    provider = tmp_path / "provider.json.gz"
    with gzip.open(provider, "wt", encoding="utf-8") as stream:
        json.dump([{"date": "2025-01-02", "open": 10, "high": 12,
                    "low": 9, "close": 11.1, "volume": 100}], stream)
    assert read_euronext(ref)["2025-01-02"]["shares"] == 100
    report = audit(ref, provider, isin="FR0000000000", compare_volume=True)
    assert report["overlap_rows"] == 1
    assert report["difference_count"] == 1
    assert report["difference_examples"][0]["field"] == "close"
    assert report["canonical_go"] is False
