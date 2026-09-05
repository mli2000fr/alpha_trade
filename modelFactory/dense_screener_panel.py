"""Construit un panel screener PIT dense sur la population Oracle OOF.

Artefact de recherche uniquement : aucune table n'est modifiée et le screener
de production reste inchangé. Les facteurs sont calculés avant tout rejet.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from screener.models import ScreenerConfig

LOGGER = logging.getLogger(__name__)
DEFAULT_OUTPUT_ROOT = Path("artifacts/research/screener_dense")


def load_oracle_population(gate_path: Path, *, start_date: str | None = None,
                           end_date: str | None = None,
                           pool_pct: float = 0.20) -> pd.DataFrame:
    """Charge toute la population OOF et marque le TOP Oracle sans la réduire."""
    gate = pd.read_parquet(gate_path)
    required = {"date", "symbol", "directional_oracle_oof_available",
                "directional_oracle_extreme_pct"}
    missing = sorted(required.difference(gate.columns))
    if missing:
        raise ValueError(f"Cache Oracle OOF incomplet: {missing}")
    gate = gate.copy()
    gate["date"] = pd.to_datetime(gate["date"], errors="coerce").dt.normalize()
    gate["symbol"] = gate["symbol"].astype(str).str.strip().str.upper()
    gate["oracle_percentile"] = pd.to_numeric(
        gate["directional_oracle_extreme_pct"], errors="coerce")
    gate["oracle_oof_available"] = gate[
        "directional_oracle_oof_available"].fillna(False).astype(bool)
    gate = gate[gate["oracle_oof_available"]].dropna(
        subset=["date", "symbol", "oracle_percentile"])
    if start_date:
        gate = gate[gate["date"] >= pd.Timestamp(start_date)]
    if end_date:
        gate = gate[gate["date"] <= pd.Timestamp(end_date)]
    gate["oracle_top_pool"] = gate["oracle_percentile"].ge(1.0 - float(pool_pct))
    return gate[["date", "symbol", "oracle_oof_available", "oracle_percentile",
                 "oracle_top_pool"]].drop_duplicates(
        ["date", "symbol"], keep="last").sort_values(
            ["symbol", "date"]).reset_index(drop=True)


def load_bars(engine: Any, symbols: list[str], *, start_date: pd.Timestamp,
              end_date: pd.Timestamp, lookback_calendar_days: int = 800,
              chunk_size: int = 500) -> pd.DataFrame:
    """Charge l'historique requis sans condition de tradabilité."""
    requested = sorted(set(symbols) | {"SPY"})
    statement = text(
        "SELECT symbol, `date`, COALESCE(adj_close, `close`) AS close, "
        "high, low, volume, COALESCE(is_filled, 0) AS is_filled "
        "FROM stock_bars_daily WHERE symbol IN :symbols "
        "AND `date` >= :start_date AND `date` <= :end_date "
        "ORDER BY symbol, `date`").bindparams(bindparam("symbols", expanding=True))
    parts: list[pd.DataFrame] = []
    for offset in range(0, len(requested), int(chunk_size)):
        with engine.connect() as connection:
            parts.append(pd.read_sql(statement, connection, params={
                "symbols": requested[offset:offset + int(chunk_size)],
                "start_date": (start_date - pd.Timedelta(
                    days=int(lookback_calendar_days))).date(),
                "end_date": end_date.date(),
            }))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _calendar_window_return(dates: pd.Series, closes: pd.Series,
                            days: int) -> np.ndarray:
    date_values = pd.to_datetime(dates).to_numpy(dtype="datetime64[ns]")
    close_values = pd.to_numeric(closes, errors="coerce").to_numpy(dtype=float)
    starts = np.searchsorted(
        date_values, date_values - np.timedelta64(int(days), "D"), side="left")
    start_values = close_values[starts]
    return np.where(
        np.isfinite(close_values) & np.isfinite(start_values) & (start_values > 0),
        close_values / start_values - 1.0, np.nan)


def _daily_percentile(frame: pd.DataFrame, column: str,
                      mask: pd.Series | None = None) -> pd.Series:
    eligible = pd.Series(True, index=frame.index) if mask is None else mask.fillna(False)
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    result.loc[eligible] = frame.loc[eligible].groupby("date")[column].rank(
        method="average", pct=True) * 100.0
    return result


