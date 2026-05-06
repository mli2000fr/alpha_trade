"""Phase F / S22.3 — Liste les mutants survivants après ``mutmut run``.

Wrapper autour de ``mutmut results`` qui extrait les IDs survivants et émet
un ``survivors.json`` consommable par les développeurs pour ajouter des tests
killer ciblés.

Usage::

    mutmut run --paths-to-mutate corporate_actions
    python scripts/list_mutation_survivors.py --module corporate_actions
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


def _list_survivors() -> list[str]:
    try:
        proc = subprocess.run(
            ["mutmut", "results"], capture_output=True, text=True, cwd=ROOT, timeout=120,
        )
    except FileNotFoundError:
        return []
    survivors: list[str] = []
    in_section = False
    for line in proc.stdout.splitlines():
        low = line.lower()
        if "survived" in low:
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if not stripped:
                in_section = False
                continue
            for token in re.findall(r"\b\d+\b", stripped):
                survivors.append(token)
    return survivors


def _show(mutant_id: str) -> str:
    try:
        proc = subprocess.run(
            ["mutmut", "show", mutant_id], capture_output=True, text=True, cwd=ROOT, timeout=30,
        )
        return proc.stdout
    except Exception as exc:
        return f"<show failed: {exc}>"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=SUPPORTED_MODULES, default=None)
    parser.add_argument("--max-detail", type=int, default=20,
                        help="Nombre max de mutants détaillés (mutmut show)")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    survivors = _list_survivors()
    details: dict[str, str] = {}
    for mid in survivors[: args.max_detail]:
        details[mid] = _show(mid)

    if args.output is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        args.output = DEFAULT_OUTPUT_DIR / date / "survivors.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "module": args.module,
        "count": len(survivors),
        "ids": survivors,
        "details": details,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[mutation-survivors] {len(survivors)} survivants → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

