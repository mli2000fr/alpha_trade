# -*- coding: utf-8 -*-
"""Mesure du biais pullback (2026-08-17) — exécution au marché vs pullback 1%.

4 runs :
- pb_ctl_2026   : benchmark 2026 pile gelée, pullback 0.01 (contrôle parité = 27.09%)
- pb0_2026      : benchmark 2026 pile gelée, pullback 0 (exécution au marché)
- ihm2526_ctl   : run IHM 2025-2026 équivalent (TP12/TS7/m8), pullback 0.01 (contrôle ≈ 63.9%)
- ihm2526_pb0   : run IHM 2025-2026 équivalent (TP12/TS7/m8), pullback 0

B25, H20 (config backtest_horizon:20), top10, min_prob 0.55, coûts canoniques.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PROGRESS = ROOT / "logs" / "pullback_bias_progress.txt"
B25 = "model-factory-20260811223551-ef2cd0"


def _log(line: str) -> None:
    with open(PROGRESS, "a", encoding="utf-8") as fh:
        fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")


def _base(start: str, end: str, out: str) -> list[str]:
    return [
        str(PY), "-X", "utf8", "-m", "backtesting", "run",
        "--engine-mode", "pipeline",
        "--ml-pit-strategy", "use-persisted",
        "--phase2-mode", "risk_execution",
        "--phase3-mode", "execution_replay",
        "--phase4-mode", "protection_replay",
        "--phase5-mode", "watcher_replay",
        "--phase7-mode", "exit_lifecycle_replay",
        "--start", start, "--end", end,
        "--ml-batch-id", B25,
        "--cascade-batch-id", B25,
        "--batch-diagnostics-batch-id", B25,
        "--cascade-top-pct", "0.10",
        "--min-ml-coverage-ratio", "0.90",
        "--capital-preset-key", "capital_2001_5000",
        "--max-positions", "8",
        "--use-canonical-costs",
        "--output-dir", str(ROOT / "artifacts" / "backtesting" / out),
    ]


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    _log("PULLBACK-BIAS START")
    runs = [
        # (out, start, end, extra)
        ("pb_ctl_2026", "2026-01-02", "2026-05-31",
         ["--atr-risk-stop-multiple", "2.5", "--tp-atr-multiple", "3.0", "--tp-max-pct", "0.07",
          "--entry-limit-offset-pct", "0.01"]),
        ("pb0_2026", "2026-01-02", "2026-05-31",
         ["--atr-risk-stop-multiple", "2.5", "--tp-atr-multiple", "3.0", "--tp-max-pct", "0.07",
          "--entry-limit-offset-pct", "0"]),
        ("ihm2526_ctl", "2025-01-01", "2026-05-31",
         ["--equity", "4000", "--tp", "0.12", "--ts", "0.07",
          "--entry-limit-offset-pct", "0.01"]),
        ("ihm2526_pb0", "2025-01-01", "2026-05-31",
         ["--equity", "4000", "--tp", "0.12", "--ts", "0.07",
          "--entry-limit-offset-pct", "0"]),
    ]
    procs = []
    for out, start, end, extra in runs:
        cmd = _base(start, end, out) + extra
        log_path = ROOT / "logs" / f"{out}_console.log"
        with open(log_path, "ab") as lf:
            lf.write(("CMD: " + " ".join(cmd) + "\n").encode("utf-8"))
        p = subprocess.Popen(cmd, cwd=str(ROOT),
                             stdout=open(log_path, "ab"),
                             stderr=subprocess.STDOUT)
        procs.append((out, p))
        _log(f"START {out} pid={p.pid}")
        time.sleep(12)
    for out, p in procs:
        rc = p.wait()
        _log(f"DONE {out} rc={rc}")
    _log("PULLBACK-BIAS ALL DONE")
