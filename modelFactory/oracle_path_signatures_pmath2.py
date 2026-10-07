"""P-MATH-2 — signatures tensorielles de faible profondeur des chemins J-20..J.

Canaux : temps, rendement du titre, rendement SPY et rendement sectoriel.
Recherche uniquement, sans dépendance au graphe P-MATH-1 ni écriture SQL.
"""
from __future__ import annotations

import argparse
import itertools
import json
import logging
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
from modelFactory.oracle_lead_lag_pmath1 import adjusted_return_panel, benchmark_returns
from modelFactory.oracle_separability_pmath0 import (
    DECILE, TARGET, attach_task, balanced_by_date, fit_preprocessor, transform,
)
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL, _load_gate, load_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("config/research/pmath2_path_signatures.json")
CHANNELS = ("time", "asset", "market", "sector")


def signature_feature_names(depth: int, channels: tuple[str, ...] = CHANNELS) -> list[str]:
    names: list[str] = []
    for level in range(1, depth + 1):
        names.extend("sig%d_%s" % (level, "_".join(items))
                     for items in itertools.product(channels, repeat=level))
    return names


def tensor_signature_batch(increments: np.ndarray, depth: int = 3) -> np.ndarray:
    """Exact truncated signature of batched piecewise-linear paths via Chen identity."""
    values = np.asarray(increments, dtype=np.float64)
    if values.ndim != 3 or depth not in (1, 2, 3):
        raise ValueError("increments must be [batch, steps, dimensions], depth in {1,2,3}")
    batch, _, dimension = values.shape
    level1 = np.zeros((batch, dimension), dtype=np.float64)
    level2 = np.zeros((batch, dimension, dimension), dtype=np.float64)
    level3 = np.zeros((batch, dimension, dimension, dimension), dtype=np.float64)
    for step in range(values.shape[1]):
        delta = values[:, step, :]
        old1 = level1.copy()
        old2 = level2.copy()
        delta2 = np.einsum("bi,bj->bij", delta, delta)
        if depth >= 3:
            level3 += np.einsum("bij,bk->bijk", old2, delta)
            level3 += 0.5 * np.einsum("bi,bjk->bijk", old1, delta2)
            level3 += np.einsum("bi,bj,bk->bijk", delta, delta, delta) / 6.0
        if depth >= 2:
            level2 += np.einsum("bi,bj->bij", old1, delta) + 0.5 * delta2
        level1 += delta
    parts = [level1]
    if depth >= 2:
        parts.append(level2.reshape(batch, -1))
    if depth >= 3:
        parts.append(level3.reshape(batch, -1))
    return np.concatenate(parts, axis=1)


def build_sector_factor(returns: pd.DataFrame, sector_by_symbol: dict[str, str]) -> tuple[pd.DataFrame, dict[str, str]]:
    sectors = {symbol: str(sector_by_symbol.get(symbol, "UNKNOWN") or "UNKNOWN")
               for symbol in returns.columns}
    factors = pd.DataFrame(index=returns.index)
    for sector in sorted(set(sectors.values())):
        members = [symbol for symbol, value in sectors.items() if value == sector]
        factors[sector] = returns[members].median(axis=1, skipna=True)
    return factors, sectors


