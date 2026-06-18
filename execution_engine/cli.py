"""CLI du module execution_engine.

Phase 5.2.c — sous-commandes :

* ``run`` (défaut implicite) : façade de compatibilité qui délègue vers
  ``run_execution.py``.
* ``cancel-all`` : kill switch global, annule tous les ordres open d'un compte.
"""
from __future__ import annotations

import argparse
import json
import logging
import uuid
from datetime import datetime

import run_execution
from common.utils import configure_root_logging
from core.feature_flags import FeatureFlags
from core.run_summary import attach_schema_version
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import EventType
from database.run_business_summaries import persist_run_business_summary
from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
STEP_KEY = "execution_kill_switch"


def _add_run_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--trade-date", "--date", dest="trade_date", type=str, default=None)
    p.add_argument("--risk-run-id", "--run-id", dest="risk_run_id", type=str, default=None)
    p.add_argument("--broker-mode", type=str, default="paper", choices=["paper", "live"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--debug", action="store_true", default=False)
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
    p.add_argument("--auto-rebalance", action="store_true", default=False)
    p.add_argument("--max-slippage-bps", type=int, default=30)
    p.add_argument("--execution-batch-size", type=int, default=20)
    p.add_argument("--inter-order-delay-ms", type=int, default=350)
    p.add_argument("--account-type", type=str, default="cash", choices=["margin", "cash"])
    p.add_argument("--swing-only", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--submission-window", type=str, default=None, choices=["post_close", "pre_open", "both"])
    p.add_argument("--account", type=str, default=None, help="Account ID multi-comptes (défaut: premier compte)")
    p.add_argument("--auto-watcher", action="store_true", default=False)
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
    canonical_modes = {"simulate", "paper", "live"}

    def _rewrite_canonical_mode(invocation: list[str]) -> list[str] | None:
        if not invocation:
            return None
        first = str(invocation[0]).strip().lower()
        if first not in canonical_modes:
            return None
        rewritten = ["run"]
        if first == "simulate":
            rewritten.extend(["--broker-mode", "paper", "--dry-run"])
        else:
            rewritten.extend(["--broker-mode", first])
        rewritten.extend(invocation[1:])
        return rewritten

    # Détection du subcommand : si premier non-flag absent ou inconnu, fallback "run".
    known_subcommands = {"run", "cancel-all"}
    effective_argv = raw_argv
    if raw_argv is not None:
        rewritten = _rewrite_canonical_mode(raw_argv)
        if rewritten is not None:
            effective_argv = rewritten
            return parser.parse_args(effective_argv)
        first_positional = next((a for a in raw_argv if not a.startswith("-")), None)
        if first_positional not in known_subcommands:
            effective_argv = ["run", *raw_argv]
    else:
        import sys
        sys_args = sys.argv[1:]
        rewritten = _rewrite_canonical_mode(sys_args)
        if rewritten is not None:
            effective_argv = rewritten
            return parser.parse_args(effective_argv)
        first_positional = next((a for a in sys_args if not a.startswith("-")), None)
        if first_positional not in known_subcommands:
            effective_argv = ["run", *sys_args]

    return parser.parse_args(effective_argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _apply_feature_flags(args)

    if args.command == "cancel-all":
        configure_root_logging(
            level=getattr(logging, str(args.log_level).upper(), logging.INFO),
            log_path="./log/execution_engine.log",
            fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        )
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


def _resolve_canonical_mode(args: argparse.Namespace) -> str:
    return run_execution.resolve_mode_from_broker_mode(
        broker_mode=str(args.broker_mode),
        dry_run=bool(args.dry_run),
    )


def _run_execution(args: argparse.Namespace) -> None:
    account_id = str(getattr(args, "account", "") or "").strip() or None
    mode = _resolve_canonical_mode(args)
    debug = bool(getattr(args, "debug", False)) or str(getattr(args, "log_level", "INFO")).upper() == "DEBUG"

    LOGGER.info(
        "[execution.cli] délégation du chemin `run` vers run_execution.py | mode=%s account=%s",
        mode,
        account_id or "default",
    )
    run_execution.abort_missing_env(account_id=account_id, mode=mode)
    run_execution.run(
        mode=mode,
        run_id=args.risk_run_id,
        trade_date=args.trade_date,
        debug=debug,
        allow_outside_rth=bool(args.allow_outside_rth),
        auto_rebalance=bool(args.auto_rebalance),
        account_id=account_id,
        account_type=str(args.account_type),
        swing_only=bool(args.swing_only),
        submission_window=str(args.submission_window or "both"),
        auto_watcher=bool(args.auto_watcher),
        skip_preflight=bool(args.skip_preflight),
        take_profit_pct=float(args.profit_taker_pct),
        trailing_stop_pct=float(args.trailing_stop_pct),
        trailing_activation_trigger=str(args.trailing_activation_trigger),
        trailing_activation_r_multiple=float(args.trailing_activation_r_multiple),
        trailing_activation_profit_pct=float(args.trailing_activation_profit_pct),
        protection_transition_timeout_seconds=int(args.protection_transition_timeout_seconds),
        protection_transition_poll_interval_seconds=float(args.protection_transition_poll_interval_seconds),
        entry_order_type=str(args.entry_order_type),
        limit_price_buffer_bps=int(args.limit_price_buffer_bps),
        max_order_retries=int(args.max_order_retries),
        poll_interval_seconds=float(args.poll_interval_seconds),
        fill_timeout_seconds=int(args.fill_timeout_seconds),
        cancel_timeout_seconds=int(args.cancel_timeout_seconds),
        max_slippage_bps=int(args.max_slippage_bps),
        execution_batch_size=int(args.execution_batch_size),
        inter_order_delay_ms=int(args.inter_order_delay_ms),
        force_close_on_breaker=bool(
            __import__("common.config_loader", fromlist=["load_config"]).load_config()
            .get("risk_management", {})
            .get("force_close_on_breaker", False)
        ),
        force_close_pct=float(
            __import__("common.config_loader", fromlist=["load_config"]).load_config()
            .get("risk_management", {})
            .get("force_close_pct", 0.50)
        ),
    )


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
    try:
        persist_run_business_summary(
            summary=summary,
            step_key=STEP_KEY,
            run_kind="step",
            status="completed" if failed_count == 0 else "warning",
            summary_run_id=run_id,
            entity_run_id=run_id,
            account_id=account_id,
            started_at=started_at,
            finished_at=finished_at,
        )
    except Exception:
        LOGGER.debug("Persistance run_summaries indisponible pour cancel-all.", exc_info=True)

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
