"""service.market CLI — python -m service.market populate-macro ..."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from typing import Any

from common.config_loader import load_config
from common.logging_setup import configure_root_logging
from service.market import populate_macro_indicators_table, recompute_macro_regime_table

LOGGER = logging.getLogger("service.market.cli")


def _default_progress_callback(step: dict[str, Any]) -> None:
    """Affiche l'avancement session par session."""
    current = int(step.get("current", 0))
    total = int(step.get("total", 0))
    trade_date = str(step.get("trade_date", "?"))
    mode = str(step.get("mode", "?"))
    persisted = bool(step.get("persisted", False))
    error = step.get("error")
    if error:
        LOGGER.warning("[%s/%s] %s ⚠️ %s", current, total, trade_date, error)
    else:
        status = "✅" if persisted else "⏭️"
        LOGGER.info("[%s/%s] %s mode=%-20s %s", current, total, trade_date, mode, status)


def _cmd_populate_macro(args: argparse.Namespace) -> None:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    cfg = load_config() or {}
    LOGGER.info("Début populate-macro : %s → %s", start, end)
    callback = _default_progress_callback if args.progress else None
    result = populate_macro_indicators_table(
        start_date=start, end_date=end, yaml_cfg=cfg, progress_callback=callback,
    )
    error = result.get("error")
    if error:
        LOGGER.error("❌ %s", error)
        sys.exit(1)
    LOGGER.info(
        "✅ Terminé — Sessions: %s | Persistées: %s | Sans donnée: %s",
        result.get("sessions_total", 0),
        result.get("persisted_rows", 0),
        result.get("missing_rows", 0),
    )


def _cmd_recompute_regime(args: argparse.Namespace) -> None:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    equity = float(args.equity) if args.equity else None
    cfg = load_config() or {}
    LOGGER.info("Début recompute-regime : %s → %s (equity=%s)", start, end, equity)
    callback = _default_progress_callback if args.progress else None
    result = recompute_macro_regime_table(
        start_date=start, end_date=end, yaml_cfg=cfg, equity=equity, progress_callback=callback,
    )
    error = result.get("error")
    if error:
        LOGGER.error("❌ %s", error)
        sys.exit(1)
    LOGGER.info(
        "✅ Terminé — Sessions: %s | Recalculées: %s | Absentes: %s",
        result.get("sessions_total", 0),
        result.get("persisted_rows", 0),
        result.get("missing_rows", 0),
    )


def main() -> None:
    configure_root_logging()
    parser = argparse.ArgumentParser(prog="python -m service.market")
    sub = parser.add_subparsers(dest="command")

    populate_p = sub.add_parser("populate-macro", help="Alimenter stock_macro_indicators_daily")
    populate_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    populate_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    populate_p.add_argument("--progress", action="store_true", help="Afficher l'avancement session par session")

    recompute_p = sub.add_parser("recompute-regime", help="Recalculer les colonnes dérivées de régime")
    recompute_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    recompute_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    recompute_p.add_argument("--equity", type=float, default=None, help="Equity simulée ($)")
    recompute_p.add_argument("--progress", action="store_true", help="Afficher l'avancement session par session")

    args = parser.parse_args()
    if args.command == "populate-macro":
        _cmd_populate_macro(args)
    elif args.command == "recompute-regime":
        _cmd_recompute_regime(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
