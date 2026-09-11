"""E14: cible économique pré-entrée OOF après Oracle.

Deux têtes mutualisées sont comparées : rendement net PROD attendu et
probabilité de perte nette. Toute normalisation, winsorisation et tout seuil de
veto sont appris exclusivement sur le train purgé du fold courant.
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
from catboost import CatBoostClassifier, CatBoostRegressor

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.oracle_monetization_bridge import (
    E12Config,
    build_fixed_h20_events,
    deduplicate_non_overlapping,
    filter_by_membership,
    load_exact_tradable_membership,
)
from modelFactory.oracle_pre_entry_veto import (
    MODEL_FEATURES,
    _paired_daily_delta,
    _semester_stability,
    _summary,
    add_pre_entry_features,
    build_outcome_panel,
)
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class E14Config:
    max_positions: int = 8
    primary_veto_fraction: float = 0.20
    diagnostic_veto_fractions: tuple[float, ...] = (0.10, 0.20, 0.30)
    min_train_rows: int = 2_000
    iterations: int = 300
    depth: int = 5
    learning_rate: float = 0.03
    random_seed: int = 20260914
    bootstrap_samples: int = 2_000

    def __post_init__(self) -> None:
        if not 0 < self.primary_veto_fraction < 0.5:
            raise ValueError("primary_veto_fraction doit être dans ]0, 0.5[.")
        if self.min_train_rows < 100 or self.max_positions < 1:
            raise ValueError("Train minimum ou capacité invalide.")


def fit_oof_economic_heads(
    panel: pd.DataFrame, config: E14Config
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Produit les prédictions OOF avec purge stricte des labels H20."""
    outputs: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    fold_dates = sorted(pd.to_datetime(panel["fold"], errors="coerce").dropna().unique())
    for fold_index, fold_value in enumerate(fold_dates):
        fold_start = pd.Timestamp(fold_value).normalize()
        test = panel[pd.to_datetime(panel["fold"]).eq(fold_start)].copy()
        train = panel[pd.to_datetime(panel["exit_date"]).lt(fold_start)].copy()
        if len(train) < config.min_train_rows or train["loss"].nunique() < 2:
            diagnostics.append({
                "fold": str(fold_start.date()), "status": "skipped",
                "train_rows": int(len(train)), "test_rows": int(len(test)),
            })
            continue
        medians = train[list(MODEL_FEATURES)].median(numeric_only=True).fillna(0.0)
        x_train = train[list(MODEL_FEATURES)].replace([np.inf, -np.inf], np.nan).fillna(medians)
        x_test = test[list(MODEL_FEATURES)].replace([np.inf, -np.inf], np.nan).fillna(medians)
        train_net = train["net_return_lifecycle"].astype(float)
        lower, upper = (float(value) for value in train_net.quantile([0.01, 0.99]))
        utility_target = train_net.clip(lower=lower, upper=upper)

        regressor = CatBoostRegressor(
            iterations=config.iterations, depth=config.depth,
            learning_rate=config.learning_rate, loss_function="RMSE",
            verbose=False, random_seed=config.random_seed + fold_index,
            allow_writing_files=False, thread_count=4,
        )
        regressor.fit(x_train, utility_target)
        train_utility = regressor.predict(x_train)
        test["predicted_net_utility"] = regressor.predict(x_test)

        positives = int(train["loss"].sum())
        negatives = int(len(train) - positives)
        loss_weight = negatives / positives if positives else 1.0
        classifier = CatBoostClassifier(
            iterations=config.iterations, depth=config.depth,
            learning_rate=config.learning_rate, loss_function="Logloss",
            eval_metric="AUC", verbose=False,
            random_seed=config.random_seed + 100 + fold_index,
            class_weights=[1.0, loss_weight], allow_writing_files=False,
            thread_count=4,
        )
        classifier.fit(x_train, train["loss"])
        train_loss_risk = classifier.predict_proba(x_train)[:, 1]
        test["predicted_loss_probability"] = classifier.predict_proba(x_test)[:, 1]

        utility_thresholds: dict[str, float] = {}
        loss_thresholds: dict[str, float] = {}
        for fraction in config.diagnostic_veto_fractions:
            utility_threshold = float(np.quantile(train_utility, fraction))
            loss_threshold = float(np.quantile(train_loss_risk, 1.0 - fraction))
            utility_thresholds[f"{fraction:.2f}"] = utility_threshold
            loss_thresholds[f"{fraction:.2f}"] = loss_threshold
            test[f"keep_utility_{fraction:.2f}"] = test[
                "predicted_net_utility"
            ].ge(utility_threshold)
            test[f"keep_loss_{fraction:.2f}"] = test[
                "predicted_loss_probability"
            ].le(loss_threshold)

        outputs.append(test)
        diagnostics.append({
            "fold": str(fold_start.date()),
            "status": "scored", "train_rows": int(len(train)),
            "test_rows": int(len(test)), "winsor_lower": lower,
            "winsor_upper": upper, "utility_thresholds": utility_thresholds,
            "loss_thresholds": loss_thresholds,
            "test_utility_veto_rates": {
                f"{fraction:.2f}": float(
                    1.0 - test[f"keep_utility_{fraction:.2f}"].mean()
                ) for fraction in config.diagnostic_veto_fractions
            },
            "test_loss_veto_rates": {
                f"{fraction:.2f}": float(
                    1.0 - test[f"keep_loss_{fraction:.2f}"].mean()
                ) for fraction in config.diagnostic_veto_fractions
            },
            "utility_feature_importance": dict(
                zip(MODEL_FEATURES, regressor.get_feature_importance(), strict=True)
            ),
            "loss_feature_importance": dict(
                zip(MODEL_FEATURES, classifier.get_feature_importance(), strict=True)
            ),
        })
    if not outputs:
        raise RuntimeError("Aucun fold E14 évaluable après purge.")
    return pd.concat(outputs, ignore_index=True), diagnostics


