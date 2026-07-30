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


def _append_global_ranking_horizon_details(
    lines: list[str],
    metadata_json_str: str | None,
) -> None:
    """Ajoute la section Global Ranking par horizon (IC, decile spread,
    feature importance, splits)."""
    if not metadata_json_str or str(metadata_json_str) in ("None", "nan", ""):
        return

    try:
        _meta = json.loads(str(metadata_json_str))
    except (json.JSONDecodeError, TypeError):
        return

    _gr = _meta.get("global_ranking")
    if not _gr or not isinstance(_gr, dict):
        return

    _hd = _gr.get("horizon_details")
    if not _hd or not isinstance(_hd, dict):
        return

    lines.append("## 🌐 Global Ranking — Détails par Horizon")
    lines.append("")
    lines.append(
        f"Modèle LightGBM LambdaRank — {_gr.get('symbols_count', '?')} symboles, "
        f"{_gr.get('splits_count', '?')} splits walk-forward, "
        f"{_gr.get('pred_rows', '?')} lignes de prédiction"
    )
    lines.append("")

    _ic_by_h = _gr.get("ic_by_horizon", {})
    _ds_by_h = _gr.get("decile_spreads", {})

    # ── Tableau récapitulatif tous horizons ──
    _summary_rows: list[dict] = []
    for _h_key in sorted(_hd.keys(), key=lambda x: int(x)):
        _h_info = _hd[_h_key]
        _h_ic = _ic_by_h.get(_h_key)
        # IC IR = IC Mean / IC Std (depuis les splits)
        _split_ics = [s.get("ic_rank") for s in _h_info.get("splits", []) if s.get("ic_rank") is not None]
        _h_ic_ir = None
        if _split_ics and len(_split_ics) > 1:
            import numpy as np
            _arr = np.array(_split_ics, dtype=float)
            if _arr.std() > 0:
                _h_ic_ir = round(float(_arr.mean() / _arr.std()), 2)
        _summary_rows.append({
            "Horizon": f"H{_h_key}",
            "IC Mean": _h_ic,
            "IC IR": _h_ic_ir if _h_ic_ir is not None else "—",
            "Decile Spread": _ds_by_h.get(_h_key),
            "Nb Features": _h_info.get("n_features", "—"),
            "Nb Splits": len(_h_info.get("splits", [])),
        })

    if _summary_rows:
        lines.append("### 📋 Récapitulatif tous horizons")
        lines.append("")
        lines.append(_df_to_md(pd.DataFrame(_summary_rows)))

    # ── Détail par horizon ──
    for _h_key in sorted(_hd.keys(), key=lambda x: int(x)):
        _h_info = _hd[_h_key]
        _ic_val = _ic_by_h.get(_h_key, 0) or 0
        _ds_val = _ds_by_h.get(_h_key, 0) or 0

        lines.append(f"### Horizon H{_h_key}")
        lines.append("")
        lines.append(f"- **IC Rank** : {_ic_val:.4f}")
        lines.append(f"- **Decile Spread** : {_ds_val:.4f}")
        lines.append(f"- **Nb Features** : {_h_info.get('n_features', '—')}")
        lines.append("")

        # ── Feature Importance Top10 / Bottom10 ──
        _fi_top10 = _h_info.get("feature_importance_top10", [])
        _fi_bottom10 = _h_info.get("feature_importance_bottom10", [])

        if _fi_top10 or _fi_bottom10:
            lines.append("#### 🔝 Feature Importance — Top 10 / Bottom 10")
            lines.append("")
            # Tableau combiné Top 10 | Bottom 10
            _max_len = max(len(_fi_top10), len(_fi_bottom10))
            lines.append("| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |")
            lines.append("|---:|:---|---:|:---|---:|")
            for _i in range(_max_len):
                _top_feat = _fi_top10[_i].get("feature", "") if _i < len(_fi_top10) else ""
                _top_imp = f"{_fi_top10[_i].get('importance', 0):.1f}" if _i < len(_fi_top10) else ""
                _bot_feat = _fi_bottom10[_i].get("feature", "") if _i < len(_fi_bottom10) else ""
                _bot_imp = f"{_fi_bottom10[_i].get('importance', 0):.1f}" if _i < len(_fi_bottom10) else ""
                lines.append(f"| {_i + 1} | `{_top_feat}` | {_top_imp} | `{_bot_feat}` | {_bot_imp} |")
            lines.append("")

        # ── Tableau des splits ──
        _splits = _h_info.get("splits", [])
        if _splits:
            lines.append("#### 📅 Détail par split")
            lines.append("")
            _split_rows: list[dict] = []
            for _sp in _splits:
                _train_start = str(_sp.get("train_period_start", ""))[:10] if _sp.get("train_period_start") else "—"
                _train_end = str(_sp.get("train_period_end", ""))[:10] if _sp.get("train_period_end") else "—"
                _val_start = str(_sp.get("val_period_start", ""))[:10] if _sp.get("val_period_start") else "—"
                _val_end = str(_sp.get("val_period_end", ""))[:10] if _sp.get("val_period_end") else "—"
                _split_rows.append({
                    "Split": _sp.get("split_index", "—"),
                    "Train (début→fin)": f"{_train_start} → {_train_end}",
                    "Validation (début→fin)": f"{_val_start} → {_val_end}",
                    "Lignes Train": _sp.get("train_rows", "—"),
                    "Lignes Val": _sp.get("val_rows", "—"),
                    "IC Rank": _sp.get("ic_rank"),
                })
            lines.append(_df_to_md(pd.DataFrame(_split_rows)))

        # ── Stats distribution IC par split ──
        _split_ics = [_sp.get("ic_rank") for _sp in _splits if _sp.get("ic_rank") is not None]
        if _split_ics:
            import numpy as np
            _arr = np.array(_split_ics, dtype=float)
            lines.append(f"- IC Moyen = {_arr.mean():.4f}  |  IC Std = {_arr.std():.4f}  |  IC Min = {_arr.min():.4f}  |  IC Max = {_arr.max():.4f}")
            lines.append("")


