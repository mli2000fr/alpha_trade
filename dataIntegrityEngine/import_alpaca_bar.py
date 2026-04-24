import logging
import math
from collections import Counter
from datetime import timedelta
from functools import lru_cache
from typing import Any, Optional

import pytz
from dateutil import parser
from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.utils import configure_root_logging, getLastDateMarche
from database.assets import update_bars_available_false
from database.bar_metadata import TimeFrame
from database.connection import SessionLocal, get_sqlalchemy_engine
from service.alpaca.clientAlpaca import AlpacaBarsFetchError, fetch_bars

LOGGER = logging.getLogger(__name__)
TZ_NEW_YORK = pytz.timezone("America/New_York")
DATA_ADJUSTMENT = "split"


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
        LOGGER.warning("Valeur non numerique | symbol=%s field=%s value=%r → None", symbol, field, value)
        return None
    if not math.isfinite(f):
        LOGGER.warning("Valeur non finie (inf/nan) | symbol=%s field=%s value=%r → None", symbol, field, f)
        return None
    # DECIMAL(20,8) : partie entière max = 12 chiffres
    if abs(f) > 999_999_999_999.0:
        LOGGER.warning("Valeur hors plage DECIMAL(20,8) | symbol=%s field=%s value=%r → None", symbol, field, f)
        return None
    return f


def _sanitize_non_negative_int(value: Any, field: str, symbol: str) -> Optional[int]:
    if value is None:
        return 0
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        LOGGER.warning("Valeur entiere invalide | symbol=%s field=%s value=%r → None", symbol, field, value)
        return None
    if not math.isfinite(numeric_value):
        LOGGER.warning("Valeur entiere non finie | symbol=%s field=%s value=%r → None", symbol, field, value)
        return None
    if numeric_value < 0:
        LOGGER.warning("Valeur entiere negative | symbol=%s field=%s value=%r → None", symbol, field, value)
        return None
    if not float(numeric_value).is_integer():
        LOGGER.warning("Valeur entiere non entiere | symbol=%s field=%s value=%r → None", symbol, field, value)
        return None
    return int(numeric_value)


def _validate_bar_business_rules(
    *,
    symbol: str,
    timestamp: Any,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: int,
    trade_count: int,
    vwa_price: Optional[float],
) -> Optional[str]:
    if min(open_price, high_price, low_price, close_price) <= 0:
        return "prix_non_positif"
    if high_price < max(open_price, low_price, close_price):
        return "high_inferieur_aux_prix"
    if low_price > min(open_price, high_price, close_price):
        return "low_superieur_aux_prix"
    if volume < 0:
        return "volume_negatif"
    if trade_count < 0:
        return "trade_count_negatif"
    if vwa_price is not None and vwa_price <= 0:
        return "vwap_non_positif"
    return None


