from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Final, Literal

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.data_loader import load_ohlcv, load_predictions, load_scores, pivot_ohlcv
from backtesting.report import (
    extract_diagnostics,
    generate_report,
    save_equity_curve,
    save_equity_curve_csv,
    save_report_json,
    save_trades_csv,
)
from backtesting.resilience import prepare_predictions_for_ml_mode, prepare_scores_for_sentiment_mode
from backtesting.signal_replay import replay_signals
from backtesting.simulator import BacktestConfig, BacktestEngine
from backtesting.trading_constraints import TradingConstraintConfig
from database.connection import get_sqlalchemy_engine
from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS

START = pd.Timestamp("2024-01-01").date()
END = pd.Timestamp("2024-01-31").date()
LOOKBACK_START = pd.Timestamp("2024-12-20").date()
OUTPUT_DIR = Path("prompt/fix_swing/cash_eq2000_mp2_filtered_f2")
FILTERS = STRICT_SWING_CASH_FILTERS.to_backtest_filter_dict()
EQUITY: Final[float] = 2000.0
TP: Final[float] = 0.08
TS: Final[float] = 0.05
MAX_POSITIONS: Final[int] = 2
ACCOUNT_TYPE: Final[Literal["cash", "margin"]] = "cash"
PDT_RULE: Final[Literal["auto", "off"]] = "off"
SWING_ONLY: Final[bool] = True


def _parse_date(value: str) -> date:
    return pd.Timestamp(value).date()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rerun backtest filtré PIT pour petit compte cash")
    parser.add_argument("--start", default=str(START), help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", default=str(END), help="Date de fin (YYYY-MM-DD)")
    parser.add_argument(
        "--lookback-start",
        default=str(LOOKBACK_START),
        help="Date de début du chargement OHLCV pour calculer les filtres PIT",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Répertoire de sortie des artefacts",
    )
    return parser


def build_point_in_time_filters(ohlcv_full: pd.DataFrame, start, end) -> pd.DataFrame:
    prices = ohlcv_full[["symbol", "trade_date", "close", "volume"]].copy()
    prices = prices.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    prices["dollar_volume"] = prices["close"].astype(float) * prices["volume"].astype(float)
    prices["daily_return"] = (
        prices.groupby("symbol")["close"]
        .pct_change()
        .replace([float("inf"), float("-inf")], pd.NA)
        .fillna(0.0)
    )
    prices["avg_dollar_volume_20d"] = (
        prices.groupby("symbol")["dollar_volume"]
        .rolling(20, min_periods=20)
        .mean()
        .reset_index(level=0, drop=True)
    )
    prices["vol_10"] = (
        prices.groupby("symbol")["daily_return"]
        .rolling(10, min_periods=10)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )
    prices["vol_60"] = (
        prices.groupby("symbol")["daily_return"]
        .rolling(60, min_periods=60)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )
    prices["volatility_ratio"] = prices["vol_10"] / prices["vol_60"]
    features = prices[
        ["symbol", "trade_date", "close", "avg_dollar_volume_20d", "volatility_ratio"]
    ].rename(columns={"close": "latest_close"})
    trade_dates = features["trade_date"].dt.date
    return features[(trade_dates >= start) & (trade_dates <= end)].copy()


def main() -> None:
    args = _build_parser().parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    lookback_start = _parse_date(args.lookback_start)
    output_dir = Path(args.output_dir)

    engine = get_sqlalchemy_engine()
    ohlcv_full = load_ohlcv(engine, lookback_start, end)
    ohlcv_df = ohlcv_full[ohlcv_full["trade_date"].dt.date.between(start, end)].copy()
    scores_df = load_scores(engine, start, end)
    scores_df = prepare_scores_for_sentiment_mode(engine, scores_df, sentiment_mode="auto")
    preds_df = load_predictions(engine, start, end)
    preds_df = prepare_predictions_for_ml_mode(
        engine,
        scores_df,
        preds_df,
        ml_mode="auto",
        artifacts_dir=Path("artifacts/models"),
    )

    features = build_point_in_time_filters(ohlcv_full, start, end)
    filtered_scores = scores_df.merge(features, on=["symbol", "trade_date"], how="left")
    filtered_scores = STRICT_SWING_CASH_FILTERS.apply_to_frame(filtered_scores)

    signals = replay_signals(
        filtered_scores,
        preds_df if not preds_df.empty else None,
        max_positions=MAX_POSITIONS,
    )
    pivoted = pivot_ohlcv(ohlcv_df)
    pf = BacktestEngine(
        BacktestConfig(
            start_date=start,
            end_date=end,
            initial_equity=EQUITY,
            profit_taker_pct=TP,
            trailing_stop_pct=TS,
            max_positions=MAX_POSITIONS,
            trading_constraints=TradingConstraintConfig(
                account_type=ACCOUNT_TYPE,
                pdt_rule=PDT_RULE,
                swing_only=SWING_ONLY,
            ),
        )
    ).run(
        open=pivoted["open"],
        close=pivoted["close"],
        high=pivoted["high"],
        low=pivoted["low"],
        signals_df=signals,
    )

    report = generate_report(pf, EQUITY)
    diagnostics = extract_diagnostics(pf)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "equity_curve_csv": str(save_equity_curve_csv(pf, output_dir=output_dir)),
        "trades_csv": str(save_trades_csv(pf, output_dir=output_dir)),
        "equity_curve_png": str(save_equity_curve(pf, output_dir=output_dir)),
    }
    report_path = save_report_json(
        report,
        output_dir=output_dir,
        artifacts=artifacts,
        params={
            "start": str(start),
            "end": str(end),
            "lookback_start": str(lookback_start),
            "equity": EQUITY,
            "tp": TP,
            "ts": TS,
            "max_positions": MAX_POSITIONS,
            "account_type": ACCOUNT_TYPE,
            "pdt_rule": PDT_RULE,
            "swing_only": SWING_ONLY,
            "execution_timing": "signal J (calculé après clôture) -> ordre pour J+1 open",
            "filters": FILTERS,
        },
        diagnostics=diagnostics,
    )

    trades = pf.closed_trades_df.copy()
    pnl_by_symbol = trades.groupby("symbol")["pnl"].sum().sort_values(ascending=False) if not trades.empty else pd.Series(dtype=float)
    total_pnl = float(trades["pnl"].sum()) if not trades.empty else 0.0
    summary = {
        "summary": report.to_serializable_dict(),
        "diagnostics": diagnostics,
        "filters": FILTERS,
        "filtered_score_rows": int(len(filtered_scores)),
        "filtered_days": int(filtered_scores["trade_date"].nunique()),
        "selected_entries": int(signals["selected"].sum()),
        "top3_trades_share_pct": float(trades["pnl"].nlargest(3).sum() / total_pnl * 100.0)
        if not trades.empty and total_pnl
        else 0.0,
        "top3_symbols_share_pct": float(pnl_by_symbol.head(3).sum() / total_pnl * 100.0)
        if not pnl_by_symbol.empty and total_pnl
        else 0.0,
        "top_symbols_pnl": pnl_by_symbol.head(10).round(6).to_dict(),
        "median_trade_pnl": float(trades["pnl"].median()) if not trades.empty else 0.0,
        "non_positive_trade_pct": float((trades["pnl"] <= 0).mean() * 100.0) if not trades.empty else 0.0,
        "unique_symbols": int(trades["symbol"].nunique()) if not trades.empty else 0,
        "report_path": str(report_path),
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


