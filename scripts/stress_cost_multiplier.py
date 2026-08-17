# -*- coding: utf-8 -*-
"""Test 1 (2026-08-17) — Stress test des coûts sur la pile GELÉE B25+H20+top10%+P14+m8.

But : déterminer à quel niveau de coût le système cesse d'être rentable
("marge d'erreur économique"). Le coût réel (canonique) est multiplié par un
facteur ``--cost-multiplier`` (nouveau flag de diagnostic, défaut 1.0 = parité
bit-for-bit avec le benchmark OOS 2026).

Runs (2026-01-02 → 2026-05-31) :
- stress_cost_ctl_m1    → cost_multiplier 1.0  (contrôle, doit = benchmark 27.09%)
- stress_cost_m125      → cost_multiplier 1.25 (+25 %)
- stress_cost_m15       → cost_multiplier 1.50 (+50 %)
- stress_cost_m20       → cost_multiplier 2.00 (×2)
- stress_cost_m30       → cost_multiplier 3.00 (scénario pessimiste)

Stack IDENTIQUE au benchmark : B25, H20 (config backtest_horizon:20, PAS de
--best-horizon pour préserver le sizing stop/TP H10), top 10 %, P14 (défauts
code), m8 (--max-positions 8), coûts canoniques réels.
"""
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
        "--start", START,
        "--end", END,
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
    _log("STRESS-COST START")
    runs = [
        (1.0, "stress_cost_ctl_m1"),
        (1.25, "stress_cost_m125"),
        (1.5, "stress_cost_m15"),
        (2.0, "stress_cost_m20"),
        (3.0, "stress_cost_m30"),
    ]
    procs = []
    for mult, out in runs:
        cmd = _flags(mult, out)
        log_path = ROOT / "logs" / f"{out}_console.log"
        with open(log_path, "ab") as lf:
            lf.write(("CMD: " + " ".join(cmd) + "\n").encode("utf-8"))
        p = subprocess.Popen(cmd, cwd=str(ROOT),
                             stdout=open(log_path, "ab"),
                             stderr=subprocess.STDOUT)
        procs.append((out, mult, p))
        _log(f"START {out} mult={mult} pid={p.pid}")
        time.sleep(15)
    for out, mult, p in procs:
        rc = p.wait()
        _log(f"DONE {out} mult={mult} rc={rc}")
    _log("STRESS-COST ALL DONE")
