from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_monetization_bridge import E12Config, build_fixed_h20_events
from modelFactory.oracle_pre_entry_veto import (
    MODEL_FEATURES,
    E13Config,
    add_daily_vetoes,
    add_pre_entry_features,
    fit_oof_risk,
    schedule_dynamic_capacity,
)


def _bars(periods: int = 90) -> pd.DataFrame:
    rows = []
    for symbol_index, symbol in enumerate(("AAA", "BBB")):
        for index, date in enumerate(pd.bdate_range("2024-01-02", periods=periods)):
            price = 100 + symbol_index + index * 0.1
            rows.append({
                "symbol": symbol, "date": date, "open": price,
                "high": price + 0.5, "low": price - 0.5, "close": price,
                "adj_close": price, "volume": 1_000_000 + index * 1_000,
            })
    return pd.DataFrame(rows)


def _events() -> pd.DataFrame:
    gate = pd.DataFrame([
        {
            "date": pd.Timestamp("2024-02-15"), "symbol": symbol,
            "directional_oracle_fold_start": "2024-01-01",
            "directional_oracle_proba_extreme": probability,
            "directional_oracle_extreme_pct": percentile,
            "directional_oracle_eligible": True,
            "directional_oracle_oof_available": True,
        }
        for symbol, probability, percentile in (
            ("AAA", 0.8, 0.9), ("BBB", 0.7, 0.8)
        )
    ])
    return build_fixed_h20_events(gate, _bars(), E12Config())


def test_feature_panel_contains_only_declared_pre_entry_features() -> None:
    featured = add_pre_entry_features(_events(), _bars())
    assert set(MODEL_FEATURES).issubset(featured.columns)
    assert featured["entry_gap_signed"].abs().max() < 0.01
    for column in (name for name in MODEL_FEATURES if name.endswith("_xs_rank")):
        assert featured[column].between(0, 1).all()


def test_daily_veto_rejects_highest_risk_fraction() -> None:
    frame = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-02")] * 10,
        "pre_entry_trailing_risk": np.arange(10, dtype=float),
    })
    marked = add_daily_vetoes(frame, (0.20,))
    assert int(marked["keep_0.20"].sum()) == 8
    assert not marked.iloc[-1]["keep_0.20"]


def test_dynamic_scheduler_refills_after_exit() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    panel = pd.DataFrame([
        {
            "date": date, "entry_date": date + pd.offsets.BDay(1),
            "exit_date": date + pd.offsets.BDay(1), "symbol": f"S{index}",
            "directional_oracle_proba_extreme": 0.9 - index * 0.1,
        }
        for index, date in enumerate(dates)
    ])
    selected = schedule_dynamic_capacity(panel, max_positions=1)
    assert selected["symbol"].tolist() == ["S0", "S1", "S2"]


def test_dynamic_scheduler_respects_veto_and_priority() -> None:
    date = pd.Timestamp("2024-01-02")
    panel = pd.DataFrame([
        {
            "date": date, "entry_date": date + pd.offsets.BDay(1),
            "exit_date": date + pd.offsets.BDay(2), "symbol": symbol,
            "directional_oracle_proba_extreme": probability, "keep": keep,
        }
        for symbol, probability, keep in (
            ("AAA", 0.9, False), ("BBB", 0.8, True), ("CCC", 0.7, True)
        )
    ])
    selected = schedule_dynamic_capacity(panel, max_positions=1, keep_column="keep")
    assert selected["symbol"].tolist() == ["BBB"]


def test_oof_training_requires_purged_history() -> None:
    rows = []
    for index in range(120):
        row = {feature: float(index % 7) for feature in MODEL_FEATURES}
        row.update({
            "fold": "2024-01-01", "exit_date": pd.Timestamp("2024-03-01"),
            "bad_trailing": index % 2, "date": pd.Timestamp("2024-02-01"),
        })
        rows.append(row)
    for index in range(12):
        row = {feature: float(index % 5) for feature in MODEL_FEATURES}
        row.update({
            "fold": "2024-07-01", "exit_date": pd.Timestamp("2024-08-01"),
            "bad_trailing": index % 2, "date": pd.Timestamp("2024-07-02"),
        })
        rows.append(row)
    scored, diagnostics = fit_oof_risk(
        pd.DataFrame(rows), E13Config(min_train_rows=100, iterations=1)
    )
    assert diagnostics[0]["status"] == "skipped"
    assert diagnostics[1]["status"] == "scored"
    assert len(scored) == 12
    assert scored["pre_entry_trailing_risk"].between(0, 1).all()
    assert "keep_absolute_0.20" in scored
    assert "train_risk_thresholds" in diagnostics[1]


def test_config_rejects_invalid_primary_veto() -> None:
    with pytest.raises(ValueError, match="primary_veto_fraction"):
        E13Config(primary_veto_fraction=0.0)
