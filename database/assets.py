from functools import lru_cache
from typing import Any, Iterable, Mapping

from sqlalchemy import Boolean, Column, String, TIMESTAMP, Table, and_, func, or_, select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from database.connection import get_sqlalchemy_engine, SessionLocal, metadata
from service.alpaca.clientAlpaca import fetch_alpaca_assets

@lru_cache(maxsize=1)
def get_stock_metadata_table() -> Table:
    return Table(
        "stock_metadata",
        metadata,
        Column("symbol", String(100), primary_key=True),
        Column("id_alpaca", String(88)),
        Column("company_name", String(255)),
        Column("exchange", String(20)),
        Column("asset_class", String(20)),
        Column("status", String(20)),
        Column("tradable", Boolean),
        Column("bars_available", Boolean),
        Column("sector", String(50)),
        Column("last_updated", TIMESTAMP),
        autoload_with=get_sqlalchemy_engine(),
    )


def _require_sector_column(stock_metadata: Table) -> None:
    if "sector" not in stock_metadata.c:
        raise RuntimeError("La colonne stock_metadata.sector est absente du schéma SQL courant.")


def get_symbols_missing_sector(limit: int | None = None) -> list[str]:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    stock_metadata = get_stock_metadata_table()
    _require_sector_column(stock_metadata)
    stmt = (
        select(stock_metadata.c.symbol)
        .where(
            and_(
                stock_metadata.c.status == "active",
                stock_metadata.c.tradable.is_(True),
                stock_metadata.c.bars_available.is_(True),
                or_(
                    stock_metadata.c.sector.is_(None),
                    func.trim(stock_metadata.c.sector) == "",
                ),
            )
        )
        .order_by(stock_metadata.c.symbol)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    with get_sqlalchemy_engine().connect() as conn:
        return [str(symbol) for symbol in conn.execute(stmt).scalars().all()]


def update_stock_metadata_sector(symbol: str, sector: str) -> int:
    normalized_symbol = (symbol or "").strip().upper()
    normalized_sector = (sector or "").strip()
    if not normalized_symbol:
        raise ValueError("symbol ne peut pas être vide.")
    if not normalized_sector:
        raise ValueError("sector ne peut pas être vide.")

    stock_metadata = get_stock_metadata_table()
    _require_sector_column(stock_metadata)
    with get_sqlalchemy_engine().begin() as conn:
        result = conn.execute(
            text("UPDATE stock_metadata SET sector = :sector WHERE symbol = :symbol"),
            {"symbol": normalized_symbol, "sector": normalized_sector},
        )
        return int(result.rowcount or 0)


def insert_assets_to_db(assets: Iterable[Mapping[str, Any]]) -> int:
    stock_metadata = get_stock_metadata_table()
    asset_rows = [
        {
            "symbol": asset["symbol"],
            "id_alpaca": asset["id"],
            "company_name": asset.get("name", ""),
            "exchange": asset.get("exchange", ""),
            "asset_class": asset.get("class", ""),
            "status": asset.get("status", ""),
            "tradable": asset.get("tradable", False),
            "bars_available": True,
        }
        for asset in assets
    ]
    if not asset_rows:
        return 0

    session = SessionLocal()
    try:
        stmt = mysql_insert(stock_metadata).values(asset_rows)
        update_dict = {
            "id_alpaca": stmt.inserted.id_alpaca,
            "company_name": stmt.inserted.company_name,
            "exchange": stmt.inserted.exchange,
            "asset_class": stmt.inserted.asset_class,
            "status": stmt.inserted.status,
            "tradable": stmt.inserted.tradable,
            "bars_available": stmt.inserted.bars_available,
            "last_updated": func.current_timestamp(),
        }
        session.execute(stmt.on_duplicate_key_update(**update_dict))
        session.commit()
        return len(asset_rows)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sync_assets_from_alpaca() -> int:
    return insert_assets_to_db(fetch_alpaca_assets())


def update_bars_available_false(symbol: str) -> None:
    stock_metadata = get_stock_metadata_table()
    session = SessionLocal()
    try:
        stmt = stock_metadata.update().where(stock_metadata.c.symbol == symbol).values(bars_available=False)
        session.execute(stmt)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
