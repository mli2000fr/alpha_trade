"""Sprint S7 — Repository SQL pour ``AlphaScanner``.

Fonctions libres prenant ``engine + config`` en paramètres ; AlphaScanner
les délègue via composition. Aucune logique métier de scoring ici, juste
les requêtes SELECT / UPDATE et l'introspection schéma.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from selector.config import (
    DATA_QUALITY_MODE_BLOCK,
    PRICE_COLUMNS,
)
from selector.filters import ELIGIBLE_HISTORY_STATUSES, METADATA_COLUMNS
from selector.ranking import PERSISTED_SELECTOR_SCORE_COLUMNS, SCORE_COLUMNS

if TYPE_CHECKING:
    from selector.config import AlphaScannerConfig

LOGGER = logging.getLogger("selector.alpha_scanner")

DATA_QUALITY_QUOTE_MAX_AGE_DAYS = 5
DEFAULT_SELECTOR_SCORE_TABLE_COLUMNS = {
    "symbol",
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
    "is_candidate",
    "last_updated_scan",
    "candidate_rank",
    "raw_final_score",
    "normalized_total_score",
    "normalized_rsi",
    "total_score_neutralized",
    "relative_strength_index_neutralized",
    "trend_vcp_component",
    "total_score_component",
    "rsi_component",
    "atr_pct_20",
    "weekly_trend_score",
    "high_52w_proximity",
    "volatility_ratio",
    "selector_signal_mode",
    "selection_explanation",
}
RESET_NULL_COLUMNS = [
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "candidate_rank",
    "raw_final_score",
    "normalized_total_score",
    "normalized_rsi",
    "total_score_neutralized",
    "relative_strength_index_neutralized",
    "trend_vcp_component",
    "total_score_component",
    "rsi_component",
    "atr_pct_20",
    "weekly_trend_score",
    "high_52w_proximity",
    "volatility_ratio",
    "selector_signal_mode",
    "selection_explanation",
]
SNAPSHOT_NUMERIC_COLUMNS = [
    "trend_score",
    "vcp_score",
    "final_score",
    "market_cap",
    "beta_126",
    "spread_bps",
    "candidate_rank",
    "raw_final_score",
    "normalized_total_score",
    "normalized_rsi",
    "total_score_neutralized",
    "relative_strength_index_neutralized",
    "trend_vcp_component",
    "total_score_component",
    "rsi_component",
    "atr_pct_20",
    "weekly_trend_score",
    "high_52w_proximity",
    "volatility_ratio",
]
SNAPSHOT_TEXT_COLUMNS = ["selector_signal_mode", "selection_explanation"]
PRESELECTION_AUDIT_SAMPLE_LIMIT = 5
PRESELECTION_REASON_LABELS = {
    "metadata_missing": "metadata absente",
    "non_us_equity": "asset_class non us_equity",
    "inactive": "instrument inactif",
    "not_tradable": "instrument non tradable",
    "bars_unavailable": "bars indisponibles",
    "history_status_blocked": "history_status bloqué",
    "insufficient_history": "historique insuffisant",
    "below_min_close": "prix sous le seuil",
    "below_liquidity_threshold": "liquidité 20j insuffisante",
}


def _build_data_quality_check_payload(
    *,
    enabled: bool,
    fallback_mode: str,
    filter_key: str,
    healthy: bool,
    reason: str,
    recommended_action: str,
    **extra: object,
) -> dict[str, object]:
    status = "ok" if healthy else "blocked" if fallback_mode == DATA_QUALITY_MODE_BLOCK else "warning"
    return {
        "enabled": enabled,
        "status": status,
        "reason": reason,
        "filter_key": filter_key,
        "configured_fallback_mode": fallback_mode,
        "applied_filter_fallback": "none"
        if healthy
        else "block"
        if fallback_mode == DATA_QUALITY_MODE_BLOCK
        else "skip_filter",
        "recommended_action": recommended_action,
        **extra,
    }


def _has_table(engine: Engine, table_name: str) -> bool:
    try:
        return bool(inspect(engine).has_table(table_name))
    except Exception:
        LOGGER.debug("Inspection table %s indisponible.", table_name, exc_info=True)
        return False


def get_table_columns(
    engine: Engine,
    table_name: str,
    *,
    fallback_columns: set[str] | None = None,
) -> set[str]:
    try:
        return {str(column.get("name")) for column in inspect(engine).get_columns(table_name)}
    except Exception:
        LOGGER.debug("Inspection colonnes %s indisponible.", table_name, exc_info=True)
        return set(fallback_columns or set())


def _read_scalar_date(
    engine: Engine,
    stmt,
    params: dict[str, object] | None = None,
) -> date | None:
    try:
        with engine.connect() as conn:
            value = conn.execute(stmt, params or {}).scalar()
    except SQLAlchemyError:
        LOGGER.debug("Lecture scalaire date indisponible pour le preflight selector.", exc_info=True)
        return None
    if value is None:
        return None
    timestamp = pd.to_datetime(value, errors="coerce", utc=False)
    if pd.isna(timestamp):
        return None
    return timestamp.date()


def build_data_quality_gate(
    engine: Engine,
    config: AlphaScannerConfig,
    *,
    reference_date: date | None = None,
) -> dict[str, object]:
    effective_reference_date = reference_date or date.today()
    checks = {
        "quotes": _build_quotes_quality_check(engine, config, effective_reference_date),
        "earnings": _build_earnings_quality_check(engine, config, effective_reference_date),
        "market_cap": _build_market_cap_quality_check(engine, config, effective_reference_date),
    }
    blocking_checks = [name for name, payload in checks.items() if payload.get("status") == "blocked"]
    warning_checks = [name for name, payload in checks.items() if payload.get("status") == "warning"]
    skipped_filters = [
        str(payload.get("filter_key"))
        for payload in checks.values()
        if payload.get("applied_filter_fallback") == "skip_filter"
    ]
    return {
        "status": "blocked" if blocking_checks else "warning" if warning_checks else "ok",
        "reference_date": effective_reference_date.isoformat(),
        "blocking_checks": blocking_checks,
        "warning_checks": warning_checks,
        "skipped_filters": skipped_filters,
        "checks": checks,
    }


def _build_quotes_quality_check(
    engine: Engine,
    config: AlphaScannerConfig,
    reference_date: date,
) -> dict[str, object]:
    if config.max_spread_bps is None:
        return _build_data_quality_check_payload(
            enabled=False,
            fallback_mode=config.spread_data_quality_mode,
            filter_key="spread",
            healthy=True,
            reason="spread_filter_disabled",
            recommended_action="none",
        ) | {"status": "disabled"}
    if not _has_table(engine, "stock_quote_snapshots"):
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.spread_data_quality_mode,
            filter_key="spread",
            healthy=False,
            reason="quotes_table_missing",
            recommended_action="refresh_stock_quote_snapshots_or_disable_spread_filter",
            max_age_days=DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
        )
    latest_quote_date = _read_scalar_date(
        engine,
        text("SELECT MAX(quote_date) FROM stock_quote_snapshots WHERE quote_date <= :reference_date"),
        {"reference_date": reference_date},
    )
    if latest_quote_date is None:
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.spread_data_quality_mode,
            filter_key="spread",
            healthy=False,
            reason="quotes_unavailable",
            recommended_action="refresh_stock_quote_snapshots_or_disable_spread_filter",
            max_age_days=DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
        )
    age_days = max((reference_date - latest_quote_date).days, 0)
    return _build_data_quality_check_payload(
        enabled=True,
        fallback_mode=config.spread_data_quality_mode,
        filter_key="spread",
        healthy=age_days <= DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
        reason="ok" if age_days <= DATA_QUALITY_QUOTE_MAX_AGE_DAYS else "quotes_stale",
        recommended_action="none"
        if age_days <= DATA_QUALITY_QUOTE_MAX_AGE_DAYS
        else "refresh_stock_quote_snapshots_or_disable_spread_filter",
        latest_quote_date=latest_quote_date.isoformat(),
        age_days=age_days,
        max_age_days=DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
    )


def _build_earnings_quality_check(
    engine: Engine,
    config: AlphaScannerConfig,
    reference_date: date,
) -> dict[str, object]:
    if config.earnings_blackout_days is None:
        return _build_data_quality_check_payload(
            enabled=False,
            fallback_mode=config.earnings_data_quality_mode,
            filter_key="earnings_blackout",
            healthy=True,
            reason="earnings_filter_disabled",
            recommended_action="none",
        ) | {"status": "disabled"}
    required_horizon_days = max(int(config.earnings_blackout_days), 1)
    required_until = reference_date + timedelta(days=required_horizon_days)
    if not _has_table(engine, "stock_earnings_calendar"):
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.earnings_data_quality_mode,
            filter_key="earnings_blackout",
            healthy=False,
            reason="earnings_table_missing",
            recommended_action="refresh_stock_earnings_calendar_or_disable_earnings_filter",
            required_until=required_until.isoformat(),
            required_horizon_days=required_horizon_days,
        )
    latest_earnings_date = _read_scalar_date(
        engine,
        text("SELECT MAX(earnings_date) FROM stock_earnings_calendar"),
    )
    next_earnings_date = _read_scalar_date(
        engine,
        text("SELECT MIN(earnings_date) FROM stock_earnings_calendar WHERE earnings_date >= :reference_date"),
        {"reference_date": reference_date},
    )
    if latest_earnings_date is None:
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.earnings_data_quality_mode,
            filter_key="earnings_blackout",
            healthy=False,
            reason="earnings_unavailable",
            recommended_action="refresh_stock_earnings_calendar_or_disable_earnings_filter",
            required_until=required_until.isoformat(),
            required_horizon_days=required_horizon_days,
        )
    if next_earnings_date is None:
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.earnings_data_quality_mode,
            filter_key="earnings_blackout",
            healthy=False,
            reason="earnings_no_future_coverage",
            recommended_action="refresh_stock_earnings_calendar_or_disable_earnings_filter",
            latest_earnings_date=latest_earnings_date.isoformat(),
            required_until=required_until.isoformat(),
            required_horizon_days=required_horizon_days,
        )
    return _build_data_quality_check_payload(
        enabled=True,
        fallback_mode=config.earnings_data_quality_mode,
        filter_key="earnings_blackout",
        healthy=latest_earnings_date >= required_until,
        reason="ok" if latest_earnings_date >= required_until else "earnings_horizon_too_short",
        recommended_action="none"
        if latest_earnings_date >= required_until
        else "refresh_stock_earnings_calendar_or_disable_earnings_filter",
        next_earnings_date=next_earnings_date.isoformat(),
        latest_earnings_date=latest_earnings_date.isoformat(),
        required_until=required_until.isoformat(),
        required_horizon_days=required_horizon_days,
    )


def _build_market_cap_quality_check(
    engine: Engine,
    config: AlphaScannerConfig,
    reference_date: date,
) -> dict[str, object]:
    if config.min_market_cap is None or config.market_cap_max_age_days is None:
        return _build_data_quality_check_payload(
            enabled=False,
            fallback_mode=config.market_cap_filter_data_quality_mode,
            filter_key="market_cap_ttl",
            healthy=True,
            reason="market_cap_ttl_filter_disabled",
            recommended_action="none",
        ) | {"status": "disabled"}
    if not _has_table(engine, "stock_metadata"):
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.market_cap_filter_data_quality_mode,
            filter_key="market_cap_ttl",
            healthy=False,
            reason="stock_metadata_missing",
            recommended_action="refresh_stock_metadata_or_disable_market_cap_ttl_filter",
            max_age_days=int(config.market_cap_max_age_days),
        )
    metadata_columns = get_stock_metadata_columns(engine)
    if "market_cap_refreshed_at" not in metadata_columns:
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.market_cap_filter_data_quality_mode,
            filter_key="market_cap_ttl",
            healthy=False,
            reason="market_cap_refreshed_at_missing",
            recommended_action="backfill_market_cap_refreshed_at_or_disable_market_cap_ttl_filter",
            max_age_days=int(config.market_cap_max_age_days),
        )
    latest_refresh_date = _read_scalar_date(
        engine,
        text("SELECT MAX(market_cap_refreshed_at) FROM stock_metadata WHERE market_cap_refreshed_at IS NOT NULL"),
    )
    if latest_refresh_date is None:
        return _build_data_quality_check_payload(
            enabled=True,
            fallback_mode=config.market_cap_filter_data_quality_mode,
            filter_key="market_cap_ttl",
            healthy=False,
            reason="market_cap_refresh_unavailable",
            recommended_action="refresh_stock_metadata_or_disable_market_cap_ttl_filter",
            max_age_days=int(config.market_cap_max_age_days),
        )
    age_days = max((reference_date - latest_refresh_date).days, 0)
    max_age_days = int(config.market_cap_max_age_days)
    return _build_data_quality_check_payload(
        enabled=True,
        fallback_mode=config.market_cap_filter_data_quality_mode,
        filter_key="market_cap_ttl",
        healthy=age_days <= max_age_days,
        reason="ok" if age_days <= max_age_days else "market_cap_refresh_stale",
        recommended_action="none"
        if age_days <= max_age_days
        else "refresh_stock_metadata_or_disable_market_cap_ttl_filter",
        latest_refresh_date=latest_refresh_date.isoformat(),
        age_days=age_days,
        max_age_days=max_age_days,
    )


def get_stock_metadata_columns(engine: Engine) -> set[str]:
    try:
        return {
            str(column.get("name"))
            for column in inspect(engine).get_columns("stock_metadata")
        }
    except Exception:
        LOGGER.warning("Inspection stock_metadata indisponible; fallback sans history_status explicite.")
        return set()


def get_stock_quote_snapshots_columns(engine: Engine) -> set[str]:
    try:
        return {
            str(column.get("name"))
            for column in inspect(engine).get_columns("stock_quote_snapshots")
        }
    except Exception:
        return set()


def fetch_market_data(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    LOGGER.debug("Chargement market data | symboles=%s", len(symbols))
    stmt = text(
        f"""
        SELECT symbol, date, close, volume, high, low
        FROM {config.price_table}
        WHERE symbol IN :symbols
        ORDER BY symbol, date
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        market_data = pd.read_sql_query(
            stmt,
            engine,
            params=cast(dict[str, Any], {"symbols": list(symbols)}),
        )
    except SQLAlchemyError as exc:
        LOGGER.exception("Echec lecture %s pour %s symboles.", config.price_table, len(symbols))
        raise RuntimeError("Impossible de charger les données marché.") from exc
    if market_data.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    market_data["date"] = pd.to_datetime(market_data["date"], utc=False)
    return market_data


