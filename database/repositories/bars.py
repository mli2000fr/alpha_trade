"""Repository ``stock_bars`` / ``stock_bars_daily`` (Phase 2.2).

Squelette : la migration des appels ``database/sanitizer_db_ops.py`` et
``database/bar_metadata.py`` est faite Phase 3.1 (dataIntegrityEngine).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import text

from database.repositories._base import Repository
from database.repositories.instruments import InstrumentRepository


class BarsRepository(Repository):
    """Repository OHLCV (table ``stock_bars_daily`` actuellement).

    Lit/écrit avec la convention canonique ``data_adjustment='split'``
    (CHECK `chk_daily_adj`). La colonne ``data_source`` est renseignée
    par défaut à ``alpaca_iex``.
    """

    def load_bars(
        self,
        symbol: str | None = None,
        start: date | None = None,
        end: date | None = None,
        *,
        instrument_id: int | None = None,
        market_code: str = "US_EQ",
    ) -> pd.DataFrame:
        if instrument_id is None:
            if not symbol or not symbol.strip():
                raise ValueError("symbol ou instrument_id est obligatoire")
            instrument = InstrumentRepository(engine=self.engine).resolve_local_symbol(
                market_code,
                symbol,
            )
            if instrument is None:
                raise LookupError(f"Instrument introuvable: {market_code}/{symbol}")
            instrument_id = int(instrument["instrument_id"])
        clauses = ["instrument_id = :instrument_id"]
        params: dict[str, object] = {"instrument_id": int(instrument_id)}
        if start is not None:
            clauses.append("date >= :start")
            params["start"] = start
        if end is not None:
            clauses.append("date <= :end")
            params["end"] = end
        sql = text(
            f"SELECT * FROM stock_bars_daily WHERE {' AND '.join(clauses)} "
            "ORDER BY date ASC"
        )
        with self.connect() as conn:
            return pd.read_sql(sql, conn, params=params)

    def upsert_bars(  # pragma: no cover - Phase 3.1
        self,
        symbol: str,
        bars: pd.DataFrame,
        *,
        data_adjustment: str = "split",
        data_source: str = "alpaca_iex",
    ) -> int:
        raise NotImplementedError(
            "upsert_bars sera branché Phase 3.1 (migration sanitizer_db_ops)."
        )

