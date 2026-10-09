"""CLI EODHD daily ingestion."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
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
    p.add_argument("--target-date", default=None, help="Date cible YYYY-MM-DD (défaut dernière séance publiée).")
    p.add_argument('--symbol-source', help="Fichier explicite universe-file:... ; incompatible avec --symbols")
    p.add_argument('--wait-for-publication', action='store_true', help='Attendre clôture J + délai EODHD avant import')
    p.add_argument('--require-target-coverage', action='store_true', help='Bloquer le workflow si les cours canoniques J sont insuffisants')
    p.add_argument('--min-target-coverage', type=float, default=.95)
    p.add_argument('--benchmark-symbol', default='SPY')
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
    if args.symbols is not None and args.symbol_source:
        raise ValueError('Choisir --symbols OU --symbol-source')
    if args.require_target_coverage and (not args.target_date or not args.write):
        raise ValueError('--require-target-coverage exige --target-date et --write')
    if args.wait_for_publication and not args.target_date:
        raise ValueError('--wait-for-publication exige --target-date')
    symbols = args.symbols
    if args.symbol_source:
        from common.universe_files import load_universe_file_symbols
        symbols = load_universe_file_symbols(args.symbol_source)
    if symbols is not None and not symbols:
        raise ValueError('Univers explicite vide ; pas de fallback vers tous les titres')
    if args.require_target_coverage and not symbols:
        raise ValueError('Contrôle de couverture : univers explicite requis')

    cfg = shim._load_config_safe()
    provider = shim.resolve_bars_provider(cfg)
    if provider != "eodhd":
        if args.require_target_coverage:
            raise ValueError('Import quotidien EODHD requis mais fournisseur configuré différent')
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
    if args.require_target_coverage:
        # Validate configuration BEFORE provider calls or writes.
        from dataIntegrityEngine.eodhd.readiness import publication_at
        import math
        if not math.isfinite(args.min_target_coverage) or not 0 < args.min_target_coverage <= 1:
            raise ValueError('--min-target-coverage attendu dans ]0,1]')
        if not args.benchmark_symbol.strip():
            raise ValueError('Benchmark vide')
        publication_at(date.fromisoformat(args.target_date), cfg)
    if args.wait_for_publication and not dry_run:
        from dataIntegrityEngine.eodhd.readiness import wait_for_publication
        wait_for_publication(date.fromisoformat(args.target_date), cfg)
    import_symbols = symbols
    if args.require_target_coverage:
        import_symbols = list(dict.fromkeys([*symbols, args.benchmark_symbol.strip().upper()]))
    summary = run_eodhd_ingestion(
        dry_run=dry_run,
        target_date=args.target_date,
        symbols=import_symbols,
        per_symbol_limit=args.per_symbol_limit,
        write_commit_every_symbols=args.commit_every_symbols,
        enable_stooq_cross_check=not args.no_stooq_cross_check,
        config=cfg,
        refresh_target_date=args.require_target_coverage,
    )
    if args.require_target_coverage:
        from dataIntegrityEngine.eodhd.readiness import target_coverage
        from database.connection import get_sqlalchemy_engine
        try:
            gate = target_coverage(get_sqlalchemy_engine(), symbols, args.target_date,
                benchmark=args.benchmark_symbol, minimum=args.min_target_coverage)
        except Exception as exc:
            # Preserve import counters even when the read-only qualification fails.
            summary['errors'] = int(summary.get('errors', 0)) + 1
            summary['status'] = 'FAILED'
            summary['stopped_reason'] = 'target_date_coverage_check_failed'
            summary['error_message'] = f'Contrôle des cours J impossible : {type(exc).__name__}'
            emit_run_summary(attach_schema_version(summary))
            return 1
        summary['target_coverage'] = gate
        if gate['status'] != 'PASSED':
            summary['errors'] = int(summary.get('errors', 0)) + 1
            summary['stopped_reason'] = 'target_date_coverage_insufficient'
            summary['error_message'] = (f"Cours {args.target_date} insuffisants : "
                f"{gate['covered']}/{gate['requested']} ({gate['coverage_ratio']:.1%}), "
                f"minimum={gate['minimum']:.1%}, benchmark {gate['benchmark']} "
                f"disponible={gate['benchmark_available']}")
            LOGGER.error('[eodhd] %s ; absents=%s', summary['error_message'], gate['missing_symbols'][:25])
        summary['status'] = 'FAILED' if summary.get('errors', 0) else 'COMPLETED'
    emit_run_summary(attach_schema_version(summary))
    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["build_arg_parser", "main"]