def fetch_scores(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str]) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=SCORE_COLUMNS)
    LOGGER.debug("Chargement scores auxiliaires | symboles=%s", len(symbols))
    stmt = text(
        f"""
        SELECT symbol,
               liquidity_val,
               relative_strength_index,
               total_score,
               sector,
               market_cap,
               beta_126,
               spread_bps,
               earnings_date,
               days_to_earnings,
               earnings_blackout,
               sanitizer_status,
               anomaly_count,
               missing_days_count
        FROM {config.score_table}
        WHERE symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        scores = pd.read_sql_query(
            stmt,
            engine,
            params=cast(dict[str, Any], {"symbols": list(symbols)}),
        )
    except SQLAlchemyError:
        LOGGER.warning(
            "Lecture auxiliaire %s indisponible; poursuite avec facteurs recalcules seulement.",
            config.score_table,
        )
        return pd.DataFrame(columns=SCORE_COLUMNS)
    return scores if not scores.empty else pd.DataFrame(columns=SCORE_COLUMNS)


def fetch_instrument_metadata(
    engine: Engine,
    available_columns: set[str],
    symbols: Sequence[str],
) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=METADATA_COLUMNS)
    select_columns = [
        "symbol",
        "company_name",
        "asset_class",
        "status",
        "tradable",
        "bars_available",
    ]
    if "history_status" in available_columns:
        select_columns.append("history_status")
    if "sector" in available_columns:
        select_columns.append("sector")
    if "market_cap" in available_columns:
        select_columns.append("market_cap")
    # Phase 3.3.d — TTL filtre market_cap basé sur la fraîcheur SQL.
    if "market_cap_refreshed_at" in available_columns:
        select_columns.append("market_cap_refreshed_at")

    stmt = text(
        f"""
        SELECT {', '.join(select_columns)}
        FROM stock_metadata
        WHERE symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        metadata_df = pd.read_sql_query(
            stmt,
            engine,
            params=cast(dict[str, Any], {"symbols": list(symbols)}),
        )
    except SQLAlchemyError:
        LOGGER.warning("Lecture stock_metadata indisponible; impossibilite de filtrer explicitement les ETFs.")
        return pd.DataFrame(columns=METADATA_COLUMNS)
    if metadata_df.empty:
        return pd.DataFrame(columns=METADATA_COLUMNS)
    for column in METADATA_COLUMNS:
        if column not in metadata_df.columns:
            metadata_df[column] = pd.NA
    return metadata_df.loc[:, METADATA_COLUMNS]


def load_benchmark_returns(
    engine: Engine, config: AlphaScannerConfig, start_date: date, end_date: date
) -> pd.DataFrame:
    stmt = text(
        f"""
        SELECT date, close
        FROM {config.price_table}
        WHERE symbol = 'SPY'
          AND date BETWEEN :start_date AND :end_date
        ORDER BY date
        """
    )
    try:
        benchmark_df = pd.read_sql_query(
            stmt,
            engine,
            params={"start_date": start_date, "end_date": end_date},
        )
    except SQLAlchemyError:
        LOGGER.warning("Lecture benchmark SPY indisponible pour le calcul du beta.")
        return pd.DataFrame(columns=["date", "spy_return"])
    if benchmark_df.empty:
        return pd.DataFrame(columns=["date", "spy_return"])
    benchmark_df["date"] = pd.to_datetime(benchmark_df["date"], utc=False)
    benchmark_df["close"] = pd.to_numeric(benchmark_df["close"], errors="coerce")
    benchmark_df["spy_return"] = benchmark_df["close"].pct_change()
    return benchmark_df[["date", "spy_return"]].dropna().reset_index(drop=True)


def fetch_quote_snapshots(
    engine: Engine,
    available_columns: set[str],
    symbols: Sequence[str],
    *,
    reference_date: date | None = None,
) -> pd.DataFrame:
    select_extra: list[str] = []
    if "quote_timestamp" in available_columns:
        select_extra.append("q.quote_timestamp")
    if "bid_size" in available_columns:
        select_extra.append("q.bid_size")
    if "ask_size" in available_columns:
        select_extra.append("q.ask_size")
    empty_columns = [
        "symbol",
        "quote_date",
        "quote_timestamp",
        "spread_bps",
        "bid_size",
        "ask_size",
        "quote_source",
        "quote_age_days",
        "quote_size_quality",
    ]
    if not symbols:
        return pd.DataFrame(columns=empty_columns)

    effective_reference_date = reference_date or date.today()
    select_clause = "q.symbol, q.quote_date, q.spread_bps"
    if select_extra:
        select_clause = select_clause + ", " + ", ".join(select_extra)

    stmt = text(
        f"""
        SELECT {select_clause}
        FROM stock_quote_snapshots q
        INNER JOIN (
            SELECT symbol, MAX(quote_date) AS max_quote_date
            FROM stock_quote_snapshots
            WHERE symbol IN :symbols
              AND quote_date <= :reference_date
            GROUP BY symbol
        ) latest ON latest.symbol = q.symbol AND latest.max_quote_date = q.quote_date
        WHERE q.symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        quotes_df = pd.read_sql_query(
            stmt,
            engine,
            params={"symbols": list(symbols), "reference_date": effective_reference_date},
        )
    except SQLAlchemyError:
        LOGGER.warning("Lecture stock_quote_snapshots indisponible; filtre de spread desactive.")
        return pd.DataFrame(columns=empty_columns)
    normalized_quotes = quotes_df.copy()
    for column in empty_columns:
        if column not in normalized_quotes.columns:
            normalized_quotes[column] = pd.NA
    if normalized_quotes.empty:
        return pd.DataFrame(columns=empty_columns)
    quote_dates = pd.to_datetime(normalized_quotes["quote_date"], errors="coerce", utc=False)
    bid_size = pd.to_numeric(normalized_quotes["bid_size"], errors="coerce")
    ask_size = pd.to_numeric(normalized_quotes["ask_size"], errors="coerce")
    normalized_quotes["quote_age_days"] = (
        pd.Timestamp(effective_reference_date).normalize() - quote_dates.dt.normalize()
    ).dt.days.where(quote_dates.notna(), pd.NA)
    normalized_quotes["quote_source"] = pd.Series("alpaca_quote_snapshots", index=normalized_quotes.index, dtype="object")
    normalized_quotes.loc[
        normalized_quotes["quote_age_days"].fillna(9999).astype(float) <= 0,
        "quote_source",
    ] = "alpaca_latest_snapshot"
    normalized_quotes.loc[
        normalized_quotes["quote_age_days"].fillna(9999).astype(float) > 0,
        "quote_source",
    ] = "alpaca_historical_snapshot"
    normalized_quotes["quote_size_quality"] = pd.Series("missing", index=normalized_quotes.index, dtype="object")
    two_sided_mask = bid_size.gt(0) & ask_size.gt(0)
    normalized_quotes.loc[two_sided_mask, "quote_size_quality"] = "thin"
    normalized_quotes.loc[
        two_sided_mask & bid_size.ge(100) & ask_size.ge(100),
        "quote_size_quality",
    ] = "sufficient"
    normalized_quotes.loc[
        (bid_size.gt(0) ^ ask_size.gt(0)),
        "quote_size_quality",
    ] = "partial"
    return normalized_quotes.loc[:, empty_columns]


def fetch_next_earnings(
    engine: Engine,
    config: AlphaScannerConfig,
    symbols: Sequence[str],
    *,
    reference_date: date | None = None,
) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])
    effective_reference_date = reference_date or date.today()
    stmt = text(
        """
        SELECT e.symbol,
               e.earnings_date
        FROM stock_earnings_calendar e
        INNER JOIN (
            SELECT symbol, MIN(earnings_date) AS next_earnings_date
            FROM stock_earnings_calendar
            WHERE symbol IN :symbols
              AND earnings_date >= :reference_date
            GROUP BY symbol
        ) next_e ON next_e.symbol = e.symbol AND next_e.next_earnings_date = e.earnings_date
        WHERE e.symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
    try:
        earnings_df = pd.read_sql_query(
            stmt,
            engine,
            params={"symbols": list(symbols), "reference_date": effective_reference_date},
        )
    except SQLAlchemyError:
        LOGGER.warning("Lecture stock_earnings_calendar indisponible; filtre earnings blackout desactive.")
        return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])
    if earnings_df.empty:
        return pd.DataFrame(columns=["symbol", "earnings_date", "days_to_earnings", "earnings_blackout"])
    earnings_timestamps = pd.to_datetime(earnings_df["earnings_date"], utc=False)
    earnings_df["earnings_date"] = earnings_timestamps.dt.date
    days_to_earnings = (earnings_timestamps - pd.Timestamp(effective_reference_date)).dt.days
    earnings_df["days_to_earnings"] = pd.Series(days_to_earnings, index=earnings_df.index)
    blackout_days = config.earnings_blackout_days if config.earnings_blackout_days is not None else 0
    earnings_df["earnings_blackout"] = (
        pd.Series(pd.to_numeric(earnings_df["days_to_earnings"], errors="coerce"), index=earnings_df.index)
        .fillna(9999)
        .astype(int)
        <= blackout_days
    ).astype(int)
    return earnings_df


