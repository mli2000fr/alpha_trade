"""service.market CLI — python -m service.market populate-macro ..."""
from __future__ import annotations

import argparse
import sys
from datetime import date

from common.config_loader import load_config
from service.market import populate_macro_indicators_table, recompute_macro_regime_table


def _cmd_populate_macro(args: argparse.Namespace) -> None:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    cfg = load_config() or {}
    result = populate_macro_indicators_table(start_date=start, end_date=end, yaml_cfg=cfg)
    error = result.get("error")
    if error:
        print(f"❌ {error}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ Sessions: {result.get('sessions_total', 0)} | Persisted: {result.get('persisted_rows', 0)} | Missing: {result.get('missing_rows', 0)}")


def _cmd_recompute_regime(args: argparse.Namespace) -> None:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    equity = float(args.equity) if args.equity else None
    cfg = load_config() or {}
    result = recompute_macro_regime_table(start_date=start, end_date=end, yaml_cfg=cfg, equity=equity)
    error = result.get("error")
    if error:
        print(f"❌ {error}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ Sessions: {result.get('sessions_total', 0)} | Persisted: {result.get('persisted_rows', 0)} | Missing: {result.get('missing_rows', 0)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m service.market")
    sub = parser.add_subparsers(dest="command")

    populate_p = sub.add_parser("populate-macro", help="Alimenter stock_macro_indicators_daily")
    populate_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    populate_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")

    recompute_p = sub.add_parser("recompute-regime", help="Recalculer les colonnes dérivées de régime")
    recompute_p.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    recompute_p.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    recompute_p.add_argument("--equity", type=float, default=None, help="Equity simulée ($)")

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
