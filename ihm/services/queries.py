"""ihm/services/queries.py — Requêtes SQL centralisées pour l'IHM."""
from __future__ import annotations

from datetime import date, datetime
import json

import pandas as pd
import streamlit as st

from database.run_business_summaries import parse_summary_json
from ihm.services.alpha_scanner_threshold_presets import DEFAULT_ALPHA_SCANNER_DEPENDENCY_THRESHOLDS
from ihm.services.run_summary import build_run_summary_caption
from ihm.services.db import get_last_query_error, safe_query, safe_scalar
from ihm.services.screener_preferences import load_persisted_alpha_scanner_dependency_thresholds

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
    return safe_query("""
        SELECT symbol, sector, is_candidate, total_score, final_score, final_score_sentiment,
               trend_score, vcp_score, signal_active, total_news,
               anomaly_count, missing_days_count,
               last_updated_score, last_updated_scan, last_updated_sentiment
        FROM stock_scores
        ORDER BY final_score_sentiment DESC, total_score DESC
    """)


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


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_execution_runs(limit: int = 20, account_id: str | None = None) -> pd.DataFrame:
    if account_id:
        return safe_query(f"""
            SELECT exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
                   status, started_at, completed_at, total_targets, total_submitted,
                   total_filled, error_message, account_id
            FROM execution_runs WHERE account_id = :account_id ORDER BY started_at DESC LIMIT {limit}
        """, {"account_id": account_id})
    return safe_query(f"""
        SELECT exec_run_id, risk_run_id, trade_date, broker_mode, dry_run,
               status, started_at, completed_at, total_targets, total_submitted,
               total_filled, error_message
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
def get_execution_orders(exec_run_id: str | None = None) -> pd.DataFrame:
    if exec_run_id:
        return safe_query(
            """
            SELECT exec_run_id, risk_run_id, symbol, intent_id, parent_intent_id,
                   intent_role, broker_order_id, side, qty, filled_qty, avg_fill_price,
                   order_type, limit_price, stop_price, trail_percent, decision_price,
                   status, created_at, updated_at
            FROM execution_orders
            WHERE exec_run_id = :eid
            ORDER BY CASE WHEN parent_intent_id IS NULL THEN 0 ELSE 1 END,
                     COALESCE(parent_intent_id, intent_id), created_at DESC
            """,
            {"eid": exec_run_id},
        )
    return safe_query(
        """
        SELECT exec_run_id, risk_run_id, symbol, intent_id, parent_intent_id,
               intent_role, broker_order_id, side, qty, filled_qty, avg_fill_price,
               order_type, limit_price, stop_price, trail_percent, decision_price,
               status, created_at, updated_at
        FROM execution_orders
        ORDER BY created_at DESC
        LIMIT 200
        """
    )


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
    if df.empty:
        return {}

    row = df.iloc[0]
    payload_raw = row.get("payload_json")
    payload: dict[str, object] = {}
    if isinstance(payload_raw, str) and payload_raw.strip():
        try:
            parsed = json.loads(payload_raw)
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}
    payload.setdefault("message", row.get("message", ""))
    payload.setdefault("created_at", row.get("created_at"))
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
def get_execution_fills(exec_run_id: str | None = None) -> pd.DataFrame:
    if exec_run_id:
        return safe_query("""
            SELECT * FROM execution_fills WHERE exec_run_id = :eid ORDER BY fill_timestamp DESC
        """, {"eid": exec_run_id})
    return safe_query("SELECT * FROM execution_fills ORDER BY fill_timestamp DESC LIMIT 100")


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


