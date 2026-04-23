"""ihm/services/queries.py — Requêtes SQL centralisées pour l'IHM."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from ihm.services.db import safe_query, safe_scalar


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
            SELECT * FROM risk_decisions WHERE run_id = :run_id ORDER BY created_at DESC
        """, {"run_id": run_id})
    return safe_query("SELECT * FROM risk_decisions ORDER BY created_at DESC LIMIT 200")


@st.cache_data(ttl=60, show_spinner=False)
def get_portfolio_targets(run_id: str | None = None) -> pd.DataFrame:
    if run_id:
        return safe_query("""
            SELECT * FROM portfolio_targets WHERE run_id = :run_id ORDER BY target_weight DESC
        """, {"run_id": run_id})
    return safe_query("""
        SELECT * FROM portfolio_targets
        WHERE run_id = (SELECT run_id FROM portfolio_targets ORDER BY created_at DESC LIMIT 1)
        ORDER BY target_weight DESC
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


