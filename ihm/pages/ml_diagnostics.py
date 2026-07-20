"""ihm/pages/ml_diagnostics.py — Diagnostic ML (Analyse & Recherche)."""
from __future__ import annotations

import json as _json

import pandas as pd
import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable
from ihm.services.db import db_available, safe_query, get_engine
from modelFactory.report import generate_batch_report


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
        mm.model_name,
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
    GROUP BY mm.model_name, mm.split_name
    ORDER BY mm.model_name, FIELD(mm.split_name, 'train', 'val', 'test', 'wf')
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
        mm.model_name,
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
        mm.model_name,
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
        mm.model_name,
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

TRUE_PRED_AGG_QUERY = """
    SELECT
        mm.model_name,
        mm.split_name,
        COUNT(DISTINCT mm.symbol) AS nb_symbols,
        ROUND(AVG(mm.true_short_pct), 3) AS avg_true_short_pct,
        ROUND(AVG(mm.true_flat_pct), 3) AS avg_true_flat_pct,
        ROUND(AVG(mm.true_long_pct), 3) AS avg_true_long_pct,
        ROUND(AVG(mm.pred_short_pct), 3) AS avg_pred_short_pct,
        ROUND(AVG(mm.pred_flat_pct), 3) AS avg_pred_flat_pct,
        ROUND(AVG(mm.pred_long_pct), 3) AS avg_pred_long_pct
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
    GROUP BY mm.model_name, mm.split_name
    ORDER BY mm.model_name, FIELD(mm.split_name, 'train', 'val', 'test', 'wf')
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

ALL_WF_JSON_QUERY = """
    SELECT
        mmf.symbol,
        mmf.metrics_json
    FROM alpha_trade.model_metrics_full AS mmf
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mmf.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
"""

SPY_QUERY = """
    SELECT `date`, adj_close
    FROM alpha_trade.stock_bars_daily
    WHERE symbol = 'SPY'
    ORDER BY `date`
