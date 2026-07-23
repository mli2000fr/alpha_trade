"""modelFactory/batch_diagnostics.py — Snapshot des diagnostics ML par batch.

Stocke dans ``alpha_trade.model_batch_diagnostics`` le top/bottom N des
symboles classés par F1 macro WF, les symboles avec f1_short=0, et les
symboles avec f1_long ou f1_short en dessous d'un seuil configurable.

Ces données sont consommées par le live et le backtest pour :
- Exclure les symboles du bottom N (long et short)
- Bloquer le short sur les zero_short / weak_short
- Bloquer le long sur les weak_long
- Privilégier les symboles du top N dans la sélection du jour
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)

# ── Constantes de classification ──
RANK_TYPE_TOP = "top"
RANK_TYPE_BOTTOM = "bottom"
RANK_TYPE_ZERO_SHORT = "zero_short"
RANK_TYPE_WEAK_LONG = "weak_long"
RANK_TYPE_WEAK_SHORT = "weak_short"

# ── Groupes de filtrage pour le live/backtest ──
EXCLUDE_LONG_RANK_TYPES = frozenset({RANK_TYPE_BOTTOM, RANK_TYPE_WEAK_LONG})
EXCLUDE_SHORT_RANK_TYPES = frozenset({RANK_TYPE_BOTTOM, RANK_TYPE_ZERO_SHORT, RANK_TYPE_WEAK_SHORT})
PREFER_RANK_TYPES = frozenset({RANK_TYPE_TOP})


# ────────────────────────────────────────────────────────────────────
# Queries (même logique que report.py mais avec batch_started_at)
# ────────────────────────────────────────────────────────────────────

_BATCH_STARTED_QUERY = """
    SELECT started_at
    FROM alpha_trade.model_training_batch
    WHERE batch_id = :batch_id
"""

# Récupère TOUS les symboles avec leur F1 macro WF, triés par f1_macro DESC.
# On ne limite pas ici — le slicing top/bottom N est fait en Python pour
# pouvoir extraire à la fois top N et bottom N en une seule requête.
_ALL_WF_METRICS_QUERY = """
    SELECT
        mm.symbol,
        ROUND(mm.f1_macro, 6) AS f1_macro_wf,
        ROUND(mm.f1_long, 6) AS f1_long_wf,
        ROUND(mm.f1_short, 6) AS f1_short_wf,
        ROUND(mm.f1_flat, 6) AS f1_flat_wf
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    JOIN alpha_trade.model_governance AS mg
        ON mg.symbol = mm.symbol
       AND mg.model_name = mm.model_name
       AND mg.is_selected_model = 1
    JOIN alpha_trade.model_training_run AS mtr_gov
        ON mtr_gov.run_id = mg.run_id
       AND mtr_gov.batch_id = :batch_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
    ORDER BY mm.f1_macro DESC
"""

_DELETE_BATCH_QUERY = """
    DELETE FROM alpha_trade.model_batch_diagnostics
    WHERE batch_id = :batch_id
"""

_INSERT_DIAG_QUERY = """
    INSERT INTO alpha_trade.model_batch_diagnostics
        (batch_id, batch_started_at, symbol,
         f1_macro_wf, f1_long_wf, f1_short_wf, f1_flat_wf,
         rank_type, rank_position, threshold_used)
    VALUES
        (:batch_id, :batch_started_at, :symbol,
         :f1_macro_wf, :f1_long_wf, :f1_short_wf, :f1_flat_wf,
         :rank_type, :rank_position, :threshold_used)
"""

_LATEST_BATCH_QUERY = """
    SELECT batch_id
    FROM alpha_trade.model_batch_diagnostics
    GROUP BY batch_id, batch_started_at
    ORDER BY batch_started_at DESC
    LIMIT 1
"""

_LOAD_DIAG_QUERY = """
    SELECT symbol, rank_type, rank_position,
           f1_macro_wf, f1_long_wf, f1_short_wf, f1_flat_wf
    FROM alpha_trade.model_batch_diagnostics
    WHERE batch_id = :batch_id
