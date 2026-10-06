import gzip
import json
from collections import Counter
from datetime import date

from service.fr.sprint5_limited_manifest import (
    build_manifest,
    passes_survivorship_gate,
    price_proof,
    reference_state,
)


def test_reference_state_requires_equity_cfi_and_unambiguous_version():
    markets = [{"mic": "XPAR", "versions": [{
        "asof_from": "2018-01-06", "asof_to": None, "event": "Full",
        "cfi": "ESVUFR", "source_file": "full.zip",
    }]}]
    assert reference_state("2018-01-05", markets, set(), "2018-01-06")["reason"] == "BEFORE_INITIAL_FULL"
    assert reference_state("2018-01-08", markets, {"2018-01-08"}, "2018-01-06")["reason"] == "MISSING_DELTA_PUBLICATION_DAY"
    assert reference_state("2018-01-09", markets, set(), "2018-01-06")["verified"] is True
    markets[0]["versions"][0]["cfi"] = "CBMIXX"
    assert reference_state("2018-01-09", markets, set(), "2018-01-06")["reason"] == "NON_EQUITY_CFI"


def test_price_proof_distinguishes_official_and_independent():
    windows = {"AAA.PA": [
        {"source": "YAHOO_INDEPENDENT", "official": False, "from": "2020-01-01", "to": "2020-01-03", "difference_days": {"2020-01-02"}, "examples_complete": True},
        {"source": "EURONEXT_OFFICIAL_EXPORT", "official": True, "from": "2020-01-03", "to": "2020-01-04", "difference_days": set(), "examples_complete": True},
    ]}
    assert price_proof("AAA.PA", "2020-01-01", windows) == (True, False, ["YAHOO_INDEPENDENT"])
    assert price_proof("AAA.PA", "2020-01-02", windows) == (False, False, [])
    assert price_proof("AAA.PA", "2020-01-03", windows) == (True, True, ["EURONEXT_OFFICIAL_EXPORT", "YAHOO_INDEPENDENT"])


def test_price_proof_uses_only_exact_delisted_dates():
    windows = {"OLD.PA": [{
        "source": "EURONEXT_OFFICIAL_DELISTED", "official": True,
        "exact_dates": {"2025-01-02", "2025-01-06"},
    }]}
    assert price_proof("OLD.PA", "2025-01-02", windows) == (
        True, True, ["EURONEXT_OFFICIAL_DELISTED"])
    assert price_proof("OLD.PA", "2025-01-03", windows) == (False, False, [])


def test_manifest_never_promotes_research_j1_to_canonical(tmp_path, monkeypatch):
    history = {"start": "2018-01-06", "end": "2018-01-31", "missing_delta_days": [], "symbols": [{
        "symbol": "AAA.PA", "isin": "FR0000000001", "market_reference": [{"mic": "XPAR", "versions": [{
            "asof_from": "2018-01-06", "asof_to": None, "event": "Full", "cfi": "ESXXXX", "source_file": "full.zip",
        }]}],
    }]}
    subset = {"symbols": [{"symbol": "AAA.PA", "status": "CANDIDATE_REQUIRES_EXTERNAL_PROOFS", "splits": 0}]}
    monkeypatch.setattr("service.fr.sprint5_limited_manifest._bar_rows", lambda *_: iter([{
        "date": "2018-01-09", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
    }]))
    monkeypatch.setattr("service.fr.sprint5_limited_manifest._price_windows", lambda *_: {"AAA.PA": [{
        "source": "YAHOO_INDEPENDENT", "official": False, "from": "2018-01-09", "to": "2018-01-09", "difference_days": set(), "examples_complete": True,
    }]})
    policy = {"policy_version": "fr_s5_limited_v1", "start_date": date(2018, 1, 1), "end_date": date(2018, 1, 31), "research_j1": {"minimum_symbols_per_session": 1}}
    output = tmp_path / "manifest.jsonl.gz"
    report = build_manifest(history=history, subset=subset, archive_root=tmp_path,
                            yahoo_report={}, euronext_dir=tmp_path, policy=policy,
                            output_jsonl_gz=output)
    with gzip.open(output, "rt", encoding="utf-8") as stream:
        row = json.loads(stream.readline())
    assert row["research_j1_eligible"] is True
    assert row["canonical_strict_eligible"] is False
    assert row["decision"] == "RESEARCH_J1_ELIGIBLE"
    assert report["verdict"] == "GO_RESEARCH_J1"
    assert report["canonical_writes_performed"] is False


def test_survivorship_gate_requires_absolute_and_relative_delisted_coverage():
    counts = Counter({"active": 294, "delisted": 2})
    assert not passes_survivorship_gate(
        counts, 296, minimum_delisted=20, minimum_delisted_ratio=0.10)
    assert passes_survivorship_gate(
        Counter({"active": 180, "delisted": 20}), 200,
        minimum_delisted=20, minimum_delisted_ratio=0.10)

