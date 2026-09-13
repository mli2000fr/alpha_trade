"""E7-A: dataset PIT quotidien des décisions KEEP/EXIT.

Le programme réutilise les entrées appariées du replay Oracle rolling V2 et la
politique témoin ``fixed_h20``. Il ne modifie ni tables, ni serving, ni backtest.
Une ligne représente une position encore ouverte à une clôture; une décision
éventuelle est exécutable au prochain open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)

IDENTITY_COLUMNS = [
    "trade_id", "signal_date", "symbol", "entry_date", "state_date",
    "execution_date", "terminal_date", "terminal_exit_reason",
]
TARGET_COLUMNS = [
    "immediate_exit_net", "keep_terminal_net", "target_keep_advantage",
    "target_future_residual", "label_keep", "label_tp_before_stop",
    "label_stop_before_tp", "future_return_h3", "future_return_h5",
    "future_mfe_h5", "future_mae_h5", "label_end_date",
]
FEATURE_COLUMNS = [
    "holding_session", "remaining_sessions_h20", "entry_atr_pct",
    "current_pnl_gross", "current_pnl_net", "mfe_so_far", "mae_so_far",
    "drawdown_from_peak", "distance_to_tp", "distance_to_active_stop",
    "return_1d", "return_3d", "return_5d", "realized_vol_5d",
    "realized_vol_10d", "volume_ratio_20d", "pct_h5", "pct_h10",
    "pct_h15", "pct_h20", "consensus_mean", "consensus_std",
    "consensus_rank", "oracle_h5_delta_1d", "oracle_h5_delta_3d",
    "oracle_h5_top20", "spy_return_1d", "spy_return_5d",
    "spy_realized_vol_5d", "relative_return_1d", "relative_return_5d",
]


@dataclass(frozen=True, slots=True)
class KeepExitDatasetConfig:
    fixed_holding_sessions: int = 20
    initial_stop_atr_multiple: float = 2.5
    trailing_atr_multiple: float = 2.5
    tp_atr_multiple: float = 3.0
    tp_max_pct: float = 0.07
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    min_states_per_bin: int = 100

    def __post_init__(self) -> None:
        if self.fixed_holding_sessions < 2:
            raise ValueError("fixed_holding_sessions doit être >= 2.")
        if min(
            self.initial_stop_atr_multiple, self.trailing_atr_multiple,
            self.tp_atr_multiple, self.tp_max_pct,
        ) <= 0:
            raise ValueError("Les paramètres du lifecycle doivent être positifs.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_oracle_features(aligned: pd.DataFrame) -> pd.DataFrame:
    """Conserve seulement les scores OOF observables à la date d'état."""
    columns = [
        "date", "symbol", "pct_h5", "pct_h10", "pct_h15", "pct_h20",
        "consensus_mean", "consensus_std", "consensus_rank",
    ]
    missing = set(columns) - set(aligned.columns)
    if missing:
        raise ValueError(f"Prédictions Oracle incomplètes: {sorted(missing)}")
    frame = aligned[columns].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame = frame.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"])
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("Prédictions Oracle dupliquées pour (date, symbol).")
    grouped = frame.groupby("symbol", sort=False)["pct_h5"]
    frame["oracle_h5_delta_1d"] = grouped.diff(1)
    frame["oracle_h5_delta_3d"] = grouped.diff(3)
    frame["oracle_h5_top20"] = frame["pct_h5"].ge(0.80).astype(float)
    return frame


def prepare_market_features(spy_bars: pd.DataFrame) -> pd.DataFrame:
    """Construit un contexte marché connu à la clôture de la décision."""
    if spy_bars.empty:
        return pd.DataFrame(columns=[
            "date", "spy_return_1d", "spy_return_5d", "spy_realized_vol_5d",
        ])
    frame = spy_bars.sort_values("date").drop_duplicates("date").copy()
    returns = frame["px_close"].pct_change()
    frame["spy_return_1d"] = returns
    frame["spy_return_5d"] = frame["px_close"].pct_change(5)
    frame["spy_realized_vol_5d"] = returns.rolling(5, min_periods=3).std(ddof=0)
    return frame[["date", "spy_return_1d", "spy_return_5d", "spy_realized_vol_5d"]]


def _safe_return(end: float, start: float) -> float:
    return end / start - 1.0 if np.isfinite(end) and np.isfinite(start) and start > 0 else np.nan


