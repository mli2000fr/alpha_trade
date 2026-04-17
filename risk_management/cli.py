"""CLI standalone pour le module risk_management."""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

from risk_management.audit import build_run_id, persist_decisions, persist_portfolio_targets
from risk_management.config import RiskConfig
from risk_management.db_io import RiskRepository
from risk_management.models import PortfolioEntry
from risk_management.portfolio_builder import PortfolioBuilder

LOGGER = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Module de gestion de risque Alpha Trade")
    p.add_argument("--account-equity", type=float, default=100_000.0)
    p.add_argument("--risk-per-trade-pct", type=float, default=0.01)
    p.add_argument("--max-positions", type=int, default=20)
    p.add_argument("--max-position-weight", type=float, default=0.10)
    p.add_argument("--max-sector-weight", type=float, default=0.30)
    p.add_argument("--trade-date", type=str, default=None, help="YYYY-MM-DD (défaut: aujourd'hui)")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def _print_summary(entries: list[PortfolioEntry], run_id: str, trade_date: date) -> None:
    accepted = [e for e in entries if e.approved_shares > 0]
    rejected = [e for e in entries if e.approved_shares == 0]
    total_notional = sum(e.target_notional for e in accepted)
    print(f"\n{'=' * 70}")
    print(f"  Risk Management — run_id={run_id}  trade_date={trade_date}")
    print(f"  Candidats évalués : {len(entries)}")
    print(f"  Positions retenues: {len(accepted)}  |  Rejetées: {len(rejected)}")
    print(f"  Notional total    : ${total_notional:,.2f}")
    print(f"{'=' * 70}")
    for e in accepted:
        print(f"  {e.symbol:<8} {e.decision:<10} shares={e.approved_shares:>6}  "
              f"price={e.entry_price:>8.2f}  weight={e.target_weight:>6.2%}  "
              f"score={e.score_used:.4f} ({e.score_source})")
    if rejected:
        print(f"  --- rejetés ---")
        for e in rejected:
            print(f"  {e.symbol:<8} {e.decision:<10} raison={e.decision_reason}")
    print()


def main() -> None:
    args = build_arg_parser().parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    trade_date = datetime.strptime(args.trade_date, "%Y-%m-%d").date() if args.trade_date else date.today()

    config = RiskConfig(
        account_equity=args.account_equity,
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_positions=args.max_positions,
        max_position_weight=args.max_position_weight,
        max_sector_weight=args.max_sector_weight,
        dry_run=args.dry_run,
    )

    repo = RiskRepository()
    LOGGER.info("Chargement des candidats…")
    candidates = repo.load_candidates(config)
    LOGGER.info("Candidats chargés : %d", len(candidates))

    symbols = [c.symbol for c in candidates]
    LOGGER.info("Chargement des prix et ATR…")
    prices = repo.load_prices(symbols, atr_window=config.atr_window)
    LOGGER.info("Prix chargés pour %d symboles.", len(prices))

    builder = PortfolioBuilder(config)
    entries = builder.build(candidates, prices)

    run_id = build_run_id()
    _print_summary(entries, run_id, trade_date)

    if config.dry_run:
        LOGGER.info("Mode dry-run — aucune écriture en DB.")
    else:
        n_dec = persist_decisions(repo, entries, run_id, trade_date)
        n_tgt = persist_portfolio_targets(repo, entries, run_id, trade_date)
        LOGGER.info("Écrit %d décisions et %d cibles en DB.", n_dec, n_tgt)
