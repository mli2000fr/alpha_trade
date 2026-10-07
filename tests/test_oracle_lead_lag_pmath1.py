from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.oracle_lead_lag_pmath1 import (
    PRESSURE,
    adjusted_return_panel,
    compute_pressure,
    fit_residual_model,
    learn_stable_edges,
)


def test_adjusted_return_panel_uses_adjusted_close() -> None:
    bars = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"] * 2),
        "symbol": ["A", "A", "B", "B"],
        "close": [10.0, 5.0, 20.0, 22.0],
        "adj_close": [10.0, 10.0, 20.0, 22.0],
    })
    panel = adjusted_return_panel(bars)
    assert panel.loc[pd.Timestamp("2024-01-02"), "A"] == 0.0
    assert np.isclose(panel.loc[pd.Timestamp("2024-01-02"), "B"], 0.1)


def test_residual_betas_are_fit_only_on_train_dates() -> None:
    dates = pd.bdate_range("2024-01-01", periods=12)
    market = pd.Series(np.linspace(-0.02, 0.02, len(dates)), index=dates)
    sector = np.sin(np.arange(len(dates))) * 0.01
    returns = pd.DataFrame({
        "A": 2.0 * market + sector,
        "B": 1.0 * market + sector,
    }, index=dates)
    model, residual = fit_residual_model(
        returns, market, {"A": "S", "B": "S"}, dates[:10], min_observations=5,
    )
    before = model.coefficients.copy()
    mutated = returns.copy()
    mutated.loc[dates[10]:, "A"] = 99.0
    model_after, _ = fit_residual_model(
        mutated, market, {"A": "S", "B": "S"}, dates[:10], min_observations=5,
    )
    pd.testing.assert_frame_equal(before, model_after.coefficients)
    assert residual.loc[dates[:10], "A"].abs().max() < 1e-10


def test_stable_edges_reject_sign_flip_between_train_halves() -> None:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2020-01-01", periods=300)
    leader = pd.Series(rng.normal(size=len(dates)), index=dates)
    follower_stable = leader.shift(1) + rng.normal(scale=0.05, size=len(dates))
    follower_flip = leader.shift(1).copy()
    follower_flip.iloc[150:] *= -1.0
    residuals = pd.DataFrame({"L": leader, "STABLE": follower_stable, "FLIP": follower_flip})
    edges = learn_stable_edges(
        residuals, dates, lags=[1], max_candidate_leaders=1, max_edges_per_follower=2,
        min_half_overlap=100, min_abs_half_correlation=0.2,
        min_symbol_train_observations=250,
    )
    pairs = set(zip(edges["follower"], edges["leader"], edges["lag"]))
    assert ("STABLE", "L", 1) in pairs
    assert ("FLIP", "L", 1) not in pairs


def test_pressure_uses_only_shifted_leader_and_normalizes_weights() -> None:
    dates = pd.bdate_range("2024-01-01", periods=6)
    residuals = pd.DataFrame({"L1": [1, 2, 3, 4, 5, 6], "L2": [2, 4, 6, 8, 10, 12]}, index=dates)
    edges = pd.DataFrame([
        {"follower": "F", "leader": "L1", "lag": 1, "weight": 0.5},
        {"follower": "F", "leader": "L2", "lag": 2, "weight": -0.25},
    ])
    pressure = compute_pressure(residuals, edges).set_index("date")
    assert np.isnan(pressure.loc[dates[0], PRESSURE])
    assert pressure.loc[dates[1], PRESSURE] == 1.0
    expected = (0.5 * 2.0 - 0.25 * 2.0) / 0.75
    assert np.isclose(pressure.loc[dates[2], PRESSURE], expected)
    residuals.loc[dates[2], "L1"] = 999.0
    unchanged = compute_pressure(residuals, edges).set_index("date")
    assert np.isclose(unchanged.loc[dates[2], PRESSURE], expected)


def test_research_config_has_no_contemporaneous_lag() -> None:
    import json
    from pathlib import Path

    config = json.loads(Path("config/research/pmath1_cross_asset_lead_lag.json").read_text(encoding="utf-8"))
    assert config["lags"] == [1, 2, 3, 5]
    assert all(lag > 0 for lag in config["lags"])
    assert config["status"] == "COMPLETED_NO_GO_INCREMENTAL_LEAD_LAG"
