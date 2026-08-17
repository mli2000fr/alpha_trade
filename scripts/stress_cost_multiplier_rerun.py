# -*- coding: utf-8 -*-
"""Relance des runs m20 et m30 (Test 1) après purge du cache bytecode."""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PROGRESS = ROOT / "logs" / "stress_cost_multiplier_progress.txt"
B25 = "model-factory-20260811223551-ef2cd0"
START, END = "2026-01-02", "2026-05-31"


def _log(line: str) -> None:
    with open(PROGRESS, "a", encoding="utf-8") as fh:
        fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")


def _flags(mult: float, out: str) -> list[str]:
    return [
        str(PY), "-X", "utf8", "-m", "backtesting", "run",
        "--engine-mode", "pipeline",
        "--ml-pit-strategy", "use-persisted",
        "--phase2-mode", "risk_execution",
        "--phase3-mode", "execution_replay",
        "--phase4-mode", "protection_replay",
        "--phase5-mode", "watcher_replay",
        "--phase7-mode", "exit_lifecycle_replay",
        "--start", START, "--end", END,
        "--ml-batch-id", B25,
        "--cascade-batch-id", B25,
        "--batch-diagnostics-batch-id", B25,
        "--cascade-top-pct", "0.10",
        "--min-ml-coverage-ratio", "0.90",
        "--capital-preset-key", "capital_2001_5000",
        "--max-positions", "8",
        "--use-canonical-costs",
        "--cost-multiplier", f"{mult:g}",
        "--atr-risk-stop-multiple", "2.5",
        "--tp-atr-multiple", "3.0",
        "--tp-max-pct", "0.07",
        "--output-dir", str(ROOT / "artifacts" / "backtesting" / out),
    ]


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    _log("STRESS-COST RERUN m20/m30 START")
    runs = [(2.0, "stress_cost_m20"), (3.0, "stress_cost_m30")]
    procs = []
    for mult, out in runs:
        cmd = _flags(mult, out)
        log_path = ROOT / "logs" / f"{out}_rerun_console.log"
        with open(log_path, "ab") as lf:
            lf.write(("CMD: " + " ".join(cmd) + "\n").encode("utf-8"))
        p = subprocess.Popen(cmd, cwd=str(ROOT),
                             stdout=open(log_path, "ab"),
                             stderr=subprocess.STDOUT)
        procs.append((out, mult, p))
        _log(f"RERUN START {out} mult={mult} pid={p.pid}")
        time.sleep(10)
    for out, mult, p in procs:
        rc = p.wait()
        _log(f"RERUN DONE {out} mult={mult} rc={rc}")
    _log("STRESS-COST RERUN ALL DONE")
