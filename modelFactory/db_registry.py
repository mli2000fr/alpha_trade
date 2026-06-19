"""modelFactory/db_registry.py — Opérations MySQL pour le registre ML."""
from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from database.stock_scores import (
    list_candidate_symbols as list_candidate_stock_score_symbols,
)
from database.stock_scores import (
    load_candidate_selector_context as load_candidate_stock_score_context,
)

LOGGER = logging.getLogger(__name__)

_PREDICTION_REQUIRED_COLUMNS = {
    "symbol",
    "prediction_date",
    "predicted_proba",
    "predicted_class",
    "run_id",
    "selected_model",
    "decision_threshold",
    "signal_label",
    "calibration_method",
}

# ML Sprint 3 — colonnes optionnelles pour le mode ternaire
_PREDICTION_TERNARY_COLUMNS = {
    "predicted_side",   # "long" | "flat" | "short"
    "proba_long",       # probabilité long
    "proba_flat",       # probabilité flat
    "proba_short",      # probabilité short
}


def _required_text(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"model_predictions requires non-empty field '{field_name}'.")
    return normalized


def _required_finite_float(value: Any, *, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"model_predictions requires numeric field '{field_name}'.") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"model_predictions requires finite field '{field_name}'.")
    return numeric


def _validate_predictions_frame(predictions: pd.DataFrame) -> None:
    missing = sorted(_PREDICTION_REQUIRED_COLUMNS.difference(predictions.columns))
    if missing:
        raise ValueError(f"model_predictions missing required columns: {', '.join(missing)}")


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_symbol in symbols:
        symbol = str(raw_symbol).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _normalize_signal_modes(signal_modes: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in signal_modes or ():
        value = str(raw_value).strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return tuple(normalized)


def _load_distinct_symbols(engine: Engine, query: str) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(query)).scalars().all()
    return _normalize_symbols([str(symbol) for symbol in rows if symbol])


def has_selector_universe_filter(
    *,
    signal_modes: tuple[str, ...] | list[str] | None = None,
    max_candidate_rank: int | None = None,
    exclude_earnings_blackout: bool = False,
) -> bool:
    return bool(_normalize_signal_modes(signal_modes) or max_candidate_rank is not None or exclude_earnings_blackout)


