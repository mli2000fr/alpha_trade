# -*- coding: utf-8 -*-
"""Test 2 (2026-08-17) — Stress test FILLS / SLIPPAGE sur la pile gelée B25+H20+top10%+P14+m8.

But : mesurer la robustesse à la détérioration de la QUALITÉ d'exécution
(fills partiels → impact volume ; latence → prix ≠ open/mid). Pas pour choisir
un paramètre — uniquement pour mesurer la marge de robustesse.

Le baseline (benchmark 27.09 %) n'a AUCUN slippage volume : preset capital_2001_5000
→ slippage_base_bps=0, impact_coef=0, model=fixed. Seul le coût canonique
(spread réel + comm 1bps + slippage 2bps) s'applique.

Runs (2026-01-02 → 2026-05-31) :
- fills_ctl          → --slippage-model sqrt, base 0, impact 0   (contrôle = benchmark)
- fills_imp50        → sqrt, base 0, impact 50 bps   (fills légèrement dégradés)
- fills_imp100       → sqrt, base 0, impact 100 bps  (dégradation moyenne)
- fills_imp200       → sqrt, base 0, impact 200 bps  (forte dégradation)
- fills_lat5         → sqrt, base 5, impact 100 bps  (latence systématique + impact)
- fills_arrival50    → --execution-model arrival_price, factor 0.5 (latence prix ≠ open)

Note : --slippage-model sqrt/impact s'ajoute au coût canonique en extra_slippage
(sortie). Le replay phase3 n'est pas modifié. arrival_price testé séparément.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PROGRESS = ROOT / "logs" / "stress_fills_progress.txt"
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
    _log("STRESS-FILLS START")
    runs = [
        ("fills_ctl", ["--slippage-model", "sqrt", "--slippage-base-bps", "0", "--slippage-impact-coef", "0"]),
        ("fills_imp50", ["--slippage-model", "sqrt", "--slippage-base-bps", "0", "--slippage-impact-coef", "50"]),
        ("fills_imp100", ["--slippage-model", "sqrt", "--slippage-base-bps", "0", "--slippage-impact-coef", "100"]),
        ("fills_imp200", ["--slippage-model", "sqrt", "--slippage-base-bps", "0", "--slippage-impact-coef", "200"]),
        ("fills_lat5", ["--slippage-model", "sqrt", "--slippage-base-bps", "5", "--slippage-impact-coef", "100"]),
        ("fills_arrival50", ["--execution-model", "arrival_price", "--execution-arrival-slippage-factor", "0.5"]),
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
    _log("STRESS-FILLS ALL DONE")
