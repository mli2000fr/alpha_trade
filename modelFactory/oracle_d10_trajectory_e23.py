"""E23 research-only: D10 one-vs-rest after the Oracle TOP20 gate."""
from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import GUARD_COL, build_dataset as build_oracle_dataset
from modelFactory.oracle.train import get_universe_symbols, roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import ORACLE_GATE_SCORE_COL, _load_gate, load_profile

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("config/research/e23_oracle_d10_trajectory.json")
TARGET = "e23_d10_target"
RAW_SCORE = "e23_raw_probability"
CAL_SCORE = "e23_calibrated_probability"


def attach_d10_one_vs_rest(frame: pd.DataFrame) -> pd.DataFrame:
    """D10=1; every valid D1..D9 Oracle candidate=0."""
    result = frame.copy()
    decile = pd.to_numeric(result["oracle_decile"], errors="coerce")
    valid = decile.between(1, 10, inclusive="both")
    result[TARGET] = decile.eq(10).astype(float).where(valid)
    return result


def _session_map(dates: Iterable[Any]) -> dict[pd.Timestamp, int]:
    values = pd.to_datetime(pd.Series(list(dates)), errors="coerce").dropna().dt.normalize()
    unique = pd.DatetimeIndex(values.unique()).sort_values()
    return {pd.Timestamp(date): index for index, date in enumerate(unique)}


