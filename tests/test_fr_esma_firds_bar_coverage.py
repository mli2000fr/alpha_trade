import gzip
import hashlib
import json

import pytest

from service.fr.esma_firds_bar_coverage import audit, classify, valid_bar


def test_classify_respects_initial_full_gap_and_intervals():
    markets = [{"observed_asof_intervals": [
        {"from": "2018-01-06", "to": "2018-01-10"},
    ]}]
    assert classify("2018-01-05", markets, set(), "2018-01-06") == "BEFORE_INITIAL_FULL"
    assert classify("2018-01-08", markets, {"2018-01-08"}, "2018-01-06") == "MISSING_DELTA_PUBLICATION_DAY"
    assert classify("2018-01-09", markets, set(), "2018-01-06") == "CURRENT_ISIN_HAS_OBSERVED_TARGET_MIC"
    assert classify("2018-01-11", markets, set(), "2018-01-06") == "NO_OBSERVED_TARGET_MIC_FOR_CURRENT_ISIN"


def test_valid_bar_rejects_zero_volume_or_bad_ohlc():
    bar = {"open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}
    assert valid_bar(bar)
    assert not valid_bar({**bar, "volume": 0})
    assert not valid_bar({**bar, "high": 10})


def test_audit_keeps_diagnostic_categories_separate(tmp_path):
    root = tmp_path / "archive"
    (root / "symbols").mkdir(parents=True)
    (root / "eod").mkdir()
    code = "ABC.PA"
    key = hashlib.sha256(code.encode()).hexdigest()[:16]
    (root / "symbols" / f"{key}.json").write_text(json.dumps({
        "symbol": code, "status": "COMPLETED",
        "payloads": {"eod": {"file": f"eod/{key}.json.gz"}},
    }), encoding="utf-8")
    bars = [{"date": day, "open": 10, "high": 12, "low": 9,
             "close": 11, "volume": 100}
            for day in ("2018-01-05", "2018-01-08", "2018-01-09", "2018-01-11")]
    with gzip.open(root / "eod" / f"{key}.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(bars, stream)
    history = {"start": "2018-01-06", "end": "2018-12-31",
               "missing_delta_days": ["2018-01-08"], "symbols": [{
                   "symbol": code, "isin": "FR0000000000",
                   "provider_status_current": "active",
                   "market_reference": [{"observed_asof_intervals": [
                       {"from": "2018-01-06", "to": "2018-01-10"},
                   ]}],
               }]}
    report = audit(history, root, start="2018-01-01", end="2018-01-31")
    assert report["counts"] == {
        "BEFORE_INITIAL_FULL": 1,
        "MISSING_DELTA_PUBLICATION_DAY": 1,
        "CURRENT_ISIN_HAS_OBSERVED_TARGET_MIC": 1,
        "NO_OBSERVED_TARGET_MIC_FOR_CURRENT_ISIN": 1,
    }
    assert report["canonical_go"] is False
    with pytest.raises(ValueError, match="hors du rejeu"):
        audit(history, root, start="2018-01-01", end="2019-01-01")

def test_classify_rejects_active_non_equity_cfi_from_equity_scope():
    markets = [{"mic": "XPAR", "versions": [{
        "asof_from": "2025-07-11", "asof_to": None,
        "event": "ModfdRcrd", "cfi": "CBMIXX",
    }], "observed_asof_intervals": [{"from": "2025-07-11", "to": None}]}]
    assert classify("2025-12-27", markets, set(), "2018-01-06") == (
        "NON_EQUITY_CFI_FOR_CURRENT_ISIN")
