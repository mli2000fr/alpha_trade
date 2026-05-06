"""Sprint S12.2 — CLI de vérification du chaînage d'audit HMAC.

Usage::

    python scripts/verify_audit_chain.py --run-kind execution_runs --strict

Exit 0 si la chaîne est intègre. Exit 1 si des anomalies sont détectées.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Sequence

LOGGER = logging.getLogger("scripts.verify_audit_chain")


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Vérifie la chaîne d'audit HMAC SOX-like.")
    parser.add_argument("--run-kind", default=None,
                        help="Filtrer sur un run_kind (sinon toutes les chaînes).")
    parser.add_argument("--strict", action="store_true",
                        help="Exit code 1 si la moindre anomalie est détectée.")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Sortie JSON (machine-readable).")
    args = parser.parse_args(argv)

    try:
        from database.audit_chain import AuditChainRepository
        from database.connection import get_sqlalchemy_engine
    except Exception as exc:  # pragma: no cover
        LOGGER.error("Imports indisponibles: %s", exc)
        return 2

    try:
        engine = get_sqlalchemy_engine()
    except RuntimeError as exc:
        LOGGER.error("DB indisponible: %s", exc)
        return 2

    repo = AuditChainRepository(engine)
    anomalies = repo.verify_chain(args.run_kind)

    if args.as_json:
        print(json.dumps(
            {"anomalies": [a.to_dict() for a in anomalies], "count": len(anomalies)},
            indent=2,
        ))
    else:
        if not anomalies:
            print(f"[OK] Audit chain intègre (run_kind={args.run_kind or 'ALL'}).")
        else:
            print(f"[FAIL] {len(anomalies)} anomalie(s) détectée(s):")
            for a in anomalies:
                print(f"  - {a.run_kind}#{a.event_id} reason={a.reason}")

    if anomalies and args.strict:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