def compute_dense_panel(oracle_population: pd.DataFrame, bars: pd.DataFrame,
                        config: ScreenerConfig | None = None) -> pd.DataFrame:
    """Rejoue les facteurs screener avant filtre et les joint aux lignes Oracle."""
    cfg = config or ScreenerConfig()
    if oracle_population.empty:
        return oracle_population.copy()
    required = {"symbol", "date", "close", "high", "low", "volume"}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"Barres incomplètes: {missing}")
    prices = bars.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["symbol"] = prices["symbol"].astype(str).str.strip().str.upper()
    for column in ("close", "high", "low", "volume"):
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    if "is_filled" not in prices:
        prices["is_filled"] = 0
    prices = prices.dropna(subset=["date", "symbol"]).sort_values(
        ["symbol", "date"]).drop_duplicates(
            ["symbol", "date"], keep="last").reset_index(drop=True)
    prices["history_bars_loaded"] = prices.groupby("symbol").cumcount() + 1
    prices["dollar_volume"] = prices["close"] * prices["volume"]
    prices["liquidity_val"] = prices.groupby("symbol")["dollar_volume"].rolling(
        cfg.lookback_liquidity_bars,
        min_periods=cfg.lookback_liquidity_bars).mean().reset_index(level=0, drop=True)
    prices["stock_return_6m"] = np.nan
    for _, indices in prices.groupby("symbol", sort=False).groups.items():
        idx = pd.Index(indices)
        prices.loc[idx, "stock_return_6m"] = _calendar_window_return(
            prices.loc[idx, "date"], prices.loc[idx, "close"],
            cfg.lookback_relative_days)
    benchmark = prices[prices["symbol"].eq(cfg.benchmark_symbol)].copy()
    if benchmark.empty:
        raise ValueError(f"Benchmark {cfg.benchmark_symbol} absent des barres.")
    benchmark["spy_return_6m"] = _calendar_window_return(
        benchmark["date"], benchmark["close"], cfg.lookback_relative_days)
    prices = prices.merge(benchmark[["date", "spy_return_6m"]], on="date",
                          how="left", validate="many_to_one")
    denominator = 1.0 + prices["spy_return_6m"]
    prices["relative_strength_index"] = np.where(
        denominator > 0.0001,
        ((1.0 + prices["stock_return_6m"]) / denominator) * 100.0, np.nan)
    valid_range = pd.to_numeric(prices["is_filled"], errors="coerce").fillna(0).eq(0)
    prices["range_low_input"] = prices["low"].where(valid_range)
    prices["range_high_input"] = prices["high"].where(valid_range)
    indexed = prices.set_index("date")
    prices["hist_low"] = indexed.groupby("symbol")["range_low_input"].rolling(
        f"{cfg.historical_range_lookback_days}D", closed="both",
        min_periods=1).min().reset_index(level=0, drop=True).to_numpy()
    prices["hist_high"] = indexed.groupby("symbol")["range_high_input"].rolling(
        f"{cfg.historical_range_lookback_days}D", closed="both",
        min_periods=1).max().reset_index(level=0, drop=True).to_numpy()
    span = prices["hist_high"] - prices["hist_low"]
    prices["historical_range_score"] = np.where(
        span > 0, (prices["close"] - prices["hist_low"]) / span * 100.0, 50.0)
    prices["historical_range_score"] = prices["historical_range_score"].clip(0, 100)
    population = oracle_population.copy()
    population["date"] = pd.to_datetime(population["date"]).dt.normalize()
    panel = population.merge(prices[[
        "date", "symbol", "close", "volume", "history_bars_loaded",
        "liquidity_val", "stock_return_6m", "spy_return_6m",
        "relative_strength_index", "hist_low", "hist_high",
        "historical_range_score", "is_filled",
    ]], on=["date", "symbol"], how="left", validate="one_to_one")
    panel["feature_available_price"] = panel["close"].notna()
    panel["feature_available_liquidity"] = panel["liquidity_val"].notna()
    panel["feature_available_relative_strength"] = panel[
        "relative_strength_index"].notna()
    panel["feature_available_historical_range"] = panel[
        "historical_range_score"].notna()
    panel["filter_history_pass"] = (panel["history_bars_loaded"].ge(
        cfg.min_history_days) & panel["close"].ge(cfg.min_close_price)).fillna(False)
    panel["filter_liquidity_pass"] = panel["liquidity_val"].ge(
        cfg.liquidity_threshold_usd).fillna(False)
    panel["filter_relative_strength_pass"] = panel[
        "relative_strength_index"].ge(cfg.min_relative_strength_index).fillna(False)
    panel["filter_historical_range_pass"] = panel[
        "historical_range_score"].ge(cfg.min_historical_range_score).fillna(False)
    panel["filter_all_pass"] = panel[[
        "filter_history_pass", "filter_liquidity_pass",
        "filter_relative_strength_pass", "filter_historical_range_pass"]].all(axis=1)
    for suffix, eligibility in (("dense", None),
                                ("survivors", panel["filter_all_pass"])):
        panel[f"liquidity_score_{suffix}"] = _daily_percentile(
            panel, "liquidity_val", eligibility)
        panel[f"relative_strength_score_{suffix}"] = _daily_percentile(
            panel, "relative_strength_index", eligibility)
        panel[f"historical_range_percentile_{suffix}"] = _daily_percentile(
            panel, "historical_range_score", eligibility)
        weight_sum = cfg.weight_liquidity + cfg.weight_relative_strength + cfg.weight_historical_range
        panel[f"total_score_{suffix}"] = (
            panel[f"liquidity_score_{suffix}"] * cfg.weight_liquidity
            + panel[f"relative_strength_score_{suffix}"] * cfg.weight_relative_strength
            + panel[f"historical_range_percentile_{suffix}"] * cfg.weight_historical_range
        ) / weight_sum
    quality = panel[["close", "volume"]].apply(pd.to_numeric, errors="coerce")
    panel["data_quality_valid"] = (
        np.isfinite(quality).all(axis=1) & quality["close"].gt(0)
        & quality["volume"].ge(0)
        & pd.to_numeric(panel["is_filled"], errors="coerce").fillna(0).eq(0))
    flag_columns = [("filter_history_pass", "history_or_price"),
                    ("filter_liquidity_pass", "liquidity"),
                    ("filter_relative_strength_pass", "relative_strength"),
                    ("filter_historical_range_pass", "historical_range")]
    panel["rejection_reasons"] = panel.apply(
        lambda row: ",".join(label for column, label in flag_columns
                             if not bool(row[column])), axis=1)
    return panel.sort_values(["date", "symbol"]).reset_index(drop=True)