"""


# ────────────────────────────────────────────────────────────────────
# Data class
# ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BatchFilters:
    """Résultat de ``get_batch_filters()`` pour un batch donné."""
    batch_id: str
    batch_started_at: datetime | None
    prefer: frozenset[str]         # symboles dans le top N
    exclude_long: frozenset[str]   # symboles à exclure du long
    exclude_short: frozenset[str]  # symboles à exclure du short
    all_diagnostics: pd.DataFrame  # DataFrame complet pour analyse fine
    batch_comment: str | None = None  # commentaire libre du batch (model_training_batch)


# ────────────────────────────────────────────────────────────────────
# Persistence (appelé en fin de run_training_batch)
# ────────────────────────────────────────────────────────────────────

def _load_config_defaults() -> dict[str, Any]:
    """Charge les seuils depuis config.yaml avec fallback."""
    try:
        import yaml
        with open("config.yaml", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        return (cfg.get("batch_diagnostics") or {})
    except Exception:
        return {}


def persist_batch_diagnostics(
    engine: Engine,
    batch_id: str,
    *,
    top_n: int | None = None,
    bottom_n: int | None = None,
    weak_long_threshold: float | None = None,
    weak_short_threshold: float | None = None,
) -> int:
    """Snapshot les diagnostics du batch dans ``model_batch_diagnostics``.

    Args:
        engine: Engine SQLAlchemy.
        batch_id: Identifiant du batch.
        top_n: Nombre de symboles dans le top. Défaut : config.yaml ou 50.
        bottom_n: Nombre de symboles dans le bottom. Défaut : config.yaml ou 50.
        weak_long_threshold: Seuil f1_long en dessous duquel on marque weak_long.
        weak_short_threshold: Seuil f1_short en dessous duquel on marque weak_short.

    Returns:
        Nombre de lignes insérées.
    """
    cfg = _load_config_defaults()
    top_n = top_n or cfg.get("top_n", 50)
    bottom_n = bottom_n or cfg.get("bottom_n", 50)
    weak_long_threshold = weak_long_threshold or cfg.get("weak_long_threshold", 0.15)
    weak_short_threshold = weak_short_threshold or cfg.get("weak_short_threshold", 0.15)

    # ── Récupérer batch_started_at ──
    batch_started_at: datetime | None = None
    try:
        with engine.connect() as conn:
            row = conn.execute(text(_BATCH_STARTED_QUERY), {"batch_id": batch_id}).fetchone()
            if row:
                batch_started_at = row[0]
    except Exception:
        LOGGER.warning("batch_diagnostics: cannot read started_at for batch %s", batch_id)

    if batch_started_at is None:
        batch_started_at = datetime.now(timezone.utc)

    # ── Récupérer tous les symboles avec F1 WF ──
    df = pd.DataFrame()
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(_ALL_WF_METRICS_QUERY), conn, params={"batch_id": batch_id})
    except Exception as exc:
        LOGGER.warning("batch_diagnostics: query failed for batch %s: %s", batch_id, exc)
        return 0

    if df.empty:
        LOGGER.info("batch_diagnostics: no WF metrics for batch %s, skipping", batch_id)
        return 0

    # ── Supprimer les anciennes entrées pour ce batch (idempotent) ──
    try:
        with engine.begin() as conn:
            conn.execute(text(_DELETE_BATCH_QUERY), {"batch_id": batch_id})
    except Exception as exc:
        LOGGER.warning("batch_diagnostics: delete failed for batch %s: %s", batch_id, exc)

    # ── Construire les rows à insérer ──
    rows: list[dict[str, Any]] = []
    total_symbols = len(df)
    effective_top_n = min(top_n, total_symbols)
    effective_bottom_n = min(bottom_n, total_symbols)

    for rank_idx, (_, row) in enumerate(df.iterrows()):
        symbol = str(row["symbol"])
        f1_macro = float(row["f1_macro_wf"])
        f1_long = float(row["f1_long_wf"])
        f1_short = float(row["f1_short_wf"])
        f1_flat = float(row["f1_flat_wf"])

        base = {
            "batch_id": batch_id,
            "batch_started_at": batch_started_at,
            "symbol": symbol,
            "f1_macro_wf": f1_macro,
            "f1_long_wf": f1_long,
            "f1_short_wf": f1_short,
            "f1_flat_wf": f1_flat,
        }

        # ── rank_type: top ──
        if rank_idx < effective_top_n:
            rows.append({**base, "rank_type": RANK_TYPE_TOP,
                         "rank_position": rank_idx + 1, "threshold_used": None})

        # ── rank_type: bottom ──
        if rank_idx >= total_symbols - effective_bottom_n:
            bottom_pos = total_symbols - rank_idx
            rows.append({**base, "rank_type": RANK_TYPE_BOTTOM,
                         "rank_position": bottom_pos, "threshold_used": None})

        # ── rank_type: zero_short ──
        if f1_short == 0.0:
            rows.append({**base, "rank_type": RANK_TYPE_ZERO_SHORT,
                         "rank_position": None, "threshold_used": None})

        # ── rank_type: weak_long ──
        if f1_long < weak_long_threshold and f1_long > 0.0:
            rows.append({**base, "rank_type": RANK_TYPE_WEAK_LONG,
                         "rank_position": None,
                         "threshold_used": weak_long_threshold})

        # ── rank_type: weak_short ──
        if 0.0 < f1_short < weak_short_threshold:
            rows.append({**base, "rank_type": RANK_TYPE_WEAK_SHORT,
                         "rank_position": None,
                         "threshold_used": weak_short_threshold})

    # ── Insérer ──
    if not rows:
        LOGGER.info("batch_diagnostics: no rows to insert for batch %s", batch_id)
        return 0

    try:
        with engine.begin() as conn:
            conn.execute(text(_INSERT_DIAG_QUERY), rows)
    except Exception as exc:
        LOGGER.warning("batch_diagnostics: insert failed for batch %s: %s", batch_id, exc)
        return 0

    LOGGER.info(
        "batch_diagnostics: persisted %d rows for batch %s "
        "(top=%d bottom=%d zero_short=%d weak_long=%d weak_short=%d)",
        len(rows), batch_id,
        sum(1 for r in rows if r["rank_type"] == RANK_TYPE_TOP),
        sum(1 for r in rows if r["rank_type"] == RANK_TYPE_BOTTOM),
        sum(1 for r in rows if r["rank_type"] == RANK_TYPE_ZERO_SHORT),
        sum(1 for r in rows if r["rank_type"] == RANK_TYPE_WEAK_LONG),
        sum(1 for r in rows if r["rank_type"] == RANK_TYPE_WEAK_SHORT),
    )
    return len(rows)


# ────────────────────────────────────────────────────────────────────
# Lecture (consommé par le live / backtest)
# ────────────────────────────────────────────────────────────────────

def _get_latest_completed_batch_id(engine: Engine) -> str | None:
    """Retourne le batch_id du dernier batch ayant des diagnostics."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text(_LATEST_BATCH_QUERY)).fetchone()
            return str(row[0]) if row else None
    except Exception:
        return None


