import logging
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Optional
from uuid import uuid4

import pytz
from dateutil import parser
from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.utils import configure_root_logging, getLastDateMarche, is_trading_day
from database.assets import (
    HISTORY_STATUS_NO_HISTORY,
    HISTORY_STATUS_PENDING,
    HISTORY_STATUS_PROVIDER_ERROR,
    HISTORY_STATUS_READY,
    HISTORY_STATUS_SUSPENDED_OR_STALE,
    mark_symbol_history_ready,
    update_bars_available_false,
    update_symbol_history_status,
)
from database.bar_metadata import TimeFrame, validate_data_integrity_timeframe
from database.connection import SessionLocal, get_sqlalchemy_engine
from service.alpaca.clientAlpaca import AlpacaBarsFetchError, fetch_bars

LOGGER = logging.getLogger(__name__)
TZ_NEW_YORK = pytz.timezone("America/New_York")
DATA_ADJUSTMENT = "split"
MAX_STALENESS_CALENDAR_DAYS = 7
MAX_STALENESS_TRADING_DAYS = 5


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _coerce_to_date(value: Any) -> Any:
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value


def _count_trading_days_between(start_date: Any, end_date: Any) -> Optional[int]:
    if start_date is None or end_date is None or not hasattr(end_date, "__sub__"):
        return None
    if end_date <= start_date:
        return 0
    current = start_date + timedelta(days=1)
    trading_days = 0
    while current <= end_date:
        if is_trading_day(current):
            trading_days += 1
        current += timedelta(days=1)
    return trading_days


def _assess_staleness(last_timestamp: Any, market_date: Any) -> dict[str, Any]:
    last_date = _coerce_to_date(last_timestamp)
    market_day = _coerce_to_date(market_date)
    if last_date is None or market_day is None or not hasattr(market_day, "__sub__"):
        return {"last_date": last_date, "market_date": market_day, "calendar_days": None, "trading_days": None, "is_stale": False}
    try:
        calendar_gap = max(0, int((market_day - last_date).days))
    except Exception:
        return {"last_date": last_date, "market_date": market_day, "calendar_days": None, "trading_days": None, "is_stale": False}
    trading_gap = _count_trading_days_between(last_date, market_day)
    is_stale = False
    if trading_gap is not None:
        is_stale = trading_gap > MAX_STALENESS_TRADING_DAYS
    elif calendar_gap is not None:
        is_stale = calendar_gap > MAX_STALENESS_CALENDAR_DAYS
    return {
        "last_date": last_date,
        "market_date": market_day,
        "calendar_days": calendar_gap,
        "trading_days": trading_gap,
        "is_stale": is_stale,
    }


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


