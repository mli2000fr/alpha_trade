"""E13: veto pré-entrée OOF après Oracle, avant portefeuille et lifecycle.

Research-only : ce module ne modifie ni le serving, ni les prédictions
persistées, ni le backtest applicatif. Le modèle apprend uniquement sur des
trades dont la sortie H20 précède le début du fold évalué (purge temporelle).
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import block_bootstrap_mean
from modelFactory.oracle_monetization_bridge import (
    E12Config,
    build_fixed_h20_events,
    filter_by_membership,
    load_exact_tradable_membership,
    replay_lifecycle_on_selected,
)
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)

RAW_FEATURES = (
    "directional_oracle_proba_extreme",
    "directional_oracle_extreme_pct",
    "signal_ret_1",
    "signal_ret_5",
    "signal_ret_20",
    "signal_volatility_20",
    "signal_atr_pct",
    "signal_drawdown_20",
    "signal_range_position_20",
    "signal_volume_ratio_20",
    "log_adv20",
    "log_signal_price",
    "entry_gap_signed",
    "entry_gap_pct",
)
RANK_FEATURES = tuple(f"{name}_xs_rank" for name in RAW_FEATURES)
MODEL_FEATURES = RAW_FEATURES + RANK_FEATURES


@dataclass(frozen=True, slots=True)
class E13Config:
    max_positions: int = 8
    primary_veto_fraction: float = 0.20
    diagnostic_veto_fractions: tuple[float, ...] = (0.10, 0.20, 0.30)
    min_train_rows: int = 2_000
    iterations: int = 300
    depth: int = 5
    learning_rate: float = 0.03
    random_seed: int = 20260913
    bootstrap_samples: int = 2_000

    def __post_init__(self) -> None:
        if not 0 < self.primary_veto_fraction < 0.5:
            raise ValueError("primary_veto_fraction doit être dans ]0, 0.5[.")
        if self.max_positions < 1 or self.min_train_rows < 100:
            raise ValueError("Capacité ou train minimum invalide.")


def add_pre_entry_features(events: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """Ajoute seulement des variables disponibles au plus tard à l'open J+1."""
    frame = prepare_bars(bars)
    grouped = frame.groupby("symbol", sort=False)
    frame["signal_ret_1"] = grouped["px_close"].pct_change(1, fill_method=None)
    frame["signal_ret_5"] = grouped["px_close"].pct_change(5, fill_method=None)
    frame["signal_ret_20"] = grouped["px_close"].pct_change(20, fill_method=None)
    frame["signal_volatility_20"] = frame["signal_ret_1"].groupby(
        frame["symbol"]
    ).transform(lambda values: values.rolling(20, min_periods=20).std())
    frame["signal_atr_pct"] = frame["atr20"] / frame["px_close"]
    rolling_high = grouped["px_high"].transform(
        lambda values: values.rolling(20, min_periods=20).max()
    )
    rolling_low = grouped["px_low"].transform(
        lambda values: values.rolling(20, min_periods=20).min()
    )
    frame["signal_drawdown_20"] = frame["px_close"] / rolling_high - 1.0
    span = (rolling_high - rolling_low).replace(0, np.nan)
    frame["signal_range_position_20"] = (frame["px_close"] - rolling_low) / span
    median_volume = grouped["volume"].transform(
        lambda values: values.rolling(20, min_periods=20).median()
    )
    frame["signal_volume_ratio_20"] = pd.to_numeric(
        frame["volume"], errors="coerce"
    ) / median_volume.replace(0, np.nan)
    feature_columns = [
        "date", "symbol", "signal_ret_1", "signal_ret_5", "signal_ret_20",
        "signal_volatility_20", "signal_atr_pct", "signal_drawdown_20",
        "signal_range_position_20", "signal_volume_ratio_20",
    ]
    result = events.merge(
        frame[feature_columns], on=["date", "symbol"], how="left",
        validate="many_to_one",
    )
    result["entry_gap_signed"] = (
        result["entry_open"] / result["entry_previous_close"] - 1.0
    )
    result["log_adv20"] = np.log1p(pd.to_numeric(result["adv20"], errors="coerce"))
    result["log_signal_price"] = np.log1p(
        pd.to_numeric(result["px_close"], errors="coerce").clip(lower=0)
    )
    for feature in RAW_FEATURES:
        result[f"{feature}_xs_rank"] = result.groupby("date")[feature].rank(
            method="average", pct=True
        )
    return result


