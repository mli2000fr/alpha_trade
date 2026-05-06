"""Phase F / S22.2 — Vérifie que la couverture branches est > 95 % sur les 3
modules critiques (``risk_management/``, ``execution_engine/``,
``corporate_actions/``).

Lit ``coverage.json`` (généré par ``pytest --cov-report=json:coverage.json``)
et calcule le ratio ``branches_covered / branches_total`` agrégé par module.

Exit codes :
    0 — OK (tous les modules critiques au-dessus du seuil)
    1 — Échec (au moins un module sous le seuil)
    2 — Erreur (coverage.json absent/illisible)

Usage::

    pytest --cov=. --cov-branch --cov-report=json:coverage.json
    python scripts/check_branch_coverage_critical.py
    python scripts/check_branch_coverage_critical.py --threshold 90.0
    python scripts/check_branch_coverage_critical.py --modules risk_management execution_engine
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "coverage.json"
CRITICAL_MODULES = ("risk_management", "execution_engine", "corporate_actions")
DEFAULT_THRESHOLD = 95.0


def _aggregate(report: dict, module: str) -> tuple[int, int]:
    """Retourne (branches_covered, branches_total) agrégés pour ``module``."""
    files = report.get("files", {})
    covered = total = 0
    prefix = f"{module}/"
    prefix_alt = f"{module}\\"
    for path, data in files.items():
        if not (path.startswith(prefix) or path.startswith(prefix_alt) or path == module):
            continue
        summary = data.get("summary", {})
        # coverage.py expose num_branches / covered_branches en --branch.
        nb = int(summary.get("num_branches", 0) or 0)
        cb = int(summary.get("covered_branches", 0) or 0)
        if nb:
            total += nb
            covered += cb
    return covered, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--modules", nargs="+", default=list(CRITICAL_MODULES))
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[branch-cov] coverage.json absent : {args.input}", file=sys.stderr)
        print("→ Lance d'abord : pytest --cov=. --cov-branch --cov-report=json:coverage.json",
              file=sys.stderr)
        return 2

    try:
        report = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[branch-cov] coverage.json illisible : {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    print(f"[branch-cov] seuil = {args.threshold} %")
    for mod in args.modules:
        covered, total = _aggregate(report, mod)
        if total == 0:
            print(f"  · {mod}: aucune branche détectée (skip)")
            continue
        pct = covered / total * 100.0
        status = "OK" if pct >= args.threshold else "FAIL"
        print(f"  · {mod}: {covered}/{total} branches → {pct:.2f} % [{status}]")
        if pct < args.threshold:
            failures.append(f"{mod}={pct:.2f}%")

    if failures:
        print(f"[branch-cov] ÉCHEC seuil {args.threshold}% : {failures}", file=sys.stderr)
        return 1
    print(f"[branch-cov] OK — tous les modules critiques ≥ {args.threshold} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())

