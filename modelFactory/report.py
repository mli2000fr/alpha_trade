"""modelFactory/report.py — Génération de rapport Markdown par batch."""
from __future__ import annotations

import json

import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Requêtes (dupliquées de ml_diagnostics.py pour éviter dépendance circulaire)
# ---------------------------------------------------------------------------

BATCH_DETAIL_QUERY = """
    SELECT * FROM model_training_batch WHERE batch_id = :batch_id
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
      AND mm.model_name != 'global_model'
    GROUP BY mm.model_name, mm.split_name
    ORDER BY mm.model_name, FIELD(mm.split_name, 'train', 'val', 'test', 'wf')
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
      AND mm.model_name != 'global_model'
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
    JOIN alpha_trade.model_governance AS mg
        ON mg.symbol = mm.symbol AND mg.model_name = mm.model_name AND mg.is_selected_model = 1
    JOIN alpha_trade.model_training_run AS mtr_gov
        ON mtr_gov.run_id = mg.run_id AND mtr_gov.batch_id = :batch_id
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
    JOIN alpha_trade.model_governance AS mg
        ON mg.symbol = mm.symbol AND mg.model_name = mm.model_name AND mg.is_selected_model = 1
    JOIN alpha_trade.model_training_run AS mtr_gov
        ON mtr_gov.run_id = mg.run_id AND mtr_gov.batch_id = :batch_id
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
    JOIN alpha_trade.model_governance AS mg
        ON mg.symbol = mm.symbol AND mg.model_name = mm.model_name AND mg.is_selected_model = 1
    JOIN alpha_trade.model_training_run AS mtr_gov
        ON mtr_gov.run_id = mg.run_id AND mtr_gov.batch_id = :batch_id
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
    JOIN alpha_trade.model_governance AS mg
        ON mg.symbol = mm.symbol AND mg.model_name = mm.model_name AND mg.is_selected_model = 1
    JOIN alpha_trade.model_training_run AS mtr_gov
        ON mtr_gov.run_id = mg.run_id AND mtr_gov.batch_id = :batch_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
      AND mm.f1_short = 0
    LIMIT 10
"""

CHAMPION_MODE_QUERY = """
    SELECT
        mg.selection_mode,
        COUNT(DISTINCT mg.symbol) AS nb_symbols
    FROM alpha_trade.model_governance AS mg
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mg.run_id
    WHERE mtr.batch_id = :batch_id
      AND mg.is_selected_model = 1
    GROUP BY mg.selection_mode
    ORDER BY mg.selection_mode
"""

