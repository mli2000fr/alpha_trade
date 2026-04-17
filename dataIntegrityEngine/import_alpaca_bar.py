import logging
import math
from datetime import timedelta
from functools import lru_cache
from typing import Any, Optional

import pytz
from dateutil import parser
from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.utils import getLastDateMarche
from database.assets import update_bars_available_false
from database.bar_metadata import TimeFrame
from database.connection import SessionLocal, get_sqlalchemy_engine
from service.alpaca.clientAlpaca import fetch_bars

LOGGER = logging.getLogger(__name__)
TZ_NEW_YORK = pytz.timezone("America/New_York")


@lru_cache(maxsize=1)
def _get_tables() -> tuple[Table, Table]:
    metadata = MetaData()
    engine = get_sqlalchemy_engine()
    stock_metadata = Table("stock_metadata", metadata, autoload_with=engine)
    stock_bars = Table("stock_bars", metadata, autoload_with=engine)
    return stock_metadata, stock_bars


def get_active_tradable_symbols(session) -> list[str]:
    stock_metadata, _ = _get_tables()
    q = select(stock_metadata.c.symbol).where(
        and_(
            stock_metadata.c.status == "active",
            stock_metadata.c.tradable.is_(True),
            stock_metadata.c.bars_available.is_(True),
            stock_metadata.c.asset_class == "us_equity",  # exclut crypto (us_crypto)
        )
    )
    return [row[0] for row in session.execute(q).all()]


def symbol_exists_in_stock_bars(session, symbol: str) -> bool:
    _, stock_bars = _get_tables()
    q = select(stock_bars.c.symbol).where(stock_bars.c.symbol == symbol).limit(1)
    return session.execute(q).first() is not None


def get_last_bar_timestamp(session, symbol: str, time_frame: TimeFrame):
    _, stock_bars = _get_tables()
    q = select(func.max(stock_bars.c.timestamp)).where(
        and_(stock_bars.c.symbol == symbol, stock_bars.c.timeframe == time_frame.db_value)
    )
    return session.execute(q).scalar_one_or_none()


def _normalize_bar_timestamp(raw_timestamp: Any) -> Any:
    if not (isinstance(raw_timestamp, str) and "T" in raw_timestamp):
        return raw_timestamp

    dt_utc = parser.isoparse(raw_timestamp)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
    return dt_utc.astimezone(TZ_NEW_YORK).strftime("%Y-%m-%d %H:%M:%S")


