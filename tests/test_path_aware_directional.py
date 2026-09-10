from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory import path_aware_directional as path
from modelFactory.shared_directional import LONG_TARGET_COL, P_LONG_COL, P_SHORT_COL


def _bars() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    close = np.full(60, 100.0)
    return pd.DataFrame({
        "date": dates,
        "symbol": "AAA",
        "open": close.copy(),
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": 1_000_000.0,
    })


def test_barrier_race_config_matches_prefixed_contract() -> None:
    config = path.BarrierRaceConfig()
    assert config.stop_atr_mult == pytest.approx(2.5)
    assert config.tp_atr_mult == pytest.approx(3.0)
    assert config.tp_max_pct == pytest.approx(0.07)
    assert config.max_sessions == 20
    assert config.max_entry_gap_pct == pytest.approx(0.03)


def test_build_path_label_panel_filters_large_next_open_gap() -> None:
    bars = _bars()
    bars.loc[21, "open"] = 110.0
    panel = path.build_path_label_panel(
        bars, path.BarrierRaceConfig(max_sessions=5, max_entry_gap_pct=0.03)
    )
    signal = panel.loc[panel["date"].eq(bars.loc[20, "date"])].iloc[0]
    assert signal["path_entry_gap_abs"] == pytest.approx(0.10)
    assert not bool(signal["path_entry_gap_eligible"])
    assert pd.isna(signal[path.LONG_NET_RETURN_COL])
    assert pd.isna(signal[path.SHORT_NET_RETURN_COL])
    assert pd.isna(signal[LONG_TARGET_COL])
    assert pd.isna(signal[path.SHORT_TARGET_COL])


def test_path_targets_allow_both_sides_to_be_unprofitable() -> None:
    panel = path.build_path_label_panel(
        _bars(),
        path.BarrierRaceConfig(
            max_sessions=5, spread_bps=5.0, commission_bps=1.0, slippage_bps=2.0,
        ),
    )
    valid = panel.dropna(subset=[LONG_TARGET_COL, path.SHORT_TARGET_COL])
    assert not valid.empty
    assert bool((valid[LONG_TARGET_COL].eq(0) & valid[path.SHORT_TARGET_COL].eq(0)).all())


def test_evaluate_path_aware_oos_uses_side_specific_net_returns() -> None:
    rows = []
    for date in pd.date_range("2024-01-02", periods=3, freq="B"):
        for index in range(20):
            long_return = -0.04 + index * 0.005
            short_return = 0.04 - index * 0.005
            rows.append({
                "date": date, "symbol": f"S{index:02d}",
                path.LONG_NET_RETURN_COL: long_return,
                path.SHORT_NET_RETURN_COL: short_return,
                LONG_TARGET_COL: int(long_return > 0),
                path.SHORT_TARGET_COL: int(short_return > 0),
                P_LONG_COL: index / 19,
                P_SHORT_COL: 1.0 - index / 19,
            })
    metrics = path.evaluate_path_aware_oos(pd.DataFrame(rows), top_fraction=0.10)
    assert metrics["auc_long"] == pytest.approx(1.0)
    assert metrics["auc_short"] == pytest.approx(1.0)
    assert metrics["long_top_decile"]["mean_net_return"] > 0
    assert metrics["short_top_decile"]["mean_net_return"] > 0
    assert metrics["long_top_decile"]["return_lift_vs_matched"] > 0
    assert metrics["short_top_decile"]["return_lift_vs_matched"] > 0
    assert metrics["policies"][path.PRIMARY_POLICY]["coverage"] > 0
