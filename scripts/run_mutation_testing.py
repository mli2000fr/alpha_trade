"""Phase C / S14.1 — Wrapper mutation testing (mutmut).

Limite intentionnellement le scope aux modules critiques :
``risk_management/``, ``execution_engine/``, ``corporate_actions/``.
Cible baseline : 50 % score (objectif 70 % en S14-bis).

Usage::

    python scripts/run_mutation_testing.py --module corporate_actions
    python scripts/run_mutation_testing.py --module risk_management
    python scripts/run_mutation_testing.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "mutation_runs"
SUPPORTED_MODULES = ("risk_management", "execution_engine", "corporate_actions")
BASELINE_THRESHOLD = 50.0  # % minimum (échec CI sous ce seuil)


def _parse_mutmut_results(stdout: str) -> dict[str, int]:
    """Parse la sortie ``mutmut results`` (formats variables).

    Cherche les compteurs killed/survived/timeout/skipped.
    """
    counts = {"killed": 0, "survived": 0, "timeout": 0, "skipped": 0}
    for key in counts:
        m = re.search(rf"(\d+)\s+{key}", stdout, re.IGNORECASE)
        if m:
            counts[key] = int(m.group(1))
    return counts


def _run_module(module: str) -> dict:
    try:
        # `mutmut run` modifie le code in-place ; on isole avec --paths-to-mutate
        proc_run = subprocess.run(
            ["mutmut", "run", "--paths-to-mutate", module,
             "--runner", "pytest -x -q --no-cov"],
            capture_output=True, text=True, cwd=ROOT, timeout=1800,
        )
    except FileNotFoundError:
        return {"module": module, "status": "skipped", "reason": "mutmut absent"}
    except subprocess.TimeoutExpired:
        return {"module": module, "status": "timeout"}

    proc_results = subprocess.run(
        ["mutmut", "results"], capture_output=True, text=True, cwd=ROOT,
    )
    counts = _parse_mutmut_results(proc_results.stdout)
    total = sum(counts.values())
    score = (counts["killed"] / total * 100.0) if total else 0.0
    return {
        "module": module,
        "status": "ok",
        "counts": counts,
        "total": total,
        "killed": counts["killed"],
        "survived": counts["survived"],
        "score_pct": round(score, 2),
        "rc_run": proc_run.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=SUPPORTED_MODULES, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--threshold", type=float, default=BASELINE_THRESHOLD)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.all and args.module is None:
        parser.error("--module ou --all requis")

    modules = SUPPORTED_MODULES if args.all else (args.module,)
    if args.output is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        args.output = DEFAULT_OUTPUT_DIR / date / "score.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)

    results = [_run_module(m) for m in modules]
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "threshold_pct": args.threshold,
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[mutation] résultats écrits : {args.output}")

    failed = []
    for r in results:
        if r.get("status") == "skipped":
            continue
        if r.get("score_pct", 0.0) < args.threshold:
            failed.append(f"{r['module']}={r.get('score_pct', 0)}%")
    if failed:
        print(f"[mutation] ÉCHEC seuil {args.threshold}% : {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

