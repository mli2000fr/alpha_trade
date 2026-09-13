"""E19-C: locked confirmation of the E19-B PIT value factor."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean


@dataclass(frozen=True, slots=True)
class E19CConfig:
    early_start: str = "2018-07-02"
    early_end: str = "2020-07-01"
    late_start: str = "2025-07-10"
    late_end: str = "2025-12-31"
    horizons: tuple[int, ...] = (60, 120)
    tail_pct: float = 0.20
    min_leg_symbols: int = 10
    rebalance_sessions: int = 20
    round_trip_cost_bps: float = 6.0
    bootstrap_samples: int = 2_000
    bootstrap_seed: int = 20260920
    hash_partitions: int = 5

    @property
    def cost(self) -> float:
        return self.round_trip_cost_bps / 10_000.0


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_partition(symbol: str, partitions: int) -> int:
    value = hashlib.sha256(str(symbol).upper().encode()).digest()
    return int.from_bytes(value[:8], "big") % partitions


def holdout_mask(panel: pd.DataFrame, config: E19CConfig) -> pd.Series:
    date = pd.to_datetime(panel["date"], errors="coerce")
    return date.between(config.early_start, config.early_end) | date.between(config.late_start, config.late_end)


def label_windows(panel: pd.DataFrame, config: E19CConfig) -> pd.Series:
    date = pd.to_datetime(panel["date"], errors="coerce")
    labels = pd.Series(pd.NA, index=panel.index, dtype="string")
    labels.loc[date.between(config.early_start, config.early_end)] = "EARLY_HOLDBACK"
    labels.loc[date.between(config.late_start, config.late_end)] = "LATE_HOLDBACK"
    return labels


def _bootstrap(values: pd.Series, config: E19CConfig, horizon: int, salt: int) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return float("nan"), float("nan")
    rolling = RollingConfig(
        bootstrap_samples=config.bootstrap_samples,
        bootstrap_block_sessions=max(2, math.ceil(horizon / config.rebalance_sessions)),
        bootstrap_seed=config.bootstrap_seed + horizon + salt,
    )
    return block_bootstrap_mean(clean.reset_index(drop=True), rolling)


def evaluate(panel: pd.DataFrame, horizon: int, config: E19CConfig, *, partition: int | None = None) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    score, raw, excess = "score_value__sector_size_neutral", f"future_return_h{horizon}", f"future_excess_h{horizon}"
    needed = ["date", "symbol", "window", score, raw, excess, "market_eligible"]
    scope = panel.loc[panel[needed].notna().all(axis=1) & panel["market_eligible"].astype(bool)].copy()
    if partition is not None:
        scope = scope[scope["hash_partition"].eq(partition)].copy()
    ic_rows: list[dict[str, Any]] = []
    cohort_rows: list[dict[str, Any]] = []
    for window, frame in scope.groupby("window", sort=True):
        rebalance = {pd.Timestamp(x) for x in sorted(frame["date"].unique())[::config.rebalance_sessions]}
        for date, group in frame.groupby("date", sort=True):
            valid = group[[score, excess]].dropna()
            if len(valid) >= 30 and valid[score].nunique() > 1 and valid[excess].nunique() > 1:
                ic_rows.append({"date": date, "window": window, "horizon": horizon, "ic": float(spearmanr(valid[score], valid[excess]).statistic), "partition": partition})
            if pd.Timestamp(date) not in rebalance:
                continue
            ordered = group.sort_values([score, "symbol"])
            leg = max(config.min_leg_symbols, int(math.floor(len(ordered) * config.tail_pct)))
            if len(ordered) < 2 * leg:
                continue
            bottom, top = ordered.head(leg), ordered.tail(leg)
            universe = float(ordered[raw].mean())
            benchmark = float((ordered[raw] - ordered[excess]).median())
            long_gross, bottom_gross = float(top[raw].mean()), float(bottom[raw].mean())
            long_net, short_net = long_gross - config.cost, -bottom_gross - config.cost
            cohort_rows.append({"date": date, "window": window, "horizon": horizon, "partition": partition, "universe": len(ordered), "leg_size": leg, "long_return_net": long_net, "short_return_net": short_net, "long_short_return_net": .5 * (long_net + short_net), "long_excess_spy_net": long_gross - benchmark - config.cost, "long_excess_universe_net": long_gross - universe - config.cost, "bottom_underperformance_universe_net": universe - bottom_gross - config.cost})
    daily_ic, cohorts = pd.DataFrame(ic_rows), pd.DataFrame(cohort_rows)
    if cohorts.empty or daily_ic.empty:
        return {"horizon": horizon, "partition": partition, "cohorts": 0}, daily_ic, cohorts
    ic_ci = _bootstrap(daily_ic["ic"], config, horizon, 1)
    ls_ci = _bootstrap(cohorts["long_short_return_net"], config, horizon, 2)
    summary: dict[str, Any] = {"horizon": horizon, "partition": partition, "dates": int(daily_ic.date.nunique()), "cohorts": len(cohorts), "mean_leg_size": float(cohorts.leg_size.mean()), "ic_mean": float(daily_ic.ic.mean()), "ic_ci95_low": ic_ci[0], "ic_ci95_high": ic_ci[1], "long_return_net": float(cohorts.long_return_net.mean()), "short_return_net": float(cohorts.short_return_net.mean()), "long_short_return_net": float(cohorts.long_short_return_net.mean()), "long_short_ci95_low": ls_ci[0], "long_short_ci95_high": ls_ci[1], "long_excess_spy_net": float(cohorts.long_excess_spy_net.mean()), "long_excess_universe_net": float(cohorts.long_excess_universe_net.mean()), "bottom_underperformance_universe_net": float(cohorts.bottom_underperformance_universe_net.mean()), "windows": {}}
    for window, group in cohorts.groupby("window"):
        summary["windows"][str(window)] = {key: (int(len(group)) if key == "cohorts" else float(group[key].mean())) for key in ["cohorts", "long_short_return_net", "long_excess_spy_net", "long_excess_universe_net", "bottom_underperformance_universe_net"]}
    return summary, daily_ic, cohorts


def build_gates(results: dict[str, Any], hashes: pd.DataFrame) -> dict[str, bool]:
    a, b = results["h60"], results["h120"]
    positive = hashes.groupby("horizon").long_short_return_net.apply(lambda x: int(x.gt(0).sum()))
    window_positive = lambda x: all(x.get("windows", {}).get(w, {}).get("long_short_return_net", -np.inf) > 0 for w in ("EARLY_HOLDBACK", "LATE_HOLDBACK"))
    return {"minimum_25_cohorts": a.get("cohorts", 0) >= 25, "h60_ic_positive": a.get("ic_mean", -np.inf) > 0, "h60_ic_ci95_positive": a.get("ic_ci95_low", -np.inf) > 0, "h60_spread_positive": a.get("long_short_return_net", -np.inf) > 0, "h60_spread_ci95_positive": a.get("long_short_ci95_low", -np.inf) > 0, "h60_long_excess_spy_positive": a.get("long_excess_spy_net", -np.inf) > 0, "h60_long_excess_universe_positive": a.get("long_excess_universe_net", -np.inf) > 0, "h60_bottom_underperforms": a.get("bottom_underperformance_universe_net", -np.inf) > 0, "h60_both_holdouts_positive": window_positive(a), "h120_ic_positive": b.get("ic_mean", -np.inf) > 0, "h120_spread_positive": b.get("long_short_return_net", -np.inf) > 0, "h120_spread_ci95_positive": b.get("long_short_ci95_low", -np.inf) > 0, "h120_both_holdouts_positive": window_positive(b), "h60_hash_4_of_5_positive": int(positive.get(60, 0)) >= 4, "h120_hash_4_of_5_positive": int(positive.get(120, 0)) >= 4}


def run(e19b_dir: Path, output_root: Path, config: E19CConfig) -> Path:
    panel_path, source_report = e19b_dir / "alpha_panel.parquet", e19b_dir / "report.json"
    source = json.loads(source_report.read_text(encoding="utf-8"))
    panel = pd.read_parquet(panel_path)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel[holdout_mask(panel, config)].copy()
    panel["window"] = label_windows(panel, config)
    panel["hash_partition"] = panel.symbol.map(lambda x: hash_partition(x, config.hash_partitions))
    results, all_ic, all_cohorts = {}, [], []
    for horizon in config.horizons:
        summary, ic, cohorts = evaluate(panel, horizon, config)
        results[f"h{horizon}"] = summary; all_ic.append(ic); all_cohorts.append(cohorts)
    hash_rows = []
    for partition in range(config.hash_partitions):
        for horizon in config.horizons:
            hash_rows.append(evaluate(panel, horizon, config, partition=partition)[0])
    hash_frame = pd.DataFrame(hash_rows)
    gates = build_gates(results, hash_frame)
    verdict = "GO_RESEARCH_SHADOW" if all(gates.values()) else "NO_GO"
    run_id = "fundamental-value-confirmation-" + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    output = output_root / run_id; output.mkdir(parents=True)
    pd.concat(all_ic, ignore_index=True).to_csv(output / "daily_ic.csv", index=False)
    pd.concat(all_cohorts, ignore_index=True).to_csv(output / "cohorts.csv", index=False)
    hash_frame.to_csv(output / "hash_robustness.csv", index=False)
    report = {"schema_version": 1, "experiment": "E19-C", "status": "COMPLETE", "research_only": True, "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id, "source": {"e19b_run_id": source.get("run_id"), "directory": str(e19b_dir), "report_sha256": file_sha256(source_report), "panel_sha256": file_sha256(panel_path)}, "config": asdict(config), "population": {"rows": len(panel), "symbols": panel.symbol.nunique(), "dates": panel.date.nunique()}, "results": results, "hash_robustness": hash_rows, "gates": gates, "verdict": verdict, "promotion_authorized": False}
    (output / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e19b-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/fundamental_value_confirmation"))
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args()
    output = run(args.e19b_dir, args.output_root, E19CConfig(bootstrap_samples=args.bootstrap_samples))
    report = json.loads((output / "report.json").read_text())
    print(f"E19-C termine: {output}"); print(json.dumps({"verdict": report["verdict"], "gates": report["gates"]}))


if __name__ == "__main__":
    main()

