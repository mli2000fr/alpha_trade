"""
backtesting/data_loader.py
===========================
Charge les données historiques depuis la base MySQL pour le backtest :
  - OHLCV (stock_bars_daily) : jusqu'à 10 ans
  - Scores quantitatifs (stock_scores) : is_candidate, score, secteur
  - Sentiment ticker (ticker_daily_sentiment_features) : 365 jours de lookback
  - Prédictions ML (model_predictions)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from backtesting.fidelity import PitHistoryRequiredError, ScoreLoadDiagnostics, ScoreLoadResult

LOGGER = logging.getLogger(__name__)
BACKTEST_REQUIRED_BARS_DATA_SOURCE = "eodhd_eod"


def _build_table_access_error(table_name: str, exc: Exception) -> RuntimeError:
    message = (
        f"Impossible d'inspecter la table {table_name}. "
        "Vérifiez la base ciblée (DB_HOST/DB_NAME), les droits SQL et les dépendances d'authentification MySQL du runtime. "
        f"Cause initiale: {exc}"
    )
    return RuntimeError(message)


def _table_exists(engine: Engine, table_name: str) -> bool:
    """Retourne True si la table existe."""
    try:
        return inspect(engine).has_table(table_name)
    except Exception:
        LOGGER.debug("Impossible d'inspecter la table %s.", table_name, exc_info=True)
        return False


def _get_table_columns(engine: Engine, table_name: str, *, required: bool = False) -> set[str]:
    """Retourne l'ensemble des colonnes d'une table."""
    try:
        return {str(col["name"]) for col in inspect(engine).get_columns(table_name)}
    except Exception as exc:
        LOGGER.debug("Impossible d'inspecter les colonnes de %s.", table_name, exc_info=True)
        if required:
            raise _build_table_access_error(table_name, exc) from exc
        return set()


def get_required_bars_source_filter(
    engine: Engine,
    *,
    table_name: str = "stock_bars_daily",
    table_alias: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Retourne un fragment SQL imposant la source canonique EODHD.

    Le backtesting doit désormais s'exécuter uniquement sur les barres issues
    d'EODHD, même si la table contient un mélange de providers historiques.
    """
    columns = _get_table_columns(engine, table_name, required=True)
    if not columns:
        raise RuntimeError(f"La table {table_name} est introuvable ou inaccessible.")
    if "data_source" not in columns:
        raise RuntimeError(
            f"La colonne {table_name}.data_source est requise pour forcer le backtest sur "
            f"{BACKTEST_REQUIRED_BARS_DATA_SOURCE}."
        )
    qualified = f"{table_alias}.data_source" if table_alias else "`data_source`"
    return f"AND {qualified} = :required_data_source", {"required_data_source": BACKTEST_REQUIRED_BARS_DATA_SOURCE}


def load_ohlcv(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Charge les barres OHLCV journalières.

    Returns
    -------
    DataFrame avec colonnes : symbol, trade_date, open, high, low, close, volume
    """
    columns = _get_table_columns(engine, "stock_bars_daily", required=True)
    if not columns:
        raise RuntimeError("La table stock_bars_daily est introuvable ou inaccessible.")

    date_col = "trade_date" if "trade_date" in columns else "date" if "date" in columns else None
    if date_col is None:
        raise RuntimeError("Aucune colonne date compatible dans stock_bars_daily (attendu: trade_date ou date).")

    close_expr = "COALESCE(adj_close, `close`)" if "adj_close" in columns else "`close`"
    source_filter_sql, source_filter_params = get_required_bars_source_filter(engine, table_name="stock_bars_daily")
    query = text(f"""
        SELECT symbol,
               `{date_col}` AS trade_date,
               `open` AS open,
               `high` AS high,
               `low` AS low,
               {close_expr} AS `close`,
               volume
        FROM stock_bars_daily
        WHERE `{date_col}` BETWEEN :start AND :end
          {source_filter_sql}
        ORDER BY `{date_col}`, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={"start": start, "end": end, **source_filter_params},
            parse_dates=["trade_date"],
        )
    LOGGER.info("OHLCV chargé : %d lignes, %d symboles, [%s → %s]",
                len(df), df["symbol"].nunique() if len(df) else 0, start, end)
    return df


