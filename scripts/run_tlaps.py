"""Sprint S24.3 — Wrapper d'invocation TLAPS / TLC.

Lance ``tlapm`` (TLA+ Proof Manager) sur les 3 spécifications de
``formal/tla/`` puis écrit ``artifacts/formal_runs/<date>/tlaps.json``.
Si ``tlapm`` est absent (cas commun en CI hors image dédiée), tombe
en fallback sur ``tlc2.TLC`` model-checking et marque le rapport
``tool="tlc"`` au lieu de ``tool="tlaps"``.

Usage::

    python scripts/run_tlaps.py --out artifacts/formal_runs/
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)

TLA_DIR = Path(__file__).resolve().parent.parent / "formal" / "tla"
SPECS = ("IdempotenceCA.tla", "OCOBracket.tla", "NoDoubleExec.tla")


def _run_tlapm(spec: Path) -> dict:
    """Tente l'exécution de tlapm. Retourne dict {ok, stdout, stderr}."""
    try:
        proc = subprocess.run(
            ["tlapm", str(spec)],
            capture_output=True, text=True, timeout=300,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": -1, "stderr": "tlapm not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stderr": "timeout"}


def _run_tlc(spec: Path) -> dict:
    """Fallback : model-check via tla2tools (tlc2.TLC)."""
    jar = shutil.which("tla2tools.jar") or "tla2tools.jar"
    try:
        proc = subprocess.run(
            ["java", "-cp", jar, "tlc2.TLC", "-deadlock", str(spec)],
            capture_output=True, text=True, timeout=600,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": -1, "stderr": "java/tla2tools missing"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stderr": "timeout"}


def run_all(out_dir: Path) -> dict:
    has_tlapm = shutil.which("tlapm") is not None
    tool = "tlaps" if has_tlapm else "tlc-fallback"

    results: list[dict] = []
    for spec_name in SPECS:
        spec_path = TLA_DIR / spec_name
        if not spec_path.exists():
            results.append({"spec": spec_name, "ok": False,
                            "error": "spec missing"})
            continue
        outcome = _run_tlapm(spec_path) if has_tlapm else _run_tlc(spec_path)
        results.append({"spec": spec_name, "tool": tool, **outcome})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "n_specs": len(results),
        "n_ok": sum(1 for r in results if r.get("ok")),
        "n_failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }
    date_dir = out_dir / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    target = date_dir / "tlaps.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("tlaps.json écrit : %s", target)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Run TLAPS proofs (avec fallback TLC).")
    p.add_argument("--out", type=Path, default=Path("artifacts/formal_runs/"))
    p.add_argument("--strict", action="store_true",
                   help="Exit 1 si une preuve échoue.")
    args = p.parse_args(argv)

    payload = run_all(args.out)
    print(f"[tlaps] tool={payload['tool']} ok={payload['n_ok']}/{payload['n_specs']}")
    if args.strict and payload["n_failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

