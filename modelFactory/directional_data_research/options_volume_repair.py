"""Répare et réévalue le ratio volume call/put de la campagne E7 existante."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import fields
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.eroya_directional_poc import EroyaClient
from modelFactory.options_directional_poc import (
    OptionsDirectionalConfig, evaluate_features, fetch_daily_volume,
)

UTC = timezone.utc


def aggregate_four_leg_volumes(values: dict[str, float | None]) -> dict[str, Any]:
    names = ("atm_call", "atm_put", "otm_call", "otm_put")
    available = sum(values.get(name) is not None for name in names)
    if available < 4:
        return {
            "volume_legs_available": available, "call_volume": None,
            "put_volume": None, "call_put_volume_log_ratio": None,
        }
    call_volume = float(values["atm_call"] or 0) + float(values["otm_call"] or 0)
    put_volume = float(values["atm_put"] or 0) + float(values["otm_put"] or 0)
    return {
        "volume_legs_available": 4, "call_volume": call_volume,
        "put_volume": put_volume,
        "call_put_volume_log_ratio": float(np.log((call_volume + 1.0) / (put_volume + 1.0))),
    }


def _load_config(source: Path) -> OptionsDirectionalConfig:
    payload = json.loads((source / "collection_report.json").read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(OptionsDirectionalConfig)}
    values = {key: value for key, value in (payload.get("config") or {}).items() if key in allowed}
    return OptionsDirectionalConfig(**values)


def run(args: argparse.Namespace) -> Path:
    key = os.environ.get("EROYA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("EROYA_API_KEY absente.")
    source = Path(args.source)
    output = args.output or source.parent / f"options-volume-repair-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output.mkdir(parents=True, exist_ok=False)
    frame = pd.read_parquet(source / "option_features.parquet")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    complete = frame[frame["status"].eq("complete")].copy()
    checkpoint = output / "volume_checkpoint.jsonl"
    done: dict[tuple[str, str], dict[str, Any]] = {}
    local = threading.local()

    def task(row: dict[str, Any]) -> dict[str, Any]:
        if not hasattr(local, "client"):
            local.client = EroyaClient(key)
        session_date = pd.Timestamp(row["date"]).date()
        values = {
            name: fetch_daily_volume(local.client, str(row[f"{name}_ticker"]), session_date)
            for name in ("atm_call", "atm_put", "otm_call", "otm_put")
        }
        return {
            "date": session_date.isoformat(), "symbol": str(row["symbol"]),
            "tickers": {name: str(row[f"{name}_ticker"]) for name in values},
            "raw_volumes": values, **aggregate_four_leg_volumes(values),
        }

    rows = complete.to_dict(orient="records")
    with checkpoint.open("w", encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {pool.submit(task, row): row for row in rows}
        for index, future in enumerate(as_completed(futures), start=1):
            source_row = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    "date": str(source_row["date"])[:10], "symbol": str(source_row["symbol"]),
                    "error": f"{type(error).__name__}: {error}", "volume_legs_available": 0,
                    "call_volume": None, "put_volume": None, "call_put_volume_log_ratio": None,
                }
            done[(result["date"], result["symbol"])] = result
            stream.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
            stream.flush()
            if index == 1 or index % 10 == 0 or index == len(rows):
                print(f"events={index}/{len(rows)} symbol={result['symbol']} date={result['date']}", flush=True)
    repaired = frame.copy()
    for index, row in repaired[repaired["status"].eq("complete")].iterrows():
        result = done.get((str(row["date"])[:10], str(row["symbol"])))
        if result:
            for name in ("volume_legs_available", "call_volume", "put_volume", "call_put_volume_log_ratio"):
                repaired.at[index, name] = result.get(name)
    repaired.to_parquet(output / "option_features_repaired.parquet", index=False)
    config = _load_config(source)
    evaluation = evaluate_features(repaired[repaired["status"].eq("complete")].copy(), config)
    coverage = repaired[repaired["status"].eq("complete")]["volume_legs_available"].fillna(0).eq(4)
    report = {
        "schema_version": 1, "experiment": "E7_OPTIONS_VOLUME_KEY_REPAIR",
        "status": "completed", "research_only": True, "serving_ready": False,
        "source": str(source), "events_complete": int(len(complete)),
        "four_leg_volume_events": int(coverage.sum()), "four_leg_volume_coverage": float(coverage.mean()),
        "mapping": "v primary, volume legacy fallback", "config": {field.name: getattr(config, field.name) for field in fields(config)},
        "evaluation": evaluation,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"completed coverage={coverage.mean():.3f} verdict={evaluation['verdict']}", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    path = run(args)
    print(json.dumps({"output": str(path), "report": str(path / "report.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