"""

VIX_QUERY = """
    SELECT trade_date, vix
    FROM alpha_trade.stock_macro_indicators_daily
    ORDER BY trade_date
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

    # ── Probas moyennes par split (depuis metrics.json) ──
    st.markdown("")
    st.markdown("**🎯 Probas moyennes par split (brutes → calibrées)**")
    probas_rows: list[dict] = []
    sym_wf = safe_query(SYMBOL_WF_JSON_QUERY, {"batch_id": batch_id, "symbol": symbol})
    if not sym_wf.empty:
        blob = sym_wf.iloc[0].get("metrics_json")
        if blob is not None:
            try:
                if isinstance(blob, bytes):
                    blob = blob.decode("utf-8")
                all_m = _json.loads(blob) if isinstance(blob, str) else blob
                for split_name in ("val", "test", "walk_forward"):
                    split_data = all_m.get(split_name, {})
                    if isinstance(split_data, dict):
                        row_p = {
                            "Split": split_name if split_name != "walk_forward" else "wf",
                            "brut short": round(split_data.get("avg_prob_short", 0) or 0, 3),
                            "brut flat": round(split_data.get("avg_prob_flat", 0) or 0, 3),
                            "brut long": round(split_data.get("avg_prob_long", 0) or 0, 3),
                            "calib short": round(split_data.get("avg_calib_prob_short", 0) or 0, 3),
                            "calib flat": round(split_data.get("avg_calib_prob_flat", 0) or 0, 3),
                            "calib long": round(split_data.get("avg_calib_prob_long", 0) or 0, 3),
                        }
                        if any(v != 0 for v in [row_p["brut short"], row_p["brut flat"], row_p["brut long"]]):
                            probas_rows.append(row_p)
            except Exception:
                pass
    if probas_rows:
        probas_df = pd.DataFrame(probas_rows)
        st.dataframe(probas_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Probas non disponibles (seront renseignées au prochain entraînement).")

    st.markdown("")
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

    st.markdown("")
    # ── Interprétation ──
    with st.expander("ℹ️ Aide à l'interprétation", expanded=False):
        st.markdown("""
- **Peu de `true_short_pct`** : le label est trop rare ou mal défini pour ce symbole.
- **`true_short_pct` normal mais `pred_short_pct` proche de zéro** : le modèle évite la classe `short`.
- **`pred_short_pct` élevé mais `f1_short` faible** : les signaux short sont bruyants ou les seuils de décision sont trop permissifs.
""")


def _classify_regime(spy_return_pct: float, vix: float, median_vix: float) -> str:
    """Classifie le régime de marché d'une période OOS."""
    if spy_return_pct < 0 and vix > median_vix:
        return "bear_high_vol"
    if spy_return_pct > 0 and vix <= median_vix:
        return "bull"
    if abs(spy_return_pct) < 2 and vix > median_vix:
        return "range_high_vol"
    return "range_low_vol"


_REGIME_LABELS: dict[str, str] = {
    "bear_high_vol": "🔴 Bear high vol",
    "bull": "🟢 Bull",
    "range_high_vol": "🟠 Range high vol",
    "range_low_vol": "🔵 Range low vol",
}


def _render_regime_table(batch_id: str) -> None:
    """Affiche le tableau de diagnostic par régime (§3.4 du plan ML)."""
    st.subheader("📅 Diagnostic par régime de marché — Walk-Forward")

    # ── 1. Récupérer tous les metrics_json du batch ──
    all_json_df = safe_query(ALL_WF_JSON_QUERY, {"batch_id": batch_id})
    if all_json_df.empty:
        st.info("Aucune donnée walk-forward détaillée disponible pour ce batch.")
        return

    # ── 2. Parser les folds ──
    folds_data: list[dict] = []
    for _, row in all_json_df.iterrows():
        blob = row.get("metrics_json")
        if blob is None:
            continue
        try:
            if isinstance(blob, bytes):
                blob = blob.decode("utf-8")
            wf_data = (_json.loads(blob) if isinstance(blob, str) else blob).get("walk_forward", {})
            splits = wf_data.get("splits", []) if isinstance(wf_data, dict) else []
        except Exception:
            continue
        for s in splits:
            oos_start = s.get("test_start_date")
            oos_end = s.get("test_end_date")
            if not oos_start or not oos_end:
                continue
            folds_data.append({
                "split_index": s.get("split_index"),
                "oos_start": str(oos_start),
                "oos_end": str(oos_end),
                "f1_macro": s.get("f1_macro"),
                "f1_short": s.get("f1_short"),
                "f1_flat": s.get("f1_flat"),
                "f1_long": s.get("f1_long"),
                "action_rate": s.get("action_rate"),
            })

    if not folds_data:
        st.info("Aucun fold OOS avec dates trouvé (les métriques datent peut-être d'avant la mise à jour).")
        return

    folds_df = pd.DataFrame(folds_data)

    # ── 3. Agréger par split_index ──
    agg = folds_df.groupby(["split_index", "oos_start", "oos_end"], dropna=False).agg(
        nb_symbols=("f1_macro", "count"),
        f1_macro=("f1_macro", "mean"),
        f1_short=("f1_short", "mean"),
        f1_flat=("f1_flat", "mean"),
        f1_long=("f1_long", "mean"),
        action_rate=("action_rate", "mean"),
    ).reset_index().sort_values("oos_start")

    if agg.empty:
        st.info("Agrégation vide.")
        return

    # ── 4. Récupérer SPY et VIX ──
    spy_df = safe_query(SPY_QUERY)
    vix_df = safe_query(VIX_QUERY)

    def _spy_return(start: str, end: str) -> float | None:
        if spy_df.empty or "date" not in spy_df.columns:
            return None
        spy_df["date"] = pd.to_datetime(spy_df["date"])
        mask = (spy_df["date"] >= pd.Timestamp(start)) & (spy_df["date"] <= pd.Timestamp(end))
        window = spy_df.loc[mask].sort_values("date")
        if len(window) < 2:
            return None
        p0 = window["adj_close"].iloc[0]
        p1 = window["adj_close"].iloc[-1]
        return float(100 * (p1 / p0 - 1)) if p0 and p0 > 0 else None

    def _avg_vix(start: str, end: str) -> float | None:
        if vix_df.empty or "trade_date" not in vix_df.columns:
            return None
        vix_df["trade_date"] = pd.to_datetime(vix_df["trade_date"])
        mask = (vix_df["trade_date"] >= pd.Timestamp(start)) & (vix_df["trade_date"] <= pd.Timestamp(end))
        vals = vix_df.loc[mask, "vix"].dropna()
        return float(vals.mean()) if len(vals) > 0 else None

    spy_returns = []
    vix_values = []
    for _, r in agg.iterrows():
        sr = _spy_return(str(r["oos_start"]), str(r["oos_end"]))
        vx = _avg_vix(str(r["oos_start"]), str(r["oos_end"]))
        spy_returns.append(sr)
        vix_values.append(vx)

    agg["spy_return_pct"] = spy_returns
    agg["avg_vix"] = vix_values

    # ── 5. Classifier les régimes ──
    valid_vix = [v for v in vix_values if v is not None]
    median_vix = float(pd.Series(valid_vix).median()) if valid_vix else 20.0

    def _safe_regime(sr: float | None, vx: float | None) -> str:
        if sr is None or vx is None:
            return "—"
        return _REGIME_LABELS.get(_classify_regime(sr, vx, median_vix), _classify_regime(sr, vx, median_vix))

    agg["regime"] = [_safe_regime(sr, vx) for sr, vx in zip(spy_returns, vix_values)]

    # ── 6. Affichage ──
    display = agg.rename(columns={
        "split_index": "Split",
        "oos_start": "Début OOS",
        "oos_end": "Fin OOS",
        "nb_symbols": "Nb symboles",
        "f1_macro": "F1 macro",
        "f1_short": "F1 short",
        "f1_flat": "F1 flat",
        "f1_long": "F1 long",
        "action_rate": "Taux action",
        "spy_return_pct": "SPY %",
        "avg_vix": "VIX moy",
        "regime": "Régime",
    })

    # Formater
    for col in ["F1 macro", "F1 short", "F1 flat", "F1 long"]:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
    if "Taux action" in display.columns:
        display["Taux action"] = display["Taux action"].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
    if "SPY %" in display.columns:
        display["SPY %"] = display["SPY %"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
    if "VIX moy" in display.columns:
        display["VIX moy"] = display["VIX moy"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")

    cols = ["Split", "Début OOS", "Fin OOS", "Régime", "F1 macro", "F1 short", "F1 flat", "F1 long", "Taux action", "SPY %", "VIX moy", "Nb symboles"]
    display = display[[c for c in cols if c in display.columns]]

    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption(f"Classification basée sur la médiane VIX = {median_vix:.1f} | SPY < 0 & VIX > médiane → bear_high_vol | SPY > 0 & VIX ≤ médiane → bull")


def _render_batch_detail(batch: pd.Series) -> None:
    """Affiche le détail complet d'un batch."""
    batch_id = str(batch["batch_id"])
    st.subheader("📋 Détail du batch")

    detail_df = safe_query(BATCH_DETAIL_QUERY, {"batch_id": batch_id})
    if detail_df.empty:
        st.warning("Impossible de charger le détail du batch.")
        return

    # ── Bouton téléchargement ──
    safe_bid = batch_id.replace("/", "_").replace("\\", "_")[:64]
    engine = get_engine()
    if engine is not None:
        st.download_button(
            label="📥 Télécharger le rapport (.md)",
            data=generate_batch_report(engine, batch_id),
            file_name=f"{safe_bid}.md",
            mime="text/markdown",
            key=f"dl_{safe_bid}",
        )

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

    cmd = row.get("command_line")
    if cmd and str(cmd) not in ("None", "nan", ""):
        with st.expander("💻 Commande exécutée", expanded=False):
            st.code(str(cmd), language="powershell")

    st.markdown("")
    # ── Statut sélection du champion ──
    champion_df = safe_query(
        """SELECT mg.selection_mode, COUNT(DISTINCT mg.symbol) AS nb_symbols
           FROM alpha_trade.model_governance AS mg
           JOIN alpha_trade.model_training_run AS mtr ON mtr.run_id = mg.run_id
           WHERE mtr.batch_id = :batch_id AND mg.is_selected_model = 1
           GROUP BY mg.selection_mode""",
        {"batch_id": batch["batch_id"]},
    )
    if not champion_df.empty:
        mode_map: dict[str, int] = {}
        for _, crow in champion_df.iterrows():
            mode_map[str(crow["selection_mode"])] = int(crow["nb_symbols"])
        auto_count = mode_map.get("auto_selected_champion", 0)
        fallback_count = mode_map.get("fallback_default_champion", 0)
        default_count = mode_map.get("default_champion", 0)
        problem_count = fallback_count + default_count
        total = sum(mode_map.values())

        if problem_count == 0 and auto_count > 0:
            st.success(f"✅ Sélection du champion : {auto_count}/{total} symboles en `auto_selected_champion` — tout va bien.")
        elif problem_count > 0:
            st.error(
                f"⚠️ Sélection du champion : **{problem_count} fallback(s)** sur {total} symboles "
                f"(auto={auto_count}, fallback_default={fallback_count}, default={default_count}). "
                f"Vérifiez les logs pour les raisons d'inéligibilité."
            )

        # ── Répartition champions par modèle ──
        champion_by_model_df = safe_query(
            """SELECT mg.model_name, COUNT(DISTINCT mg.symbol) AS nb_symbols
               FROM alpha_trade.model_governance AS mg
               JOIN alpha_trade.model_training_run AS mtr ON mtr.run_id = mg.run_id
               WHERE mtr.batch_id = :batch_id AND mg.is_selected_model = 1
               GROUP BY mg.model_name
               ORDER BY nb_symbols DESC""",
            {"batch_id": batch["batch_id"]},
        )
        if not champion_by_model_df.empty:
            st.markdown("**Champions par modèle :**")
            cols_model = st.columns(len(champion_by_model_df))
            for idx, (_, crow) in enumerate(champion_by_model_df.iterrows()):
                model_label = str(crow["model_name"]).replace("_", " ").title()
                count = int(crow["nb_symbols"])
                pct = f"{100 * count / total:.0f}%" if total > 0 else "—"
                with cols_model[idx]:
                    st.metric(label=model_label, value=f"{count} ({pct})")

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

    st.markdown("")
    # ── Bloc distribution true / pred par split ──
    st.subheader("📊 Distribution true / pred par split")
    tp_df = safe_query(TRUE_PRED_AGG_QUERY, {"batch_id": batch["batch_id"]})
    if tp_df.empty:
        st.info("Aucune donnée true_*_pct / pred_*_pct disponible (vérifiez que le mode ternaire est activé).")
    else:
        # Ligne Total (moyenne globale toutes splits/modeles confondus)
        total_row: dict[str, object] = {
            "model_name": "TOTAL",
            "split_name": "",
            "nb_symbols": tp_df["nb_symbols"].sum() if "nb_symbols" in tp_df.columns else 0,
        }
        for col in ["avg_true_short_pct", "avg_true_flat_pct", "avg_true_long_pct",
                     "avg_pred_short_pct", "avg_pred_flat_pct", "avg_pred_long_pct"]:
            if col in tp_df.columns:
                total_row[col] = round(float(tp_df[col].mean()), 3) if not tp_df[col].isna().all() else None
        total_df_row = pd.DataFrame([total_row])
        display_df = pd.concat([tp_df, total_df_row], ignore_index=True)

        styled = display_df.copy()
        for col in ["avg_true_short_pct", "avg_true_flat_pct", "avg_true_long_pct",
                     "avg_pred_short_pct", "avg_pred_flat_pct", "avg_pred_long_pct"]:
            if col in styled.columns:
                styled[col] = styled[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        styled = styled.rename(columns={
            "model_name": "Modèle",
            "split_name": "Split",
            "nb_symbols": "Nb symboles",
            "avg_true_short_pct": "true short %",
            "avg_true_flat_pct": "true flat %",
            "avg_true_long_pct": "true long %",
            "avg_pred_short_pct": "pred short %",
            "avg_pred_flat_pct": "pred flat %",
            "avg_pred_long_pct": "pred long %",
        })
        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("")
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

    st.markdown("")
    # ── Diagnostic par régime (§3.4) ──
    _render_regime_table(str(batch["batch_id"]))

    st.markdown("")
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