def build_position_states(
    fixed_trades: pd.DataFrame, bars: pd.DataFrame, oracle: pd.DataFrame,
    *, config: KeepExitDatasetConfig,
) -> pd.DataFrame:
    """Crée les snapshots quotidiens PIT et leurs labels futurs séparés."""
    required_trades = {
        "signal_date", "symbol", "entry_date", "entry_price", "exit_date",
        "exit_price", "exit_reason", "net_return",
    }
    missing = required_trades - set(fixed_trades.columns)
    if missing:
        raise ValueError(f"Trades H20 incomplets: {sorted(missing)}")
    trades = fixed_trades.copy()
    for column in ("signal_date", "entry_date", "exit_date"):
        trades[column] = pd.to_datetime(trades[column], errors="coerce").dt.normalize()
    trades["symbol"] = trades["symbol"].astype(str).str.upper()
    if trades.duplicated(["signal_date", "symbol"]).any():
        raise ValueError("Trades H20 dupliqués pour (signal_date, symbol).")

    oracle_lookup = oracle.set_index(["date", "symbol"]).to_dict(orient="index")
    bars_by_symbol = dict(tuple(bars.groupby("symbol", sort=False)))
    market = prepare_market_features(bars[bars["symbol"].eq("SPY")])
    market_lookup = market.set_index("date").to_dict(orient="index")
    rows: list[dict[str, Any]] = []

    for trade in trades.itertuples(index=False):
        symbol = str(trade.symbol)
        symbol_bars = bars_by_symbol.get(symbol)
        if symbol_bars is None:
            continue
        sb = symbol_bars.sort_values("date").reset_index(drop=True)
        entry_hits = sb.index[sb["date"].eq(trade.entry_date)]
        if len(entry_hits) != 1:
            continue
        entry_index = int(entry_hits[0])
        entry_price = float(trade.entry_price)
        atr = float(sb.iloc[entry_index]["entry_atr20"])
        previous_close = float(sb.iloc[entry_index]["previous_close"])
        if not all(np.isfinite(value) and value > 0 for value in (entry_price, atr, previous_close)):
            continue
        atr_pct = atr / previous_close
        take_profit = entry_price * (1.0 + min(config.tp_atr_multiple * atr_pct, config.tp_max_pct))
        initial_stop = entry_price * (1.0 - config.initial_stop_atr_multiple * atr_pct)
        peak = entry_price
        trough = entry_price
        trade_id = f"{pd.Timestamp(trade.signal_date):%Y%m%d}:{symbol}"

        for offset in range(config.fixed_holding_sessions):
            index = entry_index + offset
            if index + 1 >= len(sb):
                break
            state = sb.iloc[index]
            state_date = pd.Timestamp(state["date"])
            if state_date >= pd.Timestamp(trade.exit_date):
                break
            next_row = sb.iloc[index + 1]
            execution_date = pd.Timestamp(next_row["date"])
            if execution_date > pd.Timestamp(trade.exit_date):
                break
            # À H20 la sortie au prochain open est imposée par le témoin : il
            # n'existe plus de choix KEEP/EXIT à apprendre.
            if trade.exit_reason == "fixed_h20" and execution_date == pd.Timestamp(trade.exit_date):
                break

            peak = max(peak, float(state["px_high"]))
            trough = min(trough, float(state["px_low"]))
            close = float(state["px_close"])
            active_stop = (
                initial_stop if offset == 0
                else peak * (1.0 - config.trailing_atr_multiple * atr_pct)
            )
            # Les indicateurs techniques utilisent tout l'historique PIT
            # disponible, pas seulement les observations depuis l'entrée.
            history = sb.iloc[max(0, index - 20):index + 1]
            closes = history["px_close"]
            daily_returns = closes.pct_change()
            volume_ratio = np.nan
            if "volume" in history and len(history) >= 2:
                volume = pd.to_numeric(history["volume"], errors="coerce")
                denominator = volume.tail(20).mean()
                if np.isfinite(denominator) and denominator > 0:
                    volume_ratio = float(volume.iloc[-1] / denominator)

            immediate_exit_net = _safe_return(float(next_row["px_open"]), entry_price) - config.round_trip_cost
            keep_terminal_net = float(trade.net_return)
            future_residual = _safe_return(float(trade.exit_price), float(next_row["px_open"]))
            future = sb.iloc[index + 1:min(index + 6, len(sb))]
            future_h3 = sb.iloc[index + 3]["px_close"] if index + 3 < len(sb) else np.nan
            future_h5 = sb.iloc[index + 5]["px_close"] if index + 5 < len(sb) else np.nan
            future_label_index = min(index + 5, len(sb) - 1)
            label_end_date = max(
                pd.Timestamp(trade.exit_date),
                pd.Timestamp(sb.iloc[future_label_index]["date"]),
            )
            oracle_values = oracle_lookup.get((state_date, symbol), {})
            market_values = market_lookup.get(state_date, {})
            ret1 = closes.pct_change(1).iloc[-1] if len(closes) > 1 else np.nan
            ret3 = closes.pct_change(3).iloc[-1] if len(closes) > 3 else np.nan
            ret5 = closes.pct_change(5).iloc[-1] if len(closes) > 5 else np.nan
            row = {
                "trade_id": trade_id, "signal_date": trade.signal_date,
                "symbol": symbol, "entry_date": trade.entry_date,
                "state_date": state_date, "execution_date": execution_date,
                "terminal_date": trade.exit_date,
                "terminal_exit_reason": trade.exit_reason,
                "holding_session": offset + 1,
                "remaining_sessions_h20": config.fixed_holding_sessions - (offset + 1),
                "entry_atr_pct": atr_pct,
                "current_pnl_gross": _safe_return(close, entry_price),
                "current_pnl_net": _safe_return(close, entry_price) - config.round_trip_cost,
                "mfe_so_far": _safe_return(peak, entry_price),
                "mae_so_far": _safe_return(trough, entry_price),
                "drawdown_from_peak": _safe_return(close, peak),
                "distance_to_tp": _safe_return(take_profit, close),
                "distance_to_active_stop": _safe_return(close, active_stop),
                "return_1d": ret1, "return_3d": ret3, "return_5d": ret5,
                "realized_vol_5d": daily_returns.tail(5).std(ddof=0),
                "realized_vol_10d": daily_returns.tail(10).std(ddof=0),
                "volume_ratio_20d": volume_ratio,
                "immediate_exit_net": immediate_exit_net,
                "keep_terminal_net": keep_terminal_net,
                "target_keep_advantage": keep_terminal_net - immediate_exit_net,
                "target_future_residual": future_residual,
                "label_keep": float(future_residual > 0),
                "label_tp_before_stop": float(trade.exit_reason == "take_profit"),
                "label_stop_before_tp": float(trade.exit_reason in {"initial_stop", "trailing_stop"}),
                "future_return_h3": _safe_return(float(future_h3), float(next_row["px_open"])),
                "future_return_h5": _safe_return(float(future_h5), float(next_row["px_open"])),
                "future_mfe_h5": _safe_return(float(future["px_high"].max()), float(next_row["px_open"])) if not future.empty else np.nan,
                "future_mae_h5": _safe_return(float(future["px_low"].min()), float(next_row["px_open"])) if not future.empty else np.nan,
                # La purge couvre aussi les labels diagnostiques H3/H5, qui
                # peuvent dépasser la sortie du lifecycle témoin.
                "label_end_date": label_end_date,
            }
            row.update({column: oracle_values.get(column, np.nan) for column in [
                "pct_h5", "pct_h10", "pct_h15", "pct_h20", "consensus_mean",
                "consensus_std", "consensus_rank", "oracle_h5_delta_1d",
                "oracle_h5_delta_3d", "oracle_h5_top20",
            ]})
            row.update({column: market_values.get(column, np.nan) for column in [
                "spy_return_1d", "spy_return_5d", "spy_realized_vol_5d",
            ]})
            row["relative_return_1d"] = ret1 - row["spy_return_1d"]
            row["relative_return_5d"] = ret5 - row["spy_return_5d"]
            rows.append(row)

    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("Aucun état quotidien E7 construit.")
    if not (result["state_date"] < result["execution_date"]).all():
        raise AssertionError("Horloge invalide: state_date doit précéder execution_date.")
    if not (result["execution_date"] <= result["label_end_date"]).all():
        raise AssertionError("Horloge invalide: exécution postérieure au label.")
    return result.sort_values(["state_date", "symbol", "trade_id"]).reset_index(drop=True)


