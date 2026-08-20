"""E4-B0 — couverture des candidats sur l'univers TRADING réel (config/ticket_recherche.txt, 400)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

TICKET = Path("config/ticket_recherche.txt")
OUT = "artifacts/models/oracle/e4b0_coverage_trading_universe.md"

# tables avec (date_col, symbol_col) — couverture par année vs univers 400
TABLES = [
    ("stock_earnings_calendar", "earnings_date", "symbol", "A", "par événement"),
    ("stock_fundamentals_daily", "trade_date", "symbol", "A", "trimestriel"),
    ("ticker_daily_sentiment_features", "trade_date", "symbol", "B", "quotidien"),
    ("global_rank_history", "date", "symbol", "E", "quotidien"),
]


def main() -> None:
    syms = [s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()]
    print(f"univers trading: {len(syms)} symboles")
    # années cibles = 2022..2026 (périodes de test E4)
    years = [2022, 2023, 2024, 2025, 2026]
    sym_set = set(syms)

    eng = get_sqlalchemy_engine()
    lines = [
        "# E4-B0 — Couverture des candidats sur l'univers TRADING réel",
        "",
        f"Univers : `config/ticket_recherche.txt` = **{len(syms)} symboles** (celui utilisé en trade).",
        "",
        "| table | cat | 1ère date | dernière date | N | sym. dans univers 400 | couverture 400 par année | fréquence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    with eng.connect() as c:
        for table, date_col, sym_col, cat, freq in TABLES:
            try:
                q = f"SELECT COUNT(*) n, COUNT(DISTINCT {sym_col}) ns, MIN({date_col}) mn, MAX({date_col}) mx FROM {table}"
                n, ns, mn, mx = tuple(c.execute(text(q)).fetchone())
                # symboles de l'univers présents (toutes années)
                in_univ = c.execute(text(
                    f"SELECT DISTINCT {sym_col} FROM {table} WHERE {sym_col} IN ({','.join([':s%d' % i for i in range(len(syms))])})"
                ), {f"s{i}": s for i, s in enumerate(syms)}).fetchall()
                in_univ_set = {r[0] for r in in_univ}
                # couverture par année
                cov_parts = []
                for y in years:
                    qy = (f"SELECT COUNT(DISTINCT {sym_col}) FROM {table} WHERE YEAR({date_col})=:y "
                          f"AND {sym_col} IN ({','.join([':s%d' % i for i in range(len(syms))])})")
                    hit = c.execute(text(qy), {"y": y, **{f"s{i}": s for i, s in enumerate(syms)}}).scalar()
                    cov_parts.append(f"{y}:{int(hit)}/{len(syms)}")
                lines.append(
                    f"| {table} | {cat} | {mn} | {mx} | {int(n):,} | {len(in_univ_set):,} | "
                    f"{' '.join(cov_parts)} | {freq} |"
                )
                print(f"  OK {table}: N={int(n):,} sym400={len(in_univ_set)} | {' '.join(cov_parts)}")
            except Exception as e:  # noqa: BLE001
                lines.append(f"| {table} | {cat} | ERREUR: {str(e)[:70]} | | | | | |")
                print(f"  !! {table}: {e}")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
