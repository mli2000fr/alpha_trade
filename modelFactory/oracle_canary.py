"""P0j — canary quotidien de l'Oracle dynamique, strictement shadow.

Le canary ne persiste jamais dans les tables ML. Il produit un score quotidien,
un contrôle de dérive immédiat et, à D+20 disponible, une évaluation réalisée.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.drift_monitor import _psi, compute_drift
from modelFactory.oracle.build_labels import build_labels
from modelFactory.oracle.predict_history import predict_oracle_extreme_history
from modelFactory.oracle.train import precision_recall_at_top_pct, roc_auc
from modelFactory.oracle_universe_p0e_compare import daily_top_metrics
from modelFactory.oracle_universe_p0i_evaluate import load_shadow, prepare_evaluation

DEFAULT_CONFIG = Path("config/oracle_canary.yaml")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    required = ("batch_id", "symbols_file", "baseline_shadow_dir", "artifact_root")
    missing = [key for key in required if not str(config.get(key) or "").strip()]
    if missing:
        raise ValueError(f"Configuration canary incomplète: {','.join(missing)}")
    return config


def load_symbols(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    return sorted({
        value.strip().upper()
        for value in raw.replace("\r", ",").replace("\n", ",").split(",")
        if value.strip()
    })


def latest_benchmark_date(engine: Any, symbol: str = "SPY") -> str:
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT MAX(`date`) FROM stock_bars_daily WHERE symbol=:symbol"),
            {"symbol": symbol},
        ).scalar()
    if value is None:
        raise RuntimeError(f"Aucune barre disponible pour {symbol}")
    return str(value)[:10]


def _percentile(values: np.ndarray, current: float) -> float:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite <= current)) if finite.size else float("nan")


def monitor_distribution(current: pd.DataFrame, baseline: pd.DataFrame, *, model_id: str,
                         champion_age_days: int | None = None) -> dict[str, Any]:
    """Contrôle un jour relativement à la distribution empirique des jours P0i."""
    now = current["proba_extreme"].dropna().to_numpy(dtype=float)
    base = baseline["proba_extreme"].dropna().to_numpy(dtype=float)
    raw = compute_drift(now, base, model_id=model_id).to_payload()
    daily = baseline.groupby("date")["proba_extreme"].agg(["size", "mean", "std"])
    daily_psi = np.asarray([
        _psi(group["proba_extreme"].dropna().to_numpy(dtype=float), base)
        for _, group in baseline.groupby("date")
    ])
    current_psi = float(_psi(now, base))
    current_size = int(len(now))
    current_mean = float(np.mean(now))
    current_std = float(np.std(now))
    psi_q95, psi_q99 = np.quantile(daily_psi, [0.95, 0.99])
    size_q01, size_q99 = np.quantile(daily["size"], [0.01, 0.99])
    mean_q01, mean_q99 = np.quantile(daily["mean"], [0.01, 0.99])
    reasons: list[str] = []
    status = "OK"
    if current_psi > psi_q99 or current_size < 0.9 * size_q01 or current_size > 1.1 * size_q99:
        status = "ALERT"
        reasons.append("distribution_or_coverage_outside_empirical_alert_band")
    elif current_psi > psi_q95 or not size_q01 <= current_size <= size_q99:
        status = "WARN"
        reasons.append("distribution_or_coverage_outside_empirical_warning_band")
    if not mean_q01 <= current_mean <= mean_q99 and status == "OK":
        status = "WARN"
        reasons.append("score_mean_outside_empirical_1_99pct_band")
    if champion_age_days is not None and champion_age_days > 365:
        if status == "OK":
            status = "WARN"
        reasons.append("champion_older_than_365_calendar_days")
    return {
        "status": status,
        "reasons": reasons,
        "current": {"rows": current_size, "score_mean": current_mean,
                    "score_std": current_std, "psi_vs_pooled_baseline": current_psi},
        "empirical_baseline": {
            "dates": int(len(daily)), "rows": int(len(base)),
            "psi_q95": float(psi_q95), "psi_q99": float(psi_q99),
            "universe_q01": float(size_q01), "universe_q99": float(size_q99),
            "score_mean_q01": float(mean_q01), "score_mean_q99": float(mean_q99),
        },
        "raw_two_sample_drift_informational": raw,
        "champion_age_days": champion_age_days,
    }


def daily_realized_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    score = frame["proba_extreme"].to_numpy(dtype=float)
    target = frame["oracle_extreme10"].to_numpy(dtype=float)
    valid = np.isfinite(score) & np.isfinite(target)
    pr20 = precision_recall_at_top_pct(
        frame, "proba_extreme", pct=0.20, target_col="oracle_extreme10"
    )
    daily20 = daily_top_metrics(frame, 0.20)
    return {
        "rows": int(len(frame)), "auc": roc_auc(target[valid], score[valid]),
        "precision_at_20pct": pr20["precision"], "recall_at_20pct": pr20["recall"],
        "top20_amplitude_lift": float(daily20["amplitude_lift"].mean()),
        "top20_mean_abs_return": float(daily20["selected_abs_return"].mean()),
        "top20_positive_rate": float(
            frame.nlargest(max(1, int(np.ceil(len(frame) * 0.20))), "proba_extreme")[
                "future_return"
            ].gt(0).mean()
        ),
    }


def _load_state(path: Path, batch_id: str) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"schema_version": 1, "batch_id": batch_id, "runs": {}}


def _mature_dates(engine: Any, dates: list[str], horizon: int, benchmark: str) -> list[str]:
    if not dates:
        return []
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT DISTINCT `date` FROM stock_bars_daily WHERE symbol=:symbol "
            "AND `date` >= :start ORDER BY `date`"
        ), {"symbol": benchmark, "start": min(dates)}).scalars().all()
    calendar = [str(value)[:10] for value in rows]
    positions = {value: index for index, value in enumerate(calendar)}
    return [value for value in dates if value in positions and len(calendar) - positions[value] - 1 >= horizon + 1]


def evaluate_matured(state: dict[str, Any], *, state_path: Path, config: dict[str, Any],
                     engine: Any, symbols: list[str]) -> int:
    pending = [
        day for day, record in state["runs"].items()
        if record.get("status") == "completed" and not record.get("realized_evaluation")
    ]
    horizon = int(config.get("horizon", 20))
    matured = _mature_dates(
        engine, pending, horizon, str(config.get("benchmark_symbol", "SPY"))
    )
    if not matured:
        return 0
    root = state_path.parent / "evaluation_batches"
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    labels_path = root / f"labels-{min(matured)}-{max(matured)}-{stamp}.parquet"
    result = build_labels(
        str(config["batch_id"]), horizon=horizon, start_date=min(matured),
        end_date=max(matured), engine=engine, dry_run=True,
        universe_mode="pit_dynamic_bars", symbols=symbols,
        output_parquet=str(labels_path),
    )
    if result.get("status") != "dry_run" or not labels_path.is_file():
        raise RuntimeError(f"Reconstruction D+{horizon} échouée: {result}")
    labels = pd.read_parquet(labels_path)
    evaluated_count = 0
    for day in matured:
        record = state["runs"][day]
        scores = load_shadow(Path(record["artifact_dir"]))
        day_labels = labels[
            pd.to_datetime(labels["prediction_date"]).dt.strftime("%Y-%m-%d").eq(day)
        ]
        evaluated, coverage = prepare_evaluation(scores, day_labels)
        if evaluated.empty:
            continue
        record["realized_evaluation"] = {
            "evaluated_at": datetime.now(UTC).isoformat(),
            "labels_path": str(labels_path), "coverage": coverage,
            "metrics": daily_realized_metrics(evaluated),
        }
        evaluated_count += 1
    metrics = [
        record["realized_evaluation"]["metrics"]
        for record in state["runs"].values() if record.get("realized_evaluation")
    ]
    minimum = int(config.get("minimum_rolling_evaluation_dates", 20))
    rolling = metrics[-minimum:]
    state["delayed_monitor"] = {
        "status": "INSUFFICIENT_HISTORY" if len(rolling) < minimum else "OK",
        "evaluated_dates": len(metrics), "required_dates": minimum,
    }
    if len(rolling) >= minimum:
        means = {
            key: float(np.nanmean([item[key] for item in rolling]))
            for key in ("auc", "precision_at_20pct", "top20_amplitude_lift")
        }
        status = "OK"
        if means["auc"] < 0.60 or means["top20_amplitude_lift"] < 1.15:
            status = "ALERT"
        elif means["auc"] < 0.70 or means["top20_amplitude_lift"] < 1.40:
            status = "WARN"
        state["delayed_monitor"].update({"status": status, "rolling": means})
    _write_json_atomic(state_path, state)
    return evaluated_count


def run_canary(config_path: Path, *, prediction_date: str | None = None,
               force: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    if not bool(config.get("enabled", False)):
        return {"status": "disabled", "config": str(config_path)}
    batch_id = str(config["batch_id"])
    symbols = load_symbols(Path(config["symbols_file"]))
    engine = get_sqlalchemy_engine()
    day = prediction_date or latest_benchmark_date(
        engine, str(config.get("benchmark_symbol", "SPY"))
    )
    canary_root = Path(config["artifact_root"]) / batch_id
    state_path = canary_root / "index.json"
    lock_path = canary_root / ".lock"
    canary_root.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(descriptor)
    except FileExistsError as exc:
        raise RuntimeError(f"Un canary P0j est déjà actif: {lock_path}") from exc
    try:
        state = _load_state(state_path, batch_id)
        existing = state["runs"].get(day)
        if existing and existing.get("status") == "completed" and not force:
            evaluated = evaluate_matured(
                state, state_path=state_path, config=config, engine=engine, symbols=symbols
            ) if bool(config.get("auto_evaluate_matured", True)) else 0
            return {"status": "already_completed", "prediction_date": day,
                    "artifact_dir": existing.get("artifact_dir"),
                    "matured_evaluated": evaluated}
        outcome = predict_oracle_extreme_history(
            engine, batch_id, day, day, horizon=int(config.get("horizon", 20)),
            symbols=symbols, shadow_mode=True,
            shadow_artifacts_root=canary_root / "predictions",
        )
        if outcome.get("status") != "completed" or outcome.get("trading_eligible") is not False:
            raise RuntimeError(f"Prédiction canary invalide: {outcome}")
        artifact_dir = Path(str(outcome["artifact_dir"]))
        current = load_shadow(artifact_dir)
        baseline = load_shadow(Path(config["baseline_shadow_dir"]))
        champion = pd.to_datetime(current["champion_t_start"], errors="coerce").max()
        champion_age = (pd.Timestamp(day) - champion).days if pd.notna(champion) else None
        monitor = monitor_distribution(
            current, baseline, model_id=batch_id, champion_age_days=champion_age
        )
        record = {
            "status": "completed", "prediction_date": day,
            "completed_at": datetime.now(UTC).isoformat(),
            "artifact_dir": str(artifact_dir), "prediction": outcome,
            "immediate_monitor": monitor, "trading_eligible": False,
            "research_only": True,
        }
        state["runs"][day] = record
        state["updated_at"] = datetime.now(UTC).isoformat()
        _write_json_atomic(artifact_dir / "canary_report.json", record)
        _write_json_atomic(state_path, state)
        evaluated = evaluate_matured(
            state, state_path=state_path, config=config, engine=engine, symbols=symbols
        ) if bool(config.get("auto_evaluate_matured", True)) else 0
        return {"status": "completed", "prediction_date": day,
                "artifact_dir": str(artifact_dir), "monitor_status": monitor["status"],
                "matured_evaluated": evaluated, "trading_eligible": False}
    finally:
        lock_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="P0j — Oracle dynamic daily shadow canary")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--prediction-date", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.status:
        state_path = Path(config["artifact_root"]) / str(config["batch_id"]) / "index.json"
        print(state_path.read_text(encoding="utf-8") if state_path.is_file() else "{}")
        return
    print(json.dumps(_json_safe(run_canary(
        args.config, prediction_date=args.prediction_date, force=args.force
    )), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
