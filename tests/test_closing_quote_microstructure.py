from __future__ import annotations

import numpy as np
import pandas as pd

import modelFactory.directional_data_research.harness as harness
from modelFactory.directional_data_research.closing_quote_microstructure import (
    derive_closing_quote_features,
    evaluate_gates,
    summarize_coverage,
)


def _raw() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-02"]),
        "symbol": ["A", "A", "B"],
        "quote_timestamp": ["2025-01-02 20:59:00", "2025-01-03 20:58:00", "2025-01-02 21:01:00"],
        "bid_price": [99.0, 100.0, 49.0],
        "ask_price": [101.0, 102.0, 51.0],
        "bid_size": [300.0, 100.0, 100.0],
        "ask_size": [100.0, 300.0, 100.0],
        "spread_bps": [200.0, 198.0, 400.0],
        "close": [100.0, 101.0, 50.0],
    })


def test_derive_features_respects_1600_new_york_cutoff():
    result = derive_closing_quote_features(_raw())
    assert result.loc[0, "quote_valid"] == 1
    assert result.loc[0, "quote_near_close_15m"] == 1
    assert result.loc[0, "quote_age_seconds"] == 60
    assert result.loc[0, "size_imbalance"] == 0.5
    assert result.loc[0, "microprice_minus_mid_bps"] > 0
    assert result.loc[2, "quote_valid"] == 0
    assert np.isnan(result.loc[2, "size_imbalance"])


def test_summarize_coverage_keeps_missing_quotes_as_zero():
    pool = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "symbol": ["A", "MISSING"],
    })
    features = derive_closing_quote_features(_raw())
    coverage, overall = summarize_coverage(pool, features)
    assert overall["pool_rows"] == 2
    assert overall["valid_quote_rows"] == 1
    assert overall["valid_quote_coverage"] == 0.5
    assert set(coverage["year"]) == {"ALL", "2025"}


def test_discovery_gate_requires_two_stable_features():
    diagnostics = pd.DataFrame({
        "feature": ["size_imbalance", "spread_bps_z60"],
        "stabilite_signes_folds": ["OUI", "OUI"],
        "n_ic_folds": [3, 4],
        "IC_decile": [0.03, -0.025],
        "AUC_direction": [0.52, 0.48],
    })
    coverage = pd.DataFrame({
        "year": ["ALL", "2024", "2025"],
        "valid_quote_coverage": [0.8, 0.7, 0.65],
    })
    gates = evaluate_gates(diagnostics, coverage)
    assert gates["discovery_pass"] is True
    assert gates["stable_directional_features"] == ["size_imbalance", "spread_bps_z60"]
    assert gates["stable_directional_families"] == ["book_imbalance", "spread"]


def test_depth_level_and_rank_do_not_count_as_two_microstructure_families():
    diagnostics = pd.DataFrame({
        "feature": ["log_quoted_depth_usd", "log_quoted_depth_usd_xs_rank"],
        "stabilite_signes_folds": ["OUI", "OUI"],
        "n_ic_folds": [4, 4],
        "IC_decile": [-0.048, -0.039],
        "AUC_direction": [0.476, 0.481],
    })
    coverage = pd.DataFrame({
        "year": ["ALL", "2024", "2025"],
        "valid_quote_coverage": [0.8, 0.7, 0.65],
    })
    gates = evaluate_gates(diagnostics, coverage)
    assert gates["discovery_pass"] is False
    assert gates["stable_directional_features"] == []


def test_assemble_pool_accepts_only_valid_exported_labels(tmp_path, monkeypatch):
    labels = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "symbol": ["A", "B"],
        "batch_id": ["batch", "batch"],
        "horizon": [20, 20],
        "oracle_decile": [10, 1],
        "future_return": [0.2, np.nan],
        "target_quality_valid": [1, 0],
    })
    labels_path = tmp_path / "labels.parquet"
    labels.to_parquet(labels_path, index=False)
    oracle = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "symbol": ["A", "B"],
        "proba_extreme": [0.9, 0.8],
    })
    monkeypatch.setattr(harness, "load_oracle_pool_proba", lambda *args, **kwargs: oracle)
    pool = harness.assemble_pool(
        None,
        "batch",
        start_date="2025-01-01",
        end_date="2025-12-31",
        labels_parquet=labels_path,
        pool_pct=1.0,
    )
    assert pool["symbol"].tolist() == ["A"]


def test_assemble_pool_uses_preselected_oracle_panel_without_reranking(tmp_path):
    labels = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "symbol": ["A", "B"],
        "batch_id": ["batch", "batch"],
        "horizon": [20, 20],
        "oracle_decile": [10, 1],
        "future_return": [0.2, -0.2],
        "target_quality_valid": [1, 1],
    })
    panel = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "symbol": ["A", "B"],
        "oracle_percentile": [0.99, 0.81],
        "oracle_top_pool": [1, 1],
    })
    labels_path = tmp_path / "labels.parquet"
    panel_path = tmp_path / "pool.parquet"
    labels.to_parquet(labels_path, index=False)
    panel.to_parquet(panel_path, index=False)
    pool = harness.assemble_pool(
        None,
        "batch",
        start_date="2025-01-01",
        end_date="2025-12-31",
        labels_parquet=labels_path,
        oracle_pool_parquet=panel_path,
        pool_pct=0.20,
    )
    assert set(pool["symbol"]) == {"A", "B"}
