"""CLI standalone pour le module risk_management."""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

from common.utils import configure_root_logging
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from risk_management.audit import build_run_id, persist_decisions, persist_portfolio_targets
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
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
    p.add_argument("--account", type=str, default=None, help="ID du compte Alpaca multi-comptes")
    return p


def _print_summary(entries: list[PortfolioEntry], run_id: str, trade_date: date) -> None:
    accepted = [e for e in entries if e.approved_shares > 0]
    rejected = [e for e in entries if e.approved_shares == 0]
    total_notional = sum(e.target_notional for e in accepted)
    print(f"\n{'=' * 70}")
    print(f"  Risk Management — run_id={run_id}  trade_date={trade_date}")
    print(f"  Candidats evalues : {len(entries)}")
    print(f"  Positions retenues: {len(accepted)}  |  Rejetees: {len(rejected)}")
    print(f"  Notional total    : ${total_notional:,.2f}")
    print(f"{'=' * 70}")
    for e in accepted:
        print(f"  {e.symbol:<8} {e.decision:<10} shares={e.approved_shares:>6}  "
              f"price={e.entry_price:>8.2f}  weight={e.target_weight:>6.2%}  "
              f"score={e.score_used:.4f} ({e.score_source})  "
              f"conviction={e.conviction_score:.4f}  sizing={e.sizing_method}")
    if rejected:
        print(f"  --- rejetes ---")
        for e in rejected:
            print(f"  {e.symbol:<8} {e.decision:<10} raison={e.decision_reason}")
    print()


def main(args: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(args)
    configure_root_logging(
        level=getattr(logging, args.log_level),
        log_path="./log/risk_management.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )

    started_at = datetime.now()

    trade_date = datetime.strptime(args.trade_date, "%Y-%m-%d").date() if args.trade_date else date.today()

    repo = RiskRepository()
    account_snapshot = repo.load_account_risk_snapshot(args.account, trade_date)
    if account_snapshot is None:
        if args.dry_run:
            effective_equity = float(args.account_equity)
            pnl_snapshot = PnLSnapshot(
                portfolio_high_watermark=effective_equity,
                portfolio_current_value=effective_equity,
                daily_pnl=0.0,
            )
            LOGGER.warning(
                "Aucun account_risk_snapshot pour account=%s date=%s ; fallback dry-run sur --account-equity=%.2f.",
                args.account or "default",
                trade_date,
                effective_equity,
            )
        else:
            raise RuntimeError(
                f"Aucun account_risk_snapshot disponible pour account={args.account or 'default'} au {trade_date}."
            )
    else:
        effective_equity = float(account_snapshot.equity)
        daily_pnl = account_snapshot.daily_total_pnl
        if daily_pnl is None:
            realized = account_snapshot.daily_realized_pnl or 0.0
            unrealized = account_snapshot.daily_unrealized_pnl or 0.0
            daily_pnl = realized + unrealized
        pnl_snapshot = PnLSnapshot(
            portfolio_high_watermark=account_snapshot.high_watermark,
            portfolio_current_value=account_snapshot.equity,
            daily_pnl=daily_pnl,
        )
        LOGGER.info(
            "Account snapshot charge | account=%s snapshot_trade_date=%s equity=%.2f buying_power=%.2f",
            account_snapshot.account_id,
            account_snapshot.trade_date,
            account_snapshot.equity,
            account_snapshot.buying_power,
        )

    config = RiskConfig(
        account_equity=effective_equity,
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

    LOGGER.info("Chargement des candidats…")
    candidates = repo.load_candidates_asof(trade_date)
    LOGGER.info("Candidats charges : %d", len(candidates))

    symbols = [c.symbol for c in candidates]
    LOGGER.info("Chargement des prix et ATR…")
    prices = repo.load_prices_asof(symbols, trade_date, atr_window=config.atr_window)
    LOGGER.info("Prix charges pour %d symboles.", len(prices))

    # --- V2 data loading ---
    LOGGER.info("Chargement des predictions ML…")
    predictions = repo.load_predictions_asof(symbols, trade_date)
    LOGGER.info("Predictions chargees pour %d symboles.", len(predictions))

    LOGGER.info("Chargement des win rates…")
    win_rates = repo.load_win_rates_asof(symbols, trade_date)
    LOGGER.info("Win rates charges pour %d symboles.", len(win_rates))

    LOGGER.info("Chargement de la matrice de rendements…")
    return_matrix = repo.load_return_matrix_asof(symbols, trade_date, config.correlation_lookback_days)
    LOGGER.info("Matrice de rendements : %s", return_matrix.shape if not return_matrix.empty else "vide")

    builder = PortfolioBuilder(config, pnl=pnl_snapshot)
    entries = builder.build(candidates, prices, predictions, win_rates, return_matrix)

    run_id = build_run_id()
    _print_summary(entries, run_id, trade_date)

    if config.dry_run:
        LOGGER.info("Mode dry-run — aucune ecriture en DB.")
    else:
        n_dec = persist_decisions(repo, entries, run_id, trade_date, account_id=args.account)
        n_tgt = persist_portfolio_targets(repo, entries, run_id, trade_date, account_id=args.account)
        LOGGER.info("Ecrit %d decisions et %d cibles en DB.", n_dec, n_tgt)

    accepted_entries = [entry for entry in entries if entry.approved_shares > 0 and str(entry.decision).upper() == "ACCEPTED"]
    reduced_entries = [entry for entry in entries if entry.approved_shares > 0 and str(entry.decision).upper() == "REDUCED"]
    rejected_entries = [entry for entry in entries if entry.approved_shares == 0]
    finished_at = datetime.now()
    summary = {
        "run_id": run_id,
        "trade_date": trade_date.isoformat(),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "targeted_symbols": len(entries),
        "accepted_symbols": len(accepted_entries),
        "reduced_symbols": len(reduced_entries),
        "rejected_symbols": len(rejected_entries),
        "target_positions": len([entry for entry in entries if entry.approved_shares > 0]),
        "total_target_shares": int(sum(entry.approved_shares for entry in entries if entry.approved_shares > 0)),
        "total_target_notional": round(sum(entry.target_notional for entry in entries if entry.approved_shares > 0), 2),
        "dry_run": bool(config.dry_run),
        "effective_equity": round(float(effective_equity), 2),
        "account_equity": round(float(args.account_equity), 2),
        "account_snapshot_trade_date": account_snapshot.trade_date.isoformat() if account_snapshot is not None else None,
        "circuit_breaker_active": CircuitBreaker(config, pnl_snapshot).is_active(),
    }
    persist_run_business_summary(
        summary=summary,
        step_key="risk_management",
        run_kind="step",
        status="completed",
        summary_run_id=run_id,
        entity_run_id=run_id,
        account_id=args.account,
        trade_date=trade_date,
        started_at=started_at,
        finished_at=finished_at,
    )
    emit_run_summary(summary)


if __name__ == "__main__":
    raise SystemExit(main())

