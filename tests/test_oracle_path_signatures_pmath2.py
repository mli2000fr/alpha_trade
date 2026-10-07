from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle_path_signatures_pmath2 import (
    build_sector_factor,
    build_signature_panel,
    signature_feature_names,
    tensor_signature_batch,
)


def test_one_dimensional_signature_matches_exponential_series() -> None:
    increments = np.array([[[0.2], [-0.1], [0.4]]])
    signature = tensor_signature_batch(increments, depth=3)[0]
    total = 0.5
    np.testing.assert_allclose(signature, [total, total**2 / 2.0, total**3 / 6.0])


def test_depth_two_signature_preserves_order() -> None:
    x_then_y = np.array([[[1.0, 0.0], [0.0, 1.0]]])
    y_then_x = np.array([[[0.0, 1.0], [1.0, 0.0]]])
    first = tensor_signature_batch(x_then_y, depth=2)[0]
    second = tensor_signature_batch(y_then_x, depth=2)[0]
    # level 1 is identical, but ordered integrals xy/yx differ.
    np.testing.assert_allclose(first[:2], second[:2])
    assert not np.allclose(first[2:], second[2:])
    assert first[2 + 1] == 1.0  # xy
    assert second[2 + 2] == 1.0  # yx


def test_signature_dimensions_are_frozen() -> None:
    assert len(signature_feature_names(1)) == 4
    assert len(signature_feature_names(2)) == 20
    assert len(signature_feature_names(3)) == 84


def test_panel_ends_at_event_date_and_never_reads_next_day() -> None:
    dates = pd.bdate_range("2024-01-01", periods=25)
    returns = pd.DataFrame({"A": np.arange(25, dtype=float) / 1000.0}, index=dates)
    market = pd.Series(np.arange(25, dtype=float) / 2000.0, index=dates)
    factors, sectors = build_sector_factor(returns, {"A": "TECH"})
    events = pd.DataFrame({"date": [dates[20]], "symbol": ["A"]})
    before, names = build_signature_panel(
        events, returns, market, factors, sectors, window=20, max_depth=3,
        min_valid_asset_sessions=18, chunk_size=10,
    )
    mutated = returns.copy()
    mutated.loc[dates[21]:, "A"] = 999.0
    factors_after, sectors_after = build_sector_factor(mutated, {"A": "TECH"})
    after, _ = build_signature_panel(
        events, mutated, market, factors_after, sectors_after, window=20, max_depth=3,
        min_valid_asset_sessions=18, chunk_size=10,
    )
    np.testing.assert_allclose(before[names], after[names], equal_nan=True)


def test_missing_history_is_rejected() -> None:
    dates = pd.bdate_range("2024-01-01", periods=20)
    values = np.arange(20, dtype=float) / 1000.0
    values[:3] = np.nan
    returns = pd.DataFrame({"A": values}, index=dates)
    market = pd.Series(0.0, index=dates)
    factors, sectors = build_sector_factor(returns, {"A": "TECH"})
    panel, names = build_signature_panel(
        pd.DataFrame({"date": [dates[-1]], "symbol": ["A"]}), returns, market,
        factors, sectors, window=20, max_depth=3, min_valid_asset_sessions=18,
        chunk_size=10,
    )
    assert panel.loc[0, "path_valid_asset_sessions"] == 17
    assert panel.loc[0, names].isna().all()


def test_config_has_depth_two_primary_and_no_graph_dependency() -> None:
    config = json.loads(Path("config/research/pmath2_path_signatures.json").read_text(encoding="utf-8"))
    assert config["path"]["primary_depth"] == 2
    assert config["path"]["max_depth"] == 3
    assert config["path"]["channels"] == ["time", "asset_return", "market_return", "sector_return"]
    assert config["status"] == "COMPLETED_NO_GO_INCREMENTAL_PATH_SIGNATURE"
