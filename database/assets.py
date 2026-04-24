from functools import lru_cache
from typing import Any, Iterable, Mapping

from sqlalchemy import Boolean, Column, Float, MetaData, String, TIMESTAMP, Table, and_, func, or_, select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from database.connection import get_sqlalchemy_engine, SessionLocal, metadata
from service.alpaca.clientAlpaca import fetch_alpaca_assets

HISTORY_STATUS_PENDING = "pending"
HISTORY_STATUS_READY = "ready"
HISTORY_STATUS_NO_HISTORY = "no_history"
HISTORY_STATUS_PROVIDER_ERROR = "provider_error"
HISTORY_STATUS_SUSPENDED_OR_STALE = "suspended_or_stale"
HISTORY_STATUS_EXCLUDED_BY_POLICY = "excluded_by_policy"
ELIGIBLE_HISTORY_STATUSES: tuple[str, ...] = (
    HISTORY_STATUS_PENDING,
    HISTORY_STATUS_READY,
)

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
        Column("history_status", String(32)),
        Column("sector", String(50)),
        Column("market_cap", Float),
        Column("last_updated", TIMESTAMP),
        autoload_with=get_sqlalchemy_engine(),
    )


def _require_sector_column(stock_metadata: Table) -> None:
    if "sector" not in stock_metadata.c:
        raise RuntimeError("La colonne stock_metadata.sector est absente du schéma SQL courant.")


def _require_market_cap_column(stock_metadata: Table) -> None:
    if "market_cap" not in stock_metadata.c:
        raise RuntimeError("La colonne stock_metadata.market_cap est absente du schéma SQL courant.")


def _has_history_status_column(stock_metadata: Table) -> bool:
    return "history_status" in stock_metadata.c


def build_eligible_stock_metadata_filters(stock_metadata: Table) -> list[Any]:
    filters: list[Any] = []
    if "status" in stock_metadata.c:
        filters.append(stock_metadata.c.status == "active")
    if "tradable" in stock_metadata.c:
        filters.append(stock_metadata.c.tradable.is_(True))
    if "bars_available" in stock_metadata.c:
        filters.append(stock_metadata.c.bars_available.is_(True))
    if "asset_class" in stock_metadata.c:
        filters.append(stock_metadata.c.asset_class == "us_equity")
    if _has_history_status_column(stock_metadata):
        filters.append(
            or_(
                stock_metadata.c.history_status.is_(None),
                func.trim(stock_metadata.c.history_status) == "",
                func.lower(func.trim(stock_metadata.c.history_status)).in_(ELIGIBLE_HISTORY_STATUSES),
            )
        )
    return filters


def list_eligible_stock_symbols(
    limit: int | None = None,
    *,
    engine=None,
    stock_metadata: Table | None = None,
) -> list[str]:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    resolved_engine = engine or get_sqlalchemy_engine()
    if stock_metadata is None:
        stock_metadata = Table("stock_metadata", MetaData(), autoload_with=resolved_engine)

    stmt = (
        select(stock_metadata.c.symbol)
        .where(and_(*build_eligible_stock_metadata_filters(stock_metadata)))
        .order_by(stock_metadata.c.symbol)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    with resolved_engine.connect() as conn:
        rows = conn.execute(stmt).scalars().all()
    return [str(symbol).strip().upper() for symbol in rows if str(symbol).strip()]


def get_symbols_missing_sector(limit: int | None = None) -> list[str]:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    stock_metadata = get_stock_metadata_table()
    _require_sector_column(stock_metadata)
    stmt = (
        select(stock_metadata.c.symbol)
        .where(
            and_(
                *build_eligible_stock_metadata_filters(stock_metadata),
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


def get_symbols_missing_fundamentals(limit: int | None = None) -> list[str]:
    if limit is not None and limit < 1:
        raise ValueError("limit doit être supérieur ou égal à 1.")

    stock_metadata = get_stock_metadata_table()
    _require_sector_column(stock_metadata)
    _require_market_cap_column(stock_metadata)
    stmt = (
        select(stock_metadata.c.symbol)
        .where(
            and_(
                *build_eligible_stock_metadata_filters(stock_metadata),
                or_(
                    stock_metadata.c.sector.is_(None),
                    func.trim(stock_metadata.c.sector) == "",
                    stock_metadata.c.market_cap.is_(None),
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
    return update_stock_metadata_fundamentals(symbol, sector=sector)


def update_stock_metadata_fundamentals(
    symbol: str,
    *,
    sector: str | None = None,
    market_cap: float | None = None,
) -> int:
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol ne peut pas être vide.")
    normalized_sector = (sector or "").strip() or None
    normalized_market_cap = None if market_cap is None else float(market_cap)
    if normalized_sector is None and normalized_market_cap is None:
        raise ValueError("Au moins une valeur parmi sector ou market_cap doit être renseignée.")

    stock_metadata = get_stock_metadata_table()
    assignments: list[str] = []
    params: dict[str, object] = {"symbol": normalized_symbol}
    if normalized_sector is not None:
        _require_sector_column(stock_metadata)
        assignments.append("sector = :sector")
        params["sector"] = normalized_sector
    if normalized_market_cap is not None:
        _require_market_cap_column(stock_metadata)
        assignments.append("market_cap = :market_cap")
        params["market_cap"] = normalized_market_cap

    with get_sqlalchemy_engine().begin() as conn:
        result = conn.execute(
            text(f"UPDATE stock_metadata SET {', '.join(assignments)} WHERE symbol = :symbol"),
            params,
        )
        return int(result.rowcount or 0)


def insert_assets_to_db(assets: Iterable[Mapping[str, Any]]) -> int:
    stock_metadata = get_stock_metadata_table()
    asset_rows = [
        {
            **{
                "symbol": asset["symbol"],
                "id_alpaca": asset["id"],
                "company_name": asset.get("name", ""),
                "exchange": asset.get("exchange", ""),
                "asset_class": asset.get("class", ""),
                "status": asset.get("status", ""),
                "tradable": asset.get("tradable", False),
                "bars_available": True,
                "market_cap": None,
            },
            **({"history_status": HISTORY_STATUS_PENDING} if _has_history_status_column(stock_metadata) else {}),
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
        if _has_history_status_column(stock_metadata):
            update_dict["history_status"] = stmt.inserted.history_status
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
    update_symbol_history_status(symbol, HISTORY_STATUS_NO_HISTORY, bars_available=False)


def mark_symbol_history_ready(symbol: str) -> int:
    return update_symbol_history_status(symbol, HISTORY_STATUS_READY, bars_available=True)


def update_symbol_history_status(
    symbol: str,
    history_status: str,
    *,
    bars_available: bool | None = None,
) -> int:
    stock_metadata = get_stock_metadata_table()
    session = SessionLocal()
    normalized_symbol = str(symbol).strip().upper()
    values: dict[str, object] = {}
    if bars_available is not None:
        values["bars_available"] = bool(bars_available)
    if _has_history_status_column(stock_metadata):
        values["history_status"] = str(history_status).strip().lower()
    if not values:
        return 0
    try:
        stmt = stock_metadata.update().where(stock_metadata.c.symbol == normalized_symbol).values(**values)
        session.execute(stmt)
        session.commit()
        return 1
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