def add_priority_scores(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    oracle_rank = result.groupby("date")["directional_oracle_proba_extreme"].rank(
        method="average", pct=True
    )
    utility_rank = result.groupby("date")["predicted_net_utility"].rank(
        method="average", pct=True
    )
    result["oracle_priority"] = oracle_rank
    result["utility_priority"] = utility_rank
    result["hybrid_priority"] = 0.5 * oracle_rank + 0.5 * utility_rank
    result["low_loss_priority"] = 1.0 - result.groupby("date")[
        "predicted_loss_probability"
    ].rank(method="average", pct=True)
    return result


def schedule_economic_capacity(
    panel: pd.DataFrame, *, max_positions: int,
    priority_column: str = "oracle_priority", keep_column: str | None = None,
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
            [priority_column, "directional_oracle_proba_extreme", "symbol"],
            ascending=[False, False, True],
        )
        for row in candidates.head(slots).itertuples():
            selected.append(int(row.Index))
            active[str(row.symbol)] = pd.Timestamp(row.exit_date)
    return panel.loc[selected].sort_values(["entry_date", "symbol"]).reset_index(drop=True)


def _rank_ic(frame: pd.DataFrame, score: str) -> float:
    valid = frame[[score, "net_return_lifecycle"]].dropna()
    if (
        len(valid) < 2
        or valid[score].nunique() < 2
        or valid["net_return_lifecycle"].nunique() < 2
    ):
        return float("nan")
    return float(valid[score].corr(valid["net_return_lifecycle"], method="spearman"))


def economic_model_diagnostics(panel: pd.DataFrame) -> dict[str, Any]:
    decile = pd.qcut(panel["predicted_net_utility"], 10, labels=False, duplicates="drop")
    deciles = []
    for value, group in panel.groupby(decile, observed=True):
        deciles.append({
            "decile": int(value), "events": int(len(group)),
            "mean_net_return": float(group["net_return_lifecycle"].mean()),
            "loss_rate": float(group["loss"].mean()),
            "trailing_rate": float(group["bad_trailing"].mean()),
        })
    daily_ic = panel.groupby("date").apply(
        lambda group: _rank_ic(group, "predicted_net_utility"),
        include_groups=False,
    ).dropna()
    return {
        "utility_ic_oof": _rank_ic(panel, "predicted_net_utility"),
        "utility_daily_ic_mean": float(daily_ic.mean()),
        "utility_daily_ic_positive_rate": float(daily_ic.gt(0).mean()),
        "utility_ic_by_fold": {
            str(fold): _rank_ic(group, "predicted_net_utility")
            for fold, group in panel.groupby("fold", sort=True)
        },
        "utility_deciles": deciles,
        "loss_score_ic_oof": _rank_ic(
            panel.assign(_safe=-panel["predicted_loss_probability"]), "_safe"
        ),
    }


def _evaluate_policy(
    baseline: pd.DataFrame, candidate: pd.DataFrame, config: E14Config
) -> dict[str, Any]:
    return {
        **_summary(candidate, config),
        "loss_rate": float(candidate["loss"].mean()) if len(candidate) else None,
        "comparison": _paired_daily_delta(baseline, candidate, config),
        "semester_stability": _semester_stability(baseline, candidate),
    }


def run(*, oracle_gate_path: Path, output_root: Path, config: E14Config) -> Path:
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
    events = deduplicate_non_overlapping(
        build_fixed_h20_events(oracle, bars, lifecycle_config)
    )
    events = add_pre_entry_features(events, bars)
    panel, rejected = build_outcome_panel(events, prepare_bars(bars), lifecycle_config)
    panel = panel[~panel["gap_rejected"]].copy()
    scored, fold_diagnostics = fit_oof_economic_heads(panel, config)
    scored = add_priority_scores(scored)

    baseline = schedule_economic_capacity(scored, max_positions=config.max_positions)
    policies: dict[str, Any] = {"baseline": {
        **_summary(baseline, config), "loss_rate": float(baseline["loss"].mean())
    }}
    selected: dict[str, pd.DataFrame] = {"baseline": baseline}
    for fraction in config.diagnostic_veto_fractions:
        for head in ("utility", "loss"):
            key = f"{head}_veto_{fraction:.2f}"
            chosen = schedule_economic_capacity(
                scored, max_positions=config.max_positions,
                keep_column=f"keep_{head}_{fraction:.2f}",
            )
            selected[key] = chosen
            policies[key] = _evaluate_policy(baseline, chosen, config)
    for key, priority in (
        ("utility_rerank", "utility_priority"),
        ("hybrid_rerank", "hybrid_priority"),
        ("low_loss_rerank", "low_loss_priority"),
    ):
        chosen = schedule_economic_capacity(
            scored, max_positions=config.max_positions, priority_column=priority
        )
        selected[key] = chosen
        policies[key] = _evaluate_policy(baseline, chosen, config)

    full_members, full_diag = load_exact_tradable_membership(
        engine, start_date=scored["date"].min(), end_date=scored["date"].max(),
        preset=lifecycle_config.capital_preset_key, quality="full",
    )
    degraded_members, degraded_diag = load_exact_tradable_membership(
        engine, start_date=scored["date"].min(), end_date=scored["date"].max(),
        preset=lifecycle_config.capital_preset_key, quality="any",
    )
    degraded = add_priority_scores(filter_by_membership(scored, degraded_members))
    degraded_baseline = schedule_economic_capacity(
        degraded, max_positions=config.max_positions
    ) if len(degraded) else degraded
    primary_key = f"utility_veto_{config.primary_veto_fraction:.2f}"
    degraded_primary = schedule_economic_capacity(
        degraded, max_positions=config.max_positions,
        keep_column=f"keep_utility_{config.primary_veto_fraction:.2f}",
    ) if len(degraded) else degraded

    primary = selected[primary_key]
    primary_metrics = policies[primary_key]
    comparison = primary_metrics["comparison"]
    semester_rows = [
        row for row in primary_metrics["semester_stability"] if row["lift"] is not None
    ]
    model_diagnostics = economic_model_diagnostics(scored)
    gates = {
        "utility_ic_positive": model_diagnostics["utility_ic_oof"] > 0,
        "utility_daily_ic_positive": model_diagnostics["utility_daily_ic_mean"] > 0,
        "coverage_at_least_70pct": len(primary) / len(baseline) >= 0.70,
        "daily_lift_positive": comparison["daily_delta"] > 0,
        "daily_lift_ci95_above_zero": comparison["ci95_low"] > 0,
        "loss_rate_not_worse": primary_metrics["loss_rate"] <= policies["baseline"]["loss_rate"],
        "q05_not_worse": primary_metrics["q05"] >= policies["baseline"]["q05"],
        "positive_lift_semesters_70pct": (
            bool(semester_rows)
            and sum(row["lift"] > 0 for row in semester_rows) / len(semester_rows) >= 0.70
        ),
        "strict_tradable_pit_available": full_diag["dates"] == scored["date"].nunique(),
    }
    gates["promotion_authorized"] = all(gates.values())
    verdict = "GO_EXACT_BACKTEST" if gates["promotion_authorized"] else "NO_GO_OR_BLOCKED"

    run_id = f"oracle-pre-entry-utility-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    scored.to_parquet(output / "oof_economic_scores.parquet", index=False)
    for key, frame in selected.items():
        frame.to_csv(output / f"portfolio_{key}.csv", index=False)
    rejected.to_csv(output / "entry_rejections.csv", index=False)
    report = {
        "schema_version": 1, "experiment": "E14_ORACLE_PRE_ENTRY_UTILITY",
        "status": "complete", "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "input": str(oracle_gate_path), "config": asdict(config),
        "contract": {
            "primary_target": "train-winsorized PROD net return",
            "secondary_target": "probability PROD net return below zero",
            "features": list(MODEL_FEATURES),
            "timing": "close J plus gap observable at open J+1",
            "purge": "train exit_date strictly before Oracle test fold start",
            "primary_policy": primary_key,
            "selection": "Oracle priority, max 8, refill after actual exit",
            "diagnostic_reranks": ["utility", "equal_weight_oracle_utility", "low_loss"],
        },
        "population": {
            "deduplicated_events": int(len(events)),
            "lifecycle_outcomes_after_gap": int(len(panel)),
            "oof_scored": int(len(scored)), "entry_rejections": int(len(rejected)),
        },
        "folds": fold_diagnostics, "models": model_diagnostics,
        "policies": policies,
        "tradable_pit": {
            "full": full_diag, "degraded": degraded_diag,
            "degraded_baseline": _summary(degraded_baseline, config),
            "degraded_primary": _summary(degraded_primary, config),
        },
        "gates": gates, "verdict": verdict,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E14 terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-gate", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_pre_entry_utility"),
    )
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_gate_path=args.oracle_gate, output_root=args.output_root,
        config=E14Config(
            iterations=args.iterations, bootstrap_samples=args.bootstrap_samples
        ),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E14 terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
