"""E3 research-only: direction conditionnelle Oracle avec cibles de chemin.

Le module entraîne deux têtes mutualisées indépendantes sur le TOP20 Oracle
strictement OOF. Les labels ne sont plus des rendements terminaux : chaque
signal est rejoué LONG et SHORT depuis l'open suivant avec des barrières fixes,
des coûts explicites et une résolution intrabar conservatrice.

Ce contrat ``barrier_race_v1`` isole la prédictibilité de la direction. Il ne
prétend pas reproduire le trailing de production et ne peut pas être servi.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.labeling import TripleBarrierConfig, build_triple_barrier_labels
from modelFactory.oracle.train import get_universe_symbols, roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import (
    DEFAULT_ARTIFACTS_ROOT,
    DEFAULT_PROFILE,
    LONG_TARGET_COL,
    ORACLE_GATE_SCORE_COL,
    P_LONG_COL,
    P_SHORT_COL,
    SharedDirectionalConfig,
    _fit_dual_head,
    _prepare_X,
    _semester_label,
    _tail,
    build_shared_dataset,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

SHORT_TARGET_COL = "path_short_target"
LONG_NET_RETURN_COL = "path_long_net_return"
SHORT_NET_RETURN_COL = "path_short_net_return"
LONG_EXIT_REASON_COL = "path_long_exit_reason"
SHORT_EXIT_REASON_COL = "path_short_exit_reason"
PATH_DIRECTION_SCORE_COL = "path_direction_score"
PRIMARY_POLICY = "p0.50_m0.05"


@dataclass(frozen=True, slots=True)
class BarrierRaceConfig:
    stop_atr_mult: float = 2.5
    tp_atr_mult: float = 3.0
    tp_max_pct: float = 0.07
    max_sessions: int = 20
    atr_window: int = 14
    min_atr: float = 0.001
    spread_bps: float = 5.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    borrow_fee_annual: float = 0.003
    entry_delay_sessions: int = 1
    max_entry_gap_pct: float = 0.03

    def __post_init__(self) -> None:
        TripleBarrierConfig(**self.labeler_kwargs())
        if self.max_entry_gap_pct < 0:
            raise ValueError("max_entry_gap_pct doit être >= 0.")

    def labeler_kwargs(self) -> dict[str, Any]:
        return {
            "stop_atr_mult": self.stop_atr_mult,
            "tp_atr_mult": self.tp_atr_mult,
            "tp_max_pct": self.tp_max_pct,
            "max_sessions": self.max_sessions,
            "atr_window": self.atr_window,
            "min_atr": self.min_atr,
            "spread_bps": self.spread_bps,
            "commission_bps": self.commission_bps,
            "slippage_bps": self.slippage_bps,
            "borrow_fee_annual": self.borrow_fee_annual,
            "entry_delay_sessions": self.entry_delay_sessions,
        }


def build_path_label_panel(
    bars: pd.DataFrame,
    config: BarrierRaceConfig,
) -> pd.DataFrame:
    """Construit les deux replays sans utiliser les dates Oracle futures."""
    required = {"date", "symbol", "open", "high", "low", "close"}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"Barres incomplètes pour E3: {missing}")
    cfg = TripleBarrierConfig(**config.labeler_kwargs())
    outputs: list[pd.DataFrame] = []
    for symbol, raw in bars.groupby("symbol", sort=False):
        part = raw.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        if len(part) <= cfg.max_sessions + cfg.entry_delay_sessions:
            continue
        long_labels = build_triple_barrier_labels(part, cfg, side="long")
        short_labels = build_triple_barrier_labels(part, cfg, side="short")
        next_open = pd.to_numeric(part["open"], errors="coerce").shift(-cfg.entry_delay_sessions)
        signal_close = pd.to_numeric(part["close"], errors="coerce")
        gap = (next_open / signal_close - 1.0).abs()
        gap_eligible = gap.notna()
        if config.max_entry_gap_pct > 0:
            gap_eligible &= gap.le(config.max_entry_gap_pct)
        output = pd.DataFrame({
            "date": pd.to_datetime(part["date"], errors="coerce").dt.normalize(),
            "symbol": str(symbol).upper(),
            LONG_NET_RETURN_COL: pd.to_numeric(long_labels["net_return_pct"], errors="coerce"),
            SHORT_NET_RETURN_COL: pd.to_numeric(short_labels["net_return_pct"], errors="coerce"),
            LONG_EXIT_REASON_COL: long_labels["exit_reason"],
            SHORT_EXIT_REASON_COL: short_labels["exit_reason"],
            "path_entry_gap_abs": gap,
            "path_entry_gap_eligible": gap_eligible,
        })
        invalid = ~gap_eligible
        output.loc[invalid, [
            LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
            LONG_EXIT_REASON_COL, SHORT_EXIT_REASON_COL,
        ]] = pd.NA
        output[LONG_TARGET_COL] = output[LONG_NET_RETURN_COL].gt(0).astype(float).where(
            output[LONG_NET_RETURN_COL].notna()
        )
        output[SHORT_TARGET_COL] = output[SHORT_NET_RETURN_COL].gt(0).astype(float).where(
            output[SHORT_NET_RETURN_COL].notna()
        )
        outputs.append(output)
    if not outputs:
        return pd.DataFrame()
    panel = pd.concat(outputs, ignore_index=True)
    if panel.duplicated(["date", "symbol"]).any():
        raise ValueError("Labels E3 non uniques par date/symbole.")
    return panel


def attach_path_targets(oracle_pool: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date", "symbol", LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
        LONG_EXIT_REASON_COL, SHORT_EXIT_REASON_COL, "path_entry_gap_abs",
        "path_entry_gap_eligible", LONG_TARGET_COL, SHORT_TARGET_COL,
    ]
    missing = sorted(set(columns).difference(panel.columns))
    if missing:
        raise ValueError(f"Panel de labels E3 incomplet: {missing}")
    return oracle_pool.merge(panel[columns], on=["date", "symbol"], how="left", validate="one_to_one")


def _head_metrics(work: pd.DataFrame, target: str, probability: str) -> dict[str, Any]:
    y = work[target].astype(int).to_numpy()
    p = work[probability].astype(float).clip(0.0, 1.0).to_numpy()
    return {
        "base_rate": float(y.mean()),
        "auc": roc_auc(y, p) if len(np.unique(y)) == 2 else None,
        "brier": float(np.mean(np.square(p - y))),
    }


def _concentration(selected: pd.DataFrame, return_col: str) -> dict[str, Any]:
    if selected.empty:
        return {"top1_positive_contribution_share": None, "top5_positive_contribution_share": None}
    totals = selected.groupby("symbol")[return_col].sum().sort_values(ascending=False)
    positive_total = float(totals.clip(lower=0).sum())
    return {
        "top1_positive_contribution_share": (
            float(max(0.0, totals.iloc[0]) / positive_total) if positive_total > 0 else None
        ),
        "top5_positive_contribution_share": (
            float(totals.head(5).clip(lower=0).sum() / positive_total) if positive_total > 0 else None
        ),
        "top_profit_symbols": [str(value) for value in totals.head(5).index],
    }


def _side_metrics(
    selected: pd.DataFrame,
    pool: pd.DataFrame,
    *,
    side: str,
) -> dict[str, Any]:
    return_col = LONG_NET_RETURN_COL if side == "long" else SHORT_NET_RETURN_COL
    target_col = LONG_TARGET_COL if side == "long" else SHORT_TARGET_COL
    if selected.empty:
        return {
            "rows": 0, "dates": 0, "symbols": 0, "success_rate": None,
            "mean_net_return": None, "median_net_return": None,
            "matched_date_return": None, "return_lift_vs_matched": None,
            "concentration": _concentration(selected, return_col),
        }
    date_base = pool.groupby("date")[return_col].mean()
    matched = float(date_base.reindex(selected["date"]).mean())
    values = pd.to_numeric(selected[return_col], errors="coerce")
    return {
        "rows": int(len(selected)),
        "dates": int(selected["date"].nunique()),
        "symbols": int(selected["symbol"].nunique()),
        "success_rate": float(selected[target_col].mean()),
        "mean_net_return": float(values.mean()),
        "median_net_return": float(values.median()),
        "matched_date_return": matched,
        "return_lift_vs_matched": float(values.mean() - matched),
        "concentration": _concentration(selected, return_col),
    }


def evaluate_path_aware_oos(frame: pd.DataFrame, top_fraction: float = 0.10) -> dict[str, Any]:
    required = [
        "date", "symbol", LONG_TARGET_COL, SHORT_TARGET_COL,
        LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL, P_LONG_COL, P_SHORT_COL,
    ]
    work = frame.dropna(subset=required).copy()
    if work.empty:
        return {"rows": 0, "auc_long": None, "auc_short": None}
    work[PATH_DIRECTION_SCORE_COL] = work[P_LONG_COL] - work[P_SHORT_COL]
    long_tail = _tail(work, P_LONG_COL, top_fraction, ascending=False)
    short_tail = _tail(work, P_SHORT_COL, top_fraction, ascending=False)

    policies: dict[str, Any] = {}
    for min_probability in (0.50, 0.55):
        for min_margin in (0.00, 0.05, 0.10):
            margin = work[PATH_DIRECTION_SCORE_COL]
            long_selected = work[
                work[P_LONG_COL].ge(min_probability) & margin.ge(min_margin)
            ]
            short_selected = work[
                work[P_SHORT_COL].ge(min_probability) & (-margin).ge(min_margin)
            ]
            key = f"p{min_probability:.2f}_m{min_margin:.2f}"
            policies[key] = {
                "coverage": float((len(long_selected) + len(short_selected)) / len(work)),
                "long": _side_metrics(long_selected, work, side="long"),
                "short": _side_metrics(short_selected, work, side="short"),
            }

    semesters: dict[str, Any] = {}
    for semester, group in work.groupby(work["date"].map(_semester_label), sort=True):
        semesters[str(semester)] = {
            "rows": int(len(group)),
            "long_top": _side_metrics(
                _tail(group, P_LONG_COL, top_fraction, ascending=False), group, side="long"
            ),
            "short_top": _side_metrics(
                _tail(group, P_SHORT_COL, top_fraction, ascending=False), group, side="short"
            ),
        }
    long_head = _head_metrics(work, LONG_TARGET_COL, P_LONG_COL)
    short_head = _head_metrics(work, SHORT_TARGET_COL, P_SHORT_COL)
    return {
        "rows": int(len(work)),
        "auc_long": long_head["auc"],
        "auc_short": short_head["auc"],
        "long_head": long_head,
        "short_head": short_head,
        "both_profitable_rate": float(
            (work[LONG_TARGET_COL].eq(1) & work[SHORT_TARGET_COL].eq(1)).mean()
        ),
        "neither_profitable_rate": float(
            (work[LONG_TARGET_COL].eq(0) & work[SHORT_TARGET_COL].eq(0)).mean()
        ),
        "long_top_decile": _side_metrics(long_tail, work, side="long"),
        "short_top_decile": _side_metrics(short_tail, work, side="short"),
        "policies": policies,
        "semesters": semesters,
    }


def _fold_stability(folds: list[dict[str, Any]], overall: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for side in ("long", "short"):
        aucs = np.asarray([fold[f"auc_{side}"] for fold in folds], dtype=float)
        lifts = np.asarray([
            fold[f"{side}_top_decile"]["return_lift_vs_matched"] for fold in folds
        ], dtype=float)
        returns = np.asarray([
            fold[f"{side}_top_decile"]["mean_net_return"] for fold in folds
        ], dtype=float)
        concentration = overall[f"{side}_top_decile"]["concentration"]
        gates = {
            "mean_auc_gte_0_53": bool(np.nanmean(aucs) >= 0.53),
            "auc_above_half_folds_gte_7": bool(np.sum(aucs > 0.5) >= 7),
            "return_lift_gte_0_0025": bool(
                overall[f"{side}_top_decile"]["return_lift_vs_matched"] >= 0.0025
            ),
            "positive_return_lift_folds_gte_7": bool(np.sum(lifts > 0) >= 7),
            "positive_net_return_folds_gte_7": bool(np.sum(returns > 0) >= 7),
            "top1_positive_contribution_lte_0_35": bool(
                concentration["top1_positive_contribution_share"] is not None
                and concentration["top1_positive_contribution_share"] <= 0.35
            ),
        }
        result[side] = {
            "mean_auc": float(np.nanmean(aucs)),
            "auc_above_half_folds": int(np.sum(aucs > 0.5)),
            "positive_return_lift_folds": int(np.sum(lifts > 0)),
            "positive_net_return_folds": int(np.sum(returns > 0)),
            "gates": gates,
            "all_gates_passed": bool(all(gates.values())),
        }
    return result


def train_path_aware(
    dataset: pd.DataFrame,
    feature_columns: list[str],
    categorical_columns: list[str],
    config: SharedDirectionalConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    target_columns = [LONG_TARGET_COL, SHORT_TARGET_COL]
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=config.min_train_dates,
        val_dates=config.val_dates,
        test_dates=config.test_dates,
        step_dates=config.step_dates,
        max_splits=config.max_splits,
        forecast_horizon=config.horizon,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E3 valide.")
    oos_parts: list[pd.DataFrame] = []
    fold_metrics: list[dict[str, Any]] = []
    long_iterations: list[int] = []
    short_iterations: list[int] = []
    for index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=target_columns).copy()
        valid = fold["val"].dropna(subset=target_columns).copy()
        test = fold["test"].dropna(subset=target_columns).copy()
        classes_valid = all(
            part[column].nunique() == 2
            for part in (train, valid)
            for column in target_columns
        )
        if not classes_valid or train.empty or valid.empty or test.empty:
            LOGGER.warning(
                "path_aware fold=%d ignoré: classes insuffisantes "
                "train=%s valid=%s test=%s",
                index,
                {column: train[column].value_counts(dropna=False).to_dict() for column in target_columns},
                {column: valid[column].value_counts(dropna=False).to_dict() for column in target_columns},
                {column: test[column].value_counts(dropna=False).to_dict() for column in target_columns},
            )
            continue
        long_model = _fit_dual_head(
            train, valid, feature_columns, categorical_columns, config, LONG_TARGET_COL
        )
        short_model = _fit_dual_head(
            train, valid, feature_columns, categorical_columns, config, SHORT_TARGET_COL
        )
        X_test = _prepare_X(test, feature_columns, categorical_columns)
        scored = test[[
            "date", "symbol", "future_return", "oracle_decile", ORACLE_GATE_SCORE_COL,
            LONG_TARGET_COL, SHORT_TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
            LONG_EXIT_REASON_COL, SHORT_EXIT_REASON_COL, "path_entry_gap_abs",
        ]].copy()
        scored[P_LONG_COL] = long_model.predict_proba(X_test)[:, 1]
        scored[P_SHORT_COL] = short_model.predict_proba(X_test)[:, 1]
        scored[PATH_DIRECTION_SCORE_COL] = scored[P_LONG_COL] - scored[P_SHORT_COL]
        scored["fold_index"] = index
        oos_parts.append(scored)
        metrics = evaluate_path_aware_oos(scored, config.top_fraction)
        metrics.update({
            "fold_index": index,
            "test_start": str(pd.Timestamp(test["date"].min()).date()),
            "test_end": str(pd.Timestamp(test["date"].max()).date()),
            "train_rows": int(len(train)), "valid_rows": int(len(valid)),
        })
        fold_metrics.append(metrics)
        long_iterations.append(max(1, int(long_model.get_best_iteration()) + 1))
        short_iterations.append(max(1, int(short_model.get_best_iteration()) + 1))
        LOGGER.info(
            "path_aware fold=%d aucL=%s aucS=%s long=%s short=%s",
            index, metrics["auc_long"], metrics["auc_short"],
            metrics["long_top_decile"]["mean_net_return"],
            metrics["short_top_decile"]["mean_net_return"],
        )
    if not oos_parts:
        raise ValueError("Tous les folds E3 ont été rejetés.")
    oos = pd.concat(oos_parts, ignore_index=True)
    overall = evaluate_path_aware_oos(oos, config.top_fraction)
    labeled = dataset.dropna(subset=target_columns).copy()
    long_iterations_final = max(10, int(np.median(long_iterations)))
    short_iterations_final = max(10, int(np.median(short_iterations)))
    final_long = _fit_dual_head(
        labeled, None, feature_columns, categorical_columns, config,
        LONG_TARGET_COL, iterations=long_iterations_final,
    )
    final_short = _fit_dual_head(
        labeled, None, feature_columns, categorical_columns, config,
        SHORT_TARGET_COL, iterations=short_iterations_final,
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    long_path = artifact_dir / "long_model.cbm"
    short_path = artifact_dir / "short_model.cbm"
    oos_path = artifact_dir / "oof_predictions.parquet"
    final_long.save_model(str(long_path))
    final_short.save_model(str(short_path))
    oos.to_parquet(oos_path, index=False)
    metrics = {
        "status": "completed", "research_only": True, "serving_ready": False,
        "model_role": "oracle_conditional_path_aware_dual",
        "n_folds": len(fold_metrics),
        "final_iterations": {"long": long_iterations_final, "short": short_iterations_final},
        "overall": overall, "folds": fold_metrics,
        "fold_stability": _fold_stability(fold_metrics, overall),
        "trained_rows": int(len(labeled)),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "artifact_paths": {
            "long_model": str(long_path), "short_model": str(short_path), "oof": str(oos_path),
        },
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_path_aware_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    training_config: SharedDirectionalConfig | None = None,
    barrier_config: BarrierRaceConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    barrier = barrier_config or BarrierRaceConfig()
    training = training_config or SharedDirectionalConfig(
        horizon=barrier.max_sessions, objective="dual_classifier",
        target_mode="dual_threshold", context_mode="none", amplitude_weighting=False,
    )
    training = replace(
        training, horizon=barrier.max_sessions, objective="dual_classifier",
        target_mode="dual_threshold", amplitude_weighting=False,
    )
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, oracle_batch_id, 20)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    base_config = replace(
        training, horizon=barrier.max_sessions, objective="classifier",
        target_mode="decile_direction",
    )
    oracle_pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols,
        start_date=start_date, end_date=end_date, gate_path=gate_path,
        profile=profile, config=base_config,
    )
    requested_start = pd.Timestamp(start_date).normalize()
    requested_end = pd.Timestamp(end_date).normalize()
    oracle_pool = oracle_pool[
        pd.to_datetime(oracle_pool["date"]).between(requested_start, requested_end)
    ].copy()
    if oracle_pool.empty:
        raise ValueError("Pool Oracle E3 vide dans la période demandée.")
    population = {
        **population,
        "rows_oracle_pool": int(len(oracle_pool)),
        "symbols": int(oracle_pool["symbol"].nunique()),
        "dates": int(oracle_pool["date"].nunique()),
        "requested_period_start": str(requested_start.date()),
        "requested_period_end": str(requested_end.date()),
        "actual_period_start": str(pd.Timestamp(oracle_pool["date"].min()).date()),
        "actual_period_end": str(pd.Timestamp(oracle_pool["date"].max()).date()),
    }
    warmup_start = (pd.Timestamp(start_date) - pd.offsets.BDay(barrier.atr_window + 5)).date()
    future_end = (pd.Timestamp(end_date) + pd.offsets.BDay(barrier.max_sessions + 2)).date()
    bars = load_universe_bars(
        engine, symbols, start_date=warmup_start, end_date=future_end,
    )
    panel = build_path_label_panel(bars, barrier)
    dataset = attach_path_targets(oracle_pool, panel)
    usable = dataset[[LONG_TARGET_COL, SHORT_TARGET_COL]].notna().all(axis=1)
    if int(usable.sum()) < 100:
        raise ValueError(f"Cibles E3 insuffisantes: {int(usable.sum())} lignes.")
    LOGGER.info(
        "path_aware labels rows=%d long_base=%.4f short_base=%.4f both=%.4f",
        int(usable.sum()), float(dataset.loc[usable, LONG_TARGET_COL].mean()),
        float(dataset.loc[usable, SHORT_TARGET_COL].mean()),
        float((dataset.loc[usable, LONG_TARGET_COL].eq(1)
               & dataset.loc[usable, SHORT_TARGET_COL].eq(1)).mean()),
    )
    run_id = (
        f"shared-path-aware-{datetime.now(UTC):%Y%m%d%H%M%S}-"
        f"{oracle_batch_id[-6:]}"
    )
    output = artifacts_root / run_id
    metrics = train_path_aware(dataset, features, categoricals, training, output)
    contract = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E3_oracle_conditional_barrier_race_v1",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed", "research_only": True, "serving_ready": False,
        "target_contract": {
            "entry": "next_open_J_plus_1",
            "price_convention": "stock_bars_daily_split_adjusted",
            "long_and_short_replayed_independently": True,
            "positive_label": "side_net_return_after_costs_gt_0",
            "intrabar_resolution": "conservative_stop_first",
            "entry_day_exit": False,
            "entry_gap_filter_absolute": barrier.max_entry_gap_pct,
            "time_exit_sessions": barrier.max_sessions,
            "trailing": "disabled_to_isolate_direction",
            "production_parity": False,
            "production_parity_reason": (
                "barrier_race_v1 inclut une sortie H20 et omet le trailing risk-based PROD"
            ),
            "barrier": asdict(barrier),
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test", "pool_pct": training.pool_pct,
            "oracle_score_is_feature": False, "gate_path": str(gate_path),
        },
        "population": {
            **population, "target_rows": int(usable.sum()),
            "target_coverage": float(usable.mean()),
            "long_base_rate": float(dataset.loc[usable, LONG_TARGET_COL].mean()),
            "short_base_rate": float(dataset.loc[usable, SHORT_TARGET_COL].mean()),
            "both_profitable_rate": float(
                (dataset.loc[usable, LONG_TARGET_COL].eq(1)
                 & dataset.loc[usable, SHORT_TARGET_COL].eq(1)).mean()
            ),
        },
        "feature_profile": profile, "feature_columns": features,
        "categorical_columns": categoricals, "context_mode": training.context_mode,
        "walk_forward": {
            "min_train_dates": training.min_train_dates, "val_dates": training.val_dates,
            "test_dates": training.test_dates, "step_dates": training.step_dates,
            "max_splits": training.max_splits,
            "purge_sessions": barrier.max_sessions,
        },
        "primary_policy": {
            "name": PRIMARY_POLICY, "purpose": "diagnostic_only_raw_probabilities",
            "selection": "P(side)>=0.50 and probability_margin>=0.05",
        },
        "metrics": metrics,
    }
    (output / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output / "feature_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output, contract


def _format_summary(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    overall = metrics["overall"]
    stability = metrics["fold_stability"]
    return "\n".join([
        f"E3 path-aware terminé: {path}",
        f"Population labellisée: {contract['population']['target_rows']} lignes, "
        f"folds={metrics['n_folds']}",
        f"LONG AUC={overall['auc_long']:.4f} net top10="
        f"{overall['long_top_decile']['mean_net_return']:+.2%} "
        f"lift={overall['long_top_decile']['return_lift_vs_matched']:+.2%} "
        f"gates={stability['long']['all_gates_passed']}",
        f"SHORT AUC={overall['auc_short']:.4f} net top10="
        f"{overall['short_top_decile']['mean_net_return']:+.2%} "
        f"lift={overall['short_top_decile']['return_lift_vs_matched']:+.2%} "
        f"gates={stability['short']['all_gates_passed']}",
        "Serving désactivé: barrier_race_v1 est une expérience de direction, pas le lifecycle PROD.",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--stop-atr-mult", type=float, default=2.5)
    parser.add_argument("--tp-atr-mult", type=float, default=3.0)
    parser.add_argument("--tp-max-pct", type=float, default=0.07)
    parser.add_argument("--max-sessions", type=int, default=20)
    parser.add_argument("--max-entry-gap-pct", type=float, default=0.03)
    parser.add_argument("--spread-bps", type=float, default=5.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--borrow-fee-annual", type=float, default=0.003)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--context-mode", choices=["symbol_sector", "sector", "none"], default="none")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    barrier = BarrierRaceConfig(
        stop_atr_mult=args.stop_atr_mult, tp_atr_mult=args.tp_atr_mult,
        tp_max_pct=args.tp_max_pct, max_sessions=args.max_sessions,
        max_entry_gap_pct=args.max_entry_gap_pct, spread_bps=args.spread_bps,
        commission_bps=args.commission_bps, slippage_bps=args.slippage_bps,
        borrow_fee_annual=args.borrow_fee_annual,
    )
    training = SharedDirectionalConfig(
        horizon=args.max_sessions, min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size, test_dates=args.wf_test_size,
        step_dates=args.wf_step_size, max_splits=args.wf_max_splits,
        iterations=args.iterations, depth=args.depth,
        learning_rate=args.learning_rate, context_mode=args.context_mode,
        amplitude_weighting=False, objective="dual_classifier",
        target_mode="dual_threshold",
    )
    path, contract = run_path_aware_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit, training_config=training,
        barrier_config=barrier,
    )
    print(_format_summary(path, contract))


if __name__ == "__main__":
    main()
