"""E12: attribution Oracle OOF -> portefeuille contraint -> lifecycle PROD.

Le module est research-only. Il ne modifie ni les signaux persistés, ni le
backtest applicatif, ni le serving. Les snapshots tradables non ``full`` sont
rapportés comme sensibilité et ne sont jamais qualifiés de preuve PIT canonique.
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
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backtesting.microstructure import resolve_intrabar_exit, should_skip_entry_for_gap
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean
from modelFactory.oracle_rolling_lifecycle import prepare_bars

LOGGER = logging.getLogger(__name__)
Policy = Literal["oracle_score", "liquidity", "random"]


@dataclass(frozen=True, slots=True)
class E12Config:
    horizon: int = 20
    max_positions: int = 8
    initial_stop_atr_multiple: float = 2.5
    trailing_atr_multiple: float = 2.5
    tp_atr_multiple: float = 3.0
    tp_max_pct: float = 0.07
    max_entry_gap_pct: float = 0.03
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    random_seeds: int = 200
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260912
    capital_preset_key: str = "capital_2001_5000"

    def __post_init__(self) -> None:
        if self.horizon != 20:
            raise ValueError("E12 primaire est gele a H20.")
        if self.max_positions < 1 or self.random_seeds < 1:
            raise ValueError("Capacite ou nombre de seeds invalide.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0

    def bootstrap_config(self) -> RollingConfig:
        return RollingConfig(
            commission_bps=self.commission_bps,
            slippage_bps=self.slippage_bps,
            bootstrap_samples=self.bootstrap_samples,
            bootstrap_block_sessions=self.bootstrap_block_sessions,
            bootstrap_seed=self.bootstrap_seed,
        )


def build_fixed_h20_events(
    oracle_gate: pd.DataFrame, bars: pd.DataFrame, config: E12Config
) -> pd.DataFrame:
    required = {
        "date", "symbol", "directional_oracle_fold_start",
        "directional_oracle_proba_extreme", "directional_oracle_eligible",
        "directional_oracle_oof_available",
    }
    if missing := required - set(oracle_gate.columns):
        raise ValueError(f"Gate Oracle incomplet: {sorted(missing)}")
    gate = oracle_gate[
        oracle_gate["directional_oracle_eligible"].fillna(False)
        & oracle_gate["directional_oracle_oof_available"].fillna(False)
        & oracle_gate["directional_oracle_fold_start"].notna()
    ].copy()
    gate["date"] = pd.to_datetime(gate["date"], errors="coerce").dt.normalize()
    gate["symbol"] = gate["symbol"].astype(str).str.strip().str.upper()
    if gate.duplicated(["date", "symbol"]).any():
        raise ValueError("Doublons Oracle (date,symbol).")

    prepared = prepare_bars(bars)
    grouped = prepared.groupby("symbol", sort=False)
    prepared["entry_date"] = grouped["date"].shift(-1)
    prepared["entry_open"] = grouped["px_open"].shift(-1)
    prepared["entry_atr20_for_signal"] = grouped["entry_atr20"].shift(-1)
    prepared["entry_previous_close"] = grouped["previous_close"].shift(-1)
    prepared["terminal_date"] = grouped["date"].shift(-(config.horizon + 1))
    prepared["terminal_exit_open"] = grouped["px_open"].shift(-(config.horizon + 1))
    prepared["dollar_volume"] = prepared["px_close"] * pd.to_numeric(
        prepared["volume"], errors="coerce"
    )
    prepared["adv20"] = grouped["dollar_volume"].transform(
        lambda values: values.rolling(20, min_periods=20).mean()
    )
    cols = [
        "date", "symbol", "px_close", "entry_date", "entry_open",
        "entry_atr20_for_signal", "entry_previous_close", "terminal_date",
        "terminal_exit_open", "adv20",
    ]
    events = gate.merge(
        prepared[cols], on=["date", "symbol"], how="left", validate="one_to_one"
    ).dropna(subset=["entry_date", "entry_open", "terminal_date", "terminal_exit_open"])
    events = events[events["entry_open"].gt(0) & events["terminal_exit_open"].gt(0)].copy()
    events["gross_return"] = events["terminal_exit_open"] / events["entry_open"] - 1.0
    events["net_return"] = events["gross_return"] - config.round_trip_cost
    events["entry_gap_pct"] = (
        (events["entry_open"] - events["entry_previous_close"])
        / events["entry_previous_close"]
    ).abs()
    events["gap_rejected"] = events["entry_gap_pct"].gt(config.max_entry_gap_pct)
    events["fold"] = pd.to_datetime(
        events["directional_oracle_fold_start"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    events["semester"] = (
        events["date"].dt.year.astype(str)
        + "H" + np.where(events["date"].dt.month.le(6), "1", "2")
    )
    return events.sort_values(["date", "symbol"]).reset_index(drop=True)


def deduplicate_non_overlapping(events: pd.DataFrame) -> pd.DataFrame:
    """Conserve le premier signal dont l'entree suit la sortie H20 précédente."""
    selected: list[int] = []
    for _, group in events.sort_values(["symbol", "entry_date", "date"]).groupby(
        "symbol", sort=False
    ):
        last_exit: pd.Timestamp | None = None
        for row in group.itertuples():
            entry, exit_date = pd.Timestamp(row.entry_date), pd.Timestamp(row.terminal_date)
            if last_exit is None or entry >= last_exit:
                selected.append(int(row.Index))
                last_exit = exit_date
    return events.loc[selected].sort_values(["date", "symbol"]).reset_index(drop=True)


