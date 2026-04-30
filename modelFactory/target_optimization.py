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
    target_up_threshold: float
    target_down_threshold: float
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
    positive_threshold: float | None = None,
    negative_threshold: float | None = None,
) -> TargetCandidateResult:
    up_threshold = float(data_cfg.target_up_threshold if positive_threshold is None else positive_threshold)
    down_threshold = float(data_cfg.target_down_threshold if negative_threshold is None else negative_threshold)
    future_return = compute_future_return(df, horizon=horizon)
    target = build_target(
        df,
        horizon=horizon,
        mode=data_cfg.target_mode,
        positive_threshold=up_threshold,
        negative_threshold=down_threshold,
    )
    mask = target.notna() & future_return.notna()
    trade_rate = float(mask.mean())
    if trade_rate < min_trades_fraction:
        return TargetCandidateResult(horizon, up_threshold, down_threshold, -1.0, trade_rate, 0.0, None, None)

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
    return TargetCandidateResult(horizon, up_threshold, down_threshold, score, trade_rate, class_balance, mean_pos, mean_neg)


def optimize_target_parameters(
    df: pd.DataFrame,
    *,
    data_cfg: DataConfig,
    opt_cfg: TargetOptimizationConfig,
) -> dict[str, Any]:
    candidates = []
    for horizon in opt_cfg.candidate_horizons:
        for up_threshold in opt_cfg.candidate_up_thresholds:
            for down_threshold in opt_cfg.candidate_down_thresholds:
                if down_threshold > up_threshold:
                    continue
                candidates.append(
                    score_target_candidate(
                        df,
                        horizon=horizon,
                        data_cfg=data_cfg,
                        min_trades_fraction=opt_cfg.min_trades_fraction,
                        positive_threshold=up_threshold,
                        negative_threshold=down_threshold,
                    )
                )
    if not candidates:
        raise ValueError("Aucune combinaison target valide n'a pu être générée.")
    best = max(candidates, key=lambda c: c.score)
    return {
        "selected_horizon": int(best.horizon),
        "selected_target_up_threshold": float(best.target_up_threshold),
        "selected_target_down_threshold": float(best.target_down_threshold),
        "selected_score": float(best.score),
        "candidates": [
            {
                "horizon": c.horizon,
                "target_up_threshold": c.target_up_threshold,
                "target_down_threshold": c.target_down_threshold,
                "score": c.score,
                "trade_rate": c.trade_rate,
                "class_balance": c.class_balance,
                "mean_positive_return": c.mean_positive_return,
                "mean_negative_return": c.mean_negative_return,
            }
            for c in candidates
        ],
    }


def optimize_target_horizon(
    df: pd.DataFrame,
    *,
    data_cfg: DataConfig,
    opt_cfg: TargetOptimizationConfig,
) -> dict[str, Any]:
    """Wrapper backward-compatible : optimise uniquement l'horizon avec les seuils courants."""
    narrowed_opt_cfg = TargetOptimizationConfig(
        enabled=opt_cfg.enabled,
        candidate_horizons=opt_cfg.candidate_horizons,
        candidate_up_thresholds=(data_cfg.target_up_threshold,),
        candidate_down_thresholds=(data_cfg.target_down_threshold,),
        min_trades_fraction=opt_cfg.min_trades_fraction,
    )
    result = optimize_target_parameters(df, data_cfg=data_cfg, opt_cfg=narrowed_opt_cfg)
    return {
        "selected_horizon": result["selected_horizon"],
        "selected_score": result["selected_score"],
        "candidates": [
            {
                "horizon": candidate["horizon"],
                "score": candidate["score"],
                "trade_rate": candidate["trade_rate"],
                "class_balance": candidate["class_balance"],
                "mean_positive_return": candidate["mean_positive_return"],
                "mean_negative_return": candidate["mean_negative_return"],
            }
            for candidate in result["candidates"]
        ],
    }

