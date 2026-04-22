"""modelFactory/target_optimization.py — Sélection d'horizon swing et scoring de target."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from modelFactory.config import DataConfig, TargetOptimizationConfig
from modelFactory.features import build_target, compute_future_return


@dataclass(frozen=True, slots=True)
class TargetCandidateResult:
    horizon: int
    score: float
    trade_rate: float
    class_balance: float
    mean_positive_return: float | None
    mean_negative_return: float | None


def score_target_candidate(
    df: pd.DataFrame,
    *,
    horizon: int,
    data_cfg: DataConfig,
    min_trades_fraction: float,
) -> TargetCandidateResult:
    future_return = compute_future_return(df, horizon=horizon)
    target = build_target(
        df,
        horizon=horizon,
        mode=data_cfg.target_mode,
        positive_threshold=data_cfg.target_up_threshold,
        negative_threshold=data_cfg.target_down_threshold,
    )
    mask = target.notna() & future_return.notna()
    trade_rate = float(mask.mean())
    if trade_rate < min_trades_fraction:
        return TargetCandidateResult(horizon, -1.0, trade_rate, 0.0, None, None)

    active_target = target.loc[mask].astype(int)
    active_returns = future_return.loc[mask]
    pos_mask = active_target == 1
    neg_mask = active_target == 0
    pos_rate = float(pos_mask.mean())
    class_balance = 1.0 - abs(pos_rate - 0.5) / 0.5 if len(active_target) else 0.0
    mean_pos = float(active_returns.loc[pos_mask].mean()) if pos_mask.any() else None
    mean_neg = float(active_returns.loc[neg_mask].mean()) if neg_mask.any() else None
    separation = (mean_pos - mean_neg) if mean_pos is not None and mean_neg is not None else 0.0
    score = float(max(trade_rate, 1e-8) * max(class_balance, 0.0) * max(separation, 0.0))
    return TargetCandidateResult(horizon, score, trade_rate, class_balance, mean_pos, mean_neg)


def optimize_target_horizon(
    df: pd.DataFrame,
    *,
    data_cfg: DataConfig,
    opt_cfg: TargetOptimizationConfig,
) -> dict[str, Any]:
    candidates = [
        score_target_candidate(
            df,
            horizon=h,
            data_cfg=data_cfg,
            min_trades_fraction=opt_cfg.min_trades_fraction,
        )
        for h in opt_cfg.candidate_horizons
    ]
    best = max(candidates, key=lambda c: c.score)
    return {
        "selected_horizon": int(best.horizon),
        "selected_score": float(best.score),
        "candidates": [
            {
                "horizon": c.horizon,
                "score": c.score,
                "trade_rate": c.trade_rate,
                "class_balance": c.class_balance,
                "mean_positive_return": c.mean_positive_return,
                "mean_negative_return": c.mean_negative_return,
            }
            for c in candidates
        ],
    }
