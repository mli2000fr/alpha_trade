"""ihm/pages/ml_diagnostics.py — Diagnostic ML (Analyse & Recherche)."""
from __future__ import annotations

import json as _json

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable
from ihm.services.db import db_available, safe_query


# ---------------------------------------------------------------------------
# Requêtes SQL
# ---------------------------------------------------------------------------

BATCH_LIST_QUERY = """
    SELECT
        batch_id,
        status,
        symbol_source,
        comment,
        training_start_date,
        training_end_date,
        finished_at
    FROM model_training_batch
    ORDER BY started_at DESC
    LIMIT 200
"""

BATCH_DETAIL_QUERY = """
    SELECT *
    FROM model_training_batch
    WHERE batch_id = :batch_id
"""

F1_BY_SPLIT_QUERY = """
    SELECT
        mm.split_name,
        COUNT(DISTINCT mm.symbol) AS nb_symbols,
        ROUND(AVG(mm.f1_macro), 3) AS avg_f1_macro,
        ROUND(AVG(mm.f1_short), 3) AS avg_f1_short,
        ROUND(AVG(mm.f1_flat), 3) AS avg_f1_flat,
        ROUND(AVG(mm.f1_long), 3) AS avg_f1_long
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
    GROUP BY mm.split_name
    ORDER BY FIELD(mm.split_name, 'train', 'val', 'test', 'wf')
"""

F1_BUCKET_QUERY = """
    SELECT
        CASE
            WHEN mm.f1_macro < 0.10 THEN '0.00-0.09'
            WHEN mm.f1_macro < 0.20 THEN '0.10-0.19'
            WHEN mm.f1_macro < 0.30 THEN '0.20-0.29'
            WHEN mm.f1_macro < 0.40 THEN '0.30-0.39'
            ELSE '0.40+'
        END AS wf_f1_macro_bucket,
        COUNT(DISTINCT mm.symbol) AS nb_symbols
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
    GROUP BY wf_f1_macro_bucket
    ORDER BY wf_f1_macro_bucket
"""

TOP5_BEST_F1_QUERY = """
    SELECT
        mm.symbol,
        ROUND(mm.f1_macro, 3) AS f1_macro,
        ROUND(mm.f1_long, 3) AS f1_long,
        ROUND(mm.f1_short, 3) AS f1_short,
        ROUND(mm.f1_flat, 3) AS f1_flat
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
    ORDER BY mm.f1_macro DESC
    LIMIT 10
"""

TOP5_WORST_F1_QUERY = """
    SELECT
        mm.symbol,
        ROUND(mm.f1_macro, 3) AS f1_macro,
        ROUND(mm.f1_long, 3) AS f1_long,
        ROUND(mm.f1_short, 3) AS f1_short,
        ROUND(mm.f1_flat, 3) AS f1_flat
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
    ORDER BY mm.f1_macro ASC
    LIMIT 10
"""

ZERO_F1_SHORT_QUERY = """
    SELECT
        mm.symbol,
        ROUND(mm.f1_macro, 3) AS f1_macro,
        ROUND(mm.f1_long, 3) AS f1_long,
        ROUND(mm.f1_short, 3) AS f1_short,
        ROUND(mm.f1_flat, 3) AS f1_flat
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
      AND mm.f1_short = 0
    LIMIT 10
"""

SYMBOL_METRICS_QUERY = """
    SELECT
        mm.split_name,
        ROUND(mm.true_short_pct, 3) AS true_short_pct,
        ROUND(mm.true_flat_pct, 3) AS true_flat_pct,
        ROUND(mm.true_long_pct, 3) AS true_long_pct,
        ROUND(mm.pred_short_pct, 3) AS pred_short_pct,
        ROUND(mm.pred_flat_pct, 3) AS pred_flat_pct,
        ROUND(mm.pred_long_pct, 3) AS pred_long_pct,
        ROUND(mm.f1_short, 3) AS f1_short,
        ROUND(mm.f1_flat, 3) AS f1_flat,
        ROUND(mm.f1_long, 3) AS f1_long,
        ROUND(mm.f1_macro, 3) AS f1_macro
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.symbol = :symbol
    ORDER BY FIELD(mm.split_name, 'train', 'val', 'test', 'wf')
"""

