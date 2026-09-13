"""E19-B: PIT fundamental alpha library with OOS walk-forward evaluation.

Research only. The module reads bars, metadata and the E19-A2 fundamental
contract, then writes isolated artifacts. It never changes serving state.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.directional_alpha_book import load_sector_reference
from modelFactory.fundamental_features import load_fundamentals_from_db
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean
from modelFactory.oracle_tradable_pit_reconstruction import (
    classify_instruments,
    load_instrument_reference,
)

LOGGER = logging.getLogger(__name__)

FAMILY_COMPONENTS: dict[str, tuple[tuple[str, int], ...]] = {
    "quality": (
        ("roe", 1), ("roa", 1), ("net_margin", 1),
        ("operating_margin", 1), ("gross_margin", 1), ("current_ratio", 1),
    ),
    "value": (
        ("pe_ratio", -1), ("pb_ratio", -1),
        ("ps_ratio", -1), ("ev_to_ebitda", -1),
    ),
    "growth": (("eps_growth_yoy", 1), ("revenue_growth_yoy", 1)),
    "leverage": (("debt_to_equity", -1),),
    "improvement": (
        ("delta_roe", 1), ("delta_roa", 1), ("delta_net_margin", 1),
        ("delta_operating_margin", 1), ("delta_eps_growth_yoy", 1),
        ("delta_revenue_growth_yoy", 1),
    ),
}
FAMILY_MIN_COMPONENTS = {
    "quality": 3,
    "value": 2,
    "growth": 1,
    "leverage": 1,
    "improvement": 2,
}
ALPHAS = (*FAMILY_COMPONENTS.keys(), "fundamental_composite")
VIEWS = ("raw", "sector_neutral", "sector_size_neutral")
PRIMARY_ALPHA = "fundamental_composite"
PRIMARY_VIEW = "sector_size_neutral"


@dataclass(frozen=True, slots=True)
class E19BConfig:
    start_date: str = "2018-07-01"
    end_date: str = "2025-12-31"
    horizons: tuple[int, ...] = (20, 60, 120)
    primary_horizon: int = 60
    confirmation_horizon: int = 120
    max_fundamental_age_days: int = 180
    min_history_sessions: int = 252
    min_close: float = 10.0
    min_avg_volume_20d: float = 50_000.0
    min_adv_usd_20d: float = 10_000_000.0
    min_cross_section: int = 30
    min_sector_members: int = 5
    min_global_families: int = 3
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    tail_pct: float = 0.20
    min_leg_symbols: int = 10
    rebalance_sessions: int = 20
    round_trip_cost_bps: float = 6.0
    wf_min_train_size: int = 504
    wf_test_size: int = 252
    wf_step_size: int = 252
    wf_max_splits: int = 8
    wf_min_partial_test_size: int = 126
    bootstrap_samples: int = 2_000
    bootstrap_seed: int = 20260919
    confirmation_start: str = "2023-01-01"

    def __post_init__(self) -> None:
        if self.primary_horizon not in self.horizons:
            raise ValueError("primary_horizon absent de horizons")
        if self.confirmation_horizon not in self.horizons:
            raise ValueError("confirmation_horizon absent de horizons")
        if not 0 < self.tail_pct <= 0.5:
            raise ValueError("tail_pct doit être dans ]0, 0.5]")
        if not 0 <= self.winsor_lower < self.winsor_upper <= 1:
            raise ValueError("bornes de winsorisation invalides")

    @property
    def round_trip_cost(self) -> float:
        return self.round_trip_cost_bps / 10_000.0


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def _cross_section_rank(
    values: pd.Series,
    dates: pd.Series,
    eligible: pd.Series,
    sign: int,
    config: E19BConfig,
) -> pd.Series:
    scoped = values.where(eligible)

    def rank_date(group: pd.Series) -> pd.Series:
        clean = group.dropna()
        if len(clean) < config.min_cross_section:
            return pd.Series(np.nan, index=group.index, dtype=float)
        low, high = clean.quantile([config.winsor_lower, config.winsor_upper])
        clipped = group.clip(lower=low, upper=high)
        return sign * (2.0 * clipped.rank(pct=True, method="average") - 1.0)

    return scoped.groupby(dates, group_keys=False).apply(rank_date).reindex(values.index)


def _prepare_fundamental_snapshots(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return raw
    frame = raw.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["available_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["source_trade_date"] = pd.to_datetime(
        frame.get("source_trade_date"), errors="coerce"
    ).dt.normalize()
    source = frame.get("source", pd.Series("", index=frame.index)).astype(str).str.upper()
    frame = frame[source.eq("SEC_EDGAR")].sort_values(["symbol", "available_date"])
    delta_columns = (
        "roe", "roa", "net_margin", "operating_margin",
        "eps_growth_yoy", "revenue_growth_yoy",
    )
    for column in delta_columns:
        values = _numeric(frame, column)
        frame[f"delta_{column}"] = values.groupby(frame["symbol"]).diff()
    return frame.drop_duplicates(["symbol", "available_date"], keep="last")


def build_family_scores(panel: pd.DataFrame, config: E19BConfig) -> pd.DataFrame:
    """Build fixed-sign family ranks without imputing absent observations."""
    result = panel.copy()
    eligible = result["market_eligible"] & result["fundamental_fresh"]
    dates = result["date"]
    for family, components in FAMILY_COMPONENTS.items():
        component_scores: list[str] = []
        for component, sign in components:
            values = _numeric(result, component)
            if family == "value" or component == "debt_to_equity":
                values = values.where(values.gt(0))
            name = f"component_{component}"
            result[name] = _cross_section_rank(values, dates, eligible, sign, config)
            component_scores.append(name)
        observed = result[component_scores].notna().sum(axis=1)
        result[f"score_{family}__raw"] = result[component_scores].mean(axis=1).where(
            observed.ge(FAMILY_MIN_COMPONENTS[family])
        )
    family_raw = [f"score_{family}__raw" for family in FAMILY_COMPONENTS]
    family_count = result[family_raw].notna().sum(axis=1)
    result[f"score_{PRIMARY_ALPHA}__raw"] = result[family_raw].mean(axis=1).where(
        family_count.ge(config.min_global_families)
    )
    return result


def _standardize(values: pd.Series, dates: pd.Series, minimum: int) -> pd.Series:
    def one(group: pd.Series) -> pd.Series:
        if group.notna().sum() < minimum:
            return pd.Series(np.nan, index=group.index, dtype=float)
        centered = group - group.mean()
        scale = centered.std(ddof=0)
        if not np.isfinite(scale) or scale <= 0:
            return pd.Series(np.nan, index=group.index, dtype=float)
        return centered / scale
    return values.groupby(dates, group_keys=False).apply(one).reindex(values.index)


def add_neutralized_views(panel: pd.DataFrame, config: E19BConfig) -> pd.DataFrame:
    """Remove sector, then sector plus PIT size exposure for every alpha."""
    result = panel.copy()
    for alpha in ALPHAS:
        raw_col = f"score_{alpha}__raw"
        sector_counts = result.groupby(["date", "sector"])[raw_col].transform("count")
        sector_mean = result.groupby(["date", "sector"])[raw_col].transform("mean")
        sector_residual = (result[raw_col] - sector_mean).where(
            sector_counts.ge(config.min_sector_members)
        )
        result[f"score_{alpha}__sector_neutral"] = _standardize(
            sector_residual, result["date"], config.min_cross_section
        )

        output = pd.Series(np.nan, index=result.index, dtype=float)
        required = result[[raw_col, "market_cap_log", "sector"]].notna().all(axis=1)
        for _date, index in result[required].groupby("date", sort=False).groups.items():
            if len(index) < config.min_cross_section:
                continue
            group = result.loc[index]
            sector = pd.get_dummies(group["sector"].astype(str), drop_first=True, dtype=float)
            size = group["market_cap_log"].astype(float)
            size = (size - size.mean()) / (size.std(ddof=0) or 1.0)
            design = np.column_stack([
                np.ones(len(group), dtype=float), size.to_numpy(dtype=float),
                sector.to_numpy(dtype=float),
            ])
            y = group[raw_col].to_numpy(dtype=float)
            try:
                fitted = design @ np.linalg.lstsq(design, y, rcond=None)[0]
                output.loc[index] = y - fitted
            except np.linalg.LinAlgError:
                continue
        # Standardisation affine par date: elle conserve l'orthogonalité des
        # résidus à la taille et aux indicatrices secteur. Un reranking ici
        # réintroduirait mécaniquement des expositions après la régression.
        result[f"score_{alpha}__sector_size_neutral"] = _standardize(
            output, result["date"], config.min_cross_section
        )
    return result


def build_walk_forward_folds(dates: Iterable[pd.Timestamp], config: E19BConfig) -> pd.DataFrame:
    unique = pd.DatetimeIndex(sorted(pd.to_datetime(pd.Series(list(dates))).dropna().unique()))
    rows: list[dict[str, Any]] = []
    cursor = config.wf_min_train_size
    fold = 0
    while cursor < len(unique) and fold < config.wf_max_splits:
        test = unique[cursor : cursor + config.wf_test_size]
        if len(test) < config.wf_min_partial_test_size:
            break
        rows.append({
            "fold": fold,
            "train_start": unique[0],
            "train_end": unique[cursor - 1],
            "test_start": test[0],
            "test_end": test[-1],
            "test_sessions": len(test),
        })
        fold += 1
        cursor += config.wf_step_size
    return pd.DataFrame(rows)


def assign_oos_folds(panel: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    result["fold"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    for row in folds.itertuples(index=False):
        mask = result["date"].between(row.test_start, row.test_end)
        result.loc[mask, "fold"] = int(row.fold)
    return result


def _safe_spearman(group: pd.DataFrame, score: str, target: str) -> float:
    valid = group[[score, target]].dropna()
    if len(valid) < 20 or valid[score].nunique() < 2 or valid[target].nunique() < 2:
        return float("nan")
    return float(spearmanr(valid[score], valid[target]).statistic)


def _bootstrap(values: pd.Series, config: E19BConfig, horizon: int, salt: int) -> tuple[float, float]:
    clean = values.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if clean.empty:
        return float("nan"), float("nan")
    rolling = RollingConfig(
        bootstrap_samples=config.bootstrap_samples,
        bootstrap_block_sessions=max(2, math.ceil(horizon / config.rebalance_sessions)),
        bootstrap_seed=config.bootstrap_seed + horizon + salt,
    )
    return block_bootstrap_mean(clean, rolling)


def evaluate_alpha(
    panel: pd.DataFrame,
    alpha: str,
    view: str,
    horizon: int,
    config: E19BConfig,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score = f"score_{alpha}__{view}"
    excess = f"future_excess_h{horizon}"
    raw_return = f"future_return_h{horizon}"
    scope = panel[
        panel["fold"].notna() & panel["market_eligible"]
        & panel[score].notna() & panel[excess].notna()
    ].copy()
    daily_ic = scope.groupby("date", sort=True).apply(
        lambda group: _safe_spearman(group, score, excess), include_groups=False
    ).rename("ic").dropna().reset_index()
    date_to_fold = scope.drop_duplicates("date").set_index("date")["fold"]
    daily_ic["fold"] = daily_ic["date"].map(date_to_fold).astype("Int64")

    oos_dates = sorted(scope["date"].unique())
    rebalance_dates = {pd.Timestamp(value) for value in oos_dates[:: config.rebalance_sessions]}
    rows: list[dict[str, Any]] = []
    for date, group in scope[scope["date"].isin(rebalance_dates)].groupby("date", sort=True):
        ordered = group.sort_values([score, "symbol"])
        leg_size = max(config.min_leg_symbols, int(math.floor(len(ordered) * config.tail_pct)))
        if len(ordered) < 2 * leg_size:
            continue
        short = ordered.head(leg_size)
        long = ordered.tail(leg_size)
        long_net = float(long[raw_return].mean() - config.round_trip_cost)
        short_net = float(-short[raw_return].mean() - config.round_trip_cost)
        rows.append({
            "date": pd.Timestamp(date), "fold": int(group["fold"].iloc[0]),
            "alpha": alpha, "view": view, "horizon": horizon,
            "universe": len(ordered), "leg_size": leg_size,
            "long_return_net": long_net, "short_return_net": short_net,
            "long_short_return_net": 0.5 * (long_net + short_net),
        })
    cohorts = pd.DataFrame(rows)
    if cohorts.empty:
        return {"alpha": alpha, "view": view, "horizon": horizon, "cohorts": 0}, daily_ic, cohorts, pd.DataFrame()
    cohorts["semester"] = cohorts["date"].dt.year.astype(str) + "H" + np.where(
        cohorts["date"].dt.month.le(6), "1", "2"
    )
    fold_metrics = cohorts.groupby("fold").agg(
        cohorts=("date", "count"),
        long_mean_net=("long_return_net", "mean"),
        short_mean_net=("short_return_net", "mean"),
        long_short_mean_net=("long_short_return_net", "mean"),
    ).reset_index()
    fold_ic = daily_ic.groupby("fold", as_index=False)["ic"].mean().rename(columns={"ic": "ic_mean"})
    fold_metrics = fold_metrics.merge(fold_ic, on="fold", how="left")
    semester = cohorts.groupby("semester")["long_short_return_net"].agg(["count", "mean", "sum"])
    positive_sum = semester["sum"].clip(lower=0).sum()
    concentration = float(semester["sum"].clip(lower=0).max() / positive_sum) if positive_sum > 0 else 1.0
    ic_ci = _bootstrap(daily_ic["ic"], config, horizon, 1)
    long_ci = _bootstrap(cohorts["long_return_net"], config, horizon, 2)
    short_ci = _bootstrap(cohorts["short_return_net"], config, horizon, 3)
    ls_ci = _bootstrap(cohorts["long_short_return_net"], config, horizon, 4)
    confirmation = cohorts[cohorts["date"].ge(pd.Timestamp(config.confirmation_start))]
    summary = {
        "alpha": alpha, "view": view, "horizon": horizon,
        "observations": int(len(scope)), "dates": int(scope["date"].nunique()),
        "daily_ic_mean": float(daily_ic["ic"].mean()),
        "daily_ic_median": float(daily_ic["ic"].median()),
        "daily_ic_ci95_low": ic_ci[0], "daily_ic_ci95_high": ic_ci[1],
        "cohorts": int(len(cohorts)), "mean_leg_size": float(cohorts["leg_size"].mean()),
        "long_mean_net": float(cohorts["long_return_net"].mean()),
        "long_ci95_low": long_ci[0], "long_ci95_high": long_ci[1],
        "short_mean_net": float(cohorts["short_return_net"].mean()),
        "short_ci95_low": short_ci[0], "short_ci95_high": short_ci[1],
        "long_short_mean_net": float(cohorts["long_short_return_net"].mean()),
        "long_short_ci95_low": ls_ci[0], "long_short_ci95_high": ls_ci[1],
        "positive_fold_ratio": float(fold_metrics["long_short_mean_net"].gt(0).mean()),
        "positive_long_fold_ratio": float(fold_metrics["long_mean_net"].gt(0).mean()),
        "positive_short_fold_ratio": float(fold_metrics["short_mean_net"].gt(0).mean()),
        "positive_semester_ratio": float(semester["mean"].gt(0).mean()),
        "positive_pnl_semester_concentration": concentration,
        "confirmation_cohorts": int(len(confirmation)),
        "confirmation_long_mean_net": float(confirmation["long_return_net"].mean()) if len(confirmation) else None,
        "confirmation_short_mean_net": float(confirmation["short_return_net"].mean()) if len(confirmation) else None,
        "confirmation_long_short_mean_net": float(confirmation["long_short_return_net"].mean()) if len(confirmation) else None,
        "semesters": semester.reset_index().to_dict(orient="records"),
    }
    return summary, daily_ic, cohorts, fold_metrics


def build_gates(results: dict[str, dict[str, Any]], config: E19BConfig) -> dict[str, Any]:
    primary = results[f"{PRIMARY_ALPHA}__{PRIMARY_VIEW}__h{config.primary_horizon}"]
    confirmation = results[f"{PRIMARY_ALPHA}__{PRIMARY_VIEW}__h{config.confirmation_horizon}"]
    long_gates = {
        "h60_long_positive": primary.get("long_mean_net", -np.inf) > 0,
        "h60_long_ci95_above_zero": primary.get("long_ci95_low", -np.inf) > 0,
        "h60_long_positive_folds_70pct": primary.get("positive_long_fold_ratio", 0) >= 0.70,
        "since_2023_long_positive": (primary.get("confirmation_long_mean_net") or -np.inf) > 0,
    }
    short_gates = {
        "h60_short_positive": primary.get("short_mean_net", -np.inf) > 0,
        "h60_short_ci95_above_zero": primary.get("short_ci95_low", -np.inf) > 0,
        "h60_short_positive_folds_70pct": primary.get("positive_short_fold_ratio", 0) >= 0.70,
        "since_2023_short_positive": (primary.get("confirmation_short_mean_net") or -np.inf) > 0,
    }
    long_short_gates = {
        "h60_ic_positive": primary.get("daily_ic_mean", -np.inf) > 0,
        "h60_ic_ci95_above_zero": primary.get("daily_ic_ci95_low", -np.inf) > 0,
        "h60_long_short_positive": primary.get("long_short_mean_net", -np.inf) > 0,
        "h60_long_short_ci95_above_zero": primary.get("long_short_ci95_low", -np.inf) > 0,
        "h60_positive_folds_70pct": primary.get("positive_fold_ratio", 0) >= 0.70,
        "h60_positive_semesters_70pct": primary.get("positive_semester_ratio", 0) >= 0.70,
        "since_2023_long_short_positive": (primary.get("confirmation_long_short_mean_net") or -np.inf) > 0,
        "h120_ic_positive": confirmation.get("daily_ic_mean", -np.inf) > 0,
        "h120_long_short_positive": confirmation.get("long_short_mean_net", -np.inf) > 0,
        "enough_h60_cohorts": primary.get("cohorts", 0) >= 50,
    }
    return {
        "long": long_gates, "short": short_gates, "long_short": long_short_gates,
        "go_long": all(long_gates.values()),
        "go_short": all(short_gates.values()),
        "go_long_short": all(long_short_gates.values()),
    }


def build_panel(engine: Any, symbols: list[str], config: E19BConfig) -> pd.DataFrame:
    history_start = pd.Timestamp(config.start_date) - pd.offsets.BDay(config.min_history_sessions + 30)
    label_end = pd.Timestamp(config.end_date) + pd.offsets.BDay(max(config.horizons) + 5)
    bars = load_universe_bars(engine, symbols, start_date=history_start.date(), end_date=label_end.date())
    benchmark = load_universe_bars(engine, ["SPY"], start_date=history_start.date(), end_date=label_end.date())
    sectors = load_sector_reference(engine, symbols)
    instruments = classify_instruments(load_instrument_reference(engine, symbols))
    raw_fundamentals = load_fundamentals_from_db(
        symbols, start_date=history_start, end_date=config.end_date, engine=engine
    )
    fundamentals = _prepare_fundamental_snapshots(raw_fundamentals)
    if fundamentals.empty:
        raise ValueError("Aucun fondamental SEC PIT disponible")

    frame = bars.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    raw_close = _numeric(frame, "close")
    adj_close = _numeric(frame, "adj_close").fillna(raw_close)
    adjustment = adj_close / raw_close.replace(0, np.nan)
    frame["px_close"] = adj_close
    frame["px_open"] = _numeric(frame, "open") * adjustment
    frame["volume_num"] = _numeric(frame, "volume")
    filled = frame.get("is_filled", pd.Series(False, index=frame.index)).fillna(False).astype(bool)
    frame["valid_bar"] = frame["px_close"].gt(0) & frame["px_open"].gt(0) & frame["volume_num"].gt(0) & ~filled
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    grouped = frame.groupby("symbol", sort=False)
    frame["history_sessions"] = grouped["valid_bar"].cumsum()
    valid_volume = frame["volume_num"].where(frame["valid_bar"])
    dollar_volume = (frame["px_close"] * frame["volume_num"]).where(frame["valid_bar"])
    frame["avg_volume_20d"] = valid_volume.groupby(frame["symbol"]).transform(lambda x: x.rolling(20, min_periods=20).mean())
    frame["adv_usd_20d"] = dollar_volume.groupby(frame["symbol"]).transform(lambda x: x.rolling(20, min_periods=20).mean())
    frame = frame.merge(sectors, on="symbol", how="left", validate="many_to_one")
    frame = frame.merge(instruments, on="symbol", how="left", validate="many_to_one")
    frame["sector"] = frame["sector"].fillna("UNKNOWN")
    frame["instrument_eligible"] = frame["instrument_eligible"].fillna(False).astype(bool)
    frame["market_eligible"] = (
        frame["valid_bar"] & frame["instrument_eligible"]
        & frame["history_sessions"].ge(config.min_history_sessions)
        & frame["px_close"].ge(config.min_close)
        & frame["avg_volume_20d"].ge(config.min_avg_volume_20d)
        & frame["adv_usd_20d"].ge(config.min_adv_usd_20d)
    )

    benchmark = benchmark.copy()
    benchmark["date"] = pd.to_datetime(benchmark["date"], errors="coerce").dt.normalize()
    bench_raw = _numeric(benchmark, "close")
    bench_adj = _numeric(benchmark, "adj_close").fillna(bench_raw)
    benchmark["benchmark_open"] = _numeric(benchmark, "open") * (bench_adj / bench_raw.replace(0, np.nan))
    benchmark = benchmark.drop_duplicates("date").sort_values("date")
    grouped = frame.groupby("symbol", sort=False)
    for horizon in config.horizons:
        entry = grouped["px_open"].shift(-1)
        exit_price = grouped["px_open"].shift(-(horizon + 1))
        future = (exit_price / entry - 1).where(entry.gt(0) & exit_price.gt(0)).where(lambda x: x.between(-0.95, 3.0))
        frame[f"future_return_h{horizon}"] = future
        benchmark[f"benchmark_future_return_h{horizon}"] = (
            benchmark["benchmark_open"].shift(-(horizon + 1)) / benchmark["benchmark_open"].shift(-1) - 1
        )
        mapping = benchmark.set_index("date")[f"benchmark_future_return_h{horizon}"]
        frame[f"future_excess_h{horizon}"] = future - frame["date"].map(mapping)

    left = frame.sort_values(["date", "symbol"])
    right = fundamentals.sort_values(["available_date", "symbol"])
    panel = pd.merge_asof(
        left, right, left_on="date", right_on="available_date", by="symbol",
        direction="backward", allow_exact_matches=True,
    ).sort_values(["symbol", "date"]).reset_index(drop=True)
    source_date = pd.to_datetime(panel["source_trade_date"], errors="coerce").dt.normalize()
    panel["fundamental_age_days"] = (panel["date"] - source_date).dt.days
    panel["fundamental_fresh"] = panel["fundamental_age_days"].between(0, config.max_fundamental_age_days)
    panel["market_cap_log"] = np.log10(_numeric(panel, "market_cap").where(lambda x: x.gt(0)))
    return add_neutralized_views(build_family_scores(panel, config), config)


def _neutrality_diagnostics(panel: pd.DataFrame) -> dict[str, Any]:
    score = f"score_{PRIMARY_ALPHA}__{PRIMARY_VIEW}"
    valid = panel[["date", "sector", "market_cap_log", score]].dropna()
    if valid.empty:
        return {}
    size_corr = valid.groupby("date").apply(
        lambda g: g[score].corr(g["market_cap_log"]) if len(g) >= 20 else np.nan,
        include_groups=False,
    ).dropna()
    sector_means = valid.groupby(["date", "sector"])[score].mean()
    return {
        "mean_absolute_daily_size_correlation": float(size_corr.abs().mean()),
        "p95_absolute_daily_size_correlation": float(size_corr.abs().quantile(0.95)),
        "mean_absolute_sector_score": float(sector_means.abs().mean()),
        "p95_absolute_sector_score": float(sector_means.abs().quantile(0.95)),
    }


def run(*, symbol_source: str, output_root: Path, config: E19BConfig) -> Path:
    symbols = sorted(set(load_universe_file_symbols(symbol_source)))
    if not symbols:
        raise ValueError(f"Univers vide: {symbol_source}")
    engine = get_sqlalchemy_engine()
    panel = build_panel(engine, symbols, config)
    study = panel[panel["date"].between(pd.Timestamp(config.start_date), pd.Timestamp(config.end_date))].copy()
    folds = build_walk_forward_folds(study.loc[study["market_eligible"], "date"], config)
    if folds.empty:
        raise ValueError("Aucun fold Walk-Forward E19-B valide")
    study = assign_oos_folds(study, folds)

    results: dict[str, dict[str, Any]] = {}
    daily_frames: list[pd.DataFrame] = []
    cohort_frames: list[pd.DataFrame] = []
    fold_frames: list[pd.DataFrame] = []
    for alpha in ALPHAS:
        for view in VIEWS:
            for horizon in config.horizons:
                summary, daily, cohorts, fold_metrics = evaluate_alpha(study, alpha, view, horizon, config)
                key = f"{alpha}__{view}__h{horizon}"
                results[key] = summary
                if not daily.empty:
                    daily_frames.append(daily.assign(alpha=alpha, view=view, horizon=horizon))
                if not cohorts.empty:
                    cohort_frames.append(cohorts)
                if not fold_metrics.empty:
                    fold_frames.append(fold_metrics.assign(alpha=alpha, view=view, horizon=horizon))
    gates = build_gates(results, config)
    verdicts = {
        "long": "GO_LONG" if gates["go_long"] else "NO_GO_LONG",
        "short": "GO_SHORT" if gates["go_short"] else "NO_GO_SHORT",
        "long_short": "GO_LONG_SHORT" if gates["go_long_short"] else "NO_GO_LONG_SHORT",
    }
    run_id = f"fundamental-alpha-book-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    keep = [
        "date", "symbol", "sector", "fold", "market_eligible", "fundamental_fresh",
        "fundamental_age_days", "market_cap_log",
        *(f"score_{alpha}__{view}" for alpha in ALPHAS for view in VIEWS),
        *(f"future_return_h{h}" for h in config.horizons),
        *(f"future_excess_h{h}" for h in config.horizons),
    ]
    study[keep].to_parquet(output / "alpha_panel.parquet", index=False)
    pd.concat(daily_frames, ignore_index=True).to_csv(output / "daily_ic.csv", index=False)
    pd.concat(cohort_frames, ignore_index=True).to_csv(output / "portfolio_cohorts.csv", index=False)
    pd.concat(fold_frames, ignore_index=True).to_csv(output / "fold_metrics.csv", index=False)
    folds.to_csv(output / "walk_forward_folds.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E19B_FUNDAMENTAL_ALPHA_BOOK",
        "status": "complete", "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "symbol_source": symbol_source, "symbols_requested": len(symbols),
        "config": asdict(config),
        "contract": {
            "fundamental_source": "SEC_EDGAR",
            "availability": "strictly after filing under E19-A2",
            "signal_time": "close J", "entry_exit": "adjusted open J+1 to J+H+1",
            "primary": f"{PRIMARY_ALPHA} {PRIMARY_VIEW} H{config.primary_horizon}",
            "confirmation": f"H{config.confirmation_horizon}",
            "portfolio": "equal-weight top/bottom 20%, 50/50 dollar-neutral",
            "costs": "6 bps round trip per leg; borrow fees unavailable",
            "survivorship_warning": "universe and metadata are current snapshots",
        },
        "population": {
            "panel_rows": len(study), "dates": int(study["date"].nunique()),
            "symbols": int(study["symbol"].nunique()),
            "eligible_rows": int(study["market_eligible"].sum()),
            "fresh_fundamental_rows": int((study["market_eligible"] & study["fundamental_fresh"]).sum()),
            "oos_rows": int(study["fold"].notna().sum()), "folds": len(folds),
        },
        "neutrality_diagnostics": _neutrality_diagnostics(study[study["fold"].notna()]),
        "results": results, "gates": gates, "verdicts": verdicts,
        "promotion_authorized": False,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LOGGER.info("E19-B terminé: %s verdicts=%s", output, verdicts)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol-source", default="universe-file:univers_filtred_equities.txt")
    parser.add_argument("--start-date", default="2018-07-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/fundamental_alpha_book"))
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        symbol_source=args.symbol_source, output_root=args.output_root,
        config=E19BConfig(start_date=args.start_date, end_date=args.end_date, bootstrap_samples=args.bootstrap_samples),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E19-B terminé: {output}")
    print(json.dumps(report["verdicts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