def attach_exact_session_lags(
    pool: pd.DataFrame,
    history: pd.DataFrame,
    source_columns: list[str],
    *,
    max_lag: int,
    prefix: str,
    session_map: dict[pd.Timestamp, int],
    include_current: bool,
    fill_zero_columns: set[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Attach exact J-k values without treating sparse pool appearances as days."""
    result = pool.copy()
    result["_e23_session"] = pd.to_datetime(result["date"]).dt.normalize().map(session_map)
    source = history.copy()
    source["_e23_session"] = pd.to_datetime(source["date"]).dt.normalize().map(session_map)
    source["symbol"] = source["symbol"].astype(str).str.upper()
    source = source.dropna(subset=["_e23_session"]).drop_duplicates(
        ["symbol", "_e23_session"], keep="last")
    added: list[str] = []
    first = 0 if include_current else 1
    zeroes = fill_zero_columns or set()
    for lag in range(first, max_lag + 1):
        names = {column: f"{prefix}_{column}_lag{lag}" for column in source_columns}
        lookup = source[["symbol", "_e23_session", *source_columns]].copy()
        lookup["_e23_session"] = lookup["_e23_session"].astype(int) + lag
        lookup = lookup.rename(columns=names)
        result = result.merge(
            lookup, on=["symbol", "_e23_session"], how="left", validate="many_to_one")
        for column, name in names.items():
            if column in zeroes:
                result[name] = pd.to_numeric(result[name], errors="coerce").fillna(0.0)
            added.append(name)
    return result.drop(columns=["_e23_session"]), added


def add_path_summaries(
    frame: pd.DataFrame,
    *,
    source: str,
    ordered_columns: list[str],
    prefix: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Compact summaries over columns ordered from oldest session to J."""
    result = frame.copy()
    values = result[ordered_columns].apply(pd.to_numeric, errors="coerce")
    x = np.arange(len(ordered_columns), dtype=float)
    centered = x - x.mean()
    valid_count = values.notna().sum(axis=1)
    names = {
        f"{prefix}_{source}_mean": values.mean(axis=1),
        f"{prefix}_{source}_std": values.std(axis=1, ddof=0),
        f"{prefix}_{source}_sum": values.sum(axis=1, min_count=1),
        f"{prefix}_{source}_delta": values.iloc[:, -1] - values.iloc[:, 0],
        f"{prefix}_{source}_slope": (
            values.sub(values.mean(axis=1), axis=0).mul(centered, axis=1).sum(axis=1)
            / float(np.square(centered).sum())
        ).where(valid_count.eq(len(ordered_columns))),
    }
    for name, series in names.items():
        result[name] = series
    return result, list(names)


def load_sentiment_daily(
    engine: Any, symbols: list[str], start_date: str, end_date: str,
) -> pd.DataFrame:
    """Load PIT-aligned FinBERT observations and aggregate each effective session."""
    query = text(
        """
        SELECT nts.symbol, nr.effective_trade_date AS date,
               nts.sentiment_net_score, nts.sentiment_label
        FROM news_ticker_sentiment nts
        JOIN news_raw nr ON nr.article_id = nts.article_id
        WHERE nts.symbol IN :symbols
          AND nr.effective_trade_date BETWEEN :start_date AND :end_date
        """
    ).bindparams(bindparam("symbols", expanding=True))
    parts: list[pd.DataFrame] = []
    with engine.connect() as connection:
        for offset in range(0, len(symbols), 500):
            part = pd.read_sql(query, connection, params={
                "symbols": symbols[offset:offset + 500],
                "start_date": start_date, "end_date": end_date,
            })
            if not part.empty:
                parts.append(part)
    columns = [
        "symbol", "date", "sentiment_net_sum", "sentiment_net_mean",
        "sentiment_article_count", "sentiment_pos_ratio", "sentiment_neg_ratio",
        "sentiment_has_news",
    ]
    if not parts:
        return pd.DataFrame(columns=columns)
    raw = pd.concat(parts, ignore_index=True)
    raw["symbol"] = raw["symbol"].astype(str).str.upper()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
    raw["sentiment_net_score"] = pd.to_numeric(raw["sentiment_net_score"], errors="coerce")
    raw = raw.dropna(subset=["symbol", "date", "sentiment_net_score"])
    daily = raw.groupby(["symbol", "date"], sort=False).agg(
        sentiment_net_sum=("sentiment_net_score", "sum"),
        sentiment_net_mean=("sentiment_net_score", "mean"),
        sentiment_article_count=("sentiment_net_score", "size"),
        sentiment_positive_count=("sentiment_label", lambda values: values.eq("positive").sum()),
        sentiment_negative_count=("sentiment_label", lambda values: values.eq("negative").sum()),
    ).reset_index()
    denominator = daily["sentiment_article_count"].replace(0, np.nan)
    daily["sentiment_pos_ratio"] = daily.pop("sentiment_positive_count") / denominator
    daily["sentiment_neg_ratio"] = daily.pop("sentiment_negative_count") / denominator
    daily["sentiment_has_news"] = 1.0
    return daily[columns]


def add_sentiment_summaries(
    frame: pd.DataFrame, daily_columns: list[str], max_lag: int,
) -> tuple[pd.DataFrame, list[str]]:
    result = frame.copy()
    added: list[str] = []
    for source in daily_columns:
        ordered = [f"sent_{source}_lag{lag}" for lag in range(max_lag, -1, -1)]
        result, names = add_path_summaries(
            result, source=source, ordered_columns=ordered, prefix="sent_path")
        added.extend(names)
    count_columns = [f"sent_sentiment_article_count_lag{lag}" for lag in range(max_lag, -1, -1)]
    score_columns = [f"sent_sentiment_net_mean_lag{lag}" for lag in range(max_lag, -1, -1)]
    has_columns = [f"sent_sentiment_has_news_lag{lag}" for lag in range(max_lag, -1, -1)]
    result["sent_path_active_sessions"] = result[has_columns].sum(axis=1)
    result["sent_path_total_articles"] = result[count_columns].sum(axis=1)
    result["sent_path_latest_surprise"] = result[score_columns[-1]] - result[score_columns[:-1]].mean(axis=1)
    added.extend(["sent_path_active_sessions", "sent_path_total_articles", "sent_path_latest_surprise"])
    return result, added


def _date_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.groupby("date")["date"].transform("size").astype(float)
    weights = 1.0 / counts
    return (weights / weights.mean()).to_numpy(float)


def _prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    return frame[features].apply(pd.to_numeric, errors="coerce").replace(
        [np.inf, -np.inf], np.nan)


def fit_model(
    name: str, train: pd.DataFrame, valid: pd.DataFrame, features: list[str],
    *, threads: int,
) -> tuple[Any, int | None]:
    x_train, x_valid = _prepare(train, features), _prepare(valid, features)
    y_train, y_valid = train[TARGET].astype(int), valid[TARGET].astype(int)
    weights = _date_weights(train)
    if name == "logistic":
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        model = Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, random_state=42, n_jobs=threads)),
        ])
        model.fit(x_train, y_train, model__sample_weight=weights)
        return model, None
    if name == "lightgbm":
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            objective="binary", n_estimators=500, learning_rate=0.03,
            max_depth=6, num_leaves=31, min_child_samples=100,
            subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1,
            reg_lambda=0.1, random_state=42, n_jobs=threads, verbosity=-1,
        )
        model.fit(
            x_train, y_train, sample_weight=weights,
            eval_set=[(x_valid, y_valid)], eval_metric="auc",
            callbacks=[lgb.early_stopping(30, verbose=False)],
        )
        return model, int(model.best_iteration_ or 500)
    if name == "catboost":
        from catboost import CatBoostClassifier
        model = CatBoostClassifier(
            loss_function="Logloss", eval_metric="AUC", iterations=500,
            depth=6, learning_rate=0.03, l2_leaf_reg=5.0,
            random_seed=42, allow_writing_files=False, verbose=False,
            thread_count=threads,
        )
        model.fit(
            x_train, y_train, sample_weight=weights,
            eval_set=(x_valid, y_valid), early_stopping_rounds=30,
            use_best_model=True,
        )
        return model, max(1, int(model.get_best_iteration()) + 1)
    raise ValueError(f"Unknown E23 model: {name}")


