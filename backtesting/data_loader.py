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
from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY
from common.tradable_universe import UniverseResolution, resolve_universe_asof

LOGGER = logging.getLogger(__name__)
BACKTEST_REQUIRED_BARS_DATA_SOURCE = "eodhd_eod"


def load_tradable_universe_asof(
    engine: Engine,
    trade_date: date,
    capital_preset_key: str = DEFAULT_CAPITAL_PRESET_KEY,
    *,
    tradable_only: bool = True,
) -> UniverseResolution:
    """Charge l'univers PIT canonique utilisé par le backtest."""
    return resolve_universe_asof(
        engine,
        trade_date,
        capital_preset_key,
        tradable_only=tradable_only,
    )


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


def _resolve_bars_date_column(columns: set[str], table_name: str) -> str:
    date_col = "trade_date" if "trade_date" in columns else "date" if "date" in columns else None
    if date_col is None:
        raise RuntimeError(
            f"Aucune colonne date compatible dans {table_name} (attendu: trade_date ou date)."
        )
    return date_col


def preflight_required_bars_data_source(
    engine: Engine,
    start: date,
    end: date,
    *,
    table_name: str = "stock_bars_daily",
) -> dict[str, Any]:
    """Valide la présence de la source OHLCV requise sur la fenêtre demandée.

    Le backtesting canonique consomme uniquement ``data_source='eodhd_eod'``.
    Cette pré-vérification rend explicites :
    - l'absence de colonne ``data_source`` ;
    - l'absence totale de barres sur la fenêtre ;
    - l'absence de barres ``eodhd_eod`` sur la fenêtre ;
    - l'existence éventuelle d'un mix de sources (status ``warning``).
    """
    columns = _get_table_columns(engine, table_name, required=True)
    if not columns:
        raise RuntimeError(f"La table {table_name} est introuvable ou inaccessible.")
    if "data_source" not in columns:
        raise RuntimeError(
            f"La colonne {table_name}.data_source est requise pour pré-valider le backtesting sur "
            f"{BACKTEST_REQUIRED_BARS_DATA_SOURCE}."
        )
    date_col = _resolve_bars_date_column(columns, table_name)

    stmt = text(
        f"""
        SELECT COALESCE(NULLIF(TRIM(data_source), ''), 'unknown') AS source,
               COUNT(*) AS rows_n,
               MIN(`{date_col}`) AS min_trade_date,
               MAX(`{date_col}`) AS max_trade_date
        FROM {table_name}
        WHERE `{date_col}` BETWEEN :start AND :end
        GROUP BY source
        ORDER BY rows_n DESC
        """
    )
    with engine.connect() as conn:
        rows = pd.read_sql(stmt, conn, params={"start": start, "end": end})

    counts = {
        str(row["source"]): int(row["rows_n"])
        for _, row in rows.iterrows()
    } if not rows.empty else {}
    rows_total = int(sum(counts.values()))
    if rows_total <= 0:
        raise RuntimeError(
            f"Aucune barre OHLCV disponible dans {table_name} sur [{start} → {end}]."
        )

    required_rows = int(counts.get(BACKTEST_REQUIRED_BARS_DATA_SOURCE, 0))
    if required_rows <= 0:
        available = ", ".join(sorted(counts)) or "aucune"
        raise RuntimeError(
            f"Préflight OHLCV échoué : aucune barre `{BACKTEST_REQUIRED_BARS_DATA_SOURCE}` dans {table_name} "
            f"sur [{start} → {end}] (sources observées: {available})."
        )

    dominant_source = max(counts, key=lambda source: counts[source])
    dominant_ratio = counts[dominant_source] / rows_total if rows_total else 0.0
    status = "ok" if required_rows == rows_total else "warning"
    degraded_reasons = [] if status == "ok" else ["mixed_data_source_window"]
    return {
        "table_name": table_name,
        "date_column": date_col,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "required_data_source": BACKTEST_REQUIRED_BARS_DATA_SOURCE,
        "status": status,
        "degraded_reasons": degraded_reasons,
        "rows_total": rows_total,
        "required_rows": required_rows,
        "counts": counts,
        "sources_present": sorted(counts),
        "dominant_source": dominant_source,
        "dominant_ratio": round(float(dominant_ratio), 6),
        "mixed_sources_detected": bool(status != "ok"),
    }


def load_ohlcv(engine: Engine, start: date, end: date) -> pd.DataFrame:
    """Charge les barres OHLCV journalières.

    Returns
    -------
    DataFrame avec colonnes : symbol, trade_date, open, high, low, close, volume
    """
    columns = _get_table_columns(engine, "stock_bars_daily", required=True)
    if not columns:
        raise RuntimeError("La table stock_bars_daily est introuvable ou inaccessible.")

    date_col = _resolve_bars_date_column(columns, "stock_bars_daily")

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