def _classify_preselection_rejection_reason(
    row: Mapping[str, object],
    config: AlphaScannerConfig,
    *,
    history_status_enabled: bool,
) -> str | None:
    metadata_symbol = str(row.get("metadata_symbol") or "").strip()
    if not metadata_symbol:
        return "metadata_missing"
    asset_class = str(row.get("asset_class") or "").strip().lower()
    if asset_class != "us_equity":
        return "non_us_equity"
    instrument_status = str(row.get("status") or "").strip().lower()
    if instrument_status != "active":
        return "inactive"
    tradable = row.get("tradable")
    if pd.isna(tradable) or not bool(tradable):
        return "not_tradable"
    bars_available = row.get("bars_available")
    if pd.isna(bars_available) or not bool(bars_available):
        return "bars_unavailable"
    if history_status_enabled:
        history_status = str(row.get("history_status") or "").strip().lower()
        if history_status and history_status not in ELIGIBLE_HISTORY_STATUSES:
            return "history_status_blocked"

    history_days_value = pd.to_numeric(row.get("history_days"), errors="coerce")
    if pd.isna(history_days_value) or float(history_days_value) < float(config.min_history_days):
        return "insufficient_history"
    latest_close_value = pd.to_numeric(row.get("latest_close"), errors="coerce")
    if pd.isna(latest_close_value) or float(latest_close_value) <= float(config.min_close):
        return "below_min_close"
    avg_dollar_volume_value = pd.to_numeric(row.get("avg_dollar_volume_20d"), errors="coerce")
    if pd.isna(avg_dollar_volume_value) or float(avg_dollar_volume_value) <= float(config.liquidity_threshold):
        return "below_liquidity_threshold"
    return None


