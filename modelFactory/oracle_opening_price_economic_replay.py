"""E20-D — replay économique de la confirmation Opening Window price-only.

Recherche uniquement. Le signal est connu au checkpoint de 30 minutes et
l'entrée se fait au dernier prix observé à ce checkpoint. Deux traitements de
la séance d'entrée encadrent l'incertitude intraday après 10:00.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from backtesting.microstructure import resolve_intrabar_exit, should_skip_entry_for_gap
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import block_bootstrap_mean
from modelFactory.oracle_monetization_bridge import E12Config
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)
EntryDayPolicy = Literal["full_day_conservative", "next_session_protection"]


@dataclass(frozen=True, slots=True)
class E20DConfig:
    checkpoint_minutes: int = 30
    direction_threshold: float = 0.005
    horizon: int = 20
    max_positions: int = 8
    initial_stop_atr_multiple: float = 2.5
    trailing_atr_multiple: float = 2.5
    tp_atr_multiple: float = 3.0
    tp_max_pct: float = 0.07
    max_entry_gap_pct: float = 0.03
    minimum_price: float = 10.0
    minimum_adv_usd: float = 1_000_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    short_borrow_annual_rate: float = 0.003
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260914
    minimum_portfolio_trades: int = 500
    minimum_positive_semester_ratio: float = 0.60

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0

    def bootstrap_config(self):
        return E12Config(
            bootstrap_samples=self.bootstrap_samples,
            bootstrap_block_sessions=self.bootstrap_block_sessions,
            bootstrap_seed=self.bootstrap_seed,
        ).bootstrap_config()


def select_price_confirmed(events: pd.DataFrame, config: E20DConfig) -> pd.DataFrame:
    required = {
        "date", "target_session", "symbol", "price_30m", "return_30m",
        "opening_price", "directional_oracle_proba_extreme", "oracle_decile",
    }
    if missing := required - set(events.columns):
        raise ValueError(f"Événements E20-B incomplets: {sorted(missing)}")
    frame = events.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["target_session"] = pd.to_datetime(
        frame["target_session"], errors="coerce"
    ).dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    score = pd.to_numeric(frame["return_30m"], errors="coerce")
    frame["direction"] = np.select(
        [score.gt(config.direction_threshold), score.lt(-config.direction_threshold)],
        [1, -1], default=0,
    )
    return frame[
        frame["direction"].ne(0)
        & pd.to_numeric(frame["price_30m"], errors="coerce").gt(0)
    ].sort_values(["target_session", "symbol"]).reset_index(drop=True)


def _return(side: int, exit_price: float, entry_price: float) -> float:
    return side * (exit_price / entry_price - 1.0)


def simulate_delayed_trade(
    symbol_bars: pd.DataFrame, event: Any, *, policy: EntryDayPolicy,
    config: E20DConfig,
) -> dict[str, Any] | None:
    bars = symbol_bars.sort_values("date").reset_index(drop=True)
    matches = bars.index[bars["date"].eq(pd.Timestamp(event.target_session))]
    if len(matches) != 1:
        return None
    entry_index = int(matches[0])
    if entry_index + config.horizon >= len(bars):
        return None
    entry_row = bars.iloc[entry_index]
    raw_close = float(entry_row["close"])
    adjustment_factor = float(entry_row["px_close"]) / raw_close if raw_close > 0 else np.nan
    entry_price = float(event.price_30m) * adjustment_factor
    opening_price = float(event.opening_price) * adjustment_factor
    previous_close = float(entry_row["previous_close"])
    atr = float(entry_row["entry_atr20"])
    adv = float(entry_row["adv20"])
    if not all(np.isfinite(value) and value > 0 for value in (
        entry_price, opening_price, previous_close, atr, adjustment_factor,
    )):
        return None
    if should_skip_entry_for_gap(
        previous_close, opening_price, max_gap_pct=config.max_entry_gap_pct
    ):
        return {"rejected": True, "rejection_reason": "opening_gap"}
    if entry_price < config.minimum_price:
        return {"rejected": True, "rejection_reason": "minimum_price"}
    if not np.isfinite(adv) or adv < config.minimum_adv_usd:
        return {"rejected": True, "rejection_reason": "minimum_adv"}

    side = int(event.direction)
    terminal = bars.iloc[entry_index + config.horizon]
    terminal_price = float(terminal["px_open"])
    terminal_borrow = (
        config.short_borrow_annual_rate * config.horizon / 252.0
        if side == -1 else 0.0
    )
    delayed_fixed_h20_net = (
        _return(side, terminal_price, entry_price)
        - config.round_trip_cost - terminal_borrow
    )
    next_open_fixed_h20_net = (
        _return(side, terminal_price, opening_price)
        - config.round_trip_cost - terminal_borrow
    )
    counterfactual = {
        "delayed_fixed_h20_net": delayed_fixed_h20_net,
        "next_open_fixed_h20_net": next_open_fixed_h20_net,
        "delay_impact_fixed_h20": delayed_fixed_h20_net - next_open_fixed_h20_net,
    }
    atr_pct = atr / previous_close
    risk = entry_price * config.initial_stop_atr_multiple * atr_pct
    initial_stop = entry_price - side * risk
    distance = min(config.tp_atr_multiple * atr_pct, config.tp_max_pct)
    take_profit = entry_price * (1.0 + side * distance)
    trailing_pct = config.trailing_atr_multiple * atr_pct
    favorable_extreme = entry_price
    mfe, mae = 0.0, 0.0
    start_offset = 0 if policy == "full_day_conservative" else 1
    for offset in range(start_offset, config.horizon):
        row = bars.iloc[entry_index + offset]
        holding_session = offset + 1
        trailing_active = holding_session >= 2
        trailing_stop = (
            favorable_extreme * (1.0 - trailing_pct) if side == 1
            else favorable_extreme * (1.0 + trailing_pct)
        ) if trailing_active else (-np.inf if side == 1 else np.inf)
        resolution = resolve_intrabar_exit(
            day_high=float(row["px_high"]), day_low=float(row["px_low"]),
            take_profit_price=take_profit, trailing_stop_price=trailing_stop,
            initial_stop_price=None if trailing_active else initial_stop,
            priority="conservative", side="buy" if side == 1 else "sell",
        )
        high_return = _return(side, float(row["px_high"]), entry_price)
        low_return = _return(side, float(row["px_low"]), entry_price)
        mfe = max(mfe, high_return, low_return)
        mae = min(mae, high_return, low_return)
        if resolution.triggered:
            exit_price = float(resolution.exit_price)
            gross = _return(side, exit_price, entry_price)
            borrow = (
                config.short_borrow_annual_rate * holding_session / 252.0
                if side == -1 else 0.0
            )
            return {
                "rejected": False, "entry_date": pd.Timestamp(event.target_session),
                "entry_price": entry_price, "exit_date": pd.Timestamp(row["date"]),
                "exit_price": exit_price, "exit_reason": resolution.exit_reason,
                "holding_sessions": holding_session, "gross_return": gross,
                "net_return": gross - config.round_trip_cost - borrow,
                "borrow_cost": borrow, "mfe": mfe, "mae": mae, **counterfactual,
            }
        favorable_extreme = (
            max(favorable_extreme, float(row["px_high"])) if side == 1
            else min(favorable_extreme, float(row["px_low"]))
        )
    exit_price = terminal_price
    gross = _return(side, exit_price, entry_price)
    borrow = (
        config.short_borrow_annual_rate * config.horizon / 252.0
        if side == -1 else 0.0
    )
    return {
        "rejected": False, "entry_date": pd.Timestamp(event.target_session),
        "entry_price": entry_price, "exit_date": pd.Timestamp(terminal["date"]),
        "exit_price": exit_price, "exit_reason": "fixed_h20",
        "holding_sessions": config.horizon, "gross_return": gross,
        "net_return": gross - config.round_trip_cost - borrow,
        "borrow_cost": borrow, "mfe": mfe, "mae": mae, **counterfactual,
    }


def build_outcomes(events: pd.DataFrame, bars: pd.DataFrame, config: E20DConfig):
    prepared = prepare_bars(bars)
    prepared["dollar_volume"] = prepared["px_close"] * pd.to_numeric(
        prepared.get("volume"), errors="coerce"
    )
    prepared["adv20"] = prepared.groupby("symbol", sort=False)["dollar_volume"].transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    by_symbol = dict(tuple(prepared.groupby("symbol", sort=False)))
    outputs = {policy: [] for policy in ("full_day_conservative", "next_session_protection")}
    rejected: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        identity = {
            "signal_date": pd.Timestamp(event.date),
            "symbol": str(event.symbol), "direction": int(event.direction),
            "side": "LONG" if int(event.direction) == 1 else "SHORT",
            "oracle_score": float(event.directional_oracle_proba_extreme),
            "oracle_decile": int(event.oracle_decile),
        }
        symbol_bars = by_symbol.get(str(event.symbol))
        if symbol_bars is None:
            rejected.append({**identity, "policy": "all", "reason": "missing_bars"})
            continue
        for policy in outputs:
            result = simulate_delayed_trade(symbol_bars, event, policy=policy, config=config)
            if result is None or result.get("rejected"):
                rejected.append({
                    **identity, "policy": policy,
                    "reason": "missing_path" if result is None else result["rejection_reason"],
                })
                continue
            outputs[policy].append({**identity, "policy": policy, **result})
    return {key: pd.DataFrame(value) for key, value in outputs.items()}, pd.DataFrame(rejected)


def schedule_capacity(frame: pd.DataFrame, max_positions: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    active: dict[str, pd.Timestamp] = {}
    selected: list[int] = []
    for entry_date, group in frame.groupby("entry_date", sort=True):
        date = pd.Timestamp(entry_date)
        active = {symbol: end for symbol, end in active.items() if end >= date}
        slots = max_positions - len(active)
        if slots <= 0:
            continue
        candidates = group[~group["symbol"].isin(active)].sort_values(
            ["oracle_score", "symbol"], ascending=[False, True]
        )
        for row in candidates.head(slots).itertuples():
            selected.append(int(row.Index))
            active[str(row.symbol)] = pd.Timestamp(row.exit_date)
    return frame.loc[selected].sort_values(["entry_date", "symbol"]).reset_index(drop=True)


def summarize(frame: pd.DataFrame, config: E20DConfig) -> dict[str, Any]:
    if frame.empty:
        return {"trades": 0}
    daily = frame.groupby("entry_date")["net_return"].mean().sort_index()
    ci = block_bootstrap_mean(daily, config.bootstrap_config())
    fixed_daily = frame.groupby("entry_date")["delayed_fixed_h20_net"].mean().sort_index()
    fixed_ci = block_bootstrap_mean(fixed_daily, config.bootstrap_config())
    delay_daily = frame.groupby("entry_date")["delay_impact_fixed_h20"].mean().sort_index()
    delay_ci = block_bootstrap_mean(delay_daily, config.bootstrap_config())
    semesters = frame.assign(
        semester=frame["signal_date"].dt.year.astype(str) + "H"
        + np.where(frame["signal_date"].dt.month.le(6), "1", "2")
    ).groupby("semester")["net_return"].mean()
    sides = {
        side: {
            "trades": int(len(group)), "mean_net_return": float(group["net_return"].mean()),
            "win_rate": float(group["net_return"].gt(0).mean()),
        }
        for side, group in frame.groupby("side")
    }
    return {
        "trades": int(len(frame)), "dates": int(frame["entry_date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "mean_net_return": float(frame["net_return"].mean()),
        "median_net_return": float(frame["net_return"].median()),
        "win_rate": float(frame["net_return"].gt(0).mean()),
        "daily_mean_net_return": float(daily.mean()),
        "daily_ci95_low": float(ci[0]), "daily_ci95_high": float(ci[1]),
        "delayed_fixed_h20_mean": float(frame["delayed_fixed_h20_net"].mean()),
        "delayed_fixed_h20_daily_mean": float(fixed_daily.mean()),
        "delayed_fixed_h20_ci95_low": float(fixed_ci[0]),
        "delayed_fixed_h20_ci95_high": float(fixed_ci[1]),
        "next_open_fixed_h20_mean": float(frame["next_open_fixed_h20_net"].mean()),
        "delay_impact_fixed_h20_mean": float(frame["delay_impact_fixed_h20"].mean()),
        "delay_impact_fixed_h20_daily_mean": float(delay_daily.mean()),
        "delay_impact_fixed_h20_ci95_low": float(delay_ci[0]),
        "delay_impact_fixed_h20_ci95_high": float(delay_ci[1]),
        "q05": float(frame["net_return"].quantile(0.05)),
        "q01": float(frame["net_return"].quantile(0.01)),
        "mean_holding_sessions": float(frame["holding_sessions"].mean()),
        "normalized_capital_contribution": float(frame["net_return"].sum() / config.max_positions),
        "positive_semester_ratio": float(semesters.gt(0).mean()),
        "semester_returns": {str(key): float(value) for key, value in semesters.items()},
        "exit_reasons": frame["exit_reason"].value_counts().to_dict(),
        "by_side": sides,
    }


def paired_policy_delta(primary: pd.DataFrame, sensitivity: pd.DataFrame, config: E20DConfig):
    paired = primary[["signal_date", "symbol", "net_return"]].merge(
        sensitivity[["signal_date", "symbol", "net_return"]],
        on=["signal_date", "symbol"], suffixes=("_primary", "_sensitivity"),
        validate="one_to_one",
    )
    paired["delta"] = paired["net_return_sensitivity"] - paired["net_return_primary"]
    daily = paired.groupby("signal_date")["delta"].mean().sort_index()
    ci = block_bootstrap_mean(daily, config.bootstrap_config())
    return {
        "events": int(len(paired)), "mean_delta": float(paired["delta"].mean()),
        "daily_delta": float(daily.mean()), "ci95_low": float(ci[0]),
        "ci95_high": float(ci[1]),
    }


def run(*, events_path: Path, output_root: Path, config: E20DConfig) -> Path:
    events = select_price_confirmed(pd.read_parquet(events_path), config)
    symbols = sorted(events["symbol"].unique())
    start = events["date"].min() - pd.offsets.BDay(40)
    end = events["target_session"].max() + pd.offsets.BDay(config.horizon + 5)
    bars = load_universe_bars(
        get_sqlalchemy_engine(), symbols, start_date=start.date(), end_date=end.date()
    )
    outcomes, rejected = build_outcomes(events, bars, config)
    portfolios = {name: schedule_capacity(frame, config.max_positions) for name, frame in outcomes.items()}
    primary = portfolios["full_day_conservative"]
    sensitivity = portfolios["next_session_protection"]
    primary_summary = summarize(primary, config)
    sensitivity_summary = summarize(sensitivity, config)
    gates = {
        "minimum_trades": primary_summary.get("trades", 0) >= config.minimum_portfolio_trades,
        "primary_ci_positive": primary_summary.get("daily_ci95_low", -np.inf) > 0,
        "sensitivity_ci_positive": sensitivity_summary.get("daily_ci95_low", -np.inf) > 0,
        "primary_semester_stability": primary_summary.get("positive_semester_ratio", 0) >= config.minimum_positive_semester_ratio,
        "sensitivity_semester_stability": sensitivity_summary.get("positive_semester_ratio", 0) >= config.minimum_positive_semester_ratio,
    }
    verdict = "GO_EXACT_INTRADAY_CONFIRMATION" if all(gates.values()) else "NO_GO_OR_BLOCKED_ECONOMIC_REPLAY"
    run_id = f"e20d-opening-price-economic-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    for name, frame in outcomes.items():
        frame.to_parquet(output / f"events_{name}.parquet", index=False)
    for name, frame in portfolios.items():
        frame.to_csv(output / f"portfolio_{name}.csv", index=False)
    rejected.to_csv(output / "entry_rejections.csv", index=False)
    report = {
        "schema_version": 1, "experiment": "E20_D_OPENING_PRICE_ECONOMIC_REPLAY",
        "status": "complete", "research_only": True, "production_change": False,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "source": {"events_path": str(events_path), "selected_signals": len(events)},
        "config": asdict(config),
        "contract": {
            "signal": "E20-B return_30m abs >= 0.5%", "entry": "price_30m adjusted",
            "capacity": "8 positions, oracle score priority, LONG/SHORT shared",
            "lifecycle": "stop 2.5 ATR, trailing session 2, TP min(3 ATR,7%), H20",
            "costs": "1 bps commission + 2 bps slippage each side; short borrow 0.3% annual",
            "day0_limitation": "full daily OHLC includes 09:30-10:00 before entry",
            "capital_metric_warning": "normalized contribution is not an account equity curve",
            "counterfactual_warning": "next-open uses a direction only known at 10:00 and is attribution-only",
        },
        "population": {
            "symbols": len(symbols), "selected_events": len(events),
            "rejections": int(len(rejected)),
        },
        "primary": primary_summary, "sensitivity": sensitivity_summary,
        "paired_sensitivity_minus_primary": paired_policy_delta(primary, sensitivity, config),
        "gates": gates, "verdict": verdict, "promotion_authorized": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E20-D terminé: %s verdict=%s", output, verdict)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/oracle_opening_price_economic_replay"))
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        events_path=args.events_path, output_root=args.output_root,
        config=E20DConfig(bootstrap_samples=args.bootstrap_samples),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E20-D terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
