"""CLI standalone pour le module risk_management."""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

from common.utils import setup_logging_with_file_handler
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
    # --- V2 arguments ---
    p.add_argument("--correlation-threshold", type=float, default=0.80)
    p.add_argument("--correlation-lookback-days", type=int, default=60)
    p.add_argument("--correlation-min-overlap", type=int, default=40)
    p.add_argument("--enable-kelly-sizing", action="store_true", default=False)
    p.add_argument("--assumed-payoff-ratio", type=float, default=1.5)
    p.add_argument("--kelly-fraction-multiplier", type=float, default=0.25)
    p.add_argument("--score-weight", type=float, default=0.40)
    p.add_argument("--prediction-weight", type=float, default=0.60)
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
              f"score={e.score_used:.4f} ({e.score_source})  "
              f"conviction={e.conviction_score:.4f}  sizing={e.sizing_method}")
    if rejected:
        print(f"  --- rejetés ---")
        for e in rejected:
            print(f"  {e.symbol:<8} {e.decision:<10} raison={e.decision_reason}")
    print()


def main(args: list[str] | None = None) -> None:
    setup_logging_with_file_handler("risk_management.log")
    args = build_arg_parser().parse_args(args)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    trade_date = datetime.strptime(args.trade_date, "%Y-%m-%d").date() if args.trade_date else date.today()

    config = RiskConfig(
        account_equity=args.account_equity,
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_positions=args.max_positions,
        max_position_weight=args.max_position_weight,
        max_sector_weight=args.max_sector_weight,
        dry_run=args.dry_run,
        correlation_threshold=args.correlation_threshold,
        correlation_lookback_days=args.correlation_lookback_days,
        correlation_min_overlap=args.correlation_min_overlap,
        enable_kelly_sizing=args.enable_kelly_sizing,
        assumed_payoff_ratio=args.assumed_payoff_ratio,
        kelly_fraction_multiplier=args.kelly_fraction_multiplier,
        score_weight=args.score_weight,
        prediction_weight=args.prediction_weight,
    )

    repo = RiskRepository()
    LOGGER.info("Chargement des candidats…")
    candidates = repo.load_candidates(config)
    LOGGER.info("Candidats chargés : %d", len(candidates))

    symbols = [c.symbol for c in candidates]
    LOGGER.info("Chargement des prix et ATR…")
    prices = repo.load_prices(symbols, atr_window=config.atr_window)
    LOGGER.info("Prix chargés pour %d symboles.", len(prices))

    # --- V2 data loading ---
    LOGGER.info("Chargement des prédictions ML…")
    predictions = repo.load_predictions(symbols, trade_date)
    LOGGER.info("Prédictions chargées pour %d symboles.", len(predictions))

    LOGGER.info("Chargement des win rates…")
    win_rates = repo.load_win_rates(symbols)
    LOGGER.info("Win rates chargés pour %d symboles.", len(win_rates))

    LOGGER.info("Chargement de la matrice de rendements…")
    return_matrix = repo.load_return_matrix(symbols, config.correlation_lookback_days)
    LOGGER.info("Matrice de rendements : %s", return_matrix.shape if not return_matrix.empty else "vide")

    builder = PortfolioBuilder(config)
    entries = builder.build(candidates, prices, predictions, win_rates, return_matrix)

    run_id = build_run_id()
    _print_summary(entries, run_id, trade_date)

    if config.dry_run:
        LOGGER.info("Mode dry-run — aucune écriture en DB.")
    else:
        n_dec = persist_decisions(repo, entries, run_id, trade_date)
        n_tgt = persist_portfolio_targets(repo, entries, run_id, trade_date)
        LOGGER.info("Écrit %d décisions et %d cibles en DB.", n_dec, n_tgt)