SYMBOL_WF_JSON_QUERY = """
    SELECT
        mmf.metrics_json,
        mtr.train_start_date,
        mtr.train_end_date
    FROM alpha_trade.model_metrics_full AS mmf
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mmf.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mmf.symbol = :symbol
    LIMIT 1
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BATCH_TABLE_KEY = "ml_diagnostics_batch_table"
BEST_TABLE_KEY = "ml_diagnostics_best_table"
WORST_TABLE_KEY = "ml_diagnostics_worst_table"
ZERO_TABLE_KEY = "ml_diagnostics_zero_table"


def _selected_row_index(table_key: str) -> int | None:
    state = st.session_state.get(table_key)
    if state is None:
        return None
    selection = getattr(state, "selection", None) or (state.get("selection") if isinstance(state, dict) else None)
    if not selection:
        return None
    rows = getattr(selection, "rows", None) or (selection.get("rows") if isinstance(selection, dict) else None)
    if not rows:
        return None
    try:
        return int(rows[0])
    except (TypeError, ValueError, IndexError):
        return None


def _status_badge(status: str) -> str:
    mapping = {
        "running": "🟨 En cours",
        "completed": "🟢 Terminé",
        "failed": "🔴 Échec",
    }
    return mapping.get(str(status).strip().lower(), str(status))


def _render_symbol_detail(batch_id: str, symbol: str) -> None:
    """Affiche le détail des métriques par split pour un symbole."""
    st.subheader(f"🔍 Détail symbole : `{symbol}`")

    # ── Métriques par split ──
    sym_df = safe_query(SYMBOL_METRICS_QUERY, {"batch_id": batch_id, "symbol": symbol})
    if sym_df.empty:
        st.info(f"Aucune métrique détaillée trouvée pour `{symbol}` dans ce batch.")
        return

    st.markdown("**Métriques par split**")
    st.dataframe(sym_df, use_container_width=True, hide_index=True)

    # ── Walk-Forward : splits et dates par fold ──
    st.markdown("**📅 Splits Walk-Forward**")
    wf_row = safe_query(SYMBOL_WF_JSON_QUERY, {"batch_id": batch_id, "symbol": symbol})
    if wf_row.empty:
        st.caption("Aucune donnée walk-forward.")
    else:
        row = wf_row.iloc[0]
        metrics_blob = row.get("metrics_json")
        wf_splits: list[dict] = []
        n_splits: int | None = None
        if metrics_blob is not None:
            try:
                if isinstance(metrics_blob, bytes):
                    metrics_blob = metrics_blob.decode("utf-8")
                wf_data = (_json.loads(metrics_blob) if isinstance(metrics_blob, str) else metrics_blob).get("walk_forward", {})
                if isinstance(wf_data, dict):
                    n_splits = wf_data.get("n_splits")
                    wf_splits = wf_data.get("splits", []) or []
            except Exception:
                pass

        if n_splits is not None:
            st.metric("Nombre de splits", n_splits)

        _has_fold_dates = any(
            s.get("train_start_date") or s.get("val_start_date") or s.get("test_start_date")
            for s in wf_splits
        ) if wf_splits else False

        if wf_splits and _has_fold_dates:
            folds_df = pd.DataFrame([
                {
                    "Split": s.get("split_index", "—"),
                    "Début train": s.get("train_start_date", "—"),
                    "Fin train": s.get("train_end_date", "—"),
                    "Début val": s.get("val_start_date", "—"),
                    "Fin val": s.get("val_end_date", "—"),
                    "Début test": s.get("test_start_date", "—"),
                    "Fin test": s.get("test_end_date", "—"),
                    "Lignes train": s.get("train_rows", "—"),
                    "Lignes val": s.get("val_rows", "—"),
                    "Lignes test": s.get("test_rows", "—"),
                }
                for s in wf_splits
            ])
            st.dataframe(folds_df, use_container_width=True, hide_index=True)
        else:
            # Fallback : dates globales du training run
            train_start = row.get("train_start_date", "—")
            train_end = row.get("train_end_date", "—")
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Début training (global)", str(train_start) if train_start and str(train_start) not in ("None", "nan", "") else "—")
            with c2:
                st.metric("Fin training (global)", str(train_end) if train_end and str(train_end) not in ("None", "nan", "") else "—")
            if wf_splits:
                st.caption("ℹ️ Les dates par fold seront disponibles après le prochain entraînement de ce symbole.")
            else:
                st.caption("Détail des folds non disponible (métriques antérieures à la mise à jour).")

    # ── Interprétation ──
    with st.expander("ℹ️ Aide à l'interprétation", expanded=False):
        st.markdown("""
