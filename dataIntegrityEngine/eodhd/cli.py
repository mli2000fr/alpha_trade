"""CLI EODHD daily ingestion."""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from core.run_summary import attach_schema_version

from dataIntegrityEngine.eodhd.orchestrator import (
    DEFAULT_PER_SYMBOL_LIMIT,
    DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS,
    resolve_target_date,
    run_eodhd_ingestion,
)
from dataIntegrityEngine.eodhd.progress import (
    build_run_id,
    emit_run_summary,
    utc_now_naive,
)

LOGGER = logging.getLogger("dataIntegrityEngine.import_eodhd_bar")


def _shim():
    from dataIntegrityEngine import import_eodhd_bar as shim_mod
    return shim_mod


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Importe les barres daily EODHD (Phase 3 shadow).")
    p.add_argument("--symbols", nargs="+", default=None, help="Sous-univers explicite.")
    p.add_argument("--target-date", default=None, help="Date cible YYYY-MM-DD (défaut J-1).")
    p.add_argument(
        "--per-symbol-limit",
        type=int,
        default=DEFAULT_PER_SYMBOL_LIMIT,
        help=f"Plafond appels per-symbol pour récup absences bulk (défaut: {DEFAULT_PER_SYMBOL_LIMIT}).",
    )
    p.add_argument(
        "--commit-every-symbols",
        type=int,
        default=DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS,
        help=(
            "En mode --write, effectue un upsert + commit intermédiaire toutes les N itérations symbole. "
            f"0 = commit final unique uniquement. Défaut: {DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS}."
        ),
    )
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--dry-run", action="store_true", default=True,
                     help="Mode shadow (défaut Phase 3) — aucune écriture DB.")
    grp.add_argument("--write", action="store_true", default=False,
                     help="Mode write — upsert effectif dans stock_bars + stock_bars_daily.")
    p.add_argument("--no-stooq-cross-check", action="store_true", default=False)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    shim = _shim()
    shim.configure_root_logging(
        level=logging.INFO,
        log_path="./log/import_eodhd_bar.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = build_arg_parser().parse_args(argv)

    cfg = shim._load_config_safe()
    provider = shim.resolve_bars_provider(cfg)
    if provider != "eodhd":
        LOGGER.info(
            "[eodhd] bars_provider=%s -> import_eodhd_bar no-op (Phase 3 conformité plan §5.6)",
            provider,
        )
        skip_summary = {
            "run_id": build_run_id("import-eodhd-noop"),
            "provider": "eodhd",
            "mode": "noop",
            "target_date": resolve_target_date(cfg),
            "skipped_reason": f"bars_provider={provider}",
            "started_at": utc_now_naive().isoformat(timespec="seconds"),
            "finished_at": utc_now_naive().isoformat(timespec="seconds"),
            "duration_seconds": 0.0,
            "eodhd": {"calls_used": 0, "calls_failed": 0, "circuit_open": False},
            "stooq_cross_check_enabled": False,
            "cross_check_stooq": {"anomalies_count": 0, "failed": False, "skipped": True},
        }
        emit_run_summary(attach_schema_version(skip_summary))
        return 0

    dry_run = not args.write
    summary = run_eodhd_ingestion(
        dry_run=dry_run,
        target_date=args.target_date,
        symbols=args.symbols,
        per_symbol_limit=args.per_symbol_limit,
        write_commit_every_symbols=args.commit_every_symbols,
        enable_stooq_cross_check=not args.no_stooq_cross_check,
        config=cfg,
    )
    emit_run_summary(attach_schema_version(summary))
    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["build_arg_parser", "main"]

