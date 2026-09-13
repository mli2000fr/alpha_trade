"""E10: filtre d'entree LONG contrariant apres un signal Oracle H20."""
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

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean
from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon
from modelFactory.oracle.predictions_store import load_oracle_predictions
from modelFactory.oracle_post_signal_confirmation import prepare_price_panel

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class E10Config:
    delay: int = 1
    top_pct: float = 0.20
    threshold_grid: tuple[float, ...] = (0.0, 0.0025, 0.005, 0.01, 0.02)
    minimum_events: int = 500
    minimum_coverage: float = 0.15
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260911

    def __post_init__(self) -> None:
        if self.delay != 1:
            raise ValueError("E10 primaire est gele a J+1.")
        if not 0 < self.top_pct < 0.5:
            raise ValueError("top_pct invalide.")
        if not self.threshold_grid or min(self.threshold_grid) < 0:
            raise ValueError("threshold_grid invalide.")
        if not 0 < self.minimum_coverage <= 1:
            raise ValueError("minimum_coverage invalide.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0

    def bootstrap_config(self) -> RollingConfig:
        return RollingConfig(
            top_pct=self.top_pct,
            commission_bps=self.commission_bps,
            slippage_bps=self.slippage_bps,
            bootstrap_samples=self.bootstrap_samples,
            bootstrap_block_sessions=self.bootstrap_block_sessions,
            bootstrap_seed=self.bootstrap_seed,
        )


def _normalise_events(frame: pd.DataFrame, *, fold_column: str) -> pd.DataFrame:
    required = {
        "date", "symbol", "signal_absolute_d1", "delayed_long_net_d1", fold_column,
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Evenements incomplets: {sorted(missing)}")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["fold"] = out[fold_column].astype(str)
    out["signal_absolute_d1"] = pd.to_numeric(
        out["signal_absolute_d1"], errors="coerce"
    )
    out["delayed_long_net_d1"] = pd.to_numeric(
        out["delayed_long_net_d1"], errors="coerce"
    )
    return out.dropna(subset=["date", "symbol", "signal_absolute_d1", "delayed_long_net_d1"])


def select_pullbacks(events: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Selection connue au close J+1, entree LONG seulement a l'open J+2."""
    return events[events["signal_absolute_d1"].le(-threshold)].copy()


def compare_with_delayed_long(
    events: pd.DataFrame, threshold: float, config: E10Config
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected = select_pullbacks(events, threshold)
    selected_dates = pd.Index(selected["date"].unique())
    baseline = events[events["date"].isin(selected_dates)].copy()
    selected_daily = selected.groupby("date")["delayed_long_net_d1"].mean()
    baseline_daily = baseline.groupby("date")["delayed_long_net_d1"].mean()
    daily = pd.concat(
        [selected_daily.rename("selected_long_net"), baseline_daily.rename("baseline_long_net")],
        axis=1,
    ).dropna()
    daily["delta"] = daily["selected_long_net"] - daily["baseline_long_net"]
    bootstrap = config.bootstrap_config()
    selected_ci = block_bootstrap_mean(daily["selected_long_net"], bootstrap)
    delta_ci = block_bootstrap_mean(daily["delta"], bootstrap)

    by_fold_rows: list[dict[str, Any]] = []
    for fold, group in selected.groupby("fold", sort=True):
        dates = pd.Index(group["date"].unique())
        control = events[events["fold"].eq(fold) & events["date"].isin(dates)]
        left = group.groupby("date")["delayed_long_net_d1"].mean()
        right = control.groupby("date")["delayed_long_net_d1"].mean()
        delta = left.sub(right, fill_value=np.nan).dropna()
        by_fold_rows.append({
            "fold": fold,
            "trades": int(len(group)),
            "dates": int(len(delta)),
            "selected_long_net": float(group["delayed_long_net_d1"].mean()),
            "baseline_long_net": float(control["delayed_long_net_d1"].mean()),
            "daily_delta": float(delta.mean()),
        })
    by_fold = pd.DataFrame(by_fold_rows)

    selected = selected.copy()
    selected["semester"] = (
        selected["date"].dt.year.astype(str)
        + "H"
        + np.where(selected["date"].dt.month.le(6), "1", "2")
    )
    by_semester_rows: list[dict[str, Any]] = []
    for semester, group in selected.groupby("semester", sort=True):
        dates = pd.Index(group["date"].unique())
        control = events[events["date"].isin(dates)]
        left = group.groupby("date")["delayed_long_net_d1"].mean()
        right = control.groupby("date")["delayed_long_net_d1"].mean()
        delta = left.sub(right, fill_value=np.nan).dropna()
        by_semester_rows.append({
            "semester": semester,
            "trades": int(len(group)),
            "dates": int(len(delta)),
            "selected_long_net": float(group["delayed_long_net_d1"].mean()),
            "baseline_long_net": float(control["delayed_long_net_d1"].mean()),
            "daily_delta": float(delta.mean()),
        })
    by_semester = pd.DataFrame(by_semester_rows)

    selected_p05 = float(daily["selected_long_net"].quantile(0.05))
    baseline_p05 = float(daily["baseline_long_net"].quantile(0.05))
    metrics = {
        "threshold": float(threshold),
        "eligible_events": int(len(events)),
        "trades": int(len(selected)),
        "coverage": float(len(selected) / len(events)) if len(events) else 0.0,
        "dates": int(len(daily)),
        "symbols": int(selected["symbol"].nunique()),
        "mean_selected_long_net": float(selected["delayed_long_net_d1"].mean()),
        "mean_baseline_long_net_same_dates": float(baseline["delayed_long_net_d1"].mean()),
        "daily_selected_long_net": float(daily["selected_long_net"].mean()),
        "daily_selected_ci95_low": selected_ci[0],
        "daily_selected_ci95_high": selected_ci[1],
        "daily_baseline_long_net": float(daily["baseline_long_net"].mean()),
        "daily_delta": float(daily["delta"].mean()),
        "daily_delta_ci95_low": delta_ci[0],
        "daily_delta_ci95_high": delta_ci[1],
        "positive_fold_ratio": float(by_fold["daily_delta"].gt(0).mean()) if len(by_fold) else 0.0,
        "positive_semester_ratio": (
            float(by_semester["daily_delta"].gt(0).mean()) if len(by_semester) else 0.0
        ),
        "selected_daily_p05": selected_p05,
        "baseline_daily_p05": baseline_p05,
        "daily_p05_delta": selected_p05 - baseline_p05,
    }
    return metrics, daily.reset_index(), by_fold, by_semester


def choose_discovery_threshold(
    events: pd.DataFrame, config: E10Config
) -> tuple[float, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    candidates: list[tuple[float, float]] = []
    for threshold in config.threshold_grid:
        metrics, _, _, _ = compare_with_delayed_long(events, threshold, config)
        eligible = (
            metrics["trades"] >= config.minimum_events
            and metrics["coverage"] >= config.minimum_coverage
        )
        rows.append({**metrics, "selection_eligible": eligible})
        if eligible and np.isfinite(metrics["daily_delta"]):
            candidates.append((metrics["daily_delta"], threshold))
    if not candidates:
        raise ValueError("Aucun seuil de developpement ne respecte volume et couverture.")
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return float(candidates[0][1]), pd.DataFrame(rows)


def build_confirmation_events(
    predictions: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    config: E10Config,
) -> pd.DataFrame:
    required = {"date", "symbol", "proba_extreme", "fold_start"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Predictions Oracle incompletes: {sorted(missing)}")
    pred = predictions.copy()
    pred["date"] = pd.to_datetime(pred["date"], errors="coerce").dt.normalize()
    pred["symbol"] = pred["symbol"].astype(str).str.strip().str.upper()
    pred["proba_extreme"] = pd.to_numeric(pred["proba_extreme"], errors="coerce")
    pred = pred[
        pred["fold_start"].notna()
        & pred["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
    ].dropna(subset=["date", "symbol", "proba_extreme"])
    if pred.duplicated(["date", "symbol"]).any():
        raise ValueError("Doublons Oracle (date,symbol) dans la confirmation.")
    pred["oracle_percentile"] = pred.groupby("date")["proba_extreme"].rank(
        method="average", pct=True
    )
    selected = pred[pred["oracle_percentile"].ge(1.0 - config.top_pct)].copy()
    panel = prepare_price_panel(prices, (config.delay,))
    path_columns = [
        "date", "symbol", "px_close", "reveal_date_d1", "reveal_close_d1",
        "delayed_entry_date_d1", "delayed_entry_open_d1", "terminal_date",
        "terminal_exit_open", "signal_absolute_d1",
    ]
    events = selected.merge(
        panel[path_columns], on=["date", "symbol"], how="left", validate="one_to_one"
    )
    events["delayed_long_net_d1"] = (
        events["terminal_exit_open"] / events["delayed_entry_open_d1"]
        - 1.0
        - config.round_trip_cost
    )
    return _normalise_events(events, fold_column="fold_start")


def evaluate_confirmation(metrics: dict[str, Any], config: E10Config) -> dict[str, Any]:
    gates = {
        "trades_ge_minimum": metrics["trades"] >= config.minimum_events,
        "coverage_ge_minimum": metrics["coverage"] >= config.minimum_coverage,
        "selected_daily_net_positive": metrics["daily_selected_long_net"] > 0,
        "daily_delta_positive": metrics["daily_delta"] > 0,
        "daily_delta_ci95_above_zero": metrics["daily_delta_ci95_low"] > 0,
        "positive_folds_ge_60pct": metrics["positive_fold_ratio"] >= 0.60,
        "positive_semesters_ge_60pct": metrics["positive_semester_ratio"] >= 0.60,
        "daily_p05_not_worse": metrics["daily_p05_delta"] >= 0,
    }
    passed = all(gates.values())
    return {
        "verdict": "GO_RESEARCH_LIFECYCLE" if passed else "NO_GO",
        "gates": gates,
        "promotion_authorized": False,
        "next_step": "E10-B canonical lifecycle replay" if passed else "close E10",
    }


def _profile_summary(artifacts_root: Path, batch_id: str) -> dict[str, Any]:
    path = artifacts_root / batch_id / "oracle" / "feature_profile.json"
    if not path.is_file():
        return {"available": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "sha256": payload.get("sha256"),
        "feature_count": len(payload.get("feature_columns") or []),
        "oracle_universe_mode": payload.get("oracle_universe_mode"),
    }


def run(
    *,
    discovery_artifact: Path,
    confirmation_batch_id: str,
    confirmation_start: str,
    confirmation_end: str,
    artifacts_root: Path,
    output_root: Path,
    config: E10Config,
) -> Path:
    discovery_path = discovery_artifact / "eligible_events.parquet"
    if not discovery_path.is_file():
        raise ValueError(f"Artefact E9 absent: {discovery_path}")
    if resolve_oracle_artifact_horizon(confirmation_batch_id, artifacts_root) != 20:
        raise ValueError("Le batch de confirmation E10 doit etre Oracle H20.")
    discovery = _normalise_events(pd.read_parquet(discovery_path), fold_column="fold_h20")
    discovery_last_date = pd.Timestamp(discovery["date"].max())
    if pd.Timestamp(confirmation_start) <= discovery_last_date:
        raise ValueError("La confirmation doit commencer apres la fin du developpement E9.")
    threshold, grid = choose_discovery_threshold(discovery, config)
    discovery_metrics, _, _, _ = compare_with_delayed_long(discovery, threshold, config)

    engine = get_sqlalchemy_engine()
    predictions = load_oracle_predictions(
        engine,
        batch_id=confirmation_batch_id,
        start_date=confirmation_start,
        end_date=confirmation_end,
    )
    if predictions.empty:
        raise ValueError("Aucune prediction Oracle sur la periode de confirmation.")
    symbols = sorted(predictions["symbol"].astype(str).str.upper().unique())
    price_end = (pd.Timestamp(confirmation_end) + pd.offsets.BDay(25)).date()
    bars = load_universe_bars(
        engine,
        symbols,
        start_date=pd.Timestamp(confirmation_start).date(),
        end_date=price_end,
    )
    confirmation = build_confirmation_events(
        predictions,
        bars,
        start_date=confirmation_start,
        end_date=confirmation_end,
        config=config,
    )
    confirmation_metrics, daily, folds, semesters = compare_with_delayed_long(
        confirmation, threshold, config
    )
    decision = evaluate_confirmation(confirmation_metrics, config)

    run_id = f"oracle-pullback-long-{datetime.now(UTC):%Y%m%d%H%M%S}-{confirmation_batch_id[-6:]}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    grid.to_csv(output / "discovery_threshold_grid.csv", index=False)
    confirmation.to_parquet(output / "confirmation_events.parquet", index=False)
    select_pullbacks(confirmation, threshold).to_parquet(
        output / "confirmation_selected.parquet", index=False
    )
    daily.to_csv(output / "confirmation_daily.csv", index=False)
    folds.to_csv(output / "confirmation_by_fold.csv", index=False)
    semesters.to_csv(output / "confirmation_by_semester.csv", index=False)
    report = {
        "schema_version": 1,
        "experiment": "E10_ORACLE_PULLBACK_LONG",
        "status": "complete",
        "research_only": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "contract": {
            "oracle": "H20 TOP20 amplitude",
            "observation": "close J+1 absolute return",
            "selection": "signal <= -frozen_threshold",
            "entry": "open J+2 LONG",
            "terminal": "open J+21 from original Oracle date",
            "benchmark": "all Oracle TOP20 LONG entered open J+2 on same dates",
            "threshold_selected_on_confirmation": False,
        },
        "config": asdict(config),
        "discovery": {
            "artifact": str(discovery_artifact),
            "first_date": discovery["date"].min().date().isoformat(),
            "last_date": discovery_last_date.date().isoformat(),
            "frozen_threshold": threshold,
            "metrics": discovery_metrics,
        },
        "confirmation": {
            "batch_id": confirmation_batch_id,
            "requested_start": confirmation_start,
            "requested_end": confirmation_end,
            "first_date": confirmation["date"].min().date().isoformat(),
            "last_date": confirmation["date"].max().date().isoformat(),
            "metrics": confirmation_metrics,
            "profile": _profile_summary(artifacts_root, confirmation_batch_id),
        },
        "decision": decision,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E10 termine: %s verdict=%s", output, decision["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery-artifact", type=Path, required=True)
    parser.add_argument("--confirmation-batch-id", required=True)
    parser.add_argument("--confirmation-start", default="2024-07-10")
    parser.add_argument("--confirmation-end", default="2025-07-11")
    parser.add_argument("--artifacts-root", type=Path, default=Path("artifacts/models"))
    parser.add_argument(
        "--output-root", type=Path, default=Path("artifacts/research/oracle_pullback_long")
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    output = run(
        discovery_artifact=args.discovery_artifact,
        confirmation_batch_id=args.confirmation_batch_id,
        confirmation_start=args.confirmation_start,
        confirmation_end=args.confirmation_end,
        artifacts_root=args.artifacts_root,
        output_root=args.output_root,
        config=E10Config(bootstrap_samples=args.bootstrap_samples),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E10 termine: {output}")
    print(report["decision"]["verdict"])


if __name__ == "__main__":
    main()
