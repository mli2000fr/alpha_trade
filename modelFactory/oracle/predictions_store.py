"""modelFactory/oracle/predictions_store.py — Stockage table des prédictions OOS Oracle Extreme.

Persistance en base des prédictions ``proba_extreme`` de l'Oracle O0, en
complément du parquet (option b : double écriture puis bascule).

- Table : ``alpha_trade.oracle_extreme_predictions`` (DDL dans
  ``database/sql/oracle/oracle_extreme_predictions.sql``).
- Écriture : ``walk_forward.persist_oos`` → ``write_oracle_predictions``.
- Lecture (backtest) : ``load_oracle_predictions`` via ``--oracle-batch-id``.

DISCIPLINE BATCH (cf. doc/controle_couverture.md) :
  TOUJOURS filtrer par ``batch_id``. La table accumule les prédictions de
  toutes les campagnes Oracle ; sans filtre strict on retomberait sur le
  problème « tous batchs confondus ». ``load_oracle_predictions`` refuse donc
  un batch_id vide par défaut.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sqlalchemy import text

LOGGER = logging.getLogger(__name__)

ORACLE_PREDICTIONS_TABLE = "alpha_trade.oracle_extreme_predictions"

# DDL idempotent — miroir de database/sql/oracle/oracle_extreme_predictions.sql
_DDL = (
    "CREATE TABLE IF NOT EXISTS alpha_trade.oracle_extreme_predictions ("
    "  prediction_date  DATE         NOT NULL,"
    "  symbol           VARCHAR(20)  NOT NULL,"
    "  proba_extreme    DOUBLE       NOT NULL,"
    "  future_return    DOUBLE       NULL,"
    "  oracle_extreme10 TINYINT      NULL,"
    "  fold_start       DATE         NULL,"
    "  batch_id         VARCHAR(255) NOT NULL,"
    "  created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,"
    "  PRIMARY KEY (prediction_date, symbol, batch_id),"
    "  KEY idx_oracle_extreme_batch_date (batch_id, prediction_date),"
    "  KEY idx_oracle_extreme_batch_symbol (batch_id, symbol)"
    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
)

_INSERT = text(
    "INSERT INTO alpha_trade.oracle_extreme_predictions "
    "(prediction_date, symbol, proba_extreme, future_return, oracle_extreme10, "
    " fold_start, batch_id) "
    "VALUES (:prediction_date, :symbol, :proba_extreme, :future_return, "
    " :oracle_extreme10, :fold_start, :batch_id) "
    "ON DUPLICATE KEY UPDATE "
    "proba_extreme=VALUES(proba_extreme), future_return=VALUES(future_return), "
    "oracle_extreme10=VALUES(oracle_extreme10), fold_start=VALUES(fold_start)"
)


def ensure_oracle_predictions_table(engine: Any) -> None:
    """Crée la table si absente (idempotent)."""
    with engine.begin() as conn:
        conn.execute(text(_DDL))


def write_oracle_predictions(
    engine: Any,
    df: pd.DataFrame,
    batch_id: str,
) -> int:
    """Upsert des prédictions OOS dans la table (idempotent par (date, symbol, batch)).

    PK = ``(prediction_date, symbol, batch_id)`` : toute ré-écriture pour le même
    couple écrase la ligne existante (ON DUPLICATE KEY UPDATE). Pas de ``run_id`` :
    on ne cumule jamais de doublons entre runs.

    ``df`` attendu avec les colonnes du parquet OOS S4 :
    ``date, symbol, proba_extreme, future_return, oracle_extreme10, fold_start``.
    """
    if df is None or df.empty:
        return 0
    if not (batch_id or "").strip():
        raise ValueError("write_oracle_predictions: batch_id obligatoire.")

    ensure_oracle_predictions_table(engine)

    # Colonne cible du label Oracle (peut différer de "oracle_extreme10").
    _label_col = "oracle_extreme10" if "oracle_extreme10" in df.columns else None
    _future_col = "future_return" if "future_return" in df.columns else None
    _fold_col = "fold_start" if "fold_start" in df.columns else None

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append({
            "prediction_date": str(row["date"])[:10],
            "symbol": str(row["symbol"]).upper(),
            "proba_extreme": float(row["proba_extreme"]),
            "future_return": float(row[_future_col]) if (_future_col and pd.notna(row[_future_col])) else None,
            "oracle_extreme10": int(row[_label_col]) if (_label_col and pd.notna(row[_label_col])) else None,
            "fold_start": str(row[_fold_col])[:10] if (_fold_col and pd.notna(row[_fold_col])) else None,
            "batch_id": str(batch_id),
        })

    inserted = 0
    with engine.begin() as conn:
        for p in rows:
            conn.execute(_INSERT, p)
            inserted += 1
    LOGGER.info(
        "oracle_extreme_predictions upserted=%d batch=%s", inserted, batch_id,
    )
    return inserted


def load_oracle_predictions(
    engine: Any,
    *,
    batch_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    require_batch: bool = True,
) -> pd.DataFrame:
    """Lit les prédictions OOS Oracle Extreme de la table, filtrées STRICTEMENT par batch.

    Retourne un DataFrame avec ``date, symbol, proba_extreme, future_return,
    oracle_extreme10, fold_start`` — compatible avec
    ``build_oracle_rank_map`` et le chargement parquet historique de ``_impl.py``.

    Paramètres
    ----------
    batch_id : obligatoire si ``require_batch`` (défaut True) — anti-mélange
        multi-campagnes (cf. doc/controle_couverture.md).
    start_date / end_date : filtre optionnel de fenêtre (YYYY-MM-DD).
    """
    if require_batch and not (batch_id or "").strip():
        raise ValueError(
            "load_oracle_predictions: batch_id obligatoire — la table accumule "
            "toutes les campagnes, filtre strict requis (jamais 'tous batchs confondus')."
        )

    sql = (
        "SELECT prediction_date AS `date`, symbol, proba_extreme, future_return, "
        "       oracle_extreme10, fold_start "
        f"FROM {ORACLE_PREDICTIONS_TABLE} WHERE batch_id = :batch_id"
    )
    params: dict[str, Any] = {"batch_id": batch_id}
    if start_date:
        sql += " AND prediction_date >= :start_date"
        params["start_date"] = str(start_date)[:10]
    if end_date:
        sql += " AND prediction_date <= :end_date"
        params["end_date"] = str(end_date)[:10]
    sql += " ORDER BY prediction_date, symbol"

    try:
        df = pd.read_sql(text(sql), engine, params=params)
    except Exception as exc:  # table absente → on la crée puis on relit
        ensure_oracle_predictions_table(engine)
        df = pd.read_sql(text(sql), engine, params=params)

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    LOGGER.info("load_oracle_predictions batch=%s rows=%d", batch_id, len(df))
    return df
