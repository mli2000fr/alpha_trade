"""modelFactory/db_registry.py — Opérations MySQL pour le registre ML."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


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
            {"rid": run_id, "reg": registry_id, "sym": symbol, "st": status, "now": datetime.now(timezone.utc)},
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
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO model_metrics (run_id, symbol, split_name, loss, directional_accuracy, `precision`, recall, auc) "
                "VALUES (:rid, :sym, :split, :loss, :da, :prec, :rec, :auc)"
            ),
            {
                "rid": run_id, "sym": symbol, "split": split_name,
                "loss": metrics.get("loss"),
                "da": metrics.get("directional_accuracy"),
                "prec": metrics.get("precision"),
                "rec": metrics.get("recall"),
                "auc": metrics.get("auc"),
            },
        )


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def insert_predictions(engine: Engine, predictions: pd.DataFrame) -> int:
    """Insert prediction rows. DataFrame cols: symbol, prediction_date, predicted_proba, predicted_class, run_id."""
    if predictions.empty:
        return 0
    with engine.begin() as conn:
        for _, row in predictions.iterrows():
            conn.execute(
                text(
                    "INSERT INTO model_predictions (symbol, prediction_date, predicted_proba, predicted_class, run_id) "
                    "VALUES (:sym, :pd, :pp, :pc, :rid) "
                    "ON DUPLICATE KEY UPDATE predicted_proba = VALUES(predicted_proba), predicted_class = VALUES(predicted_class)"
                ),
                {
                    "sym": row["symbol"], "pd": row["prediction_date"],
                    "pp": float(row["predicted_proba"]), "pc": int(row["predicted_class"]),
                    "rid": row["run_id"],
                },
            )
    LOGGER.info("insert_predictions rows=%d", len(predictions))
    return len(predictions)


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def load_candidate_symbols(engine: Engine) -> list[str]:
    """Charge les symboles avec is_candidate=1 depuis stock_scores."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol FROM stock_scores WHERE is_candidate = 1")).fetchall()
    symbols = [r[0] for r in rows]
    LOGGER.info("load_candidate_symbols count=%d", len(symbols))
    return symbols

