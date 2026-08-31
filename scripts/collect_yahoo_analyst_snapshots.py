#!/usr/bin/env python
"""CLI de collecte quotidienne Yahoo analyst (RESEARCH ONLY).

Usage :
    python scripts/collect_yahoo_analyst_snapshots.py --universe analyst_research --write-db
    python scripts/collect_yahoo_analyst_snapshots.py --symbols AAPL,MSFT,NVDA --dry-run
    python scripts/collect_yahoo_analyst_snapshots.py --universe analyst_research \
        --write-db --resume

Options :
    --universe analyst_research   Univers configuré (liste figée ~400 symboles).
    --symbols A,B,C               Surcharge temporaire de l'univers (tests manuels).
    --max-symbols N               Limite (POC).
    --dry-run                     Aucune écriture DB, aucun run tracé.
    --write-db                    Persiste dans MySQL (append-only, idempotent).
    --resume                      Saute les symboles déjà collectés aujourd'hui.
    --sleep-seconds / --timeout-seconds / --max-retries   Réseau.
    --run-id                      Identifiant de run (défaut auto).

Il n'existe volontairement PAS d'option ``--write-file`` : le seul stockage est
MySQL (les réponses brutes sont conservées dans ``raw_payload_json``).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Bootstrap : rend la racine du dépôt importable même quand le script est
# lancé PAR CHEMIN (`python scripts/collect_yahoo_analyst_snapshots.py`) —
# sinon sys.path[0] = scripts/ et les packages racine (`analyst_research`,
# `common`, `database`) ne sont pas résolus.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from analyst_research.available_at import snapshot_date_of
from analyst_research.collector import run_collection
from analyst_research.universe import resolve_universe
from common.config_loader import load_config
from database.repositories.analyst_snapshots import AnalystSnapshotRepository


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)

LOGGER = logging.getLogger("collect_yahoo_analyst_snapshots")


def _setup_logging(log_file: str | None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler
            handlers.append(RotatingFileHandler(log_file, maxBytes=5_000_000,
                                                backupCount=3, encoding="utf-8"))
        except OSError as e:  # pragma: no cover
            LOGGER.warning("log_file %s inaccessible (%s)", log_file, e)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collecte Yahoo analyst (RESEARCH ONLY).")
    parser.add_argument("--universe", default="analyst_research")
    parser.add_argument("--symbols", default=None, help="Surcharge : AAPL,MSFT,NVDA")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--log-file", default=None)
    args = parser.parse_args(argv)

    cfg = (load_config().get("analyst_snapshot_collection") or {})
    _setup_logging(args.log_file or cfg.get("log_file"))

    universe = resolve_universe(args.universe, args.symbols)
    if args.max_symbols:
        universe = universe[: args.max_symbols]
    LOGGER.info("univers %s : %d symboles", args.universe or "cli", len(universe))

    if args.resume and args.write_db and not args.dry_run:
        done = AnalystSnapshotRepository().get_symbols_with_snapshot_on(
            snapshot_date_of(_utcnow())
        )
        skipped = sorted(set(universe) & done)
        if skipped:
            universe = [s for s in universe if s not in done]
            LOGGER.info("--resume : %d symboles déjà collectés aujourd'hui, restants=%d",
                        len(skipped), len(universe))
    if not universe:
        LOGGER.warning("univers vide après résumé — rien à faire")
        return 0

    summary = run_collection(
        universe,
        write_db=args.write_db,
        dry_run=args.dry_run,
        sleep_seconds=args.sleep_seconds if args.sleep_seconds is not None else cfg.get("sleep_seconds", 0.25),
        timeout_seconds=args.timeout_seconds if args.timeout_seconds is not None else cfg.get("timeout_seconds", 20.0),
        max_retries=args.max_retries if args.max_retries is not None else cfg.get("max_retries", 2),
        run_id=args.run_id,
    )

    print("\n" + "=" * 60)
    print("COLLECTION SUMMARY")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