CHAMPION_BY_MODEL_QUERY = """
    SELECT
        mg.model_name,
        COUNT(DISTINCT mg.symbol) AS nb_symbols
    FROM alpha_trade.model_governance AS mg
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mg.run_id
    WHERE mtr.batch_id = :batch_id
      AND mg.is_selected_model = 1
    GROUP BY mg.model_name
    ORDER BY nb_symbols DESC
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_query(engine: Engine, query: str, params: dict | None = None) -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params=params or {})
    except Exception:
        return pd.DataFrame()


def _df_to_md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Aucune donnée._\n"
    return df.to_markdown(index=False) + "\n"


# ---------------------------------------------------------------------------
# Génération du rapport
# ---------------------------------------------------------------------------

def _append_champion_status(
    lines: list[str],
    champion_df: pd.DataFrame,
    champion_by_model_df: pd.DataFrame | None = None,
) -> None:
    """Ajoute la section statut champion (⚠️ fallback ou ✅ OK) + répartition par modèle."""
    if champion_df.empty:
        return

    mode_map: dict[str, int] = {}
    for _, row in champion_df.iterrows():
        mode_map[str(row["selection_mode"])] = int(row["nb_symbols"])

    total = sum(mode_map.values())
    auto_count = mode_map.get("auto_selected_champion", 0)
    fallback_count = mode_map.get("fallback_default_champion", 0)
    default_count = mode_map.get("default_champion", 0)
    problem_count = fallback_count + default_count

    lines.append("## 🏆 Sélection du champion")
    lines.append("")
    if problem_count == 0 and auto_count > 0:
        lines.append(f"✅ **Tout va bien** — {auto_count} champions sélectionnés automatiquement sur {total} symboles.")
    else:
        lines.append(f"⚠️ **{problem_count} symboles en fallback** sur {total} :")
        lines.append("")
        lines.append("| Mode | Nb symboles |")
        lines.append("|---|---|")
        if auto_count > 0:
            lines.append(f"| ✅ `auto_selected_champion` | {auto_count} |")
        if fallback_count > 0:
            lines.append(f"| ⚠️ `fallback_default_champion` | {fallback_count} |")
        if default_count > 0:
            lines.append(f"| ⚠️ `default_champion` | {default_count} |")
    lines.append("")

    # ── Répartition par modèle ──
    if champion_by_model_df is not None and not champion_by_model_df.empty:
        lines.append("### 📊 Champions par modèle")
        lines.append("")
        lines.append(_df_to_md(champion_by_model_df))


def generate_batch_report(engine: Engine, batch_id: str) -> str:
    """Génère un rapport Markdown complet pour un batch d'entraînement."""
    detail_df = _safe_query(engine, BATCH_DETAIL_QUERY, {"batch_id": batch_id})
    f1_df = _safe_query(engine, F1_BY_SPLIT_QUERY, {"batch_id": batch_id})
    tp_df = _safe_query(engine, TRUE_PRED_AGG_QUERY, {"batch_id": batch_id})
    bucket_df = _safe_query(engine, F1_BUCKET_QUERY, {"batch_id": batch_id})
    best_df = _safe_query(engine, TOP5_BEST_F1_QUERY, {"batch_id": batch_id})
    worst_df = _safe_query(engine, TOP5_WORST_F1_QUERY, {"batch_id": batch_id})
    zero_df = _safe_query(engine, ZERO_F1_SHORT_QUERY, {"batch_id": batch_id})
    champion_df = _safe_query(engine, CHAMPION_MODE_QUERY, {"batch_id": batch_id})
    champion_by_model_df = _safe_query(engine, CHAMPION_BY_MODEL_QUERY, {"batch_id": batch_id})

    lines: list[str] = []
    lines.append(f"# Diagnostic ML — Batch `{batch_id}`")
    lines.append("")

    # ── Détail du batch ──
    lines.append("## 📋 Détail du batch")
    lines.append("")
    if not detail_df.empty:
        row = detail_df.iloc[0]
        lines.append(f"- **Batch ID** : `{row.get('batch_id', '—')}`")
        lines.append(f"- **Statut** : {row.get('status', '—')}")
        lines.append(f"- **Source symboles** : {row.get('symbol_source', '—')}")
        comment = row.get("comment")
        if comment and str(comment) not in ("None", "nan", ""):
            lines.append(f"- **Commentaire** : {comment}")
        lines.append(f"- **Date début training** : {row.get('training_start_date', '—')}")
        lines.append(f"- **Date fin training** : {row.get('training_end_date', '—')}")
        lines.append(f"- **Date univers** : {row.get('universe_date', '—')}")
        lines.append(f"- **Nb symboles demandés** : {row.get('requested_symbol_count', '—')}")
        # ── IC Rank & Decile Spread du Global Ranking ──
        _ic = row.get("ic_rank")
        if _ic is not None and str(_ic) not in ("None", "nan", ""):
            lines.append(f"- **🎯 IC Rank Global** : {float(_ic):.4f}")
        _ds_h3 = row.get("decile_spread_h3")
        _ds_h5 = row.get("decile_spread_h5")
        _ds_h10 = row.get("decile_spread_h10")
        if _ds_h3 is not None or _ds_h5 is not None or _ds_h10 is not None:
            _ds_parts = []
            if _ds_h3 is not None and str(_ds_h3) not in ("None", "nan", ""):
                _ds_parts.append(f"H3={float(_ds_h3):.4f}")
            if _ds_h5 is not None and str(_ds_h5) not in ("None", "nan", ""):
                _ds_parts.append(f"H5={float(_ds_h5):.4f}")
            if _ds_h10 is not None and str(_ds_h10) not in ("None", "nan", ""):
                _ds_parts.append(f"H10={float(_ds_h10):.4f}")
            if _ds_parts:
                lines.append(f"- **📊 Decile Spread (Top−Bottom)** : {', '.join(_ds_parts)}")
        lines.append(f"- **Démarré le** : {row.get('started_at', '—')}")
        lines.append(f"- **Terminé le** : {row.get('finished_at', '—')}")
        lines.append(f"- **Complétés / Skippés / Échecs** : {row.get('symbols_completed', 0)} / {row.get('symbols_skipped', 0)} / {row.get('symbols_failed', 0)}")
        failure = row.get("failure_reason")
        if failure and str(failure) not in ("None", "nan", ""):
            lines.append(f"- **Raison échec** : {failure}")

        # ── Liquidité filtrée (Sprint 2026-07-24) ──
        _meta_raw = row.get("metadata_json")
        if _meta_raw and str(_meta_raw) not in ("None", "nan", ""):
            try:
                _meta = json.loads(str(_meta_raw))
                _liq = _meta.get("liquidity_filter")
                if isinstance(_liq, dict) and _liq.get("filtered_count", 0) > 0:
                    lines.append(f"- **Symboles filtrés (liquidité)** : {_liq['filtered_count']} exclus / {_liq['kept_count']} conservés")
                    _th = _liq.get("thresholds", {})
                    if _th:
                        lines.append(f"  - Seuils : vol ≥ {_th.get('min_avg_volume_20d', '—'):,}, "
                                     f"market cap ≥ ${_th.get('min_market_cap_proxy', '—'):,.0f}, "
                                     f"spread ≤ {_th.get('max_avg_spread_pct', '—')}%")
                    _details = _liq.get("details", {})
                    if _details:
                        lines.append("")
                        lines.append("### 🚫 Symboles filtrés par liquidité")
                        lines.append("")
                        lines.append("| Symbole | Raison |")
                        lines.append("|:---|:---|")
                        for sym, reason in sorted(_details.items()):
                            lines.append(f"| {sym} | {reason} |")
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        cmd = row.get("command_line")
        if cmd and str(cmd) not in ("None", "nan", ""):
            lines.append("")
            lines.append("### Commande exécutée")
            lines.append("```powershell")
            lines.append(str(cmd))
            lines.append("```")
    lines.append("")

    # ── Statut champion ──
    _append_champion_status(lines, champion_df, champion_by_model_df)

    # ── Métriques F1 par split ──
    lines.append("## 📊 Métriques F1 par split")
    lines.append("")
    lines.append(_df_to_md(f1_df))

    # ── Distribution true / pred par split ──
    lines.append("## 📊 Distribution true / pred par split")
    lines.append("")
    lines.append(_df_to_md(tp_df))

    # ── Distribution F1 macro WF ──
    lines.append("## 📈 Distribution F1 macro — Walk-Forward")
    lines.append("")
    lines.append(_df_to_md(bucket_df))

    # ── Top / Flop ──
    lines.append("## 🏆 Top 10 meilleurs `f1_macro` (WF)")
    lines.append("")
    lines.append(_df_to_md(best_df))

    lines.append("## 🥉 Top 10 plus mauvais `f1_macro` (WF)")
    lines.append("")
    lines.append(_df_to_md(worst_df))

    lines.append("## ⚪ `f1_short = 0` (WF)")
    lines.append("")
    lines.append(_df_to_md(zero_df))

    return "\n".join(lines)