def _build_bar_records(symbol: str, bars: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
    records = []
    skip_reasons: Counter[str] = Counter()
    for bar in bars:
        timestamp = bar.get("t")
        if timestamp is None:
            skip_reasons["timestamp_absent"] += 1
            LOGGER.warning("Barre ignoree (timestamp absent) | symbol=%s raw=%r", symbol, bar)
            continue

        open_price  = _sanitize_price(bar.get("o"),  "open_price",  symbol)
        high_price  = _sanitize_price(bar.get("h"),  "high_price",  symbol)
        low_price   = _sanitize_price(bar.get("l"),  "low_price",   symbol)
        close_price = _sanitize_price(bar.get("c"),  "close_price", symbol)
        vwa_price   = _sanitize_price(bar.get("vw"), "vwa_price",   symbol)
        volume = _sanitize_non_negative_int(bar.get("v"), "volume", symbol)
        trade_count = _sanitize_non_negative_int(bar.get("n"), "trade_count", symbol)

        # Ignorer la barre si un prix obligatoire est invalide (NOT NULL en DB)
        if None in (open_price, high_price, low_price, close_price, volume, trade_count):
            skip_reasons["champ_obligatoire_invalide"] += 1
            LOGGER.warning(
                "Barre ignoree (champ obligatoire invalide) | symbol=%s timestamp=%s o=%s h=%s l=%s c=%s v=%s n=%s",
                symbol, timestamp, bar.get("o"), bar.get("h"), bar.get("l"), bar.get("c"), bar.get("v"), bar.get("n"),
            )
            continue

        rejection_reason = _validate_bar_business_rules(
            symbol=symbol,
            timestamp=timestamp,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume,
            trade_count=trade_count,
            vwa_price=vwa_price,
        )
        if rejection_reason is not None:
            skip_reasons[rejection_reason] += 1
            LOGGER.warning(
                "Barre ignoree (validation metier) | symbol=%s timestamp=%s reason=%s o=%s h=%s l=%s c=%s v=%s n=%s vw=%s",
                symbol,
                timestamp,
                rejection_reason,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                trade_count,
                vwa_price,
            )
            continue

        records.append({
            "symbol":      symbol,
            "timestamp":   _normalize_bar_timestamp(timestamp),
            "timeframe":   timeframe,
            "open_price":  open_price,
            "high_price":  high_price,
            "low_price":   low_price,
            "close_price": close_price,
            "volume":      volume,
            "trade_count": trade_count,
            "vwa_price":   vwa_price,
        })

    if skip_reasons:
        LOGGER.warning(
            "Barres ignorees au total | symbol=%s skipped=%s total=%s reasons=%s",
            symbol,
            sum(skip_reasons.values()),
            len(bars),
            dict(skip_reasons),
        )
    return records


def insert_bars(session, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int:
    if not bars:
        return 0

    _, stock_bars = _get_tables()
    records = _build_bar_records(symbol, bars, timeframe)

    if not records:
        LOGGER.warning("insert_bars | aucune barre valide apres sanitization | symbol=%s total_brut=%s", symbol, len(bars))
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
        LOGGER.error("Echec insert_bars | symbol=%s timeframe=%s bars=%s", symbol, timeframe, len(bars))
        raise
    return len(records)


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
            LOGGER.info("Import Alpaca cible | timeframe=%s symbols=%s", time_frame.db_value, ",".join(target_symbols))

        total = len(target_symbols)

        for idx, symbol in enumerate(target_symbols, 1):
            LOGGER.info("Traitement du symbole (%s/%s) : %s", idx, total, symbol)
            try:
                last_timestamp = get_last_bar_timestamp(session, symbol, time_frame)
                LOGGER.info(
                    "Derniere barre connue | symbol=%s timestamp=%s adjustment=%s",
                    symbol,
                    last_timestamp,
                    DATA_ADJUSTMENT,
                )

                if last_timestamp:
                    last_date = last_timestamp.date() if hasattr(last_timestamp, "date") else last_timestamp
                    market_date = getLastDateMarche()
                    if str(last_date) == str(market_date):
                        LOGGER.info("%s deja a jour pour la derniere date de marche (%s).", symbol, market_date)
                        continue
                    next_start = _format_last_timestamp(last_timestamp)
                else:
                    next_start = None

                inserted_count = 0
                while True:
                    next_start_call = _increment_start_timestamp(next_start)
                    LOGGER.info("Appel Alpaca | symbol=%s start=%s adjustment=%s", symbol, next_start_call, DATA_ADJUSTMENT)
                    bars = fetch_bars(symbol, time_frame.api_value, next_start_call)
                    LOGGER.info("Reponse Alpaca | symbol=%s bars=%s", symbol, len(bars))

                    if not bars:
                        if not symbol_exists_in_stock_bars(session, symbol):
                            LOGGER.warning(
                                "Aucun bar confirme par Alpaca pour %s, mise a jour bars_available=False.",
                                symbol,
                            )
                            update_bars_available_false(symbol)
                        break

                    inserted_count += insert_bars(session, symbol, bars, time_frame.db_value)
                    next_start = bars[-1]["t"]

                LOGGER.info("Import termine | symbol=%s inserted=%s adjustment=%s", symbol, inserted_count, DATA_ADJUSTMENT)
            except AlpacaBarsFetchError as exc:
                LOGGER.error(
                    "Incident technique Alpaca | symbol=%s timeframe=%s error=%s | bars_available conserve",
                    symbol,
                    time_frame.db_value,
                    exc,
                )
                continue
    finally:
        session.close()


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/import_alpaca_bar.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    import_alpaca_bars(TimeFrame.ONE_DAY)
    # import_alpaca_bars(TimeFrame.THIRTY_MINS)


if __name__ == "__main__":
    main()
