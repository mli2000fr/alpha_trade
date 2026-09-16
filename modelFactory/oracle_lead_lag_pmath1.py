"""P-MATH-1 — graphe cross-asset lead-lag sur rendements résiduels.

Recherche uniquement : aucune écriture SQL et aucune modification du serving.
Les bêtas, leaders et arêtes sont réappris dans le train de chaque fold. La
pression à J emploie exclusivement les rendements des leaders à J-k, k>0.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_benchmark_bars, load_universe_bars
from modelFactory.directional_alpha_book import load_sector_reference
from modelFactory.oracle.dataset import GUARD_COL, build_dataset as build_oracle_dataset
from modelFactory.oracle.train import get_universe_symbols
from modelFactory.oracle_separability_pmath0 import (
    DECILE, TARGET, attach_task, balanced_by_date, fit_preprocessor, transform,
)
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL, _load_gate, load_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("config/research/pmath1_cross_asset_lead_lag.json")
PRESSURE = "lead_lag_pressure"


@dataclass(frozen=True)
class ResidualModel:
    coefficients: pd.DataFrame
    sectors: dict[str, str]


def adjusted_return_panel(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    close = pd.to_numeric(frame.get("adj_close"), errors="coerce")
    close = close.fillna(pd.to_numeric(frame["close"], errors="coerce"))
    frame["adjusted_close"] = close.where(close.gt(0))
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    frame["return"] = frame.groupby("symbol")["adjusted_close"].pct_change(fill_method=None)
    return frame.pivot(index="date", columns="symbol", values="return").sort_index()


def benchmark_returns(frame: pd.DataFrame) -> pd.Series:
    work = frame.copy().sort_values("date")
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    close = pd.to_numeric(work.get("adj_close"), errors="coerce")
    close = close.fillna(pd.to_numeric(work["close"], errors="coerce"))
    return close.pct_change(fill_method=None).set_axis(work["date"]).rename("market")


def fit_residual_model(
    returns: pd.DataFrame,
    market: pd.Series,
    sector_by_symbol: dict[str, str],
    train_dates: pd.Index,
    *,
    min_observations: int,
) -> tuple[ResidualModel, pd.DataFrame]:
    """Fit fixed train-only market/sector betas and residualize all dates."""
    sectors = pd.Series({c: sector_by_symbol.get(c, "UNKNOWN") for c in returns.columns})
    sector_factor = pd.DataFrame(index=returns.index)
    for sector in sorted(sectors.unique()):
        members = sectors[sectors.eq(sector)].index.intersection(returns.columns)
        sector_factor[sector] = returns[members].median(axis=1, skipna=True)
    train_index = returns.index.intersection(pd.DatetimeIndex(train_dates))
    rows: list[dict[str, Any]] = []
    residual = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    aligned_market = market.reindex(returns.index)
    for symbol in returns.columns:
        sector = sectors[symbol]
        design = pd.DataFrame({"market": aligned_market, "sector": sector_factor[sector]})
        joined = pd.concat([returns[symbol].rename("asset"), design], axis=1).loc[train_index].dropna()
        if len(joined) < min_observations:
            rows.append({"symbol": symbol, "intercept": np.nan, "beta_market": np.nan,
                         "beta_sector": np.nan, "observations": len(joined)})
            continue
        matrix = np.column_stack([np.ones(len(joined)), joined["market"], joined["sector"]])
        coef, *_ = np.linalg.lstsq(matrix, joined["asset"].to_numpy(float), rcond=None)
        fitted = coef[0] + coef[1] * design["market"] + coef[2] * design["sector"]
        residual[symbol] = returns[symbol] - fitted
        rows.append({"symbol": symbol, "intercept": coef[0], "beta_market": coef[1],
                     "beta_sector": coef[2], "observations": len(joined)})
    coefficients = pd.DataFrame(rows).set_index("symbol")
    return ResidualModel(coefficients, sectors.to_dict()), residual


def _corr_and_overlap(frame: pd.DataFrame, series: pd.Series) -> tuple[pd.Series, pd.Series]:
    valid = frame.notna().mul(series.notna(), axis=0)
    return frame.corrwith(series), valid.sum(axis=0)


def learn_stable_edges(
    residuals: pd.DataFrame,
    train_dates: pd.Index,
    *,
    lags: list[int],
    max_candidate_leaders: int,
    max_edges_per_follower: int,
    min_half_overlap: int,
    min_abs_half_correlation: float,
    min_symbol_train_observations: int,
) -> pd.DataFrame:
    """Select unsupervised edges stable in both chronological train halves."""
    train = residuals.loc[residuals.index.intersection(pd.DatetimeIndex(train_dates))]
    coverage = train.notna().sum()
    volatility = train.std().fillna(0.0)
    eligible = coverage[coverage.ge(min_symbol_train_observations)].index
    leaders = pd.DataFrame({"coverage": coverage.loc[eligible], "volatility": volatility.loc[eligible]})
    leaders = leaders.sort_values(["coverage", "volatility"], ascending=False).head(max_candidate_leaders).index
    if len(train) < 2 or not len(leaders):
        return pd.DataFrame(columns=["follower", "leader", "lag", "weight", "corr_first", "corr_second"])
    midpoint = len(train) // 2
    halves = (train.iloc[:midpoint], train.iloc[midpoint:])
    candidates: list[pd.DataFrame] = []
    for lag in lags:
        for leader in leaders:
            first_corr, first_n = _corr_and_overlap(halves[0], halves[0][leader].shift(lag))
            second_corr, second_n = _corr_and_overlap(halves[1], halves[1][leader].shift(lag))
            stable = (
                first_n.ge(min_half_overlap) & second_n.ge(min_half_overlap)
                & first_corr.abs().ge(min_abs_half_correlation)
                & second_corr.abs().ge(min_abs_half_correlation)
                & np.sign(first_corr).eq(np.sign(second_corr))
            )
            stable.loc[leader] = False
            followers = stable[stable].index
            if not len(followers):
                continue
            weight = np.sign(first_corr.loc[followers]) * np.minimum(
                first_corr.loc[followers].abs(), second_corr.loc[followers].abs())
            candidates.append(pd.DataFrame({
                "follower": followers, "leader": leader, "lag": lag,
                "weight": weight.to_numpy(float),
                "corr_first": first_corr.loc[followers].to_numpy(float),
                "corr_second": second_corr.loc[followers].to_numpy(float),
            }))
    if not candidates:
        return pd.DataFrame(columns=["follower", "leader", "lag", "weight", "corr_first", "corr_second"])
    edges = pd.concat(candidates, ignore_index=True)
    edges["strength"] = edges["weight"].abs()
    edges = edges.sort_values(["follower", "strength"], ascending=[True, False])
    return edges.groupby("follower", sort=False).head(max_edges_per_follower).drop(columns="strength").reset_index(drop=True)


def compute_pressure(residuals: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """Return normalized pressure; every input is shifted by a strictly positive lag."""
    if edges.empty:
        return pd.DataFrame(columns=["date", "symbol", PRESSURE, "lead_lag_edges_available"])
    rows: list[pd.DataFrame] = []
    for follower, group in edges.groupby("follower", sort=False):
        numerator = pd.Series(0.0, index=residuals.index)
        denominator = pd.Series(0.0, index=residuals.index)
        count = pd.Series(0, index=residuals.index, dtype=int)
        for edge in group.itertuples(index=False):
            signal = residuals[edge.leader].shift(int(edge.lag))
            valid = signal.notna()
            numerator = numerator.add(signal.fillna(0.0) * float(edge.weight), fill_value=0.0)
            denominator = denominator.add(valid.astype(float) * abs(float(edge.weight)), fill_value=0.0)
            count = count.add(valid.astype(int), fill_value=0).astype(int)
        rows.append(pd.DataFrame({
            "date": residuals.index, "symbol": follower,
            PRESSURE: numerator.div(denominator.replace(0.0, np.nan)).to_numpy(float),
            "lead_lag_edges_available": count.to_numpy(int),
        }))
    return pd.concat(rows, ignore_index=True)


def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]:
    wf = config["walk_forward"]
    folds = build_folds_adaptive(
        dataset, min_train_dates=int(wf["min_train_dates"]), val_dates=int(wf["val_dates"]),
        test_dates=int(wf["test_dates"]), step_dates=int(wf["step_dates"]), max_splits=10_000,
        forecast_horizon=horizon, materialize=False,
    )
    return folds[-int(wf["max_splits"]):]


def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(frame["date"])
    guards = pd.to_datetime(frame[GUARD_COL])
    train = frame[dates.isin(spec["train_dates"]) & guards.lt(pd.Timestamp(spec["val_start"]))]
    return train, frame[dates.isin(spec["test_dates"])]


def _signed_return(task: str, frame: pd.DataFrame) -> pd.Series:
    raw = pd.to_numeric(frame["future_return"], errors="coerce")
    return -raw if task == "D1_VS_REST" else raw


def evaluate_task(
    train: pd.DataFrame, test: pd.DataFrame, features: list[str], task: str,
    config: dict[str, Any], seed: int,
) -> dict[str, Any]:
    model_cfg = config["model"]
    raw_test_rows = len(test)
    pressure_coverage = float(test[PRESSURE].notna().mean()) if raw_test_rows else 0.0
    train = train.dropna(subset=[PRESSURE]).copy()
    test = test.dropna(subset=[PRESSURE]).copy()
    train_sample = balanced_by_date(train, max_per_class=int(model_cfg["classifier_train_max_per_class"]), seed=seed)
    test_sample = balanced_by_date(test, max_per_class=int(model_cfg["test_max_per_class"]), seed=seed + 1)
    if train_sample[TARGET].nunique() < 2 or test_sample[TARGET].nunique() < 2:
        raise ValueError(f"P-MATH-1 {task}: classes insuffisantes")
    prep = fit_preprocessor(
        train_sample, features, lower_q=float(model_cfg["winsor_lower"]),
        upper_q=float(model_cfg["winsor_upper"]), max_missing_rate=float(model_cfg["max_missing_rate"]),
    )
    train_x, test_x = transform(train_sample, prep), transform(test_sample, prep)
    train_y, test_y = train_sample[TARGET].to_numpy(int), test_sample[TARGET].to_numpy(int)
    baseline = LogisticRegression(max_iter=500, solver="lbfgs", random_state=seed).fit(train_x, train_y)
    augmented = LogisticRegression(max_iter=500, solver="lbfgs", random_state=seed).fit(
        np.column_stack([train_x, train_sample[PRESSURE]]), train_y)
    base_score = baseline.predict_proba(test_x)[:, 1]
    aug_score = augmented.predict_proba(np.column_stack([test_x, test_sample[PRESSURE]]))[:, 1]
    pressure_score = test_sample[PRESSURE].to_numpy(float)
    if task == "D1_VS_REST":
        pressure_score = -pressure_score
    auc_base = float(roc_auc_score(test_y, base_score))
    auc_aug = float(roc_auc_score(test_y, aug_score))
    auc_pressure = float(roc_auc_score(test_y, pressure_score))
    cutoff_base = np.nanquantile(base_score, 0.9)
    cutoff_aug = np.nanquantile(aug_score, 0.9)
    signed = _signed_return(task, test_sample)
    ret_base = float(signed[base_score >= cutoff_base].mean())
    ret_aug = float(signed[aug_score >= cutoff_aug].mean())
    return {
        "rows_train": len(train_sample), "rows_test": len(test_sample), "features_used": len(prep.features),
        "pressure_auc": auc_pressure, "baseline_auc": auc_base, "augmented_auc": auc_aug,
        "incremental_auc_delta": auc_aug - auc_base,
        "baseline_signed_top_decile_return": ret_base,
        "augmented_signed_top_decile_return": ret_aug,
        "signed_top_decile_return_lift": ret_aug - ret_base,
        "pressure_coverage_test": pressure_coverage,
        "rows_test_before_pressure_filter": raw_test_rows,
    }


def summarize(rows: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    pressure_auc = np.asarray([r["pressure_auc"] for r in rows])
    delta = np.asarray([r["incremental_auc_delta"] for r in rows])
    lift = np.asarray([r["signed_top_decile_return_lift"] for r in rows])
    checks = {
        "pressure_auc": float(np.nanmedian(pressure_auc)) >= float(gates["pressure_auc_median_min"]),
        "incremental_auc": float(np.nanmedian(delta)) >= float(gates["incremental_auc_median_delta_min"]),
        "fold_stability": float(np.mean(delta > 0)) >= float(gates["incremental_auc_positive_fold_rate_min"]),
        "economic_lift": float(np.nanmedian(lift)) >= float(gates["signed_top_decile_return_lift_min"]),
    }
    return {
        "folds": len(rows), "pressure_auc_median": float(np.nanmedian(pressure_auc)),
        "baseline_auc_median": float(np.nanmedian([r["baseline_auc"] for r in rows])),
        "augmented_auc_median": float(np.nanmedian([r["augmented_auc"] for r in rows])),
        "incremental_auc_delta_median": float(np.nanmedian(delta)),
        "incremental_auc_positive_fold_rate": float(np.mean(delta > 0)),
        "signed_top_decile_return_lift_median": float(np.nanmedian(lift)),
        "gate_checks": checks,
        "verdict": "GO_INCREMENTAL_LEAD_LAG" if all(checks.values()) else "NO_GO_INCREMENTAL_LEAD_LAG",
    }


def run(args: argparse.Namespace) -> Path:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.max_folds is not None:
        config["walk_forward"]["max_splits"] = args.max_folds
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, args.batch_id, args.horizon)
    if args.max_symbols:
        symbols = symbols[:args.max_symbols]
    profile = load_profile(Path(args.state_profile or config["state_profile"]))
    pool, features = build_oracle_dataset(
        engine, args.batch_id, symbols, start_date=args.start_date, end_date=args.end_date,
        horizon=args.horizon, require_global_rank=False, need_targets=False,
        feature_whitelist=profile["feature_columns"], generator_options=profile["generator_options"],
    )
    pool["date"] = pd.to_datetime(pool["date"]).dt.normalize()
    pool["symbol"] = pool["symbol"].astype(str).str.upper()
    gate = _load_gate(Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet", float(config["pool_pct"]))
    eligible = gate[gate["shared_oracle_eligible"]][["date", "symbol", ORACLE_GATE_SCORE_COL]]
    pool = pool.merge(eligible, on=["date", "symbol"], how="inner", validate="one_to_one")
    pool = pool.dropna(subset=[DECILE, GUARD_COL, "future_return"])
    specs = _fold_specs(pool, config, args.horizon)
    if not specs:
        raise ValueError("Aucun fold P-MATH-1")
    warmup = (pd.Timestamp(args.start_date) - pd.Timedelta(days=30)).date()
    bars = load_universe_bars(engine, symbols, start_date=warmup, end_date=pd.Timestamp(args.end_date).date())
    benchmark = load_benchmark_bars(engine, "SPY", start_date=warmup, end_date=pd.Timestamp(args.end_date).date())
    returns = adjusted_return_panel(bars)
    market = benchmark_returns(benchmark)
    sectors = load_sector_reference(engine, symbols).set_index("symbol")["sector"].to_dict()
    output = args.output or Path("artifacts/research/pmath1_cross_asset_lead_lag") / datetime.now(UTC).strftime("pmath1-%Y%m%d%H%M%S")
    output.mkdir(parents=True, exist_ok=False)
    all_metrics: list[dict[str, Any]] = []
    all_edges: list[pd.DataFrame] = []
    seed = int(config["model"]["random_seed"])
    for fold_index, spec in enumerate(specs):
        LOGGER.info("P-MATH-1 fold=%d residualisation et graphe", fold_index)
        _, residuals = fit_residual_model(
            returns, market, sectors, pd.Index(spec["train_dates"]),
            min_observations=int(config["graph"]["beta_min_observations"]),
        )
        edges = learn_stable_edges(
            residuals, pd.Index(spec["train_dates"]), lags=[int(x) for x in config["lags"]],
            max_candidate_leaders=int(config["graph"]["max_candidate_leaders"]),
            max_edges_per_follower=int(config["graph"]["max_edges_per_follower"]),
            min_half_overlap=int(config["graph"]["min_half_overlap"]),
            min_abs_half_correlation=float(config["graph"]["min_abs_half_correlation"]),
            min_symbol_train_observations=int(config["graph"]["min_symbol_train_observations"]),
        )
        edges.insert(0, "fold_index", fold_index)
        all_edges.append(edges)
        pressure = compute_pressure(residuals, edges.drop(columns="fold_index"))
        fold_pool = pool.merge(pressure, on=["date", "symbol"], how="left", validate="one_to_one")
        for task_index, task in enumerate(config["tasks"]):
            task_pool = attach_task(fold_pool, task)
            train, test = _split(task_pool, spec)
            metrics = evaluate_task(train, test, features, task, config, seed + 1000 * fold_index + task_index)
            metrics.update({"task": task, "fold_index": fold_index, "test_start": spec["t_start"],
                            "test_end": spec["t_end"], "edges": len(edges),
                            "followers_with_edges": int(edges["follower"].nunique()) if len(edges) else 0})
            all_metrics.append(metrics)
    metrics_frame = pd.DataFrame(all_metrics)
    metrics_frame.to_csv(output / "fold_metrics.csv", index=False)
    pd.concat(all_edges, ignore_index=True).to_csv(output / "stable_edges.csv", index=False)
    summaries = {task: summarize(metrics_frame[metrics_frame["task"].eq(task)].to_dict("records"), config["gates"])
                 for task in config["tasks"]}
    report = {
        "experiment": config["experiment"], "status": "COMPLETED_RESEARCH_ONLY",
        "batch_id": args.batch_id, "horizon": args.horizon,
        "period": [args.start_date, args.end_date], "folds": len(specs),
        "pool": {"rows": len(pool), "dates": pool["date"].nunique(), "symbols": pool["symbol"].nunique()},
        "graph_contract": {"train_only": True, "strictly_positive_lags": config["lags"],
                           "stable_across_train_halves": True, "supervised_edge_selection": False},
        "tasks": summaries, "config": config, "serving_changed": False, "database_writes": False,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"P-MATH-1 terminé: {output}")
    for task, summary in summaries.items():
        print(task, summary["verdict"], f"pressure_auc={summary['pressure_auc_median']:.4f}",
              f"delta_auc={summary['incremental_auc_delta_median']:+.4f}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--state-profile")
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--max-folds", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run(args)


if __name__ == "__main__":
    main()