def get_batch_filters(
    engine: Engine,
    batch_id: str | None = None,
    *,
    prefer_top_n: int | None = None,
) -> BatchFilters:
    """Retourne les filtres live/backtest pour un batch donné.

    Args:
        engine: Engine SQLAlchemy.
        batch_id: Identifiant du batch. Si None, utilise le dernier batch.
        prefer_top_n: Nombre de symboles du top à privilégier (filtre rank_position).
            Défaut : config.yaml (batch_diagnostics.prefer_top_n) ou 50.

    Returns:
        BatchFilters avec les sets prefer / exclude_long / exclude_short.
    """
    if prefer_top_n is None:
        prefer_top_n = _load_config_defaults().get("prefer_top_n", 50)
    if batch_id is None:
        batch_id = _get_latest_completed_batch_id(engine)
    if batch_id is None:
        return BatchFilters(
            batch_id="",
            batch_started_at=None,
            prefer=frozenset(),
            exclude_long=frozenset(),
            exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame(),
        )

    df = pd.DataFrame()
    batch_started_at: datetime | None = None
    batch_comment: str | None = None
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(_LOAD_DIAG_QUERY), conn, params={"batch_id": batch_id})
            # Récupérer batch_started_at + comment depuis model_training_batch
            meta_row = conn.execute(
                text(
                    "SELECT mbd.batch_started_at, COALESCE(mtb.comment, '') "
                    "FROM alpha_trade.model_batch_diagnostics AS mbd "
                    "LEFT JOIN alpha_trade.model_training_batch AS mtb ON mtb.batch_id = mbd.batch_id "
                    "WHERE mbd.batch_id = :bid LIMIT 1"
                ),
                {"bid": batch_id},
            ).fetchone()
            if meta_row:
                batch_started_at = meta_row[0]
                batch_comment = str(meta_row[1]).strip() or None
    except Exception as exc:
        LOGGER.warning("batch_diagnostics: get_batch_filters failed: %s", exc)

    if df.empty:
        return BatchFilters(
            batch_id=batch_id,
            batch_started_at=batch_started_at,
            prefer=frozenset(),
            exclude_long=frozenset(),
            exclude_short=frozenset(),
            all_diagnostics=df,
            batch_comment=batch_comment,
        )

    prefer = frozenset(
        df[(df["rank_type"] == RANK_TYPE_TOP) & (df["rank_position"] <= prefer_top_n)]["symbol"]
    )
    exclude_long = frozenset(
        df[df["rank_type"].isin(EXCLUDE_LONG_RANK_TYPES)]["symbol"]
    )
    exclude_short = frozenset(
        df[df["rank_type"].isin(EXCLUDE_SHORT_RANK_TYPES)]["symbol"]
    )

    return BatchFilters(
        batch_id=batch_id,
        batch_started_at=batch_started_at,
        prefer=prefer,
        exclude_long=exclude_long,
        exclude_short=exclude_short,
        all_diagnostics=df,
        batch_comment=batch_comment,
    )