def load_scores(
    engine: Engine,
    start: date,
    end: date,
    capital_preset_key: str | None = None,
    *,
    strict_pit: bool = False,
    return_diagnostics: bool = False,
) -> Any:
    """Charge les scores candidats.

    Priorité :
    1. `stock_scores_history` (point-in-time correct pour le backtest)
    2. `stock_scores` avec fallback sur les horodatages de mise à jour
    """
    history_exists = _table_exists(engine, "stock_scores_history")

    def _optional_select(columns: set[str], column: str) -> str:
        return column if column in columns else f"NULL AS {column}"

    def _build_result(df: pd.DataFrame, diagnostics: ScoreLoadDiagnostics) -> Any:
        if return_diagnostics:
            return ScoreLoadResult(frame=df, diagnostics=diagnostics)
        return df

    if history_exists:
        history_columns = _get_table_columns(engine, "stock_scores_history")
        has_walk_forward = "final_score_walk_forward" in history_columns
        has_capital_preset_key = "capital_preset_key" in history_columns
        history_preset_filter = ""
        history_params: dict[str, object] = {"start": start, "end": end}
        if has_capital_preset_key and capital_preset_key:
            history_preset_filter = " AND capital_preset_key = :capital_preset_key"
            history_params["capital_preset_key"] = str(capital_preset_key)
        history_query = text(f"""
            SELECT symbol,
                   snapshot_date AS trade_date,
                   {_optional_select(history_columns, 'capital_preset_key')},
                   {_optional_select(history_columns, 'config_fingerprint')},
                   final_score,
                   final_score_sentiment,
                   {_optional_select(history_columns, 'final_score_walk_forward')},
                   sector,
                   is_candidate,
                   {_optional_select(history_columns, 'sentiment_net_agg')},
                   {_optional_select(history_columns, 'sector_impact_agg')},
                   {_optional_select(history_columns, 'company_idio_score')},
                   {_optional_select(history_columns, 'macro_regime_score')},
                   {_optional_select(history_columns, 'company_idio_signal_norm')},
                   {_optional_select(history_columns, 'macro_regime_signal_norm')},
                   {_optional_select(history_columns, 'company_idio_component')},
                   {_optional_select(history_columns, 'macro_regime_component')},
                   {_optional_select(history_columns, 'quant_component')},
                   {_optional_select(history_columns, 'walk_forward_sentiment_weight')},
                   {_optional_select(history_columns, 'walk_forward_macro_weight')},
                   {_optional_select(history_columns, 'walk_forward_quant_weight')},
                   {_optional_select(history_columns, 'calibration_run_id')},
                   {_optional_select(history_columns, 'calibration_source')},
                   CASE
                       WHEN {('final_score_walk_forward IS NOT NULL' if has_walk_forward else '0 = 1')} THEN 'final_score_walk_forward'
                       WHEN final_score_sentiment IS NOT NULL THEN 'final_score_sentiment'
                       ELSE 'final_score'
                   END AS score_source
            FROM stock_scores_history
            WHERE snapshot_date BETWEEN :start AND :end
              {history_preset_filter}
              AND is_candidate = 1
            ORDER BY snapshot_date, symbol
        """)
        with engine.connect() as conn:
            df = pd.read_sql(history_query, conn, params=history_params, parse_dates=["trade_date"])
        if not df.empty:
            LOGGER.info(
                "Scores candidats chargés depuis stock_scores_history : %d lignes%s",
                len(df),
                f" | preset={capital_preset_key}" if capital_preset_key and has_capital_preset_key else "",
            )
            return _build_result(
                df,
                ScoreLoadDiagnostics(
                    source_table="stock_scores_history",
                    strict_pit_requested=bool(strict_pit),
                    history_table_exists=True,
                    history_rows_found=int(len(df)),
                    capital_preset_key=str(capital_preset_key) if capital_preset_key else None,
                    config_fingerprint_present="config_fingerprint" in df.columns and df["config_fingerprint"].notna().any(),
                ),
            )
        LOGGER.warning(
            "stock_scores_history existe mais aucune ligne n'a ete trouvee sur [%s → %s] — fallback sur stock_scores.",
            start,
            end,
        )
        if strict_pit:
            raise PitHistoryRequiredError(
                "Mode pipeline: aucun snapshot PIT disponible dans stock_scores_history "
                f"sur [{start} → {end}]"
                + (f" pour preset={capital_preset_key}." if capital_preset_key else ".")
            )
        degraded_reasons = ("stock_scores_history_empty",)
    else:
        if strict_pit:
            raise PitHistoryRequiredError(
                "Mode pipeline: table stock_scores_history indisponible — "
                "impossible de garantir un replay strictement point-in-time."
            )
        degraded_reasons = ("stock_scores_history_missing",)

    LOGGER.warning(
        "Lecture des scores depuis stock_scores (snapshot courant). "
        "Le backtest ne sera pas strictement point-in-time."
    )
    stock_columns = _get_table_columns(engine, "stock_scores")
    has_walk_forward = "final_score_walk_forward" in stock_columns
    query = text(f"""
        SELECT symbol,
               DATE(COALESCE(last_updated_sentiment, last_updated_scan, last_updated_score)) AS trade_date,
               NULL AS capital_preset_key,
               NULL AS config_fingerprint,
               final_score,
               final_score_sentiment,
               {_optional_select(stock_columns, 'final_score_walk_forward')},
               sector,
               is_candidate,
               {_optional_select(stock_columns, 'sentiment_net_agg')},
               {_optional_select(stock_columns, 'sector_impact_agg')},
               {_optional_select(stock_columns, 'company_idio_score')},
               {_optional_select(stock_columns, 'macro_regime_score')},
               {_optional_select(stock_columns, 'company_idio_signal_norm')},
               {_optional_select(stock_columns, 'macro_regime_signal_norm')},
               {_optional_select(stock_columns, 'company_idio_component')},
               {_optional_select(stock_columns, 'macro_regime_component')},
               {_optional_select(stock_columns, 'quant_component')},
               {_optional_select(stock_columns, 'walk_forward_sentiment_weight')},
               {_optional_select(stock_columns, 'walk_forward_macro_weight')},
               {_optional_select(stock_columns, 'walk_forward_quant_weight')},
               {_optional_select(stock_columns, 'calibration_run_id')},
               {_optional_select(stock_columns, 'calibration_source')},
               CASE
                   WHEN {('final_score_walk_forward IS NOT NULL' if has_walk_forward else '0 = 1')} THEN 'final_score_walk_forward'
                   WHEN final_score_sentiment IS NOT NULL THEN 'final_score_sentiment'
                   ELSE 'final_score'
               END AS score_source
        FROM stock_scores
        WHERE DATE(COALESCE(last_updated_sentiment, last_updated_scan, last_updated_score)) BETWEEN :start AND :end
          AND is_candidate = 1
        ORDER BY trade_date, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start": start, "end": end}, parse_dates=["trade_date"])
    LOGGER.info("Scores candidats chargés : %d lignes", len(df))
    return _build_result(
        df,
        ScoreLoadDiagnostics(
            source_table="stock_scores",
            strict_pit_requested=bool(strict_pit),
            history_table_exists=history_exists,
            history_rows_found=0,
            capital_preset_key=str(capital_preset_key) if capital_preset_key else None,
            fallback_used=True,
            degraded_reasons=degraded_reasons,
        ),
    )


def load_sentiment(engine: Engine, start: date, end: date, lookback_days: int = 365) -> pd.DataFrame:
    """Charge les features sentiment ticker avec lookback étendu (365j par défaut)."""
    sentiment_start = start - timedelta(days=lookback_days)
    columns = _get_table_columns(engine, "ticker_daily_sentiment_features")
    if not columns:
        LOGGER.warning("ticker_daily_sentiment_features introuvable — sentiment externe ignoré.")
        return pd.DataFrame(columns=["symbol", "trade_date", "sentiment_net_mean", "news_count"])

    sentiment_col = (
        "sentiment_net_mean_5d" if "sentiment_net_mean_5d" in columns
        else "sentiment_net_mean_1d" if "sentiment_net_mean_1d" in columns
        else None
    )
    news_col = "news_count_5d" if "news_count_5d" in columns else "news_count_1d" if "news_count_1d" in columns else None
    if sentiment_col is None or news_col is None:
        LOGGER.warning("Colonnes sentiment compatibles absentes — sentiment externe ignoré.")
        return pd.DataFrame(columns=["symbol", "trade_date", "sentiment_net_mean", "news_count"])

    query = text(f"""
        SELECT symbol,
               trade_date,
               {sentiment_col} AS sentiment_net_mean,
               {news_col} AS news_count
        FROM ticker_daily_sentiment_features
        WHERE trade_date BETWEEN :start AND :end
        ORDER BY trade_date, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"start": sentiment_start, "end": end}, parse_dates=["trade_date"])
    LOGGER.info("Sentiment chargé : %d lignes (lookback %dj)", len(df), lookback_days)
    return df


