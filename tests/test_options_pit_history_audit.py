from __future__ import annotations

import gzip
import json

import pandas as pd

from modelFactory.options_pit_history_audit import (
    OptionsPitRequirements,
    assess_readiness,
    audit_directional_collection,
    audit_snapshot_file,
)


def test_snapshot_is_explicitly_current_only(tmp_path) -> None:
    path = tmp_path / "options_chain.jsonl.gz"
    envelope = {
        "symbol_requested": "AAA",
        "payload": {"results": [{
            "implied_volatility": 0.4, "open_interest": 100,
            "greeks": {"delta": 0.5}, "last_quote": {"bid": 1.0, "ask": 1.2},
        }]},
    }
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(envelope) + "\n")
    audit = audit_snapshot_file(path)
    assert audit["contracts_with_bid_ask"] == 1
    assert audit["contracts_with_greeks"] == 1
    assert "current snapshot only" in audit["pit_role"]


def test_directional_collection_counts_dates_but_not_observed_iv(tmp_path) -> None:
    path = tmp_path / "options-directional-test"
    path.mkdir()
    pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03"], "symbol": ["AAA", "BBB"],
        "status": ["complete", "rejected_no_surface"],
        "atm_call_relative_spread": [0.1, None], "approx_atm_iv": [0.3, None],
    }).to_parquet(path / "option_features.parquet", index=False)
    audit = audit_directional_collection(path)
    assert audit["dates"] == 2
    assert audit["complete_rows"] == 1
    assert audit["historical_iv_observed"] is False
    assert audit["historical_iv_approximation"] is True


def test_sparse_local_sample_blocks_e8_b() -> None:
    database = {"persistent_options_storage": False}
    artifacts = {"directional_collections": [{
        "dates": 8, "symbols": 155, "complete_rows": 323,
        "complete_rate": 0.5168, "bid_ask_derived_fields": ["spread"],
        "historical_iv_observed": False, "historical_greeks": False,
        "historical_open_interest": False,
    }]}
    result = assess_readiness(database, artifacts, OptionsPitRequirements())
    assert result["verdict"] == "BLOCKED_NO_DENSE_PIT_HISTORY"
    assert result["e8_b_authorized"] is False
    assert result["gates"]["minimum_complete_rate"] is True


def test_dense_sample_still_requires_entry_exit_and_reference_data() -> None:
    database = {"persistent_options_storage": True}
    artifacts = {"directional_collections": [{
        "dates": 600, "symbols": 200, "complete_rows": 50_000,
        "complete_rate": 0.8, "bid_ask_derived_fields": ["spread"],
        "historical_iv_observed": True, "historical_greeks": True,
        "historical_open_interest": True,
    }]}
    result = assess_readiness(database, artifacts, OptionsPitRequirements())
    assert result["e8_b_authorized"] is False
    assert result["gates"]["daily_entry_exit_valuation"] is False
