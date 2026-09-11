"""Replay research-only de la variante 2 Oracle rolling H5.

Entrée LONG retardée à J+6 après H20 TOP20, prix J->J+5 positif et consensus
restant confirmé. Trois politiques appariées sont rejouées avec le lifecycle
PROD : H20 fixe, extension 60 séances sans rolling, extension 60 séances avec
contrôle H5 + PnL net positif tous les cinq jours.
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

from backtesting.microstructure import resolve_intrabar_exit, should_skip_entry_for_gap
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean

LOGGER = logging.getLogger(__name__)
POLICIES = ("fixed_h20", "extended_60_no_rolling", "rolling_h5_60")


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    initial_stop_atr_multiple: float = 2.5
    trailing_atr_multiple: float = 2.5
    tp_atr_multiple: float = 3.0
    tp_max_pct: float = 0.07
    max_entry_gap_pct: float = 0.03
    checkpoint_sessions: int = 5
    fixed_holding_sessions: int = 20
    max_holding_sessions: int = 60
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    bootstrap_samples: int = 2_000

    def __post_init__(self) -> None:
        if not 0 < self.checkpoint_sessions <= self.fixed_holding_sessions:
            raise ValueError("checkpoint_sessions invalide.")
        if self.max_holding_sessions <= self.fixed_holding_sessions:
            raise ValueError("max_holding_sessions doit dépasser H20.")
        if min(
            self.initial_stop_atr_multiple, self.trailing_atr_multiple,
            self.tp_atr_multiple, self.tp_max_pct,
        ) <= 0:
            raise ValueError("Les paramètres de protection doivent être positifs.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0


def prepare_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Ajuste OHLC et calcule ATR20 disponible à la clôture précédente."""
    required = {"symbol", "date", "open", "high", "low", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"Colonnes OHLC absentes: {sorted(missing)}")
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    for column in ("open", "high", "low", "close", "adj_close"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "adj_close" in frame:
        factor = frame["adj_close"] / frame["close"].replace(0, np.nan)
        frame["px_close"] = frame["adj_close"].where(frame["adj_close"].gt(0), frame["close"])
    else:
        factor = pd.Series(1.0, index=frame.index)
        frame["px_close"] = frame["close"]
    for column in ("open", "high", "low"):
        frame[f"px_{column}"] = (frame[column] * factor).where(factor.gt(0), frame[column])
    frame = frame.dropna(subset=["date", "symbol", "px_open", "px_high", "px_low", "px_close"])
    frame = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = frame.groupby("symbol", sort=False)
    previous_close = grouped["px_close"].shift(1)
    true_range = pd.concat([
        frame["px_high"] - frame["px_low"],
        (frame["px_high"] - previous_close).abs(),
        (frame["px_low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    frame["atr20"] = true_range.groupby(frame["symbol"]).transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    # L'ATR utilisable à l'open d'entrée est celui calculé au close précédent.
    frame["entry_atr20"] = frame.groupby("symbol")["atr20"].shift(1)
    frame["previous_close"] = previous_close
    return frame


def build_delayed_candidates(events: pd.DataFrame) -> pd.DataFrame:
    """Freeze de l'entrée : H20 TOP20, prix J->J+5 positif, consensus confirmé."""
    required = {
        "date", "symbol", "mh0", "px_close", "cp5_close", "cp5_date",
        "cp5_exit_open", "cp5_oracle_confirmed",
    }
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"Artefact phase 1 incomplet: {sorted(missing)}")
    candidates = events[
        events["mh0"]
        & events["cp5_oracle_confirmed"]
        & (events["cp5_close"] / events["px_close"] - 1.0).gt(0)
    ].copy()
    candidates["decision_date"] = pd.to_datetime(candidates["cp5_date"]).dt.normalize()
    return candidates.sort_values(["date", "symbol"]).reset_index(drop=True)


def _exit_payload(
    *, policy: str, signal_date: pd.Timestamp, symbol: str,
    entry_date: pd.Timestamp, entry_price: float, exit_date: pd.Timestamp,
    exit_price: float, exit_reason: str, holding_sessions: int,
    config: LifecycleConfig, checkpoints_passed: int,
) -> dict[str, Any]:
    gross = exit_price / entry_price - 1.0
    return {
        "policy": policy, "signal_date": signal_date, "symbol": symbol,
        "entry_date": entry_date, "entry_price": entry_price,
        "exit_date": exit_date, "exit_price": exit_price,
        "exit_reason": exit_reason, "holding_sessions": holding_sessions,
        "checkpoints_passed": checkpoints_passed,
        "gross_return": gross, "net_return": gross - config.round_trip_cost,
    }


def simulate_trade(
    symbol_bars: pd.DataFrame, *, signal_date: pd.Timestamp,
    decision_date: pd.Timestamp, policy: str, h5_rank: dict[tuple[pd.Timestamp, str], float],
    config: LifecycleConfig,
) -> dict[str, Any] | None:
    """Rejoue une entrée avec l'horloge et la résolution conservative PROD."""
    if policy not in POLICIES:
        raise ValueError(f"Politique inconnue: {policy}")
    bars = symbol_bars.reset_index(drop=True)
    matches = bars.index[bars["date"].gt(pd.Timestamp(decision_date).normalize())]
    if len(matches) < 1:
        return None
    entry_index = int(matches[0])
    if entry_index == 0 or entry_index + config.max_holding_sessions >= len(bars):
        return None
    entry = bars.iloc[entry_index]
    entry_date = pd.Timestamp(entry["date"])
    entry_price = float(entry["px_open"])
    previous_close = float(entry["previous_close"])
    atr = float(entry["entry_atr20"])
    if not all(np.isfinite(value) and value > 0 for value in (entry_price, previous_close, atr)):
        return None
    if should_skip_entry_for_gap(previous_close, entry_price, max_gap_pct=config.max_entry_gap_pct):
        return {"policy": policy, "signal_date": signal_date, "symbol": str(entry["symbol"]),
                "entry_date": entry_date, "exit_reason": "entry_gap_rejected"}
    atr_pct = atr / previous_close
    initial_stop = entry_price * (1.0 - config.initial_stop_atr_multiple * atr_pct)
    trail_pct = config.trailing_atr_multiple * atr_pct
    take_profit = entry_price * (1.0 + min(config.tp_atr_multiple * atr_pct, config.tp_max_pct))
    previous_peak = entry_price
    checkpoints_passed = 0
    symbol = str(entry["symbol"])
    limit = config.fixed_holding_sessions if policy == "fixed_h20" else config.max_holding_sessions
    if policy == "rolling_h5_60":
        checkpoint_rows = [
            bars.iloc[entry_index + session - 1]
            for session in range(config.checkpoint_sessions, limit + 1, config.checkpoint_sessions)
        ]
        if any(
            (pd.Timestamp(row["date"]).normalize(), symbol) not in h5_rank
            for row in checkpoint_rows
        ):
            return None

    for holding_session in range(1, limit + 1):
        row = bars.iloc[entry_index + holding_session - 1]
        trailing_active = holding_session >= 2
        trailing_stop = previous_peak * (1.0 - trail_pct) if trailing_active else float("-inf")
        resolution = resolve_intrabar_exit(
            day_high=float(row["px_high"]), day_low=float(row["px_low"]),
            take_profit_price=take_profit, trailing_stop_price=trailing_stop,
            initial_stop_price=None if trailing_active else initial_stop,
            priority="conservative", side="buy",
        )
        if resolution.triggered:
            return _exit_payload(
                policy=policy, signal_date=signal_date, symbol=symbol,
                entry_date=pd.Timestamp(entry_date), entry_price=entry_price,
                exit_date=pd.Timestamp(row["date"]), exit_price=float(resolution.exit_price),
                exit_reason=resolution.exit_reason, holding_sessions=holding_session,
                config=config, checkpoints_passed=checkpoints_passed,
            )
        previous_peak = max(previous_peak, float(row["px_high"]))

        checkpoint = holding_session % config.checkpoint_sessions == 0
        if policy == "rolling_h5_60" and checkpoint:
            close_net = float(row["px_close"]) / entry_price - 1.0 - config.round_trip_cost
            rank = h5_rank.get((pd.Timestamp(row["date"]).normalize(), symbol))
            confirmed = rank is not None and np.isfinite(rank) and rank >= 0.80
            if close_net <= 0 or not confirmed:
                next_row = bars.iloc[entry_index + holding_session]
                reason = "rolling_price_nonpositive" if close_net <= 0 else "rolling_h5_not_confirmed"
                return _exit_payload(
                    policy=policy, signal_date=signal_date, symbol=symbol,
                    entry_date=pd.Timestamp(entry_date), entry_price=entry_price,
                    exit_date=pd.Timestamp(next_row["date"]), exit_price=float(next_row["px_open"]),
                    exit_reason=reason, holding_sessions=holding_session,
                    config=config, checkpoints_passed=checkpoints_passed,
                )
            checkpoints_passed += 1

        if holding_session == limit:
            next_row = bars.iloc[entry_index + holding_session]
            reason = "fixed_h20" if policy == "fixed_h20" else "max_holding_60"
            return _exit_payload(
                policy=policy, signal_date=signal_date, symbol=symbol,
                entry_date=pd.Timestamp(entry_date), entry_price=entry_price,
                exit_date=pd.Timestamp(next_row["date"]), exit_price=float(next_row["px_open"]),
                exit_reason=reason, holding_sessions=holding_session,
                config=config, checkpoints_passed=checkpoints_passed,
            )
    return None


def simulate_paired(
    candidates: pd.DataFrame, bars: pd.DataFrame, aligned: pd.DataFrame,
    config: LifecycleConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars_by_symbol = dict(tuple(bars.groupby("symbol", sort=False)))
    h5_rank = {
        (pd.Timestamp(row.date).normalize(), str(row.symbol)): float(row.pct_h5)
        for row in aligned[["date", "symbol", "pct_h5"]].itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates.itertuples(index=False):
        symbol = str(candidate.symbol)
        symbol_bars = bars_by_symbol.get(symbol)
        if symbol_bars is None:
            rejected.append({"signal_date": candidate.date, "symbol": symbol, "reason": "bars_missing"})
            continue
        simulations = [simulate_trade(
            symbol_bars, signal_date=pd.Timestamp(candidate.date),
            decision_date=pd.Timestamp(candidate.decision_date), policy=policy,
            h5_rank=h5_rank, config=config,
        ) for policy in POLICIES]
        if any(result is None for result in simulations):
            rejected.append({"signal_date": candidate.date, "symbol": symbol, "reason": "incomplete_60_session_window"})
            continue
        if any(result.get("exit_reason") == "entry_gap_rejected" for result in simulations if result):
            rejected.append({"signal_date": candidate.date, "symbol": symbol, "reason": "entry_gap_rejected"})
            continue
        rows.extend(result for result in simulations if result)
    return pd.DataFrame(rows), pd.DataFrame(rejected)


def summarize(trades: pd.DataFrame, config: LifecycleConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    semesters: list[dict[str, Any]] = []
    for policy, group in trades.groupby("policy", sort=False):
        daily = group.groupby("signal_date")["net_return"].mean().sort_index()
        ci = block_bootstrap_mean(
            daily, RollingConfig(bootstrap_samples=config.bootstrap_samples)
        )
        summaries.append({
            "policy": policy, "trades": int(len(group)),
            "mean_net_return": float(group["net_return"].mean()),
            "median_net_return": float(group["net_return"].median()),
            "win_rate": float(group["net_return"].gt(0).mean()),
            "q05": float(group["net_return"].quantile(0.05)),
            "q01": float(group["net_return"].quantile(0.01)),
            "mean_holding_sessions": float(group["holding_sessions"].mean()),
            "daily_mean_ci95_low": ci[0], "daily_mean_ci95_high": ci[1],
        })
        part = group.copy()
        part["semester"] = part["signal_date"].dt.year.astype(str) + "H" + np.where(
            part["signal_date"].dt.month.le(6), "1", "2"
        )
        for semester, semester_group in part.groupby("semester"):
            semesters.append({"policy": policy, "semester": semester,
                              "trades": len(semester_group),
                              "mean_net_return": semester_group["net_return"].mean()})
    pivot = trades.pivot(index=["signal_date", "symbol"], columns="policy", values="net_return").dropna()
    comparisons: dict[str, Any] = {}
    for challenger in ("extended_60_no_rolling", "rolling_h5_60"):
        delta = (pivot[challenger] - pivot["fixed_h20"]).rename("delta").reset_index()
        daily = delta.groupby("signal_date")["delta"].mean().sort_index()
        low, high = block_bootstrap_mean(
            daily, RollingConfig(bootstrap_samples=config.bootstrap_samples)
        )
        comparisons[challenger] = {
            "paired_trades": int(len(delta)), "mean_delta": float(delta["delta"].mean()),
            "paired_daily_delta": float(daily.mean()), "paired_daily_ci95": [low, high],
            "positive_delta_rate": float(delta["delta"].gt(0).mean()),
        }
    extension_delta = (pivot["rolling_h5_60"] - pivot["extended_60_no_rolling"]).rename("delta").reset_index()
    extension_daily = extension_delta.groupby("signal_date")["delta"].mean().sort_index()
    low, high = block_bootstrap_mean(
        extension_daily, RollingConfig(bootstrap_samples=config.bootstrap_samples)
    )
    comparisons["rolling_vs_same_60_day_extension"] = {
        "paired_trades": int(len(extension_delta)),
        "mean_delta": float(extension_delta["delta"].mean()),
        "paired_daily_delta": float(extension_daily.mean()),
        "paired_daily_ci95": [low, high],
        "positive_delta_rate": float(extension_delta["delta"].gt(0).mean()),
    }
    return pd.DataFrame(summaries), pd.DataFrame(semesters), comparisons


def run(
    phase1_artifact: Path, *, output_root: Path, config: LifecycleConfig,
) -> Path:
    aligned_path = phase1_artifact / "aligned_predictions.parquet"
    events_path = phase1_artifact / "fixed_origin_events.parquet"
    if not aligned_path.is_file() or not events_path.is_file():
        raise ValueError("Artefact phase 1 incomplet.")
    aligned = pd.read_parquet(aligned_path)
    events = pd.read_parquet(events_path)
    candidates = build_delayed_candidates(events)
    symbols = sorted(candidates["symbol"].unique())
    start = (pd.Timestamp(candidates["decision_date"].min()) - pd.offsets.BDay(25)).date()
    end = (pd.Timestamp(candidates["decision_date"].max()) + pd.offsets.BDay(
        config.max_holding_sessions + 5
    )).date()
    bars = prepare_bars(load_universe_bars(
        get_sqlalchemy_engine(), symbols, start_date=start, end_date=end,
    ))
    trades, rejected = simulate_paired(candidates, bars, aligned, config)
    if trades.empty:
        raise ValueError("Aucun trade évaluable pour la variante 2.")
    summary, semesters, comparisons = summarize(trades, config)
    run_id = f"oracle-rolling-lifecycle-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    trades.to_parquet(output / "paired_trades.parquet", index=False)
    rejected.to_csv(output / "rejected_candidates.csv", index=False)
    summary.to_csv(output / "policy_summary.csv", index=False)
    semesters.to_csv(output / "policy_by_semester.csv", index=False)
    trades.groupby(["policy", "exit_reason"]).agg(
        trades=("net_return", "size"), mean_net_return=("net_return", "mean")
    ).reset_index().to_csv(output / "exit_attribution.csv", index=False)
    rolling_delta = comparisons["rolling_vs_same_60_day_extension"]
    ci_low = rolling_delta["paired_daily_ci95"][0]
    verdict = (
        "GO_RESEARCH" if rolling_delta["mean_delta"] > 0 and np.isfinite(ci_low) and ci_low > 0
        else "WEAK_SIGNAL" if rolling_delta["mean_delta"] > 0
        else "NO_GO"
    )
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "oracle_delayed_long_rolling_h5_lifecycle_v2",
        "status": "complete", "research_only": True,
        "source_phase1_artifact": str(phase1_artifact),
        "generated_at": datetime.now(UTC).isoformat(),
        "config": asdict(config), "candidates": int(len(candidates)),
        "paired_candidates": int(trades[["signal_date", "symbol"]].drop_duplicates().shape[0]),
        "rejected_candidates": int(len(rejected)),
        "policy_summary": summary.to_dict(orient="records"),
        "comparisons": comparisons, "verdict": verdict,
        "promotion_authorized": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("Replay rolling lifecycle terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase1-artifact", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/oracle_rolling_lifecycle"))
    parser.add_argument("--max-holding-sessions", type=int, default=60)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    print(run(
        args.phase1_artifact, output_root=args.output_root,
        config=LifecycleConfig(
            max_holding_sessions=args.max_holding_sessions,
            bootstrap_samples=args.bootstrap_samples,
        ),
    ))


if __name__ == "__main__":
    main()
