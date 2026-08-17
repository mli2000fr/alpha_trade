# -*- coding: utf-8 -*-
"""Test 1b (2026-08-17) — Stress coûts ABSOLU + fallback (dernière série).

Deux familles de scénarios sur la pile gelée B25+H20+top10%+P14+m8 (2026) :

Série A — coût round-trip ABSOLU forcé (--cost-round-trip-bps) :
- cost_rt10  → 10 bps RT (≈ coût actuel, contrôle)
- cost_rt20  → 20 bps RT (prudent)
- cost_rt30  → 30 bps RT (très prudent)
- cost_rt44  → 44 bps RT (pessimiste = médiane globale observée)
- cost_rt60  → 60 bps RT (extrême)

Série B — fallback de spread relevé (--fallback-spread-bps), données absentes
ou corrompues (>300 bps) rejetées, coût variable canonique conservé :
- fb10 → fallback 10 bps
- fb15 → fallback 15 bps
- fb20 → fallback 20 bps

Note : --cost-round-trip-bps et --fallback-spread-bps sont exclusifs (ne pas
combiner). coût RT forcé = C/2 à l'entrée + C/2 à la sortie, spread réel ignoré.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PROGRESS = ROOT / "logs" / "stress_cost_abs_progress.txt"
B25 = "model-factory-20260811223551-ef2cd0"
START, END = "2026-01-02", "2026-05-31"


def _log(line: str) -> None:
    with open(PROGRESS, "a", encoding="utf-8") as fh:
        fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")


def _flags(out: str, extra: list[str]) -> list[str]:
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
        "--atr-risk-stop-multiple", "2.5",
        "--tp-atr-multiple", "3.0",
        "--tp-max-pct", "0.07",
    ] + extra + [
        "--output-dir", str(ROOT / "artifacts" / "backtesting" / out),
    ]


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    _log("STRESS-COST-ABS START")
    runs = [
        ("cost_rt10", ["--cost-round-trip-bps", "10"]),
        ("cost_rt20", ["--cost-round-trip-bps", "20"]),
        ("cost_rt30", ["--cost-round-trip-bps", "30"]),
        ("cost_rt44", ["--cost-round-trip-bps", "44"]),
        ("cost_rt60", ["--cost-round-trip-bps", "60"]),
        ("fb10", ["--fallback-spread-bps", "10"]),
        ("fb15", ["--fallback-spread-bps", "15"]),
        ("fb20", ["--fallback-spread-bps", "20"]),
    ]
    procs = []
    for out, extra in runs:
        cmd = _flags(out, extra)
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
    _log("STRESS-COST-ABS ALL DONE")
