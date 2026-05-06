"""Sprint S25.2 — Vérifie la fraîcheur du dernier rapport d'audit externe.

* < 9 mois : OK silencieux ;
* 9-12 mois : warning (exit 0 mais log) ;
* > 12 mois : fail (exit 1).

Cherche un fichier ``doc/external_audit/<auditor>_<YYYY-MM-DD>/report.md``
ou tout fichier ``doc/external_audit_report_*.md`` à la racine doc.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _latest_report_date() -> date | None:
    candidates: list[date] = []
    audit_root = PROJECT_ROOT / "doc" / "external_audit"
    if audit_root.exists():
        for p in audit_root.iterdir():
            m = _DATE_RE.search(p.name)
            if m:
                try:
                    candidates.append(date.fromisoformat(m.group(1)))
                except ValueError:
                    pass
    for p in (PROJECT_ROOT / "doc").glob("external_audit_report_*.md"):
        m = _DATE_RE.search(p.name)
        if m:
            try:
                candidates.append(date.fromisoformat(m.group(1)))
            except ValueError:
                pass
    if not candidates:
        return None
    return max(candidates)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Vérifie la fraîcheur audit externe.")
    p.add_argument("--warn-days", type=int, default=270,
                   help="Au-delà : warning (défaut 9 mois = 270 j).")
    p.add_argument("--fail-days", type=int, default=365,
                   help="Au-delà : fail (défaut 12 mois = 365 j).")
    args = p.parse_args(argv)

    last = _latest_report_date()
    today = datetime.now(timezone.utc).date()
    if last is None:
        LOGGER.warning("Aucun rapport d'audit externe trouvé "
                       "(doc/external_audit/ ou doc/external_audit_report_*.md).")
        print("[external_audit] no report found")
        return 1
    age = (today - last).days
    print(f"[external_audit] last report : {last} ({age} jours)")
    if age > args.fail_days:
        LOGGER.error("Rapport audit externe trop ancien (> %d j).", args.fail_days)
        return 1
    if age > args.warn_days:
        LOGGER.warning("Rapport audit externe vieillissant (> %d j) — "
                       "prévoir nouvelle mission.", args.warn_days)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