def build_outcome_panel(
    events: pd.DataFrame, prepared_bars: pd.DataFrame, lifecycle: E12Config
) -> tuple[pd.DataFrame, pd.DataFrame]:
    outcomes, rejected = replay_lifecycle_on_selected(events, prepared_bars, lifecycle)
    identity = ["date", "symbol"]
    outcome_columns = [
        *identity, "exit_date", "exit_reason", "holding_sessions", "net_return",
        "gross_return", "fixed_h20_net_return",
    ]
    panel = events.merge(
        outcomes[outcome_columns], on=identity, how="inner", validate="one_to_one",
        suffixes=("", "_lifecycle"),
    )
    if "fixed_h20_net_return_lifecycle" in panel:
        panel = panel.drop(columns=["fixed_h20_net_return_lifecycle"])
    panel["bad_trailing"] = panel["exit_reason"].eq("trailing_stop").astype(int)
    panel["loss"] = panel["net_return_lifecycle"].lt(0).astype(int)
    return panel, rejected


def fit_oof_risk(panel: pd.DataFrame, config: E13Config) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Prédit le trailing stop avec folds Oracle et purge par date de sortie."""
    scored: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    fold_dates = sorted(pd.to_datetime(panel["fold"], errors="coerce").dropna().unique())
    for fold_index, fold_value in enumerate(fold_dates):
        fold_start = pd.Timestamp(fold_value).normalize()
        test = panel[pd.to_datetime(panel["fold"]).eq(fold_start)].copy()
        train = panel[pd.to_datetime(panel["exit_date"]).lt(fold_start)].copy()
        if len(train) < config.min_train_rows or train["bad_trailing"].nunique() < 2:
            diagnostics.append({
                "fold": str(fold_start.date()), "status": "skipped",
                "train_rows": int(len(train)), "test_rows": int(len(test)),
            })
            continue
        medians = train[list(MODEL_FEATURES)].median(numeric_only=True).fillna(0.0)
        x_train = train[list(MODEL_FEATURES)].replace([np.inf, -np.inf], np.nan).fillna(medians)
        x_test = test[list(MODEL_FEATURES)].replace([np.inf, -np.inf], np.nan).fillna(medians)
        positives = int(train["bad_trailing"].sum())
        negatives = int(len(train) - positives)
        positive_weight = negatives / positives if positives else 1.0
        model = CatBoostClassifier(
            iterations=config.iterations, depth=config.depth,
            learning_rate=config.learning_rate, loss_function="Logloss",
            eval_metric="AUC", verbose=False,
            random_seed=config.random_seed + fold_index,
            class_weights=[1.0, positive_weight], allow_writing_files=False,
            thread_count=4,
        )
        model.fit(x_train, train["bad_trailing"])
        train_risk = model.predict_proba(x_train)[:, 1]
        test["pre_entry_trailing_risk"] = model.predict_proba(x_test)[:, 1]
        thresholds: dict[str, float] = {}
        for fraction in config.diagnostic_veto_fractions:
            threshold = float(np.quantile(train_risk, 1.0 - fraction))
            thresholds[f"{fraction:.2f}"] = threshold
            test[f"keep_absolute_{fraction:.2f}"] = test[
                "pre_entry_trailing_risk"
            ].le(threshold)
        scored.append(test)
        diagnostics.append({
            "fold": str(fold_start.date()), "status": "scored",
            "train_rows": int(len(train)), "test_rows": int(len(test)),
            "train_trailing_rate": float(train["bad_trailing"].mean()),
            "test_trailing_rate": float(test["bad_trailing"].mean()),
            "train_risk_thresholds": thresholds,
            "test_veto_rates": {
                f"{fraction:.2f}": float(
                    1.0 - test[f"keep_absolute_{fraction:.2f}"].mean()
                )
                for fraction in config.diagnostic_veto_fractions
            },
            "feature_importance": dict(
                zip(MODEL_FEATURES, model.get_feature_importance(), strict=True)
            ),
        })
    if not scored:
        raise RuntimeError("Aucun fold E13 évaluable après purge.")
    return pd.concat(scored, ignore_index=True), diagnostics


def add_daily_vetoes(panel: pd.DataFrame, fractions: tuple[float, ...]) -> pd.DataFrame:
    result = panel.copy()
    risk_rank = result.groupby("date")["pre_entry_trailing_risk"].rank(
        method="first", pct=True, ascending=True
    )
    for fraction in fractions:
        result[f"keep_{fraction:.2f}"] = risk_rank.le(1.0 - fraction)
    return result


def schedule_dynamic_capacity(
    panel: pd.DataFrame, *, max_positions: int, keep_column: str | None = None
) -> pd.DataFrame:
    active: dict[str, pd.Timestamp] = {}
    selected: list[int] = []
    for _, group in panel.groupby("date", sort=True):
        entry_date = pd.Timestamp(group["entry_date"].min())
        active = {symbol: end for symbol, end in active.items() if end >= entry_date}
        slots = max_positions - len(active)
        if slots <= 0:
            continue
        candidates = group[~group["symbol"].isin(active)]
        if keep_column is not None:
            candidates = candidates[candidates[keep_column].fillna(False)]
        candidates = candidates.sort_values(
            ["directional_oracle_proba_extreme", "symbol"], ascending=[False, True]
        )
        for row in candidates.head(slots).itertuples():
            selected.append(int(row.Index))
            active[str(row.symbol)] = pd.Timestamp(row.exit_date)
    return panel.loc[selected].sort_values(["entry_date", "symbol"]).reset_index(drop=True)


def _summary(frame: pd.DataFrame, config: E13Config) -> dict[str, Any]:
    if frame.empty:
        return {"trades": 0}
    daily = frame.groupby("date")["net_return_lifecycle"].mean().sort_index()
    boot_config = E12Config(bootstrap_samples=config.bootstrap_samples).bootstrap_config()
    ci = block_bootstrap_mean(daily, boot_config)
    return {
        "trades": int(len(frame)), "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "mean_net_return": float(frame["net_return_lifecycle"].mean()),
        "median_net_return": float(frame["net_return_lifecycle"].median()),
        "win_rate": float(frame["net_return_lifecycle"].gt(0).mean()),
        "trailing_rate": float(frame["bad_trailing"].mean()),
        "q05": float(frame["net_return_lifecycle"].quantile(0.05)),
        "daily_mean": float(daily.mean()), "daily_ci95_low": ci[0],
        "daily_ci95_high": ci[1],
    }


def _paired_daily_delta(
    baseline: pd.DataFrame, candidate: pd.DataFrame, config: E13Config
) -> dict[str, float]:
    left = baseline.groupby("date")["net_return_lifecycle"].mean()
    right = candidate.groupby("date")["net_return_lifecycle"].mean()
    index = left.index.union(right.index)
    delta = right.reindex(index, fill_value=0.0) - left.reindex(index, fill_value=0.0)
    ci = block_bootstrap_mean(
        delta.sort_index(), E12Config(bootstrap_samples=config.bootstrap_samples).bootstrap_config()
    )
    return {"daily_delta": float(delta.mean()), "ci95_low": ci[0], "ci95_high": ci[1]}


def _semester_stability(baseline: pd.DataFrame, candidate: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    semesters = sorted(set(baseline["semester"]) | set(candidate["semester"]))
    for semester in semesters:
        before = baseline[baseline["semester"].eq(semester)]["net_return_lifecycle"]
        after = candidate[candidate["semester"].eq(semester)]["net_return_lifecycle"]
        rows.append({
            "semester": semester, "baseline_trades": int(len(before)),
            "candidate_trades": int(len(after)),
            "baseline_mean": float(before.mean()) if len(before) else None,
            "candidate_mean": float(after.mean()) if len(after) else None,
            "lift": float(after.mean() - before.mean()) if len(before) and len(after) else None,
        })
    return rows


def _feature_diagnostics(panel: pd.DataFrame) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for feature in RAW_FEATURES:
        values = pd.to_numeric(panel[feature], errors="coerce")
        valid = values.notna()
        if valid.sum() < 100:
            continue
        ranks = values[valid].rank(method="average", pct=True)
        low = panel.loc[ranks[ranks.le(0.1)].index]
        high = panel.loc[ranks[ranks.gt(0.9)].index]
        diagnostics[feature] = {
            "coverage": float(valid.mean()),
            "low_decile_trailing_rate": float(low["bad_trailing"].mean()),
            "high_decile_trailing_rate": float(high["bad_trailing"].mean()),
            "low_decile_mean_net": float(low["net_return_lifecycle"].mean()),
            "high_decile_mean_net": float(high["net_return_lifecycle"].mean()),
        }
    return diagnostics


def _binary_auc(labels: pd.Series, scores: pd.Series) -> float:
    valid = labels.notna() & scores.notna()
    y = labels[valid].astype(int)
    rank = scores[valid].rank(method="average")
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    rank_sum = float(rank[y.eq(1)].sum())
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _risk_model_diagnostics(panel: pd.DataFrame) -> dict[str, Any]:
    decile = pd.qcut(
        panel["pre_entry_trailing_risk"], 10, labels=False, duplicates="drop"
    )
    rows = []
    for value, group in panel.groupby(decile, observed=True):
        rows.append({
            "decile": int(value), "events": int(len(group)),
            "trailing_rate": float(group["bad_trailing"].mean()),
            "mean_net_return": float(group["net_return_lifecycle"].mean()),
        })
    return {
        "auc_oof": _binary_auc(
            panel["bad_trailing"], panel["pre_entry_trailing_risk"]
        ),
        "auc_by_fold": {
            str(fold): _binary_auc(group["bad_trailing"], group["pre_entry_trailing_risk"])
            for fold, group in panel.groupby("fold", sort=True)
        },
        "risk_deciles": rows,
    }


def run(*, oracle_gate_path: Path, output_root: Path, config: E13Config) -> Path:
    lifecycle_config = E12Config(bootstrap_samples=config.bootstrap_samples)
    oracle = pd.read_parquet(oracle_gate_path)
    eligible = oracle[
        oracle["directional_oracle_eligible"].fillna(False)
        & oracle["directional_oracle_oof_available"].fillna(False)
    ]
    symbols = sorted(eligible["symbol"].astype(str).str.upper().unique())
    start = pd.Timestamp(eligible["date"].min()) - pd.offsets.BDay(40)
    end = pd.Timestamp(eligible["date"].max()) + pd.offsets.BDay(25)
    engine = get_sqlalchemy_engine()
    bars = load_universe_bars(engine, symbols, start_date=start.date(), end_date=end.date())
    events = build_fixed_h20_events(oracle, bars, lifecycle_config)
    from modelFactory.oracle_monetization_bridge import deduplicate_non_overlapping
    events = deduplicate_non_overlapping(events)
    events = add_pre_entry_features(events, bars)
    panel, rejected = build_outcome_panel(events, prepare_bars(bars), lifecycle_config)
    panel = panel[~panel["gap_rejected"]].copy()
    scored, fold_diagnostics = fit_oof_risk(panel, config)
    scored = add_daily_vetoes(scored, config.diagnostic_veto_fractions)

    baseline = schedule_dynamic_capacity(scored, max_positions=config.max_positions)
    policies: dict[str, Any] = {"baseline": _summary(baseline, config)}
    selected_frames: dict[str, pd.DataFrame] = {"baseline": baseline}
    for fraction in config.diagnostic_veto_fractions:
        daily_key = f"daily_veto_{fraction:.2f}"
        daily_chosen = schedule_dynamic_capacity(
            scored, max_positions=config.max_positions, keep_column=f"keep_{fraction:.2f}"
        )
        selected_frames[daily_key] = daily_chosen
        policies[daily_key] = {
            **_summary(daily_chosen, config),
            "comparison": _paired_daily_delta(baseline, daily_chosen, config),
            "semester_stability": _semester_stability(baseline, daily_chosen),
        }
        absolute_key = f"absolute_oof_veto_{fraction:.2f}"
        absolute_chosen = schedule_dynamic_capacity(
            scored, max_positions=config.max_positions,
            keep_column=f"keep_absolute_{fraction:.2f}",
        )
        selected_frames[absolute_key] = absolute_chosen
        policies[absolute_key] = {
            **_summary(absolute_chosen, config),
            "comparison": _paired_daily_delta(baseline, absolute_chosen, config),
            "semester_stability": _semester_stability(baseline, absolute_chosen),
        }

    full_members, full_diag = load_exact_tradable_membership(
        engine, start_date=scored["date"].min(), end_date=scored["date"].max(),
        preset=lifecycle_config.capital_preset_key, quality="full",
    )
    degraded_members, degraded_diag = load_exact_tradable_membership(
        engine, start_date=scored["date"].min(), end_date=scored["date"].max(),
        preset=lifecycle_config.capital_preset_key, quality="any",
    )
    degraded = filter_by_membership(scored, degraded_members)
    degraded_baseline = schedule_dynamic_capacity(
        degraded, max_positions=config.max_positions
    ) if len(degraded) else degraded
    primary_key = f"absolute_oof_veto_{config.primary_veto_fraction:.2f}"
    degraded_primary = schedule_dynamic_capacity(
        degraded, max_positions=config.max_positions,
        keep_column=f"keep_absolute_{config.primary_veto_fraction:.2f}",
    ) if len(degraded) else degraded
    primary = selected_frames[primary_key]
    comparison = policies[primary_key]["comparison"]
    stability = policies[primary_key]["semester_stability"]
    comparable_semesters = [row for row in stability if row["lift"] is not None]
    positive_semesters = sum(row["lift"] > 0 for row in comparable_semesters)
    gates = {
        "coverage_at_least_70pct": len(primary) / len(baseline) >= 0.70,
        "daily_lift_positive": comparison["daily_delta"] > 0,
        "daily_lift_ci95_above_zero": comparison["ci95_low"] > 0,
        "trailing_rate_reduction_20pct": (
            policies[primary_key]["trailing_rate"]
            <= policies["baseline"]["trailing_rate"] * 0.80
        ),
        "q05_not_worse": policies[primary_key]["q05"] >= policies["baseline"]["q05"],
        "positive_lift_semesters_70pct": (
            bool(comparable_semesters)
            and positive_semesters / len(comparable_semesters) >= 0.70
        ),
        "strict_tradable_pit_available": full_diag["dates"] == scored["date"].nunique(),
    }
    gates["promotion_authorized"] = all(gates.values())
    verdict = "GO_EXACT_BACKTEST" if gates["promotion_authorized"] else "NO_GO_OR_BLOCKED"

    run_id = f"oracle-pre-entry-veto-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    scored.to_parquet(output / "oof_pre_entry_risk.parquet", index=False)
    for key, frame in selected_frames.items():
        frame.to_csv(output / f"portfolio_{key}.csv", index=False)
    rejected.to_csv(output / "entry_rejections.csv", index=False)
    report = {
        "schema_version": 2, "experiment": "E13_ORACLE_PRE_ENTRY_VETO",
        "status": "complete", "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "input": str(oracle_gate_path), "config": asdict(config),
        "contract": {
            "target": "future PROD trailing_stop",
            "features": list(MODEL_FEATURES),
            "timing": "close J plus gap observable at open J+1",
            "purge": "train exit_date strictly before evaluated Oracle fold start",
            "selection": "Oracle score priority, max 8, refill after actual exit",
            "primary_veto": config.primary_veto_fraction,
            "primary_veto_rule": "fold-train risk quantile, applied unchanged to test fold",
            "diagnostic_vetoes": list(config.diagnostic_veto_fractions),
        },
        "population": {
            "deduplicated_events": int(len(events)),
            "lifecycle_outcomes_after_gap": int(len(panel)),
            "oof_scored": int(len(scored)),
            "entry_rejections": int(len(rejected)),
        },
        "folds": fold_diagnostics,
        "risk_model": _risk_model_diagnostics(scored),
        "feature_diagnostics": _feature_diagnostics(scored),
        "policies": policies,
        "tradable_pit": {
            "full": full_diag, "degraded": degraded_diag,
            "degraded_baseline": _summary(degraded_baseline, config),
            "degraded_primary_veto": _summary(degraded_primary, config),
        },
        "gates": gates, "verdict": verdict,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E13 terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-gate", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_pre_entry_veto"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_gate_path=args.oracle_gate, output_root=args.output_root,
        config=E13Config(
            bootstrap_samples=args.bootstrap_samples, iterations=args.iterations
        ),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E13 terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
