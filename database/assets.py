from functools import lru_cache
from typing import Any, Iterable, Mapping

from sqlalchemy import Boolean, Column, String, TIMESTAMP, Table
from sqlalchemy.dialects.mysql import insert as mysql_insert
from database.connection import get_sqlalchemy_engine, SessionLocal, metadata
from service.alpaca.client import fetch_alpaca_assets

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
        Column("last_updated", TIMESTAMP),
        autoload_with=get_sqlalchemy_engine(),
    )


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
            "last_updated": stmt.inserted.last_updated,
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
