"""CLI standalone pour le module risk_management."""
from __future__ import annotations

import argparse
import logging
from collections import Counter
from datetime import date, datetime

from common.utils import configure_root_logging
from core.run_summary import attach_live_progress, attach_schema_version
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from risk_management.audit import build_run_id, persist_decisions, persist_portfolio_targets
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.db_io import RiskRepository
from risk_management.models import PortfolioEntry
from risk_management.portfolio_builder import PortfolioBuilder

LOGGER = logging.getLogger(__name__)


def _emit_live_progress(
    summary: dict[str, object],
    *,
    current: int,
    total: int,
    label: str,
    phase: str,
    item: str | None = None,
    unit: str = "étapes",
) -> None:
    emit_run_summary(
        attach_live_progress(
            summary,
            current=current,
            total=total,
            label=label,
            phase=phase,
            unit=unit,
            item=item,
        )
    )


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Module de gestion de risque Alpha Trade")
    p.add_argument("--account-equity", type=float, default=100_000.0)
    p.add_argument("--risk-per-trade-pct", type=float, default=0.01)
    p.add_argument("--max-positions", type=int, default=20)
    p.add_argument("--max-position-weight", type=float, default=0.10)
    p.add_argument("--max-sector-weight", type=float, default=0.30)
    p.add_argument("--min-position-notional", type=float, default=500.0)
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
    raw_account_id = (args.account or "").strip() or None
    requested_equity = float(args.account_equity)
    # L'IHM transmet systématiquement `--account default`. On considère cette
    # valeur comme un compte implicite : si aucun snapshot n'est disponible, on
    # fallback sur `--account-equity` plutôt que de bloquer le pipeline.
    requested_account_id = None if (raw_account_id is None or raw_account_id.lower() == "default") else raw_account_id

    repo = RiskRepository()
    account_snapshot = repo.load_account_risk_snapshot(requested_account_id, trade_date)
    effective_account_id = account_snapshot.account_id if account_snapshot is not None else requested_account_id
    equity_breakdown = repo.load_account_equity_breakdown(effective_account_id, trade_date)
    if account_snapshot is None:
        # Fallback systématique sur --account-equity quand aucun snapshot broker
        # n'est disponible. Cas typiques :
        #   - premier run de la journée pour un compte (broker_account_snapshots
        #     n'est rempli qu'après l'étape 12 — Execution paper/live).
        #   - switch vers un compte qui n'a jamais exécuté l'étape 12.
        #   - mode simulate (jamais d'écriture broker_account_snapshots).
        # Le sizing utilise --account-equity de l'IHM ; le risque est borné
        # par cette valeur, donc safe même en multi-comptes.
        effective_equity = requested_equity
        pnl_snapshot = PnLSnapshot(
            portfolio_high_watermark=effective_equity,
            portfolio_current_value=effective_equity,
            daily_pnl=0.0,
        )
        LOGGER.warning(
            "Aucun account_risk_snapshot pour account=%s date=%s ; fallback sur --account-equity=%.2f. "
            "Pour utiliser l'equity broker reel, lancez l'etape 12 (Execution paper/live) sur ce compte.",
            raw_account_id or "default",
            trade_date,
            effective_equity,
        )
    else:
        effective_equity = float(account_snapshot.equity)
        if account_snapshot.trade_date < trade_date and requested_equity > 0:
            capped_equity = min(effective_equity, requested_equity)
            if capped_equity < effective_equity:
                LOGGER.warning(
                    "Snapshot equity stale pour account=%s (snapshot=%s, trade_date=%s) ; "
                    "cap conservateur applique: snapshot=%.2f -> requested=%.2f.",
                    account_snapshot.account_id,
                    account_snapshot.trade_date,
                    trade_date,
                    effective_equity,
                    capped_equity,
                )
                effective_equity = capped_equity
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

    progress_total_steps = 8
    progress_context: dict[str, object] = {
        "trade_date": trade_date.isoformat(),
        "dry_run": bool(args.dry_run),
        "effective_equity": round(float(effective_equity), 2),
        "account_id": effective_account_id or raw_account_id or "default",
    }
    _emit_live_progress(
        dict(progress_context),
        current=1,
        total=progress_total_steps,
        label="🛡️ Progression risk management — résolution du compte",
        phase="resolve_account",
    )

    config = RiskConfig(
        account_equity=effective_equity,
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_positions=args.max_positions,
        max_position_weight=args.max_position_weight,
        max_sector_weight=args.max_sector_weight,
        min_position_notional=args.min_position_notional,
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
    _emit_live_progress(
        dict(progress_context, targeted_symbols=len(candidates)),
        current=2,
        total=progress_total_steps,
        label="🛡️ Progression risk management — chargement des candidats",
        phase="load_candidates",
        unit="étapes",
    )

    symbols = [c.symbol for c in candidates]
    LOGGER.info("Chargement des prix et ATR…")
    prices = repo.load_prices_asof(symbols, trade_date, atr_window=config.atr_window)
    LOGGER.info("Prix charges pour %d symboles.", len(prices))
    _emit_live_progress(
        dict(progress_context, targeted_symbols=len(candidates), price_symbols=len(prices)),
        current=3,
        total=progress_total_steps,
        label="🛡️ Progression risk management — chargement prix & ATR",
        phase="load_prices",
    )

    # --- V2 data loading ---
    LOGGER.info("Chargement des predictions ML…")
    predictions = repo.load_predictions_asof(symbols, trade_date)
    LOGGER.info("Predictions chargees pour %d symboles.", len(predictions))
    _emit_live_progress(
        dict(progress_context, targeted_symbols=len(candidates), prediction_symbols=len(predictions)),
        current=4,
        total=progress_total_steps,
        label="🛡️ Progression risk management — chargement des prédictions ML",
        phase="load_predictions",
    )

    LOGGER.info("Chargement des win rates…")
    win_rates = repo.load_win_rates_asof(symbols, trade_date)
    LOGGER.info("Win rates charges pour %d symboles.", len(win_rates))
    _emit_live_progress(
        dict(progress_context, targeted_symbols=len(candidates), win_rate_symbols=len(win_rates)),
        current=5,
        total=progress_total_steps,
        label="🛡️ Progression risk management — chargement des win rates",
        phase="load_win_rates",
    )

    LOGGER.info("Chargement de la matrice de rendements…")
    return_matrix = repo.load_return_matrix_asof(symbols, trade_date, config.correlation_lookback_days)
    LOGGER.info("Matrice de rendements : %s", return_matrix.shape if not return_matrix.empty else "vide")
    _emit_live_progress(
        dict(
            progress_context,
            targeted_symbols=len(candidates),
            return_matrix_rows=int(return_matrix.shape[0]) if not return_matrix.empty else 0,
            return_matrix_columns=int(return_matrix.shape[1]) if not return_matrix.empty else 0,
        ),
        current=6,
        total=progress_total_steps,
        label="🛡️ Progression risk management — chargement de la matrice de rendements",
        phase="load_return_matrix",
    )

    builder = PortfolioBuilder(config, pnl=pnl_snapshot)
    builder.progress_callback = emit_run_summary
    entries = builder.build(candidates, prices, predictions, win_rates, return_matrix)
    _emit_live_progress(
        dict(progress_context, targeted_symbols=len(candidates), built_entries=len(entries)),
        current=7,
        total=progress_total_steps,
        label="🛡️ Progression risk management — portefeuille construit",
        phase="build_portfolio",
    )

    run_id = build_run_id()
    _print_summary(entries, run_id, trade_date)

    if config.dry_run:
        LOGGER.info("Mode dry-run — aucune ecriture en DB.")
    else:
        n_dec = persist_decisions(repo, entries, run_id, trade_date, account_id=effective_account_id)
        n_tgt = persist_portfolio_targets(repo, entries, run_id, trade_date, account_id=effective_account_id)
        LOGGER.info("Ecrit %d decisions et %d cibles en DB.", n_dec, n_tgt)

    _emit_live_progress(
        dict(
            progress_context,
            targeted_symbols=len(entries),
            persisted_decisions=0 if config.dry_run else int(n_dec),
            persisted_targets=0 if config.dry_run else int(n_tgt),
        ),
        current=8,
        total=progress_total_steps,
        label="🛡️ Progression risk management — finalisation",
        phase="persist_results",
    )

    accepted_entries = [entry for entry in entries if entry.approved_shares > 0 and str(entry.decision).upper() == "ACCEPTED"]
    reduced_entries = [entry for entry in entries if entry.approved_shares > 0 and str(entry.decision).upper() == "REDUCED"]
    rejected_entries = [entry for entry in entries if entry.approved_shares == 0]
    retained_entries = [entry for entry in entries if entry.approved_shares > 0]
    total_target_notional = sum(entry.target_notional for entry in retained_entries)
    gross_exposure_pct = (total_target_notional / effective_equity) if effective_equity > 0 else 0.0
    max_target_weight = max((entry.target_weight for entry in retained_entries), default=0.0)
    sector_weights: dict[str, float] = {}
    for entry in retained_entries:
        sector_weights[entry.sector] = sector_weights.get(entry.sector, 0.0) + entry.target_weight
    max_sector_weight_realized = max(sector_weights.values(), default=0.0)
    total_initial_risk_dollars = sum(float(entry.initial_risk_dollars or 0.0) for entry in retained_entries)
    total_risk_budget_dollars = sum(float(entry.risk_budget_dollars or 0.0) for entry in retained_entries)
    atr_available_symbols = sum(1 for entry in entries if entry.atr_20 is not None and entry.atr_20 > 0)
    prediction_available_symbols = sum(1 for entry in entries if entry.predicted_proba is not None)
    atr_coverage_pct = (atr_available_symbols / len(entries)) if entries else 0.0
    prediction_coverage_pct = (prediction_available_symbols / len(entries)) if entries else 0.0
    rejection_reason_counts = dict(Counter(str(entry.decision_reason or "").strip() or "UNKNOWN" for entry in rejected_entries))
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
        "target_positions": len(retained_entries),
        "total_target_shares": int(sum(entry.approved_shares for entry in retained_entries)),
        "total_target_notional": round(total_target_notional, 2),
        "gross_exposure_pct": round(gross_exposure_pct, 4),
        "max_target_weight": round(max_target_weight, 4),
        "max_sector_weight_realized": round(max_sector_weight_realized, 4),
        "total_initial_risk_dollars": round(total_initial_risk_dollars, 2),
        "total_risk_budget_dollars": round(total_risk_budget_dollars, 2),
        "atr_available_symbols": atr_available_symbols,
        "prediction_available_symbols": prediction_available_symbols,
        "atr_coverage_pct": round(atr_coverage_pct, 4),
        "prediction_coverage_pct": round(prediction_coverage_pct, 4),
        "rejection_reason_counts": rejection_reason_counts,
        "dry_run": bool(config.dry_run),
        "effective_equity": round(float(effective_equity), 2),
        "account_equity": round(float(args.account_equity), 2),
        "account_snapshot_trade_date": account_snapshot.trade_date.isoformat() if account_snapshot is not None else None,
        "circuit_breaker_active": CircuitBreaker(config, pnl_snapshot).is_active(),
        # Phase 5.1.a — décomposition equity (cash + positions + dividendes ledger)
        "account_equity_breakdown": equity_breakdown,
        # Phase 5.1.b — pondérations conviction unifiées via core.conviction
        "conviction_weights": {
            "score_weight": float(config.score_weight),
            "prediction_weight": float(config.prediction_weight),
            "source": "core.conviction",
        },
        # Phase 5.1.c — placeholder calibration (cf. backlog Phase 7)
        "conviction_weights_calibration": {
            "source": "default",
            "calibration_run_id": None,
        },
    }
    summary = attach_schema_version(summary, version=1)
    persist_run_business_summary(
        summary=summary,
        step_key="risk_management",
        run_kind="step",
        status="completed",
        summary_run_id=run_id,
        entity_run_id=run_id,
        account_id=effective_account_id,
        trade_date=trade_date,
        started_at=started_at,
        finished_at=finished_at,
    )
    emit_run_summary(summary)


if __name__ == "__main__":
    raise SystemExit(main())