def audit_univariate(states: pd.DataFrame, *, min_states: int) -> pd.DataFrame:
    """Audit descriptif; aucun seuil de trading n'est sélectionné ici."""
    rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLUMNS:
        values = pd.to_numeric(states[feature], errors="coerce")
        valid = states.loc[values.notna(), ["label_keep", "target_keep_advantage"]].copy()
        valid["value"] = values[values.notna()]
        if len(valid) < max(min_states, 10) or valid["value"].nunique() < 2:
            continue
        try:
            valid["bin"] = pd.qcut(valid["value"], q=10, duplicates="drop")
        except ValueError:
            continue
        for order, (_, group) in enumerate(valid.groupby("bin", observed=True), start=1):
            rows.append({
                "feature": feature, "bin_order": order, "states": len(group),
                "value_min": group["value"].min(), "value_max": group["value"].max(),
                "keep_rate": group["label_keep"].mean(),
                "mean_keep_advantage": group["target_keep_advantage"].mean(),
            })
    return pd.DataFrame(rows)


def summarize_quality(states: pd.DataFrame) -> dict[str, Any]:
    feature_coverage = states[FEATURE_COLUMNS].notna().mean().sort_values()
    per_trade = states.groupby("trade_id").size()
    semesters = (
        states.assign(semester=states["state_date"].dt.year.astype(str) + "H" +
                      np.where(states["state_date"].dt.month.le(6), "1", "2"))
        .groupby("semester")
        .agg(states=("trade_id", "size"), trades=("trade_id", "nunique"),
             keep_rate=("label_keep", "mean"),
             mean_keep_advantage=("target_keep_advantage", "mean"))
        .reset_index()
    )
    return {
        "states": int(len(states)), "trades": int(states["trade_id"].nunique()),
        "date_start": str(states["state_date"].min().date()),
        "date_end": str(states["state_date"].max().date()),
        "keep_rate": float(states["label_keep"].mean()),
        "mean_keep_advantage": float(states["target_keep_advantage"].mean()),
        "forced_horizon_states": int(
            ((states["terminal_exit_reason"] == "fixed_h20")
             & (states["execution_date"] == states["terminal_date"])).sum()
        ),
        "states_per_trade": {
            "mean": float(per_trade.mean()), "median": float(per_trade.median()),
            "max": int(per_trade.max()),
        },
        "feature_coverage": {key: float(value) for key, value in feature_coverage.items()},
        "semesters": semesters.to_dict(orient="records"),
    }


