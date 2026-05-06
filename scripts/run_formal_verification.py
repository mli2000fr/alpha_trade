"""Phase C / S15 — Lance les preuves Z3 et écrit l'agrégat JSON.

Usage::

    python scripts/run_formal_verification.py
    python scripts/run_formal_verification.py --output artifacts/formal_runs/2026-05-06/proofs.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "formal_runs"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.output is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        args.output = DEFAULT_OUTPUT_DIR / date / "proofs.json"
    args.output.parent.mkdir(parents=True, exist_ok=True)

    from formal.z3_invariants import (  # noqa: E402
        idempotence_corporate_actions,
        no_double_execution,
        oco_synthetic_bracket,
    )

    proofs = {
        "timestamp": datetime.now(UTC).isoformat(),
        "results": {
            "idempotence_corporate_actions": idempotence_corporate_actions.prove(),
            "oco_synthetic_bracket": oco_synthetic_bracket.prove(),
            "no_double_execution": no_double_execution.prove(),
        },
    }
    args.output.write_text(json.dumps(proofs, indent=2, default=str), encoding="utf-8")
    print(f"[formal] preuves écrites : {args.output}")

    failed = []
    for module, results in proofs["results"].items():
        for theorem, status in results.items():
            if status not in ("proved", "skipped") and not theorem.startswith("reason"):
                failed.append(f"{module}.{theorem}={status}")
    if failed:
        print(f"[formal] ÉCHEC : {failed}", file=sys.stderr)
        return 1
    print("[formal] OK : tous les théorèmes prouvés (ou skipped).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