- **Peu de `true_short_pct`** : le label est trop rare ou mal défini pour ce symbole.
- **`true_short_pct` normal mais `pred_short_pct` proche de zéro** : le modèle évite la classe `short`.
- **`pred_short_pct` élevé mais `f1_short` faible** : les signaux short sont bruyants ou les seuils de décision sont trop permissifs.
""")


def _render_batch_detail(batch: pd.Series) -> None:
    """Affiche le détail complet d'un batch."""
    st.subheader("📋 Détail du batch")

    detail_df = safe_query(BATCH_DETAIL_QUERY, {"batch_id": batch["batch_id"]})
    if detail_df.empty:
        st.warning("Impossible de charger le détail du batch.")
        return

    row = detail_df.iloc[0]
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Batch ID", str(row.get("batch_id", ""))[:32] + "…" if len(str(row.get("batch_id", ""))) > 32 else str(row.get("batch_id", "")))
        st.metric("Statut", _status_badge(str(row.get("status", ""))))
        st.metric("Source symboles", str(row.get("symbol_source", "")))
        comment_val = row.get("comment")
        st.metric("Commentaire", str(comment_val) if comment_val and str(comment_val) != "None" and str(comment_val) != "nan" else "—")

    with col2:
        st.metric("Date début training", str(row.get("training_start_date", "—")))
        st.metric("Date fin training", str(row.get("training_end_date", "—")))
        st.metric("Date univers", str(row.get("universe_date", "—")))
        st.metric("Nb symboles demandés", str(row.get("requested_symbol_count", "—")))

    with col3:
        st.metric("Démarré le", str(row.get("started_at", "—")))
        st.metric("Terminé le", str(row.get("finished_at", "—")))
        st.metric("Complétés / Skippés / Échecs",
                  f"{row.get('symbols_completed', 0)} / {row.get('symbols_skipped', 0)} / {row.get('symbols_failed', 0)}")
        failure = row.get("failure_reason")
        if failure and str(failure) != "None" and str(failure) != "nan":
            st.metric("Raison échec", str(failure)[:100] + "…" if len(str(failure)) > 100 else str(failure))

    # ── Bloc F1 par split ──
    st.subheader("📊 Métriques F1 par split")
    f1_df = safe_query(F1_BY_SPLIT_QUERY, {"batch_id": batch["batch_id"]})
    if f1_df.empty:
        st.info("Aucune métrique F1 disponible pour ce batch (vérifiez que les runs sont `completed`).")
    else:
        # Formater les colonnes numériques
        styled = f1_df.copy()
        for col in ["avg_f1_macro", "avg_f1_short", "avg_f1_flat", "avg_f1_long"]:
            if col in styled.columns:
                styled[col] = styled[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Bloc distribution F1 macro (walk-forward) ──
    st.subheader("📈 Distribution F1 macro — Walk-Forward")
    bucket_df = safe_query(F1_BUCKET_QUERY, {"batch_id": batch["batch_id"]})
    if bucket_df.empty:
        st.info("Aucune métrique walk-forward disponible pour ce batch.")
    else:
        col_chart, col_table = st.columns([3, 2])
        with col_chart:
            chart_df = bucket_df.set_index("wf_f1_macro_bucket")
            # Convertir en int pour le graphique
            chart_df["nb_symbols"] = pd.to_numeric(chart_df["nb_symbols"], errors="coerce").fillna(0).astype(int)
            st.bar_chart(chart_df["nb_symbols"], y_label="Nb symboles", x_label="Bucket F1 macro")
        with col_table:
            st.dataframe(bucket_df, use_container_width=True, hide_index=True)

    # ── Top 10 / Flop 10 / F1 short = 0 ──
    st.subheader("🏆 Top / Flop symboles — Walk-Forward")

    _ALL_SYMBOL_TABLE_KEYS = (BEST_TABLE_KEY, WORST_TABLE_KEY, ZERO_TABLE_KEY)

    def _make_exclusive_callback(own_key: str):
        """Callback : efface les sélections des 2 autres tableaux puis rerun."""
        def _cb() -> None:
            _empty = {"selection": {"rows": [], "columns": [], "cells": []}}
            for _tk in _ALL_SYMBOL_TABLE_KEYS:
                if _tk != own_key and _tk in st.session_state:
                    st.session_state[_tk] = _empty
            st.rerun()
        return _cb

    best_df = pd.DataFrame()
    worst_df = pd.DataFrame()
    zero_df = pd.DataFrame()

    col_best, col_worst, col_zero = st.columns(3)

    with col_best:
        st.markdown("**🥇 10 meilleurs `f1_macro`**")
        best_df = safe_query(TOP5_BEST_F1_QUERY, {"batch_id": batch["batch_id"]})
        if best_df.empty:
            st.caption("Aucune donnée.")
        else:
            st.dataframe(
                best_df, use_container_width=True, hide_index=True,
                on_select=_make_exclusive_callback(BEST_TABLE_KEY),
                selection_mode="single-row", key=BEST_TABLE_KEY,
            )

    with col_worst:
        st.markdown("**🥉 10 plus mauvais `f1_macro`**")
        worst_df = safe_query(TOP5_WORST_F1_QUERY, {"batch_id": batch["batch_id"]})
        if worst_df.empty:
            st.caption("Aucune donnée.")
        else:
            st.dataframe(
                worst_df, use_container_width=True, hide_index=True,
                on_select=_make_exclusive_callback(WORST_TABLE_KEY),
                selection_mode="single-row", key=WORST_TABLE_KEY,
            )

    with col_zero:
        st.markdown("**⚪ `f1_short = 0`**")
        zero_df = safe_query(ZERO_F1_SHORT_QUERY, {"batch_id": batch["batch_id"]})
        if zero_df.empty:
            st.caption("Aucun symbole avec f1_short = 0.")
        else:
            st.dataframe(
                zero_df, use_container_width=True, hide_index=True,
                on_select=_make_exclusive_callback(ZERO_TABLE_KEY),
                selection_mode="single-row", key=ZERO_TABLE_KEY,
            )

    # ── Détail symbole sélectionné ──
    selected_symbol: str | None = None
    for table_key in _ALL_SYMBOL_TABLE_KEYS:
        idx = _selected_row_index(table_key)
        if idx is None:
            continue
        if table_key == BEST_TABLE_KEY:
            lookup_df = best_df
        elif table_key == WORST_TABLE_KEY:
            lookup_df = worst_df
        else:
            lookup_df = zero_df
        if not lookup_df.empty and idx < len(lookup_df):
            selected_symbol = str(lookup_df.iloc[idx]["symbol"])
            break

    if selected_symbol:
        st.divider()
        _render_symbol_detail(str(batch["batch_id"]), selected_symbol)


# ---------------------------------------------------------------------------
# Page principale
# ---------------------------------------------------------------------------

def render() -> None:
    st.header("🩺 Diagnostic ML")
    st.caption("Analyse agrégée des batchs d'entraînement et de leurs métriques.")

    if not db_available():
        render_db_unavailable("Diagnostic ML", form_key="ml_diagnostics_db_form")
        return

    # ── Tableau des batchs ──
    st.subheader("📋 Batchs d'entraînement")

    batches_df = safe_query(BATCH_LIST_QUERY)
    if batches_df.empty:
        st.info("Aucun batch d'entraînement trouvé dans `model_training_batch`.")
        return

    # Formater les colonnes pour l'affichage
    display_df = batches_df.copy()
    if "status" in display_df.columns:
        display_df["status"] = display_df["status"].apply(_status_badge)
    if "comment" in display_df.columns:
        display_df["comment"] = display_df["comment"].fillna("—")
        display_df["comment"] = display_df["comment"].apply(
            lambda x: (str(x)[:60] + "…") if str(x) != "—" and len(str(x)) > 60 else str(x)
        )

    # Sélection d'un batch via dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=BATCH_TABLE_KEY,
    )

    row_index = _selected_row_index(BATCH_TABLE_KEY)
    if row_index is None:
        st.info("👆 Cliquez sur un batch dans le tableau ci-dessus pour afficher son détail et ses métriques.")
        return

    selected_batch = batches_df.iloc[row_index]

    st.divider()
    _render_batch_detail(selected_batch)


if __name__ == "__main__":
    render()