def run(
    lifecycle_artifact: Path, *, output_root: Path, config: KeepExitDatasetConfig,
) -> Path:
    trades_path = lifecycle_artifact / "paired_trades.parquet"
    report_path = lifecycle_artifact / "report.json"
    if not trades_path.is_file() or not report_path.is_file():
        raise ValueError("Artefact lifecycle V2 incomplet.")
    lifecycle_report = json.loads(report_path.read_text(encoding="utf-8"))
    phase1_artifact = Path(lifecycle_report["source_phase1_artifact"])
    aligned_path = phase1_artifact / "aligned_predictions.parquet"
    if not aligned_path.is_file():
        raise ValueError(f"Artefact Oracle aligné absent: {aligned_path}")
    trades = pd.read_parquet(trades_path)
    fixed = trades[trades["policy"].eq("fixed_h20")].copy()
    oracle = prepare_oracle_features(pd.read_parquet(aligned_path))
    symbols = sorted(set(fixed["symbol"].astype(str)) | {"SPY"})
    start = (pd.Timestamp(fixed["entry_date"].min()) - pd.offsets.BDay(30)).date()
    end = (pd.Timestamp(fixed["exit_date"].max()) + pd.offsets.BDay(6)).date()
    bars = prepare_bars(load_universe_bars(
        get_sqlalchemy_engine(), symbols, start_date=start, end_date=end,
    ))
    states = build_position_states(fixed, bars, oracle, config=config)
    univariate = audit_univariate(states, min_states=config.min_states_per_bin)
    quality = summarize_quality(states)
    run_id = f"position-keep-exit-dataset-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    states.to_parquet(output / "position_states.parquet", index=False)
    univariate.to_csv(output / "univariate_deciles.csv", index=False)
    pd.DataFrame({"feature": FEATURE_COLUMNS}).to_csv(output / "feature_contract.csv", index=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "e7_daily_position_keep_exit_dataset",
        "stage": "E7-A_DATASET_AUDIT", "status": "complete",
        "research_only": True, "training_authorized": False,
        "source_lifecycle_artifact": str(lifecycle_artifact),
        "source_lifecycle_sha256": _sha256(trades_path),
        "source_phase1_artifact": str(phase1_artifact),
        "source_oracle_sha256": _sha256(aligned_path),
        "generated_at": datetime.now(UTC).isoformat(), "config": asdict(config),
        "identity_columns": IDENTITY_COLUMNS, "feature_columns": FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS, "quality": quality,
        "leakage_contract": {
            "feature_cutoff": "state_date_close",
            "decision_execution": "next_symbol_session_open",
            "group_key": "trade_id",
            "purge_requirement": "label_end_date strictly before next evaluation block",
            "symbol_is_feature": False,
            "targets_excluded_from_features": True,
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E7-A dataset terminé: %s states=%s trades=%s", output, len(states), quality["trades"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lifecycle-artifact", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/position_keep_exit"))
    parser.add_argument("--min-states-per-bin", type=int, default=100)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    print(run(
        args.lifecycle_artifact, output_root=args.output_root,
        config=KeepExitDatasetConfig(min_states_per_bin=args.min_states_per_bin),
    ))


if __name__ == "__main__":
    main()
