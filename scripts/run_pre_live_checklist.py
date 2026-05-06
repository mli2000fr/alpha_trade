"""Sprint S5 — Recette pré-live formalisée.

Wrapper opérateur autour de :func:`execution_engine.preflight.run_preflight`.

- Exécute tous les checks programmatiques.
- Persiste un rapport horodaté dans ``artifacts/pre_live_checks/<ts>_<account>.json``
  (incluant SHA git, utilisateur OS, hostname, version config).
- Imprime un résumé lisible.
- Exit 0/1 selon le statut global ``passed``.

Usage::

    python scripts/run_pre_live_checklist.py --account live1
    python scripts/run_pre_live_checklist.py --account default --skip-network
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("run_pre_live_checklist")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "pre_live_checks"
DEFAULT_CONFIG = ROOT / "config.yaml"

# Ajout au path pour accès aux modules
sys.path.insert(0, str(ROOT))


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=3, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _config_fingerprint(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    p.add_argument("--account", required=True)
    p.add_argument("--broker-mode", choices=("paper", "live"), default="live")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--max-dry-run-age-hours", type=int, default=24)
    p.add_argument("--skip-network", action="store_true")
    p.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.quiet:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from execution_engine.preflight import run_preflight

    engine = None
    try:
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine()
    except Exception as exc:
        LOGGER.warning("DB engine unavailable: %s", exc)

    report = run_preflight(
        account_id=args.account,
        broker_mode=args.broker_mode,
        engine=engine,
        config_path=args.config,
        max_dry_run_age_hours=args.max_dry_run_age_hours,
        skip_network=args.skip_network,
    )

    payload = report.to_dict()
    payload["meta"] = {
        "git_sha": _git_sha(),
        "config_fingerprint": _config_fingerprint(args.config),
        "host": socket.gethostname(),
        "user": getpass.getuser(),
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.report_dir / f"{ts}_{args.account}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if not args.quiet:
        print(f"\n{'=' * 60}")
        print(f"  Pre-live checklist — account={args.account} mode={args.broker_mode}")
        print(f"  git_sha={payload['meta']['git_sha']}  "
              f"config_fp={payload['meta']['config_fingerprint']}")
        print(f"  Report : {out}")
        print(f"  PASSED : {report.passed}")
        print(f"{'=' * 60}")
        for c in report.checks:
            print(f"  [{c.status.upper():4s}] {c.name}: {c.message}")
        print(f"{'=' * 60}")

    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

