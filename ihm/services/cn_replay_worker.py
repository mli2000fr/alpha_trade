"""Observable wrapper around the frozen CN economic research replay."""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from pathlib import Path

PROGRESS_PREFIX = "::cn_replay_progress::"


def progress_stage(output_root: Path) -> str:
    """Infer only milestones verifiable from replay artifacts."""
    if any(output_root.glob("sprint13b-*/report.json")):
        return "report_written"
    if any(output_root.glob("sprint13b-*/*/report.json")):
        return "cell_written"
    if any(output_root.glob("sprint13b-*")):
        return "replaying"
    return "initializing"


def emit_progress(*, stage: str, elapsed_seconds: int) -> None:
    print(PROGRESS_PREFIX + json.dumps({
        "stage": stage, "elapsed_seconds": elapsed_seconds,
    }, ensure_ascii=False, separators=(",", ":")), flush=True)


def latest_progress_event(journal: str) -> dict | None:
    for line in reversed(journal.splitlines()):
        if PROGRESS_PREFIX not in line:
            continue
        try:
            event = json.loads(line.split(PROGRESS_PREFIX, 1)[1])
        except (ValueError, json.JSONDecodeError):
            continue
        if event.get("stage") in (
            "initializing", "replaying", "cell_written", "report_written", "completed", "failed"
        ):
            return event
    return None


def run_worker(*, market_code: str, database_alias: str, semester: str, policy: str,
               seed: int, scenario: str, cost_profile: str, evidence: Path,
               output_root: Path, heartbeat_seconds: float = 30.0) -> dict:
    if market_code != "CN_A" or database_alias != "cn_primary":
        raise ValueError("Replay réservé à CN_A / cn_primary")
    if heartbeat_seconds <= 0:
        raise ValueError("Intervalle de suivi invalide")
    started = time.monotonic()
    done = threading.Event()
    emit_progress(stage="initializing", elapsed_seconds=0)

    def heartbeat() -> None:
        while not done.wait(heartbeat_seconds):
            emit_progress(stage=progress_stage(output_root),
                          elapsed_seconds=int(time.monotonic() - started))

    thread = threading.Thread(target=heartbeat, name="cn-replay-heartbeat", daemon=True)
    thread.start()
    try:
        from modelFactory.cn_economic_replay_13b import run

        report = run(output_root=output_root, evidence_path=evidence,
                     semesters=[semester], policies=[policy], seeds=[seed],
                     scenarios=[scenario], cost_profiles=[cost_profile])
        emit_progress(stage="completed", elapsed_seconds=int(time.monotonic() - started))
        return report
    except Exception:
        emit_progress(stage="failed", elapsed_seconds=int(time.monotonic() - started))
        raise
    finally:
        done.set()
        thread.join(timeout=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-code", choices=("CN_A",), required=True)
    parser.add_argument("--database-alias", choices=("cn_primary",), required=True)
    parser.add_argument("--semesters", nargs=1, required=True)
    parser.add_argument("--policies", nargs=1, required=True)
    parser.add_argument("--seeds", nargs=1, type=int, required=True)
    parser.add_argument("--scenarios", nargs=1, required=True)
    parser.add_argument("--cost-profiles", nargs=1, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = run_worker(
        market_code=args.market_code, database_alias=args.database_alias,
        semester=args.semesters[0], policy=args.policies[0], seed=args.seeds[0],
        scenario=args.scenarios[0], cost_profile=args.cost_profiles[0],
        evidence=args.evidence, output_root=args.output_root,
    )
    print(json.dumps({"status": report["status"], "report_path": report["report_path"],
                      "runs": len(report["runs"])}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
