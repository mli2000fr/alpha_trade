"""ihm/services/queries.py — Requêtes SQL centralisées pour l'IHM."""
from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st

from backtesting.fidelity import resolve_ml_pit_strategy
from database.run_business_summaries import parse_summary_json
from execution_engine.tca import build_tca_aggregate_frame
from ihm.services.alpha_scanner_threshold_presets import DEFAULT_ALPHA_SCANNER_DEPENDENCY_THRESHOLDS
from ihm.services.db import get_last_query_error, safe_query, safe_scalar
from ihm.services.run_summary import build_run_summary_caption
from ihm.services.screener_preferences import load_persisted_alpha_scanner_dependency_thresholds
from selector.explainability import build_candidate_explainability_payload

ALPHA_SCANNER_ELIGIBLE_UNIVERSE_SQL = """
    SELECT COUNT(DISTINCT sm.symbol)
    FROM stock_metadata sm
    WHERE LOWER(TRIM(COALESCE(sm.status, ''))) = 'active'
      AND COALESCE(sm.tradable, 0) = 1
      AND COALESCE(sm.bars_available, 0) = 1
      AND LOWER(TRIM(COALESCE(sm.asset_class, ''))) = 'us_equity'
      AND (
            sm.history_status IS NULL
         OR TRIM(sm.history_status) = ''
         OR LOWER(TRIM(sm.history_status)) IN ('pending', 'ready')
      )
"""

ALPHA_SCANNER_DEPENDENCY_THRESHOLDS: dict[str, dict[str, float]] = DEFAULT_ALPHA_SCANNER_DEPENDENCY_THRESHOLDS
STOCK_SCORES_BASE_COLUMNS = [
    "symbol",
    "sector",
    "is_candidate",
    "candidate_rank",
    "total_score",
    "final_score",
    "final_score_sentiment",
    "trend_score",
    "vcp_score",
    "signal_active",
    "total_news",
    "anomaly_count",
    "missing_days_count",
    "last_updated_score",
    "last_updated_scan",
    "last_updated_sentiment",
]
STOCK_SCORES_EXPLAINABILITY_COLUMNS = [
    "relative_strength_index",
    "market_cap",
    "beta_126",
    "spread_bps",
    "earnings_date",
    "days_to_earnings",
    "earnings_blackout",
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
    "liquidity_val",
    "sanitizer_status",
    "history_days",
]


def _coerce_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return date.fromisoformat(text_value[:10])
    except ValueError:
        return None


def _coverage_pct(covered_symbols: int, eligible_symbols: int) -> float:
    if eligible_symbols <= 0:
        return 0.0
    return round((covered_symbols / eligible_symbols) * 100.0, 2)


