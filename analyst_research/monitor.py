"""Monitoring de la collecte analyst — MySQL uniquement (RESEARCH ONLY).

Usage :
    python -m analyst_research.monitor status
    python -m analyst_research.monitor history AAPL [--horizon CURRENT_YEAR]
    python -m analyst_research.monitor errors

Aucun artifact fichier : tout est lu depuis MySQL (les tables append-only).
"""
from __future__ import annotations

import argparse
import sys

from analyst_research.parsers import HORIZON_MAP, STATUS_INVALID_SYMBOL, STATUS_PARSE_ERROR
from database.repositories.analyst_snapshots import AnalystSnapshotRepository


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def cmd_status() -> int:
    repo = AnalystSnapshotRepository()
    run = repo.get_last_collection_run()
    print("=== Dernier run de collecte ===")
    if run is None:
        print("  Aucun run enregistré.")
    else:
        for k in ("run_id", "provider", "started_at", "finished_at", "status",
                  "requested_symbols", "successful_symbols", "empty_symbols", "failed_symbols",
                  "estimates_rows_inserted", "targets_rows_inserted", "recommendations_rows_inserted",
                  "eps_coverage", "revenue_coverage", "target_coverage", "recommendation_coverage",
                  "rate_limit_count", "temporary_error_count", "schema_error_count", "parse_error_count"):
            print(f"  {k}: {_fmt(run.get(k))}")
    print("\n=== Compteurs tables ===")
    for name, n in repo.count_rows().items():
        print(f"  {name}: {n}")
    return 0


def cmd_errors() -> int:
    repo = AnalystSnapshotRepository()
    run = repo.get_last_collection_run()
    print("=== Erreurs du dernier run ===")
    if run is None:
        print("  Aucun run.")
        return 0
    # Les symboles en erreur ne sont pas stockés par run ; consulter les runs.
    print("  (les statuts par symbole sont visibles dans les logs du run ; "
          "le run trace les compteurs RATE_LIMIT/TEMP/SCHEMA/PARSE ci-dessus)")
    return 0


def cmd_history(symbol: str, horizon: str | None) -> int:
    repo = AnalystSnapshotRepository()
    print(f"=== Historique estimates {symbol} ===")
    est = repo.get_estimate_history(symbol.upper())
    if not est:
        print("  Aucune donnée estimate.")
    else:
        print(f"  {'available_at':<20} {'type':<8} {'horizon':<18} {'avg':>8} {'low':>8} {'high':>8} {'n':>4}")
        for r in est:
            if horizon and r["horizon_normalized"] != horizon:
                continue
            print(f"  {str(r['available_at']):<20} {r['estimate_type']:<8} "
                  f"{r['horizon_normalized']:<18} {_fmt(r['avg_value']):>8} "
                  f"{_fmt(r['low_value']):>8} {_fmt(r['high_value']):>8} "
                  f"{r['analyst_count'] if r['analyst_count'] is not None else '-'}")
    print(f"\n=== Historique targets {symbol.upper()} ===")
    tgt = repo.get_target_history(symbol.upper())
    if not tgt:
        print("  Aucune donnée target.")
    else:
        print(f"  {'available_at':<20} {'mean':>8} {'median':>8} {'low':>8} {'high':>8}")
        for r in tgt:
            print(f"  {str(r['available_at']):<20} {_fmt(r['target_mean']):>8} "
                  f"{_fmt(r['target_median']):>8} {_fmt(r['target_low']):>8} "
                  f"{_fmt(r['target_high']):>8}")
    print(f"\n=== Historique recommendations {symbol.upper()} (0m) ===")
    rec = repo.get_recommendation_history(symbol.upper(), period_raw="0m")
    if not rec:
        print("  Aucune donnée recommendation.")
    else:
        print(f"  {'available_at':<20} {'SB':>4} {'B':>4} {'H':>4} {'S':>4} {'SS':>4}")
        for r in rec:
            print(f"  {str(r['available_at']):<20} {r['strong_buy'] or 0:>4} {r['buy'] or 0:>4} "
                  f"{r['hold'] or 0:>4} {r['sell'] or 0:>4} {r['strong_sell'] or 0:>4}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitoring collecte analyst (RESEARCH ONLY).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Dernier run + compteurs")
    sub.add_parser("errors", help="Erreurs du dernier run")
    p_hist = sub.add_parser("history", help="Historique d'un symbole")
    p_hist.add_argument("symbol")
    p_hist.add_argument("--horizon", default=None,
                        help="Filtrer sur un horizon (ex. CURRENT_YEAR)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "errors":
        return cmd_errors()
    if args.cmd == "history":
        return cmd_history(args.symbol, args.horizon)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
