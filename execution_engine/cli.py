"""CLI du module execution_engine.

Phase 5.2.c — sous-commandes :

* ``run`` (défaut implicite — compat IHM) : exécute un run d'exécution.
* ``cancel-all`` : kill switch global, annule tous les ordres open d'un compte.
"""
from __future__ import annotations

import argparse
import json
import logging
import uuid
from datetime import date, datetime
from typing import cast

from common.utils import configure_root_logging
from core.feature_flags import FeatureFlags
from core.run_summary import attach_schema_version
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from execution_engine.audit import build_execution_run_summary
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig, load_trailing_stop_config_from_yaml
from execution_engine.db_io import ExecutionRepository
from execution_engine.executor import ProductionExecutor
from execution_engine.models import EventType
from execution_engine.oco_manager import OcoManager
from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _add_run_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--trade-date", "--date", dest="trade_date", type=str, default=None)
    p.add_argument("--risk-run-id", "--run-id", dest="risk_run_id", type=str, default=None)
    p.add_argument("--broker-mode", type=str, default="paper", choices=["paper", "live"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--entry-order-type", type=str, default="market", choices=["market", "limit"])
    p.add_argument("--limit-price-buffer-bps", type=int, default=10)
    p.add_argument("--profit-taker-pct", type=float, default=0.08)
    p.add_argument("--trailing-stop-pct", type=float, default=0.05)
    p.add_argument("--trailing-activation-trigger", type=str, default="multiple_r", choices=["multiple_r", "profit_pct"])
    p.add_argument("--trailing-activation-r-multiple", type=float, default=1.0)
    p.add_argument("--trailing-activation-profit-pct", type=float, default=0.03)
    p.add_argument("--protection-transition-timeout-seconds", type=int, default=30)
    p.add_argument("--protection-transition-poll-interval-seconds", type=float, default=2.0)
    p.add_argument("--max-order-retries", type=int, default=3)
    p.add_argument("--poll-interval-seconds", type=float, default=2.0)
    p.add_argument("--fill-timeout-seconds", type=int, default=120)
    p.add_argument("--cancel-timeout-seconds", type=int, default=30)
    p.add_argument("--allow-outside-rth", action="store_true")
    p.add_argument("--max-slippage-bps", type=int, default=30)
    p.add_argument("--execution-batch-size", type=int, default=20)
    p.add_argument("--inter-order-delay-ms", type=int, default=350)
    p.add_argument("--account-type", type=str, default="cash", choices=["margin", "cash"])
    p.add_argument("--pdt-rule", type=str, default="off", choices=["auto", "off"])
    p.add_argument("--swing-only", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--account", type=str, default=None, help="Account ID multi-comptes (défaut: premier compte)")
    p.add_argument("--skip-preflight", action="store_true", default=False)
    p.add_argument(
        "--disable-sentiment",
        action="store_true",
        help="Désactive la fusion sentiment (ALPHA_TRADE_DISABLE_SENTIMENT=1).",
    )
    p.add_argument(
        "--disable-ml",
        action="store_true",
        help="Désactive la consommation des prédictions ML (ALPHA_TRADE_DISABLE_ML=1).",
    )
    p.add_argument("--log-level", type=str, default="INFO")


def _add_cancel_all_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--account", type=str, required=True, help="ID du compte broker dont on annule les ordres open")
    p.add_argument("--broker-mode", type=str, default="paper", choices=["paper", "live"])
    p.add_argument("--dry-run", action="store_true", default=False, help="Liste les ordres sans appeler cancel_order")
    p.add_argument(
        "--reason",
        type=str,
        default="manual kill switch",
        help="Raison consignée dans execution_kill_switch_runs.reason",
    )
    p.add_argument(
        "--confirm-account",
        type=str,
        default=None,
        help="Obligatoire en --broker-mode live : doit valoir exactement --account",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Outrepasse le verrou execution_locks (dangereux : un run d'exécution peut être en cours)",
    )
    p.add_argument("--log-level", type=str, default="INFO")


def build_arg_parser() -> argparse.ArgumentParser:
    """Phase 5.2.c — argparse avec sous-commandes ; default = ``run`` pour la compat IHM."""
    parser = argparse.ArgumentParser(description="Alpha Trade — Production Executor")
    sub = parser.add_subparsers(dest="command", required=False)

    p_run = sub.add_parser("run", help="Exécute un run d'exécution (défaut implicite)")
    _add_run_arguments(p_run)

    p_cancel = sub.add_parser("cancel-all", help="Phase 5.2.c — kill switch global : annule tous les ordres open du compte")
    _add_cancel_all_arguments(p_cancel)

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Phase 5.2.c — préserve la compat IHM (``python -m execution_engine --broker-mode paper …``).

    Si aucun sous-commande n'est fournie, on injecte ``run`` au début pour
    router vers le legacy executor.
    """
    parser = build_arg_parser()
    raw_argv = list(argv) if argv is not None else None

    # Détection du subcommand : si premier non-flag absent ou inconnu, fallback "run".
    known_subcommands = {"run", "cancel-all"}
    effective_argv = raw_argv
    if raw_argv is not None:
        first_positional = next((a for a in raw_argv if not a.startswith("-")), None)
        if first_positional not in known_subcommands:
            effective_argv = ["run", *raw_argv]
    else:
        import sys
        sys_args = sys.argv[1:]
        first_positional = next((a for a in sys_args if not a.startswith("-")), None)
        if first_positional not in known_subcommands:
            effective_argv = ["run", *sys_args]

    return parser.parse_args(effective_argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _apply_feature_flags(args)
    configure_root_logging(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        log_path="./log/execution_engine.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    if args.command == "cancel-all":
        _run_cancel_all(args)
        return

    _run_execution(args)


# ---------------------------------------------------------------------------
# Sous-commande : run (legacy)
# ---------------------------------------------------------------------------


def _apply_feature_flags(args: argparse.Namespace) -> None:
    flags = FeatureFlags(
        disable_sentiment=bool(getattr(args, "disable_sentiment", False)),
        disable_ml=bool(getattr(args, "disable_ml", False)),
    )
    flags.export_env()
    if flags.disable_sentiment or flags.disable_ml:
        LOGGER.warning(
            "[feature_flags] disable_sentiment=%s disable_ml=%s",
            flags.disable_sentiment,
            flags.disable_ml,
        )


def _resolve_execution_mode(config: ExecutionConfig) -> str:
    if config.dry_run:
        return "simulate"
    return str(config.broker_mode)


def _run_live_preflight(args: argparse.Namespace) -> None:
    if str(args.broker_mode) != "live" or bool(args.dry_run):
        return
    if bool(getattr(args, "skip_preflight", False)):
        LOGGER.warning("[execution.cli] --skip-preflight actif : checks live contournés.")
        return

    from execution_engine.preflight import run_preflight

    account_id = str(getattr(args, "account", "") or "").strip() or "default"
    report = run_preflight(account_id=account_id, broker_mode="live")
    if report.passed:
        return

    for check in getattr(report, "checks", ()):
        if getattr(check, "status", "") == "fail":
            LOGGER.error("[execution.cli] preflight fail | %s: %s", check.name, check.message)
    raise SystemExit(2)


def _run_execution(args: argparse.Namespace) -> None:
    trade_date_val: date | None = None
    if args.trade_date:
        try:
            trade_date_val = date.fromisoformat(args.trade_date)
        except ValueError as exc:
            raise SystemExit(f"Format de date invalide: {args.trade_date!r}. Utilise YYYY-MM-DD.") from exc

    _run_live_preflight(args)

    config = ExecutionConfig(
        broker_mode=args.broker_mode,
        dry_run=args.dry_run,
        entry_order_type=args.entry_order_type,
        limit_price_buffer_bps=args.limit_price_buffer_bps,
        profit_taker_pct=args.profit_taker_pct,
        trailing_stop_pct=args.trailing_stop_pct,
        trailing_activation_trigger=args.trailing_activation_trigger,
        trailing_activation_r_multiple=args.trailing_activation_r_multiple,
        trailing_activation_profit_pct=args.trailing_activation_profit_pct,
        protection_transition_timeout_seconds=args.protection_transition_timeout_seconds,
        protection_transition_poll_interval_seconds=args.protection_transition_poll_interval_seconds,
        max_order_retries=args.max_order_retries,
        poll_interval_seconds=args.poll_interval_seconds,
        fill_timeout_seconds=args.fill_timeout_seconds,
        cancel_timeout_seconds=args.cancel_timeout_seconds,
        allow_outside_rth=args.allow_outside_rth,
        max_slippage_bps=args.max_slippage_bps,
        execution_batch_size=args.execution_batch_size,
        inter_order_delay_ms=args.inter_order_delay_ms,
        account_type=args.account_type,
        pdt_rule=args.pdt_rule,
        swing_only=args.swing_only,
        account_id=args.account,
        trailing_stop=load_trailing_stop_config_from_yaml(),
    )
    resolved_account_id = config.resolved_account_id

    repo = ExecutionRepository()
    client = AlpacaTradingClient(broker_mode=config.broker_mode, account_id=resolved_account_id)
    broker = BrokerAdapter(client, config)
    oco = OcoManager(broker, repo)

    from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
    from risk_management.config import RiskConfig

    equity = 100_000.0
    if not config.dry_run:
        equity = broker.get_account_equity()
        if equity is None or equity <= 0:
            raise RuntimeError(f"Equity broker invalide en mode {config.broker_mode}: {equity!r}")
    pnl = PnLSnapshot(portfolio_current_value=equity, portfolio_high_watermark=equity)
    circuit_breaker = CircuitBreaker(RiskConfig(account_equity=max(float(equity), 1.0)), pnl)
    executor = ProductionExecutor(
        config,
        repo,
        broker,
        oco,
        circuit_breaker=circuit_breaker,
        progress_callback=lambda summary: emit_run_summary(summary),
    )

    started_at = datetime.now()
    metrics = executor.execute_run(risk_run_id=args.risk_run_id, trade_date=trade_date_val)
    finished_at = datetime.now()
    summary = build_execution_run_summary(
        metrics,
        started_at=started_at,
        finished_at=finished_at,
        execution_mode=_resolve_execution_mode(config),
        broker_mode=config.broker_mode,
        account_id=resolved_account_id,
        account_type=config.account_type,
        effective_pdt_rule=config.effective_pdt_rule,
        swing_only=config.swing_only,
        dry_run=config.dry_run,
        allow_outside_rth=config.allow_outside_rth,
    )
    summary = attach_schema_version(summary, version=1)
    try:
        persist_run_business_summary(
            summary=summary,
            step_key="execution",
            run_kind="step",
            status=str(summary.get("status", "") or "") or None,
            summary_run_id=str(summary.get("run_id", "") or "") or None,
            entity_run_id=str(summary.get("run_id", "") or "") or None,
            parent_summary_run_id=args.risk_run_id,
            account_id=resolved_account_id,
            trade_date=cast(object, summary.get("trade_date")),
            started_at=cast(object, summary.get("started_at")),
            finished_at=cast(object, summary.get("finished_at")),
        )
    except Exception:
        LOGGER.debug("Persistance run_business_summaries indisponible pour execution cli.", exc_info=True)
    emit_run_summary(summary)
    LOGGER.info("Execution metrics: %s", metrics)


# ---------------------------------------------------------------------------
# Phase 5.2.c — Sous-commande : cancel-all (kill switch global)
# ---------------------------------------------------------------------------


def _run_cancel_all(args: argparse.Namespace) -> None:
    """Phase 5.2.c — Kill switch global.

    Annule tous les ordres open du compte ``--account``. En ``--broker-mode live``,
    exige ``--confirm-account`` strictement égal à ``--account``.
    """
    account_id = str(args.account)
    broker_mode = str(args.broker_mode)
    reason = str(args.reason or "manual kill switch")
    dry_run = bool(args.dry_run)

    if broker_mode == "live" and args.confirm_account != account_id:
        raise SystemExit(
            f"[cancel-all] --broker-mode live exige --confirm-account == --account "
            f"(reçu: confirm-account={args.confirm_account!r}, account={account_id!r})."
        )

    started_at = datetime.now()
    run_id = f"kill-switch-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    LOGGER.warning(
        "[cancel-all] starting kill switch run_id=%s account=%s broker_mode=%s dry_run=%s reason=%r",
        run_id, account_id, broker_mode, dry_run, reason,
    )

    repo = ExecutionRepository()
    config = ExecutionConfig(broker_mode=broker_mode, account_id=account_id)
    client = AlpacaTradingClient(broker_mode=broker_mode, account_id=account_id)
    broker = BrokerAdapter(client, config)

    results = broker.cancel_all_open_orders(dry_run=dry_run)
    finished_at = datetime.now()

    results_payload = [
        {
            "broker_order_id": r.broker_order_id,
            "symbol": r.symbol,
            "canceled": bool(r.canceled),
            "error": r.error,
        }
        for r in results
    ]
    canceled_count = sum(1 for r in results if r.canceled)
    failed_count = len(results) - canceled_count

    repo.persist_kill_switch_run(
        run_id=run_id,
        account_id=account_id,
        broker_mode=broker_mode,
        reason=reason,
        results=results_payload,
        dry_run=dry_run,
        started_at=started_at,
        finished_at=finished_at,
    )

    summary: dict = {
        "run_id": run_id,
        "command": "cancel-all",
        "account_id": account_id,
        "broker_mode": broker_mode,
        "reason": reason,
        "dry_run": dry_run,
        "total_open": len(results),
        "canceled": canceled_count,
        "failed": failed_count,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "event_type": EventType.KILL_SWITCH_TRIGGERED,
        "results": results_payload,
    }
    summary = attach_schema_version(summary, version=1)

    print(f"\n{'=' * 70}")
    print(f"  Execution Engine — KILL SWITCH ({broker_mode})")
    print(f"  account={account_id}  dry_run={dry_run}  reason={reason!r}")
    print(f"  total_open={len(results)}  canceled={canceled_count}  failed={failed_count}")
    print(f"{'=' * 70}")

    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
