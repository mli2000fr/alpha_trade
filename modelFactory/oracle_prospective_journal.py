"""Research-only, point-in-time candidate journal for fresh Oracle canary runs.

The timestamp proves when the score artifact was finished locally. It does not
prove when every upstream input first became available or authorize trading.
"""
from __future__ import annotations

import hashlib
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


def journal_freshness(prediction_date: str, observed_at: datetime) -> str:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    day = pd.Timestamp(prediction_date).date()
    local_day = observed_at.astimezone(ZoneInfo("America/New_York")).date()
    return "CURRENT_NY_DATE" if day == local_day else "HISTORICAL_OR_FUTURE_DATE"


def canary_input_preflight(config: dict, prediction_date: str, observed_at: datetime,
                           *, explicit_date: bool = False,
                           workspace_root: Path = Path(".")) -> dict:
    """Check local model artifacts and reject stale implicit daily runs."""
    batch_id = str(config["batch_id"])
    champions = workspace_root / "artifacts/models/oracle/champions" / batch_id / "oracle_champions.json"
    baseline = workspace_root / str(config["baseline_shadow_dir"]) / "parts"
    blockers = []
    if not champions.is_file():
        blockers.append("MISSING_ORACLE_CHAMPIONS")
    if not baseline.is_dir() or not any(baseline.glob("*.parquet")):
        blockers.append("MISSING_BASELINE_SHADOW_PARTS")
    freshness = journal_freshness(prediction_date, observed_at)
    if not explicit_date and freshness != "CURRENT_NY_DATE":
        blockers.append("STALE_LATEST_BENCHMARK_DATE")
    return {
        "status": "READY" if not blockers else "BLOCKED_PREFLIGHT",
        "prediction_date": prediction_date,
        "freshness": freshness,
        "blockers": blockers,
        "trading_eligible": False,
    }


def write_prospective_score_journal(
    scores: pd.DataFrame, *, artifact_dir: Path, batch_id: str,
    prediction_date: str, run_started_at: datetime, observed_at: datetime,
) -> dict:
    """Write a candidate only for today's NY date; never infer input PIT status."""
    freshness = journal_freshness(prediction_date, observed_at)
    if freshness != "CURRENT_NY_DATE":
        return {"status": "SKIPPED_STALE_DATE", "prediction_date": prediction_date,
                "observed_at": observed_at.astimezone(UTC).isoformat()}
    if run_started_at.tzinfo is None or run_started_at.utcoffset() is None:
        raise ValueError("run_started_at must be timezone-aware")
    if run_started_at > observed_at:
        raise ValueError("run_started_at is after observed_at")
    required = {"date", "symbol", "proba_extreme", "champion_t_start"}
    missing = required - set(scores.columns)
    if missing:
        raise ValueError(f"missing score columns: {sorted(missing)}")
    if scores.empty or scores["symbol"].isna().any() or scores["symbol"].duplicated().any():
        raise ValueError("score universe empty or symbol identity invalid")
    dates = pd.to_datetime(scores["date"], errors="coerce").dt.date
    if dates.isna().any() or not dates.eq(pd.Timestamp(prediction_date).date()).all():
        raise ValueError("score dates differ from prediction_date")
    probabilities = pd.to_numeric(scores["proba_extreme"], errors="coerce")
    if not probabilities.map(lambda value: math.isfinite(value) and 0 <= value <= 1).all():
        raise ValueError("scores must be finite probabilities in [0,1]")
    journal = pd.DataFrame({
        "prediction_date": prediction_date,
        "symbol": scores["symbol"].astype(str).str.upper(),
        "oracle_score": probabilities.astype(float),
        "champion_t_start": scores["champion_t_start"].astype(str),
    })
    if journal["symbol"].duplicated().any():
        raise ValueError("normalized symbols are not unique")
    journal["oracle_percentile"] = journal["oracle_score"].rank(pct=True)
    journal["oracle_top20"] = journal["oracle_percentile"].ge(0.80)
    journal["universe_size"] = len(journal)
    journal["batch_id"] = batch_id
    journal["run_started_at_utc"] = run_started_at.astimezone(UTC).isoformat()
    journal["score_artifact_available_at_utc"] = observed_at.astimezone(UTC).isoformat()
    journal["trading_eligible"] = False
    journal = journal.sort_values("symbol").reset_index(drop=True)
    path = artifact_dir / "prospective_score_journal.jsonl"
    if path.exists():
        raise FileExistsError(f"prospective journal is immutable: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(journal.to_json(orient="records", lines=True), encoding="utf-8")
    os.replace(temporary, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "status": "CANDIDATE_INPUT_PIT_UNVERIFIED",
        "prediction_date": prediction_date,
        "run_started_at_utc": run_started_at.astimezone(UTC).isoformat(),
        "score_artifact_available_at_utc": observed_at.astimezone(UTC).isoformat(),
        "rows": len(journal), "top20_rows": int(journal["oracle_top20"].sum()),
        "path": str(path), "sha256": digest, "trading_eligible": False,
    }
