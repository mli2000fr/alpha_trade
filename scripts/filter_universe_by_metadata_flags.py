"""Filtre un fichier d'univers avec les indicateurs de ``stock_metadata``.

La base est consultée en lecture seule. La sortie contient une liste de symboles
séparés par des virgules, sans espaces.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine


_ELIGIBLE_SQL = text(
    """
    SELECT UPPER(TRIM(symbol)) AS symbol
    FROM stock_metadata
    WHERE symbol IN :symbols
      AND tradable = 1
      AND bars_available = 1
    """
).bindparams(bindparam("symbols", expanding=True))


def _read_symbols(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8-sig")
    return list(
        dict.fromkeys(
            token.strip().upper()
            for token in raw.replace("\n", ",").split(",")
            if token.strip()
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Filtre un univers sur tradable et bars_available.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=500)
    args = parser.parse_args()

    symbols = _read_symbols(args.input)
    eligible: set[str] = set()
    engine = get_sqlalchemy_engine()
    for start in range(0, len(symbols), args.chunk_size):
        block = symbols[start : start + args.chunk_size]
        with engine.connect() as connection:
            rows = connection.execute(_ELIGIBLE_SQL, {"symbols": block}).scalars().all()
        eligible.update(str(symbol).strip().upper() for symbol in rows if str(symbol).strip())

    selected = [symbol for symbol in symbols if symbol in eligible]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(",".join(selected), encoding="utf-8")

    print(f"Entrée : {len(symbols)}")
    print(f"Retenus : {len(selected)}")
    print(f"Retirés : {len(symbols) - len(selected)}")
    print(f"Sortie : {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