def load_predictions(
    engine: Engine,
    start: date,
    end: date,
    *,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Charge les prédictions ML.

    Phase E.2 (refactor) : ``symbols`` permet de restreindre l'I/O à un
    sous-ensemble (typiquement les candidats déjà chargés) — gain x10 à x100
    sur des univers larges.
    """
    columns = _get_table_columns(engine, "model_predictions")
    if not columns:
        LOGGER.warning("model_predictions introuvable — prédictions ML ignorées.")
        return pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class", "run_id", "created_at"])

    date_col = "trade_date" if "trade_date" in columns else "prediction_date" if "prediction_date" in columns else None
    if date_col is None:
        LOGGER.warning("Aucune colonne date compatible dans model_predictions — prédictions ML ignorées.")
        return pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class", "run_id", "created_at"])

    params: dict[str, object] = {"start": start, "end": end}
    where_symbols = ""
    if symbols:
        unique_symbols = sorted({s for s in symbols if isinstance(s, str) and s})
        if unique_symbols:
            placeholders = ",".join(f":sym_{i}" for i in range(len(unique_symbols)))
            where_symbols = f" AND symbol IN ({placeholders})"
            params.update({f"sym_{i}": sym for i, sym in enumerate(unique_symbols)})

    def _optional_select(columns: set[str], column: str) -> str:  # noqa: redefinition-ok
        return column if column in columns else f"NULL AS {column}"

    query = text(f"""
        SELECT symbol,
               {date_col} AS trade_date,
               predicted_proba,
               predicted_class,
               {_optional_select(columns, 'run_id')},
               {_optional_select(columns, 'created_at')}
        FROM model_predictions
        WHERE {date_col} BETWEEN :start AND :end{where_symbols}
        ORDER BY {date_col}, symbol
    """)
    with engine.connect() as conn:
        parse_dates = ["trade_date"]
        if "created_at" in columns:
            parse_dates.append("created_at")
        df = pd.read_sql(query, conn, params=params, parse_dates=parse_dates)
    LOGGER.info("Prédictions ML chargées : %d lignes (filter symbols=%s)", len(df), bool(symbols))
    return df


def pivot_ohlcv(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Pivote les OHLCV en DataFrames indexés par date, colonnes = symboles.

    Returns
    -------
    dict avec clés 'open', 'high', 'low', 'close', 'volume'
    """
    required_columns = {"symbol", "trade_date", "open", "high", "low", "close", "volume"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            "pivot_ohlcv requiert les colonnes {} (manquantes: {}).".format(
                sorted(required_columns),
                sorted(missing_columns),
            )
        )

    result = {}
    for col in ("open", "high", "low", "close", "volume"):
        pivoted = df.pivot_table(index="trade_date", columns="symbol", values=col)
        pivoted.sort_index(inplace=True)
        result[col] = pivoted
    return result