def build_signature_panel(
    events: pd.DataFrame,
    returns: pd.DataFrame,
    market: pd.Series,
    sector_factors: pd.DataFrame,
    sector_by_symbol: dict[str, str],
    *,
    window: int,
    max_depth: int,
    min_valid_asset_sessions: int,
    chunk_size: int,
) -> tuple[pd.DataFrame, list[str]]:
    """Build signatures ending at J; no observation after the event date is read."""
    keys = events[["date", "symbol"]].drop_duplicates().copy()
    keys["date"] = pd.to_datetime(keys["date"]).dt.normalize()
    keys["symbol"] = keys["symbol"].astype(str).str.upper()
    dates = pd.DatetimeIndex(returns.index)
    date_position = pd.Series(np.arange(len(dates)), index=dates)
    symbol_position = {symbol: i for i, symbol in enumerate(returns.columns)}
    sector_position = {sector: i for i, sector in enumerate(sector_factors.columns)}
    return_values = returns.to_numpy(np.float64)
    market_values = market.reindex(dates).to_numpy(np.float64)
    sector_values = sector_factors.reindex(dates).to_numpy(np.float64)
    names = signature_feature_names(max_depth)
    output_parts: list[pd.DataFrame] = []
    offsets = np.arange(window - 1, -1, -1)
    for start in range(0, len(keys), chunk_size):
        chunk = keys.iloc[start:start + chunk_size].copy()
        date_pos = chunk["date"].map(date_position).fillna(-1).to_numpy(int)
        symbol_pos = chunk["symbol"].map(symbol_position).fillna(-1).to_numpy(int)
        sectors = chunk["symbol"].map(sector_by_symbol).fillna("UNKNOWN")
        sector_pos = sectors.map(sector_position).fillna(-1).to_numpy(int)
        eligible = (date_pos >= window - 1) & (symbol_pos >= 0) & (sector_pos >= 0)
        features = np.full((len(chunk), len(names)), np.nan, dtype=np.float32)
        valid_counts = np.zeros(len(chunk), dtype=np.int16)
        eligible_rows = np.flatnonzero(eligible)
        if len(eligible_rows):
            positions = date_pos[eligible_rows, None] - offsets[None, :]
            asset = return_values[positions, symbol_pos[eligible_rows, None]]
            market_path = market_values[positions]
            sector = sector_values[positions, sector_pos[eligible_rows, None]]
            valid = np.isfinite(asset)
            valid_counts[eligible_rows] = valid.sum(axis=1)
            accepted = valid_counts[eligible_rows] >= min_valid_asset_sessions
            if accepted.any():
                selected_rows = eligible_rows[accepted]
                increments = np.stack([
                    np.full_like(asset[accepted], 1.0 / window),
                    np.nan_to_num(asset[accepted], nan=0.0),
                    np.nan_to_num(market_path[accepted], nan=0.0),
                    np.nan_to_num(sector[accepted], nan=0.0),
                ], axis=2)
                features[selected_rows] = tensor_signature_batch(increments, max_depth).astype(np.float32)
        feature_frame = pd.DataFrame(features, columns=names, index=chunk.index)
        chunk["path_valid_asset_sessions"] = valid_counts
        output_parts.append(pd.concat([chunk, feature_frame], axis=1))
    return pd.concat(output_parts, ignore_index=True), names


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
    return (
        frame[dates.isin(spec["train_dates"]) & guards.lt(pd.Timestamp(spec["val_start"]))],
        frame[dates.isin(spec["test_dates"])],
    )


def _signed_return(task: str, frame: pd.DataFrame) -> pd.Series:
    raw = pd.to_numeric(frame["future_return"], errors="coerce")
    return -raw if task == "D1_VS_REST" else raw


def _fit_score(train: pd.DataFrame, test: pd.DataFrame, columns: list[str], cfg: dict[str, Any], seed: int) -> np.ndarray:
    prep = fit_preprocessor(
        train, columns, lower_q=float(cfg["winsor_lower"]), upper_q=float(cfg["winsor_upper"]),
        max_missing_rate=float(cfg["max_missing_rate"]),
    )
    train_x, test_x = transform(train, prep), transform(test, prep)
    model = LogisticRegression(max_iter=600, solver="lbfgs", random_state=seed).fit(train_x, train[TARGET].to_numpy(int))
    return model.predict_proba(test_x)[:, 1]


def evaluate_task(
    train: pd.DataFrame, test: pd.DataFrame, state_features: list[str], signature_names: list[str],
    task: str, config: dict[str, Any], seed: int,
) -> list[dict[str, Any]]:
    cfg = config["model"]
    coverage = float(test[signature_names[0]].notna().mean()) if len(test) else 0.0
    train = train.dropna(subset=[signature_names[0]]).copy()
    test = test.dropna(subset=[signature_names[0]]).copy()
    train = balanced_by_date(train, max_per_class=int(cfg["classifier_train_max_per_class"]), seed=seed)
    test = balanced_by_date(test, max_per_class=int(cfg["test_max_per_class"]), seed=seed + 1)
    if train[TARGET].nunique() < 2 or test[TARGET].nunique() < 2:
        raise ValueError(f"P-MATH-2 {task}: classes insuffisantes")
    depth1 = signature_feature_names(1)
    depth2 = signature_feature_names(2)
    variants = {
        "STATE_J": state_features,
        "SIGNATURE_D1": depth1,
        "SIGNATURE_D2": depth2,
        "SIGNATURE_D3": signature_names,
        "STATE_PLUS_SIGNATURE_D2": state_features + depth2,
        "STATE_PLUS_SIGNATURE_D3": state_features + signature_names,
    }
    signed = _signed_return(task, test)
    rows: list[dict[str, Any]] = []
    for offset, (variant, columns) in enumerate(variants.items()):
        score = _fit_score(train, test, columns, cfg, seed + offset)
        cutoff = np.nanquantile(score, 0.9)
        rows.append({
            "variant": variant, "auc": float(roc_auc_score(test[TARGET], score)),
            "signed_top_decile_return": float(signed[score >= cutoff].mean()),
            "rows_train": len(train), "rows_test": len(test), "path_coverage_test": coverage,
        })
    return rows


