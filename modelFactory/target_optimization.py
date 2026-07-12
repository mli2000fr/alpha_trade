"""modelFactory/target_optimization.py — Sélection d'horizon swing et scoring de target.

Sprint Maître 3 — correction multiclasses :
- ``score_target_candidate()`` sépare correctement short, flat et long en ternaire.
- Ajout du scoring triple-barrier.
- ``score_triple_barrier_candidate()`` évalue un TripleBarrierConfig sur le train.
- ``optimize_target_parameters()`` optimise les paramètres triple-barrier
  quand ``label_method='triple_barrier'`` (Section 17, Point 3.3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.config import DataConfig, TargetOptimizationConfig
from modelFactory.features import build_target, compute_future_return
from modelFactory.labeling import (
    TripleBarrierConfig,
    TripleBarrierLabel,
    build_triple_barrier_label,
    build_triple_barrier_labels,
)


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
    # ── Sprint Maître 3 : stats ternaires ──────────────────────────────
    mean_short_return: float | None = None
    long_pct: float = 0.0
    flat_pct: float = 0.0
    short_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class TripleBarrierCandidateResult:
    """Résultat d'évaluation d'un candidat TripleBarrierConfig sur le train."""
    stop_atr_mult: float
    tp_atr_mult: float
    max_sessions: int
    score: float
    trade_rate: float
    class_balance: float
    long_pct: float
    short_pct: float
    flat_pct: float
    stop_hit_pct: float
    tp_hit_pct: float
    expiry_pct: float
    mean_long_return: float | None
    mean_short_return: float | None


def score_target_candidate(
    df: pd.DataFrame,
    *,
    horizon: int,
    data_cfg: DataConfig,
    min_trades_fraction: float,
    positive_threshold: float | None = None,
    negative_threshold: float | None = None,
) -> TargetCandidateResult:
    """Score un candidat de target (Sprint Maître 3 : correction multiclasses).

    En mode ternaire, les trois classes (short=-1, flat=0, long=+1) sont
    traitées séparément. Le class balance est calculé sur les 3 classes.
    """
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

    is_ternary = data_cfg.target_mode == "ternary"

    if is_ternary:
        # ── Sprint Maître 3 : séparation short/flat/long ──────────────
        short_mask = active_target == -1
        flat_mask = active_target == 0
        long_mask = active_target == 1
        long_pct = float(long_mask.mean())
        short_pct = float(short_mask.mean())
        flat_pct = float(flat_mask.mean())

        # Class balance ternaire : 1.0 = équilibré, 0.0 = tout dans une classe
        total = len(active_target)
        if total > 0:
            ideal = 1.0 / 3.0
            class_balance = 1.0 - (
                abs(long_pct - ideal) + abs(short_pct - ideal) + abs(flat_pct - ideal)
            ) / 2.0
        else:
            class_balance = 0.0

        mean_long = float(active_returns.loc[long_mask].mean()) if long_mask.any() else None
        mean_short_ret = float(active_returns.loc[short_mask].mean()) if short_mask.any() else None

        # Score : trade_rate * class_balance * separation
        separation = 0.0
        if mean_long is not None and mean_short_ret is not None:
            separation = max(mean_long - mean_short_ret, 0.0)
        elif mean_long is not None:
            separation = max(mean_long, 0.0)
        elif mean_short_ret is not None:
            separation = max(-mean_short_ret, 0.0)

        score = float(max(trade_rate, 1e-8) * max(class_balance, 0.0) * max(separation, 0.0))
        return TargetCandidateResult(
            horizon, up_threshold, down_threshold, score, trade_rate, class_balance,
            mean_long, mean_short_ret,
            mean_short_return=mean_short_ret,
            long_pct=long_pct, flat_pct=flat_pct, short_pct=short_pct,
        )
    else:
        # ── Binaire / swing_cash (comportement legacy) ─────────────────
        pos_mask = active_target == 1
        neg_mask = active_target == 0
        pos_rate = float(pos_mask.mean())
        class_balance = 1.0 - abs(pos_rate - 0.5) / 0.5 if len(active_target) else 0.0
        mean_pos = float(active_returns.loc[pos_mask].mean()) if pos_mask.any() else None
        mean_neg = float(active_returns.loc[neg_mask].mean()) if neg_mask.any() else None
        separation = (mean_pos - mean_neg) if mean_pos is not None and mean_neg is not None else 0.0
        score = float(max(trade_rate, 1e-8) * max(class_balance, 0.0) * max(separation, 0.0))
        return TargetCandidateResult(
            horizon, up_threshold, down_threshold, score, trade_rate, class_balance,
            mean_pos, mean_neg,
            long_pct=pos_rate, flat_pct=1.0 - pos_rate, short_pct=0.0,
        )


def score_triple_barrier_candidate(
    df: pd.DataFrame,
    *,
    stop_atr_mult: float,
    tp_atr_mult: float,
    max_sessions: int,
    data_cfg: DataConfig,
    min_trades_fraction: float,
) -> TripleBarrierCandidateResult:
    """Score un candidat de paramètres triple-barrier sur le train uniquement.

    La fonction construit les labels triple-barrier sur ``df`` (qui DOIT être
    le fold train uniquement) et évalue la qualité de la segmentation obtenue.

    Le score est construit à partir de :
    - trade_rate (fraction de trades qui atteignent une barrière)
    - class_balance (équilibre long/short/flat)
    - séparation des rendements (mean_long - mean_short)

    Returns
    -------
    TripleBarrierCandidateResult
        Résultat contenant le score et les métriques détaillées.
    """
    tb_cfg = TripleBarrierConfig(
        stop_atr_mult=stop_atr_mult,
        tp_atr_mult=tp_atr_mult,
        max_sessions=max_sessions,
    )
    labels_df: pd.DataFrame = build_triple_barrier_labels(df, cfg=tb_cfg)
    labels: pd.Series = labels_df["label"]

    # Calculer les rendements forward sur max_sessions pour évaluer la qualité
    future_return = compute_future_return(df, horizon=max_sessions)

    mask = labels.notna() & future_return.notna()
    trade_rate = float(mask.mean())

    if trade_rate < min_trades_fraction:
        return TripleBarrierCandidateResult(
            stop_atr_mult, tp_atr_mult, max_sessions,
            score=-1.0, trade_rate=trade_rate, class_balance=0.0,
            long_pct=0.0, short_pct=0.0, flat_pct=0.0,
            stop_hit_pct=0.0, tp_hit_pct=0.0, expiry_pct=0.0,
            mean_long_return=None, mean_short_return=None,
        )

    active_labels = labels.loc[mask].astype(int)
    active_returns = future_return.loc[mask]

    # Distribution des classes (label: 1=long, -1=short, 0=flat)
    long_mask = active_labels == 1
    short_mask = active_labels == -1
    flat_mask = active_labels == 0
    long_pct = float(long_mask.mean())
    short_pct = float(short_mask.mean())
    flat_pct = float(flat_mask.mean())

    # Distribution des barrières atteintes via exit_reason
    exit_reasons = labels_df["exit_reason"].loc[mask]
    stop_hit_pct = float((exit_reasons == "stop_loss").mean())
    tp_hit_pct = float((exit_reasons == "take_profit").mean())
    expiry_pct = float((exit_reasons == "expiry").mean())

    # Class balance ternaire
    ideal = 1.0 / 3.0
    class_balance = 1.0 - (
        abs(long_pct - ideal) + abs(short_pct - ideal) + abs(flat_pct - ideal)
    ) / 2.0
    class_balance = max(0.0, class_balance)

    # Rendements moyens par classe
    mean_long = float(active_returns.loc[long_mask].mean()) if long_mask.any() else None
    mean_short = float(active_returns.loc[short_mask].mean()) if short_mask.any() else None

    # Séparation
    separation = 0.0
    if mean_long is not None and mean_short is not None:
        separation = max(mean_long - mean_short, 0.0)
    elif mean_long is not None:
        separation = max(mean_long, 0.0)
    elif mean_short is not None:
        separation = max(-mean_short, 0.0)

    score = float(max(trade_rate, 1e-8) * max(class_balance, 0.0) * max(separation, 0.0))

    return TripleBarrierCandidateResult(
        stop_atr_mult, tp_atr_mult, max_sessions,
        score=score, trade_rate=trade_rate, class_balance=class_balance,
        long_pct=long_pct, short_pct=short_pct, flat_pct=flat_pct,
        stop_hit_pct=stop_hit_pct, tp_hit_pct=tp_hit_pct, expiry_pct=expiry_pct,
        mean_long_return=mean_long, mean_short_return=mean_short,
    )


def optimize_triple_barrier_parameters(
    df: pd.DataFrame,
    *,
    data_cfg: DataConfig,
    opt_cfg: TargetOptimizationConfig,
) -> dict[str, Any]:
    """Optimise les paramètres triple-barrier (stop_atr_mult, tp_atr_mult, max_sessions)
    sur le fold train uniquement.

    Cette fonction ne doit JAMAIS recevoir de données de validation ou de test.
    """
    candidates: list[TripleBarrierCandidateResult] = []
    for stop_m in opt_cfg.candidate_stop_atr_mults:
        for tp_m in opt_cfg.candidate_tp_atr_mults:
            for max_s in opt_cfg.candidate_max_sessions:
                candidates.append(
                    score_triple_barrier_candidate(
                        df,
                        stop_atr_mult=stop_m,
                        tp_atr_mult=tp_m,
                        max_sessions=max_s,
                        data_cfg=data_cfg,
                        min_trades_fraction=opt_cfg.min_trades_fraction,
                    )
                )
    if not candidates:
        raise ValueError("Aucune combinaison triple-barrier valide n'a pu être générée.")
    best = max(candidates, key=lambda c: c.score)
    return {
        "selected_triple_barrier_stop_atr_mult": float(best.stop_atr_mult),
        "selected_triple_barrier_tp_atr_mult": float(best.tp_atr_mult),
        "selected_triple_barrier_max_sessions": int(best.max_sessions),
        "selected_triple_barrier_score": float(best.score),
        "triple_barrier_candidates": [
            {
                "stop_atr_mult": c.stop_atr_mult,
                "tp_atr_mult": c.tp_atr_mult,
                "max_sessions": c.max_sessions,
                "score": c.score,
                "trade_rate": c.trade_rate,
                "class_balance": c.class_balance,
                "long_pct": c.long_pct,
                "short_pct": c.short_pct,
                "flat_pct": c.flat_pct,
                "stop_hit_pct": c.stop_hit_pct,
                "tp_hit_pct": c.tp_hit_pct,
                "expiry_pct": c.expiry_pct,
                "mean_long_return": c.mean_long_return,
                "mean_short_return": c.mean_short_return,
            }
            for c in candidates
        ],
    }


def optimize_target_parameters(
    df: pd.DataFrame,
    *,
    data_cfg: DataConfig,
    opt_cfg: TargetOptimizationConfig,
) -> dict[str, Any]:
    """Optimise les paramètres de target sur le fold train uniquement.

    Pour ``label_method='fixed_horizon'``, optimise horizon, up_threshold, down_threshold.
    Pour ``label_method='triple_barrier'``, optimise stop_atr_mult, tp_atr_mult, max_sessions
    (et horizon si ``candidate_horizons`` est fourni).

    Le paramètre ``df`` DOIT contenir uniquement les données du fold train.
    Aucune donnée de validation ou de test ne doit être passée ici.
    """
    result: dict[str, Any] = {}

    # ── Optimisation fixed_horizon ─────────────────────────────────────
    if data_cfg.label_method == "fixed_horizon":
        candidates: list[TargetCandidateResult] = []
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
        result.update({
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
        })

    # ── Optimisation triple_barrier (Section 17 Point 3.3) ─────────────
    if data_cfg.label_method == "triple_barrier":
        tb_result = optimize_triple_barrier_parameters(
            df, data_cfg=data_cfg, opt_cfg=opt_cfg,
        )
        result.update(tb_result)

        # Si des horizons candidats sont fournis, on optimise aussi l'horizon
        # (utilisé comme max_sessions par le triple-barrier via DataConfig.forecast_horizon)
        if opt_cfg.candidate_horizons:
            horizon_candidates: list[TargetCandidateResult] = []
            for horizon in opt_cfg.candidate_horizons:
                horizon_candidates.append(
                    score_target_candidate(
                        df,
                        horizon=horizon,
                        data_cfg=data_cfg,
                        min_trades_fraction=opt_cfg.min_trades_fraction,
                    )
                )
            if horizon_candidates:
                best_h = max(horizon_candidates, key=lambda c: c.score)
                result["selected_horizon"] = int(best_h.horizon)
                result["selected_score"] = float(best_h.score)
                result["horizon_candidates"] = [
                    {
                        "horizon": c.horizon,
                        "score": c.score,
                        "trade_rate": c.trade_rate,
                        "class_balance": c.class_balance,
                        "mean_positive_return": c.mean_positive_return,
                        "mean_negative_return": c.mean_negative_return,
                    }
                    for c in horizon_candidates
                ]

    if not result:
        raise ValueError(
            f"label_method '{data_cfg.label_method}' non supporté par optimize_target_parameters."
        )
    return result


def optimize_target_horizon(
    df: pd.DataFrame,
    *,
    data_cfg: DataConfig,
    opt_cfg: TargetOptimizationConfig,
) -> dict[str, Any]:
    """Wrapper backward-compatible : optimise uniquement l'horizon avec les seuils courants.

    Pour ``label_method='triple_barrier'``, optimise uniquement max_sessions
    (pas les multiples ATR).
    """
    narrowed_opt_cfg = TargetOptimizationConfig(
        enabled=opt_cfg.enabled,
        candidate_horizons=opt_cfg.candidate_horizons,
        candidate_up_thresholds=(data_cfg.target_up_threshold,),
        candidate_down_thresholds=(data_cfg.target_down_threshold,),
        candidate_stop_atr_mults=(data_cfg.triple_barrier_stop_atr_mult,),
        candidate_tp_atr_mults=(data_cfg.triple_barrier_tp_atr_mult,),
        candidate_max_sessions=opt_cfg.candidate_horizons,
        min_trades_fraction=opt_cfg.min_trades_fraction,
    )
    result = optimize_target_parameters(df, data_cfg=data_cfg, opt_cfg=narrowed_opt_cfg)
    return {
        "selected_horizon": result.get("selected_horizon"),
        "selected_score": result.get("selected_score"),
        "candidates": result.get("candidates") or result.get("horizon_candidates") or [],
    }

