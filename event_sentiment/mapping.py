from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import select

from database.assets import get_stock_metadata_table
from database.connection import get_sqlalchemy_engine
from service.finnhub.clientFinnhub import fetch_multiple_symbol_sector_records

UNKNOWN_SECTOR = "UNKNOWN"


class EntitySectorMapper:
    def __init__(self) -> None:
        self.engine = get_sqlalchemy_engine()
        self.stock_metadata = get_stock_metadata_table()

    def _load_local_sectors(self, symbols: Iterable[str]) -> dict[str, dict]:
        symbol_list = sorted({(symbol or "").strip().upper() for symbol in symbols if symbol})
        if not symbol_list:
            return {}

        # ``company_name`` est utilisé par :mod:`event_sentiment.relevance`
        # pour l'heuristique « nom société dans headline ». La colonne est
        # NULL-able dans ``stock_metadata`` ; on tolère son absence.
        columns = [
            self.stock_metadata.c.symbol,
            self.stock_metadata.c.sector,
            self.stock_metadata.c.last_updated,
        ]
        company_col = getattr(self.stock_metadata.c, "company_name", None)
        if company_col is not None:
            columns.append(company_col)
        stmt = select(*columns).where(self.stock_metadata.c.symbol.in_(symbol_list))
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()

        result: dict[str, dict] = {}
        for row in rows:
            symbol = row[0]
            sector = row[1]
            last_updated = row[2]
            company_name = row[3] if company_col is not None and len(row) > 3 else None
            normalized_sector = str(sector).strip() if sector is not None else ""
            if normalized_sector:
                result[str(symbol)] = {
                    "sector": normalized_sector,
                    "sector_source": "stock_metadata",
                    "sector_updated_at": last_updated if isinstance(last_updated, datetime) else None,
                    "company_name": str(company_name).strip() if company_name else None,
                }
        return result

    def resolve(self, symbols: Iterable[str], allow_fallback: bool = True) -> dict[str, dict]:
        normalized_symbols = [str(symbol).strip().upper() for symbol in symbols if symbol]
        resolved = self._load_local_sectors(normalized_symbols)
        missing = [symbol for symbol in normalized_symbols if symbol not in resolved]

        if allow_fallback and missing:
            fallback_rows = fetch_multiple_symbol_sector_records(missing)
            for row in fallback_rows:
                symbol = str(row["symbol"]).upper()
                sector = row.get("sector")
                if sector:
                    resolved[symbol] = {
                        "sector": str(sector).strip(),
                        "sector_source": row.get("source", "Finnhub"),
                        "sector_updated_at": datetime.now(UTC).replace(tzinfo=None),
                    }
        return resolved