def build_preselection_rejection_audit(
    engine: Engine,
    config: AlphaScannerConfig,
    metadata_columns: set[str],
    *,
    sample_limit: int = PRESELECTION_AUDIT_SAMPLE_LIMIT,
) -> dict[str, object]:
    if not _has_table(engine, config.price_table):
        return {
            "status": "unavailable",
            "reason": "price_table_missing",
            "price_table": config.price_table,
        }

    history_status_enabled = "history_status" in metadata_columns
    history_status_select = "sm.history_status" if history_status_enabled else "NULL AS history_status"
    stmt = text(
        f"""
        WITH ranked AS (
            SELECT symbol,
                   date,
                   close,
                   volume,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM {config.price_table}
        ), aggregated AS (
            SELECT symbol,
                   COUNT(*) AS history_days,
                   MAX(CASE WHEN rn = 1 THEN close END) AS latest_close,
                   AVG(CASE WHEN rn <= :liquidity_lookback_days THEN close * volume END) AS avg_dollar_volume_20d
            FROM ranked
            GROUP BY symbol
        )
        SELECT agg.symbol,
               agg.history_days,
               agg.latest_close,
               agg.avg_dollar_volume_20d,
               sm.symbol AS metadata_symbol,
               sm.asset_class,
               sm.status,
               sm.tradable,
               sm.bars_available,
               {history_status_select}
        FROM aggregated agg
        LEFT JOIN stock_metadata sm ON sm.symbol = agg.symbol
        ORDER BY agg.symbol
        """
    )
    try:
        audit_df = pd.read_sql_query(
            stmt,
            engine,
            params={"liquidity_lookback_days": config.liquidity_lookback_days},
        )
    except SQLAlchemyError:
        LOGGER.warning("Audit des rejets de pré-sélection indisponible.", exc_info=True)
        return {
            "status": "unavailable",
            "reason": "preselection_audit_query_failed",
            "price_table": config.price_table,
        }

    if audit_df.empty:
        return {
            "status": "ok",
            "input_symbols": 0,
            "eligible_symbols": 0,
            "rejected_symbols": 0,
            "eligible_ratio": 0.0,
            "reason_counts": {},
            "sample_symbols_by_reason": {},
            "top_reasons": [],
        }

    reason_counts: Counter[str] = Counter()
    sample_symbols_by_reason: dict[str, list[str]] = {}
    eligible_symbols = 0
    safe_sample_limit = max(int(sample_limit), 1)
    for row in audit_df.to_dict(orient="records"):
        reason = _classify_preselection_rejection_reason(
            row,
            config,
            history_status_enabled=history_status_enabled,
        )
        if reason is None:
            eligible_symbols += 1
            continue
        reason_counts[reason] += 1
        symbol = str(row.get("symbol") or "").strip()
        if not symbol:
            continue
        samples = sample_symbols_by_reason.setdefault(reason, [])
        if symbol not in samples and len(samples) < safe_sample_limit:
            samples.append(symbol)

    top_reasons = [
        {
            "reason": reason,
            "label": PRESELECTION_REASON_LABELS.get(reason, reason),
            "count": int(count),
            "sample_symbols": sample_symbols_by_reason.get(reason, []),
        }
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    total_symbols = int(len(audit_df))
    rejected_symbols = int(sum(reason_counts.values()))
    return {
        "status": "ok",
        "input_symbols": total_symbols,
        "eligible_symbols": int(eligible_symbols),
        "rejected_symbols": rejected_symbols,
        "eligible_ratio": round((eligible_symbols / total_symbols), 4) if total_symbols > 0 else 0.0,
        "reason_counts": dict(sorted(reason_counts.items())),
        "sample_symbols_by_reason": sample_symbols_by_reason,
        "top_reasons": top_reasons,
        "sample_limit": safe_sample_limit,
    }


def iter_eligible_symbol_chunks(
    engine: Engine,
    config: AlphaScannerConfig,
    metadata_columns: set[str],
) -> Iterator[list[str]]:
    """Filtre SQL brut: liquidité 20j, close > min_close, historique >= min_history_days."""
    offset = 0
    history_status_filter = ""
    if "history_status" in metadata_columns:
        eligible_statuses = ", ".join(f"'{status}'" for status in sorted(ELIGIBLE_HISTORY_STATUSES))
        history_status_filter = f"""
              AND (
                    sm.history_status IS NULL
                 OR TRIM(sm.history_status) = ''
                 OR LOWER(TRIM(sm.history_status)) IN ({eligible_statuses})
              )
        """
    stmt = text(
        f"""
        WITH ranked AS (
            SELECT symbol,
                   date,
                   close,
                   volume,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM {config.price_table}
        ), eligible AS (
            SELECT r.symbol
            FROM ranked r
            INNER JOIN stock_metadata sm ON sm.symbol = r.symbol
            WHERE sm.asset_class = 'us_equity'
              AND sm.tradable    = 1
              AND sm.status      = 'active'
              AND sm.bars_available = 1
              {history_status_filter}
            GROUP BY r.symbol
            HAVING COUNT(*) >= :min_history_days
               AND MAX(CASE WHEN rn = 1 THEN close END) > :min_close
               AND AVG(CASE WHEN rn <= :liquidity_lookback_days THEN close * volume END) > :liquidity_threshold
        )
        SELECT symbol
        FROM eligible
        ORDER BY symbol
        LIMIT :limit OFFSET :offset
        """
    )
    while True:
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    stmt,
                    {
                        "min_history_days": config.min_history_days,
                        "min_close": config.min_close,
                        "liquidity_lookback_days": config.liquidity_lookback_days,
                        "liquidity_threshold": config.liquidity_threshold,
                        "limit": config.chunk_size,
                        "offset": offset,
                    },
                ).fetchall()
        except SQLAlchemyError as exc:
            LOGGER.exception("Echec de la preselection SQL sur %s.", config.price_table)
            raise RuntimeError("Impossible de présélectionner les symboles.") from exc

        symbols = [str(row[0]) for row in rows]
        if not symbols:
            break
        LOGGER.info(
            "Preselection SQL | offset=%s chunk_size=%s retournes=%s",
            offset,
            config.chunk_size,
            len(symbols),
        )
        yield symbols
        offset += config.chunk_size


