from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.config import DataConfig, TargetOptimizationConfig
from modelFactory.target_optimization import optimize_target_horizon, score_target_candidate


def _make_prices(n: int = 80) -> pd.DataFrame:
    close = pd.Series(100 + np.arange(n) * 0.8, dtype=float)
    return pd.DataFrame({"close": close, "adj_close": close})


def test_score_target_candidate_returns_positive_trade_rate() -> None:
    df = _make_prices()
    cfg = DataConfig(target_mode="binary", target_up_threshold=0.0)

    result = score_target_candidate(df, horizon=5, data_cfg=cfg, min_trades_fraction=0.05)

    assert result.trade_rate > 0.05
    assert result.horizon == 5


def test_optimize_target_horizon_returns_candidate_summary() -> None:
    df = _make_prices(120)
    cfg = DataConfig(target_mode="binary", target_up_threshold=0.0)
    opt_cfg = TargetOptimizationConfig(enabled=True, candidate_horizons=(3, 5, 10), min_trades_fraction=0.05)

    result = optimize_target_horizon(df, data_cfg=cfg, opt_cfg=opt_cfg)

    assert result["selected_horizon"] in {3, 5, 10}
    assert len(result["candidates"]) == 3