def predict_probability(model: Any, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.asarray(model.predict_proba(_prepare(frame, features))[:, 1], dtype=float)


def _average_precision(labels: pd.Series, scores: pd.Series) -> float | None:
    from sklearn.metrics import average_precision_score
    valid = labels.notna() & scores.notna()
    if valid.sum() < 2 or labels[valid].nunique() < 2:
        return None
    return float(average_precision_score(labels[valid].astype(int), scores[valid]))


def _tail(frame: pd.DataFrame, score: str, fraction: float) -> pd.DataFrame:
    parts = []
    for _, group in frame.groupby("date", sort=False):
        usable = group.dropna(subset=[score])
        if not usable.empty:
            parts.append(usable.nlargest(max(1, math.ceil(len(usable) * fraction)), score))
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[:0].copy()


def _selection(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"rows": 0, "precision_d10": None, "mean_return": None,
                "median_return": None, "hit_rate": None, "return_ge_3pct_rate": None}
    returns = pd.to_numeric(frame["future_return"], errors="coerce")
    return {
        "rows": int(len(frame)), "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "precision_d10": float(frame[TARGET].mean()),
        "mean_return": float(returns.mean()), "median_return": float(returns.median()),
        "hit_rate": float(returns.gt(0).mean()),
        "return_ge_3pct_rate": float(returns.ge(0.03).mean()),
    }


def evaluate(frame: pd.DataFrame, fractions: list[float]) -> dict[str, Any]:
    work = frame.dropna(subset=[TARGET, RAW_SCORE, CAL_SCORE, "future_return"]).copy()
    prevalence = float(work[TARGET].mean())
    result: dict[str, Any] = {
        "rows": int(len(work)), "dates": int(work["date"].nunique()),
        "prevalence_d10": prevalence,
        "pool_mean_return": float(work["future_return"].mean()),
        "auc": roc_auc(work[TARGET].to_numpy(), work[RAW_SCORE].to_numpy()),
        "average_precision": _average_precision(work[TARGET], work[RAW_SCORE]),
        "brier_raw": float(np.mean(np.square(work[RAW_SCORE] - work[TARGET]))),
        "brier_calibrated": float(np.mean(np.square(work[CAL_SCORE] - work[TARGET]))),
        "selections": {},
    }
    for fraction in fractions:
        model = _selection(_tail(work, RAW_SCORE, fraction))
        oracle = _selection(_tail(work, ORACLE_GATE_SCORE_COL, fraction))
        pool_metrics = _selection(work)
        model["precision_lift_vs_pool"] = model["precision_d10"] - prevalence
        model["return_lift_vs_pool"] = model["mean_return"] - result["pool_mean_return"]
        result["selections"][f"top_{int(round(fraction * 100)):02d}_pct"] = {
            "model": model, "oracle_amplitude": oracle, "pool": pool_metrics,
        }
    semesters = {}
    semester_key = work["date"].dt.year.astype(str) + "H" + (
        ((work["date"].dt.month - 1) // 6) + 1).astype(str)
    for semester, group in work.groupby(semester_key):
        metrics = _selection(_tail(group, RAW_SCORE, 0.10))
        metrics["return_lift_vs_pool"] = metrics["mean_return"] - float(group["future_return"].mean())
        metrics["precision_lift_vs_pool"] = metrics["precision_d10"] - float(group[TARGET].mean())
        semesters[str(semester)] = metrics
    result["semesters"] = semesters
    return result


def latest_fold_specs(dataset: pd.DataFrame, wf: dict[str, Any], horizon: int) -> list[dict[str, Any]]:
    if wf.get("fold_selection") != "latest":
        raise ValueError("E23 requires latest folds")
    specs = build_folds_adaptive(
        dataset, min_train_dates=int(wf["min_train_dates"]),
        val_dates=int(wf["val_dates"]), test_dates=int(wf["test_dates"]),
        step_dates=int(wf["step_dates"]), max_splits=10_000,
        forecast_horizon=horizon, materialize=False,
    )
    return specs[-int(wf["max_splits"]):]


def _split(dataset: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(dataset["date"])
    guards = pd.to_datetime(dataset[GUARD_COL])
    val_start, test_start = pd.Timestamp(spec["val_start"]), pd.Timestamp(spec["t_start"])
    train = dataset[dates.isin(spec["train_dates"]) & guards.lt(val_start)]
    valid = dataset[dates.isin(spec["val_dates"]) & guards.lt(test_start)]
    test = dataset[dates.isin(spec["test_dates"])]
    return train, valid, test


def train_variant(
    dataset: pd.DataFrame, features: list[str], specs: list[dict[str, Any]],
    *, model_name: str, fractions: list[float], threads: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from modelFactory.shared_directional import apply_platt, fit_non_inverting_platt

    pieces, folds = [], []
    for index, spec in enumerate(specs):
        train, valid, test = _split(dataset, spec)
        if any(part.empty or part[TARGET].nunique() < 2 for part in (train, valid, test)):
            LOGGER.warning("E23 %s fold=%d skipped: target classes", model_name, index)
            continue
        model, iterations = fit_model(model_name, train, valid, features, threads=threads)
        valid_raw = predict_probability(model, valid, features)
        calibrator, calibration = fit_non_inverting_platt(
            valid_raw, valid[TARGET].astype(int).to_numpy(), max_iter=100)
        test_raw = predict_probability(model, test, features)
        scored = test[[
            "date", "symbol", "future_return", "oracle_decile", TARGET,
            ORACLE_GATE_SCORE_COL,
        ]].copy()
        scored[RAW_SCORE] = test_raw
        scored[CAL_SCORE] = apply_platt(calibrator, test_raw)
        scored["fold_index"] = index
        pieces.append(scored)
        metrics = evaluate(scored, fractions)
        top10 = metrics["selections"]["top_10_pct"]["model"]
        folds.append({
            "fold_index": index, "test_start": spec["t_start"], "test_end": spec["t_end"],
            "train_rows": int(len(train)), "valid_rows": int(len(valid)),
            "auc": metrics["auc"], "average_precision": metrics["average_precision"],
            "top10_precision": top10["precision_d10"],
            "top10_precision_lift_vs_pool": top10["precision_lift_vs_pool"],
            "top10_mean_return": top10["mean_return"],
            "top10_return_lift_vs_pool": top10["return_lift_vs_pool"],
            "iterations": iterations, "calibration": calibration,
        })
        LOGGER.info(
            "E23 model=%s fold=%d auc=%.4f ap=%.4f p10_lift=%+.4f ret_lift=%+.4f",
            model_name, index, metrics["auc"], metrics["average_precision"],
            top10["precision_lift_vs_pool"], top10["return_lift_vs_pool"],
        )
    if not pieces:
        raise ValueError(f"No valid E23 folds for {model_name}")
    oos = pd.concat(pieces, ignore_index=True)
    return oos, {"overall": evaluate(oos, fractions), "folds": folds}


def absolute_gates(result: dict[str, Any], gates: dict[str, float]) -> dict[str, Any]:
    overall = result["overall"]
    top10 = overall["selections"]["top_10_pct"]["model"]
    fold_lifts = [row["top10_return_lift_vs_pool"] for row in result["folds"]]
    semesters = [row["return_lift_vs_pool"] for row in overall["semesters"].values()]
    checks = {
        "auc": overall["auc"] >= gates["auc_min"],
        "average_precision": overall["average_precision"] - overall["prevalence_d10"]
            >= gates["average_precision_lift_vs_prevalence_min"],
        "top10_precision": top10["precision_lift_vs_pool"]
            >= gates["top10_precision_lift_vs_pool_min"],
        "top10_return": top10["return_lift_vs_pool"]
            >= gates["top10_return_lift_vs_pool_min"],
        "fold_stability": np.mean(np.asarray(fold_lifts) > 0)
            >= gates["positive_top10_return_lift_fold_rate_min"],
        "semester_safety": bool(semesters) and min(semesters)
            >= gates["worst_semester_top10_return_lift_min"],
    }
    return {"checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def incremental_gates(
    result: dict[str, Any], baseline: dict[str, Any], gates: dict[str, float],
) -> dict[str, Any]:
    current, base = result["overall"], baseline["overall"]
    current_top = current["selections"]["top_10_pct"]["model"]
    base_top = base["selections"]["top_10_pct"]["model"]
    base_folds = {row["test_start"]: row for row in baseline["folds"]}
    fold_deltas = [
        row["top10_return_lift_vs_pool"]
        - base_folds[row["test_start"]]["top10_return_lift_vs_pool"]
        for row in result["folds"] if row["test_start"] in base_folds
    ]
    metrics = {
        "auc_delta": current["auc"] - base["auc"],
        "average_precision_delta": current["average_precision"] - base["average_precision"],
        "top10_precision_delta": current_top["precision_d10"] - base_top["precision_d10"],
        "top10_return_delta": current_top["mean_return"] - base_top["mean_return"],
        "positive_top10_return_delta_fold_rate": float(np.mean(np.asarray(fold_deltas) > 0)),
    }
    checks = {key: metrics[key] >= gates[f"{key}_min"] for key in metrics}
    return {**metrics, "checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"}


def run(args: argparse.Namespace) -> Path:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if int(config["horizon"]) != args.horizon:
        raise ValueError("E23 config/CLI horizon mismatch")
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, args.batch_id, args.horizon)
    if args.max_symbols:
        symbols = symbols[:args.max_symbols]
    if not symbols:
        raise ValueError("Empty E23 Oracle universe")
    profile = load_profile(Path(args.state_profile or config["state_profile"]))
    # Le panel dense des lags ne doit pas être conditionné par la disponibilité
    # ou la qualité d'un label futur à J-k. Les targets restent jointes lorsque
    # disponibles, puis le gate OOF et le filtre de labels définissent le pool.
    full, state_features = build_oracle_dataset(
        engine, args.batch_id, symbols, start_date=args.start_date, end_date=args.end_date,
        horizon=args.horizon, require_global_rank=False, need_targets=False,
        feature_whitelist=profile["feature_columns"],
        generator_options=profile["generator_options"],
    )
    if full.empty:
        raise ValueError("Empty E23 feature panel")
    full["date"] = pd.to_datetime(full["date"]).dt.normalize()
    full["symbol"] = full["symbol"].astype(str).str.upper()
    sessions = _session_map(full["date"])
    price_sources = list(config["price_source_columns"])
    missing_price = sorted(set(price_sources).difference(full.columns))
    if missing_price:
        raise ValueError(f"Missing E23 price sources: {missing_price}")
    history = full[["date", "symbol", *price_sources]].copy()
    gate = _load_gate(
        Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet",
        float(config["pool_pct"]),
    )
    eligible = gate[gate["shared_oracle_eligible"]][
        ["date", "symbol", ORACLE_GATE_SCORE_COL]]
    pool = full.merge(eligible, on=["date", "symbol"], how="inner", validate="one_to_one")
    del full
    pool = attach_d10_one_vs_rest(pool).dropna(subset=[TARGET, "future_return", GUARD_COL])

    pool, price_lags = attach_exact_session_lags(
        pool, history, price_sources, max_lag=int(config["price_lag_sessions"]),
        prefix="price", session_map=sessions, include_current=False)
    del history
    price_summaries: list[str] = []
    price_max_lag = int(config["price_lag_sessions"])
    for source in price_sources:
        ordered = [f"price_{source}_lag{lag}" for lag in range(price_max_lag, 0, -1)] + [source]
        pool, names = add_path_summaries(
            pool, source=source, ordered_columns=ordered, prefix="price_path")
        price_summaries.extend(names)

    padded_start = str((pd.Timestamp(args.start_date) - pd.Timedelta(days=30)).date())
    sentiment = load_sentiment_daily(engine, symbols, padded_start, args.end_date)
    sentiment_columns = list(config["sentiment_daily_columns"])
    pool, sentiment_lags = attach_exact_session_lags(
        pool, sentiment, sentiment_columns,
        max_lag=int(config["sentiment_lag_sessions"]), prefix="sent",
        session_map=sessions, include_current=True,
        fill_zero_columns=set(sentiment_columns))
    pool, sentiment_summaries = add_sentiment_summaries(
        pool, sentiment_columns, int(config["sentiment_lag_sessions"]))
    sentiment_features = sentiment_lags + sentiment_summaries
    price_features = price_lags + price_summaries
    variants = {
        "E23_A_STATE_J": state_features,
        "E23_B_PRICE_PATH": state_features + price_features,
        "E23_C_SENTIMENT_PATH": state_features + sentiment_features,
        "E23_D_PRICE_SENTIMENT": state_features + price_features + sentiment_features,
    }
    wf = dict(config["walk_forward"])
    if args.max_folds:
        wf["max_splits"] = args.max_folds
    specs = latest_fold_specs(pool, wf, args.horizon)
    if not specs:
        raise ValueError("No E23 walk-forward folds")
    output = args.output or Path("artifacts/research/oracle_d10_trajectory") / (
        datetime.now(UTC).strftime("e23-d10-%Y%m%d%H%M%S"))
    output.mkdir(parents=True, exist_ok=False)
    models = [item.strip() for item in (args.models.split(",") if args.models else config["models"])]
    allowed_models = {"logistic", "lightgbm", "catboost"}
    if not models or not set(models).issubset(allowed_models):
        raise ValueError(f"Invalid E23 models: {models}")
    fractions = [float(value) for value in config["selection_fractions"]]
    results: dict[str, Any] = {}
    for variant, features in variants.items():
        results[variant] = {}
        for model_name in models:
            LOGGER.info("E23 variant=%s model=%s features=%d", variant, model_name, len(features))
            oos, metrics = train_variant(
                pool, features, specs, model_name=model_name,
                fractions=fractions, threads=args.threads)
            oos.to_parquet(output / f"{variant.lower()}_{model_name}_oos.parquet", index=False)
            metrics["feature_count"] = len(features)
            metrics["absolute_gates"] = absolute_gates(metrics, config["absolute_gates"])
            results[variant][model_name] = metrics

    comparisons: dict[str, Any] = {}
    for model_name in models:
        baseline = results["E23_A_STATE_J"][model_name]
        comparisons[model_name] = {
            variant: incremental_gates(
                results[variant][model_name], baseline,
                config["incremental_gates_vs_state_j"])
            for variant in ("E23_B_PRICE_PATH", "E23_C_SENTIMENT_PATH", "E23_D_PRICE_SENTIMENT")
        }
    has_news = [
        f"sent_sentiment_has_news_lag{lag}"
        for lag in range(int(config["sentiment_lag_sessions"]), -1, -1)
    ]
    report = {
        "experiment": config["experiment"], "status": "COMPLETED_RESEARCH_ONLY",
        "batch_id": args.batch_id, "horizon": args.horizon,
        "period": [args.start_date, args.end_date], "symbols_requested": len(symbols),
        "pool": {
            "rows": int(len(pool)), "dates": int(pool["date"].nunique()),
            "symbols": int(pool["symbol"].nunique()), "d10_prevalence": float(pool[TARGET].mean()),
            "first_date": str(pool["date"].min().date()), "last_date": str(pool["date"].max().date()),
        },
        "sentiment_coverage": {
            "daily_source_rows": int(len(sentiment)),
            "symbols_with_news": int(sentiment["symbol"].nunique()) if len(sentiment) else 0,
            "pool_rows_with_news_j_minus_10_to_j": float(pool[has_news].max(axis=1).mean()),
            "pool_rows_with_news_at_j": float(pool["sent_sentiment_has_news_lag0"].mean()),
        },
        "fold_coverage": {
            "folds": len(specs), "first_test_start": specs[0]["t_start"],
            "last_test_end": specs[-1]["t_end"], "selection": "latest",
        },
        "feature_contract": {"state": state_features, "price_path": price_features,
                             "sentiment_path": sentiment_features},
        "config": config, "results": results, "comparisons_vs_state_j": comparisons,
        "serving_changed": False, "database_writes": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"E23 terminé: {output}")
    for model_name, values in comparisons.items():
        print(model_name, {variant: value["status"] for variant, value in values.items()})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--state-profile")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--models", help="comma-separated logistic,lightgbm,catboost")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--max-folds", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.horizon != 20:
        parser.error("E23 primary contract is frozen at H20")
    if args.start_date > args.end_date:
        parser.error("invalid date window")
    run(args)


if __name__ == "__main__":
    main()