def reset_selector_outputs(engine: Engine, config: AlphaScannerConfig) -> None:
    available_columns = get_table_columns(
        engine,
        config.score_table,
        fallback_columns=DEFAULT_SELECTOR_SCORE_TABLE_COLUMNS,
    )
    assignments: list[str] = []
    assignments.extend(f"{column} = NULL" for column in RESET_NULL_COLUMNS if column in available_columns)
    if "earnings_blackout" in available_columns:
        assignments.append("earnings_blackout = 0")
    if "is_candidate" in available_columns:
        assignments.append("is_candidate = 0")
    if not assignments:
        LOGGER.info("Reset selector saute | table=%s aucune colonne applicable", config.score_table)
        return
    reset_stmt = text(f"UPDATE {config.score_table} SET " + ", ".join(assignments))
    LOGGER.info(
        "Reset selector avant run | table=%s colonnes=%s",
        config.score_table,
        sorted(assignments),
    )
    try:
        with engine.begin() as conn:
            conn.execute(reset_stmt)
    except SQLAlchemyError as exc:
        LOGGER.exception("Echec du reset selector sur %s.", config.score_table)
        raise RuntimeError("Impossible de réinitialiser les colonnes selector avant exécution.") from exc


def prepare_scores_snapshot(scored_df: pd.DataFrame | None) -> list[dict[str, object]]:
    if scored_df is None or scored_df.empty:
        return []
    available_columns = set(scored_df.columns)
    missing_required = [
        column
        for column in ("symbol", "trend_score", "vcp_score", "final_score")
        if column not in available_columns
    ]
    if missing_required:
        raise ValueError(f"Colonnes selector manquantes pour persistance: {missing_required}")
    snapshot = scored_df.copy()
    for column in PERSISTED_SELECTOR_SCORE_COLUMNS:
        if column not in snapshot.columns:
            snapshot[column] = pd.NA
    snapshot = snapshot.loc[:, PERSISTED_SELECTOR_SCORE_COLUMNS].copy()
    snapshot = snapshot.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last")
    for column in SNAPSHOT_NUMERIC_COLUMNS:
        if column in snapshot.columns:
            snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
    snapshot["days_to_earnings"] = pd.to_numeric(snapshot["days_to_earnings"], errors="coerce")
    snapshot["earnings_blackout"] = (
        pd.to_numeric(snapshot["earnings_blackout"], errors="coerce").fillna(0).astype(int)
    )
    snapshot["earnings_date"] = pd.to_datetime(snapshot["earnings_date"], errors="coerce", utc=False).dt.date
    for column in SNAPSHOT_TEXT_COLUMNS:
        snapshot[column] = snapshot[column].where(snapshot[column].notna(), None)
    snapshot = snapshot.astype(object)
    snapshot = snapshot.where(pd.notna(snapshot), None)
    return snapshot.to_dict(orient="records")


