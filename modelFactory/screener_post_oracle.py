"""Recherche PIT des signaux screener après le TOP Oracle OOF.

Le module produit des artefacts d'audit uniquement. Il ne modifie ni serving,
ni cascade, ni backtest. Les règles sont découvertes sur train, filtrées sur
validation et mesurées sur test Walk-Forward purgé.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, inspect, text

from database.connection import get_sqlalchemy_engine
from modelFactory.dataset import generate_walk_forward_splits_by_dates
from modelFactory.shared_directional import _load_gate, load_forward_return_panel

LOGGER = logging.getLogger(__name__)
DEFAULT_ARTIFACTS_ROOT = Path("artifacts/models/screener_post_oracle")

# final_score_walk_forward et les poids/calibrations associés restent exclus :
# leur provenance strictement OOF n'est pas démontrée pour cette expérience.
PREDICTIVE_FEATURES = (
    "relative_strength_index", "historical_range_score", "total_score",
    "trend_score", "vcp_score", "final_score", "beta_126",
    "selection_rank", "raw_final_score", "normalized_total_score",
    "normalized_rsi", "total_score_neutralized",
    "relative_strength_index_neutralized", "trend_vcp_component",
    "total_score_component", "rsi_component", "atr_pct_20",
    "weekly_trend_score", "high_52w_proximity", "volatility_ratio",
    "sentiment_net_agg", "sector_impact_agg", "company_idio_score",
    "macro_regime_score", "company_idio_signal_norm",
    "macro_regime_signal_norm", "company_idio_component",
    "macro_regime_component", "quant_component", "final_score_sentiment",
    "short_score",
)
TRADABILITY_FEATURES = (
    "liquidity_val", "market_cap", "spread_bps", "days_to_earnings",
    "earnings_blackout", "signal_active", "anomaly_count",
    "missing_days_count",
)


@dataclass(frozen=True, slots=True)
class ScreenerAuditConfig:
    horizons: tuple[int, ...] = (3, 10, 20)
    pool_pct: float = 0.20
    capital_preset_key: str = "capital_2001_5000"
    max_snapshot_age_days: int = 7
    quantile_bins: int = 5
    min_feature_coverage: float = 0.50
    min_rule_retention: float = 0.20
    min_effective_retention: float = 0.02
    min_train_dates: int = 504
    val_dates: int = 126
    test_dates: int = 126
    step_dates: int = 126
    max_splits: int = 12
    up_threshold: float = 0.03
    down_threshold: float = -0.03
    max_abs_future_return: float = 10.0
    sector_min_members: int = 5

    def __post_init__(self) -> None:
        horizons = tuple(sorted({int(value) for value in self.horizons}))
        object.__setattr__(self, "horizons", horizons)
        if not horizons or min(horizons) < 1:
            raise ValueError("Les horizons doivent être positifs.")
        if not 0 < self.pool_pct < 1:
            raise ValueError("pool_pct doit être dans ]0,1[.")
        if self.quantile_bins < 3:
            raise ValueError("quantile_bins doit être >= 3.")
        if not 0 < self.min_feature_coverage <= 1:
            raise ValueError("min_feature_coverage doit être dans ]0,1].")
        if not 0 < self.min_rule_retention < 1:
            raise ValueError("min_rule_retention doit être dans ]0,1[.")
        if not 0 < self.min_effective_retention < 1:
            raise ValueError("min_effective_retention doit être dans ]0,1[.")
        if self.up_threshold <= 0 or self.down_threshold >= 0:
            raise ValueError("Les seuils directionnels doivent encadrer zéro.")
        if self.max_abs_future_return <= 1:
            raise ValueError("max_abs_future_return doit être > 1.")


def available_screener_features(engine: Any) -> tuple[list[str], list[str]]:
    columns = {str(item["name"]) for item in inspect(engine).get_columns("stock_scores_history")}
    return (
        [name for name in PREDICTIVE_FEATURES if name in columns],
        [name for name in TRADABILITY_FEATURES if name in columns],
    )


def load_screener_snapshots(
    engine: Any,
    symbols: list[str],
    *,
    start_date: str,
    end_date: str,
    capital_preset_key: str,
    feature_columns: list[str],
) -> pd.DataFrame:
    """Charge les valeurs brutes sans jamais remplacer les absences par zéro."""
    if not symbols:
        return pd.DataFrame()
    columns = ["symbol", "snapshot_date", "created_at", *feature_columns]
    query = text(
        "SELECT " + ", ".join(f"`{column}`" for column in columns)
        + " FROM stock_scores_history WHERE symbol IN :symbols"
        + " AND snapshot_date >= :start_date AND snapshot_date <= :end_date"
        + " AND capital_preset_key = :capital_preset_key"
        + " ORDER BY symbol, snapshot_date, created_at"
    ).bindparams(bindparam("symbols", expanding=True))
    with engine.connect() as connection:
        frame = pd.read_sql(query, connection, params={
            "symbols": symbols, "start_date": start_date, "end_date": end_date,
            "capital_preset_key": capital_preset_key,
        })
    if frame.empty:
        return frame
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce").dt.normalize()
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
    frame = frame.dropna(subset=["symbol", "snapshot_date"])
    return frame.drop_duplicates(["symbol", "snapshot_date"], keep="last")


def merge_screener_asof(
    pool: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    feature_columns: list[str],
    max_age_days: int,
) -> pd.DataFrame:
    """Joint le dernier snapshot avec snapshot_date <= date de décision."""
    base = pool.copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    base["symbol"] = base["symbol"].astype(str).str.upper()
    parts: list[pd.DataFrame] = []
    for symbol, events in base.groupby("symbol", sort=False):
        left = events.sort_values("date")
        right = snapshots[snapshots["symbol"].eq(symbol)].drop(columns=["symbol"]).sort_values("snapshot_date")
        if right.empty:
            merged = left.copy()
            merged["snapshot_date"] = pd.NaT
            merged["created_at"] = pd.NaT
            for column in feature_columns:
                merged[column] = np.nan
        else:
            merged = pd.merge_asof(
                left, right, left_on="date", right_on="snapshot_date",
                direction="backward", allow_exact_matches=True,
            )
        parts.append(merged)
    result = pd.concat(parts, ignore_index=True) if parts else base.iloc[0:0].copy()
    result["snapshot_age_days"] = (result["date"] - result["snapshot_date"]).dt.days
    result["screener_snapshot_present"] = result["snapshot_date"].notna()
    result["screener_snapshot_fresh"] = result["snapshot_age_days"].between(
        0, int(max_age_days), inclusive="both"
    ).fillna(False)
    return result


def attach_outcome(
    dataset: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    horizon: int,
    up_threshold: float,
    down_threshold: float,
    max_abs_future_return: float,
) -> pd.DataFrame:
    columns = [
        "date", "symbol", "future_return", "future_return_excess_spy",
        "future_return_sector_residual",
    ]
    target = panel[panel["horizon"].eq(int(horizon))][columns]
    out = dataset.merge(target, on=["date", "symbol"], how="left", validate="one_to_one")
    raw = pd.to_numeric(out["future_return"], errors="coerce")
    out["target_quality_valid"] = raw.abs().le(float(max_abs_future_return)) & raw.notna()
    invalid = raw.notna() & ~out["target_quality_valid"]
    out.loc[invalid, [
        "future_return", "future_return_excess_spy",
        "future_return_sector_residual",
    ]] = np.nan
    raw = pd.to_numeric(out["future_return"], errors="coerce")
    out["true_long"] = raw.ge(float(up_threshold)).where(raw.notna())
    out["true_short"] = raw.le(float(down_threshold)).where(raw.notna())
    out["horizon"] = int(horizon)
    return out


def _equal_date_metrics(frame: pd.DataFrame, side: str) -> dict[str, Any]:
    empty = {"rows": 0, "dates": 0, "symbols": 0, "mean_signed_return": None,
             "median_signed_return": None, "event_precision": None}
    if frame.empty:
        return empty
    sign = 1.0 if side == "long" else -1.0
    event_column = "true_long" if side == "long" else "true_short"
    usable = frame.dropna(subset=["future_return", event_column]).copy()
    if usable.empty:
        return empty
    usable["signed_return"] = sign * pd.to_numeric(usable["future_return"], errors="coerce")
    daily = usable.groupby("date", as_index=False).agg(
        signed_return=("signed_return", "mean"), event=(event_column, "mean")
    )
    return {
        "rows": int(len(usable)), "dates": int(usable["date"].nunique()),
        "symbols": int(usable["symbol"].nunique()),
        "mean_signed_return": float(daily["signed_return"].mean()),
        "median_signed_return": float(usable["signed_return"].median()),
        "event_precision": float(daily["event"].mean()),
    }


def evaluate_rule(
    frame: pd.DataFrame,
    feature: str,
    side: str,
    orientation: str,
    threshold: float,
) -> dict[str, Any]:
    usable = frame[frame["screener_snapshot_fresh"] & frame[feature].notna()].copy()
    if usable.empty:
        baseline = _equal_date_metrics(usable, side)
        return {"retention": 0.0, "effective_retention": 0.0,
                "selected": baseline, "baseline": baseline,
                "return_lift": None, "precision_lift": None}
    values = pd.to_numeric(usable[feature], errors="coerce")
    mask = values.ge(threshold) if orientation == "high" else values.le(threshold)
    selected_frame = usable[mask]
    selected = _equal_date_metrics(selected_frame, side)
    # Tirage aléatoire apparié : même population observable et mêmes dates que
    # la règle. L'espérance aléatoire à taille égale est la moyenne du pool de
    # ces dates, indépendamment du nombre exact de lignes tirées.
    selected_dates = pd.Index(selected_frame["date"].unique())
    baseline = _equal_date_metrics(usable[usable["date"].isin(selected_dates)], side)
    return_lift = (
        selected["mean_signed_return"] - baseline["mean_signed_return"]
        if selected["mean_signed_return"] is not None and baseline["mean_signed_return"] is not None else None
    )
    precision_lift = (
        selected["event_precision"] - baseline["event_precision"]
        if selected["event_precision"] is not None and baseline["event_precision"] is not None else None
    )
    return {
        "retention": float(mask.sum() / len(usable)),
        "effective_retention": float(mask.sum() / max(len(frame), 1)),
        "selected": selected,
        "baseline": baseline, "return_lift": return_lift,
        "precision_lift": precision_lift,
    }


def discover_rule(
    train: pd.DataFrame,
    feature: str,
    side: str,
    min_retention: float,
) -> dict[str, Any] | None:
    values = pd.to_numeric(
        train.loc[train["screener_snapshot_fresh"], feature], errors="coerce"
    ).dropna()
    if len(values) < 100 or values.nunique() < 5:
        return None
    candidates: list[dict[str, Any]] = []
    for quantile in (0.20, 0.40, 0.60, 0.80):
        threshold = float(values.quantile(quantile))
        for orientation in ("low", "high"):
            metrics = evaluate_rule(train, feature, side, orientation, threshold)
            if metrics["retention"] < min_retention:
                continue
            if metrics["return_lift"] is None or metrics["precision_lift"] is None:
                continue
            candidates.append({
                "feature": feature, "side": side, "orientation": orientation,
                "quantile": quantile, "threshold": threshold, "metrics": metrics,
            })
    if not candidates:
        return None
    nonnegative_precision = [
        candidate for candidate in candidates
        if candidate["metrics"]["precision_lift"] >= 0
    ]
    eligible = nonnegative_precision or candidates
    return max(
        eligible,
        key=lambda candidate: (
            candidate["metrics"]["return_lift"],
            candidate["metrics"]["precision_lift"],
        ),
    )


def feature_coverage(
    dataset: pd.DataFrame,
    features: Iterable[str],
    categories: dict[str, str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    denominator = max(len(dataset), 1)
    fresh_denominator = max(int(dataset["screener_snapshot_fresh"].sum()), 1)
    for feature in features:
        numeric = pd.to_numeric(dataset[feature], errors="coerce")
        observed = numeric[dataset["screener_snapshot_fresh"] & numeric.notna()]
        quantiles = observed.quantile([0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99])
        rows.append({
            "feature": feature, "category": categories[feature],
            "coverage": float(len(observed) / denominator),
            "coverage_given_fresh": float(len(observed) / fresh_denominator),
            "observed_rows": int(len(observed)),
            "zero_rate_observed": float(observed.eq(0).mean()) if len(observed) else None,
            "distinct_values": int(observed.nunique()),
            **{
                f"p{int(quantile * 100):02d}": (
                    float(quantiles.get(quantile)) if quantile in quantiles else None
                )
                for quantile in (0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99)
            },
        })
    return pd.DataFrame(rows)


def reliability_tables(
    dataset: pd.DataFrame,
    features: Iterable[str],
    bins: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, horizon_frame in dataset.groupby("horizon"):
        for feature in features:
            usable = horizon_frame[
                horizon_frame["screener_snapshot_fresh"]
                & horizon_frame[feature].notna()
                & horizon_frame["future_return"].notna()
            ].copy()
            if len(usable) < bins * 20 or usable[feature].nunique() < bins:
                continue
            try:
                usable["bin"] = pd.qcut(
                    usable[feature], q=bins, labels=False, duplicates="drop"
                )
            except ValueError:
                continue
            usable["semester"] = (
                usable["date"].dt.year.astype(str) + "H"
                + np.where(usable["date"].dt.month.le(6), "1", "2")
            )
            periods: list[tuple[str, pd.DataFrame]] = [("ALL", usable)]
            periods.extend((str(key), value) for key, value in usable.groupby("semester"))
            for period, period_frame in periods:
                for bin_index, group in period_frame.groupby("bin", observed=True):
                    daily = group.groupby("date").agg(
                        raw_return=("future_return", "mean"),
                        p_long=("true_long", "mean"),
                        p_short=("true_short", "mean"),
                    )
                    rows.append({
                        "period": period, "horizon": int(horizon),
                        "feature": feature, "bin": int(bin_index) + 1,
                        "support": int(len(group)),
                        "dates": int(group["date"].nunique()),
                        "symbols": int(group["symbol"].nunique()),
                        "feature_min": float(pd.to_numeric(group[feature]).min()),
                        "feature_max": float(pd.to_numeric(group[feature]).max()),
                        "mean_raw_return": float(daily["raw_return"].mean()),
                        "p_true_long": float(daily["p_long"].mean()),
                        "p_true_short": float(daily["p_short"].mean()),
                    })
    return pd.DataFrame(rows)


def coverage_by_semester(dataset: pd.DataFrame, features: Iterable[str]) -> pd.DataFrame:
    working = dataset.copy()
    working["semester"] = (
        working["date"].dt.year.astype(str)
        + "H" + np.where(working["date"].dt.month.le(6), "1", "2")
    )
    rows: list[dict[str, Any]] = []
    for semester, frame in working.groupby("semester"):
        fresh_rows = int(frame["screener_snapshot_fresh"].sum())
        for feature in features:
            observed = frame["screener_snapshot_fresh"] & frame[feature].notna()
            rows.append({
                "semester": str(semester), "feature": feature,
                "pool_rows": int(len(frame)), "fresh_rows": fresh_rows,
                "observed_rows": int(observed.sum()),
                "absolute_coverage": float(observed.mean()),
                "coverage_given_fresh": float(observed.sum() / max(fresh_rows, 1)),
            })
    return pd.DataFrame(rows)


def snapshot_presence_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    """Mesure le filtre « snapshot screener frais présent », sans règle de score."""
    rows: list[dict[str, Any]] = []
    working = dataset.copy()
    working["semester"] = (
        working["date"].dt.year.astype(str)
        + "H"
        + np.where(working["date"].dt.month.le(6), "1", "2")
    )
    groups: list[tuple[str, pd.DataFrame]] = [("ALL", working)]
    groups.extend((str(key), value) for key, value in working.groupby("semester"))
    for period, frame in groups:
        for horizon, horizon_frame in frame.groupby("horizon"):
            fresh = horizon_frame[horizon_frame["screener_snapshot_fresh"]]
            for side in ("long", "short"):
                baseline = _equal_date_metrics(horizon_frame, side)
                selected = _equal_date_metrics(fresh, side)
                rows.append({
                    "period": period, "horizon": int(horizon), "side": side,
                    "pool_rows": int(len(horizon_frame)), "fresh_rows": int(len(fresh)),
                    "effective_retention": float(len(fresh) / max(len(horizon_frame), 1)),
                    "baseline_signed_return": baseline["mean_signed_return"],
                    "fresh_signed_return": selected["mean_signed_return"],
                    "return_lift": (
                        selected["mean_signed_return"] - baseline["mean_signed_return"]
                        if selected["mean_signed_return"] is not None
                        and baseline["mean_signed_return"] is not None else None
                    ),
                    "baseline_precision": baseline["event_precision"],
                    "fresh_precision": selected["event_precision"],
                    "precision_lift": (
                        selected["event_precision"] - baseline["event_precision"]
                        if selected["event_precision"] is not None
                        and baseline["event_precision"] is not None else None
                    ),
                })
    return pd.DataFrame(rows)


def run_walk_forward_rules(
    dataset: pd.DataFrame,
    features: list[str],
    config: ScreenerAuditConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fold_rows: list[dict[str, Any]] = []
    for horizon, horizon_frame in dataset.groupby("horizon"):
        splits = generate_walk_forward_splits_by_dates(
            horizon_frame.sort_values("date").reset_index(drop=True),
            min_train_dates=config.min_train_dates, val_dates=config.val_dates,
            test_dates=config.test_dates, step_dates=config.step_dates,
            max_splits=config.max_splits, forecast_horizon=int(horizon),
            date_column="date",
        )
        for fold_index, split in enumerate(splits):
            for feature in features:
                for side in ("long", "short"):
                    rule = discover_rule(split.train, feature, side, config.min_rule_retention)
                    if rule is None:
                        continue
                    validation = evaluate_rule(
                        split.val, feature, side, rule["orientation"], rule["threshold"]
                    )
                    test_metrics = evaluate_rule(
                        split.test, feature, side, rule["orientation"], rule["threshold"]
                    )
                    validation_pass = bool(
                        validation["return_lift"] is not None
                        and validation["return_lift"] > 0
                        and validation["precision_lift"] is not None
                        and validation["precision_lift"] > 0
                        and validation["retention"] >= config.min_rule_retention
                    )
                    fold_rows.append({
                        "horizon": int(horizon), "fold": fold_index,
                        "feature": feature, "side": side,
                        "orientation": rule["orientation"],
                        "train_quantile": rule["quantile"],
                        "threshold": rule["threshold"],
                        "validation_pass": validation_pass,
                        "validation_retention": validation["retention"],
                        "validation_return_lift": validation["return_lift"],
                        "validation_precision_lift": validation["precision_lift"],
                        "test_start": str(pd.Timestamp(split.test["date"].min()).date()),
                        "test_end": str(pd.Timestamp(split.test["date"].max()).date()),
                        "test_retention": test_metrics["retention"],
                        "test_effective_retention": test_metrics["effective_retention"],
                        "test_return_lift": test_metrics["return_lift"],
                        "test_precision_lift": test_metrics["precision_lift"],
                        "test_selected_return": test_metrics["selected"]["mean_signed_return"],
                        "test_selected_precision": test_metrics["selected"]["event_precision"],
                        "test_rows": test_metrics["selected"]["rows"],
                        "test_dates": test_metrics["selected"]["dates"],
                    })
    folds = pd.DataFrame(fold_rows)
    if folds.empty:
        return folds, pd.DataFrame()
    summaries: list[dict[str, Any]] = []
    for (horizon, feature, side), group in folds.groupby(["horizon", "feature", "side"]):
        count = len(group)
        required = math.ceil(0.75 * count)
        validation_positive = int(group["validation_pass"].sum())
        return_positive = int(group["test_return_lift"].fillna(-np.inf).gt(0).sum())
        precision_positive = int(group["test_precision_lift"].fillna(-np.inf).gt(0).sum())
        mean_return_lift = float(group["test_return_lift"].mean())
        mean_precision_lift = float(group["test_precision_lift"].mean())
        mean_retention = float(group["test_retention"].mean())
        mean_effective_retention = float(group["test_effective_retention"].mean())
        passed = bool(
            count >= 3 and validation_positive >= required
            and return_positive >= required and precision_positive >= required
            and mean_return_lift > 0 and mean_precision_lift > 0
            and mean_retention >= config.min_rule_retention
            and mean_effective_retention >= config.min_effective_retention
        )
        summaries.append({
            "horizon": int(horizon), "feature": feature, "side": side,
            "folds": count, "required_positive_folds": required,
            "validation_pass_folds": validation_positive,
            "positive_return_lift_folds": return_positive,
            "positive_precision_lift_folds": precision_positive,
            "mean_test_return_lift": mean_return_lift,
            "mean_test_precision_lift": mean_precision_lift,
            "mean_test_retention": mean_retention,
            "mean_test_effective_retention": mean_effective_retention,
            "test_selected_rows": int(group["test_rows"].sum()),
            "development_verdict": "CANDIDATE_DEVELOPMENT" if passed else "NO_GO",
        })
    summary = pd.DataFrame(summaries).sort_values(
        ["horizon", "side", "development_verdict", "mean_test_return_lift"],
        ascending=[True, True, True, False],
    )
    return folds, summary


def run_campaign(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    config: ScreenerAuditConfig,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
) -> tuple[Path, dict[str, Any]]:
    predictive, tradability = available_screener_features(engine)
    all_features = predictive + tradability
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    gate = _load_gate(gate_path, config.pool_pct)
    gate = gate[
        gate["shared_oracle_eligible"]
        & gate["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    ].copy()
    if gate.empty:
        raise ValueError("Pool Oracle OOF vide sur la période demandée.")
    symbols = sorted(gate["symbol"].unique())
    snapshots = load_screener_snapshots(
        engine, symbols, start_date=start_date, end_date=end_date,
        capital_preset_key=config.capital_preset_key,
        feature_columns=all_features,
    )
    merged = merge_screener_asof(
        gate, snapshots, feature_columns=all_features,
        max_age_days=config.max_snapshot_age_days,
    )
    panel, target_diagnostics = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date,
        horizons=config.horizons, sector_min_members=config.sector_min_members,
    )
    dataset = pd.concat([
        attach_outcome(
            merged, panel, horizon=horizon,
            up_threshold=config.up_threshold, down_threshold=config.down_threshold,
            max_abs_future_return=config.max_abs_future_return,
        )
        for horizon in config.horizons
    ], ignore_index=True)
    categories = (
        {name: "predictive" for name in predictive}
        | {name: "tradability" for name in tradability}
    )
    coverage = feature_coverage(merged, all_features, categories)
    semester_coverage = coverage_by_semester(merged, all_features)
    eligible = coverage[
        coverage["category"].eq("predictive")
        & coverage["coverage_given_fresh"].ge(config.min_feature_coverage)
        & coverage["distinct_values"].ge(5)
    ]["feature"].tolist()
    reliability = reliability_tables(dataset, all_features, config.quantile_bins)
    presence = snapshot_presence_summary(dataset)
    folds, rules = run_walk_forward_rules(dataset, eligible, config)

    run_id = (
        f"screener-post-oracle-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-"
        f"{oracle_batch_id[-6:]}"
    )
    output = artifacts_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    coverage.to_csv(output / "feature_coverage.csv", index=False)
    semester_coverage.to_csv(output / "feature_coverage_by_semester.csv", index=False)
    reliability.to_csv(output / "reliability_bins.csv", index=False)
    presence.to_csv(output / "snapshot_presence_summary.csv", index=False)
    folds.to_csv(output / "walk_forward_folds.csv", index=False)
    rules.to_csv(output / "rule_summary.csv", index=False)
    dataset.to_parquet(output / "analytic_dataset.parquet", index=False)
    candidates = rules[
        rules["development_verdict"].eq("CANDIDATE_DEVELOPMENT")
    ] if not rules.empty else rules
    campaign = {
        "schema_version": 1, "run_id": run_id, "status": "completed",
        "experiment": "screener_pit_post_oracle", "research_only": True,
        "serving_ready": False, "source_oracle_batch_id": oracle_batch_id,
        "requested_period": {"start": start_date, "end": end_date},
        "effective_period": {
            "start": str(gate["date"].min().date()),
            "end": str(gate["date"].max().date()),
        },
        "config": asdict(config),
        "population": {
            "oracle_pool_rows": int(len(gate)),
            "dates": int(gate["date"].nunique()),
            "symbols": int(gate["symbol"].nunique()),
            "snapshot_present_rate": float(merged["screener_snapshot_present"].mean()),
            "snapshot_fresh_rate": float(merged["screener_snapshot_fresh"].mean()),
        },
        "target_diagnostics": target_diagnostics,
        "target_quality": {
            str(horizon): {
                "invalid_abs_return_rows": int(
                    ((dataset["horizon"].eq(horizon)) & ~dataset["target_quality_valid"]).sum()
                ),
                "max_abs_future_return": config.max_abs_future_return,
            }
            for horizon in config.horizons
        },
        "predictive_features_available": predictive,
        "tradability_features_available": tradability,
        "predictive_features_walk_forward": eligible,
        "excluded_provenance_columns": [
            "final_score_walk_forward", "walk_forward_sentiment_weight",
            "walk_forward_macro_weight", "walk_forward_quant_weight",
            "calibration_run_id", "calibration_source",
        ],
        "candidate_development_rules": candidates.to_dict("records"),
        "verdict": (
            "CANDIDATES_REQUIRE_INTACT_CONFIRMATION"
            if not candidates.empty else "NO_GO_PREDICTIVE"
        ),
        "integration_performed": False,
    }
    (output / "campaign.json").write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return output, campaign


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit screener PIT après Oracle TOP20 OOF.")
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--horizons", default="3,10,20")
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--capital-preset-key", default="capital_2001_5000")
    parser.add_argument("--max-snapshot-age-days", type=int, default=7)
    parser.add_argument("--quantile-bins", type=int, default=5)
    parser.add_argument("--min-feature-coverage", type=float, default=0.50)
    parser.add_argument("--min-rule-retention", type=float, default=0.20)
    parser.add_argument("--min-effective-retention", type=float, default=0.02)
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=12)
    parser.add_argument("--target-up-threshold", type=float, default=0.03)
    parser.add_argument("--target-down-threshold", type=float, default=-0.03)
    parser.add_argument("--max-abs-future-return", type=float, default=10.0)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    config = ScreenerAuditConfig(
        horizons=tuple(
            int(value.strip()) for value in args.horizons.split(",") if value.strip()
        ),
        pool_pct=args.pool_pct, capital_preset_key=args.capital_preset_key,
        max_snapshot_age_days=args.max_snapshot_age_days,
        quantile_bins=args.quantile_bins,
        min_feature_coverage=args.min_feature_coverage,
        min_rule_retention=args.min_rule_retention,
        min_effective_retention=args.min_effective_retention,
        min_train_dates=args.wf_min_train_size, val_dates=args.wf_val_size,
        test_dates=args.wf_test_size, step_dates=args.wf_step_size,
        max_splits=args.wf_max_splits,
        up_threshold=args.target_up_threshold,
        down_threshold=args.target_down_threshold,
        max_abs_future_return=args.max_abs_future_return,
    )
    output, campaign = run_campaign(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        config=config, artifacts_root=args.artifacts_root,
    )
    print(f"Audit screener post-Oracle terminé: {output}")
    print(f"Verdict: {campaign['verdict']}")
    print(f"Règles candidates: {len(campaign['candidate_development_rules'])}")
    print("Serving, cascade et backtest inchangés.")


if __name__ == "__main__":
    main()
