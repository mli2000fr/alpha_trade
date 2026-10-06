"""Observable CN research fold worker; never changes the frozen model modules."""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from pathlib import Path

PROGRESS_PREFIX = "::cn_fold_progress::"


def progress_stage(output_root: Path, model: str) -> str:
    """Only report milestones that can be verified on disk."""
    if any(output_root.glob("*/h*/*/*/report.json")):
        return "report_written"
    extension = ".txt" if model == "lightgbm" else ".cbm"
    if any(output_root.glob(f"*/h*/*/*/model{extension}")):
        return "model_written"
    if any(output_root.glob("*/h*/*/*")):
        return "sources_verified"
    return "initializing"


def emit_progress(*, task: str, stage: str, elapsed_seconds: int) -> None:
    print(PROGRESS_PREFIX + json.dumps({
        "task": task, "stage": stage, "elapsed_seconds": elapsed_seconds,
    }, ensure_ascii=False, separators=(",", ":")), flush=True)


def latest_progress_event(journal: str) -> dict | None:
    """Extract the last valid CN heartbeat from the managed combined log."""
    for line in reversed(journal.splitlines()):
        if PROGRESS_PREFIX not in line:
            continue
        try:
            event = json.loads(line.split(PROGRESS_PREFIX, 1)[1])
        except (ValueError, json.JSONDecodeError):
            continue
        if event.get("task") in ("oracle", "ranking") and event.get("stage") in (
            "initializing", "sources_verified", "model_written", "report_written", "completed", "failed"
        ):
            return event
    return None


def run_worker(*, task: str, horizon: int, semester: str, model: str,
               output_root: Path, heartbeat_seconds: float = 30.0) -> dict:
    """Emit heartbeats while the unmodified CN fold implementation runs."""
    if task not in ("oracle", "ranking"):
        raise ValueError("Tâche CN inconnue")
    if heartbeat_seconds <= 0:
        raise ValueError("Intervalle de suivi invalide")
    started = time.monotonic()
    done = threading.Event()
    emit_progress(task=task, stage="initializing", elapsed_seconds=0)

    def heartbeat() -> None:
        while not done.wait(heartbeat_seconds):
            emit_progress(task=task, stage=progress_stage(output_root, model),
                          elapsed_seconds=int(time.monotonic() - started))

    thread = threading.Thread(target=heartbeat, name="cn-fold-heartbeat", daemon=True)
    thread.start()
    try:
        if task == "oracle":
            from modelFactory.cn_oracle_walk_forward import run
            report = run(horizon=horizon, semester=semester, model_name=model, output_root=output_root)
        else:
            from modelFactory.cn_global_ranking_walk_forward import run
            report = run(horizon=horizon, semester=semester, model_name=model, output_root=output_root)
        emit_progress(task=task, stage="completed", elapsed_seconds=int(time.monotonic() - started))
        return report
    except Exception:
        emit_progress(task=task, stage="failed", elapsed_seconds=int(time.monotonic() - started))
        raise
    finally:
        done.set()
        thread.join(timeout=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("oracle", "ranking"), required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--test-semester", required=True)
    parser.add_argument("--model", choices=("lightgbm", "catboost"), required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    report = run_worker(task=args.task, horizon=args.horizon, semester=args.test_semester,
                        model=args.model, output_root=args.output_root)
    print(json.dumps({"status": report["status"], "horizon": report["horizon"],
                      "test_semester": report["test_semester"], "model": report["model_name"]},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