# ────────────────────────────────────────────────────────────────────
# Convenience: filter a predictions DataFrame
# ────────────────────────────────────────────────────────────────────

def filter_predictions(
    predictions: pd.DataFrame,
    filters: BatchFilters,
    *,
    side_column: str = "predicted_side",
    symbol_column: str = "symbol",
    boost_prefer_sizing: bool = False,
    prefer_multiplier: float | None = None,
) -> pd.DataFrame:
    """Filter a predictions DataFrame using batch diagnostics.

    Removes rows where the predicted side conflicts with exclusion lists,
    and optionally boosts a sizing column for preferred symbols.

    Args:
        predictions: DataFrame with columns ``symbol_column`` and ``side_column``.
        filters: Result from ``get_batch_filters()``.
        side_column: Name of the column containing "long" / "short" / "flat".
        symbol_column: Name of the symbol column.
        boost_prefer_sizing: If True, multiply ``sizing_mult`` column by
            ``prefer_multiplier`` for symbols in ``filters.prefer``.
        prefer_multiplier: Multiplier for preferred symbols.
            Default: read from config.yaml (batch_diagnostics.prefer_sizing_multiplier) or 1.2.

    Returns:
        Filtered DataFrame (new copy).
    """
    if predictions.empty:
        return predictions

    # ── Résoudre le prefer_multiplier depuis config.yaml ──
    if prefer_multiplier is None:
        prefer_multiplier = 1.2
        try:
            import yaml
            with open("config.yaml", encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            prefer_multiplier = float(
                (cfg.get("batch_diagnostics") or {}).get(
                    "prefer_sizing_multiplier", 1.2
                )
            )
        except Exception:
            pass

    df = predictions.copy()

    if side_column not in df.columns:
        return df

    side_col = df[side_column].astype(str).str.lower().str.strip()
    symbol_col = df[symbol_column].astype(str).str.upper().str.strip()

    # ── Exclude long ──
    exclude_long_mask = (side_col == "long") & symbol_col.isin(filters.exclude_long)
    # ── Exclude short ──
    exclude_short_mask = (side_col == "short") & symbol_col.isin(filters.exclude_short)

    filtered = df[~(exclude_long_mask | exclude_short_mask)].copy()

    n_excluded = len(df) - len(filtered)
    if n_excluded > 0:
        LOGGER.info(
            "batch_diagnostics: filtered %d predictions (exclude_long=%d exclude_short=%d)",
            n_excluded,
            exclude_long_mask.sum(),
            exclude_short_mask.sum(),
        )

    # ── Boost sizing for preferred symbols ──
    if boost_prefer_sizing and "sizing_mult" in filtered.columns:
        prefer_mask = symbol_col[filtered.index].isin(filters.prefer)
        if prefer_mask.any():
            filtered.loc[prefer_mask, "sizing_mult"] = (
                filtered.loc[prefer_mask, "sizing_mult"] * prefer_multiplier
            )
            LOGGER.info(
                "batch_diagnostics: boosted sizing for %d preferred symbols (×%.1f)",
                prefer_mask.sum(),
                prefer_multiplier,
            )

    return filtered

