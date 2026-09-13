from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.fundamental_alpha_book import (
    ALPHAS,
    E19BConfig,
    add_neutralized_views,
    assign_oos_folds,
    build_family_scores,
    build_walk_forward_folds,
)


def _panel(rows: int = 60) -> pd.DataFrame:
    scale = np.linspace(0.0, 1.0, rows)
    return pd.DataFrame({
        "date": pd.Timestamp("2025-01-02"),
        "symbol": [f"S{i:03d}" for i in range(rows)],
        "sector": np.where(np.arange(rows) < rows / 2, "A", "B"),
        "market_eligible": True,
        "fundamental_fresh": True,
        "market_cap_log": 8.0 + 2.0 * scale,
        "roe": scale, "roa": scale, "net_margin": scale,
        "operating_margin": scale, "gross_margin": scale,
        "current_ratio": 1.0 + scale,
        "pe_ratio": 30.0 - 20.0 * scale,
        "pb_ratio": 6.0 - 4.0 * scale,
        "ps_ratio": 8.0 - 6.0 * scale,
        "ev_to_ebitda": 20.0 - 12.0 * scale,
        "eps_growth_yoy": scale, "revenue_growth_yoy": scale,
        "debt_to_equity": 3.0 - 2.0 * scale,
        "delta_roe": scale, "delta_roa": scale,
        "delta_net_margin": scale, "delta_operating_margin": scale,
        "delta_eps_growth_yoy": scale, "delta_revenue_growth_yoy": scale,
    })


def test_fixed_economic_signs_point_to_the_same_good_company() -> None:
    config = E19BConfig(min_cross_section=10)
    scored = build_family_scores(_panel(), config)
    first = scored.iloc[0]
    last = scored.iloc[-1]
    for family in ("quality", "value", "growth", "leverage", "improvement"):
        assert last[f"score_{family}__raw"] > first[f"score_{family}__raw"]
    assert last["score_fundamental_composite__raw"] > first["score_fundamental_composite__raw"]


def test_sector_size_neutral_view_removes_large_structural_exposures() -> None:
    config = E19BConfig(min_cross_section=10, min_sector_members=5)
    raw = build_family_scores(_panel(80), config)
    idiosyncratic = 0.20 * np.sin(np.arange(len(raw)) * 1.7)
    for alpha in ALPHAS:
        raw[f"score_{alpha}__raw"] += idiosyncratic
    scored = add_neutralized_views(raw, config)
    for alpha in ALPHAS:
        column = f"score_{alpha}__sector_size_neutral"
        valid = scored[[column, "market_cap_log", "sector"]].dropna()
        assert abs(valid[column].corr(valid["market_cap_log"])) < 1e-10
        assert valid.groupby("sector")[column].mean().abs().max() < 1e-10


def test_walk_forward_assigns_only_post_training_dates() -> None:
    dates = pd.bdate_range("2020-01-01", periods=900)
    config = E19BConfig(
        wf_min_train_size=504,
        wf_test_size=126,
        wf_step_size=126,
        wf_max_splits=3,
        wf_min_partial_test_size=126,
    )
    folds = build_walk_forward_folds(dates, config)
    assert len(folds) == 3
    assert folds.iloc[0]["train_end"] < folds.iloc[0]["test_start"]
    panel = pd.DataFrame({"date": dates})
    assigned = assign_oos_folds(panel, folds)
    assert assigned.loc[:502, "fold"].isna().all()
    assert assigned.loc[504:, "fold"].notna().sum() == 378