def select_with_capacity(
    events: pd.DataFrame,
    config: E12Config,
    *,
    policy: Policy,
    seed: int = 0,
    exit_column: str = "terminal_date",
) -> pd.DataFrame:
    """Sélectionne au plus ``max_positions`` sans chevauchement de positions."""
    rng = np.random.default_rng(seed)
    active: dict[str, pd.Timestamp] = {}
    selected: list[int] = []
    for _, group in events.groupby("date", sort=True):
        entry_date = pd.Timestamp(group["entry_date"].min())
        active = {symbol: end for symbol, end in active.items() if end > entry_date}
        slots = config.max_positions - len(active)
        if slots <= 0:
            continue
        candidates = group[~group["symbol"].isin(active)].copy()
        if candidates.empty:
            continue
        if policy == "oracle_score":
            candidates["_priority"] = pd.to_numeric(
                candidates["directional_oracle_proba_extreme"], errors="coerce"
            ).fillna(-np.inf)
        elif policy == "liquidity":
            candidates["_priority"] = pd.to_numeric(
                candidates["adv20"], errors="coerce"
            ).fillna(-np.inf)
        elif policy == "random":
            candidates["_priority"] = rng.random(len(candidates))
        else:
            raise ValueError(f"Politique inconnue: {policy}")
        chosen = candidates.sort_values(
            ["_priority", "symbol"], ascending=[False, True]
        ).head(slots)
        for row in chosen.itertuples():
            selected.append(int(row.Index))
            active[str(row.symbol)] = pd.Timestamp(getattr(row, exit_column))
    return events.loc[selected].sort_values(["entry_date", "symbol"]).reset_index(drop=True)


def load_exact_tradable_membership(
    engine: Engine,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    preset: str,
    quality: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    quality_clause = "AND LOWER(r.data_quality_grade) = 'full'" if quality == "full" else ""
    query = text(f"""
        SELECT r.snapshot_date AS date, UPPER(TRIM(h.symbol)) AS symbol,
               LOWER(r.data_quality_grade) AS data_quality_grade
        FROM tradable_universe_runs r
        JOIN tradable_universe_history h ON h.universe_run_id=r.universe_run_id
        WHERE r.capital_preset_key=:preset
          AND r.snapshot_date BETWEEN :start_date AND :end_date
          AND r.status='completed' AND r.is_canonical=1
          AND r.rows_written=r.rows_expected AND h.is_tradable=1
          {quality_clause}
    """)
    with engine.connect() as connection:
        frame = pd.read_sql(
            query, connection,
            params={
                "preset": preset,
                "start_date": start_date.date(), "end_date": end_date.date(),
            },
        )
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame["symbol"] = frame["symbol"].astype(str).str.upper()
    diagnostics = {
        "requested_quality": quality,
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()) if len(frame) else 0,
        "symbols": int(frame["symbol"].nunique()) if len(frame) else 0,
        "quality_values": sorted(frame["data_quality_grade"].unique().tolist()) if len(frame) else [],
    }
    return frame, diagnostics