def load_spreads(
    engine: Engine,
    start: date,
    end: date,
    *,
    table_name: str = "stock_quote_snapshots",
    fallback_spread_bps: float = 5.0,
) -> pd.DataFrame:
    """Charge les spreads historiques (bid-ask) par symbole et date.

    Retourne un DataFrame pivoté (index=quote_date, columns=symbol, values=spread_bps)
    utilisable comme coût de transaction additionnel dans le simulateur.

    Si la table ou la colonne est absente, retourne un DataFrame vide (le simulateur
    utilisera le fallback).
    """
    if not _table_exists(engine, table_name):
        LOGGER.warning(
            "Table %s indisponible — spread réel désactivé, fallback à %.1f bps.",
            table_name, fallback_spread_bps,
        )
        return pd.DataFrame()

    columns = _get_table_columns(engine, table_name)
    if "spread_bps" not in columns:
        LOGGER.warning(
            "Colonne spread_bps absente de %s — fallback à %.1f bps.",
            table_name, fallback_spread_bps,
        )
        return pd.DataFrame()

    date_col = "quote_date" if "quote_date" in columns else "date"
    if date_col not in columns:
        LOGGER.warning(
            "Aucune colonne date dans %s — spread réel désactivé.", table_name,
        )
        return pd.DataFrame()

    query = text(f"""
        SELECT symbol,
               `{date_col}` AS quote_date,
               spread_bps
        FROM {table_name}
        WHERE `{date_col}` BETWEEN :start AND :end
          AND spread_bps IS NOT NULL
          AND spread_bps >= 0
        ORDER BY `{date_col}`, symbol
    """)
    with engine.connect() as conn:
        df = pd.read_sql(
            query,
            conn,
            params={"start": start, "end": end},
            parse_dates=["quote_date"],
        )

    if df.empty:
        LOGGER.info("Aucune donnée de spread dans %s sur [%s → %s].",
                     table_name, start, end)
        return pd.DataFrame()

    # Pivoter pour obtenir une matrice (date × symbole)
    spread_df = df.pivot_table(
        index="quote_date",
        columns="symbol",
        values="spread_bps",
        aggfunc="first",
    )
    # Forward-fill pour les jours sans snapshots (le spread change peu jour à jour)
    spread_df = spread_df.ffill().fillna(fallback_spread_bps)
    LOGGER.info(
        "Spreads chargés : %d jours, %d symboles, médiane=%.1f bps, [%s → %s]",
        len(spread_df), len(spread_df.columns) if not spread_df.empty else 0,
        float(spread_df.stack().median()) if not spread_df.empty else fallback_spread_bps,
        start, end,
    )
    return spread_df


