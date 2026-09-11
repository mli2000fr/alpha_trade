"""E17-B: locked prospective confirmation of residual momentum H120.

The experiment is price-only and does not read Oracle scores, labels, pools or
artifacts.  It never changes serving, predictions, backtests or live policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.directional_alpha_book import (
    E17Config,
    build_price_alpha_panel,
    classify_instruments,
    load_instrument_reference,
    load_sector_reference,
    select_rebalance_dates,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_PREREGISTRATION = Path(
    "config/research/e17b_residual_momentum_h120_preregistration.json"
)
LOCKED_PREREGISTRATION_SHA256 = (
    "20f7376e5bd09b5dc394070bb3104cbd81fbce1439ba810f322893535bde8936"
)


def load_locked_preregistration(path: Path = DEFAULT_PREREGISTRATION) -> dict[str, Any]:
    raw = path.read_bytes()
    protocol = json.loads(raw.decode("utf-8"))
    canonical = json.dumps(
        protocol, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != LOCKED_PREREGISTRATION_SHA256:
        raise ValueError(
            "Le pré-enregistrement E17-B a changé après verrouillage : "
            f"sha256={digest}, attendu={LOCKED_PREREGISTRATION_SHA256}."
        )
    required = {
        "registration_id", "registered_at", "oracle_used", "confirmation_start_date",
        "signal", "horizon_sessions", "portfolio", "eligibility", "minimum_evidence",
        "gates", "decision_policy", "bootstrap",
    }
    if missing := required - set(protocol):
        raise ValueError(f"Pré-enregistrement E17-B incomplet : {sorted(missing)}")
    if protocol["oracle_used"] is not False:
        raise ValueError("E17-B doit rester indépendant de l’Oracle.")
    return protocol


def _bootstrap_ci(values: pd.Series, protocol: dict[str, Any]) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    bootstrap = protocol["bootstrap"]
    block = int(bootstrap["block_cohorts"])
    if len(clean) < max(10, 2 * block):
        return float("nan"), float("nan")
    block = min(block, len(clean))
    blocks = math.ceil(len(clean) / block)
    rng = np.random.default_rng(int(bootstrap["seed"]))
    means = np.empty(int(bootstrap["samples"]), dtype=float)
    for index in range(len(means)):
        starts = rng.integers(0, len(clean) - block + 1, size=blocks)
        sample = np.concatenate([clean[start : start + block] for start in starts])[: len(clean)]
        means[index] = sample.mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def build_confirmation_cohorts(
    panel: pd.DataFrame, protocol: dict[str, Any],
) -> pd.DataFrame:
    """Build only the long TOP20 cohorts fixed in the preregistration."""
    horizon = int(protocol["horizon_sessions"])
    score = f"score_{protocol['signal']}"
    future = f"future_return_h{horizon}"
    benchmark_future = f"benchmark_future_return_h{horizon}"
    required = {"date", "symbol", "market_eligible", score, future, benchmark_future}
    if missing := required - set(panel.columns):
        raise ValueError(f"Panel E17-B incomplet : {sorted(missing)}")
    start = pd.Timestamp(protocol["confirmation_start_date"])
    scope = panel[
        panel["market_eligible"]
        & panel["date"].ge(start)
        & panel[score].notna()
        & panel[future].notna()
    ].copy()
    if scope.empty:
        return pd.DataFrame(columns=[
            "date", "universe", "selected_symbols", "long_return_net",
            "universe_return_net", "spy_return_net", "excess_vs_universe",
            "excess_vs_spy",
        ])
    portfolio = protocol["portfolio"]
    rebalance_config = E17Config(
        horizons=(horizon,), primary_horizon=horizon, confirmation_horizon=horizon,
        rebalance_sessions=int(portfolio["rebalance_sessions"]),
        tail_pct=0.20,
        min_leg_symbols=int(portfolio["minimum_leg_symbols"]),
    )
    rebalance_dates = select_rebalance_dates(scope["date"], rebalance_config)
    cost = float(portfolio["round_trip_cost_bps"]) / 10_000.0
    rows: list[dict[str, Any]] = []
    for cohort_date, group in scope[scope["date"].isin(rebalance_dates)].groupby(
        "date", sort=True
    ):
        ordered = group.sort_values([score, "symbol"])
        selected_count = max(
            int(portfolio["minimum_leg_symbols"]),
            math.floor(len(ordered) * 0.20),
        )
        if len(ordered) < selected_count:
            continue
        selected = ordered.tail(selected_count)
        long_net = float(selected[future].mean() - cost)
        universe_net = float(ordered[future].mean() - cost)
        spy_value = pd.to_numeric(ordered[benchmark_future], errors="coerce").dropna()
        if spy_value.empty:
            continue
        spy_net = float(spy_value.iloc[0] - cost)
        rows.append({
            "date": pd.Timestamp(cohort_date),
            "universe": int(len(ordered)),
            "selected_symbols": int(len(selected)),
            "long_return_net": long_net,
            "universe_return_net": universe_net,
            "spy_return_net": spy_net,
            "excess_vs_universe": long_net - universe_net,
            "excess_vs_spy": long_net - spy_net,
        })
    return pd.DataFrame(rows)


def decide_confirmation(
    cohorts: pd.DataFrame, protocol: dict[str, Any],
) -> dict[str, Any]:
    evidence = protocol["minimum_evidence"]
    if cohorts.empty:
        evidence_status = {
            "matured_cohorts": 0,
            "distinct_entry_semesters": 0,
            "mean_selected_symbols": 0.0,
        }
        sufficient = False
        semesters = pd.DataFrame()
    else:
        frame = cohorts.copy()
        frame["semester"] = (
            frame["date"].dt.year.astype(str)
            + "H" + np.where(frame["date"].dt.month.le(6), "1", "2")
        )
        semesters = frame.groupby("semester").agg(
            long_return_net=("long_return_net", "mean"),
            excess_vs_universe=("excess_vs_universe", "mean"),
            excess_vs_spy=("excess_vs_spy", "mean"),
            cohorts=("date", "size"),
        )
        evidence_status = {
            "matured_cohorts": int(len(frame)),
            "distinct_entry_semesters": int(frame["semester"].nunique()),
            "mean_selected_symbols": float(frame["selected_symbols"].mean()),
        }
        sufficient = (
            evidence_status["matured_cohorts"] >= int(evidence["matured_cohorts"])
            and evidence_status["distinct_entry_semesters"]
            >= int(evidence["distinct_entry_semesters"])
            and evidence_status["mean_selected_symbols"]
            >= float(evidence["mean_selected_symbols"])
        )

    def mean(column: str) -> float:
        return float(cohorts[column].mean()) if len(cohorts) else float("nan")

    universe_ci = _bootstrap_ci(cohorts.get("excess_vs_universe", pd.Series(dtype=float)), protocol)
    spy_ci = _bootstrap_ci(cohorts.get("excess_vs_spy", pd.Series(dtype=float)), protocol)
    positive_semester_ratio = (
        float(semesters["excess_vs_universe"].gt(0).mean()) if len(semesters) else 0.0
    )
    positive_pnl = semesters["long_return_net"].clip(lower=0) if len(semesters) else pd.Series()
    concentration = (
        float(positive_pnl.max() / positive_pnl.sum()) if positive_pnl.sum() > 0 else 1.0
    )
    metrics = {
        "mean_long_net": mean("long_return_net"),
        "mean_excess_vs_universe": mean("excess_vs_universe"),
        "ci95_excess_vs_universe": list(universe_ci),
        "mean_excess_vs_spy": mean("excess_vs_spy"),
        "ci95_excess_vs_spy": list(spy_ci),
        "positive_excess_semester_ratio": positive_semester_ratio,
        "positive_pnl_semester_concentration": concentration,
    }
    gate_config = protocol["gates"]
    gates = {
        "mean_long_net_positive": metrics["mean_long_net"] > 0,
        "mean_excess_vs_universe_positive": metrics["mean_excess_vs_universe"] > 0,
        "ci95_excess_vs_universe_above_zero": universe_ci[0] > 0,
        "mean_excess_vs_spy_positive": metrics["mean_excess_vs_spy"] > 0,
        "ci95_excess_vs_spy_above_zero": spy_ci[0] > 0,
        "positive_excess_semester_ratio_min": (
            positive_semester_ratio
            >= float(gate_config["positive_excess_semester_ratio_min"])
        ),
        "max_positive_pnl_semester_concentration": (
            concentration
            <= float(gate_config["max_positive_pnl_semester_concentration"])
        ),
    }
    if not sufficient:
        verdict = protocol["decision_policy"]["before_minimum_evidence"]
    elif all(gates.values()):
        verdict = protocol["decision_policy"]["all_gates_pass"]
    else:
        verdict = protocol["decision_policy"]["otherwise"]
    return {
        "verdict": verdict,
        "minimum_evidence_satisfied": sufficient,
        "evidence": evidence_status,
        "metrics": metrics,
        "gates": gates,
        "semesters": semesters.reset_index().to_dict(orient="records") if len(semesters) else [],
    }


def run(
    *, preregistration_path: Path, end_date: str, output_root: Path,
) -> Path:
    protocol = load_locked_preregistration(preregistration_path)
    start = pd.Timestamp(protocol["confirmation_start_date"])
    end = pd.Timestamp(end_date)
    symbols = sorted(set(load_universe_file_symbols(protocol["symbol_source"])))
    if end < start:
        cohorts = pd.DataFrame()
        available_end = None
    else:
        engine = get_sqlalchemy_engine()
        history_start = start - pd.offsets.BDay(300)
        bars = load_universe_bars(
            engine, symbols, start_date=history_start.date(), end_date=end.date()
        )
        benchmark = load_universe_bars(
            engine, ["SPY"], start_date=history_start.date(), end_date=end.date()
        )
        instruments = classify_instruments(load_instrument_reference(engine, symbols))
        sectors = load_sector_reference(engine, symbols)
        horizon = int(protocol["horizon_sessions"])
        eligibility = protocol["eligibility"]
        config = E17Config(
            start_date=str(start.date()), end_date=str(end.date()), horizons=(horizon,),
            primary_horizon=horizon, confirmation_horizon=horizon,
            min_history_sessions=int(eligibility["minimum_history_sessions"]),
            min_close=float(eligibility["minimum_close_usd"]),
            min_avg_volume_20d=float(eligibility["minimum_average_volume_20d_shares"]),
            min_adv_usd_20d=float(eligibility["minimum_adv_20d_usd"]),
            rebalance_sessions=int(protocol["portfolio"]["rebalance_sessions"]),
            min_leg_symbols=int(protocol["portfolio"]["minimum_leg_symbols"]),
            round_trip_cost_bps=float(protocol["portfolio"]["round_trip_cost_bps"]),
            bootstrap_samples=int(protocol["bootstrap"]["samples"]),
            bootstrap_seed=int(protocol["bootstrap"]["seed"]),
        )
        if bars.empty or benchmark.empty:
            cohorts = pd.DataFrame()
            available_end = None
        else:
            panel = build_price_alpha_panel(bars, benchmark, instruments, sectors, config)
            cohorts = build_confirmation_cohorts(panel, protocol)
            available_end = str(pd.to_datetime(bars["date"]).max().date())
    decision = decide_confirmation(cohorts, protocol)
    run_id = f"e17b-confirmation-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    cohorts.to_csv(output / "confirmation_cohorts.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E17B_RESIDUAL_MOMENTUM_H120_LONG_ONLY_CONFIRMATION",
        "status": "complete",
        "research_only": True,
        "oracle_used": False,
        "registration_id": protocol["registration_id"],
        "registered_at": protocol["registered_at"],
        "preregistration_sha256": LOCKED_PREREGISTRATION_SHA256,
        "requested_end_date": str(end.date()),
        "available_bar_end_date": available_end,
        "symbols_requested": len(symbols),
        "decision": decision,
        "promotion_authorized": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E17-B terminé: %s verdict=%s", output, decision["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--end-date", default=str(date.today()))
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/directional_alpha_book_confirmation"),
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        preregistration_path=args.preregistration,
        end_date=args.end_date,
        output_root=args.output_root,
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E17-B terminé: {output}")
    print(report["decision"]["verdict"])


if __name__ == "__main__":
    main()
