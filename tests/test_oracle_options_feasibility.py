from __future__ import annotations

import gzip
import json
from pathlib import Path

from modelFactory import oracle_options_feasibility as feasibility


def _write_snapshot(path: Path) -> None:
    call = {
        "details": {"ticker": "O:AAA", "contract_type": "call", "expiration_date": "2026-10-16", "strike_price": 100},
        "underlying_asset": {"ticker": "AAA"}, "last_quote": {"bid": 4.0, "ask": 5.0},
        "implied_volatility": 0.4, "open_interest": 20,
    }
    put = {
        "details": {"ticker": "O:AAB", "contract_type": "put", "expiration_date": "2026-10-16", "strike_price": 100},
        "underlying_asset": {"ticker": "AAA"}, "last_quote": {"bid": 3.0, "ask": 4.0},
        "implied_volatility": 0.5, "open_interest": 30,
    }
    envelope = {"dataset": "options_chain", "symbol_requested": "AAA", "page": 1, "payload": {"results": [call, put]}}
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(envelope) + "\n")


def test_snapshot_audit_counts_complete_straddle(tmp_path: Path) -> None:
    path = tmp_path / "chain.jsonl.gz"
    _write_snapshot(path)
    audit = feasibility.audit_snapshot_collections([path])
    assert audit["unique_contracts"] == 2
    assert audit["contract_types"] == {"call": 1, "put": 1}
    assert audit["complete_same_strike_call_put_pairs"] == 1
    assert audit["contracts_with_bid_and_ask"] == 2
    assert not audit["suitable_for_historical_backtest"]


def _evidence(*, flatfile_status: int) -> dict:
    return {
        name: {"http_status": 200}
        for name in ("contracts_as_of", "daily_aggregates", "historical_trades", "historical_quotes")
    } | {
        "flatfile_catalog": {"day_entitled": True, "minute_entitled": True},
        "flatfile_object": {"http_status": flatfile_status},
    }


def test_assessment_allows_rest_pilot_but_blocks_flatfiles() -> None:
    result = feasibility.assess_remote_evidence(_evidence(flatfile_status=401))
    assert result["pilot_possible_now"]
    assert not result["full_scale_preferred_transport_ready"]
    assert result["decision"] == "GO_REST_PILOT_FLATFILES_BLOCKED"


def test_assessment_accepts_verified_partial_content() -> None:
    result = feasibility.assess_remote_evidence(_evidence(flatfile_status=206))
    assert result["full_scale_preferred_transport_ready"]
    assert result["decision"] == "GO_FULL_PIPELINE"


def test_missing_historical_quotes_blocks_pilot() -> None:
    evidence = _evidence(flatfile_status=401)
    evidence["historical_quotes"]["http_status"] = 403
    result = feasibility.assess_remote_evidence(evidence)
    assert not result["pilot_possible_now"]
    assert result["decision"] == "BLOCKED"


def test_report_freezes_conservative_ask_bid_contract() -> None:
    report = feasibility.build_report({}, _evidence(flatfile_status=401))
    pit = report["pit_contract_for_E6_B1"]
    assert "asks" in pit["entry"]
    assert "bids" in pit["exit"]
    assert report["research_only"]