def load_scores(
    engine: Engine,
    start: date,
    end: date,
    capital_preset_key: str | None = None,
    *,
    scores_pit_mode: str = "exact",
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

    normalized_scores_pit_mode = str(scores_pit_mode or "exact").strip().lower() or "exact"
    if normalized_scores_pit_mode not in {"exact", "asof_latest"}:
        raise ValueError(f"scores_pit_mode invalide: {scores_pit_mode}")

    if history_exists:
        history_columns = _get_table_columns(engine, "stock_scores_history")
        has_walk_forward = "final_score_walk_forward" in history_columns
        has_capital_preset_key = "capital_preset_key" in history_columns
        history_preset_filter = ""
        history_preset_filter_aliased = ""
        history_params: dict[str, object] = {"start": start, "end": end}
        if has_capital_preset_key and capital_preset_key:
            history_preset_filter = " AND capital_preset_key = :capital_preset_key"
            history_preset_filter_aliased = " AND s.capital_preset_key = :capital_preset_key"
            history_params["capital_preset_key"] = str(capital_preset_key)
        history_query = text(f"""
            SELECT symbol,
                   snapshot_date AS trade_date,
                   snapshot_date AS source_snapshot_date,
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
                   {_optional_select(history_columns, 'candidate_rank')},
                   {_optional_select(history_columns, 'selection_explanation')},
                   {_optional_select(history_columns, 'earnings_blackout')},
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
        if normalized_scores_pit_mode == "asof_latest":
            history_score_expr = (
                "COALESCE(s.final_score_walk_forward, s.final_score_sentiment, s.final_score)"
                if has_walk_forward
                else "COALESCE(s.final_score_sentiment, s.final_score)"
            )
            history_score_expr_unaliased = history_score_expr.replace("s.", "")
            bars_columns = _get_table_columns(engine, "stock_bars_daily", required=True)
            bars_date_col = _resolve_bars_date_column(bars_columns, "stock_bars_daily")
            source_filter_sql, source_filter_params = get_required_bars_source_filter(
                engine,
                table_name="stock_bars_daily",
            )
            history_params.update(source_filter_params)
            history_query = text(f"""
                SELECT s.symbol,
                       td.trade_date AS trade_date,
                       s.snapshot_date AS source_snapshot_date,
                       {('s.capital_preset_key' if 'capital_preset_key' in history_columns else 'NULL AS capital_preset_key')},
                       {('s.config_fingerprint' if 'config_fingerprint' in history_columns else 'NULL AS config_fingerprint')},
                       s.final_score,
                       s.final_score_sentiment,
                       {('s.final_score_walk_forward' if has_walk_forward else 'NULL AS final_score_walk_forward')},
                       s.sector,
                       s.is_candidate,
                       {('s.sentiment_net_agg' if 'sentiment_net_agg' in history_columns else 'NULL AS sentiment_net_agg')},
                       {('s.sector_impact_agg' if 'sector_impact_agg' in history_columns else 'NULL AS sector_impact_agg')},
                       {('s.company_idio_score' if 'company_idio_score' in history_columns else 'NULL AS company_idio_score')},
                       {('s.macro_regime_score' if 'macro_regime_score' in history_columns else 'NULL AS macro_regime_score')},
                       {('s.company_idio_signal_norm' if 'company_idio_signal_norm' in history_columns else 'NULL AS company_idio_signal_norm')},
                       {('s.macro_regime_signal_norm' if 'macro_regime_signal_norm' in history_columns else 'NULL AS macro_regime_signal_norm')},
                       {('s.company_idio_component' if 'company_idio_component' in history_columns else 'NULL AS company_idio_component')},
                       {('s.macro_regime_component' if 'macro_regime_component' in history_columns else 'NULL AS macro_regime_component')},
                       {('s.quant_component' if 'quant_component' in history_columns else 'NULL AS quant_component')},
                       {('s.walk_forward_sentiment_weight' if 'walk_forward_sentiment_weight' in history_columns else 'NULL AS walk_forward_sentiment_weight')},
                       {('s.walk_forward_macro_weight' if 'walk_forward_macro_weight' in history_columns else 'NULL AS walk_forward_macro_weight')},
                       {('s.walk_forward_quant_weight' if 'walk_forward_quant_weight' in history_columns else 'NULL AS walk_forward_quant_weight')},
                       {('s.calibration_run_id' if 'calibration_run_id' in history_columns else 'NULL AS calibration_run_id')},
                       {('s.calibration_source' if 'calibration_source' in history_columns else 'NULL AS calibration_source')},
                       {('s.candidate_rank' if 'candidate_rank' in history_columns else 'NULL AS candidate_rank')},
                       {('s.selection_explanation' if 'selection_explanation' in history_columns else 'NULL AS selection_explanation')},
                       {('s.earnings_blackout' if 'earnings_blackout' in history_columns else 'NULL AS earnings_blackout')},
                       CASE
                           WHEN {('s.final_score_walk_forward IS NOT NULL' if has_walk_forward else '0 = 1')} THEN 'final_score_walk_forward'
                           WHEN s.final_score_sentiment IS NOT NULL THEN 'final_score_sentiment'
                           ELSE 'final_score'
                       END AS score_source
                FROM (
                    SELECT DISTINCT `{bars_date_col}` AS trade_date
                    FROM stock_bars_daily
                    WHERE `{bars_date_col}` BETWEEN :start AND :end
                      {source_filter_sql}
                ) td
                JOIN stock_scores_history s
                  ON s.snapshot_date = (
                      SELECT MAX(snapshot_date)
                      FROM stock_scores_history
                      WHERE snapshot_date <= td.trade_date
                        {history_preset_filter}
                        AND is_candidate = 1
                        AND {history_score_expr_unaliased} IS NOT NULL
                  )
                WHERE s.is_candidate = 1
                  {history_preset_filter_aliased}
                  AND {history_score_expr} IS NOT NULL
                ORDER BY td.trade_date, s.symbol
            """)
        with engine.connect() as conn:
            df = pd.read_sql(history_query, conn, params=history_params, parse_dates=["trade_date"])
        if not df.empty:
            LOGGER.info(
                "Scores candidats chargés depuis stock_scores_history : %d lignes%s | mode=%s",
                len(df),
                f" | preset={capital_preset_key}" if capital_preset_key and has_capital_preset_key else "",
                normalized_scores_pit_mode,
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
            "stock_scores_history existe mais aucune ligne n'a ete trouvee sur [%s → %s] (mode=%s) — fallback sur stock_scores.",
            start,
            end,
            normalized_scores_pit_mode,
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
               NULL AS source_snapshot_date,
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
               {_optional_select(columns, 'predicted_side')},
               {_optional_select(columns, 'proba_long')},
               {_optional_select(columns, 'proba_flat')},
               {_optional_select(columns, 'proba_short')},
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



