"""Réduit une liste de symboles selon leur ancienneté dans stock_bars_daily.

Ce script ne lance aucun entraînement et n'écrit pas en base. Il lit une liste
séparée par des virgules, recherche la première barre disponible pour chaque
symbole, puis écrit les symboles dont l'historique commence avant la date limite.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine


_FIRST_BAR_SQL = text(
    """
    SELECT UPPER(TRIM(symbol)) AS symbol, MIN(date) AS first_bar_date
    FROM stock_bars_daily
    WHERE symbol IN :symbols
    GROUP BY UPPER(TRIM(symbol))
    """
).bindparams(bindparam("symbols", expanding=True))


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Date ISO invalide : {value}") from exc


def _read_symbols(path: Path) -> list[str]:
    return sorted(
        {
            token.strip().upper()
            for token in path.read_text(encoding="utf-8-sig").replace("\n", ",").split(",")
            if token.strip()
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Filtre read-only par date de première barre.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--must-exist-by", type=_iso_date, required=True)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--chunk-size", type=int, default=500)
    args = parser.parse_args()

    symbols = _read_symbols(args.input)
    first_dates: dict[str, date] = {}
    engine = get_sqlalchemy_engine()
    for start in range(0, len(symbols), args.chunk_size):
        block = symbols[start : start + args.chunk_size]
        with engine.connect() as connection:
            rows = connection.execute(_FIRST_BAR_SQL, {"symbols": block}).mappings().all()
        for row in rows:
            first_dates[str(row["symbol"]).strip().upper()] = row["first_bar_date"]

    eligible = [
        symbol
        for symbol in symbols
        if first_dates.get(symbol) is not None and first_dates[symbol] <= args.must_exist_by
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(",".join(eligible), encoding="utf-8")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("symbol", "first_bar_date", "eligible", "reason"))
            for symbol in symbols:
                first_date = first_dates.get(symbol)
                accepted = first_date is not None and first_date <= args.must_exist_by
                reason = "" if accepted else ("aucune_barre" if first_date is None else "creation_apres_limite")
                writer.writerow((symbol, first_date or "", int(accepted), reason))

    print(f"Entrée : {len(symbols)}")
    print(f"Retenus : {len(eligible)}")
    print(f"Retirés : {len(symbols) - len(eligible)}")
    print(f"Date limite : {args.must_exist_by.isoformat()}")
    print(f"Sortie : {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