def _coerce_int(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _safe_scalar_with_error(query: str, params: dict[str, object] | None = None) -> tuple[object, str | None]:
    value = safe_scalar(query, params)
    return value, get_last_query_error()


def _parse_json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _get_table_columns(table_name: str) -> set[str]:
    columns_df = safe_query(f"SHOW COLUMNS FROM {table_name}")
    if columns_df.empty or "Field" not in columns_df.columns:
        return set()
    return {
        str(value).strip()
        for value in columns_df["Field"].tolist()
        if str(value).strip()
    }


def _build_stock_scores_query(available_columns: set[str]) -> str:
    selected_columns = [
        column
        for column in [*STOCK_SCORES_BASE_COLUMNS, *STOCK_SCORES_EXPLAINABILITY_COLUMNS]
        if column in available_columns
    ]
    if not selected_columns:
        selected_columns = ["symbol", "sector", "is_candidate", "total_score", "final_score", "final_score_sentiment"]
    order_by_parts: list[str] = []
    if "is_candidate" in available_columns:
        order_by_parts.append("COALESCE(is_candidate, 0) DESC")
    if "candidate_rank" in available_columns:
        order_by_parts.append("CASE WHEN candidate_rank IS NULL THEN 1 ELSE 0 END ASC")
        order_by_parts.append("candidate_rank ASC")
    for column in ("final_score_sentiment", "final_score", "total_score"):
        if column in available_columns:
            order_by_parts.append(f"{column} DESC")
    if "symbol" in available_columns:
        order_by_parts.append("symbol ASC")
    order_by_clause = ", ".join(order_by_parts) or "symbol ASC"
    return (
        "SELECT "
        + ", ".join(selected_columns)
        + " FROM stock_scores ORDER BY "
        + order_by_clause
    )


def _attach_candidate_explainability_payloads(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    enriched = df.copy()
    enriched["candidate_explainability_payload"] = enriched.apply(
        lambda row: build_candidate_explainability_payload(row.to_dict()),
        axis=1,
    )
    return enriched


def get_alpha_scanner_dependency_thresholds() -> dict[str, dict[str, float]]:
    return load_persisted_alpha_scanner_dependency_thresholds(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS)


def _build_quotes_dependency_payload(
    *,
    today: date,
    eligible_symbols: int,
    latest_date: date | None,
    covered_symbols: int,
    query_error: str | None,
    thresholds: dict[str, float],
) -> dict[str, object]:
    coverage_pct = _coverage_pct(covered_symbols, eligible_symbols)
    age_days = max((today - latest_date).days, 0) if latest_date is not None else None
    reasons: list[str] = []
    status = "green"

    if query_error:
        status = "red"
        reasons.append(query_error)
    elif eligible_symbols <= 0:
        status = "red"
        reasons.append("univers éligible Alpha Scanner vide ou indisponible")
    elif latest_date is None or covered_symbols <= 0:
        status = "red"
        reasons.append("aucun snapshot quote exploitable détecté")
    else:
        if age_days is not None and age_days > thresholds["max_age_error_days"]:
            status = "red"
            reasons.append(f"snapshot trop ancien ({age_days} j)")
        elif age_days is not None and age_days > thresholds["max_age_warn_days"]:
            status = "orange"
            reasons.append(f"snapshot à rafraîchir ({age_days} j)")

        if coverage_pct < thresholds["coverage_error_pct"]:
            status = "red"
            reasons.append(f"couverture trop faible ({coverage_pct:.1f}%)")
        elif coverage_pct < thresholds["coverage_warn_pct"] and status != "red":
            status = "orange"
            reasons.append(f"couverture partielle ({coverage_pct:.1f}%)")

    if not reasons:
        reasons.append("quotes disponibles pour le filtre de spread")

    return {
        "step_key": "sync_latest_quotes",
        "label": "Sync Latest Quotes",
        "table": "stock_quote_snapshots",
        "command": "python -m dataIntegrityEngine.sync_latest_quotes",
        "status": status,
        "latest_date": latest_date.isoformat() if latest_date is not None else None,
        "covered_symbols": int(covered_symbols),
        "eligible_symbols": int(eligible_symbols),
        "coverage_pct": coverage_pct,
        "coverage_label": f"{coverage_pct:.1f}% ({int(covered_symbols)}/{int(eligible_symbols)})" if eligible_symbols > 0 else "0.0% (0/0)",
        "age_days": age_days,
        "reason": " · ".join(reasons),
        "query_error": query_error,
    }


def _build_earnings_dependency_payload(
    *,
    today: date,
    eligible_symbols: int,
    latest_date: date | None,
    covered_symbols: int,
    query_error: str | None,
    thresholds: dict[str, float],
) -> dict[str, object]:
    coverage_pct = _coverage_pct(covered_symbols, eligible_symbols)
    horizon_days = max((latest_date - today).days, 0) if latest_date is not None else None
    reasons: list[str] = []
    status = "green"

    if query_error:
        status = "red"
        reasons.append(query_error)
    elif eligible_symbols <= 0:
        status = "red"
        reasons.append("univers éligible Alpha Scanner vide ou indisponible")
    elif latest_date is None or covered_symbols <= 0:
        status = "red"
        reasons.append("aucun earnings futur exploitable détecté")
    else:
        if horizon_days is not None and horizon_days < thresholds["min_horizon_error_days"]:
            status = "red"
            reasons.append(f"horizon trop court (latest_date à J+{horizon_days})")
        elif horizon_days is not None and horizon_days < thresholds["min_horizon_warn_days"]:
            status = "orange"
            reasons.append(f"horizon à compléter (latest_date à J+{horizon_days})")

        if coverage_pct < thresholds["coverage_error_pct"]:
            status = "red"
            reasons.append(f"couverture trop faible ({coverage_pct:.1f}%)")
        elif coverage_pct < thresholds["coverage_warn_pct"] and status != "red":
            status = "orange"
            reasons.append(f"couverture partielle ({coverage_pct:.1f}%)")

    if not reasons:
        reasons.append("earnings futurs disponibles pour le blackout résultats")

    return {
        "step_key": "sync_earnings_calendar",
        "label": "Sync Earnings Calendar",
        "table": "stock_earnings_calendar",
        "command": "python -m dataIntegrityEngine.sync_earnings_calendar",
        "status": status,
        "latest_date": latest_date.isoformat() if latest_date is not None else None,
        "covered_symbols": int(covered_symbols),
        "eligible_symbols": int(eligible_symbols),
        "coverage_pct": coverage_pct,
        "coverage_label": f"{coverage_pct:.1f}% ({int(covered_symbols)}/{int(eligible_symbols)})" if eligible_symbols > 0 else "0.0% (0/0)",
        "horizon_days": horizon_days,
        "reason": " · ".join(reasons),
        "query_error": query_error,
    }


@st.cache_data(ttl=60, show_spinner=False)
def get_alpha_scanner_dependency_diagnostic(*, today: date | None = None) -> dict[str, object]:
    reference_day = today or date.today()
    configured_thresholds = get_alpha_scanner_dependency_thresholds()

    eligible_raw, eligible_error = _safe_scalar_with_error(ALPHA_SCANNER_ELIGIBLE_UNIVERSE_SQL)
    eligible_symbols = _coerce_int(eligible_raw)

    quotes_latest_raw, quotes_latest_error = _safe_scalar_with_error(
        f"""
        SELECT MAX(q.quote_date)
        FROM stock_quote_snapshots q
        INNER JOIN (
            {ALPHA_SCANNER_ELIGIBLE_UNIVERSE_SQL.replace('SELECT COUNT(DISTINCT sm.symbol)', 'SELECT DISTINCT sm.symbol')}
        ) eligible ON eligible.symbol = q.symbol
        """
    )
    quotes_latest_date = _coerce_date(quotes_latest_raw)
    quotes_covered_symbols = 0
    quotes_covered_error = quotes_latest_error
    if quotes_latest_date is not None and quotes_latest_error is None:
        quotes_covered_raw, quotes_covered_error = _safe_scalar_with_error(
            f"""
            SELECT COUNT(DISTINCT q.symbol)
            FROM stock_quote_snapshots q
            INNER JOIN (
                {ALPHA_SCANNER_ELIGIBLE_UNIVERSE_SQL.replace('SELECT COUNT(DISTINCT sm.symbol)', 'SELECT DISTINCT sm.symbol')}
            ) eligible ON eligible.symbol = q.symbol
            WHERE q.quote_date = :latest_date
            """,
            {"latest_date": quotes_latest_date.isoformat()},
        )
        quotes_covered_symbols = _coerce_int(quotes_covered_raw)

    earnings_latest_raw, earnings_latest_error = _safe_scalar_with_error(
        f"""
        SELECT MAX(e.earnings_date)
        FROM stock_earnings_calendar e
        INNER JOIN (
            {ALPHA_SCANNER_ELIGIBLE_UNIVERSE_SQL.replace('SELECT COUNT(DISTINCT sm.symbol)', 'SELECT DISTINCT sm.symbol')}
        ) eligible ON eligible.symbol = e.symbol
        WHERE e.earnings_date >= :today
        """,
        {"today": reference_day.isoformat()},
    )
    earnings_latest_date = _coerce_date(earnings_latest_raw)
    earnings_covered_symbols = 0
    earnings_covered_error = earnings_latest_error
    if earnings_latest_error is None:
        earnings_covered_raw, earnings_covered_error = _safe_scalar_with_error(
            f"""
            SELECT COUNT(DISTINCT e.symbol)
            FROM stock_earnings_calendar e
            INNER JOIN (
                {ALPHA_SCANNER_ELIGIBLE_UNIVERSE_SQL.replace('SELECT COUNT(DISTINCT sm.symbol)', 'SELECT DISTINCT sm.symbol')}
            ) eligible ON eligible.symbol = e.symbol
            WHERE e.earnings_date >= :today
            """,
            {"today": reference_day.isoformat()},
        )
        earnings_covered_symbols = _coerce_int(earnings_covered_raw)

    quotes_payload = _build_quotes_dependency_payload(
        today=reference_day,
        eligible_symbols=eligible_symbols,
        latest_date=quotes_latest_date,
        covered_symbols=quotes_covered_symbols,
        query_error=eligible_error or quotes_covered_error,
        thresholds=configured_thresholds["sync_latest_quotes"],
    )
    earnings_payload = _build_earnings_dependency_payload(
        today=reference_day,
        eligible_symbols=eligible_symbols,
        latest_date=earnings_latest_date,
        covered_symbols=earnings_covered_symbols,
        query_error=eligible_error or earnings_covered_error,
        thresholds=configured_thresholds["sync_earnings_calendar"],
    )

    dependencies = {
        quotes_payload["step_key"]: quotes_payload,
        earnings_payload["step_key"]: earnings_payload,
    }
    all_red = all(str(payload.get("status")) == "red" for payload in dependencies.values())
    any_red_or_orange = any(str(payload.get("status")) in {"red", "orange"} for payload in dependencies.values())
    return {
        "as_of_date": reference_day.isoformat(),
        "eligible_symbols": eligible_symbols,
        "dependencies": dependencies,
        "thresholds": configured_thresholds,
        "all_red": all_red,
        "any_red_or_orange": any_red_or_orange,
    }


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_candidates_count() -> int:
    v = safe_scalar("SELECT COUNT(*) FROM stock_scores WHERE is_candidate = 1")
    return int(v) if v is not None else 0


def resolve_latest_candidate_snapshot_date(trade_date: str | date | None) -> date | None:
    """Retourne le snapshot_date le plus récent <= trade_date avec is_candidate=1.

    Utilisé par ``start_pipeline_run`` quand ``force_trade_date_to_latest_snapshot``
    est activé : permet de continuer un workflow démarré la veille même après
    réouverture de la session Streamlit (qui a réinitialisé trade_date à
    ``date.today()``).

    Retourne ``None`` si la table est vide, si trade_date est invalide, ou si
    aucun snapshot is_candidate=1 n'existe <= trade_date.
    """
    if trade_date is None:
        return None
    if isinstance(trade_date, str):
        cleaned = trade_date.strip()
        if not cleaned:
            return None
        try:
            trade_date = date.fromisoformat(cleaned)
        except ValueError:
            return None
    raw = safe_scalar(
        "SELECT MAX(snapshot_date) FROM stock_scores_history "
        "WHERE snapshot_date <= :trade_date AND is_candidate = 1",
        {"trade_date": trade_date},
    )
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=60, show_spinner=False)
def get_backtesting_pit_history_diagnostic(
    *,
    start: str | date | None,
    end: str | date | None,
    capital_preset_key: str | None,
) -> dict[str, object]:
    """Diagnostique la disponibilité PIT de `stock_scores_history` pour un run backtesting.

    Le mode `pipeline` du backtesting exige au moins un snapshot historisé sur la
    plage demandée, filtré par `capital_preset_key` lorsque la colonne est
    présente. Cette fonction permet à l'IHM d'avertir l'opérateur avant de
    lancer réellement le subprocess.
    """
    start_date = _coerce_date(start)
    end_date = _coerce_date(end)
    if start_date is None or end_date is None or start_date > end_date:
        return {
            "status": "invalid_input",
            "reason": "dates invalides ou incohérentes pour le diagnostic PIT",
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
            "capital_preset_key": capital_preset_key,
            "rows": 0,
            "snapshot_days": 0,
            "first_snapshot_date": None,
            "last_snapshot_date": None,
            "query_error": None,
        }

    preset_column_query = "SHOW COLUMNS FROM stock_scores_history LIKE 'capital_preset_key'"
    preset_column_present_raw, preset_column_error = _safe_scalar_with_error(preset_column_query)
    has_capital_preset_key = bool(preset_column_present_raw) and preset_column_error is None

    filters = ["snapshot_date BETWEEN :start AND :end", "is_candidate = 1"]
    params: dict[str, object] = {"start": start_date.isoformat(), "end": end_date.isoformat()}
    if has_capital_preset_key and capital_preset_key:
        filters.append("capital_preset_key = :capital_preset_key")
        params["capital_preset_key"] = capital_preset_key

    where_clause = " AND ".join(filters)
    rows_raw, rows_error = _safe_scalar_with_error(
        f"SELECT COUNT(*) FROM stock_scores_history WHERE {where_clause}",
        params,
    )
    snapshot_days_raw, snapshot_days_error = _safe_scalar_with_error(
        f"SELECT COUNT(DISTINCT snapshot_date) FROM stock_scores_history WHERE {where_clause}",
        params,
    )
    first_snapshot_raw, first_snapshot_error = _safe_scalar_with_error(
        f"SELECT MIN(snapshot_date) FROM stock_scores_history WHERE {where_clause}",
        params,
    )
    last_snapshot_raw, last_snapshot_error = _safe_scalar_with_error(
        f"SELECT MAX(snapshot_date) FROM stock_scores_history WHERE {where_clause}",
        params,
    )

    query_error = preset_column_error or rows_error or snapshot_days_error or first_snapshot_error or last_snapshot_error
    rows = _coerce_int(rows_raw)
    snapshot_days = _coerce_int(snapshot_days_raw)
    first_snapshot_date = _coerce_date(first_snapshot_raw)
    last_snapshot_date = _coerce_date(last_snapshot_raw)

    status = "available" if query_error is None and rows > 0 else "missing"
    reason = (
        "snapshots PIT disponibles"
        if status == "available"
        else "aucun snapshot PIT candidat détecté sur la plage demandée"
    )
    if query_error:
        status = "unavailable"
        reason = query_error

    return {
        "status": status,
        "reason": reason,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "capital_preset_key": capital_preset_key,
        "capital_preset_filtered": bool(has_capital_preset_key and capital_preset_key),
        "rows": rows,
        "snapshot_days": snapshot_days,
        "first_snapshot_date": first_snapshot_date.isoformat() if first_snapshot_date else None,
        "last_snapshot_date": last_snapshot_date.isoformat() if last_snapshot_date else None,
        "query_error": query_error,
    }


def _serialize_backtesting_ml_missing_rows(df: pd.DataFrame) -> list[dict[str, object]]:
    if df.empty:
        return []
    rows: list[dict[str, object]] = []
    for row in df.to_dict(orient="records"):
        trade_date = _coerce_date(row.get("trade_date"))
        symbol = str(row.get("symbol") or "").strip().upper()
        if trade_date is None or not symbol:
            continue
        rows.append({"trade_date": trade_date.isoformat(), "symbol": symbol})
    return rows


def _serialize_backtesting_ml_missing_days(df: pd.DataFrame) -> list[dict[str, object]]:
    if df.empty:
        return []
    rows: list[dict[str, object]] = []
    for row in df.to_dict(orient="records"):
        trade_date = _coerce_date(row.get("trade_date"))
        if trade_date is None:
            continue
        rows.append(
            {
                "trade_date": trade_date.isoformat(),
                "missing_count": _coerce_int(row.get("missing_count")),
            }
        )
    return rows


@st.cache_data(ttl=60, show_spinner=False)
def get_backtesting_ml_coverage_diagnostic(
    *,
    start: str | date | None,
    end: str | date | None,
    capital_preset_key: str | None,
    engine_mode: str = "pipeline",
    ml_mode: str = "auto",
    ml_pit_strategy: str = "auto",
    missing_sample_limit: int = 25,
    missing_days_limit: int = 15,
) -> dict[str, object]:
    """Diagnostique la couverture PIT de `model_predictions` pour un backtest.

    L'univers attendu est dérivé de `stock_scores_history` (candidats PIT) sur la
    plage demandée, puis comparé aux prédictions persistées dans
    `model_predictions` au niveau `(symbol, prediction_date)`.
    """
    start_date = _coerce_date(start)
    end_date = _coerce_date(end)
    effective_strategy = resolve_ml_pit_strategy(
        engine_mode=engine_mode,
        ml_mode=ml_mode,
        requested_strategy=ml_pit_strategy,
    )
    normalized_engine_mode = str(engine_mode or "research").strip().lower() or "research"
    normalized_ml_mode = str(ml_mode or "auto").strip().lower() or "auto"
    normalized_requested_strategy = str(ml_pit_strategy or "auto").strip().lower() or "auto"
    persist_enabled = normalized_engine_mode != "pipeline"

    if start_date is None or end_date is None or start_date > end_date:
        return {
            "status": "invalid_input",
            "reason": "dates invalides ou incohérentes pour le diagnostic de couverture ML",
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
            "capital_preset_key": capital_preset_key,
            "capital_preset_filtered": False,
            "engine_mode": normalized_engine_mode,
            "ml_mode": normalized_ml_mode,
            "requested_strategy": normalized_requested_strategy,
            "effective_strategy": effective_strategy,
            "persist_enabled": persist_enabled,
            "expected_candidate_symbol_dates": 0,
            "expected_snapshot_days": 0,
            "expected_symbols": 0,
            "covered_prediction_symbol_dates": 0,
            "covered_snapshot_days": 0,
            "covered_symbols": 0,
            "missing_prediction_symbol_dates": 0,
            "missing_snapshot_days": 0,
            "missing_symbols": 0,
            "coverage_pct": 0.0,
            "first_snapshot_date": None,
            "last_snapshot_date": None,
            "missing_rows_sample": [],
            "missing_days_sample": [],
            "fast_mode_estimate": {
                "strategy": "use-persisted",
                "covered_prediction_symbol_dates": 0,
                "missing_prediction_symbol_dates": 0,
                "coverage_pct": 0.0,
                "summary": "Diagnostic non exécutable tant que les dates restent invalides.",
            },
            "rebuild_missing_estimate": {
                "strategy": "rebuild-missing",
                "pairs_to_attempt": 0,
                "snapshot_days_to_attempt": 0,
                "symbols_to_attempt": 0,
                "persist_enabled": persist_enabled,
                "summary": "Diagnostic non exécutable tant que les dates restent invalides.",
            },
            "query_error": None,
        }

    if normalized_ml_mode == "off":
        return {
            "status": "disabled",
            "reason": "Mode ML désactivé (`ml_mode=off`) : aucun préflight couverture n'est nécessaire.",
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "capital_preset_key": capital_preset_key,
            "capital_preset_filtered": False,
            "engine_mode": normalized_engine_mode,
            "ml_mode": normalized_ml_mode,
            "requested_strategy": normalized_requested_strategy,
            "effective_strategy": effective_strategy,
            "persist_enabled": persist_enabled,
            "expected_candidate_symbol_dates": 0,
            "expected_snapshot_days": 0,
            "expected_symbols": 0,
            "covered_prediction_symbol_dates": 0,
            "covered_snapshot_days": 0,
            "covered_symbols": 0,
            "missing_prediction_symbol_dates": 0,
            "missing_snapshot_days": 0,
            "missing_symbols": 0,
            "coverage_pct": 0.0,
            "first_snapshot_date": None,
            "last_snapshot_date": None,
            "missing_rows_sample": [],
            "missing_days_sample": [],
            "fast_mode_estimate": {
                "strategy": "use-persisted",
                "covered_prediction_symbol_dates": 0,
                "missing_prediction_symbol_dates": 0,
                "coverage_pct": 0.0,
                "summary": "ML désactivé : le backtest n'utilisera aucune prédiction persistée.",
            },
            "rebuild_missing_estimate": {
                "strategy": "rebuild-missing",
                "pairs_to_attempt": 0,
                "snapshot_days_to_attempt": 0,
                "symbols_to_attempt": 0,
                "persist_enabled": persist_enabled,
                "summary": "ML désactivé : aucune reconstruction n'est prévue.",
            },
            "query_error": None,
        }

    preset_column_query = "SHOW COLUMNS FROM stock_scores_history LIKE 'capital_preset_key'"
    preset_column_present_raw, preset_column_error = _safe_scalar_with_error(preset_column_query)
    has_capital_preset_key = bool(preset_column_present_raw) and preset_column_error is None

    expected_filters = [
        "snapshot_date BETWEEN :start AND :end",
        "COALESCE(is_candidate, 0) = 1",
        "COALESCE(TRIM(symbol), '') <> ''",
    ]
    params: dict[str, object] = {"start": start_date.isoformat(), "end": end_date.isoformat()}
    if has_capital_preset_key and capital_preset_key:
        expected_filters.append("capital_preset_key = :capital_preset_key")
        params["capital_preset_key"] = capital_preset_key

    expected_subquery = (
        "SELECT DISTINCT snapshot_date, UPPER(TRIM(symbol)) AS symbol "
        "FROM stock_scores_history "
        f"WHERE {' AND '.join(expected_filters)}"
    )
    predictions_subquery = (
        "SELECT DISTINCT prediction_date, UPPER(TRIM(symbol)) AS symbol "
        "FROM model_predictions "
        "WHERE prediction_date BETWEEN :start AND :end "
        "  AND COALESCE(TRIM(symbol), '') <> ''"
    )

    counts_df = safe_query(
        f"""
        SELECT COUNT(*) AS expected_candidate_symbol_dates,
               COUNT(DISTINCT expected.snapshot_date) AS expected_snapshot_days,
               COUNT(DISTINCT expected.symbol) AS expected_symbols,
               COUNT(CASE WHEN preds.symbol IS NOT NULL THEN 1 END) AS covered_prediction_symbol_dates,
               COUNT(DISTINCT CASE WHEN preds.symbol IS NOT NULL THEN expected.snapshot_date END) AS covered_snapshot_days,
               COUNT(DISTINCT CASE WHEN preds.symbol IS NOT NULL THEN expected.symbol END) AS covered_symbols,
               COUNT(CASE WHEN preds.symbol IS NULL THEN 1 END) AS missing_prediction_symbol_dates,
               COUNT(DISTINCT CASE WHEN preds.symbol IS NULL THEN expected.snapshot_date END) AS missing_snapshot_days,
               COUNT(DISTINCT CASE WHEN preds.symbol IS NULL THEN expected.symbol END) AS missing_symbols,
               MIN(expected.snapshot_date) AS first_snapshot_date,
               MAX(expected.snapshot_date) AS last_snapshot_date
        FROM ({expected_subquery}) expected
        LEFT JOIN ({predictions_subquery}) preds
               ON preds.prediction_date = expected.snapshot_date
              AND preds.symbol = expected.symbol
        """,
        params,
    )
    counts_error = get_last_query_error()

    missing_rows_sample: list[dict[str, object]] = []
    missing_days_sample: list[dict[str, object]] = []
    query_error = preset_column_error or counts_error

    if query_error is None:
        missing_params: dict[str, object] = dict(params)
        missing_params["missing_sample_limit"] = int(max(missing_sample_limit, 0))
        missing_params["missing_days_limit"] = int(max(missing_days_limit, 0))
        missing_rows_df = safe_query(
            f"""
            SELECT expected.snapshot_date AS trade_date,
                   expected.symbol AS symbol
            FROM ({expected_subquery}) expected
            LEFT JOIN ({predictions_subquery}) preds
                   ON preds.prediction_date = expected.snapshot_date
                  AND preds.symbol = expected.symbol
            WHERE preds.symbol IS NULL
            ORDER BY expected.snapshot_date ASC, expected.symbol ASC
            LIMIT :missing_sample_limit
            """,
            missing_params,
        )
        missing_rows_error = get_last_query_error()
        if missing_rows_error is None:
            missing_rows_sample = _serialize_backtesting_ml_missing_rows(missing_rows_df)
        else:
            query_error = missing_rows_error

    if query_error is None:
        missing_days_params: dict[str, object] = dict(params)
        missing_days_params["missing_days_limit"] = int(max(missing_days_limit, 0))
        missing_days_df = safe_query(
            f"""
            SELECT expected.snapshot_date AS trade_date,
                   COUNT(*) AS missing_count
            FROM ({expected_subquery}) expected
            LEFT JOIN ({predictions_subquery}) preds
                   ON preds.prediction_date = expected.snapshot_date
                  AND preds.symbol = expected.symbol
            WHERE preds.symbol IS NULL
            GROUP BY expected.snapshot_date
            ORDER BY expected.snapshot_date ASC
            LIMIT :missing_days_limit
            """,
            missing_days_params,
        )
        missing_days_error = get_last_query_error()
        if missing_days_error is None:
            missing_days_sample = _serialize_backtesting_ml_missing_days(missing_days_df)
        else:
            query_error = missing_days_error

    if query_error:
        return {
            "status": "unavailable",
            "reason": query_error,
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "capital_preset_key": capital_preset_key,
            "capital_preset_filtered": bool(has_capital_preset_key and capital_preset_key),
            "engine_mode": normalized_engine_mode,
            "ml_mode": normalized_ml_mode,
            "requested_strategy": normalized_requested_strategy,
            "effective_strategy": effective_strategy,
            "persist_enabled": persist_enabled,
            "expected_candidate_symbol_dates": 0,
            "expected_snapshot_days": 0,
            "expected_symbols": 0,
            "covered_prediction_symbol_dates": 0,
            "covered_snapshot_days": 0,
            "covered_symbols": 0,
            "missing_prediction_symbol_dates": 0,
            "missing_snapshot_days": 0,
            "missing_symbols": 0,
            "coverage_pct": 0.0,
            "first_snapshot_date": None,
            "last_snapshot_date": None,
            "missing_rows_sample": [],
            "missing_days_sample": [],
            "fast_mode_estimate": {
                "strategy": "use-persisted",
                "covered_prediction_symbol_dates": 0,
                "missing_prediction_symbol_dates": 0,
                "coverage_pct": 0.0,
                "summary": "Diagnostic indisponible : impossible d'estimer le mode rapide.",
            },
            "rebuild_missing_estimate": {
                "strategy": "rebuild-missing",
                "pairs_to_attempt": 0,
                "snapshot_days_to_attempt": 0,
                "symbols_to_attempt": 0,
                "persist_enabled": persist_enabled,
                "summary": "Diagnostic indisponible : impossible d'estimer rebuild-missing.",
            },
            "query_error": query_error,
        }

    row = counts_df.iloc[0].to_dict() if not counts_df.empty else {}
    expected_candidate_symbol_dates = _coerce_int(row.get("expected_candidate_symbol_dates"))
    expected_snapshot_days = _coerce_int(row.get("expected_snapshot_days"))
    expected_symbols = _coerce_int(row.get("expected_symbols"))
    covered_prediction_symbol_dates = _coerce_int(row.get("covered_prediction_symbol_dates"))
    covered_snapshot_days = _coerce_int(row.get("covered_snapshot_days"))
    covered_symbols = _coerce_int(row.get("covered_symbols"))
    missing_prediction_symbol_dates = _coerce_int(row.get("missing_prediction_symbol_dates"))
    missing_snapshot_days = _coerce_int(row.get("missing_snapshot_days"))
    missing_symbols = _coerce_int(row.get("missing_symbols"))
    first_snapshot_date = _coerce_date(row.get("first_snapshot_date"))
    last_snapshot_date = _coerce_date(row.get("last_snapshot_date"))
    coverage_pct = _coverage_pct(covered_prediction_symbol_dates, expected_candidate_symbol_dates)

    if expected_candidate_symbol_dates <= 0:
        status = "missing_expected_history"
        reason = "Aucun candidat PIT attendu n'a été détecté dans stock_scores_history sur la plage demandée."
    elif missing_prediction_symbol_dates <= 0:
        status = "complete"
        reason = "Couverture ML PIT complète : toutes les paires symbole×date attendues sont déjà persistées."
    elif covered_prediction_symbol_dates <= 0:
        status = "missing"
        reason = "Aucune paire symbole×date attendue n'est couverte dans model_predictions."
    else:
        status = "partial"
        reason = "Couverture ML PIT partielle : une partie des prédictions attendues manque encore."

    fast_mode_summary = (
        f"Mode rapide (`use-persisted`) : {covered_prediction_symbol_dates}/{expected_candidate_symbol_dates} "
        f"paire(s) symbole×date déjà couvertes ({coverage_pct:.1f}%) ; "
        f"{missing_prediction_symbol_dates} resteraient sans ML."
    )
    rebuild_mode_summary = (
        f"`rebuild-missing` tenterait {missing_prediction_symbol_dates} prédiction(s) sur "
        f"{missing_snapshot_days} séance(s) pour {missing_symbols} symbole(s) distinct(s)"
        f"{' avec writeback DB possible' if persist_enabled else ' sans writeback DB (mode pipeline)'}"
        "."
    )
    fast_mode_estimate: dict[str, object] = {
        "strategy": "use-persisted",
        "covered_prediction_symbol_dates": covered_prediction_symbol_dates,
        "missing_prediction_symbol_dates": missing_prediction_symbol_dates,
        "coverage_pct": coverage_pct,
        "summary": fast_mode_summary,
    }
    rebuild_missing_estimate: dict[str, object] = {
        "strategy": "rebuild-missing",
        "pairs_to_attempt": missing_prediction_symbol_dates,
        "snapshot_days_to_attempt": missing_snapshot_days,
        "symbols_to_attempt": missing_symbols,
        "persist_enabled": persist_enabled,
        "summary": rebuild_mode_summary,
    }

    return {
        "status": status,
        "reason": reason,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "capital_preset_key": capital_preset_key,
        "capital_preset_filtered": bool(has_capital_preset_key and capital_preset_key),
        "engine_mode": normalized_engine_mode,
        "ml_mode": normalized_ml_mode,
        "requested_strategy": normalized_requested_strategy,
        "effective_strategy": effective_strategy,
        "persist_enabled": persist_enabled,
        "expected_candidate_symbol_dates": expected_candidate_symbol_dates,
        "expected_snapshot_days": expected_snapshot_days,
        "expected_symbols": expected_symbols,
        "covered_prediction_symbol_dates": covered_prediction_symbol_dates,
        "covered_snapshot_days": covered_snapshot_days,
        "covered_symbols": covered_symbols,
        "missing_prediction_symbol_dates": missing_prediction_symbol_dates,
        "missing_snapshot_days": missing_snapshot_days,
        "missing_symbols": missing_symbols,
        "coverage_pct": coverage_pct,
        "first_snapshot_date": first_snapshot_date.isoformat() if first_snapshot_date else None,
        "last_snapshot_date": last_snapshot_date.isoformat() if last_snapshot_date else None,
        "missing_rows_sample": missing_rows_sample,
        "missing_days_sample": missing_days_sample,
        "fast_mode_estimate": fast_mode_estimate,
        "rebuild_missing_estimate": rebuild_missing_estimate,
        "query_error": None,
    }


@st.cache_data(ttl=60, show_spinner=False)
def get_stock_bars_daily_symbol_count() -> int:
    v = safe_scalar(
        "SELECT COUNT(DISTINCT symbol) FROM stock_bars_daily WHERE COALESCE(TRIM(symbol), '') <> ''"
    )
    return int(v) if v is not None else 0


@st.cache_data(ttl=60, show_spinner=False)
def get_top_candidates(n: int = 10) -> pd.DataFrame:
    return safe_query(f"""
        SELECT symbol, sector, final_score_sentiment, final_score, total_score, is_candidate
        FROM stock_scores
        WHERE is_candidate = 1 AND final_score_sentiment IS NOT NULL
        ORDER BY final_score_sentiment DESC
        LIMIT {n}
    """)


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_risk_run_id() -> str | None:
    v = safe_scalar("SELECT run_id FROM portfolio_targets ORDER BY created_at DESC LIMIT 1")
    return str(v) if v else None


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_exec_run() -> pd.DataFrame:
    return safe_query("""
        SELECT exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
               status, started_at, completed_at, total_targets, total_submitted, total_filled, error_message
        FROM execution_runs ORDER BY started_at DESC LIMIT 1
    """)


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_stock_scores() -> pd.DataFrame:
    available_columns = _get_table_columns("stock_scores")
    query = _build_stock_scores_query(available_columns)
    return _attach_candidate_explainability_payloads(safe_query(query))


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_risk_run_ids() -> list[str]:
    df = safe_query("SELECT DISTINCT run_id FROM risk_decisions ORDER BY run_id DESC LIMIT 50")
    return df["run_id"].tolist() if not df.empty else []


@st.cache_data(ttl=60, show_spinner=False)
def get_risk_decisions(run_id: str | None = None) -> pd.DataFrame:
    if run_id:
        return safe_query("""
            SELECT * FROM risk_decisions
            WHERE run_id = :run_id
            ORDER BY COALESCE(candidate_rank, 999999), created_at DESC
        """, {"run_id": run_id})
    return safe_query("SELECT * FROM risk_decisions ORDER BY COALESCE(candidate_rank, 999999), created_at DESC LIMIT 200")


@st.cache_data(ttl=60, show_spinner=False)
def get_portfolio_targets(run_id: str | None = None) -> pd.DataFrame:
    if run_id:
        return safe_query("""
            SELECT * FROM portfolio_targets
            WHERE run_id = :run_id
            ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
        """, {"run_id": run_id})
    return safe_query("""
        SELECT * FROM portfolio_targets
        WHERE run_id = (SELECT run_id FROM portfolio_targets ORDER BY created_at DESC LIMIT 1)
        ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
    """)


@st.cache_data(ttl=60, show_spinner=False)
def get_shadow_drift_runs(live_run_id: str | None = None, limit: int = 20) -> pd.DataFrame:
    params: dict[str, object] | None = None
    if live_run_id:
        params = {"live_run_id": live_run_id}
        return safe_query(
            f"""
            SELECT run_id, compared_at, live_run_id, simulated_run_id,
                   avg_qty_drift_pct, avg_price_drift_pct, avg_conviction_drift,
                   symbols_only_in_live, symbols_only_in_sim, payload, schema_version
            FROM shadow_drift_runs
            WHERE live_run_id = :live_run_id
            ORDER BY compared_at DESC, run_id DESC
            LIMIT {limit}
            """,
            params,
        )
    return safe_query(
        f"""
        SELECT run_id, compared_at, live_run_id, simulated_run_id,
               avg_qty_drift_pct, avg_price_drift_pct, avg_conviction_drift,
               symbols_only_in_live, symbols_only_in_sim, payload, schema_version
        FROM shadow_drift_runs
        ORDER BY compared_at DESC, run_id DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_weights_calibration_runs(
    *,
    run_id: str | None = None,
    scope: str | None = None,
    market_regime_mode: str | None = None,
    horizon_days: int | None = None,
    lookback_months: int | None = None,
    eligible_for_live: bool | None = None,
    calibration_batch_id: str | None = None,
    limit: int = 200,
) -> pd.DataFrame:
    available_columns = _get_table_columns("weights_calibration_runs")
    if not available_columns:
        return pd.DataFrame()

    selected_columns = [
        column
        for column in [
            "run_id",
            "calibrated_at",
            "calibration_batch_id",
            "scope",
            "market_regime_mode",
            "segment_key",
            "horizon_days",
            "lookback_months",
            "distinct_snapshot_days",
            "distinct_symbols",
            "eligible_for_live",
            "eligibility_reason",
            "window_start",
            "window_end",
            "metric_name",
            "metric_value",
            "observations_evaluated",
            "scenarios_evaluated",
            "latest_best_scenario_name",
            "final_value",
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "best_weights",
            "candidates",
            "artifact_dir",
            "git_sha",
            "schema_version",
        ]
        if column in available_columns
    ]
    if not selected_columns:
        selected_columns = ["run_id"]

    params: dict[str, object] = {}
    conditions: list[str] = []
    if run_id:
        params["run_id"] = run_id
        conditions.append("run_id = :run_id")
    if scope:
        params["scope"] = str(scope).strip().lower()
        conditions.append("LOWER(COALESCE(scope, '')) = :scope")
    if market_regime_mode and "market_regime_mode" in available_columns:
        params["market_regime_mode"] = str(market_regime_mode).strip().lower() or "all"
        conditions.append("LOWER(COALESCE(market_regime_mode, 'all')) = :market_regime_mode")
    if horizon_days is not None and "horizon_days" in available_columns:
        params["horizon_days"] = int(horizon_days)
        conditions.append("horizon_days = :horizon_days")
    if lookback_months is not None and "lookback_months" in available_columns:
        params["lookback_months"] = int(lookback_months)
        conditions.append("lookback_months = :lookback_months")
    if eligible_for_live is not None and "eligible_for_live" in available_columns:
        params["eligible_for_live"] = 1 if bool(eligible_for_live) else 0
        conditions.append("COALESCE(eligible_for_live, 0) = :eligible_for_live")
    if calibration_batch_id and "calibration_batch_id" in available_columns:
        params["calibration_batch_id"] = str(calibration_batch_id).strip()
        conditions.append("calibration_batch_id = :calibration_batch_id")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return safe_query(
        f"""
        SELECT {', '.join(selected_columns)}
        FROM weights_calibration_runs
        {where_clause}
        ORDER BY COALESCE(window_end, DATE('1970-01-01')) DESC,
                 COALESCE(calibrated_at, window_end) DESC,
                 run_id DESC
        LIMIT {limit}
        """,
        params or None,
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_weights_calibration_run_ids(
    *,
    scope: str | None = None,
    market_regime_mode: str | None = None,
    horizon_days: int | None = None,
    lookback_months: int | None = None,
    eligible_for_live: bool | None = None,
    calibration_batch_id: str | None = None,
    limit: int = 100,
) -> list[str]:
    df = get_weights_calibration_runs(
        scope=scope,
        market_regime_mode=market_regime_mode,
        horizon_days=horizon_days,
        lookback_months=lookback_months,
        eligible_for_live=eligible_for_live,
        calibration_batch_id=calibration_batch_id,
        limit=limit,
    )
    if df.empty or "run_id" not in df.columns:
        return []
    return [str(value).strip() for value in df["run_id"].tolist() if str(value).strip()]


@st.cache_data(ttl=60, show_spinner=False)
def get_weights_calibration_segment_drifts(
    *,
    calibration_batch_id: str | None = None,
    source_run_id: str | None = None,
    comparison_kind: str | None = None,
    limit: int = 200,
) -> pd.DataFrame:
    available_columns = _get_table_columns("weights_calibration_segment_drifts")
    if not available_columns:
        return pd.DataFrame()

    selected_columns = [
        column
        for column in [
            "run_id",
            "compared_at",
            "comparison_kind",
            "calibration_batch_id",
            "source_run_id",
            "target_run_id",
            "source_segment_key",
            "target_segment_key",
            "metric_name",
            "metric_delta",
            "final_value_drift_pct",
            "payload",
            "schema_version",
        ]
        if column in available_columns
    ]
    if not selected_columns:
        selected_columns = ["run_id"]

    params: dict[str, object] = {}
    conditions: list[str] = []
    if calibration_batch_id and "calibration_batch_id" in available_columns:
        params["calibration_batch_id"] = str(calibration_batch_id).strip()
        conditions.append("calibration_batch_id = :calibration_batch_id")
    if source_run_id and "source_run_id" in available_columns:
        params["source_run_id"] = str(source_run_id).strip()
        conditions.append("source_run_id = :source_run_id")
    if comparison_kind and "comparison_kind" in available_columns:
        params["comparison_kind"] = str(comparison_kind).strip()
        conditions.append("comparison_kind = :comparison_kind")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return safe_query(
        f"""
        SELECT {', '.join(selected_columns)}
        FROM weights_calibration_segment_drifts
        {where_clause}
        ORDER BY COALESCE(compared_at, CURRENT_TIMESTAMP) DESC, run_id DESC
        LIMIT {limit}
        """,
        params or None,
    )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@st.cache_data(ttl=15, show_spinner=False)
def get_execution_live_guard(account_id: str | None = None) -> dict[str, object]:
    params: dict[str, object] | None = None
    where_clause = "WHERE status = 'RUNNING' AND LOWER(COALESCE(broker_mode, '')) = 'live'"
    if account_id:
        where_clause += " AND account_id = :account_id"
        params = {"account_id": account_id}
    df = safe_query(
        f"""
        SELECT exec_run_id, account_id, trade_date, broker_mode, status, started_at
        FROM execution_runs
        {where_clause}
        ORDER BY started_at DESC, exec_run_id DESC
        """,
        params,
    )
    if df.empty:
        return {"active": False, "count": 0, "run_ids": [], "accounts": [], "runs": []}
    run_ids = [str(value).strip() for value in df.get("exec_run_id", pd.Series(dtype="object")).tolist() if str(value).strip()]
    accounts = [str(value).strip() for value in df.get("account_id", pd.Series(dtype="object")).tolist() if str(value).strip()]
    return {
        "active": True,
        "count": int(len(df)),
        "run_ids": run_ids,
        "accounts": sorted(set(accounts)),
        "runs": df.to_dict(orient="records"),
    }


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_reconciliation_j1_runs(
    *,
    account_id: str | None = None,
    limit: int = 20,
) -> pd.DataFrame:
    df = get_run_business_summaries(
        limit=limit,
        step_keys=["execution_reconciliation_j1"],
        account_id=account_id,
        run_kind="step",
    )
    if df.empty:
        return df
    expanded = df.copy()
    expanded["trade_date"] = expanded["run_summary"].apply(lambda value: str((value or {}).get("trade_date") or ""))
    expanded["source_kind"] = expanded["run_summary"].apply(lambda value: str((value or {}).get("source_kind") or ""))
    expanded["statement_path"] = expanded["run_summary"].apply(lambda value: str((value or {}).get("statement_path") or ""))
    expanded["activity_count"] = expanded["run_summary"].apply(lambda value: _coerce_int((value or {}).get("activity_count")))
    expanded["inserted"] = expanded["run_summary"].apply(lambda value: _coerce_int((value or {}).get("inserted")))
    expanded["diff_count"] = expanded["run_summary"].apply(lambda value: _coerce_int((value or {}).get("diff_count")))
    expanded["diff_types"] = expanded["run_summary"].apply(lambda value: (value or {}).get("diff_types") or {})
    expanded["diff_types_label"] = expanded["diff_types"].apply(
        lambda value: ", ".join(f"{key}={val}" for key, val in sorted(dict(value).items())) if isinstance(value, dict) and value else "aucun"
    )
    return expanded


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_reconciliation_j1_diff_rows(
    *,
    account_id: str | None = None,
    trade_date: str | None = None,
) -> pd.DataFrame:
    runs = get_execution_reconciliation_j1_runs(account_id=account_id, limit=50)
    if runs.empty:
        return pd.DataFrame()
    if trade_date:
        filtered = runs[runs["trade_date"].astype(str) == str(trade_date)]
        if filtered.empty:
            return pd.DataFrame()
        summary = filtered.iloc[0].get("run_summary")
    else:
        summary = runs.iloc[0].get("run_summary")
    diffs = (summary or {}).get("diffs") if isinstance(summary, dict) else []
    return pd.DataFrame(diffs if isinstance(diffs, list) else [])


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_tca_aggregates(
    *,
    account_id: str | None = None,
    exec_run_id: str | None = None,
) -> dict[str, pd.DataFrame]:
    conditions: list[str] = []
    params: dict[str, object] = {}
    if account_id:
        conditions.append("account_id = :account_id")
        params["account_id"] = account_id
    if exec_run_id:
        conditions.append("exec_run_id = :exec_run_id")
        params["exec_run_id"] = exec_run_id
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    fills = safe_query(
        f"""
        SELECT account_id, exec_run_id, symbol, filled_qty, avg_fill_price,
               fill_timestamp, slippage_bps, implementation_shortfall
        FROM execution_broker_fills
        {where_clause}
        ORDER BY fill_timestamp DESC, fill_id DESC
        """,
        params or None,
    )
    if fills.empty:
        empty = pd.DataFrame()
        return {"monthly": empty, "by_bucket": empty, "by_run": empty}
    return {
        "monthly": build_tca_aggregate_frame(fills, group_by=("account_id", "month")),
        "by_bucket": build_tca_aggregate_frame(fills, group_by=("account_id", "slippage_bucket")),
        "by_run": build_tca_aggregate_frame(fills, group_by=("account_id", "exec_run_id")),
    }

@st.cache_data(ttl=60, show_spinner=False)
def get_execution_runs(limit: int = 20, account_id: str | None = None) -> pd.DataFrame:
    if account_id:
        return safe_query(f"""
            SELECT exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
                   status, started_at, completed_at, total_targets, total_submitted,
                   total_filled, error_message, account_id, execution_profile, submission_window
            FROM execution_runs WHERE account_id = :account_id ORDER BY started_at DESC LIMIT {limit}
        """, {"account_id": account_id})
    return safe_query(f"""
        SELECT exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
               status, started_at, completed_at, total_targets, total_submitted,
               total_filled, error_message, account_id, execution_profile, submission_window
        FROM execution_runs ORDER BY started_at DESC LIMIT {limit}
    """)


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_events(exec_run_id: str | None = None) -> pd.DataFrame:
    if exec_run_id:
        return safe_query("""
            SELECT event_type, symbol, message, payload_json, created_at
            FROM execution_events WHERE exec_run_id = :eid ORDER BY created_at DESC
        """, {"eid": exec_run_id})
    return safe_query("SELECT event_type, symbol, message, payload_json, created_at FROM execution_events ORDER BY created_at DESC LIMIT 100")


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_orders(
    exec_run_id: str | None = None,
    account_id: str | None = None,
) -> pd.DataFrame:
    params: dict[str, object] | None = {"eid": exec_run_id} if exec_run_id else None
    query = """
        SELECT req.exec_run_id,
               req.risk_run_id,
               req.symbol,
               req.request_id AS intent_id,
               req.parent_request_id AS parent_intent_id,
               req.intent_role,
               bo.broker_order_id,
               req.side,
               req.target_qty AS qty,
               COALESCE(bo.filled_qty, fill_agg.filled_qty, 0) AS filled_qty,
               COALESCE(bo.avg_fill_price, fill_agg.avg_fill_price) AS avg_fill_price,
               req.order_type,
               req.limit_price,
               req.stop_price,
               req.trail_percent,
               req.decision_price,
               COALESCE(bo.normalized_status, req.status) AS status,
               req.created_at,
               COALESCE(bo.last_seen_at, req.updated_at) AS updated_at,
               req.business_key AS idempotency_key,
               req.submission_key,
               req.attempt_no,
               bo.client_order_id,
               req.account_id
        FROM execution_order_requests req
        LEFT JOIN execution_broker_orders bo
               ON bo.request_id = req.request_id
        LEFT JOIN (
            SELECT request_id,
                   SUM(filled_qty) AS filled_qty,
                   CASE
                       WHEN SUM(filled_qty) > 0 THEN SUM(filled_qty * avg_fill_price) / SUM(filled_qty)
                       ELSE AVG(avg_fill_price)
                   END AS avg_fill_price
            FROM execution_broker_fills
            GROUP BY request_id
        ) fill_agg
               ON fill_agg.request_id = req.request_id
    """
    if exec_run_id:
        query += """
        WHERE req.exec_run_id = :eid
        ORDER BY CASE WHEN req.parent_request_id IS NULL THEN 0 ELSE 1 END,
                 COALESCE(req.parent_request_id, req.request_id), req.created_at DESC
        """
    elif account_id:
        params = {"account_id": account_id}
        query += """
        WHERE req.account_id = :account_id
        ORDER BY COALESCE(bo.last_seen_at, req.updated_at, req.created_at) DESC,
                 req.created_at DESC
        LIMIT 200
        """
    else:
        query += """
        ORDER BY req.created_at DESC
        LIMIT 200
        """
    return safe_query(query, params)


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_account_constraints(exec_run_id: str) -> dict[str, object]:
    df = safe_query(
        """
        SELECT message, payload_json, created_at
        FROM execution_events
        WHERE exec_run_id = :eid AND event_type = 'ACCOUNT_CONSTRAINT_APPLIED'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"eid": exec_run_id},
    )
    if not df.empty:
        row = df.iloc[0]
        payload = _parse_json_object(row.get("payload_json"))
        payload.setdefault("message", row.get("message", ""))
        payload.setdefault("created_at", row.get("created_at"))
        return payload

    snapshot_df = safe_query(
        """
        SELECT snapshot_kind, equity, cash, settled_cash, buying_power,
               daytrade_count, raw_payload_json, created_at
        FROM broker_account_snapshots
        WHERE exec_run_id = :eid
          AND snapshot_kind = 'preflight'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"eid": exec_run_id},
    )
    if snapshot_df.empty:
        return {}
    row = snapshot_df.iloc[0]
    payload = _parse_json_object(row.get("raw_payload_json"))
    payload.setdefault("equity", row.get("equity"))
    payload.setdefault("cash", row.get("cash"))
    payload.setdefault("settled_cash", row.get("settled_cash"))
    payload.setdefault("buying_power", row.get("buying_power"))
    payload.setdefault("buying_power_available", row.get("buying_power"))
    payload.setdefault("settled_cash_available", row.get("settled_cash"))
    payload.setdefault("daytrade_count", row.get("daytrade_count"))
    payload.setdefault("created_at", row.get("created_at"))
    payload.setdefault("message", "Contraintes relues depuis le snapshot broker preflight.")
    return payload


@st.cache_data(ttl=60, show_spinner=False)
def get_broker_positions(account_id: str | None = None) -> pd.DataFrame:
    if account_id:
        return safe_query("""
            SELECT bps.* FROM broker_positions_snapshots bps
            INNER JOIN (
                SELECT MAX(created_at) AS mx FROM broker_positions_snapshots WHERE account_id = :account_id
            ) t ON bps.created_at = t.mx
            WHERE bps.account_id = :account_id
            ORDER BY market_value DESC
        """, {"account_id": account_id})
    return safe_query("""
        SELECT bps.* FROM broker_positions_snapshots bps
        INNER JOIN (SELECT MAX(created_at) AS mx FROM broker_positions_snapshots) t ON bps.created_at = t.mx
        ORDER BY market_value DESC
    """)


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_fills(
    exec_run_id: str | None = None,
) -> pd.DataFrame:
    if exec_run_id:
        return safe_query(
            """
            SELECT exec_run_id,
                   fill_id,
                   broker_order_id,
                   request_id AS intent_id,
                   symbol,
                   filled_qty,
                   avg_fill_price,
                   fill_timestamp,
                   decision_price,
                   slippage_bps,
                   implementation_shortfall,
                   account_id,
                   created_at
            FROM execution_broker_fills
            WHERE exec_run_id = :eid
            ORDER BY fill_timestamp DESC
            """,
            {"eid": exec_run_id},
        )
    return safe_query(
        """
        SELECT exec_run_id,
               fill_id,
               broker_order_id,
               request_id AS intent_id,
               symbol,
               filled_qty,
               avg_fill_price,
               fill_timestamp,
               decision_price,
               slippage_bps,
               implementation_shortfall,
               account_id,
               created_at
        FROM execution_broker_fills
        ORDER BY fill_timestamp DESC
        LIMIT 100
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_targets_snapshot(exec_run_id: str) -> pd.DataFrame:
    available_columns = _get_table_columns("execution_targets_snapshot")
    selected_columns = [
        "exec_run_id",
        "account_id",
        "risk_run_id",
        "trade_date",
        "symbol",
        *(
            ["candidate_rank"]
            if "candidate_rank" in available_columns
            else []
        ),
        "decision_rank",
        *(
            ["selector_signal_mode", "selection_explanation", "selector_earnings_blackout"]
            if {"selector_signal_mode", "selection_explanation", "selector_earnings_blackout"} & available_columns
            else []
        ),
        "side",
        "target_shares",
        "entry_price",
        "target_weight",
        "stop_price_initial",
        "risk_per_share",
        "risk_budget_dollars",
        "initial_risk_dollars",
        "target_notional",
        "price_asof_date",
        "atr_asof_date",
        "created_at",
    ]
    selected_columns = [column for column in selected_columns if column in available_columns]
    if not selected_columns:
        selected_columns = ["exec_run_id", "risk_run_id", "trade_date", "symbol", "target_shares", "entry_price"]
    return safe_query(
        f"""
        SELECT {', '.join(selected_columns)}
        FROM execution_targets_snapshot
        WHERE exec_run_id = :eid
        ORDER BY COALESCE(decision_rank, 999999), target_weight DESC, symbol ASC
        """,
        {"eid": exec_run_id},
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_broker_account_snapshots_history(account_id: str, limit: int = 200) -> pd.DataFrame:
    return safe_query(
        f"""
        SELECT exec_run_id, account_id, broker_mode, snapshot_kind,
               equity, cash, settled_cash, buying_power, daytrade_count,
               raw_payload_json, created_at
        FROM broker_account_snapshots
        WHERE account_id = :account_id
        ORDER BY created_at DESC
        LIMIT {limit}
        """,
        {"account_id": account_id},
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_positions(
    *,
    account_id: str | None = None,
    exec_run_id: str | None = None,
    allow_account_fallback: bool = True,
) -> pd.DataFrame:
    if exec_run_id:
        df = safe_query(
            """
            SELECT account_id, symbol, net_qty, avg_entry_price, market_price,
                   market_value, unrealized_pnl, broker_mode, source_exec_run_id,
                   position_status, last_broker_snapshot_at, updated_at
            FROM execution_positions
            WHERE source_exec_run_id = :eid
            ORDER BY CASE WHEN position_status = 'FLAT' THEN 1 ELSE 0 END,
                     ABS(net_qty) DESC, symbol ASC
            """,
            {"eid": exec_run_id},
        )
        if not df.empty or not allow_account_fallback:
            return df
    if account_id:
        return safe_query(
            """
            SELECT account_id, symbol, net_qty, avg_entry_price, market_price,
                   market_value, unrealized_pnl, broker_mode, source_exec_run_id,
                   position_status, last_broker_snapshot_at, updated_at
            FROM execution_positions
            WHERE account_id = :account_id
            ORDER BY CASE WHEN position_status = 'FLAT' THEN 1 ELSE 0 END,
                     ABS(net_qty) DESC, symbol ASC
            """,
            {"account_id": account_id},
        )
    return safe_query(
        """
        SELECT account_id, symbol, net_qty, avg_entry_price, market_price,
               market_value, unrealized_pnl, broker_mode, source_exec_run_id,
               position_status, last_broker_snapshot_at, updated_at
        FROM execution_positions
        ORDER BY updated_at DESC, account_id ASC, symbol ASC
        LIMIT 200
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_position_lots(
    *,
    account_id: str | None = None,
    exec_run_id: str | None = None,
    allow_account_fallback: bool = True,
) -> pd.DataFrame:
    if exec_run_id:
        df = safe_query(
            """
            SELECT lot_id, account_id, symbol, opened_qty, remaining_qty, entry_price,
                   opened_at, open_exec_run_id, open_request_id, open_fill_id, lot_status,
                   close_exec_run_id, close_request_id, close_fill_id, closed_at, exit_price,
                   source_kind, updated_at
            FROM execution_position_lots
            WHERE open_exec_run_id = :eid OR close_exec_run_id = :eid
            ORDER BY COALESCE(closed_at, opened_at) DESC, lot_id DESC
            LIMIT 500
            """,
            {"eid": exec_run_id},
        )
        if not df.empty or not allow_account_fallback:
            return df
    if account_id:
        return safe_query(
            """
            SELECT lot_id, account_id, symbol, opened_qty, remaining_qty, entry_price,
                   opened_at, open_exec_run_id, open_request_id, open_fill_id, lot_status,
                   close_exec_run_id, close_request_id, close_fill_id, closed_at, exit_price,
                   source_kind, updated_at
            FROM execution_position_lots
            WHERE account_id = :account_id
            ORDER BY opened_at DESC, lot_id DESC
            LIMIT 500
            """,
            {"account_id": account_id},
        )
    return safe_query(
        """
        SELECT lot_id, account_id, symbol, opened_qty, remaining_qty, entry_price,
               opened_at, open_exec_run_id, open_request_id, open_fill_id, lot_status,
               close_exec_run_id, close_request_id, close_fill_id, closed_at, exit_price,
               source_kind, updated_at
        FROM execution_position_lots
        ORDER BY opened_at DESC, lot_id DESC
        LIMIT 500
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_execution_reconciliation_results(
    *,
    exec_run_id: str | None = None,
    account_id: str | None = None,
    allow_account_fallback: bool = True,
) -> pd.DataFrame:
    severity_order_sql = """
        CASE reconciliation_status
            WHEN 'BLOCKED' THEN 0
            WHEN 'MANUAL_REVIEW' THEN 1
            WHEN 'SAFE_AUTO' THEN 2
            ELSE 3
        END,
        CASE action
            WHEN 'investigate' THEN 0
            WHEN 'sell_excess' THEN 1
            WHEN 'buy_more' THEN 2
            WHEN 'none' THEN 3
            ELSE 4
        END,
        symbol ASC
    """
    if exec_run_id:
        df = safe_query(
            f"""
            SELECT exec_run_id, account_id, symbol, target_qty, internal_position_qty,
                   broker_position_qty, position_delta, open_request_buy_qty,
                   open_request_sell_qty, open_broker_buy_qty, open_broker_sell_qty,
                   has_open_protection, protection_qty, action,
                   reconciliation_status, reason_code, created_at
            FROM execution_reconciliation_results
            WHERE exec_run_id = :eid
            ORDER BY {severity_order_sql}
            """,
            {"eid": exec_run_id},
        )
        if not df.empty or not allow_account_fallback:
            return df
    if account_id:
        return safe_query(
            f"""
            SELECT exec_run_id, account_id, symbol, target_qty, internal_position_qty,
                   broker_position_qty, position_delta, open_request_buy_qty,
                   open_request_sell_qty, open_broker_buy_qty, open_broker_sell_qty,
                   has_open_protection, protection_qty, action,
                   reconciliation_status, reason_code, created_at
            FROM execution_reconciliation_results
            WHERE account_id = :account_id
            ORDER BY {severity_order_sql}
            LIMIT 500
            """,
            {"account_id": account_id},
        )
    return safe_query(
        f"""
        SELECT exec_run_id, account_id, symbol, target_qty, internal_position_qty,
               broker_position_qty, position_delta, open_request_buy_qty,
               open_request_sell_qty, open_broker_buy_qty, open_broker_sell_qty,
               has_open_protection, protection_qty, action,
               reconciliation_status, reason_code, created_at
        FROM execution_reconciliation_results
        ORDER BY created_at DESC, {severity_order_sql}
        LIMIT 500
        """
    )


# ---------------------------------------------------------------------------
# Corporate Actions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_ca_events_summary() -> pd.DataFrame:
    return safe_query("""
        SELECT status, ca_type, COUNT(*) as cnt
        FROM corporate_actions_events GROUP BY status, ca_type ORDER BY status, ca_type
    """)


@st.cache_data(ttl=60, show_spinner=False)
def get_ca_events(limit: int = 100) -> pd.DataFrame:
    return safe_query(f"SELECT * FROM corporate_actions_events ORDER BY ex_date DESC LIMIT {limit}")


@st.cache_data(ttl=60, show_spinner=False)
def get_ca_applications(limit: int = 50) -> pd.DataFrame:
    return safe_query(f"SELECT * FROM corporate_actions_applications ORDER BY applied_at DESC LIMIT {limit}")


@st.cache_data(ttl=60, show_spinner=False)
def get_total_dividends() -> float:
    v = safe_scalar("SELECT COALESCE(SUM(amount), 0) FROM portfolio_cash_ledger WHERE entry_type = 'dividend_credit'")
    return float(v) if v is not None else 0.0


# ---------------------------------------------------------------------------
# ML
# ---------------------------------------------------------------------------

def _normalize_filter_values(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        text_value = str(value).strip()
        if text_value:
            normalized.append(text_value)
    return normalized


def _append_in_clause(
    conditions: list[str],
    params: dict[str, object],
    *,
    column_sql: str,
    param_prefix: str,
    values: list[str] | None,
) -> None:
    normalized = _normalize_filter_values(values)
    if not normalized:
        return
    placeholders: list[str] = []
    for index, value in enumerate(normalized):
        param_name = f"{param_prefix}_{index}"
        params[param_name] = value
        placeholders.append(f":{param_name}")
    conditions.append(f"{column_sql} IN ({', '.join(placeholders)})")


@st.cache_data(ttl=60, show_spinner=False)
def get_run_business_summaries(
    *,
    limit: int = 50,
    step_keys: list[str] | None = None,
    entity_run_id: str | None = None,
    account_id: str | None = None,
    run_kind: str | None = None,
) -> pd.DataFrame:
    params: dict[str, object] = {}
    conditions: list[str] = []
    if entity_run_id:
        params["entity_run_id"] = entity_run_id
        conditions.append("entity_run_id = :entity_run_id")
    if account_id:
        params["account_id"] = account_id
        conditions.append("account_id = :account_id")
    if run_kind:
        params["run_kind"] = run_kind
        conditions.append("run_kind = :run_kind")
    _append_in_clause(conditions, params, column_sql="step_key", param_prefix="summary_step_key", values=step_keys)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    df = safe_query(
        f"""
        SELECT summary_run_id, source_run_id, entity_run_id, parent_summary_run_id,
               step_key, run_kind, status, account_id, trade_date, started_at, finished_at,
               summary_json, created_at, updated_at
        FROM run_business_summaries
        {where_clause}
        ORDER BY COALESCE(finished_at, started_at, created_at) DESC, summary_run_id DESC
        LIMIT {limit}
        """,
        params or None,
    )
    if df.empty:
        return df

    df = df.copy()
    df["run_summary"] = df["summary_json"].apply(parse_summary_json)
    df["summary_caption"] = df.apply(
        lambda row: build_run_summary_caption({"step_key": row.get("step_key"), "run_summary": row.get("run_summary")}),
        axis=1,
    )
    return df


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_run_business_summary(
    *,
    step_key: str,
    entity_run_id: str | None = None,
    account_id: str | None = None,
    run_kind: str | None = None,
) -> dict[str, object] | None:
    df = get_run_business_summaries(
        limit=1,
        step_keys=[step_key],
        entity_run_id=entity_run_id,
        account_id=account_id,
        run_kind=run_kind,
    )
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    return row if isinstance(row, dict) else None


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_execution_protection_watch_service_summary(
    *,
    account_id: str | None = None,
    exec_run_id: str | None = None,
) -> dict[str, object] | None:
    if exec_run_id:
        scoped = get_latest_run_business_summary(
            step_key="execution_protection_watch_service",
            entity_run_id=exec_run_id,
            account_id=account_id,
            run_kind="service",
        )
        if scoped:
            return scoped
    return get_latest_run_business_summary(
        step_key="execution_protection_watch_service",
        account_id=account_id,
        run_kind="service",
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_ops_service_summaries(
    *,
    account_id: str | None = None,
    limit: int = 20,
) -> pd.DataFrame:
    return get_run_business_summaries(
        limit=limit,
        step_keys=["execution_protection_watch_service"],
        account_id=account_id,
        run_kind="service",
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_ops_latest_critical_summaries(
    *,
    account_id: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    return get_run_business_summaries(
        limit=limit,
        step_keys=[
            "pipeline_workflow",
            "risk_management",
            "execution",
            "execution_protection_watch",
            "corporate_actions_run",
        ],
        account_id=account_id,
    )

@st.cache_data(ttl=60, show_spinner=False)
def get_training_runs(limit: int = 20) -> pd.DataFrame:
    return safe_query(f"SELECT * FROM model_training_run ORDER BY started_at DESC LIMIT {limit}")


@st.cache_data(ttl=60, show_spinner=False)
def get_model_metrics() -> pd.DataFrame:
    return safe_query("SELECT * FROM model_metrics ORDER BY symbol, split_name")


@st.cache_data(ttl=60, show_spinner=False)
def get_model_governance(
    limit: int = 200,
    symbol: str | None = None,
    run_ids: list[str] | None = None,
    selection_modes: list[str] | None = None,
) -> pd.DataFrame:
    params: dict[str, object] = {}
    conditions: list[str] = []
    if symbol:
        params["symbol"] = symbol
        conditions.append("symbol = :symbol")
    _append_in_clause(conditions, params, column_sql="run_id", param_prefix="run_id", values=run_ids)
    _append_in_clause(conditions, params, column_sql="selection_mode", param_prefix="selection_mode", values=selection_modes)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return safe_query(f"""
        SELECT run_id, symbol, model_name, `rank`, is_selected_model, selection_mode, selection_metric,
               selection_score, model_status, selection_eligible, eligibility_reason, reason,
               inference_backend, backend_model_name, calibration_method, decision_threshold,
               artifact_symbol, val_auc, test_auc, wf_auc,
               val_threshold_business_score, test_threshold_business_score, wf_threshold_business_score,
               created_at
        FROM model_governance
        {where_clause}
        ORDER BY created_at DESC, run_id DESC, symbol ASC, is_selected_model DESC, `rank` ASC, model_name ASC
        LIMIT {limit}
    """, params or None)


@st.cache_data(ttl=60, show_spinner=False)
def get_prediction_symbols(limit: int = 200) -> list[str]:
    df = safe_query(f"SELECT DISTINCT symbol FROM model_predictions ORDER BY symbol LIMIT {limit}")
    return df["symbol"].tolist() if not df.empty else []


@st.cache_data(ttl=60, show_spinner=False)
def get_predictions(
    limit: int = 100,
    symbol: str | None = None,
    run_ids: list[str] | None = None,
    served_models: list[str] | None = None,
) -> pd.DataFrame:
    params: dict[str, object] = {}
    conditions: list[str] = []
    if symbol:
        params["symbol"] = symbol
        conditions.append("symbol = :symbol")
    _append_in_clause(conditions, params, column_sql="run_id", param_prefix="prediction_run_id", values=run_ids)
    _append_in_clause(conditions, params, column_sql="selected_model", param_prefix="served_model", values=served_models)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return safe_query(f"""
        SELECT symbol, predicted_proba, predicted_class, prediction_date, run_id,
               selected_model, decision_threshold, signal_label, calibration_method, created_at
        FROM model_predictions
        {where_clause}
        ORDER BY prediction_date DESC, symbol LIMIT {limit}
    """, params or None)


@st.cache_data(ttl=60, show_spinner=False)
def get_prediction_governance_audit(
    limit: int = 100,
    symbol: str | None = None,
    run_ids: list[str] | None = None,
    selection_modes: list[str] | None = None,
    served_models: list[str] | None = None,
    governance_link_statuses: list[str] | None = None,
) -> pd.DataFrame:
    params: dict[str, object] = {}
    conditions: list[str] = []
    if symbol:
        params["symbol"] = symbol
        conditions.append("symbol = :symbol")
    _append_in_clause(conditions, params, column_sql="run_id", param_prefix="audit_run_id", values=run_ids)
    _append_in_clause(conditions, params, column_sql="governance_selection_mode", param_prefix="audit_selection_mode", values=selection_modes)
    _append_in_clause(conditions, params, column_sql="served_model", param_prefix="audit_served_model", values=served_models)
    _append_in_clause(
        conditions,
        params,
        column_sql="governance_link_status",
        param_prefix="audit_link_status",
        values=governance_link_statuses,
    )
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return safe_query(
        f"""
        SELECT *
        FROM (
            SELECT p.symbol,
                   p.prediction_date,
                   p.run_id,
                   p.predicted_proba,
                   p.predicted_class,
                   p.selected_model AS served_model,
                   p.decision_threshold AS served_decision_threshold,
                   p.signal_label,
                   p.calibration_method AS served_calibration_method,
                   p.created_at,
                   served.model_name AS governance_served_model,
                   served.`rank` AS governance_served_rank,
                   served.selection_eligible AS governance_served_eligible,
                   served.eligibility_reason AS governance_served_eligibility_reason,
                   served.reason AS governance_served_reason,
                   served.inference_backend AS governance_served_backend,
                   served.backend_model_name AS governance_served_backend_model_name,
                   served.calibration_method AS governance_served_calibration_method,
                   served.decision_threshold AS governance_served_decision_threshold,
                   served.artifact_symbol AS governance_served_artifact_symbol,
                   champion.model_name AS governance_champion_model,
                   champion.selection_mode AS governance_selection_mode,
                   champion.selection_metric AS governance_selection_metric,
                   champion.selection_score AS governance_champion_selection_score,
                   champion.inference_backend AS governance_champion_backend,
                   champion.calibration_method AS governance_champion_calibration_method,
                   champion.decision_threshold AS governance_champion_decision_threshold,
                   champion.artifact_symbol AS governance_champion_artifact_symbol,
                   CASE
                       WHEN champion.run_id IS NULL THEN 'missing_governance_snapshot'
                       WHEN p.selected_model IS NULL OR p.selected_model = '' THEN 'prediction_missing_selected_model'
                       WHEN served.model_name IS NULL THEN 'served_model_missing_in_governance'
                       WHEN champion.model_name <> p.selected_model THEN 'served_model_differs_from_governance_champion'
                       ELSE 'aligned'
                   END AS governance_link_status
            FROM model_predictions p
            LEFT JOIN model_governance served
                   ON served.run_id = p.run_id
                  AND served.symbol = p.symbol
                  AND served.model_name = p.selected_model
            LEFT JOIN model_governance champion
                   ON champion.run_id = p.run_id
                  AND champion.symbol = p.symbol
                  AND champion.is_selected_model = 1
        ) audit
        {where_clause}
        ORDER BY prediction_date DESC, created_at DESC, symbol ASC
        LIMIT {limit}
        """,
        params or None,
    )


# ---------------------------------------------------------------------------
# Sprint S3 / A-015 — Fraîcheur market_cap pour alerte IHM
# ---------------------------------------------------------------------------


def get_stale_market_cap_stats(*, cutoff_days: int = 45) -> dict[str, int | float]:
    """Retourne des statistiques de fraîcheur de ``market_cap_refreshed_at``.

    Returns un dict avec :
    - ``total_symbols`` : total de symboles actifs avec market_cap renseigné
    - ``stale_symbols`` : symboles dont ``market_cap_refreshed_at`` est NULL
      ou antérieur à ``cutoff_days`` jours
    - ``stale_pct`` : pourcentage de symboles périmés (0.0–100.0)
    - ``cutoff_days`` : seuil utilisé
    """
    result = safe_scalar(
        """
        SELECT COUNT(*)
        FROM stock_metadata
        WHERE LOWER(TRIM(COALESCE(status, ''))) = 'active'
          AND COALESCE(tradable, 0) = 1
          AND market_cap IS NOT NULL
        """
    )
    total = int(result or 0)
    if total == 0:
        return {"total_symbols": 0, "stale_symbols": 0, "stale_pct": 0.0, "cutoff_days": cutoff_days}

    stale = safe_scalar(
        """
        SELECT COUNT(*)
        FROM stock_metadata
        WHERE LOWER(TRIM(COALESCE(status, ''))) = 'active'
          AND COALESCE(tradable, 0) = 1
          AND market_cap IS NOT NULL
          AND (
              market_cap_refreshed_at IS NULL
              OR market_cap_refreshed_at < (NOW() - INTERVAL :cutoff_days DAY)
          )
        """,
        {"cutoff_days": cutoff_days},
    )
    stale_count = int(stale or 0)
    return {
        "total_symbols": total,
        "stale_symbols": stale_count,
        "stale_pct": round((stale_count / total) * 100.0, 1) if total > 0 else 0.0,
        "cutoff_days": cutoff_days,
    }


# ---------------------------------------------------------------------------
# Sprint S5 — Compteurs de complétude backfill sentiment (7bis)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=30, show_spinner=False)
def get_backfill_completeness_diagnostic(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    symbols: list[str] | None = None,
    contextual_min_relevance: float | None = None,
) -> dict[str, object]:
    """Retourne les compteurs de complétude des deux backfills 7bis.

    - **Relevance backfill** (Niveau 2/3) : compte les lignes ``news_ticker_map``
      dont ``relevance_score IS NULL`` sur la fenêtre demandée.
    - **Contextual backfill** (Niveau 4 FinBERT) : compte les paires
      ``(article, symbol)`` présentes dans ``news_ticker_map`` mais absentes de
      ``news_ticker_sentiment``. Si ``contextual_min_relevance`` est fourni,
      seules les paires avec ``relevance_score >= seuil`` sont comptées
      (reflète le filtre ``--contextual-min-relevance`` des jobs de scoring).
    - **History backfill** : compare les trade-dates scorées (``news_raw`` ∩
      ``news_sentiment``) avec les dates couvertes dans
      ``ticker_daily_sentiment_features``.  Retourne le nombre de dates
      manquantes et de dates couvertes dans la plage.

    Les paramètres ``start_date`` / ``end_date`` filtrent sur
    ``news_raw.effective_trade_date`` (bornes incluses). Si ``None``, la borne
    correspondante est ignorée.

    Si ``symbols`` est fourni, les compteurs relevance et contextual sont
    restreints aux symboles de cette liste (filtre ``ntm.symbol IN (...)``).
    """
    date_filters_trade = ""
    date_filters_pub = ""
    params: dict[str, object] = {}
    if start_date is not None:
        date_filters_trade += " AND nr.effective_trade_date >= :start_date"
        date_filters_pub += " AND nr.effective_trade_date >= :start_date"
        params["start_date"] = start_date
    if end_date is not None:
        date_filters_trade += " AND nr.effective_trade_date <= :end_date"
        date_filters_pub += " AND nr.effective_trade_date <= :end_date"
        params["end_date"] = end_date

    # --- Filtre symboles (optionnel) ---
    symbol_filter_trade = ""
    if symbols:
        # Utiliser l'interpolation directe (safe : les tickers sont des symboles
        # boursiers alphanumériques, pas du user input libre). Évite les limites
        # de placeholders SQL quand l'univers est large (>1000 symboles).
        escaped = [f"'{sym.replace(chr(39), '')}'" for sym in symbols]
        symbol_filter_trade = f" AND ntm.symbol IN ({', '.join(escaped)})"

    # --- Filtre pertinence contextuelle (optionnel) ---
    contextual_relevance_filter = ""
    if contextual_min_relevance is not None and contextual_min_relevance > 0.0:
        contextual_relevance_filter = (
            f" AND ntm.relevance_score IS NOT NULL"
            f" AND ntm.relevance_score >= {float(contextual_min_relevance):g}"
        )

    # --- Relevance backfill : lignes news_ticker_map sans relevance_score ---
    relevance_null_raw, relevance_null_error = _safe_scalar_with_error(
        f"""
        SELECT COUNT(*)
        FROM news_ticker_map ntm
        JOIN news_raw nr ON nr.article_id = ntm.article_id
        WHERE ntm.relevance_score IS NULL
        {date_filters_trade}
        {symbol_filter_trade}
        """,
        params or None,
    )
    relevance_null = _coerce_int(relevance_null_raw)

    # --- Total lignes news_ticker_map sur la fenêtre (dénominateur) ---
    relevance_total_raw, relevance_total_error = _safe_scalar_with_error(
        f"""
        SELECT COUNT(*)
        FROM news_ticker_map ntm
        JOIN news_raw nr ON nr.article_id = ntm.article_id
        WHERE 1=1
        {date_filters_trade}
        {symbol_filter_trade}
        """,
        params or None,
    )
    relevance_total = _coerce_int(relevance_total_raw)
    relevance_scored = max(0, relevance_total - relevance_null)

    # --- Contextual backfill : paires sans news_ticker_sentiment ---
    contextual_pending_raw, contextual_pending_error = _safe_scalar_with_error(
        f"""
        SELECT COUNT(*)
        FROM news_ticker_map ntm
        JOIN news_raw nr ON nr.article_id = ntm.article_id
        LEFT JOIN news_ticker_sentiment nts
            ON nts.article_id = ntm.article_id AND nts.symbol = ntm.symbol
        WHERE nts.article_id IS NULL
        {date_filters_trade}
        {symbol_filter_trade}
        {contextual_relevance_filter}
        """,
        params or None,
    )
    contextual_pending = _coerce_int(contextual_pending_raw)

    contextual_total_raw, contextual_total_error = _safe_scalar_with_error(
        f"""
        SELECT COUNT(*)
        FROM news_ticker_map ntm
        JOIN news_raw nr ON nr.article_id = ntm.article_id
        WHERE 1=1
        {date_filters_trade}
        {symbol_filter_trade}
        {contextual_relevance_filter}
        """,
        params or None,
    )
    contextual_total = _coerce_int(contextual_total_raw)
    contextual_scored = max(0, contextual_total - contextual_pending)

    # --- History backfill : trade-dates scorées non couvertes par ticker_daily_sentiment_features ---
    history_missing_raw, history_missing_error = _safe_scalar_with_error(
        f"""
        SELECT COUNT(DISTINCT scored.effective_trade_date)
        FROM (
            SELECT DISTINCT nr.effective_trade_date
            FROM news_raw nr
            JOIN news_sentiment ns ON ns.article_id = nr.article_id
            WHERE 1=1
            {date_filters_trade}
        ) scored
        LEFT JOIN ticker_daily_sentiment_features tf
            ON tf.trade_date = scored.effective_trade_date
        WHERE tf.trade_date IS NULL
        """,
        params or None,
    )
    history_missing = _coerce_int(history_missing_raw)

    history_covered_raw, history_covered_error = _safe_scalar_with_error(
        f"""
        SELECT COUNT(DISTINCT tf.trade_date)
        FROM ticker_daily_sentiment_features tf
        WHERE 1=1
        {'AND tf.trade_date >= :start_date' if start_date is not None else ''}
        {'AND tf.trade_date <= :end_date' if end_date is not None else ''}
        """,
        params or None,
    )
    history_covered = _coerce_int(history_covered_raw)

    history_scored_dates_raw, _ = _safe_scalar_with_error(
        f"""
        SELECT COUNT(DISTINCT nr.effective_trade_date)
        FROM news_raw nr
        JOIN news_sentiment ns ON ns.article_id = nr.article_id
        WHERE 1=1
        {date_filters_trade}
        """,
        params or None,
    )
    history_scored_dates = _coerce_int(history_scored_dates_raw)

    query_error = (
        relevance_null_error
        or relevance_total_error
        or contextual_pending_error
        or contextual_total_error
        or history_missing_error
        or history_covered_error
    )

    return {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        # Relevance backfill
        "relevance_null": relevance_null,
        "relevance_scored": relevance_scored,
        "relevance_total": relevance_total,
        "relevance_pct": round(relevance_scored / relevance_total * 100.0, 1) if relevance_total > 0 else 100.0,
        # Contextual backfill
        "contextual_pending": contextual_pending,
        "contextual_scored": contextual_scored,
        "contextual_total": contextual_total,
        "contextual_pct": round(contextual_scored / contextual_total * 100.0, 1) if contextual_total > 0 else 100.0,
        # History backfill
        "history_missing_dates": history_missing,
        "history_covered_dates": history_covered,
        "history_scored_dates": history_scored_dates,
        "history_pct": round(
            history_covered / history_scored_dates * 100.0, 1
        ) if history_scored_dates > 0 else 100.0,
        # Méta
        "query_error": query_error,
    }


# ---------------------------------------------------------------------------
# Sprint S4 / A-021 — PnL quotidien pour la page Overview
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def get_daily_pnl_data() -> dict[str, object]:
    """Retourne les données de PnL brut depuis le dernier snapshot de positions.

    Utilise ``broker_positions_snapshots.unrealized_pnl`` (alimentation Alpaca)
    et les dividendes de ``portfolio_cash_ledger`` pour produire un PnL *day*
    approximatif sans tables supplémentaires.

    Returns:
        dict avec les clés :
        - ``unrealized_pnl`` : float — PnL latent total des positions ouvertes
        - ``total_market_value`` : float — valeur de marché totale
        - ``open_positions`` : int — nombre de positions ouvertes
        - ``available`` : bool — False si les tables sont absentes ou vides
        - ``snapshot_at`` : str | None — timestamp du dernier snapshot
    """
    positions_df = safe_query("""
        SELECT bps.unrealized_pnl, bps.market_value, bps.created_at
        FROM broker_positions_snapshots bps
        INNER JOIN (
            SELECT MAX(created_at) AS mx FROM broker_positions_snapshots
        ) t ON bps.created_at = t.mx
    """)
    if positions_df.empty:
        return {
            "unrealized_pnl": 0.0,
            "total_market_value": 0.0,
            "open_positions": 0,
            "available": False,
            "snapshot_at": None,
        }
    unrealized_pnl = float(
        pd.to_numeric(positions_df.get("unrealized_pnl"), errors="coerce").fillna(0.0).sum()
    )
    total_market_value = float(
        pd.to_numeric(positions_df.get("market_value"), errors="coerce").fillna(0.0).sum()
    )
    snapshot_at = str(positions_df["created_at"].iloc[0]) if "created_at" in positions_df.columns else None
    return {
        "unrealized_pnl": unrealized_pnl,
        "total_market_value": total_market_value,
        "open_positions": len(positions_df),
        "available": True,
        "snapshot_at": snapshot_at,
    }