def summarize(metrics: pd.DataFrame, gates: dict[str, Any], depth: int) -> dict[str, Any]:
    suffix = f"D{depth}"
    signature = metrics[metrics["variant"].eq(f"SIGNATURE_{suffix}")].sort_values("fold_index")
    baseline = metrics[metrics["variant"].eq("STATE_J")].sort_values("fold_index")
    augmented = metrics[metrics["variant"].eq(f"STATE_PLUS_SIGNATURE_{suffix}")].sort_values("fold_index")
    delta_auc = augmented["auc"].to_numpy() - baseline["auc"].to_numpy()
    lift = augmented["signed_top_decile_return"].to_numpy() - baseline["signed_top_decile_return"].to_numpy()
    checks = {
        "signature_auc": float(np.median(signature["auc"])) >= float(gates["signature_auc_median_min"]),
        "incremental_auc": float(np.median(delta_auc)) >= float(gates["incremental_auc_median_delta_min"]),
        "fold_stability": float(np.mean(delta_auc > 0)) >= float(gates["incremental_auc_positive_fold_rate_min"]),
        "economic_lift": float(np.median(lift)) >= float(gates["signed_top_decile_return_lift_min"]),
    }
    return {
        "depth": depth, "signature_auc_median": float(np.median(signature["auc"])),
        "baseline_auc_median": float(np.median(baseline["auc"])),
        "augmented_auc_median": float(np.median(augmented["auc"])),
        "incremental_auc_delta_median": float(np.median(delta_auc)),
        "incremental_auc_positive_fold_rate": float(np.mean(delta_auc > 0)),
        "signed_top_decile_return_lift_median": float(np.median(lift)),
        "gate_checks": checks,
        "verdict": "GO_INCREMENTAL_PATH_SIGNATURE" if all(checks.values()) else "NO_GO_INCREMENTAL_PATH_SIGNATURE",
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
    pool, state_features = build_oracle_dataset(
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
    path_cfg = config["path"]
    warmup = (pd.Timestamp(args.start_date) - pd.Timedelta(days=60)).date()
    bars = load_universe_bars(engine, symbols, start_date=warmup, end_date=pd.Timestamp(args.end_date).date())
    benchmark = load_benchmark_bars(engine, "SPY", start_date=warmup, end_date=pd.Timestamp(args.end_date).date())
    returns = adjusted_return_panel(bars)
    market = benchmark_returns(benchmark)
    sector_map = load_sector_reference(engine, symbols).set_index("symbol")["sector"].to_dict()
    sector_factors, normalized_sector_map = build_sector_factor(returns, sector_map)
    signatures, signature_names = build_signature_panel(
        pool, returns, market, sector_factors, normalized_sector_map,
        window=int(path_cfg["window_sessions"]), max_depth=int(path_cfg["max_depth"]),
        min_valid_asset_sessions=int(path_cfg["min_valid_asset_sessions"]),
        chunk_size=int(path_cfg["chunk_size"]),
    )
    pool = pool.merge(signatures, on=["date", "symbol"], how="left", validate="one_to_one")
    output = args.output or Path("artifacts/research/pmath2_path_signatures") / datetime.now(UTC).strftime("pmath2-%Y%m%d%H%M%S")
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    seed = int(config["model"]["random_seed"])
    for fold_index, spec in enumerate(specs):
        for task_index, task in enumerate(config["tasks"]):
            task_pool = attach_task(pool, task)
            train, test = _split(task_pool, spec)
            LOGGER.info("P-MATH-2 task=%s fold=%d train=%d test=%d", task, fold_index, len(train), len(test))
            results = evaluate_task(train, test, state_features, signature_names, task, config,
                                    seed + 1000 * fold_index + task_index)
            for result in results:
                result.update({"task": task, "fold_index": fold_index,
                               "test_start": spec["t_start"], "test_end": spec["t_end"]})
                rows.append(result)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output / "fold_metrics.csv", index=False)
    summaries = {
        task: {f"depth_{depth}": summarize(metrics[metrics["task"].eq(task)], config["gates"], depth)
               for depth in (2, 3)}
        for task in config["tasks"]
    }
    report = {
        "experiment": config["experiment"], "status": "COMPLETED_RESEARCH_ONLY",
        "batch_id": args.batch_id, "horizon": args.horizon, "period": [args.start_date, args.end_date],
        "pool": {"rows": len(pool), "dates": pool["date"].nunique(), "symbols": pool["symbol"].nunique(),
                 "path_coverage": float(pool[signature_names[0]].notna().mean())},
        "folds": len(specs), "signature_dimensions": {"depth_1": 4, "depth_2": 20, "depth_3": 84},
        "path_contract": {"window_sessions": path_cfg["window_sessions"], "ends_at_event_date": True,
                          "uses_future_observations": False, "channels": path_cfg["channels"],
                          "primary_depth": path_cfg["primary_depth"], "graph_dependency": False},
        "tasks": summaries, "config": config, "serving_changed": False, "database_writes": False,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"P-MATH-2 terminé: {output}")
    for task, values in summaries.items():
        primary = values["depth_2"]
        print(task, primary["verdict"], f"sig_auc={primary['signature_auc_median']:.4f}",
              f"delta_auc={primary['incremental_auc_delta_median']:+.4f}")
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