def import_alpaca_bars(time_frame: TimeFrame, symbols: Optional[list[str]] = None) -> dict[str, Any]:
    validate_data_integrity_timeframe(time_frame)
    session = SessionLocal()
    started_at = _utc_now_naive()
    market_date = getLastDateMarche()
    summary = {
        "run_id": _build_run_id("import-bars"),
        "timeframe": time_frame.db_value,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": 0.0,
        "market_date": market_date.isoformat() if hasattr(market_date, "isoformat") else str(market_date),
        "targeted_symbols": 0,
        "existing_history_symbols": 0,
        "first_import_symbols": 0,
        "successful_symbols": 0,
        "failed_symbols": 0,
        "provider_error_symbols": 0,
        "skipped_symbols": 0,
        "up_to_date_symbols": 0,
        "no_data_symbols": 0,
        "stale_symbols": 0,
        "inserted_bars": 0,
        "max_calendar_gap_days": 0,
        "max_trading_gap_days": 0,
        "staleness_calendar_days_threshold": MAX_STALENESS_CALENDAR_DAYS,
        "staleness_trading_days_threshold": MAX_STALENESS_TRADING_DAYS,
        "history_status_counts": {
            HISTORY_STATUS_PENDING: 0,
            HISTORY_STATUS_READY: 0,
            HISTORY_STATUS_NO_HISTORY: 0,
            HISTORY_STATUS_PROVIDER_ERROR: 0,
            HISTORY_STATUS_SUSPENDED_OR_STALE: 0,
        },
    }
    try:
        target_symbols = _normalize_target_symbols(symbols)
        if target_symbols is None:
            target_symbols = get_active_tradable_symbols(session)
            LOGGER.info("Import Alpaca univers complet | timeframe=%s symbols=%s", time_frame.db_value, len(target_symbols))
        else:
            LOGGER.info("Import Alpaca cible | timeframe=%s symbols=%s", time_frame.db_value, ",".join(target_symbols))

        total = len(target_symbols)
        summary["targeted_symbols"] = total
        LOGGER.info(
            "Demarrage import Alpaca | run_id=%s timeframe=%s targeted_symbols=%s adjustment=%s",
            summary["run_id"],
            time_frame.db_value,
            total,
            DATA_ADJUSTMENT,
        )

        for idx, symbol in enumerate(target_symbols, 1):
            LOGGER.info("Traitement du symbole (%s/%s) : %s", idx, total, symbol)
            try:
                symbol_no_data = False
                symbol_skipped = False
                symbol_stale = False
                last_timestamp = get_last_bar_timestamp(session, symbol, time_frame)
                if last_timestamp:
                    summary["existing_history_symbols"] += 1
                else:
                    summary["first_import_symbols"] += 1
                LOGGER.info(
                    "Derniere barre connue | symbol=%s timestamp=%s adjustment=%s",
                    symbol,
                    last_timestamp,
                    DATA_ADJUSTMENT,
                )

                if last_timestamp:
                    last_date = last_timestamp.date() if hasattr(last_timestamp, "date") else last_timestamp
                    if str(last_date) == str(market_date):
                        LOGGER.info("%s deja a jour pour la derniere date de marche (%s).", symbol, market_date)
                        summary["skipped_symbols"] += 1
                        summary["up_to_date_symbols"] += 1
                        symbol_skipped = True
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
                            summary["no_data_symbols"] += 1
                            summary["history_status_counts"][HISTORY_STATUS_NO_HISTORY] += 1
                            symbol_no_data = True
                        else:
                            staleness = _assess_staleness(last_timestamp, market_date)
                            if staleness["calendar_days"] is not None:
                                summary["max_calendar_gap_days"] = max(
                                    int(summary["max_calendar_gap_days"]),
                                    int(staleness["calendar_days"]),
                                )
                            if staleness["trading_days"] is not None:
                                summary["max_trading_gap_days"] = max(
                                    int(summary["max_trading_gap_days"]),
                                    int(staleness["trading_days"]),
                                )
                            if staleness["is_stale"]:
                                update_symbol_history_status(symbol, HISTORY_STATUS_SUSPENDED_OR_STALE)
                                summary["stale_symbols"] += 1
                                summary["history_status_counts"][HISTORY_STATUS_SUSPENDED_OR_STALE] += 1
                                symbol_stale = True
                                LOGGER.warning(
                                    "Symbole stale detecte | symbol=%s last_date=%s market_date=%s trading_gap=%s calendar_gap=%s",
                                    symbol,
                                    staleness["last_date"],
                                    staleness["market_date"],
                                    staleness["trading_days"],
                                    staleness["calendar_days"],
                                )
                            else:
                                summary["skipped_symbols"] += 1
                                symbol_skipped = True
                        break

                    inserted_count += insert_bars(session, symbol, bars, time_frame.db_value)
                    next_start = bars[-1]["t"]

                LOGGER.info("Import termine | symbol=%s inserted=%s adjustment=%s", symbol, inserted_count, DATA_ADJUSTMENT)
                if inserted_count > 0:
                    mark_symbol_history_ready(symbol)
                    summary["successful_symbols"] += 1
                    summary["inserted_bars"] += inserted_count
                    summary["history_status_counts"][HISTORY_STATUS_READY] += 1
                elif not symbol_no_data and not symbol_skipped and not symbol_stale:
                    summary["skipped_symbols"] += 1
            except AlpacaBarsFetchError as exc:
                LOGGER.error(
                    "Incident technique Alpaca | symbol=%s timeframe=%s error=%s | bars_available conserve",
                    symbol,
                    time_frame.db_value,
                    exc,
                )
                update_symbol_history_status(symbol, HISTORY_STATUS_PROVIDER_ERROR)
                summary["failed_symbols"] += 1
                summary["provider_error_symbols"] += 1
                summary["history_status_counts"][HISTORY_STATUS_PROVIDER_ERROR] += 1
                continue
    finally:
        finished_at = _utc_now_naive()
        summary["finished_at"] = finished_at.isoformat(timespec="seconds")
        summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 2)
        LOGGER.info(
            "Resume import Alpaca | run_id=%s timeframe=%s market_date=%s targeted=%s first_import=%s existing_history=%s up_to_date=%s success=%s failed=%s provider_error=%s skipped=%s no_data=%s stale=%s inserted_bars=%s max_calendar_gap=%s max_trading_gap=%s status_breakdown=%s duration_s=%s",
            summary["run_id"],
            summary["timeframe"],
            summary["market_date"],
            summary["targeted_symbols"],
            summary["first_import_symbols"],
            summary["existing_history_symbols"],
            summary["up_to_date_symbols"],
            summary["successful_symbols"],
            summary["failed_symbols"],
            summary["provider_error_symbols"],
            summary["skipped_symbols"],
            summary["no_data_symbols"],
            summary["stale_symbols"],
            summary["inserted_bars"],
            summary["max_calendar_gap_days"],
            summary["max_trading_gap_days"],
            summary["history_status_counts"],
            summary["duration_seconds"],
        )
        session.close()
    return summary


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