def update_database(
    engine: Engine,
    config: AlphaScannerConfig,
    selected_df: pd.DataFrame,
    scored_df: pd.DataFrame | None = None,
    *,
    progress: Callable[..., None] | None = None,
    snapshot_date_override: date | None = None,
) -> int:
    """Persiste scores + flag is_candidate + archive stock_scores_history."""
    selected_symbols = (
        selected_df["symbol"].astype(str).dropna().tolist() if not selected_df.empty else []
    )
    scores_snapshot = prepare_scores_snapshot(scored_df)
    available_columns = get_table_columns(
        engine,
        config.score_table,
        fallback_columns=DEFAULT_SELECTOR_SCORE_TABLE_COLUMNS,
    )
    reset_stmt = (
        text(f"UPDATE {config.score_table} SET is_candidate = 0")
        if "is_candidate" in available_columns
        else None
    )
    persisted_update_columns = [
        column for column in PERSISTED_SELECTOR_SCORE_COLUMNS
        if column != "symbol" and column in available_columns
    ]
    set_clauses = [f"{column} = :{column}" for column in persisted_update_columns]
    if "last_updated_scan" in available_columns:
        set_clauses.append("last_updated_scan = :updated_at")
    score_stmt = (
        text(
            f"UPDATE {config.score_table} SET " + ", ".join(set_clauses) + " WHERE symbol = :symbol"
        )
        if set_clauses
        else None
    )
    mark_stmt = (
        text(
            f"""
            UPDATE {config.score_table}
            SET is_candidate = 1
            WHERE symbol IN :symbols
            """
        ).bindparams(bindparam("symbols", expanding=True))
        if "is_candidate" in available_columns
        else None
    )
    updated_at = datetime.now(UTC).replace(tzinfo=None)

    LOGGER.info(
        "Mise a jour DB | table=%s snapshot_scores=%s candidats=%s batch_size=%s",
        config.score_table,
        len(scores_snapshot),
        len(selected_symbols),
        config.update_batch_size,
    )

    total_score_batches = max(
        (len(scores_snapshot) + config.update_batch_size - 1) // config.update_batch_size, 0
    ) if score_stmt is not None else 0
    total_candidate_batches = max(
        (len(selected_symbols) + config.update_batch_size - 1) // config.update_batch_size, 0
    ) if mark_stmt is not None else 0
    total_db_batches = total_score_batches + total_candidate_batches
    completed_db_batches = 0

    def _emit(label: str = "🎯 Progression Alpha Scanner — persistance DB") -> None:
        if progress is None:
            return
        progress(
            current=completed_db_batches,
            total=total_db_batches,
            label=label,
            phase="persist_db",
            extra_summary={
                "eligible_symbols": len(scores_snapshot),
                "selected_candidates": len(selected_symbols),
                "db_batches_total": total_db_batches,
                "db_batches_completed": completed_db_batches,
            },
        )

    _emit()

    try:
        with engine.begin() as conn:
            for start in range(0, len(scores_snapshot), config.update_batch_size):
                if score_stmt is None:
                    break
                score_batch = [
                    {
                        **{key: value for key, value in row.items() if key in {"symbol", *persisted_update_columns}},
                        "updated_at": updated_at,
                    }
                    for row in scores_snapshot[start:start + config.update_batch_size]
                ]
                if not score_batch:
                    continue
                conn.execute(score_stmt, score_batch)
                LOGGER.info(
                    "Mise a jour DB | scores selector batch=%s-%s taille=%s",
                    start + 1,
                    start + len(score_batch),
                    len(score_batch),
                )
                completed_db_batches += 1
                _emit()
            if reset_stmt is not None:
                conn.execute(reset_stmt)
                LOGGER.info("Mise a jour DB | reset is_candidate=0 effectue")
            for start in range(0, len(selected_symbols), config.update_batch_size):
                if mark_stmt is None:
                    break
                batch = selected_symbols[start:start + config.update_batch_size]
                if not batch:
                    continue
                conn.execute(mark_stmt, {"updated_at": updated_at, "symbols": batch})
                LOGGER.info(
                    "Mise a jour DB | batch=%s-%s taille=%s",
                    start + 1,
                    start + len(batch),
                    len(batch),
                )
                completed_db_batches += 1
                _emit()
    except SQLAlchemyError as exc:
        LOGGER.exception("Echec de mise a jour transactionnelle de %s.", config.score_table)
        raise RuntimeError("Impossible de mettre à jour les candidats en base.") from exc

    LOGGER.info("Mise a jour DB terminee | candidats_mis_a_jour=%s", len(selected_symbols))

    # Re-archive stock_scores -> stock_scores_history pour propager
    # is_candidate=1 dans l'historique PIT.
    try:
        from screener.db_io import archive_scores_snapshot

        archive_target = snapshot_date_override if isinstance(snapshot_date_override, date) else date.today()
        archived = archive_scores_snapshot(engine, snapshot_date=archive_target)
        LOGGER.info(
            "Archivage stock_scores_history apres alpha_scanner | snapshot_date=%s lignes=%s",
            archive_target,
            archived,
        )
    except Exception:
        LOGGER.warning(
            "Archivage stock_scores_history apres alpha_scanner echoue ; "
            "risk_management pourrait ne pas voir les nouveaux is_candidate=1.",
            exc_info=True,
        )

    return len(selected_symbols)


__all__ = [
    "fetch_market_data",
    "fetch_scores",
    "fetch_instrument_metadata",
    "fetch_quote_snapshots",
    "fetch_next_earnings",
    "load_benchmark_returns",
    "build_preselection_rejection_audit",
    "iter_eligible_symbol_chunks",
    "reset_selector_outputs",
    "prepare_scores_snapshot",
    "update_database",
    "build_data_quality_gate",
    "get_stock_metadata_columns",
    "get_stock_quote_snapshots_columns",
]



