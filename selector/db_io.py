"""Sprint S7 — Repository SQL pour ``AlphaScanner``.

Fonctions libres prenant ``engine + config`` en paramètres ; AlphaScanner
les délègue via composition. Aucune logique métier de scoring ici, juste
les requêtes SELECT / UPDATE et l'introspection schéma.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from selector.config import PRICE_COLUMNS
from selector.filters import ELIGIBLE_HISTORY_STATUSES, METADATA_COLUMNS
from selector.ranking import PERSISTED_SELECTOR_SCORE_COLUMNS, SCORE_COLUMNS

if TYPE_CHECKING:
    from selector.config import AlphaScannerConfig

LOGGER = logging.getLogger("selector.alpha_scanner")

DATA_QUALITY_QUOTE_MAX_AGE_DAYS = 5


def _has_table(engine: Engine, table_name: str) -> bool:
    try:
        return bool(inspect(engine).has_table(table_name))
    except Exception:
        LOGGER.debug("Inspection table %s indisponible.", table_name, exc_info=True)
        return False


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
    }
    blocking_checks = [name for name, payload in checks.items() if payload.get("status") == "blocked"]
    return {
        "status": "blocked" if blocking_checks else "ok",
        "reference_date": effective_reference_date.isoformat(),
        "blocking_checks": blocking_checks,
        "checks": checks,
    }


def _build_quotes_quality_check(
    engine: Engine,
    config: AlphaScannerConfig,
    reference_date: date,
) -> dict[str, object]:
    if config.max_spread_bps is None:
        return {"enabled": False, "status": "disabled", "reason": "spread_filter_disabled"}
    if not _has_table(engine, "stock_quote_snapshots"):
        return {
            "enabled": True,
            "status": "blocked",
            "reason": "quotes_table_missing",
            "max_age_days": DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
        }
    latest_quote_date = _read_scalar_date(
        engine,
        text("SELECT MAX(quote_date) FROM stock_quote_snapshots WHERE quote_date <= :reference_date"),
        {"reference_date": reference_date},
    )
    if latest_quote_date is None:
        return {
            "enabled": True,
            "status": "blocked",
            "reason": "quotes_unavailable",
            "max_age_days": DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
        }
    age_days = max((reference_date - latest_quote_date).days, 0)
    return {
        "enabled": True,
        "status": "ok" if age_days <= DATA_QUALITY_QUOTE_MAX_AGE_DAYS else "blocked",
        "reason": "ok" if age_days <= DATA_QUALITY_QUOTE_MAX_AGE_DAYS else "quotes_stale",
        "latest_quote_date": latest_quote_date.isoformat(),
        "age_days": age_days,
        "max_age_days": DATA_QUALITY_QUOTE_MAX_AGE_DAYS,
    }


def _build_earnings_quality_check(
    engine: Engine,
    config: AlphaScannerConfig,
    reference_date: date,
) -> dict[str, object]:
    if config.earnings_blackout_days is None:
        return {"enabled": False, "status": "disabled", "reason": "earnings_filter_disabled"}
    required_horizon_days = max(int(config.earnings_blackout_days), 1)
    required_until = reference_date + timedelta(days=required_horizon_days)
    if not _has_table(engine, "stock_earnings_calendar"):
        return {
            "enabled": True,
            "status": "blocked",
            "reason": "earnings_table_missing",
            "required_until": required_until.isoformat(),
            "required_horizon_days": required_horizon_days,
        }
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
        return {
            "enabled": True,
            "status": "blocked",
            "reason": "earnings_unavailable",
            "required_until": required_until.isoformat(),
            "required_horizon_days": required_horizon_days,
        }
    if next_earnings_date is None:
        return {
            "enabled": True,
            "status": "blocked",
            "reason": "earnings_no_future_coverage",
            "latest_earnings_date": latest_earnings_date.isoformat(),
            "required_until": required_until.isoformat(),
            "required_horizon_days": required_horizon_days,
        }
    return {
        "enabled": True,
        "status": "ok" if latest_earnings_date >= required_until else "blocked",
        "reason": "ok" if latest_earnings_date >= required_until else "earnings_horizon_too_short",
        "next_earnings_date": next_earnings_date.isoformat(),
        "latest_earnings_date": latest_earnings_date.isoformat(),
        "required_until": required_until.isoformat(),
        "required_horizon_days": required_horizon_days,
    }


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
    empty_columns = ["symbol", "quote_date", "quote_timestamp", "spread_bps", "bid_size", "ask_size"]
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
    reset_stmt = text(
        f"""
        UPDATE {config.score_table}
        SET trend_score = NULL,
            vcp_score = NULL,
            final_score = NULL,
            market_cap = NULL,
            beta_126 = NULL,
            spread_bps = NULL,
            earnings_date = NULL,
            days_to_earnings = NULL,
            earnings_blackout = 0,
            is_candidate = 0
        """
    )
    LOGGER.info(
        "Reset selector avant run | table=%s colonnes=[trend_score, vcp_score, final_score, market_cap, beta_126, spread_bps, earnings_date, days_to_earnings, earnings_blackout, is_candidate]",
        config.score_table,
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
    available_columns = [c for c in PERSISTED_SELECTOR_SCORE_COLUMNS if c in scored_df.columns]
    if available_columns != PERSISTED_SELECTOR_SCORE_COLUMNS:
        missing = [c for c in PERSISTED_SELECTOR_SCORE_COLUMNS if c not in available_columns]
        raise ValueError(f"Colonnes selector manquantes pour persistance: {missing}")
    snapshot = scored_df.loc[:, PERSISTED_SELECTOR_SCORE_COLUMNS].copy()
    snapshot = snapshot.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last")
    for column in ["trend_score", "vcp_score", "final_score"]:
        snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
    for column in ["market_cap", "beta_126", "spread_bps"]:
        snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
    snapshot["days_to_earnings"] = pd.to_numeric(snapshot["days_to_earnings"], errors="coerce")
    snapshot["earnings_blackout"] = (
        pd.to_numeric(snapshot["earnings_blackout"], errors="coerce").fillna(0).astype(int)
    )
    snapshot["earnings_date"] = pd.to_datetime(snapshot["earnings_date"], errors="coerce", utc=False).dt.date
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
    reset_stmt = text(f"UPDATE {config.score_table} SET is_candidate = 0")
    score_stmt = text(
        f"""
        UPDATE {config.score_table}
        SET trend_score = :trend_score,
            vcp_score = :vcp_score,
            final_score = :final_score,
            market_cap = :market_cap,
            beta_126 = :beta_126,
            spread_bps = :spread_bps,
            earnings_date = :earnings_date,
            days_to_earnings = :days_to_earnings,
            earnings_blackout = :earnings_blackout,
            last_updated_scan = :updated_at
        WHERE symbol = :symbol
        """
    )
    mark_stmt = text(
        f"""
        UPDATE {config.score_table}
        SET is_candidate = 1
        WHERE symbol IN :symbols
        """
    ).bindparams(bindparam("symbols", expanding=True))
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
    )
    total_candidate_batches = max(
        (len(selected_symbols) + config.update_batch_size - 1) // config.update_batch_size, 0
    )
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
                score_batch = [
                    {**row, "updated_at": updated_at}
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
            conn.execute(reset_stmt)
            LOGGER.info("Mise a jour DB | reset is_candidate=0 effectue")
            for start in range(0, len(selected_symbols), config.update_batch_size):
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
    "iter_eligible_symbol_chunks",
    "reset_selector_outputs",
    "prepare_scores_snapshot",
    "update_database",
    "build_data_quality_gate",
    "get_stock_metadata_columns",
    "get_stock_quote_snapshots_columns",
]



