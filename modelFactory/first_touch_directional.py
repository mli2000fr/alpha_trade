"""E4 research-only: direction Oracle par première barrière symétrique touchée.

Chaque événement du TOP20 Oracle OOF reçoit exactement une cible parmi
``UP_FIRST``, ``DOWN_FIRST``, ``AMBIGUOUS`` et ``NO_TOUCH``. Le modèle
multiclasse est mutualisé entre symboles. Une politique séparée ne prend une
direction que si UP ou DOWN domine et si leur marge est suffisante.

Cette expérience n'est reliée ni au serving, ni au backtest de production.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.labeling import _compute_atr
from modelFactory.oracle.train import get_universe_symbols, roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.path_aware_directional import (
    BarrierRaceConfig,
    LONG_NET_RETURN_COL,
    SHORT_NET_RETURN_COL,
    attach_path_targets,
    build_path_label_panel,
)
from modelFactory.shared_directional import (
    DEFAULT_ARTIFACTS_ROOT,
    DEFAULT_PROFILE,
    ORACLE_GATE_SCORE_COL,
    SharedDirectionalConfig,
    _prepare_X,
    _semester_label,
    build_shared_dataset,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

NO_TOUCH = 0
DOWN_FIRST = 1
UP_FIRST = 2
AMBIGUOUS = 3
CLASS_NAMES = {
    NO_TOUCH: "NO_TOUCH", DOWN_FIRST: "DOWN_FIRST",
    UP_FIRST: "UP_FIRST", AMBIGUOUS: "AMBIGUOUS",
}
TARGET_COL = "first_touch_target"
TARGET_NAME_COL = "first_touch_target_name"
TOUCH_SESSIONS_COL = "first_touch_sessions"
P_NO_TOUCH_COL = "p_no_touch"
P_DOWN_COL = "p_down_first"
P_UP_COL = "p_up_first"
P_AMBIGUOUS_COL = "p_ambiguous"
PREDICTED_CLASS_COL = "predicted_first_touch_class"
DECISION_COL = "first_touch_decision"
CHOSEN_RETURN_COL = "first_touch_chosen_net_return"
PRIMARY_MARGIN = 0.10
DIAGNOSTIC_MARGINS = (0.0, 0.05, PRIMARY_MARGIN, 0.15)


@dataclass(frozen=True, slots=True)
class FirstTouchConfig:
    barrier_atr_mult: float = 3.0
    barrier_max_pct: float = 0.07
    max_sessions: int = 20
    atr_window: int = 14
    min_atr: float = 0.001
    entry_delay_sessions: int = 1
    max_entry_gap_pct: float = 0.03
    primary_margin: float = PRIMARY_MARGIN
    catastrophic_loss_threshold: float = -0.20

    def __post_init__(self) -> None:
        if self.barrier_atr_mult <= 0 or self.barrier_max_pct <= 0:
            raise ValueError("Les distances de barrière E4 doivent être positives.")
        if self.max_sessions < 1 or self.atr_window < 2:
            raise ValueError("Horizon/fenêtre ATR E4 invalides.")
        if self.entry_delay_sessions < 1:
            raise ValueError("E4 exige une entrée différée d'au moins une séance.")
        if not 0 <= self.max_entry_gap_pct < 1:
            raise ValueError("max_entry_gap_pct doit être dans [0,1[.")
        if not 0 <= self.primary_margin < 1:
            raise ValueError("primary_margin doit être dans [0,1[.")
        if self.catastrophic_loss_threshold >= 0:
            raise ValueError("catastrophic_loss_threshold doit être négatif.")


def build_first_touch_panel(bars: pd.DataFrame, config: FirstTouchConfig) -> pd.DataFrame:
    """Labellise sans résoudre arbitrairement une double touche intraday."""
    required = {"date", "symbol", "open", "high", "low", "close"}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"Barres incomplètes pour E4: {missing}")
    outputs: list[pd.DataFrame] = []
    for symbol, raw in bars.groupby("symbol", sort=False):
        part = raw.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        if len(part) <= config.atr_window + config.entry_delay_sessions:
            continue
        opens = pd.to_numeric(part["open"], errors="coerce").to_numpy(float)
        highs = pd.to_numeric(part["high"], errors="coerce").to_numpy(float)
        lows = pd.to_numeric(part["low"], errors="coerce").to_numpy(float)
        closes = pd.to_numeric(part["close"], errors="coerce").to_numpy(float)
        atr = _compute_atr(highs, lows, closes, config.atr_window)
        rows: list[dict[str, Any]] = []
        for signal_idx in range(len(part)):
            entry_idx = signal_idx + config.entry_delay_sessions
            target: int | None = None
            touch_sessions: int | None = None
            distance_pct: float | None = None
            gap_abs: float | None = None
            eligible = False
            if entry_idx < len(part) and np.isfinite(closes[signal_idx]) and closes[signal_idx] > 0:
                entry = opens[entry_idx]
                atr_value = atr[signal_idx]
                gap_abs = abs(entry / closes[signal_idx] - 1.0) if np.isfinite(entry) else None
                eligible = bool(
                    np.isfinite(entry) and entry > 0 and np.isfinite(atr_value)
                    and (config.max_entry_gap_pct == 0 or gap_abs <= config.max_entry_gap_pct)
                )
                full_horizon_available = entry_idx + config.max_sessions < len(part)
                if eligible and full_horizon_available:
                    distance = min(
                        config.barrier_atr_mult * max(float(atr_value), config.min_atr * entry),
                        config.barrier_max_pct * entry,
                    )
                    distance_pct = distance / entry
                    upper, lower = entry + distance, entry - distance
                    target = NO_TOUCH
                    last_idx = entry_idx + config.max_sessions
                    # Comme E3, la séance d'entrée ne peut pas déclencher la sortie.
                    for bar_idx in range(entry_idx + 1, last_idx + 1):
                        if opens[bar_idx] >= upper:
                            target, touch_sessions = UP_FIRST, bar_idx - entry_idx
                            break
                        if opens[bar_idx] <= lower:
                            target, touch_sessions = DOWN_FIRST, bar_idx - entry_idx
                            break
                        up_hit = highs[bar_idx] >= upper
                        down_hit = lows[bar_idx] <= lower
                        if up_hit and down_hit:
                            target, touch_sessions = AMBIGUOUS, bar_idx - entry_idx
                            break
                        if up_hit:
                            target, touch_sessions = UP_FIRST, bar_idx - entry_idx
                            break
                        if down_hit:
                            target, touch_sessions = DOWN_FIRST, bar_idx - entry_idx
                            break
            rows.append({
                "date": pd.Timestamp(part.loc[signal_idx, "date"]).normalize(),
                "symbol": str(symbol).upper(), TARGET_COL: target,
                TARGET_NAME_COL: CLASS_NAMES.get(target), TOUCH_SESSIONS_COL: touch_sessions,
                "first_touch_barrier_distance_pct": distance_pct,
                "first_touch_entry_gap_abs": gap_abs,
                "first_touch_entry_gap_eligible": eligible,
            })
        outputs.append(pd.DataFrame(rows))
    if not outputs:
        return pd.DataFrame()
    panel = pd.concat(outputs, ignore_index=True)
    if panel.duplicated(["date", "symbol"]).any():
        raise ValueError("Labels E4 non uniques par date/symbole.")
    return panel


def attach_first_touch_targets(pool: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date", "symbol", TARGET_COL, TARGET_NAME_COL, TOUCH_SESSIONS_COL,
        "first_touch_barrier_distance_pct", "first_touch_entry_gap_abs",
        "first_touch_entry_gap_eligible",
    ]
    missing = sorted(set(columns).difference(panel.columns))
    if missing:
        raise ValueError(f"Panel E4 incomplet: {missing}")
    return pool.merge(panel[columns], on=["date", "symbol"], how="left", validate="one_to_one")


def _fit_multiclass(
    train: pd.DataFrame,
    valid: pd.DataFrame | None,
    features: list[str],
    categoricals: list[str],
    config: SharedDirectionalConfig,
    *,
    iterations: int | None = None,
) -> Any:
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=int(iterations or config.iterations), depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=5.0,
        random_seed=config.random_seed, random_strength=1.0,
        bootstrap_type="Bayesian", bagging_temperature=1.0,
        loss_function="MultiClass", eval_metric="MultiClass",
        auto_class_weights="Balanced", allow_writing_files=False,
        verbose=False, thread_count=-1,
    )
    train = train.sort_values(["date", "symbol"])
    kwargs: dict[str, Any] = {"cat_features": categoricals}
    if valid is not None and not valid.empty:
        kwargs.update({
            "eval_set": (_prepare_X(valid, features, categoricals), valid[TARGET_COL].astype(int)),
            "early_stopping_rounds": 60, "use_best_model": True,
        })
    model.fit(
        _prepare_X(train, features, categoricals), train[TARGET_COL].astype(int), **kwargs
    )
    return model


def _score_model(model: Any, frame: pd.DataFrame, features: list[str], categoricals: list[str]) -> pd.DataFrame:
    probabilities = model.predict_proba(_prepare_X(frame, features, categoricals))
    class_positions = {int(value): index for index, value in enumerate(model.classes_)}
    result = frame.copy()
    for class_id, column in (
        (NO_TOUCH, P_NO_TOUCH_COL), (DOWN_FIRST, P_DOWN_COL),
        (UP_FIRST, P_UP_COL), (AMBIGUOUS, P_AMBIGUOUS_COL),
    ):
        result[column] = probabilities[:, class_positions[class_id]]
    probability_columns = [P_NO_TOUCH_COL, P_DOWN_COL, P_UP_COL, P_AMBIGUOUS_COL]
    result[PREDICTED_CLASS_COL] = np.argmax(result[probability_columns].to_numpy(), axis=1)
    return result


def apply_first_touch_policy(frame: pd.DataFrame, margin: float) -> pd.DataFrame:
    if not 0 <= margin < 1:
        raise ValueError("La marge E4 doit être dans [0,1[.")
    result = frame.copy()
    winner = pd.to_numeric(result[PREDICTED_CLASS_COL], errors="coerce")
    directional_margin = (result[P_UP_COL] - result[P_DOWN_COL]).abs()
    long_mask = winner.eq(UP_FIRST) & directional_margin.ge(margin)
    short_mask = winner.eq(DOWN_FIRST) & directional_margin.ge(margin)
    result[DECISION_COL] = "ABSTAIN"
    result.loc[long_mask, DECISION_COL] = "LONG"
    result.loc[short_mask, DECISION_COL] = "SHORT"
    result[CHOSEN_RETURN_COL] = np.nan
    result.loc[long_mask, CHOSEN_RETURN_COL] = result.loc[long_mask, LONG_NET_RETURN_COL]
    result.loc[short_mask, CHOSEN_RETURN_COL] = result.loc[short_mask, SHORT_NET_RETURN_COL]
    return result


def _cvar(values: pd.Series, fraction: float = 0.05) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna().sort_values()
    if numeric.empty:
        return None
    return float(numeric.iloc[:max(1, math.ceil(len(numeric) * fraction))].mean())


def _concentration(selected: pd.DataFrame) -> float | None:
    if selected.empty:
        return None
    totals = selected.groupby("symbol")[CHOSEN_RETURN_COL].sum().sort_values(ascending=False)
    positive = float(totals.clip(lower=0).sum())
    return float(max(0.0, totals.iloc[0]) / positive) if positive > 0 else None


def _policy_metrics(frame: pd.DataFrame, margin: float, catastrophic: float) -> dict[str, Any]:
    policy = apply_first_touch_policy(frame, margin)
    selected = policy[policy[DECISION_COL].ne("ABSTAIN")].copy()
    if selected.empty:
        return {"rows": 0, "coverage": 0.0}
    chosen = pd.to_numeric(selected[CHOSEN_RETURN_COL], errors="coerce")
    long_ret = pd.to_numeric(selected[LONG_NET_RETURN_COL], errors="coerce")
    short_ret = pd.to_numeric(selected[SHORT_NET_RETURN_COL], errors="coerce")
    random_expected = (long_ret + short_ret) / 2.0
    best_static = max(float(long_ret.mean()), float(short_ret.mean()))
    directional_truth = selected[TARGET_COL].isin([UP_FIRST, DOWN_FIRST])
    correct = (
        (selected[DECISION_COL].eq("LONG") & selected[TARGET_COL].eq(UP_FIRST))
        | (selected[DECISION_COL].eq("SHORT") & selected[TARGET_COL].eq(DOWN_FIRST))
    )
    direction_base = max(
        float(selected[TARGET_COL].eq(UP_FIRST).mean()),
        float(selected[TARGET_COL].eq(DOWN_FIRST).mean()),
    )
    long_count = int(selected[DECISION_COL].eq("LONG").sum())
    short_count = int(selected[DECISION_COL].eq("SHORT").sum())
    return {
        "rows": int(len(selected)), "coverage": float(len(selected) / len(frame)),
        "dates": int(selected["date"].nunique()), "symbols": int(selected["symbol"].nunique()),
        "long_count": long_count, "short_count": short_count,
        "long_share": float(long_count / len(selected)),
        "short_share": float(short_count / len(selected)),
        "decision_precision": float(correct.mean()),
        "directional_truth_share": float(directional_truth.mean()),
        "direction_majority_baseline": direction_base,
        "precision_lift_vs_majority": float(correct.mean() - direction_base),
        "mean_net_return": float(chosen.mean()), "median_net_return": float(chosen.median()),
        "success_rate": float(chosen.gt(0).mean()),
        "chosen_side_better_rate": float(np.where(
            selected[DECISION_COL].eq("LONG"), long_ret.gt(short_ret), short_ret.gt(long_ret)
        ).mean()),
        "random_50_50_expected_return": float(random_expected.mean()),
        "best_static_side_return": best_static,
        "lift_vs_random_50_50": float(chosen.mean() - random_expected.mean()),
        "lift_vs_best_static_side": float(chosen.mean() - best_static),
        "catastrophic_loss_rate": float(chosen.le(catastrophic).mean()),
        "cvar_05": _cvar(chosen), "worst_return": float(chosen.min()),
        "top1_positive_contribution_share": _concentration(selected),
    }


def evaluate_first_touch_oos(
    frame: pd.DataFrame,
    config: FirstTouchConfig | None = None,
    margins: tuple[float, ...] = DIAGNOSTIC_MARGINS,
) -> dict[str, Any]:
    cfg = config or FirstTouchConfig()
    required = [
        "date", "symbol", TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL,
        P_NO_TOUCH_COL, P_DOWN_COL, P_UP_COL, P_AMBIGUOUS_COL, PREDICTED_CLASS_COL,
    ]
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Prédictions E4 incomplètes: {missing}")
    work = frame.dropna(subset=required).copy()
    if work.empty:
        return {"rows": 0, "policies": {}}
    truth = work[TARGET_COL].astype(int)
    prediction = work[PREDICTED_CLASS_COL].astype(int)
    recalls = []
    confusion: dict[str, dict[str, int]] = {}
    for actual in CLASS_NAMES:
        actual_mask = truth.eq(actual)
        recalls.append(float(prediction[actual_mask].eq(actual).mean()) if actual_mask.any() else np.nan)
        confusion[CLASS_NAMES[actual]] = {
            CLASS_NAMES[predicted]: int((actual_mask & prediction.eq(predicted)).sum())
            for predicted in CLASS_NAMES
        }
    f1_values = []
    for class_id in CLASS_NAMES:
        tp = int((truth.eq(class_id) & prediction.eq(class_id)).sum())
        fp = int((truth.ne(class_id) & prediction.eq(class_id)).sum())
        fn = int((truth.eq(class_id) & prediction.ne(class_id)).sum())
        denominator = 2 * tp + fp + fn
        f1_values.append(2 * tp / denominator if denominator else np.nan)
    directional = work[truth.isin([DOWN_FIRST, UP_FIRST])]
    directional_auc = None
    if not directional.empty and directional[TARGET_COL].nunique() == 2:
        denom = directional[P_UP_COL] + directional[P_DOWN_COL]
        score = directional[P_UP_COL] / denom.where(denom.gt(0), np.nan)
        directional_auc = roc_auc(directional[TARGET_COL].eq(UP_FIRST).astype(int), score)
    return {
        "rows": int(len(work)),
        "class_distribution": {CLASS_NAMES[key]: int(truth.eq(key).sum()) for key in CLASS_NAMES},
        "accuracy": float(truth.eq(prediction).mean()),
        "balanced_accuracy": float(np.nanmean(recalls)),
        "macro_f1": float(np.nanmean(f1_values)),
        "directional_auc_up_vs_down": directional_auc,
        "confusion_matrix": confusion,
        "policies": {
            f"{margin:.2f}": _policy_metrics(work, margin, cfg.catastrophic_loss_threshold)
            for margin in margins
        },
    }


def _stability(oof: pd.DataFrame, config: FirstTouchConfig) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    for fold_index, group in oof.groupby("fold_index", sort=True):
        evaluation = evaluate_first_touch_oos(group, config)
        folds.append({
            "fold_index": int(fold_index),
            "directional_auc_up_vs_down": evaluation["directional_auc_up_vs_down"],
            **evaluation["policies"][f"{config.primary_margin:.2f}"],
        })
    aucs = np.asarray([
        fold["directional_auc_up_vs_down"]
        for fold in folds if fold["directional_auc_up_vs_down"] is not None
    ], dtype=float)
    return {
        "folds": folds,
        "mean_directional_auc": float(np.mean(aucs)) if len(aucs) else None,
        "auc_above_half_folds": int(np.sum(aucs > 0.5)),
        "positive_lift_folds": int(sum(fold.get("lift_vs_random_50_50", -1) > 0 for fold in folds)),
        "positive_return_folds": int(sum(fold.get("mean_net_return", -1) > 0 for fold in folds)),
        "beats_best_static_folds": int(sum(fold.get("lift_vs_best_static_side", -1) > 0 for fold in folds)),
    }


def _gates(overall: dict[str, Any], stability: dict[str, Any], config: FirstTouchConfig) -> dict[str, Any]:
    primary = overall["policies"][f"{config.primary_margin:.2f}"]
    concentration = primary.get("top1_positive_contribution_share")
    values = {
        "mean_directional_auc_gte_0_53": bool(
            stability["mean_directional_auc"] is not None
            and stability["mean_directional_auc"] >= 0.53
        ),
        "auc_above_half_folds_gte_7": bool(stability["auc_above_half_folds"] >= 7),
        "coverage_gte_0_20": bool(primary.get("coverage", 0) >= 0.20),
        "decision_precision_gte_0_55": bool(primary.get("decision_precision", 0) >= 0.55),
        "precision_lift_vs_majority_gte_0_03": bool(
            primary.get("precision_lift_vs_majority", -1) >= 0.03
        ),
        "mean_net_return_positive": bool(primary.get("mean_net_return", -1) > 0),
        "lift_vs_random_gte_0_0025": bool(primary.get("lift_vs_random_50_50", -1) >= 0.0025),
        "positive_lift_folds_gte_7": bool(stability["positive_lift_folds"] >= 7),
        "positive_return_folds_gte_7": bool(stability["positive_return_folds"] >= 7),
        "beats_best_static_folds_gte_7": bool(stability["beats_best_static_folds"] >= 7),
        "top1_positive_contribution_lte_0_35": bool(
            concentration is not None and concentration <= 0.35
        ),
    }
    return {"values": values, "all_gates_passed": bool(all(values.values()))}


def train_first_touch(
    dataset: pd.DataFrame,
    features: list[str],
    categoricals: list[str],
    training: SharedDirectionalConfig,
    target_config: FirstTouchConfig,
    artifact_dir: Path,
) -> dict[str, Any]:
    folds = build_folds_adaptive(
        dataset, min_train_dates=training.min_train_dates, val_dates=training.val_dates,
        test_dates=training.test_dates, step_dates=training.step_dates,
        max_splits=training.max_splits, forecast_horizon=target_config.max_sessions,
    )
    if not folds:
        raise ValueError("Aucun fold Walk-Forward E4 valide.")
    oof_parts: list[pd.DataFrame] = []
    iterations: list[int] = []
    for fold_index, fold in enumerate(folds):
        train = fold["train"].dropna(subset=[TARGET_COL]).copy()
        valid = fold["val"].dropna(subset=[TARGET_COL]).copy()
        test = fold["test"].dropna(subset=[TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL]).copy()
        if train[TARGET_COL].nunique() != 4 or train.empty or valid.empty or test.empty:
            LOGGER.warning("E4 fold=%d ignoré: classes/partitions insuffisantes", fold_index)
            continue
        model = _fit_multiclass(train, valid, features, categoricals, training)
        scored = _score_model(model, test, features, categoricals)
        keep = [
            "date", "symbol", TARGET_COL, TARGET_NAME_COL, TOUCH_SESSIONS_COL,
            LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL, ORACLE_GATE_SCORE_COL,
            P_NO_TOUCH_COL, P_DOWN_COL, P_UP_COL, P_AMBIGUOUS_COL, PREDICTED_CLASS_COL,
        ]
        scored = scored[keep].copy()
        scored["fold_index"] = fold_index
        oof_parts.append(scored)
        best = int(model.get_best_iteration())
        iterations.append(max(10, best + 1 if best >= 0 else training.iterations))
        fold_eval = evaluate_first_touch_oos(scored, target_config)
        LOGGER.info(
            "E4 fold=%d macro_f1=%.4f dir_auc=%s coverage=%.1f%%",
            fold_index, fold_eval["macro_f1"], fold_eval["directional_auc_up_vs_down"],
            100 * fold_eval["policies"][f"{target_config.primary_margin:.2f}"]["coverage"],
        )
    if not oof_parts:
        raise ValueError("Tous les folds E4 ont été rejetés.")
    oof = pd.concat(oof_parts, ignore_index=True)
    overall = evaluate_first_touch_oos(oof, target_config)
    stability = _stability(oof, target_config)
    gates = _gates(overall, stability, target_config)
    labeled = dataset.dropna(subset=[TARGET_COL]).copy()
    final_iterations = max(10, int(np.median(iterations)))
    final_model = _fit_multiclass(
        labeled, None, features, categoricals, training, iterations=final_iterations
    )
    artifact_dir.mkdir(parents=True, exist_ok=False)
    model_path = artifact_dir / "first_touch_model.cbm"
    oof_path = artifact_dir / "oof_predictions.parquet"
    final_model.save_model(str(model_path))
    oof.to_parquet(oof_path, index=False)
    metrics = {
        "status": "completed", "research_only": True, "serving_ready": False,
        "model_role": "oracle_conditional_first_touch_multiclass",
        "n_folds": int(oof["fold_index"].nunique()),
        "final_iterations": final_iterations, "trained_rows": int(len(labeled)),
        "trained_symbols": int(labeled["symbol"].nunique()),
        "overall": overall, "fold_stability": stability, "gates": gates,
        "semesters": {
            str(label): evaluate_first_touch_oos(group, target_config)["policies"][
                f"{target_config.primary_margin:.2f}"
            ]
            for label, group in oof.groupby(oof["date"].map(_semester_label), sort=True)
        },
        "artifact_paths": {"model": str(model_path), "oof": str(oof_path)},
    }
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return metrics


def run_first_touch_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    profile_path: Path = DEFAULT_PROFILE,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    training_config: SharedDirectionalConfig | None = None,
    target_config: FirstTouchConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    target = target_config or FirstTouchConfig()
    training = training_config or SharedDirectionalConfig(context_mode="none", amplitude_weighting=False)
    profile = load_profile(profile_path)
    symbols = get_universe_symbols(engine, oracle_batch_id, target.max_sessions)
    if symbols_limit:
        symbols = symbols[:symbols_limit]
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    dataset_config = replace(
        training, horizon=target.max_sessions, objective="classifier",
        target_mode="decile_direction", amplitude_weighting=False,
    )
    pool, features, categoricals, population = build_shared_dataset(
        engine, oracle_batch_id, symbols, start_date=start_date, end_date=end_date,
        gate_path=gate_path, profile=profile, config=dataset_config,
    )
    requested_start, requested_end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    pool = pool[pd.to_datetime(pool["date"]).between(requested_start, requested_end)].copy()
    if pool.empty:
        raise ValueError("Pool Oracle E4 vide dans la période demandée.")
    warmup_start = (requested_start - pd.offsets.BDay(target.atr_window + 5)).date()
    future_end = (requested_end + pd.offsets.BDay(target.max_sessions + 2)).date()
    bars = load_universe_bars(engine, symbols, start_date=warmup_start, end_date=future_end)
    touch_panel = build_first_touch_panel(bars, target)
    dataset = attach_first_touch_targets(pool, touch_panel)
    # Rendements économiques seulement : même replay indépendant que E3, jamais une feature/cible E4.
    race = BarrierRaceConfig(max_sessions=target.max_sessions, max_entry_gap_pct=target.max_entry_gap_pct)
    dataset = attach_path_targets(dataset, build_path_label_panel(bars, race))
    usable = dataset[[TARGET_COL, LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL]].notna().all(axis=1)
    if int(usable.sum()) < 100:
        raise ValueError(f"Cibles E4 insuffisantes: {int(usable.sum())} lignes.")
    run_id = f"shared-first-touch-{datetime.now(UTC):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    output = artifacts_root / run_id
    metrics = train_first_touch(dataset, features, categoricals, training, target, output)
    class_counts = dataset.loc[usable, TARGET_NAME_COL].value_counts().to_dict()
    contract = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E4_oracle_conditional_first_touch_multiclass_v1",
        "source_oracle_batch_id": oracle_batch_id,
        "status": "completed", "research_only": True, "serving_ready": False,
        "target_contract": {
            "classes": CLASS_NAMES, "entry": "next_open_J_plus_1",
            "atr_information_cutoff": "signal_close_J",
            "symmetric_barriers": True, "same_daily_bar_double_touch": "AMBIGUOUS",
            "no_touch_at_horizon": "NO_TOUCH", "entry_day_exit": False,
            "configuration": asdict(target),
        },
        "conditioning": {
            "source": "oracle_walk_forward_oof_test", "pool_pct": training.pool_pct,
            "oracle_score_is_feature": False, "gate_path": str(gate_path),
        },
        "economic_evaluation": {
            "source": "E3 barrier_race_v1 independent LONG/SHORT replay",
            "target_leakage": False, "production_lifecycle": False,
        },
        "population": {
            **population, "requested_start": str(requested_start.date()),
            "requested_end": str(requested_end.date()),
            "actual_start": str(pd.Timestamp(pool["date"].min()).date()),
            "actual_end": str(pd.Timestamp(pool["date"].max()).date()),
            "target_rows": int(usable.sum()), "target_coverage": float(usable.mean()),
            "class_counts": class_counts,
        },
        "feature_profile": profile, "feature_columns": features,
        "categorical_columns": categoricals,
        "walk_forward": {
            "min_train_dates": training.min_train_dates, "val_dates": training.val_dates,
            "test_dates": training.test_dates, "step_dates": training.step_dates,
            "max_splits": training.max_splits, "purge_sessions": target.max_sessions,
        },
        "policy": {
            "primary_margin": target.primary_margin,
            "abstain_if_predicted_class": ["AMBIGUOUS", "NO_TOUCH"],
            "threshold_optimization": False,
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


def _summary(path: Path, contract: dict[str, Any]) -> str:
    metrics = contract["metrics"]
    overall = metrics["overall"]
    primary = overall["policies"][f"{contract['policy']['primary_margin']:.2f}"]
    return "\n".join([
        f"E4 first-touch terminé: {path}",
        f"Population={contract['population']['target_rows']} folds={metrics['n_folds']} ",
        f"macro_F1={overall['macro_f1']:.4f} dir_AUC={overall['directional_auc_up_vs_down']}",
        f"Politique: coverage={primary.get('coverage', 0.0):.1%} "
        f"precision={primary.get('decision_precision', float('nan')):.1%} ",
        f"net={primary.get('mean_net_return', float('nan')):+.2%} "
        f"lift_random={primary.get('lift_vs_random_50_50', float('nan')):+.2%}",
        f"Gates={metrics['gates']['all_gates_passed']}",
        "Serving désactivé: expérience OOF uniquement.",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--feature-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--barrier-atr-mult", type=float, default=3.0)
    parser.add_argument("--barrier-max-pct", type=float, default=0.07)
    parser.add_argument("--max-sessions", type=int, default=20)
    parser.add_argument("--max-entry-gap-pct", type=float, default=0.03)
    parser.add_argument("--primary-margin", type=float, default=PRIMARY_MARGIN)
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
    target = FirstTouchConfig(
        barrier_atr_mult=args.barrier_atr_mult, barrier_max_pct=args.barrier_max_pct,
        max_sessions=args.max_sessions, max_entry_gap_pct=args.max_entry_gap_pct,
        primary_margin=args.primary_margin,
    )
    training = SharedDirectionalConfig(
        horizon=args.max_sessions, min_train_dates=args.wf_min_train_size,
        val_dates=args.wf_val_size, test_dates=args.wf_test_size,
        step_dates=args.wf_step_size, max_splits=args.wf_max_splits,
        iterations=args.iterations, depth=args.depth, learning_rate=args.learning_rate,
        context_mode=args.context_mode, amplitude_weighting=False,
    )
    path, contract = run_first_touch_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        profile_path=args.feature_profile, artifacts_root=args.artifacts_root,
        symbols_limit=args.symbols_limit, training_config=training, target_config=target,
    )
    print(_summary(path, contract))


if __name__ == "__main__":
    main()