def filter_symbols_by_selector_context(
    engine: Engine,
    symbols: list[str],
    *,
    signal_modes: tuple[str, ...] | list[str] | None = None,
    max_candidate_rank: int | None = None,
    exclude_earnings_blackout: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    normalized_symbols = _normalize_symbols(symbols)
    normalized_signal_modes = _normalize_signal_modes(signal_modes)
    criteria_enabled = has_selector_universe_filter(
        signal_modes=normalized_signal_modes,
        max_candidate_rank=max_candidate_rank,
        exclude_earnings_blackout=exclude_earnings_blackout,
    )
    summary: dict[str, Any] = {
        "enabled": criteria_enabled,
        "applied": False,
        "input_symbol_count": len(normalized_symbols),
        "output_symbol_count": len(normalized_symbols),
        "signal_modes": list(normalized_signal_modes),
        "max_candidate_rank": max_candidate_rank,
        "exclude_earnings_blackout": bool(exclude_earnings_blackout),
        "reason": None,
    }
    if not normalized_symbols or not criteria_enabled:
        return normalized_symbols, summary

    try:
        context_df = load_candidate_selector_context(engine)
    except Exception as exc:  # noqa: BLE001
        summary["reason"] = f"selector_context_unavailable:{type(exc).__name__}"
        LOGGER.warning(
            "filter_symbols_by_selector_context unavailable symbols=%d reason=%s",
            len(normalized_symbols),
            summary["reason"],
        )
        return normalized_symbols, summary

    if context_df.empty or "symbol" not in context_df.columns:
        summary["reason"] = "selector_context_empty"
        LOGGER.warning("filter_symbols_by_selector_context empty_context symbols=%d", len(normalized_symbols))
        return normalized_symbols, summary

    required_columns: list[str] = []
    if normalized_signal_modes:
        required_columns.append("selector_signal_mode")
    if max_candidate_rank is not None:
        required_columns.append("candidate_rank")
    if exclude_earnings_blackout:
        required_columns.append("earnings_blackout")
    missing_columns = [column for column in required_columns if column not in context_df.columns]
    if missing_columns:
        summary["reason"] = f"selector_context_missing_columns:{','.join(sorted(missing_columns))}"
        LOGGER.warning(
            "filter_symbols_by_selector_context missing_columns=%s symbols=%d",
            ",".join(sorted(missing_columns)),
            len(normalized_symbols),
        )
        return normalized_symbols, summary

    working_df = context_df.copy()
    working_df["symbol"] = working_df["symbol"].astype(str).str.strip().str.upper()
    working_df = working_df[working_df["symbol"].isin(normalized_symbols)].copy()
    if working_df.empty:
        summary["applied"] = True
        summary["output_symbol_count"] = 0
        summary["reason"] = "selector_context_no_overlap"
        return [], summary

    if normalized_signal_modes:
        working_df = working_df[
            working_df["selector_signal_mode"].astype(str).str.strip().str.lower().isin(normalized_signal_modes)
        ]
    if max_candidate_rank is not None:
        candidate_rank = pd.Series(pd.to_numeric(working_df["candidate_rank"], errors="coerce"), index=working_df.index)
        working_df = working_df[candidate_rank.notna() & (candidate_rank <= float(max_candidate_rank))]
    if exclude_earnings_blackout:
        earnings_blackout = working_df["earnings_blackout"].fillna(False)
        blackout_mask = earnings_blackout.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})
        if getattr(earnings_blackout, "dtype", None) == bool:
            blackout_mask = earnings_blackout.astype(bool)
        working_df = working_df[~blackout_mask]

    filtered_symbols = _normalize_symbols(working_df["symbol"].tolist())
    summary.update(
        {
            "applied": True,
            "output_symbol_count": len(filtered_symbols),
            "excluded_symbol_count": max(0, len(normalized_symbols) - len(filtered_symbols)),
            "matched_context_rows": int(len(working_df)),
            "reason": "selector_context_filtered",
        }
    )
    LOGGER.info(
        "filter_symbols_by_selector_context symbols_in=%d symbols_out=%d signal_modes=%s max_candidate_rank=%s exclude_earnings_blackout=%s",
        len(normalized_symbols),
        len(filtered_symbols),
        list(normalized_signal_modes),
        max_candidate_rank,
        exclude_earnings_blackout,
    )
    return filtered_symbols, summary


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_governance_rows(
    *,
    run_id: str,
    symbol: str,
    challengers: dict[str, Any],
    artifact_routes_models: dict[str, Any],
    selected_model: str,
    selection_mode: str,
    selection_metric: str,
    ranking: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ranking_rows = ranking or []
    ranking_by_model = {
        str(row.get("model_name")): row
        for row in ranking_rows
        if isinstance(row, dict) and row.get("model_name")
    }
    rows: list[dict[str, Any]] = []
    for model_name, challenger in challengers.items():
        if model_name == "ranking" or not isinstance(challenger, dict):
            continue
        route = artifact_routes_models.get(model_name, {}) if isinstance(artifact_routes_models.get(model_name, {}), dict) else {}
        ranking_row = ranking_by_model.get(model_name, {})
        val_metrics = challenger.get("val") if isinstance(challenger.get("val"), dict) else {}
        test_metrics = challenger.get("test") if isinstance(challenger.get("test"), dict) else {}
        walk_forward_metrics = challenger.get("walk_forward") if isinstance(challenger.get("walk_forward"), dict) else {}
        wf_mean = walk_forward_metrics.get("mean") if isinstance(walk_forward_metrics.get("mean"), dict) else {}
        rows.append(
            {
                "run_id": run_id,
                "symbol": symbol,
                "model_name": model_name,
                "rank": _optional_int(ranking_row.get("rank")),
                "is_selected_model": 1 if model_name == selected_model else 0,
                "selection_mode": selection_mode,
                "selection_metric": selection_metric,
                "selection_score": _optional_float(
                    challenger.get("selection_score", ranking_row.get("selection_score"))
                ),
                "model_status": ranking_row.get("status") or challenger.get("status"),
                "selection_eligible": 1 if bool(challenger.get("selection_eligible", ranking_row.get("selection_eligible", False))) else 0,
                "eligibility_reason": challenger.get("eligibility_reason", ranking_row.get("eligibility_reason")),
                "reason": challenger.get("reason", ranking_row.get("reason")),
                "inference_backend": route.get("inference_backend"),
                "backend_model_name": challenger.get("backend_model_name") or route.get("backend_model_name"),
                "calibration_method": challenger.get("calibration_method"),
                "decision_threshold": _optional_float(route.get("selected_decision_threshold")),
                "artifact_symbol": route.get("artifact_symbol"),
                "checkpoint_path": route.get("checkpoint_path"),
                "scaler_path": route.get("scaler_path"),
                "model_path": route.get("model_path"),
                "config_path": route.get("config_path"),
                "calibrator_path": route.get("calibrator_path"),
                "val_auc": _optional_float(val_metrics.get("auc")),
                "test_auc": _optional_float(test_metrics.get("auc")),
                "wf_auc": _optional_float(wf_mean.get("auc")),
                "val_threshold_business_score": _optional_float(val_metrics.get("threshold_business_score")),
                "test_threshold_business_score": _optional_float(test_metrics.get("threshold_business_score")),
                "wf_threshold_business_score": _optional_float(wf_mean.get("threshold_business_score")),
                # ML Sprint 7 — colonnes ternaires
                "num_classes": int(challenger.get("num_classes", 2)),
                "val_f1_macro": _optional_float(val_metrics.get("f1_macro") or val_metrics.get("f1_score")),
                "test_f1_macro": _optional_float(test_metrics.get("f1_macro") or test_metrics.get("f1_score")),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def ensure_registry_entry(engine: Engine, symbol: str, architecture: str = "lstm_attention") -> int:
    """Retourne registry_id existant ou en crée un nouveau. Incrémente version si réentraînement."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT registry_id, version FROM model_registry "
                "WHERE symbol = :sym AND architecture = :arch AND is_active = 1 "
                "ORDER BY version DESC LIMIT 1"
            ),
            {"sym": symbol, "arch": architecture},
        ).fetchone()

        if row is not None:
            return int(row[0])

        conn.execute(
            text(
                "INSERT INTO model_registry (symbol, architecture, version, is_active) "
                "VALUES (:sym, :arch, 1, 1)"
            ),
            {"sym": symbol, "arch": architecture},
        )
        result = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        LOGGER.info("model_registry created registry_id=%s symbol=%s", result, symbol)
        return int(result)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Training run
# ---------------------------------------------------------------------------

def insert_training_run(engine: Engine, run_id: str, registry_id: int, symbol: str, status: str = "pending") -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO model_training_run (run_id, registry_id, symbol, status, started_at) "
                "VALUES (:rid, :reg, :sym, :st, :now)"
            ),
            {"rid": run_id, "reg": registry_id, "sym": symbol, "st": status, "now": datetime.now(UTC)},
        )


def update_training_run(engine: Engine, run_id: str, **kwargs: Any) -> None:
    if not kwargs:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in kwargs)
    params: dict[str, Any] = {**kwargs, "rid": run_id}
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE model_training_run SET {set_clause} WHERE run_id = :rid"), params)


def load_training_run(engine: Engine, symbol: str, run_id: str | None = None) -> dict[str, Any] | None:
    """Charge le run demandé, ou le dernier run complété disponible pour un symbole."""
    if run_id:
        sql = (
            "SELECT run_id, symbol, status, checkpoint_path, scaler_path, config_path, started_at, finished_at "
            "FROM model_training_run "
            "WHERE symbol = :sym AND run_id = :rid "
            "LIMIT 1"
        )
        params = {"sym": symbol, "rid": run_id}
    else:
        sql = (
            "SELECT run_id, symbol, status, checkpoint_path, scaler_path, config_path, started_at, finished_at "
            "FROM model_training_run "
            "WHERE symbol = :sym AND status = 'completed' "
            "AND checkpoint_path IS NOT NULL AND scaler_path IS NOT NULL AND config_path IS NOT NULL "
            "ORDER BY COALESCE(finished_at, started_at) DESC, started_at DESC "
            "LIMIT 1"
        )
        params = {"sym": symbol}

    with engine.connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()

    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def insert_metrics(engine: Engine, run_id: str, symbol: str, split_name: str, metrics: dict[str, float]) -> None:
    # ML Sprint 7 — inclure les métriques ternaires si disponibles
    has_ternary = "f1_macro" in metrics or "f1_short" in metrics
    if has_ternary:
        sql = text(
            "INSERT INTO model_metrics (run_id, symbol, split_name, loss, directional_accuracy, `precision`, recall, auc, "
            "f1_macro, f1_short, f1_flat, f1_long) "
            "VALUES (:rid, :sym, :split, :loss, :da, :prec, :rec, :auc, :f1m, :f1s, :f1f, :f1l)"
        )
    else:
        sql = text(
            "INSERT INTO model_metrics (run_id, symbol, split_name, loss, directional_accuracy, `precision`, recall, auc) "
            "VALUES (:rid, :sym, :split, :loss, :da, :prec, :rec, :auc)"
        )
    params = {
        "rid": run_id, "sym": symbol, "split": split_name,
        "loss": metrics.get("loss"),
        "da": metrics.get("directional_accuracy") or metrics.get("accuracy"),
        "prec": metrics.get("precision"),
        "rec": metrics.get("recall"),
        "auc": metrics.get("auc"),
    }
    if has_ternary:
        params["f1m"] = metrics.get("f1_macro") or metrics.get("f1_score")
        params["f1s"] = metrics.get("f1_short")
        params["f1f"] = metrics.get("f1_flat")
        params["f1l"] = metrics.get("f1_long")
    with engine.begin() as conn:
        conn.execute(sql, params)


def count_completed_runs(
    engine: Engine,
    symbol: str,
    model_name: str,
) -> tuple[int, datetime | None]:
    """Phase 4.2.e — quarantaine champion.

    Retourne ``(nb_runs_completed, first_completed_at)`` pour un couple
    (symbol, model_name) en consultant ``model_governance`` (vue qui suit
    les modèles servis). Tolérant à l'absence de table : ``(0, None)``.
    """
    sql = text(
        """
        SELECT COUNT(*) AS cnt, MIN(COALESCE(finished_at, started_at)) AS first_at
        FROM model_training_run mtr
        JOIN model_governance mg
          ON mg.run_id = mtr.run_id AND mg.symbol = mtr.symbol
        WHERE mtr.symbol = :sym
          AND mg.model_name = :mn
          AND mtr.status = 'completed'
        """
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"sym": symbol, "mn": model_name}).mappings().first()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("count_completed_runs failed sym=%s mn=%s err=%s", symbol, model_name, exc)
        return 0, None
    if not row:
        return 0, None
    return int(row.get("cnt") or 0), row.get("first_at")


def upsert_metrics_full(
    engine: Engine,
    *,
    run_id: str,
    symbol: str,
    metrics: dict[str, Any],
) -> None:
    """Phase 4.2.f — persiste ``metrics.json`` complet en BLOB.

    Idempotent (REPLACE-like via ON DUPLICATE KEY). Tolérant à l'absence
    de table : log un WARNING et n'arrête pas le run.
    """
    import json as _json
    payload = _json.dumps(metrics, ensure_ascii=False, default=str, sort_keys=True).encode("utf-8")
    sql = text(
        """
        INSERT INTO model_metrics_full (run_id, symbol, metrics_json, created_at)
        VALUES (:rid, :sym, :payload, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
            symbol = VALUES(symbol),
            metrics_json = VALUES(metrics_json),
            created_at = CURRENT_TIMESTAMP
        """
    )
    try:
        with engine.begin() as conn:
            conn.execute(sql, {"rid": run_id, "sym": symbol, "payload": payload})
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("upsert_metrics_full failed run_id=%s sym=%s err=%s", run_id, symbol, exc)


def replace_model_governance(
    engine: Engine,
    *,
    run_id: str,
    symbol: str,
    challengers: dict[str, Any],
    artifact_routes_models: dict[str, Any],
    selected_model: str,
    selection_mode: str,
    selection_metric: str,
    ranking: list[dict[str, Any]] | None = None,
) -> int:
    rows = build_governance_rows(
        run_id=run_id,
        symbol=symbol,
        challengers=challengers,
        artifact_routes_models=artifact_routes_models,
        selected_model=selected_model,
        selection_mode=selection_mode,
        selection_metric=selection_metric,
        ranking=ranking,
    )
    if not rows:
        return 0

    delete_stmt = text("DELETE FROM model_governance WHERE run_id = :run_id AND symbol = :symbol")
    insert_stmt = text(
        "INSERT INTO model_governance ("
        "run_id, symbol, model_name, `rank`, is_selected_model, selection_mode, selection_metric, selection_score, "
        "model_status, selection_eligible, eligibility_reason, reason, inference_backend, backend_model_name, "
        "calibration_method, decision_threshold, artifact_symbol, checkpoint_path, scaler_path, model_path, config_path, "
        "calibrator_path, val_auc, test_auc, wf_auc, val_threshold_business_score, test_threshold_business_score, wf_threshold_business_score, "
        "num_classes, val_f1_macro, test_f1_macro"
        ") VALUES ("
        ":run_id, :symbol, :model_name, :rank, :is_selected_model, :selection_mode, :selection_metric, :selection_score, "
        ":model_status, :selection_eligible, :eligibility_reason, :reason, :inference_backend, :backend_model_name, "
        ":calibration_method, :decision_threshold, :artifact_symbol, :checkpoint_path, :scaler_path, :model_path, :config_path, "
        ":calibrator_path, :val_auc, :test_auc, :wf_auc, :val_threshold_business_score, :test_threshold_business_score, :wf_threshold_business_score, "
        ":num_classes, :val_f1_macro, :test_f1_macro"
        ")"
    )
    with engine.begin() as conn:
        conn.execute(delete_stmt, {"run_id": run_id, "symbol": symbol})
        for row in rows:
            conn.execute(insert_stmt, row)
    LOGGER.info("replace_model_governance rows=%d run_id=%s symbol=%s", len(rows), run_id, symbol)
    return len(rows)


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def insert_predictions(engine: Engine, predictions: pd.DataFrame) -> int:
    """Insert prediction rows sur le schéma courant.

    Colonnes supportées côté DataFrame :
    - symbol
    - prediction_date
    - predicted_proba
    - predicted_class
    - run_id
    - selected_model
    - decision_threshold
    - signal_label
    - calibration_method
    """
    if predictions.empty:
        return 0
    _validate_predictions_frame(predictions)
    # ML Sprint 3 — détecter si les colonnes ternaires sont présentes
    has_ternary = "predicted_side" in predictions.columns
    if has_ternary:
        stmt_v2 = text(
            "INSERT INTO model_predictions ("
            "symbol, prediction_date, predicted_proba, predicted_class, "
            "predicted_side, proba_long, proba_flat, proba_short, "
            "run_id, selected_model, decision_threshold, signal_label, calibration_method"
            ") VALUES ("
            ":sym, :pd, :pp, :pc, :ps, :pl, :pf, :psh, "
            ":rid, :selected_model, :decision_threshold, :signal_label, :calibration_method"
            ") ON DUPLICATE KEY UPDATE "
            "predicted_proba = VALUES(predicted_proba), "
            "predicted_class = VALUES(predicted_class), "
            "predicted_side = VALUES(predicted_side), "
            "proba_long = VALUES(proba_long), "
            "proba_flat = VALUES(proba_flat), "
            "proba_short = VALUES(proba_short), "
            "selected_model = VALUES(selected_model), "
            "decision_threshold = VALUES(decision_threshold), "
            "signal_label = VALUES(signal_label), "
            "calibration_method = VALUES(calibration_method)"
        )
    else:
        stmt_v2 = text(
            "INSERT INTO model_predictions ("
            "symbol, prediction_date, predicted_proba, predicted_class, run_id, "
            "selected_model, decision_threshold, signal_label, calibration_method"
            ") VALUES ("
            ":sym, :pd, :pp, :pc, :rid, :selected_model, :decision_threshold, :signal_label, :calibration_method"
            ") ON DUPLICATE KEY UPDATE "
            "predicted_proba = VALUES(predicted_proba), "
            "predicted_class = VALUES(predicted_class), "
            "selected_model = VALUES(selected_model), "
            "decision_threshold = VALUES(decision_threshold), "
            "signal_label = VALUES(signal_label), "
            "calibration_method = VALUES(calibration_method)"
        )
    with engine.begin() as conn:
        for _, row in predictions.iterrows():
            params = {
                "sym": _required_text(row["symbol"], field_name="symbol"),
                "pd": row["prediction_date"],
                "pp": float(row["predicted_proba"]),
                "pc": int(row["predicted_class"]),
                "rid": _required_text(row["run_id"], field_name="run_id"),
                "selected_model": _required_text(row.get("selected_model"), field_name="selected_model"),
                "decision_threshold": _required_finite_float(row.get("decision_threshold"), field_name="decision_threshold"),
                "signal_label": _required_text(row.get("signal_label"), field_name="signal_label"),
                "calibration_method": _required_text(row.get("calibration_method"), field_name="calibration_method"),
            }
            if has_ternary:
                params["ps"] = str(row.get("predicted_side") or "") or None
                params["pl"] = float(row.get("proba_long")) if pd.notna(row.get("proba_long")) else None
                params["pf"] = float(row.get("proba_flat")) if pd.notna(row.get("proba_flat")) else None
                params["psh"] = float(row.get("proba_short")) if pd.notna(row.get("proba_short")) else None
            conn.execute(stmt_v2, params)
    LOGGER.info("insert_predictions rows=%d", len(predictions))
    return len(predictions)


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def load_candidate_symbols(engine: Engine) -> list[str]:
    """Charge les symboles avec is_candidate=1 depuis stock_scores."""
    symbols = list_candidate_stock_score_symbols(engine=engine)
    LOGGER.info("load_candidate_symbols count=%d", len(symbols))
    return symbols


def load_candidate_selector_context(engine: Engine, *, limit: int | None = None) -> pd.DataFrame:
    """Charge le contexte selector disponible pour l'univers candidat courant."""
    frame = load_candidate_stock_score_context(engine=engine, limit=limit)
    LOGGER.info("load_candidate_selector_context rows=%d cols=%d", len(frame), len(frame.columns))
    return frame


def load_stock_scores_symbols(engine: Engine) -> list[str]:
    """Charge tous les symboles distincts présents dans ``stock_scores``."""
    symbols = _load_distinct_symbols(
        engine,
        """
        SELECT DISTINCT UPPER(TRIM(symbol)) AS symbol
        FROM stock_scores
        WHERE COALESCE(TRIM(symbol), '') <> ''
        ORDER BY symbol
        """,
    )
    LOGGER.info("load_stock_scores_symbols count=%d", len(symbols))
    return symbols


def load_stock_scores_history_symbols(engine: Engine) -> list[str]:
    """Charge tous les symboles distincts présents dans ``stock_scores_history``."""
    symbols = _load_distinct_symbols(
        engine,
        """
        SELECT DISTINCT UPPER(TRIM(symbol)) AS symbol
        FROM stock_scores_history
        WHERE COALESCE(TRIM(symbol), '') <> ''
        ORDER BY symbol
        """,
    )
    LOGGER.info("load_stock_scores_history_symbols count=%d", len(symbols))
    return symbols


def load_stock_scores_all_symbols(engine: Engine) -> list[str]:
    """Charge l’union dédupliquée ``stock_scores`` + ``stock_scores_history``."""
    symbols = _load_distinct_symbols(
        engine,
        """
        SELECT DISTINCT UPPER(TRIM(symbol)) AS symbol
        FROM (
            SELECT symbol FROM stock_scores
            UNION
            SELECT symbol FROM stock_scores_history
        ) combined_symbols
        WHERE COALESCE(TRIM(symbol), '') <> ''
        ORDER BY symbol
        """,
    )
    LOGGER.info("load_stock_scores_all_symbols count=%d", len(symbols))
    return symbols


def load_symbols_for_source(engine: Engine, symbol_source: str) -> list[str]:
    """Résout l’univers ML demandé via un identifiant de source stable."""
    normalized_source = str(symbol_source or "candidates").strip().lower()
    if normalized_source == "stock-bars-daily":
        return load_stock_bars_daily_symbols(engine)
    if normalized_source == "stock-scores":
        return load_stock_scores_symbols(engine)
    if normalized_source == "stock-scores-history":
        return load_stock_scores_history_symbols(engine)
    if normalized_source == "stock-scores-all":
        return load_stock_scores_all_symbols(engine)
    return load_candidate_symbols(engine)


def load_stock_bars_daily_symbols(engine: Engine) -> list[str]:
    """Charge tous les symboles distincts présents dans stock_bars_daily."""
    query = text(
        """
        SELECT DISTINCT UPPER(TRIM(symbol)) AS symbol
        FROM stock_bars_daily
        WHERE COALESCE(TRIM(symbol), '') <> ''
        ORDER BY symbol
        """
    )
    with engine.connect() as conn:
        symbols = [str(symbol) for symbol in conn.execute(query).scalars().all() if symbol]
    LOGGER.info("load_stock_bars_daily_symbols count=%d", len(symbols))
    return symbols


