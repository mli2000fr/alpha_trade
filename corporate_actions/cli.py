"""CLI pour le module corporate_actions."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from corporate_actions.db_io import CorporateActionRepository
from corporate_actions.engine import CorporateActionEngine
from corporate_actions.provider import AlpacaCorporateActionProvider

LOGGER = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="corporate_actions",
        description="Gestion automatique des corporate actions (dividendes, splits).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- sync ---
    sync_p = sub.add_parser("sync", help="Ingérer les corporate actions depuis le provider.")
    sync_p.add_argument("--symbols", nargs="*", help="Symboles à synchroniser (tous si omis).")
    sync_p.add_argument("--start", type=str, default=None, help="Date début (YYYY-MM-DD). Défaut : -30j.")
    sync_p.add_argument("--end", type=str, default=None, help="Date fin (YYYY-MM-DD). Défaut : aujourd'hui.")

    # --- apply ---
    apply_p = sub.add_parser("apply", help="Appliquer les événements pending sur les positions.")
    apply_p.add_argument("--as-of", type=str, default=None, help="Date limite (YYYY-MM-DD). Défaut : aujourd'hui.")

    # --- status ---
    sub.add_parser("status", help="Afficher un résumé des événements corporate actions.")

    # --- run ---
    run_p = sub.add_parser("run", help="Enchaîner sync puis apply dans un seul appel.")
    run_p.add_argument("--symbols", nargs="*", help="Symboles à synchroniser (tous si omis).")
    run_p.add_argument("--start", type=str, default=None, help="Date début (YYYY-MM-DD). Défaut : -30j.")
    run_p.add_argument("--end", type=str, default=None, help="Date fin (YYYY-MM-DD). Défaut : aujourd'hui.")
    run_p.add_argument("--as-of", type=str, default=None, help="Date limite pour apply (YYYY-MM-DD). Défaut : aujourd'hui.")

    return parser


def _run_sync(args: argparse.Namespace) -> None:
    provider = AlpacaCorporateActionProvider()
    engine = CorporateActionEngine(provider=provider)

    start_date = date.fromisoformat(args.start) if args.start else date.today() - timedelta(days=30)
    end_date = date.fromisoformat(args.end) if args.end else date.today()
    symbols = [s.upper() for s in args.symbols] if args.symbols else []

    stats = engine.sync(symbols=symbols or None, start_date=start_date, end_date=end_date)
    print(f"Sync terminé : {stats}")


def _run_apply(args: argparse.Namespace) -> None:
    provider = AlpacaCorporateActionProvider()
    engine = CorporateActionEngine(provider=provider)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()

    stats = engine.apply(as_of=as_of)
    print(f"Apply terminé : {stats}")


def _run_status(_args: argparse.Namespace) -> None:
    from sqlalchemy import text as sql_text

    repo = CorporateActionRepository()
    with repo.engine.connect() as conn:
        rows = conn.execute(sql_text("""
            SELECT status, ca_type, COUNT(*) as cnt
            FROM corporate_actions_events
            GROUP BY status, ca_type
            ORDER BY status, ca_type
        """)).mappings().all()

    if not rows:
        print("Aucun événement corporate action en base.")
        return

    print(f"{'Status':<12} {'Type':<20} {'Count':>6}")
    print("-" * 40)
    for r in rows:
        print(f"{r['status']:<12} {r['ca_type']:<20} {r['cnt']:>6}")

    total_cash = repo.get_total_dividends()
    print(f"\nTotal dividendes crédités : ${total_cash:,.2f}")


def _run_all(args: argparse.Namespace) -> None:
    """Enchaîne sync puis apply dans un seul appel CLI."""
    print("[RUN] Démarrage de l'ingestion des corporate actions...")
    provider = AlpacaCorporateActionProvider()
    engine = CorporateActionEngine(provider=provider)
    start_date = date.fromisoformat(args.start) if args.start else date.today() - timedelta(days=30)
    end_date = date.fromisoformat(args.end) if args.end else date.today()
    symbols = [s.upper() for s in args.symbols] if getattr(args, "symbols", None) else []
    stats_sync = engine.sync(symbols=symbols or None, start_date=start_date, end_date=end_date)
    print(f"Sync terminé : {stats_sync}")
    print("[RUN] Application des corporate actions sur les positions...")
    as_of = date.fromisoformat(args.as_of) if getattr(args, "as_of", None) else date.today()
    stats_apply = engine.apply(as_of=as_of)
    print(f"Apply terminé : {stats_apply}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s -- %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "sync":
        _run_sync(args)
    elif args.command == "apply":
        _run_apply(args)
    elif args.command == "status":
        _run_status(args)
    elif args.command == "run":
        _run_all(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

