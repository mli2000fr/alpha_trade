"""Construit un fichier d'univers limité aux actions d'entreprises.

Le fichier source n'est jamais modifié afin de préserver la reproductibilité
des anciens batchs. Le filtrage réutilise exactement la politique instrument du
screener et du publieur d'univers tradable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.instrument_policy import excluded_collective_instrument_reason
from database.connection import get_sqlalchemy_engine


DEFAULT_SOURCE = Path("config/univers/univers_filtred.txt")
DEFAULT_OUTPUT = Path("config/univers/univers_filtred_equities.txt")


def read_symbols(path: Path) -> list[str]:
    symbols: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        clean = line.split("#", 1)[0]
        symbols.update(item.strip().upper() for item in clean.split(",") if item.strip())
    return sorted(symbols)


def filter_equity_symbols(
    symbols: list[str],
    metadata: pd.DataFrame,
) -> tuple[list[str], list[dict[str, str]]]:
    names = {
        str(row.symbol).strip().upper(): row.company_name
        for row in metadata.itertuples(index=False)
    }
    retained: list[str] = []
    excluded: list[dict[str, str]] = []
    for symbol in sorted(set(symbols)):
        reason = excluded_collective_instrument_reason(names.get(symbol))
        if reason is None:
            retained.append(symbol)
        else:
            excluded.append({"symbol": symbol, "reason": reason})
    return retained, excluded


def load_metadata(engine: Engine, symbols: list[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "company_name"])
    with engine.connect() as connection:
        return pd.read_sql(
            text("SELECT symbol, company_name FROM stock_metadata"),
            connection,
        ).query("symbol in @symbols")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exclut ETF, ETN, fonds et produits à levier/inverses d'un fichier d'univers.",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    symbols = read_symbols(args.source)
    metadata = load_metadata(get_sqlalchemy_engine(), symbols)
    retained, excluded = filter_equity_symbols(symbols, metadata)
    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(",".join(retained) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "source": str(args.source),
                "output": None if args.dry_run else str(args.output),
                "input_symbols": len(symbols),
                "retained_equities": len(retained),
                "excluded_collective_instruments": len(excluded),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