def _sanitize_price(value: Any, field: str, symbol: str) -> Optional[float]:
    """
    Nettoie une valeur de prix avant insertion MySQL.
    - None / NaN / Inf → None (sera refusé par NOT NULL, mais mieux qu'un crash silencieux)
    - Valeur > DECIMAL(20,8) max → loggée et mise à None
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        LOGGER.warning("Valeur non numérique | symbol=%s field=%s value=%r → None", symbol, field, value)
        return None
    if not math.isfinite(f):
        LOGGER.warning("Valeur non finie (inf/nan) | symbol=%s field=%s value=%r → None", symbol, field, f)
        return None
    # DECIMAL(20,8) : partie entière max = 12 chiffres
    if abs(f) > 999_999_999_999.0:
        LOGGER.warning("Valeur hors plage DECIMAL(20,8) | symbol=%s field=%s value=%r → None", symbol, field, f)
        return None
    return f


def _build_bar_records(symbol: str, bars: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    records = []
    skipped = 0
    for bar in bars:
        open_price  = _sanitize_price(bar.get("o"),  "open_price",  symbol)
        high_price  = _sanitize_price(bar.get("h"),  "high_price",  symbol)
        low_price   = _sanitize_price(bar.get("l"),  "low_price",   symbol)
        close_price = _sanitize_price(bar.get("c"),  "close_price", symbol)
        vwa_price   = _sanitize_price(bar.get("vw"), "vwa_price",   symbol)

        # Ignorer la barre si un prix obligatoire est invalide (NOT NULL en DB)
        if None in (open_price, high_price, low_price, close_price):
            skipped += 1
            LOGGER.warning(
                "Barre ignorée (prix invalide) | symbol=%s timestamp=%s o=%s h=%s l=%s c=%s",
                symbol, bar.get("t"), bar.get("o"), bar.get("h"), bar.get("l"), bar.get("c"),
            )
            continue

        # Fallback vwa_price → close si absent (colonne NOT NULL dans le schéma)
        if vwa_price is None:
            vwa_price = close_price

        records.append({
            "symbol":      symbol,
            "timestamp":   _normalize_bar_timestamp(bar["t"]),
            "timeframe":   timeframe,
            "open_price":  open_price,
            "high_price":  high_price,
            "low_price":   low_price,
            "close_price": close_price,
            "volume":      int(bar.get("v") or 0),
            "trade_count": int(bar.get("n") or 0),
            "vwa_price":   vwa_price,
        })

    if skipped:
        LOGGER.warning("Barres ignorées au total | symbol=%s skipped=%s total=%s", symbol, skipped, len(bars))
    return records


def insert_bars(session, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int:
    if not bars:
        return 0

    _, stock_bars = _get_tables()
    records = _build_bar_records(symbol, bars, timeframe)

    if not records:
        LOGGER.warning("insert_bars | aucune barre valide après sanitization | symbol=%s total_brut=%s", symbol, len(bars))
        return 0

    stmt = mysql_insert(stock_bars).values(records)
    update_dict = {
        "open_price": stmt.inserted.open_price,
        "high_price": stmt.inserted.high_price,
        "low_price": stmt.inserted.low_price,
        "close_price": stmt.inserted.close_price,
        "volume": stmt.inserted.volume,
        "trade_count": stmt.inserted.trade_count,
        "vwa_price": stmt.inserted.vwa_price,
    }
    try:
        session.execute(stmt.on_duplicate_key_update(**update_dict))
        session.commit()
    except Exception:
        session.rollback()
        LOGGER.error("Échec insert_bars | symbol=%s timeframe=%s bars=%s", symbol, timeframe, len(bars))
        raise
    return len(bars)


def _format_last_timestamp(last_timestamp: Any) -> Optional[str]:
    if last_timestamp is None:
        return None
    if hasattr(last_timestamp, "strftime"):
        return last_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(last_timestamp)


def _increment_start_timestamp(raw_timestamp: Optional[str]) -> Optional[str]:
    if not raw_timestamp:
        return None

    dt = parser.isoparse(raw_timestamp)
    next_dt = dt + timedelta(minutes=1)
    return next_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_target_symbols(symbols: Optional[list[str]]) -> Optional[list[str]]:
    if symbols is None:
        return None

    normalized: list[str] = []
    for symbol in symbols:
        cleaned = (symbol or "").strip().upper()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)

    if not normalized:
        raise ValueError("symbols doit contenir au moins un symbole non vide.")
    return normalized


def import_alpaca_bars(time_frame: TimeFrame, symbols: Optional[list[str]] = None) -> None:
    session = SessionLocal()
    try:
        target_symbols = _normalize_target_symbols(symbols)
        if target_symbols is None:
            target_symbols = get_active_tradable_symbols(session)
            LOGGER.info("Import Alpaca univers complet | timeframe=%s symbols=%s", time_frame.db_value, len(target_symbols))
        else:
            LOGGER.info("Import Alpaca ciblé | timeframe=%s symbols=%s", time_frame.db_value, ",".join(target_symbols))

        total = len(target_symbols)

        for idx, symbol in enumerate(target_symbols, 1):
            LOGGER.info("Traitement du symbole (%s/%s) : %s", idx, total, symbol)

            last_timestamp = get_last_bar_timestamp(session, symbol, time_frame)
            LOGGER.info("Dernière barre connue | symbol=%s timestamp=%s", symbol, last_timestamp)

            if last_timestamp:
                last_date = last_timestamp.date() if hasattr(last_timestamp, "date") else last_timestamp
                market_date = getLastDateMarche()
                if str(last_date) == str(market_date):
                    LOGGER.info("%s déjà à jour pour la dernière date de marché (%s).", symbol, market_date)
                    continue
                next_start = _format_last_timestamp(last_timestamp)
            else:
                next_start = None

            inserted_count = 0
            while True:
                next_start_call = _increment_start_timestamp(next_start)
                LOGGER.info("Appel Alpaca | symbol=%s start=%s", symbol, next_start_call)
                bars = fetch_bars(symbol, time_frame.api_value, next_start_call)
                LOGGER.info("Réponse Alpaca | symbol=%s bars=%s", symbol, len(bars))

                if not bars:
                    if not symbol_exists_in_stock_bars(session, symbol):
                        LOGGER.warning("Aucun bar trouvé pour %s, mise à jour bars_available=False.", symbol)
                        update_bars_available_false(symbol)
                    break

                inserted_count += insert_bars(session, symbol, bars, time_frame.db_value)
                next_start = bars[-1]["t"]

            LOGGER.info("Import terminé | symbol=%s inserted=%s", symbol, inserted_count)
    finally:
        session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import_alpaca_bars(TimeFrame.ONE_DAY)
    # import_alpaca_bars(TimeFrame.THIRTY_MINS)


if __name__ == "__main__":
    main()
