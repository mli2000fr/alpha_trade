"""CLI pour le module corporate_actions."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta

from common.utils import configure_root_logging
from corporate_actions.db_io import CorporateActionRepository
from corporate_actions.engine import CorporateActionEngine
from corporate_actions.provider import AlpacaCorporateActionProvider
from database.run_business_summaries import build_summary_run_id, emit_run_summary, persist_run_business_summary

LOGGER = logging.getLogger(__name__)


def _emit_and_persist_summary(
    *,
    summary: dict[str, object],
    step_key: str,
    status: str,
    account_id: str | None,
    trade_date: object = None,
    parent_summary_run_id: str | None = None,
) -> None:
    try:
        persist_run_business_summary(
            summary=summary,
            step_key=step_key,
            run_kind="step",
            status=status,
            summary_run_id=str(summary.get("run_id", "") or "") or None,
            entity_run_id=str(summary.get("run_id", "") or "") or None,
            parent_summary_run_id=parent_summary_run_id,
            account_id=account_id,
            trade_date=trade_date,
            started_at=summary.get("started_at"),
            finished_at=summary.get("finished_at"),
        )
    except Exception:
        LOGGER.debug("Persistance run_business_summaries indisponible pour corporate_actions.", exc_info=True)
    emit_run_summary(summary)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="corporate_actions",
        description="Gestion automatique des corporate actions (dividendes, splits).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- sync ---
    sync_p = sub.add_parser("sync", help="Ingérer les corporate actions depuis le provider.")
    sync_p.add_argument("--symbols", nargs="*", help="Symboles à synchroniser (tous si omis).")
    sync_p.add_argument("--all-symbols", action="store_true", help="Ne pas filtrer par positions broker et interroger Alpaca sans paramètre symbols.")
    sync_p.add_argument(
        "--portfolio-only",
        dest="portfolio_only",
        action="store_true",
        help="Restreindre la sync aux symboles actuellement détenus en portefeuille (broker_positions_snapshots). Recommandé en usage quotidien.",
    )
    sync_p.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        help="Ignorer les symboles déjà présents dans corporate_actions_events avant l'appel provider.",
    )
    sync_p.add_argument("--batch-size", type=int, default=25, help="Taille des lots de symboles par appel provider. Défaut : 25.")
    sync_p.add_argument("--start", type=str, default=None, help="Date début (YYYY-MM-DD). Défaut : -10 ans.")
    sync_p.add_argument("--end", type=str, default=None, help="Date fin (YYYY-MM-DD). Défaut : aujourd'hui.")
    sync_p.add_argument("--account", type=str, default=None, help="ID du compte Alpaca multi-comptes.")

    # --- apply ---
    apply_p = sub.add_parser("apply", help="Appliquer les événements pending sur les positions.")
    apply_p.add_argument("--as-of", type=str, default=None, help="Date limite (YYYY-MM-DD). Défaut : aujourd'hui.")
    apply_p.add_argument("--account", type=str, default=None, help="ID du compte Alpaca multi-comptes.")

    # --- status ---
    sub.add_parser("status", help="Afficher un résumé des événements corporate actions.")

    # --- run ---
    run_p = sub.add_parser("run", help="Enchaîner sync puis apply dans un seul appel.")
    run_p.add_argument("--symbols", nargs="*", help="Symboles à synchroniser (tous si omis).")
    run_p.add_argument("--all-symbols", action="store_true", help="Ne pas filtrer par positions broker et interroger Alpaca sans paramètre symbols.")
    run_p.add_argument(
        "--portfolio-only",
        dest="portfolio_only",
        action="store_true",
        help="Restreindre la sync aux symboles actuellement détenus en portefeuille (broker_positions_snapshots). Recommandé en usage quotidien.",
    )
    run_p.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        help="Ignorer les symboles déjà présents dans corporate_actions_events avant l'appel provider.",
    )
    run_p.add_argument("--batch-size", type=int, default=25, help="Taille des lots de symboles par appel provider. Défaut : 25.")
    run_p.add_argument("--start", type=str, default=None, help="Date début (YYYY-MM-DD). Défaut : -10 ans.")
    run_p.add_argument("--end", type=str, default=None, help="Date fin (YYYY-MM-DD). Défaut : aujourd'hui.")
    run_p.add_argument("--as-of", type=str, default=None, help="Date limite pour apply (YYYY-MM-DD). Défaut : aujourd'hui.")
    run_p.add_argument("--account", type=str, default=None, help="ID du compte Alpaca multi-comptes.")

    return parser


def _resolve_sync_symbols_portfolio(repo: CorporateActionRepository, account_id: str | None = None) -> list[str]:
    """Résout le périmètre de sync : positions live Alpaca + ordres BUY pending + snapshot DB (fallback)."""
    all_symbols: set[str] = set()

    # 1. Positions live sur le compte Alpaca (source de vérité)
    live_symbols = repo.load_broker_live_position_symbols(account_id=account_id)
    if live_symbols:
        LOGGER.info("Portfolio-only : positions live Alpaca | count=%d", len(live_symbols))
        all_symbols.update(live_symbols)

    # 2. Ordres BUY en attente (accepted/new → deviendront des positions à l'ouverture)
    buy_symbols = repo.load_pending_buy_order_symbols(account_id=account_id)
    if buy_symbols:
        LOGGER.info("Portfolio-only : ordres BUY pending Alpaca | count=%d", len(buy_symbols))
        all_symbols.update(buy_symbols)

    # 3. Fallback : snapshot DB (broker_positions_snapshots) si aucune donnée live
    if not all_symbols:
        broker_symbols = repo.load_latest_position_symbols()
        if broker_symbols:
            LOGGER.info("Portfolio-only : fallback snapshot DB | count=%d", len(broker_symbols))
            all_symbols.update(broker_symbols)

    if all_symbols:
        result = sorted(all_symbols)
        LOGGER.info(
            "Corporate actions sync scope = portfolio-only | count=%d symbols=%s",
            len(result), result,
        )
        return result

    LOGGER.warning(
        "Portfolio-only demande mais aucune position broker (live ni snapshot) ni ordre BUY pending. "
        "Verifier que run_execution a tourne au moins une fois. Sync ignoree.",
    )
    return []


def _resolve_sync_symbols(args: argparse.Namespace, repo: CorporateActionRepository, account_id: str | None = None) -> list[str] | None:
    """Résout le périmètre de sync: symboles explicites, positions broker, ou all-symbols."""
    if getattr(args, "all_symbols", False):
        LOGGER.info("Corporate actions sync scope = all symbols (pas de filtre symbols).")
        return None

    explicit_symbols = [s.upper() for s in args.symbols] if getattr(args, "symbols", None) else []
    if explicit_symbols:
        LOGGER.info("Corporate actions sync scope = explicit symbols | count=%d", len(explicit_symbols))
        return explicit_symbols

    all_symbols: set[str] = set()

    # Positions live Alpaca
    live_symbols = repo.load_broker_live_position_symbols(account_id=account_id)
    all_symbols.update(live_symbols)

    # Ordres BUY pending Alpaca
    buy_symbols = repo.load_pending_buy_order_symbols(account_id=account_id)
    all_symbols.update(buy_symbols)

    # Snapshot DB (fallback / complément)
    broker_symbols = repo.load_latest_position_symbols()
    all_symbols.update(broker_symbols)

    if all_symbols:
        result = sorted(all_symbols)
        LOGGER.info(
            "Corporate actions sync scope = live positions + pending BUY + snapshot DB | count=%d symbols=%s",
            len(result), result,
        )
        return result

    LOGGER.warning(
        "Aucun symbole explicite ni position/ordre broker disponible ; aucune sync Alpaca lancee. "
        "Utiliser --all-symbols pour un backfill large ou --symbols pour cibler manuellement.",
    )
    return []


def _resolve_sync_symbols_bar(args: argparse.Namespace, repo: CorporateActionRepository, account_id: str | None = None) -> list[str] | None:
    """Résout le périmètre de sync depuis stock_metadata (univers actif/tradable/bars dispo)."""
    if getattr(args, "all_symbols", False):
        LOGGER.info("Corporate actions sync scope = all symbols (pas de filtre symbols).")
        return None

    explicit_symbols = [s.upper() for s in args.symbols] if getattr(args, "symbols", None) else []
    if explicit_symbols:
        LOGGER.info("Corporate actions sync scope = explicit symbols | count=%d", len(explicit_symbols))
        return explicit_symbols

    metadata_symbols = repo.load_bars_available_symbols()

    # Toujours enrichir avec positions live et ordres BUY pending
    all_symbols: set[str] = set(metadata_symbols) if metadata_symbols else set()

    live_symbols = repo.load_broker_live_position_symbols(account_id=account_id)
    all_symbols.update(live_symbols)

    buy_symbols = repo.load_pending_buy_order_symbols(account_id=account_id)
    all_symbols.update(buy_symbols)

    if not all_symbols:
        broker_symbols = repo.load_latest_position_symbols()
        all_symbols.update(broker_symbols)

    if all_symbols:
        result = sorted(all_symbols)
        LOGGER.info(
            "Corporate actions sync scope = metadata + live positions + pending BUY | count=%d",
            len(result),
        )
        return result

    LOGGER.warning(
        "Aucun symbole explicite, aucun symbole stock_metadata eligible, aucune position/ordre broker ; aucune sync Alpaca lancee. "
        "Utiliser --all-symbols pour un backfill large ou --symbols pour cibler manuellement.",
    )
    return []


def _run_sync(args: argparse.Namespace) -> None:
    account_id = getattr(args, "account", None)
    provider = AlpacaCorporateActionProvider(account_id=account_id)
    repo = CorporateActionRepository()
    engine = CorporateActionEngine(provider=provider, repo=repo, account_id=account_id)
    started_at = datetime.now()

    start_date = date.fromisoformat(args.start) if args.start else date.today() - timedelta(days=3650)
    end_date = date.fromisoformat(args.end) if args.end else date.today()

    if getattr(args, "portfolio_only", False):
        symbols: list[str] | None = _resolve_sync_symbols_portfolio(repo, account_id=account_id)
    else:
        symbols = _resolve_sync_symbols_bar(args, repo, account_id=account_id)

    stats = engine.sync(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        batch_size=args.batch_size,
        skip_existing=getattr(args, "skip_existing", False),
    )
    finished_at = datetime.now()
    summary = {
        "run_id": build_summary_run_id("ca-sync"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "targeted_symbols": len(symbols or []),
        "all_symbols_scope": symbols is None,
        "fetched_events": int(stats.get("fetched", 0)),
        "inserted_events": int(stats.get("inserted", 0)),
        "duplicate_events": int(stats.get("duplicates", 0)),
        "invalid_events": int(stats.get("invalid", 0)),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "batch_size": int(args.batch_size),
    }
    _emit_and_persist_summary(
        summary=summary,
        step_key="corporate_actions_sync",
        status="completed",
        account_id=account_id,
        trade_date=end_date,
    )
    print(f"Sync termine : {stats}")


def _run_apply(args: argparse.Namespace) -> None:
    account_id = getattr(args, "account", None)
    provider = AlpacaCorporateActionProvider(account_id=account_id)
    engine = CorporateActionEngine(provider=provider, account_id=account_id)
    started_at = datetime.now()

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    pending_loader = getattr(getattr(engine, "repo", None), "load_pending_events", None)
    pending_events = pending_loader(as_of=as_of) if callable(pending_loader) else []
    dividend_events = sum(1 for event in pending_events if "dividend" in str(getattr(event, "ca_type", "")).lower())
    split_events = sum(1 for event in pending_events if "split" in str(getattr(event, "ca_type", "")).lower())

    stats = engine.apply(as_of=as_of)
    finished_at = datetime.now()
    summary = {
        "run_id": build_summary_run_id("ca-apply"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "pending_events": len(pending_events),
        "applied_events": int(stats.get("applied", 0)),
        "skipped_events": int(stats.get("skipped", 0)),
        "failed_events": int(stats.get("failed", 0)),
        "dividend_credits": dividend_events,
        "split_applications": split_events,
        "trade_date": as_of.isoformat(),
    }
    _emit_and_persist_summary(
        summary=summary,
        step_key="corporate_actions_apply",
        status="completed",
        account_id=account_id,
        trade_date=as_of,
    )
    print(f"Apply termine : {stats}")


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
        print("Aucun evenement corporate action en base.")
        return

    print(f"{'Status':<12} {'Type':<20} {'Count':>6}")
    print("-" * 40)
    for r in rows:
        print(f"{r['status']:<12} {r['ca_type']:<20} {r['cnt']:>6}")

    total_cash = repo.get_total_dividends()
    print(f"\nTotal dividendes credits : ${total_cash:,.2f}")


def _run_all(args: argparse.Namespace) -> None:
    """Enchaîne sync puis apply dans un seul appel CLI."""
    print("[RUN] Demarrage de l'ingestion des corporate actions...")
    account_id = getattr(args, "account", None)
    started_at = datetime.now()
    parent_summary_run_id = build_summary_run_id("ca-run")
    provider = AlpacaCorporateActionProvider(account_id=account_id)
    repo = CorporateActionRepository()
    engine = CorporateActionEngine(provider=provider, repo=repo, account_id=account_id)
    start_date = date.fromisoformat(args.start) if args.start else date.today() - timedelta(days=3650)
    end_date = date.fromisoformat(args.end) if args.end else date.today()

    if getattr(args, "portfolio_only", False):
        symbols: list[str] | None = _resolve_sync_symbols_portfolio(repo, account_id=account_id)
    else:
        symbols = _resolve_sync_symbols_bar(args, repo, account_id=account_id)

    stats_sync = engine.sync(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        batch_size=args.batch_size,
        skip_existing=getattr(args, "skip_existing", False),
    )
    sync_summary = {
        "run_id": f"{parent_summary_run_id}-sync",
        "targeted_symbols": len(symbols or []),
        "all_symbols_scope": symbols is None,
        "fetched_events": int(stats_sync.get("fetched", 0)),
        "inserted_events": int(stats_sync.get("inserted", 0)),
        "duplicate_events": int(stats_sync.get("duplicates", 0)),
        "invalid_events": int(stats_sync.get("invalid", 0)),
    }
    _emit_and_persist_summary(
        summary={
            **sync_summary,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "duration_seconds": round((datetime.now() - started_at).total_seconds(), 2),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "batch_size": int(args.batch_size),
        },
        step_key="corporate_actions_sync",
        status="completed",
        account_id=account_id,
        trade_date=end_date,
        parent_summary_run_id=parent_summary_run_id,
    )
    print(f"Sync termine : {stats_sync}")
    print("[RUN] Application des corporate actions sur les positions...")
    as_of = date.fromisoformat(args.as_of) if getattr(args, "as_of", None) else date.today()
    pending_loader = getattr(getattr(engine, "repo", None), "load_pending_events", None)
    pending_events = pending_loader(as_of=as_of) if callable(pending_loader) else []
    dividend_events = sum(1 for event in pending_events if "dividend" in str(getattr(event, "ca_type", "")).lower())
    split_events = sum(1 for event in pending_events if "split" in str(getattr(event, "ca_type", "")).lower())
    stats_apply = engine.apply(as_of=as_of)
    apply_finished_at = datetime.now()
    apply_summary = {
        "run_id": f"{parent_summary_run_id}-apply",
        "pending_events": len(pending_events),
        "applied_events": int(stats_apply.get("applied", 0)),
        "skipped_events": int(stats_apply.get("skipped", 0)),
        "failed_events": int(stats_apply.get("failed", 0)),
        "dividend_credits": dividend_events,
        "split_applications": split_events,
        "trade_date": as_of.isoformat(),
    }
    _emit_and_persist_summary(
        summary={
            **apply_summary,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": apply_finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((apply_finished_at - started_at).total_seconds(), 2),
        },
        step_key="corporate_actions_apply",
        status="completed",
        account_id=account_id,
        trade_date=as_of,
        parent_summary_run_id=parent_summary_run_id,
    )
    parent_summary = {
        "run_id": parent_summary_run_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": apply_finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((apply_finished_at - started_at).total_seconds(), 2),
        "workflow_steps_with_summary": 2,
        "targeted_symbols": int(sync_summary.get("targeted_symbols", 0)),
        "fetched_events": int(sync_summary.get("fetched_events", 0)),
        "inserted_events": int(sync_summary.get("inserted_events", 0)),
        "duplicate_events": int(sync_summary.get("duplicate_events", 0)),
        "invalid_events": int(sync_summary.get("invalid_events", 0)),
        "pending_events": int(apply_summary.get("pending_events", 0)),
        "applied_events": int(apply_summary.get("applied_events", 0)),
        "skipped_events": int(apply_summary.get("skipped_events", 0)),
        "failed_events": int(apply_summary.get("failed_events", 0)),
        "dividend_credits": int(apply_summary.get("dividend_credits", 0)),
        "split_applications": int(apply_summary.get("split_applications", 0)),
    }
    _emit_and_persist_summary(
        summary=parent_summary,
        step_key="corporate_actions_run",
        status="completed",
        account_id=account_id,
        trade_date=as_of,
    )
    print(f"Apply termine : {stats_apply}")


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/corporate_actions.log",
        fmt="%(asctime)s %(levelname)-8s %(name)s -- %(message)s",
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