def _append_per_symbol_ic(
    lines: list[str],
    metadata_json_str: str | None,
) -> None:
    """Ajoute la section IC cross-sectionnel des modèles per-symbol (multi-horizon)."""
    if not metadata_json_str or str(metadata_json_str) in ("None", "nan", ""):
        return

    try:
        _meta = json.loads(str(metadata_json_str))
    except (json.JSONDecodeError, TypeError):
        return

    _ps_ic = _meta.get("per_symbol_ic")
    if not _ps_ic or not isinstance(_ps_ic, dict):
        return

    # Détection format : multi-horizon {"3": {...}, "5": {...}} ou single {"ic_mean": ...}
    _first_val = next(iter(_ps_ic.values()), None)
    if isinstance(_first_val, dict) and "ic_mean" in _first_val:
        # Format multi-horizon
        _horizons = sorted(_ps_ic.keys(), key=lambda x: int(x))
        lines.append("## 🔬 IC Cross-Sectionnel — Modèles Per-Symbol")
        lines.append("")
        _ps_rows = []
        for _h_key in _horizons:
            _h_info = _ps_ic[_h_key]
            _h_ic = _h_info.get("ic_mean")
            if _h_ic is None:
                continue
            _h_std = _h_info.get("ic_std")
            _h_n = _h_info.get("n_dates", "—")
            _ps_rows.append({
                "Horizon": f"H{_h_key}",
                "IC Mean": _h_ic,
                "IC IR": round(_h_ic / float(_h_std), 2) if _h_std and float(_h_std) > 0 else "—",
                "Nb Dates": _h_n,
            })
        if _ps_rows:
            lines.append(_df_to_md(pd.DataFrame(_ps_rows)))
        lines.append(
            "L'IC Rank cross-sectionnel mesure la capacité des **modèles per-symbol** "
            "(une fois agrégés) à classer les actions par rendement futur. "
            ">0.01 = utile, >0.02 = bon. "
            "À comparer avec l'IC Rank du **Global Ranking Model** pour évaluer "
            "la valeur ajoutée du stacking."
        )
        lines.append("")
        return

    # Format single-horizon (rétro-compatibilité)
    _ic_mean = _ps_ic.get("ic_mean")
    if _ic_mean is None:
        return

    _ic_std = _ps_ic.get("ic_std")
    _n_dates = _ps_ic.get("n_dates", "—")
    _horizon = _ps_ic.get("horizon", 5)

    lines.append("## 🔬 IC Cross-Sectionnel — Modèles Per-Symbol")
    lines.append("")
    lines.append(f"- **IC Rank Per-Symbol (H{_horizon})** : {_ic_mean:.4f}")
    if _ic_std is not None and float(_ic_std) > 0:
        _ir = _ic_mean / float(_ic_std)
        lines.append(f"- **IC IR (Stabilité)** : {_ir:.2f}")
    lines.append(f"- **Nb dates** : {_n_dates}")
    lines.append("")
    lines.append(
        "L'IC Rank cross-sectionnel mesure la capacité des **modèles per-symbol** "
        "(une fois agrégés) à classer les actions par rendement futur. "
        ">0.01 = utile, >0.02 = bon. "
        "À comparer avec l'IC Rank du **Global Ranking Model** pour évaluer "
        "la valeur ajoutée du stacking."
    )
    lines.append("")


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
        # ── IC Rank, IC IR & Decile Spread du Global Ranking ──
        _ic = row.get("ic_rank")
        if _ic is not None and str(_ic) not in ("None", "nan", ""):
            lines.append(f"- **🎯 IC Rank Global** : {float(_ic):.4f}")
        _ic_std = row.get("ic_rank_std")
        if _ic is not None and _ic_std is not None and str(_ic_std) not in ("None", "nan", "") and float(_ic_std) > 0:
            _ic_ir = float(_ic) / float(_ic_std)
            lines.append(f"- **📈 IC IR (Stabilité)** : {_ic_ir:.2f}  (IC Mean / IC Std)")
        _ds_h3 = row.get("decile_spread_h3")
        _ds_h5 = row.get("decile_spread_h5")
        _ds_h10 = row.get("decile_spread_h10")
        # Compléter avec metadata_json pour H15, H20
        _ds_all: dict[str, float] = {}
        _meta_raw2 = row.get("metadata_json")
        if _meta_raw2 and str(_meta_raw2) not in ("None", "nan", ""):
            try:
                _meta2 = json.loads(str(_meta_raw2))
                _gr2 = _meta2.get("global_ranking") if isinstance(_meta2, dict) else None
                _ds_json = _gr2.get("decile_spreads") if isinstance(_gr2, dict) else None
                if isinstance(_ds_json, dict):
                    for _hk, _hv in _ds_json.items():
                        if _hv is not None:
                            try:
                                _ds_all[str(_hk)] = float(_hv)
                            except (TypeError, ValueError):
                                pass
            except Exception:
                pass
        if not _ds_all:
            if _ds_h3 is not None and str(_ds_h3) not in ("None", "nan", ""):
                _ds_all["3"] = float(_ds_h3)
            if _ds_h5 is not None and str(_ds_h5) not in ("None", "nan", ""):
                _ds_all["5"] = float(_ds_h5)
            if _ds_h10 is not None and str(_ds_h10) not in ("None", "nan", ""):
                _ds_all["10"] = float(_ds_h10)
        if _ds_all:
            _ds_parts = [f"H{k}={v:.4f}" for k, v in sorted(_ds_all.items(), key=lambda x: int(x[0]))]
            lines.append(f"- **📊 Decile Spread (Top−Bottom)** : {' '.join(_ds_parts)}")

        # ── Stacking Global Rank ──
        _stacking = row.get("stacking_enabled")
        if _stacking is not None:
            _stacking_label = "Oui" if int(_stacking) == 1 else "Non"
            lines.append(f"- **📥 Stacking Global Rank** : {_stacking_label}")

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

    # ── Global Ranking Horizon Details ──
    _meta_raw = detail_df.iloc[0].get("metadata_json") if not detail_df.empty else None
    _append_global_ranking_horizon_details(lines, str(_meta_raw) if _meta_raw is not None else None)

    # ── Per-Symbol Cross-Sectional IC ──
    _append_per_symbol_ic(lines, str(_meta_raw) if _meta_raw is not None else None)

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