def build_quality_report(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in panel.columns:
        if (column.startswith("feature_available_") or
                column.startswith("filter_") or column == "data_quality_valid"):
            values = panel[column].fillna(False).astype(bool)
            rows.append({"metric": column, "rows": int(len(values)),
                         "count_true": int(values.sum()),
                         "ratio_true": float(values.mean())})
    return pd.DataFrame(rows)


def write_artifacts(panel: pd.DataFrame, *, output_dir: Path, batch_id: str,
                    config: ScreenerConfig, pool_pct: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    panel.to_parquet(output_dir / "dense_screener_panel.parquet", index=False)
    panel[panel["oracle_top_pool"]].to_parquet(
        output_dir / "oracle_top20_screener_panel.parquet", index=False)
    build_quality_report(panel).to_csv(output_dir / "quality_report.csv", index=False)
    coverage = {
        "batch_id": batch_id, "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(panel)), "dates": int(panel["date"].nunique()),
        "symbols": int(panel["symbol"].nunique()),
        "oracle_top_rows": int(panel["oracle_top_pool"].sum()),
        "all_filters_pass_rows": int(panel["filter_all_pass"].sum()),
        "config": asdict(config), "pool_pct": float(pool_pct),
    }
    (output_dir / "coverage.json").write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    dictionary = {
        "point_in_time": "Chaque ligne utilise uniquement les barres de date <= date.",
        "population": "Toutes les lignes Oracle OOF avant filtre; oracle_top_pool marque le TOP.",
        "liquidity_val": f"Moyenne {config.lookback_liquidity_bars} barres de close ajusté × volume.",
        "relative_strength_index": f"Ratio rendement symbole/SPY sur {config.lookback_relative_days} jours calendaires × 100.",
        "historical_range_score": f"Position du close dans le range sur {config.historical_range_lookback_days} jours; is_filled exclu.",
        "total_score_dense": "Score 15/55/30 sur toute la population quotidienne disponible.",
        "total_score_survivors": "Score 15/55/30 parmi les lignes passant les quatre filtres.",
        "rejection_reasons": "Raisons de rejet conservées sans supprimer la ligne.",
    }
    (output_dir / "feature_dictionary.json").write_text(
        json.dumps(dictionary, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--artifacts-dir", default="artifacts/models")
    parser.add_argument("--gate-path")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    gate_path = Path(args.gate_path) if args.gate_path else (
        Path(args.artifacts_dir) / args.oracle_batch_id / "_oracle_oof_gate.parquet")
    population = load_oracle_population(
        gate_path, start_date=args.start_date, end_date=args.end_date,
        pool_pct=args.pool_pct)
    if population.empty:
        raise RuntimeError("Population Oracle OOF vide sur la période demandée.")
    LOGGER.info("Population Oracle: %s lignes, %s symboles", len(population),
                population["symbol"].nunique())
    bars = load_bars(get_sqlalchemy_engine(), population["symbol"].unique().tolist(),
                     start_date=population["date"].min(),
                     end_date=population["date"].max())
    panel = compute_dense_panel(population, bars)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    output = Path(args.output_root) / (
        f"dense-screener-{stamp}-{args.oracle_batch_id[-6:]}")
    write_artifacts(panel, output_dir=output, batch_id=args.oracle_batch_id,
                    config=ScreenerConfig(), pool_pct=args.pool_pct)
    LOGGER.info("Panel dense écrit dans %s", output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
