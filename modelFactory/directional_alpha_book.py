"""E17: price-only directional alpha book, fully independent from Oracle.

The experiment evaluates fixed economic signals at H60 (primary) and H120
(confirmation).  It is research-only: no model, prediction table, backtest or
serving artifact is modified.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean
from modelFactory.oracle_tradable_pit_reconstruction import (
    classify_instruments,
    load_instrument_reference,
)

LOGGER = logging.getLogger(__name__)

BASE_ALPHA_COLUMNS = (
    "momentum_252_21",
    "momentum_120_10",
    "industry_relative_momentum",
    "residual_momentum_120_10",
    "trend_quality_120",
    "short_reversal_5",
)
PRIMARY_ALPHA = "composite_trend"
ALPHA_COLUMNS = (*BASE_ALPHA_COLUMNS, PRIMARY_ALPHA)


@dataclass(frozen=True, slots=True)
class E17Config:
    start_date: str = "2018-07-01"
    end_date: str = "2025-12-31"
    horizons: tuple[int, ...] = (60, 120)
    primary_horizon: int = 60
    confirmation_horizon: int = 120
    min_history_sessions: int = 252
    min_close: float = 10.0
    min_avg_volume_20d: float = 50_000.0
    min_adv_usd_20d: float = 10_000_000.0
    min_sector_members: int = 5
    rebalance_sessions: int = 20
    tail_pct: float = 0.20
    min_leg_symbols: int = 10
    round_trip_cost_bps: float = 6.0
    bootstrap_samples: int = 2_000
    bootstrap_seed: int = 20260917
    confirmation_start: str = "2023-01-01"

    def __post_init__(self) -> None:
        if self.primary_horizon not in self.horizons or self.confirmation_horizon not in self.horizons:
            raise ValueError("Les horizons primaire/confirmation doivent appartenir à horizons.")
        if self.min_history_sessions < 252 or self.rebalance_sessions < 1:
            raise ValueError("Historique ou fréquence de rebalance E17 invalide.")
        if not 0 < self.tail_pct <= 0.5:
            raise ValueError("tail_pct doit être dans ]0, 0.5].")

    @property
    def round_trip_cost(self) -> float:
        return self.round_trip_cost_bps / 10_000.0


def load_sector_reference(engine: Engine, symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "sector"])
    frames: list[pd.DataFrame] = []
    for offset in range(0, len(symbols), 500):
        chunk = symbols[offset : offset + 500]
        params = {f"s{i}": symbol for i, symbol in enumerate(chunk)}
        placeholders = ",".join(f":s{i}" for i in range(len(chunk)))
        with engine.connect() as connection:
            frames.append(pd.read_sql(text(
                "SELECT symbol, COALESCE(NULLIF(TRIM(provider_sector), ''), "
                "NULLIF(TRIM(sector), '')) AS sector FROM stock_metadata "
                f"WHERE symbol IN ({placeholders})"
            ), connection, params=params))
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not frame.empty:
        frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
        frame["sector"] = frame["sector"].fillna("UNKNOWN").astype(str).str.strip()
    return frame.drop_duplicates("symbol")


def _rolling_beta(group: pd.DataFrame) -> pd.Series:
    covariance = group["asset_return"].rolling(126, min_periods=126).cov(group["market_return"])
    variance = group["market_return"].rolling(126, min_periods=126).var()
    return (covariance / variance.replace(0.0, np.nan)).clip(-5.0, 5.0)


def build_price_alpha_panel(
    bars: pd.DataFrame,
    benchmark: pd.DataFrame,
    instruments: pd.DataFrame,
    sectors: pd.DataFrame,
    config: E17Config,
) -> pd.DataFrame:
    """Create fixed price-only alphas using observations no later than J."""
    required = {"symbol", "date", "open", "close", "volume"}
    if missing := required - set(bars.columns):
        raise ValueError(f"Barres E17 incomplètes: {sorted(missing)}")
    frame = bars.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    raw_close = pd.to_numeric(frame["close"], errors="coerce")
    adjusted_close = pd.to_numeric(frame.get("adj_close", raw_close), errors="coerce").fillna(raw_close)
    adjustment = (adjusted_close / raw_close.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    frame["px_close"] = adjusted_close
    frame["px_open"] = pd.to_numeric(frame["open"], errors="coerce") * adjustment
    frame["volume_num"] = pd.to_numeric(frame["volume"], errors="coerce")
    filled = frame.get("is_filled", pd.Series(False, index=frame.index))
    frame["valid_bar"] = (
        frame["px_close"].gt(0) & frame["px_open"].gt(0)
        & frame["volume_num"].gt(0) & ~filled.fillna(False).astype(bool)
    )
    frame = frame.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")

    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"], errors="coerce").dt.normalize()
    bench_raw = pd.to_numeric(bench["close"], errors="coerce")
    bench_close = pd.to_numeric(bench.get("adj_close", bench_raw), errors="coerce").fillna(bench_raw)
    bench_factor = bench_close / bench_raw.replace(0.0, np.nan)
    bench["benchmark_open"] = pd.to_numeric(bench["open"], errors="coerce") * bench_factor
    bench["market_return"] = bench_close.pct_change(fill_method=None)
    frame = frame.merge(
        bench[["date", "benchmark_open", "market_return"]].drop_duplicates("date"),
        on="date", how="left", validate="many_to_one",
    )
    frame = frame.merge(sectors, on="symbol", how="left", validate="many_to_one")
    frame = frame.merge(instruments, on="symbol", how="left", validate="many_to_one")
    frame["sector"] = frame["sector"].fillna("UNKNOWN")
    frame["instrument_eligible"] = frame["instrument_eligible"].fillna(False).astype(bool)

    grouped = frame.groupby("symbol", sort=False)
    frame["history_sessions"] = grouped["valid_bar"].cumsum()
    valid_volume = frame["volume_num"].where(frame["valid_bar"])
    dollar_volume = (frame["px_close"] * frame["volume_num"]).where(frame["valid_bar"])
    frame["avg_volume_20d"] = valid_volume.groupby(frame["symbol"]).transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    frame["adv_usd_20d"] = dollar_volume.groupby(frame["symbol"]).transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    frame["asset_return"] = grouped["px_close"].pct_change(fill_method=None)
    frame["beta_126"] = frame.groupby("symbol", group_keys=False).apply(
        _rolling_beta, include_groups=False
    ).reset_index(level=0, drop=True).sort_index()
    frame["residual_return"] = frame["asset_return"] - frame["beta_126"] * frame["market_return"]

    grouped = frame.groupby("symbol", sort=False)
    frame["momentum_252_21"] = (
        grouped["px_close"].shift(21) / grouped["px_close"].shift(252) - 1.0
    )
    frame["momentum_120_10"] = (
        grouped["px_close"].shift(10) / grouped["px_close"].shift(120) - 1.0
    )
    frame["short_reversal_5"] = -(
        frame["px_close"] / grouped["px_close"].shift(5) - 1.0
    )
    residual_shifted = grouped["residual_return"].shift(10)
    frame["residual_momentum_120_10"] = residual_shifted.groupby(frame["symbol"]).transform(
        lambda values: values.rolling(110, min_periods=110).sum()
    )
    vol120 = grouped["asset_return"].transform(
        lambda values: values.rolling(120, min_periods=120).std()
    )
    trend120 = frame["px_close"] / grouped["px_close"].shift(120) - 1.0
    frame["trend_quality_120"] = trend120 / (vol120 * math.sqrt(120)).replace(0.0, np.nan)

    frame["market_eligible"] = (
        frame["valid_bar"]
        & frame["history_sessions"].ge(config.min_history_sessions)
        & frame["px_close"].ge(config.min_close)
        & frame["avg_volume_20d"].ge(config.min_avg_volume_20d)
        & frame["adv_usd_20d"].ge(config.min_adv_usd_20d)
        & frame["instrument_eligible"]
    )
    eligible = frame["market_eligible"]
    sector_count = frame.loc[eligible].groupby(["date", "sector"])["symbol"].transform("nunique")
    sector_median = frame.loc[eligible].groupby(["date", "sector"])["momentum_120_10"].transform("median")
    frame["industry_relative_momentum"] = np.nan
    frame.loc[eligible, "industry_relative_momentum"] = (
        frame.loc[eligible, "momentum_120_10"] - sector_median
    ).where(sector_count.ge(config.min_sector_members))

    for horizon in config.horizons:
        grouped = frame.groupby("symbol", sort=False)
        entry = grouped["px_open"].shift(-1)
        exit_price = grouped["px_open"].shift(-(horizon + 1))
        # Benchmark shifts must be by date, not by symbol rows.
        bench_by_date = bench[["date", "benchmark_open"]].drop_duplicates("date").sort_values("date")
        bench_by_date[f"benchmark_future_return_h{horizon}"] = (
            bench_by_date["benchmark_open"].shift(-(horizon + 1))
            / bench_by_date["benchmark_open"].shift(-1) - 1.0
        )
        mapping = bench_by_date.set_index("date")[f"benchmark_future_return_h{horizon}"]
        raw_return = exit_price / entry - 1.0
        valid_label = raw_return.between(-0.95, 3.0) & entry.gt(0) & exit_price.gt(0)
        frame[f"future_return_h{horizon}"] = raw_return.where(valid_label)
        frame[f"benchmark_future_return_h{horizon}"] = frame["date"].map(mapping)
        frame[f"future_excess_h{horizon}"] = (
            frame[f"future_return_h{horizon}"] - frame[f"benchmark_future_return_h{horizon}"]
        )

    rank_columns: list[str] = []
    for alpha in BASE_ALPHA_COLUMNS:
        ranked = frame[alpha].where(eligible).groupby(frame["date"]).rank(pct=True, method="average")
        rank_column = f"score_{alpha}"
        frame[rank_column] = 2.0 * (ranked - 0.5)
        rank_columns.append(rank_column)
    trend_components = [f"score_{name}" for name in BASE_ALPHA_COLUMNS if name != "short_reversal_5"]
    component_count = frame[trend_components].notna().sum(axis=1)
    frame[f"score_{PRIMARY_ALPHA}"] = frame[trend_components].mean(axis=1).where(component_count.ge(4))
    return frame


def _safe_spearman(group: pd.DataFrame, score: str, target: str) -> float:
    valid = group[[score, target]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < 20 or valid[score].nunique() < 2 or valid[target].nunique() < 2:
        return float("nan")
    return float(spearmanr(valid[score], valid[target]).statistic)


def _bootstrap(values: pd.Series, config: E17Config, horizon: int) -> tuple[float, float]:
    clean = pd.Series(values).replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    if clean.empty:
        return float("nan"), float("nan")
    rolling = RollingConfig(
        bootstrap_samples=config.bootstrap_samples,
        bootstrap_block_sessions=max(2, math.ceil(horizon / config.rebalance_sessions)),
        bootstrap_seed=config.bootstrap_seed + horizon,
    )
    return block_bootstrap_mean(clean, rolling)


def select_rebalance_dates(dates: pd.Series, config: E17Config) -> set[pd.Timestamp]:
    unique = sorted(pd.to_datetime(dates.dropna()).dt.normalize().unique())
    return {pd.Timestamp(value) for value in unique[:: config.rebalance_sessions]}


def evaluate_alpha(
    panel: pd.DataFrame, alpha: str, horizon: int, config: E17Config,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    score = f"score_{alpha}"
    target = f"future_excess_h{horizon}"
    raw_target = f"future_return_h{horizon}"
    scope = panel[
        panel["market_eligible"] & panel[score].notna() & panel[target].notna()
    ].copy()
    daily_ic = scope.groupby("date", sort=True).apply(
        lambda group: _safe_spearman(group, score, target), include_groups=False
    ).rename("ic").dropna().reset_index()
    ic_ci = _bootstrap(daily_ic["ic"], config, horizon)

    rebalance_dates = select_rebalance_dates(scope["date"], config)
    rows: list[dict[str, Any]] = []
    for date, group in scope[scope["date"].isin(rebalance_dates)].groupby("date", sort=True):
        ordered = group.sort_values([score, "symbol"])
        leg_size = max(config.min_leg_symbols, int(math.floor(len(ordered) * config.tail_pct)))
        if len(ordered) < 2 * leg_size:
            continue
        short = ordered.head(leg_size)
        long = ordered.tail(leg_size)
        long_return = float(long[raw_target].mean() - config.round_trip_cost)
        short_return = float(-short[raw_target].mean() - config.round_trip_cost)
        rows.append({
            "date": pd.Timestamp(date), "alpha": alpha, "horizon": horizon,
            "universe": int(len(ordered)), "leg_size": int(leg_size),
            "long_return_net": long_return, "short_return_net": short_return,
            "long_short_return_net": 0.5 * (long_return + short_return),
            "top_mean_score": float(long[score].mean()),
            "bottom_mean_score": float(short[score].mean()),
        })
    cohorts = pd.DataFrame(rows)
    if cohorts.empty:
        return {"alpha": alpha, "horizon": horizon, "cohorts": 0}, daily_ic, cohorts
    cohorts["semester"] = (
        cohorts["date"].dt.year.astype(str)
        + "H" + np.where(cohorts["date"].dt.month.le(6), "1", "2")
    )
    semester = cohorts.groupby("semester")["long_short_return_net"].agg(["count", "mean", "sum"])
    positive_sum = semester["sum"].clip(lower=0).sum()
    concentration = (
        float(semester["sum"].clip(lower=0).max() / positive_sum) if positive_sum > 0 else 1.0
    )
    ls_ci = _bootstrap(cohorts["long_short_return_net"], config, horizon)
    confirmation = cohorts[cohorts["date"].ge(pd.Timestamp(config.confirmation_start))]
    result = {
        "alpha": alpha,
        "horizon": horizon,
        "observations": int(len(scope)),
        "dates": int(scope["date"].nunique()),
        "daily_ic_mean": float(daily_ic["ic"].mean()),
        "daily_ic_median": float(daily_ic["ic"].median()),
        "daily_ic_ci95_low": ic_ci[0],
        "daily_ic_ci95_high": ic_ci[1],
        "cohorts": int(len(cohorts)),
        "mean_leg_size": float(cohorts["leg_size"].mean()),
        "long_mean_net": float(cohorts["long_return_net"].mean()),
        "short_mean_net": float(cohorts["short_return_net"].mean()),
        "long_short_mean_net": float(cohorts["long_short_return_net"].mean()),
        "long_short_ci95_low": ls_ci[0],
        "long_short_ci95_high": ls_ci[1],
        "positive_semester_ratio": float(semester["mean"].gt(0).mean()),
        "positive_pnl_semester_concentration": concentration,
        "confirmation_cohorts": int(len(confirmation)),
        "confirmation_long_short_mean_net": (
            float(confirmation["long_short_return_net"].mean()) if len(confirmation) else None
        ),
        "semesters": semester.reset_index().to_dict(orient="records"),
    }
    return result, daily_ic, cohorts


def build_gates(results: dict[str, dict[str, Any]], config: E17Config) -> dict[str, bool]:
    primary = results[f"{PRIMARY_ALPHA}_h{config.primary_horizon}"]
    confirmation = results[f"{PRIMARY_ALPHA}_h{config.confirmation_horizon}"]
    gates = {
        "h60_ic_positive": primary.get("daily_ic_mean", -np.inf) > 0,
        "h60_ic_ci95_above_zero": primary.get("daily_ic_ci95_low", -np.inf) > 0,
        "h60_long_short_positive": primary.get("long_short_mean_net", -np.inf) > 0,
        "h60_long_short_ci95_above_zero": primary.get("long_short_ci95_low", -np.inf) > 0,
        "h60_both_legs_positive": min(
            primary.get("long_mean_net", -np.inf), primary.get("short_mean_net", -np.inf)
        ) > 0,
        "h60_positive_semesters_70pct": primary.get("positive_semester_ratio", 0.0) >= 0.70,
        "h60_no_semester_over_35pct_positive_pnl": (
            primary.get("positive_pnl_semester_concentration", 1.0) <= 0.35
        ),
        "since_2023_positive": primary.get("confirmation_long_short_mean_net", -np.inf) > 0,
        "h120_ic_positive": confirmation.get("daily_ic_mean", -np.inf) > 0,
        "h120_long_short_positive": confirmation.get("long_short_mean_net", -np.inf) > 0,
        "enough_h60_cohorts": primary.get("cohorts", 0) >= 60,
    }
    gates["go_research"] = all(gates.values())
    return gates


def run(
    *, symbol_source: str, output_root: Path, config: E17Config,
) -> Path:
    symbols = load_universe_file_symbols(symbol_source)
    if not symbols:
        raise ValueError(f"Univers vide: {symbol_source}")
    symbols = sorted(set(symbols))
    engine = get_sqlalchemy_engine()
    history_start = pd.Timestamp(config.start_date) - pd.offsets.BDay(300)
    label_end = pd.Timestamp(config.end_date) + pd.offsets.BDay(max(config.horizons) + 5)
    bars = load_universe_bars(
        engine, symbols, start_date=history_start.date(), end_date=label_end.date()
    )
    benchmark = load_universe_bars(
        engine, ["SPY"], start_date=history_start.date(), end_date=label_end.date()
    )
    instruments = classify_instruments(load_instrument_reference(engine, symbols))
    sectors = load_sector_reference(engine, symbols)
    panel = build_price_alpha_panel(bars, benchmark, instruments, sectors, config)
    study = panel[
        panel["date"].between(pd.Timestamp(config.start_date), pd.Timestamp(config.end_date))
    ].copy()
    results: dict[str, dict[str, Any]] = {}
    ic_frames: list[pd.DataFrame] = []
    cohort_frames: list[pd.DataFrame] = []
    for alpha in ALPHA_COLUMNS:
        for horizon in config.horizons:
            summary, daily_ic, cohorts = evaluate_alpha(study, alpha, horizon, config)
            results[f"{alpha}_h{horizon}"] = summary
            if len(daily_ic):
                ic_frames.append(daily_ic.assign(alpha=alpha, horizon=horizon))
            if len(cohorts):
                cohort_frames.append(cohorts)
    gates = build_gates(results, config)
    verdict = "GO_RESEARCH" if gates["go_research"] else "NO_GO"
    run_id = f"directional-alpha-book-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    study_columns = [
        "date", "symbol", "sector", "market_eligible", *BASE_ALPHA_COLUMNS,
        *(f"score_{alpha}" for alpha in ALPHA_COLUMNS),
        *(f"future_return_h{h}" for h in config.horizons),
        *(f"future_excess_h{h}" for h in config.horizons),
    ]
    study[study_columns].to_parquet(output / "alpha_panel.parquet", index=False)
    pd.concat(ic_frames, ignore_index=True).to_csv(output / "daily_ic.csv", index=False)
    pd.concat(cohort_frames, ignore_index=True).to_csv(output / "portfolio_cohorts.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E17_PRICE_ONLY_DIRECTIONAL_ALPHA_BOOK",
        "status": "complete",
        "research_only": True,
        "oracle_used": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "symbol_source": symbol_source,
        "symbols_requested": len(symbols),
        "config": asdict(config),
        "contract": {
            "signal_time": "close J",
            "entry_exit": "split-adjusted open J+1 to open J+H+1",
            "target": "stock return and excess versus SPY",
            "portfolio": "equal-weight top/bottom 20%, 50/50 dollar-neutral, rebalance every 20 sessions",
            "costs": "6 bps round trip per leg; borrow fees unavailable",
            "primary": f"{PRIMARY_ALPHA} H{config.primary_horizon}",
            "confirmation": f"{PRIMARY_ALPHA} H{config.confirmation_horizon}",
            "survivorship_warning": "input file and sector/instrument metadata are current snapshots, not historically versioned",
        },
        "population": {
            "panel_rows": int(len(study)),
            "dates": int(study["date"].nunique()),
            "symbols": int(study["symbol"].nunique()),
            "eligible_rows": int(study["market_eligible"].sum()),
            "eligible_ratio": float(study["market_eligible"].mean()),
        },
        "results": results,
        "gates": gates,
        "verdict": verdict,
        "promotion_authorized": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E17 terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbol-source", default="universe-file:univers_filtred_equities.txt"
    )
    parser.add_argument("--start-date", default="2018-07-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/directional_alpha_book"),
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        symbol_source=args.symbol_source,
        output_root=args.output_root,
        config=E17Config(
            start_date=args.start_date,
            end_date=args.end_date,
            bootstrap_samples=args.bootstrap_samples,
        ),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E17 terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
