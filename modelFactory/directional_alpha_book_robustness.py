"""E17-C: locked historical robustness audit for residual momentum H120.

This is a post-discovery audit, not an untouched OOS validation.  It is fully
independent from Oracle data and cannot authorize production promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)
DEFAULT_PROTOCOL = Path("config/research/e17c_residual_momentum_h120_robustness.json")
LOCKED_PROTOCOL_SHA256 = "a3d9469922bd45bd64f586b22de69fb60ead04532d69418cb0d3800489660869"


def load_locked_protocol(path: Path = DEFAULT_PROTOCOL) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(
        protocol, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != LOCKED_PROTOCOL_SHA256:
        raise ValueError(
            "Le protocole E17-C a changé après verrouillage : "
            f"sha256={digest}, attendu={LOCKED_PROTOCOL_SHA256}."
        )
    if protocol.get("oracle_used") is not False:
        raise ValueError("E17-C doit rester indépendant de l’Oracle.")
    return protocol


def assign_symbol_hash_fold(symbol: str, *, folds: int, salt: str) -> int:
    digest = hashlib.sha256(f"{salt}:{str(symbol).upper()}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % folds


def select_offset_dates(
    dates: pd.Series, *, rebalance_sessions: int, offset: int,
) -> set[pd.Timestamp]:
    unique = sorted(pd.to_datetime(dates.dropna()).dt.normalize().unique())
    return {pd.Timestamp(value) for value in unique[offset::rebalance_sessions]}


def evaluate_long_top(
    frame: pd.DataFrame,
    protocol: dict[str, Any],
    *,
    calendar_offset: int,
    cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    portfolio = protocol["portfolio"]
    score = protocol["score_column"]
    scope = frame[
        frame["market_eligible"]
        & frame[score].notna()
        & frame["future_return_h120"].notna()
        & frame["future_excess_h120"].notna()
    ].copy()
    dates = select_offset_dates(
        scope["date"],
        rebalance_sessions=int(portfolio["rebalance_sessions"]),
        offset=calendar_offset,
    )
    rows: list[dict[str, Any]] = []
    selected_rows: list[pd.DataFrame] = []
    cost = cost_bps / 10_000.0
    for cohort_date, group in scope[scope["date"].isin(dates)].groupby("date", sort=True):
        ordered = group.sort_values([score, "symbol"])
        selected_count = max(
            int(portfolio["minimum_selected_symbols"]),
            math.floor(len(ordered) * float(portfolio["tail_pct"])),
        )
        if len(ordered) < selected_count:
            continue
        selected = ordered.tail(selected_count).copy()
        spy_return = float(
            (ordered["future_return_h120"] - ordered["future_excess_h120"]).median()
        )
        long_net = float(selected["future_return_h120"].mean() - cost)
        universe_net = float(ordered["future_return_h120"].mean() - cost)
        spy_net = spy_return - cost
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
        selected["date"] = pd.Timestamp(cohort_date)
        selected["net_symbol_return"] = selected["future_return_h120"] - cost
        selected["equal_weight_contribution"] = (
            selected["net_symbol_return"] / selected_count
        )
        selected_rows.append(selected[[
            "date", "symbol", "sector", score, "net_symbol_return",
            "equal_weight_contribution",
        ]])
    cohorts = pd.DataFrame(rows, columns=[
        "date", "universe", "selected_symbols", "long_return_net",
        "universe_return_net", "spy_return_net", "excess_vs_universe",
        "excess_vs_spy",
    ])
    constituents = (
        pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()
    )
    return cohorts, constituents


def _bootstrap_ci(
    values: pd.Series, protocol: dict[str, Any], *, seed_offset: int = 0,
) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    boot = protocol["bootstrap"]
    block = int(boot["block_cohorts"])
    if len(clean) < max(10, 2 * block):
        return float("nan"), float("nan")
    block = min(block, len(clean))
    blocks = math.ceil(len(clean) / block)
    rng = np.random.default_rng(int(boot["seed"]) + seed_offset)
    means = np.empty(int(boot["samples"]), dtype=float)
    for index in range(len(means)):
        starts = rng.integers(0, len(clean) - block + 1, size=blocks)
        sample = np.concatenate([clean[start : start + block] for start in starts])[: len(clean)]
        means[index] = sample.mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def summarize_cohorts(
    cohorts: pd.DataFrame, protocol: dict[str, Any], *, seed_offset: int = 0,
) -> dict[str, Any]:
    if cohorts.empty:
        return {"cohorts": 0}
    frame = cohorts.copy()
    frame["semester"] = (
        frame["date"].dt.year.astype(str)
        + "H" + np.where(frame["date"].dt.month.le(6), "1", "2")
    )
    semester = frame.groupby("semester").agg(
        cohorts=("date", "size"),
        long_return_net=("long_return_net", "mean"),
        excess_vs_universe=("excess_vs_universe", "mean"),
        excess_vs_spy=("excess_vs_spy", "mean"),
    )
    return {
        "cohorts": int(len(frame)),
        "mean_selected_symbols": float(frame["selected_symbols"].mean()),
        "mean_long_net": float(frame["long_return_net"].mean()),
        "mean_excess_vs_universe": float(frame["excess_vs_universe"].mean()),
        "ci95_excess_vs_universe": list(
            _bootstrap_ci(frame["excess_vs_universe"], protocol, seed_offset=seed_offset)
        ),
        "mean_excess_vs_spy": float(frame["excess_vs_spy"].mean()),
        "ci95_excess_vs_spy": list(
            _bootstrap_ci(frame["excess_vs_spy"], protocol, seed_offset=seed_offset + 1)
        ),
        "positive_excess_semester_ratio": float(
            semester["excess_vs_universe"].gt(0).mean()
        ),
        "semesters": semester.reset_index().to_dict(orient="records"),
    }


def positive_contribution_concentration(constituents: pd.DataFrame) -> float:
    if constituents.empty:
        return 1.0
    by_symbol = constituents.groupby("symbol")["equal_weight_contribution"].sum()
    positive = by_symbol.clip(lower=0).sort_values(ascending=False)
    total = float(positive.sum())
    if total <= 0:
        return 1.0
    return float(positive.head(20).sum() / total)


def evaluate_robustness(
    frame: pd.DataFrame, protocol: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    portfolio = protocol["portfolio"]
    checks = protocol["locked_robustness_checks"]
    primary, constituents = evaluate_long_top(
        frame, protocol,
        calendar_offset=int(portfolio["primary_calendar_offset"]),
        cost_bps=float(portfolio["primary_round_trip_cost_bps"]),
    )
    primary_summary = summarize_cohorts(primary, protocol)

    time_blocks: dict[str, Any] = {}
    for name, (start, end) in checks["time_blocks"].items():
        part = primary[primary["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
        time_blocks[name] = summarize_cohorts(part, protocol)

    hash_folds: dict[str, Any] = {}
    folds = int(checks["symbol_hash_folds"])
    assigned = frame.copy()
    assigned["symbol_hash_fold"] = assigned["symbol"].map(
        lambda symbol: assign_symbol_hash_fold(
            symbol, folds=folds, salt=str(checks["symbol_hash_salt"])
        )
    )
    for fold in range(folds):
        cohorts, _ = evaluate_long_top(
            assigned[assigned["symbol_hash_fold"].eq(fold)], protocol,
            calendar_offset=int(portfolio["primary_calendar_offset"]),
            cost_bps=float(portfolio["primary_round_trip_cost_bps"]),
        )
        hash_folds[str(fold)] = summarize_cohorts(cohorts, protocol, seed_offset=10 + fold)

    offsets: dict[str, Any] = {}
    for offset in checks["calendar_offsets_sessions"]:
        cohorts, _ = evaluate_long_top(
            frame, protocol, calendar_offset=int(offset),
            cost_bps=float(portfolio["primary_round_trip_cost_bps"]),
        )
        offsets[str(offset)] = summarize_cohorts(
            cohorts, protocol, seed_offset=20 + int(offset)
        )

    costs: dict[str, Any] = {}
    for cost in checks["round_trip_cost_stress_bps"]:
        cohorts, _ = evaluate_long_top(
            frame, protocol,
            calendar_offset=int(portfolio["primary_calendar_offset"]),
            cost_bps=float(cost),
        )
        costs[str(float(cost))] = summarize_cohorts(
            cohorts, protocol, seed_offset=50 + int(cost)
        )

    sector_rows: list[dict[str, Any]] = []
    min_symbols = int(checks["minimum_sector_symbols_per_cohort"])
    min_cohorts = int(checks["minimum_sector_cohorts"])
    for sector, part in frame.groupby("sector", sort=True):
        cohorts, _ = evaluate_long_top(
            part, protocol,
            calendar_offset=int(portfolio["primary_calendar_offset"]),
            cost_bps=float(portfolio["primary_round_trip_cost_bps"]),
        )
        cohorts = cohorts[cohorts["universe"].ge(min_symbols)].copy()
        if len(cohorts) < min_cohorts:
            continue
        summary = summarize_cohorts(cohorts, protocol)
        sector_rows.append({
            "sector": str(sector),
            "cohorts": summary["cohorts"],
            "mean_selected_symbols": summary["mean_selected_symbols"],
            "mean_excess_vs_universe": summary["mean_excess_vs_universe"],
        })
    sectors = pd.DataFrame(sector_rows)
    sector_positive_ratio = (
        float(sectors["mean_excess_vs_universe"].gt(0).mean()) if len(sectors) else 0.0
    )
    concentration = positive_contribution_concentration(constituents)

    gate_config = protocol["gates"]
    time_positive = all(
        item.get("mean_excess_vs_universe", float("-inf")) > 0
        for item in time_blocks.values()
    )
    hash_positive_ratio = float(np.mean([
        item.get("mean_excess_vs_universe", float("-inf")) > 0
        for item in hash_folds.values()
    ]))
    offsets_positive = all(
        item.get("mean_excess_vs_universe", float("-inf")) > 0
        for item in offsets.values()
    )
    cost25 = costs["25.0"].get("mean_excess_vs_universe", float("-inf"))
    gates = {
        "minimum_primary_cohorts": (
            primary_summary.get("cohorts", 0) >= int(gate_config["minimum_primary_cohorts"])
        ),
        "primary_long_net_positive": primary_summary.get("mean_long_net", -np.inf) > 0,
        "primary_excess_vs_universe_ci95_above_zero": (
            primary_summary.get("ci95_excess_vs_universe", [-np.inf])[0] > 0
        ),
        "primary_excess_vs_spy_ci95_above_zero": (
            primary_summary.get("ci95_excess_vs_spy", [-np.inf])[0] > 0
        ),
        "positive_excess_semester_ratio_min": (
            primary_summary.get("positive_excess_semester_ratio", 0.0)
            >= float(gate_config["positive_excess_semester_ratio_min"])
        ),
        "all_time_blocks_excess_vs_universe_positive": time_positive,
        "positive_symbol_hash_fold_ratio_min": (
            hash_positive_ratio
            >= float(gate_config["positive_symbol_hash_fold_ratio_min"])
        ),
        "all_calendar_offsets_excess_vs_universe_positive": offsets_positive,
        "excess_vs_universe_positive_at_25bps": cost25 > 0,
        "positive_sector_ratio_min": (
            sector_positive_ratio >= float(gate_config["positive_sector_ratio_min"])
        ),
        "max_top20_symbol_positive_contribution_share": (
            concentration
            <= float(gate_config["max_top20_symbol_positive_contribution_share"])
        ),
    }
    verdict = (
        protocol["decision_policy"]["all_gates_pass"]
        if all(gates.values())
        else protocol["decision_policy"]["otherwise"]
    )
    report = {
        "primary": primary_summary,
        "time_blocks": time_blocks,
        "symbol_hash_folds": hash_folds,
        "symbol_hash_positive_ratio": hash_positive_ratio,
        "calendar_offsets": offsets,
        "cost_stress": costs,
        "sector_positive_ratio": sector_positive_ratio,
        "top20_symbol_positive_contribution_share": concentration,
        "gates": gates,
        "verdict": verdict,
    }
    return report, {
        "primary_cohorts": primary,
        "primary_constituents": constituents,
        "sector_summary": sectors,
    }


def run(*, protocol_path: Path, output_root: Path) -> Path:
    protocol = load_locked_protocol(protocol_path)
    columns = [
        "date", "symbol", "sector", "market_eligible", protocol["score_column"],
        "future_return_h120", "future_excess_h120",
    ]
    frame = pd.read_parquet(Path(protocol["source_artifact"]), columns=columns)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    start, end = map(pd.Timestamp, protocol["source_period"])
    frame = frame[frame["date"].between(start, end)].copy()
    result, tables = evaluate_robustness(frame, protocol)
    run_id = f"e17c-robustness-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E17C_RESIDUAL_MOMENTUM_H120_HISTORICAL_ROBUSTNESS",
        "status": "complete",
        "research_only": True,
        "validation_class": protocol["validation_class"],
        "oracle_used": False,
        "registration_id": protocol["registration_id"],
        "registered_at": protocol["registered_at"],
        "protocol_sha256": LOCKED_PROTOCOL_SHA256,
        "population": {
            "rows": int(len(frame)),
            "dates": int(frame["date"].nunique()),
            "symbols": int(frame["symbol"].nunique()),
        },
        "result": result,
        "oos_claim_authorized": False,
        "promotion_authorized": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E17-C terminé: %s verdict=%s", output, result["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/directional_alpha_book_robustness"),
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(protocol_path=args.protocol, output_root=args.output_root)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E17-C terminé: {output}")
    print(report["result"]["verdict"])


if __name__ == "__main__":
    main()