def filter_by_membership(events: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    if membership.empty:
        return events.iloc[0:0].copy()
    keys = membership[["date", "symbol"]].drop_duplicates()
    return events.merge(keys.assign(_tradable=True), on=["date", "symbol"], how="inner")


def simulate_prod_long(
    symbol_bars: pd.DataFrame,
    *,
    signal_date: pd.Timestamp,
    config: E12Config,
) -> dict[str, Any] | None:
    bars = symbol_bars.reset_index(drop=True)
    matches = bars.index[bars["date"].gt(pd.Timestamp(signal_date).normalize())]
    if len(matches) < 1:
        return None
    entry_index = int(matches[0])
    if entry_index == 0 or entry_index + config.horizon >= len(bars):
        return None
    entry = bars.iloc[entry_index]
    entry_price = float(entry["px_open"])
    previous_close = float(entry["previous_close"])
    atr = float(entry["entry_atr20"])
    if not all(np.isfinite(value) and value > 0 for value in (entry_price, previous_close, atr)):
        return None
    if should_skip_entry_for_gap(previous_close, entry_price, max_gap_pct=config.max_entry_gap_pct):
        return {
            "entry_date": pd.Timestamp(entry["date"]), "entry_price": entry_price,
            "exit_reason": "entry_gap_rejected",
        }
    atr_pct = atr / previous_close
    initial_stop = entry_price * (1.0 - config.initial_stop_atr_multiple * atr_pct)
    trail_pct = config.trailing_atr_multiple * atr_pct
    take_profit = entry_price * (1.0 + min(config.tp_atr_multiple * atr_pct, config.tp_max_pct))
    previous_peak = entry_price
    for holding_session in range(1, config.horizon + 1):
        row = bars.iloc[entry_index + holding_session - 1]
        trailing_active = holding_session >= 2
        trailing_stop = previous_peak * (1.0 - trail_pct) if trailing_active else -np.inf
        resolution = resolve_intrabar_exit(
            day_high=float(row["px_high"]), day_low=float(row["px_low"]),
            take_profit_price=take_profit, trailing_stop_price=trailing_stop,
            initial_stop_price=None if trailing_active else initial_stop,
            priority="conservative", side="buy",
        )
        if resolution.triggered:
            exit_price = float(resolution.exit_price)
            return {
                "entry_date": pd.Timestamp(entry["date"]), "entry_price": entry_price,
                "exit_date": pd.Timestamp(row["date"]), "exit_price": exit_price,
                "exit_reason": resolution.exit_reason, "holding_sessions": holding_session,
                "gross_return": exit_price / entry_price - 1.0,
                "net_return": exit_price / entry_price - 1.0 - config.round_trip_cost,
            }
        previous_peak = max(previous_peak, float(row["px_high"]))
    terminal = bars.iloc[entry_index + config.horizon]
    exit_price = float(terminal["px_open"])
    return {
        "entry_date": pd.Timestamp(entry["date"]), "entry_price": entry_price,
        "exit_date": pd.Timestamp(terminal["date"]), "exit_price": exit_price,
        "exit_reason": "fixed_h20", "holding_sessions": config.horizon,
        "gross_return": exit_price / entry_price - 1.0,
        "net_return": exit_price / entry_price - 1.0 - config.round_trip_cost,
    }


def replay_lifecycle_on_selected(
    selected: pd.DataFrame, prepared_bars: pd.DataFrame, config: E12Config
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars_by_symbol = dict(tuple(prepared_bars.groupby("symbol", sort=False)))
    results: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in selected.itertuples(index=False):
        outcome = simulate_prod_long(
            bars_by_symbol.get(str(candidate.symbol), pd.DataFrame()),
            signal_date=pd.Timestamp(candidate.date), config=config,
        )
        identity = {
            "date": pd.Timestamp(candidate.date), "symbol": str(candidate.symbol),
            "fixed_h20_net_return": float(candidate.net_return), "fold": str(candidate.fold),
            "semester": str(candidate.semester),
        }
        if outcome is None or outcome.get("exit_reason") == "entry_gap_rejected":
            rejected.append({**identity, "reason": "missing_path" if outcome is None else "entry_gap_rejected"})
        else:
            results.append({**identity, **outcome})
    return pd.DataFrame(results), pd.DataFrame(rejected)


def replay_lifecycle_with_dynamic_capacity(
    events: pd.DataFrame,
    prepared_bars: pd.DataFrame,
    config: E12Config,
    *,
    policy: Policy = "oracle_score",
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rejoue le lifecycle en réallouant les places après les sorties réelles.

    Une sortie intraday datée J ne libère volontairement la place qu'à partir
    de J+1 : la capacité disponible à l'open de J ne peut pas anticiper une
    sortie qui se produira plus tard dans la séance.
    """
    bars_by_symbol = dict(tuple(prepared_bars.groupby("symbol", sort=False)))
    rng = np.random.default_rng(seed)
    active: dict[str, pd.Timestamp] = {}
    results: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for _, group in events.groupby("date", sort=True):
        entry_date = pd.Timestamp(group["entry_date"].min())
        active = {symbol: end for symbol, end in active.items() if end >= entry_date}
        slots = config.max_positions - len(active)
        if slots <= 0:
            continue
        candidates = group[~group["symbol"].isin(active)].copy()
        if policy == "oracle_score":
            candidates["_priority"] = pd.to_numeric(
                candidates["directional_oracle_proba_extreme"], errors="coerce"
            ).fillna(-np.inf)
        elif policy == "liquidity":
            candidates["_priority"] = pd.to_numeric(
                candidates["adv20"], errors="coerce"
            ).fillna(-np.inf)
        elif policy == "random":
            candidates["_priority"] = rng.random(len(candidates))
        else:
            raise ValueError(f"Politique inconnue: {policy}")
        candidates = candidates.sort_values(
            ["_priority", "symbol"], ascending=[False, True]
        )
        for candidate in candidates.itertuples(index=False):
            if slots <= 0:
                break
            outcome = simulate_prod_long(
                bars_by_symbol.get(str(candidate.symbol), pd.DataFrame()),
                signal_date=pd.Timestamp(candidate.date), config=config,
            )
            identity = {
                "date": pd.Timestamp(candidate.date), "symbol": str(candidate.symbol),
                "fixed_h20_net_return": float(candidate.net_return),
                "fold": str(candidate.fold), "semester": str(candidate.semester),
            }
            if outcome is None or outcome.get("exit_reason") == "entry_gap_rejected":
                rejected.append({
                    **identity,
                    "reason": "missing_path" if outcome is None else "entry_gap_rejected",
                })
                continue
            results.append({**identity, **outcome})
            active[str(candidate.symbol)] = pd.Timestamp(outcome["exit_date"])
            slots -= 1
    return pd.DataFrame(results), pd.DataFrame(rejected)


def summarize_returns(
    frame: pd.DataFrame, *, config: E12Config, return_column: str = "net_return"
) -> dict[str, Any]:
    if frame.empty:
        return {"events": 0}
    daily = frame.groupby("date")[return_column].mean().sort_index()
    ci = block_bootstrap_mean(daily, config.bootstrap_config())
    return {
        "events": int(len(frame)), "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "mean_net_return": float(frame[return_column].mean()),
        "median_net_return": float(frame[return_column].median()),
        "win_rate": float(frame[return_column].gt(0).mean()),
        "daily_mean": float(daily.mean()),
        "daily_ci95_low": ci[0], "daily_ci95_high": ci[1],
        "q05": float(frame[return_column].quantile(0.05)),
        "q01": float(frame[return_column].quantile(0.01)),
    }


def random_capacity_distribution(
    events: pd.DataFrame, config: E12Config
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    first = pd.DataFrame()
    for seed in range(config.random_seeds):
        chosen = select_with_capacity(events, config, policy="random", seed=seed)
        if seed == 0:
            first = chosen
        daily = chosen.groupby("date")["net_return"].mean()
        rows.append({
            "seed": seed, "trades": int(len(chosen)),
            "mean_net_return": float(chosen["net_return"].mean()),
            "daily_mean": float(daily.mean()),
        })
    return pd.DataFrame(rows), first


def run(
    *, oracle_gate_path: Path, output_root: Path, config: E12Config
) -> Path:
    if oracle_gate_path.name != "_oracle_oof_gate.parquet" or not oracle_gate_path.is_file():
        raise ValueError("E12 exige _oracle_oof_gate.parquet.")
    oracle = pd.read_parquet(oracle_gate_path)
    eligible = oracle[
        oracle["directional_oracle_eligible"].fillna(False)
        & oracle["directional_oracle_oof_available"].fillna(False)
    ]
    symbols = sorted(eligible["symbol"].astype(str).str.upper().unique())
    start = pd.Timestamp(eligible["date"].min()) - pd.offsets.BDay(40)
    end = pd.Timestamp(eligible["date"].max()) + pd.offsets.BDay(25)
    engine = get_sqlalchemy_engine()
    bars = load_universe_bars(
        engine, symbols, start_date=start.date(), end_date=end.date()
    )
    events = build_fixed_h20_events(oracle, bars, config)
    dedup = deduplicate_non_overlapping(events)
    oracle_capacity = select_with_capacity(dedup, config, policy="oracle_score")
    liquidity_capacity = select_with_capacity(dedup, config, policy="liquidity")
    random_distribution, random_seed0 = random_capacity_distribution(dedup, config)

    full_members, full_diag = load_exact_tradable_membership(
        engine, start_date=events["date"].min(), end_date=events["date"].max(),
        preset=config.capital_preset_key, quality="full",
    )
    degraded_members, degraded_diag = load_exact_tradable_membership(
        engine, start_date=events["date"].min(), end_date=events["date"].max(),
        preset=config.capital_preset_key, quality="any",
    )
    degraded_events = filter_by_membership(dedup, degraded_members)
    degraded_capacity = select_with_capacity(
        degraded_events, config, policy="oracle_score"
    ) if len(degraded_events) else degraded_events

    prepared = prepare_bars(bars)
    lifecycle_frozen, lifecycle_frozen_rejected = replay_lifecycle_on_selected(
        oracle_capacity, prepared, config
    )
    lifecycle, lifecycle_rejected = replay_lifecycle_with_dynamic_capacity(
        dedup, prepared, config, policy="oracle_score"
    )
    summaries = {
        "A_all_oracle_fixed_h20": summarize_returns(events, config=config),
        "B_non_overlapping_fixed_h20": summarize_returns(dedup, config=config),
        "C_capacity8_oracle_score_fixed_h20": summarize_returns(oracle_capacity, config=config),
        "C_capacity8_liquidity_fixed_h20": summarize_returns(liquidity_capacity, config=config),
        "C_capacity8_random_seed0_fixed_h20": summarize_returns(random_seed0, config=config),
        "D_degraded_tradable_capacity8_sensitivity": summarize_returns(degraded_capacity, config=config),
        "E_capacity8_frozen_slots_prod_lifecycle": summarize_returns(
            lifecycle_frozen, config=config
        ),
        "F_capacity8_dynamic_prod_lifecycle": summarize_returns(lifecycle, config=config),
    }
    random_summary = {
        "seeds": int(len(random_distribution)),
        "daily_mean_median": float(random_distribution["daily_mean"].median()),
        "daily_mean_p05": float(random_distribution["daily_mean"].quantile(0.05)),
        "daily_mean_p95": float(random_distribution["daily_mean"].quantile(0.95)),
        "oracle_score_percentile": float(
            random_distribution["daily_mean"].le(
                summaries["C_capacity8_oracle_score_fixed_h20"]["daily_mean"]
            ).mean()
        ),
        "liquidity_percentile": float(
            random_distribution["daily_mean"].le(
                summaries["C_capacity8_liquidity_fixed_h20"]["daily_mean"]
            ).mean()
        ),
    }
    lifecycle_delta = lifecycle.copy()
    if len(lifecycle_delta):
        lifecycle_delta["delta_vs_fixed_h20"] = (
            lifecycle_delta["net_return"] - lifecycle_delta["fixed_h20_net_return"]
        )
        delta_daily = lifecycle_delta.groupby("date")["delta_vs_fixed_h20"].mean()
        delta_ci = block_bootstrap_mean(delta_daily, config.bootstrap_config())
        lifecycle_attribution = {
            "paired_trades": int(len(lifecycle_delta)),
            "rejected": int(len(lifecycle_rejected)),
            "mean_delta_vs_fixed_h20": float(lifecycle_delta["delta_vs_fixed_h20"].mean()),
            "daily_delta_vs_fixed_h20": float(delta_daily.mean()),
            "daily_delta_ci95_low": delta_ci[0], "daily_delta_ci95_high": delta_ci[1],
            "exit_reasons": lifecycle_delta["exit_reason"].value_counts().to_dict(),
        }
    else:
        lifecycle_attribution = {"paired_trades": 0, "rejected": int(len(lifecycle_rejected))}

    baseline = summaries["A_all_oracle_fixed_h20"]
    capacity = summaries["C_capacity8_oracle_score_fixed_h20"]
    lifecycle_summary = summaries["F_capacity8_dynamic_prod_lifecycle"]
    decision = {
        "event_study_positive": baseline.get("daily_mean", -np.inf) > 0,
        "event_study_ci95_above_zero": baseline.get("daily_ci95_low", -np.inf) > 0,
        "capacity_positive": capacity.get("daily_mean", -np.inf) > 0,
        "capacity_ci95_above_zero": capacity.get("daily_ci95_low", -np.inf) > 0,
        "oracle_selection_beats_random_p95": random_summary["oracle_score_percentile"] >= 0.95,
        "lifecycle_positive": lifecycle_summary.get("daily_mean", -np.inf) > 0,
        "lifecycle_ci95_above_zero": lifecycle_summary.get("daily_ci95_low", -np.inf) > 0,
        "strict_tradable_pit_available": full_diag["dates"] == events["date"].nunique(),
        "promotion_authorized": False,
    }
    decision["verdict"] = (
        "GO_EXACT_BACKTEST_REPLAY"
        if all(decision[key] for key in (
            "event_study_ci95_above_zero", "capacity_ci95_above_zero",
            "lifecycle_ci95_above_zero", "strict_tradable_pit_available",
        )) else "NO_GO_OR_BLOCKED"
    )

    run_id = f"oracle-monetization-bridge-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    events.to_parquet(output / "A_all_oracle_fixed_h20.parquet", index=False)
    dedup.to_parquet(output / "B_non_overlapping_fixed_h20.parquet", index=False)
    oracle_capacity.to_csv(output / "C_capacity8_oracle_score.csv", index=False)
    liquidity_capacity.to_csv(output / "C_capacity8_liquidity.csv", index=False)
    random_distribution.to_csv(output / "C_random_distribution.csv", index=False)
    degraded_capacity.to_csv(output / "D_degraded_tradable_sensitivity.csv", index=False)
    lifecycle.to_csv(output / "E_prod_lifecycle.csv", index=False)
    lifecycle_rejected.to_csv(output / "E_prod_lifecycle_rejected.csv", index=False)
    lifecycle_frozen.to_csv(output / "E_frozen_slots_prod_lifecycle.csv", index=False)
    lifecycle_frozen_rejected.to_csv(
        output / "E_frozen_slots_prod_lifecycle_rejected.csv", index=False
    )
    report = {
        "schema_version": 2, "experiment": "E12_ORACLE_MONETIZATION_BRIDGE",
        "status": "complete", "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "input": str(oracle_gate_path), "config": asdict(config),
        "contract": {
            "side": "LONG only", "entry": "adjusted open J+1",
            "fixed_exit": "adjusted open J+21", "dedup": "first non-overlapping per symbol",
            "capacity": config.max_positions,
            "selection": ["oracle_score", "liquidity", f"random_{config.random_seeds}_seeds"],
            "lifecycle": "PROD stop 2.5ATR, trailing 2.5ATR active session 2, TP min(3ATR,7%), conservative, gap 3%, no time stop",
        },
        "tradable_pit": {
            "full": full_diag, "degraded_sensitivity": degraded_diag,
            "canonical_layer_available": bool(decision["strict_tradable_pit_available"]),
        },
        "summaries": summaries, "random_capacity": random_summary,
        "lifecycle_attribution": lifecycle_attribution, "decision": decision,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E12 termine: %s verdict=%s", output, decision["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-gate", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_monetization_bridge"),
    )
    parser.add_argument("--random-seeds", type=int, default=200)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        oracle_gate_path=args.oracle_gate, output_root=args.output_root,
        config=E12Config(
            random_seeds=args.random_seeds, bootstrap_samples=args.bootstrap_samples
        ),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E12 termine: {output}")
    print(report["decision"]["verdict"])


if __name__ == "__main__":
    main()
