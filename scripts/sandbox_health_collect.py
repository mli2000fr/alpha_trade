"""Sprint S24.2 — Collecte du health-check d'une exécution sandbox nightly.

Lit l'environnement GitHub Actions + les artefacts produits par les
étapes du workflow ``sandbox_nightly.yml`` puis écrit
``artifacts/sandbox_runs/<YYYY-MM-DD>/health.json``.

Usage::

    python scripts/sandbox_health_collect.py \\
        --run-id 1234567890 \\
        --status success \\
        --out artifacts/sandbox_runs/
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)


def _safe_read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect_health(
    *,
    run_id: str,
    status: str,
    sha: str | None = None,
    reconciliation_path: Path | None = None,
    audit_chain_ok: bool | None = None,
    stage_durations: dict[str, float] | None = None,
) -> dict:
    """Construit la structure ``health.json`` (déterministe, testable)."""
    payload: dict = {
        "run_id": run_id,
        "sha": sha or os.environ.get("GITHUB_SHA", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": status.lower(),  # success | failure | cancelled
        "audit_chain_ok": bool(audit_chain_ok) if audit_chain_ok is not None else None,
        "reconciliation": None,
        "stage_durations": dict(stage_durations or {}),
    }
    if reconciliation_path and reconciliation_path.exists():
        recon = _safe_read_json(reconciliation_path) or {}
        payload["reconciliation"] = {
            "n_diffs": recon.get("n_diffs", recon.get("differences", 0)),
            "ok": recon.get("ok", recon.get("matched", True)),
        }
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Collecte le health-check sandbox nightly.")
    p.add_argument("--run-id", required=True)
    p.add_argument("--status", default="success",
                   choices=("success", "failure", "cancelled", "unknown"))
    p.add_argument("--sha", default=None)
    p.add_argument("--out", type=Path, default=Path("artifacts/sandbox_runs/"))
    p.add_argument("--reconciliation", type=Path, default=None,
                   help="Chemin du JSON de reconciliation (optionnel).")
    p.add_argument("--audit-ok", action="store_true",
                   help="Indique que `verify_audit_chain.py` a renvoyé 0.")
    args = p.parse_args(argv)

    payload = collect_health(
        run_id=args.run_id,
        status=args.status,
        sha=args.sha,
        reconciliation_path=args.reconciliation,
        audit_chain_ok=True if args.audit_ok else None,
    )
    date_dir = args.out / payload["date"]
    date_dir.mkdir(parents=True, exist_ok=True)
    target = date_dir / "health.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("health.json écrit : %s", target)
    print(str(target))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

