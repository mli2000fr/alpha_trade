"""modelFactory/report.py — Génération de rapport Markdown par batch."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Requêtes (dupliquées de ml_diagnostics.py pour éviter dépendance circulaire)
# ---------------------------------------------------------------------------

BATCH_DETAIL_QUERY = """
    SELECT * FROM model_training_batch WHERE batch_id = :batch_id
"""

HORIZON_LIST_QUERY = """
    SELECT DISTINCT mm.horizon
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mm.horizon IS NOT NULL
    ORDER BY mm.horizon
"""

F1_BY_HORIZON_QUERY = """
    SELECT
        mm.horizon,
        ROUND(AVG(mm.f1_macro), 3) AS f1_macro,
        ROUND(AVG(mm.f1_short), 3) AS f1_short,
        ROUND(AVG(mm.f1_long), 3) AS f1_long,
        ROUND(AVG(mm.directional_accuracy), 4) AS dir_acc
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
      AND mm.horizon IS NOT NULL
    GROUP BY mm.horizon
    ORDER BY mm.horizon
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
        mm.model_name,
        mm.horizon,
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
        mm.model_name,
        mm.horizon,
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

# ── Métriques régression (target continue) ──
REG_BY_SPLIT_QUERY = """
    SELECT
        mm.model_name,
        mm.split_name,
        COUNT(DISTINCT mm.symbol) AS nb_symbols,
        ROUND(AVG(mm.loss), 6) AS avg_mse,
        ROUND(AVG(mm.directional_accuracy), 4) AS avg_dir_acc
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.model_name != 'global_model'
    GROUP BY mm.model_name, mm.split_name
    ORDER BY mm.model_name, FIELD(mm.split_name, 'train', 'val', 'test', 'wf')
"""

REG_TOP_QUERY = """
    SELECT
        mm.model_name, mm.symbol, mm.horizon,
        ROUND(mm.directional_accuracy, 4) AS dir_acc,
        ROUND(mm.loss, 4) AS mse
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id AND mtr.status = 'completed'
      AND mm.split_name = 'wf' AND mm.model_name != 'global_model'
      AND mm.directional_accuracy IS NOT NULL
    ORDER BY mm.directional_accuracy DESC LIMIT 10
"""

REG_WORST_QUERY = """
    SELECT
        mm.model_name, mm.symbol, mm.horizon,
        ROUND(mm.directional_accuracy, 4) AS dir_acc,
        ROUND(mm.loss, 4) AS mse
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id AND mtr.status = 'completed'
      AND mm.split_name = 'wf' AND mm.model_name != 'global_model'
      AND mm.directional_accuracy IS NOT NULL
    ORDER BY mm.directional_accuracy ASC LIMIT 10
"""

# ── Régime de marché ──
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

_REGIME_LABELS: dict[str, str] = {
    "bear_high_vol": "🔴 Bear high vol",
    "bull": "🟢 Bull",
    "range_high_vol": "🟠 Range high vol",
    "range_low_vol": "🔵 Range low vol",
}


def _classify_regime(spy_return_pct: float, vix: float, median_vix: float) -> str:
    if spy_return_pct < 0 and vix > median_vix:
        return "bear_high_vol"
    if spy_return_pct > 0 and vix <= median_vix:
        return "bull"
    if abs(spy_return_pct) < 2 and vix > median_vix:
        return "range_high_vol"
    return "range_low_vol"


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

    lines.append("### 🏆 Sélection du champion")
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

    # ── Infos modèle (champion ou fixe) ──
    _model_label = str(_gr.get("backend_model_name") or "CatBoost")  # fallback
    _champion_by_h = _gr.get("champion_by_horizon")
    # Fallback: reconstruire champion_by_horizon depuis horizon_details si absent (bug orchestrator)
    if (not _champion_by_h or not isinstance(_champion_by_h, dict)) and _hd:
        _rebuilt: dict[str, str] = {}
        for _hk, _hi in _hd.items():
            if isinstance(_hi, dict) and _hi.get("champion"):
                _rebuilt[str(_hk)] = str(_hi["champion"])
        if _rebuilt:
            _champion_by_h = _rebuilt
    if _champion_by_h and isinstance(_champion_by_h, dict) and _champion_by_h:
        from collections import Counter
        _counts = Counter(_champion_by_h.values())
        _majority = _counts.most_common(1)[0][0]
        _model_label = (
            f"🏆 Champion: {_majority} "
            f"(détail: {', '.join(f'H{k}={v}' for k, v in sorted(_champion_by_h.items(), key=lambda x: int(x[0])))}) "
            f"— sélection par IC IR"
        )
    lines.append(
        f"Modèle {_model_label} — {_gr.get('symbols_count', '?')} symboles, "
        f"{_gr.get('splits_count', '?')} splits walk-forward, "
        f"{_gr.get('pred_rows', '?')} lignes de prédiction"
    )
    lines.append("")

    _ic_by_h = _gr.get("ic_by_horizon", {})
    _ds_by_h = _gr.get("decile_spreads", {})

    # ── Tableau récapitulatif tous horizons ──
    _summary_rows: list[dict] = []
    _has_champion = bool(_champion_by_h)
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
        _row: dict = {
            "Horizon": f"H{_h_key}",
            "IC Mean": _h_ic,
            "IC IR": _h_ic_ir if _h_ic_ir is not None else "—",
            "Decile Spread": _ds_by_h.get(_h_key),
            "Nb Features": _h_info.get("n_features", "—"),
            "Nb Splits": len(_h_info.get("splits", [])),
        }
        if _has_champion:
            _row["🏆 Champion"] = str(_champion_by_h.get(_h_key, "—"))
            # Score composite du champion
            _cs = _h_info.get("champion_score")
            if _cs is not None:
                _row["Score"] = f"{float(_cs):.3f}"
            # Ajouter les IC et IR par candidat
            _candidates = _h_info.get("candidates", {})
            for _cn, _cdata in sorted((_candidates or {}).items()):
                if isinstance(_cdata, dict):
                    _ic_val = _cdata.get("ic_mean")
                    _ir_val = _cdata.get("ic_ir")
                    _row[f"IC {_cn}"] = f"{_ic_val:.4f}" if _ic_val is not None else "—"
                    _row[f"IR {_cn}"] = f"{_ir_val:.2f}" if _ir_val is not None else "—"
        _summary_rows.append(_row)

    if _summary_rows:
        lines.append("### 📋 Récapitulatif tous horizons")
        lines.append("")
        lines.append(_df_to_md(pd.DataFrame(_summary_rows)))
        # ── Meilleur horizon (calculé à l'entraînement) ──
        _best_h = _gr.get("best_horizon")
        _best_scores = _gr.get("best_horizon_scores", {})
        if _best_h is not None:
            lines.append("")
            _score_detail = ""
            if _best_scores:
                _parts = [f"H{h}={_best_scores.get(str(h), '?'):.4f}" for h in sorted(int(k) for k in _best_scores.keys())]
                _score_detail = "  |  " + "  ".join(_parts)
            lines.append(
                f"🏆 **Meilleur horizon : H{_best_h}** — sélectionné par score composite "
                f"55% IC + 30% IR + 15% Positive Split"
                f"{_score_detail}"
            )
        elif _has_champion and _champion_by_h:
            # Fallback : si best_horizon absent mais champions présents
            _best_h_fallback = max(_champion_by_h.items(), key=lambda x: (
                float((_ic_by_h.get(str(x[0]), 0)) or 0)
            ))[0] if _champion_by_h else None
            if _best_h_fallback is not None:
                lines.append("")
                lines.append(
                    f"ℹ️ **Meilleur horizon estimé : H{_best_h_fallback}** "
                    f"(IC max — best_horizon non disponible dans metadata)"
                )

    # ── Détail par horizon ──
    for _h_key in sorted(_hd.keys(), key=lambda x: int(x)):
        _h_info = _hd[_h_key]
        _ic_val = _ic_by_h.get(_h_key, 0) or 0
        _ds_val = _ds_by_h.get(_h_key, 0) or 0

        # Modèle champion pour cet horizon
        _h_champion = _champion_by_h.get(_h_key) if _has_champion else None
        _champion_title = f" — 🏆 {_h_champion}" if _h_champion else ""

        lines.append(f"### Horizon H{_h_key}{_champion_title}")
        lines.append("")
        if _h_champion:
            _champ_data = _h_info.get("candidates", {}).get(_h_champion, {})
            _champ_ic = _champ_data.get("ic_mean") if isinstance(_champ_data, dict) else None
            _champ_ir = _champ_data.get("ic_ir") if isinstance(_champ_data, dict) else None
            _champ_score = _h_info.get("champion_score")
            _sel_metric = _h_info.get("selection_metric", "—")
            _champ_parts = [f"🏆 **Champion : {_h_champion}**"]
            if _champ_ic is not None:
                _champ_parts.append(f"IC = {_champ_ic:.4f}")
            if _champ_ir is not None:
                _champ_parts.append(f"IR = {_champ_ir:.2f}")
            if _champ_score is not None:
                _champ_parts.append(f"Score composite = {_champ_score:.3f}")
            _champ_parts.append(f"Métrique : {_sel_metric}")
            lines.append(f"- {' | '.join(_champ_parts)}")
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
            _champ_label = f" — 🏆 {_h_champion}" if _h_champion else ""
            lines.append(f"#### 📅 Détail par split{_champ_label}")
            lines.append("")
            # Détecter si le mode champion est actif (colonnes ic_rank_*)
            _has_split_champion = any(
                k.startswith("ic_rank_") and k != "ic_rank"
                for _sp in _splits for k in (_sp or {}).keys()
            )
            # Nom de la colonne IC Rank : inclure le champion si connu
            _ic_col = f"IC Rank ({_h_champion})" if _h_champion else "IC Rank"
            _split_rows: list[dict] = []
            for _sp in _splits:
                _train_start = str(_sp.get("train_period_start", ""))[:10] if _sp.get("train_period_start") else "—"
                _train_end = str(_sp.get("train_period_end", ""))[:10] if _sp.get("train_period_end") else "—"
                _val_start = str(_sp.get("val_period_start", ""))[:10] if _sp.get("val_period_start") else "—"
                _val_end = str(_sp.get("val_period_end", ""))[:10] if _sp.get("val_period_end") else "—"
                _row = {
                    "Split": _sp.get("split_index", "—"),
                    "Train (début→fin)": f"{_train_start} → {_train_end}",
                    "Validation (début→fin)": f"{_val_start} → {_val_end}",
                    "Lignes Train": _sp.get("train_rows", "—"),
                    "Lignes Val": _sp.get("val_rows", "—"),
                    _ic_col: _sp.get("ic_rank"),
                }
                if _has_split_champion:
                    _row["IC LightGBM"] = _sp.get("ic_rank_lightgbm")
                    _row["IC CatBoost"] = _sp.get("ic_rank_catboost")
                _split_rows.append(_row)
            lines.append(_df_to_md(pd.DataFrame(_split_rows)))

        # ── Stats distribution IC par split ──
        _split_ics = [_sp.get("ic_rank") for _sp in _splits if _sp.get("ic_rank") is not None]
        if _split_ics:
            import numpy as np
            _arr = np.array(_split_ics, dtype=float)
            lines.append(f"- IC Moyen = {_arr.mean():.4f}  |  IC Std = {_arr.std():.4f}  |  IC Min = {_arr.min():.4f}  |  IC Max = {_arr.max():.4f}")
            lines.append("")


    lines.append("")


def _append_backtest_results(
    lines: list[str],
    batch_id: str | None,
    metadata_json: str | None = None,
) -> None:
    """Ajoute la section backtest stratégies Global Rank (V1/V2/V3/V4).

    Le meilleur horizon est détecté depuis les métadonnées du batch.
    Si meilleur horizon = H5, V2/V3 sont ignorés (filtre redondant).
    V4 = consensus multi-horizons (min_rising_horizons configurable).
    """
    if not batch_id:
        return
    # ── Détection du meilleur horizon ──
    _best_h = 20  # fallback par défaut
    if metadata_json:
        try:
            import json as _json
            _meta = _json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
            _gr = _meta.get("global_ranking", {}) if isinstance(_meta, dict) else {}
            _best_h = int(_gr.get("best_horizon", 20) or 20)
        except Exception:
            pass
    # ── Paramètre V4 depuis la config ──
    _min_rising = 4
    try:
        from common.config_loader import load_config as _load_cfg
        _cfg = _load_cfg()
        _min_rising = int(_cfg.get("backtest", {}).get("min_rising_horizons", 4))
    except Exception:
        pass
    # ── Scores composites par horizon (pour V4) ──
    _horizon_scores: dict[int, float] = {}
    if metadata_json:
        try:
            import json as _json2
            _meta2 = _json2.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
            _gr2 = _meta2.get("global_ranking", {}) if isinstance(_meta2, dict) else {}
            _raw = _gr2.get("best_horizon_scores", {})
            if _raw:
                _horizon_scores = {int(k): float(v) for k, v in _raw.items()}
        except Exception:
            pass
    _cache = Path("artifacts") / "models" / batch_id / "global_rank_cache.parquet"
    if not _cache.exists():
        return
    try:
        import numpy as np
        _ALL_H = (3, 5, 10, 15, 20)
        _df = pd.read_parquet(_cache)
        _df["date"] = pd.to_datetime(_df["date"])
        _rank_col = f"global_rank_{_best_h}"
        if _rank_col not in _df.columns:
            _rank_col = "global_rank_20"  # fallback
            _best_h = 20
        # ── Pré-calcul des rangs précédents pour tous les horizons ──
        for _h in _ALL_H:
            _col = f"global_rank_{_h}"
            if _col in _df.columns:
                _df[f"{_col}_prev"] = _df.groupby("symbol")[_col].shift(1)
        _all_dates = sorted(_df["date"].unique())
        _rebal = _all_dates[::20]
        _results: dict[str, Any] = {}
        # ── Construction des variantes avec le meilleur horizon ──
        _variantes: list[tuple[str, Any]] = [
            (f"V1 — H{_best_h} seul", lambda d: d[_rank_col] > 0.70),
        ]
        if _best_h != 5:
            _variantes.extend([
                (f"V2 — H{_best_h} + H5 rising", lambda d: (d[_rank_col] > 0.70) & (d["global_rank_5"] > d["global_rank_5_prev"])),
                (f"V3 — H{_best_h} + H5 < 0.35", lambda d: (d[_rank_col] > 0.70) & (d["global_rank_5"] < 0.35)),
            ])
        # ── V4 : top N horizons par score composite ──
        if _horizon_scores and len(_horizon_scores) >= 2:
            _sorted_h = sorted(_horizon_scores.keys(), key=lambda h: _horizon_scores[h], reverse=True)
            _n_top = min(_min_rising, len(_sorted_h))
            _top_h = _sorted_h[:_n_top]
            _v4_h = [h for h in _top_h if f"global_rank_{h}" in _df.columns and f"global_rank_{h}_prev" in _df.columns]
            if len(_v4_h) >= 1:
                _v4_label = f"V4 — H{_best_h} + top {len(_v4_h)} horizons ↑ (" + ",".join(f"H{h}" for h in _v4_h) + ")"
                def _make_v4(h_list):
                    def _f(d):
                        _ok = pd.Series(True, index=d.index)
                        for _h in h_list:
                            _c = f"global_rank_{_h}"
                            _cp = f"{_c}_prev"
                            if _c in d.columns and _cp in d.columns:
                                _ok = _ok & (d[_c] > d[_cp])
                        return (d[_rank_col] > 0.70) & _ok
                    return _f
                _variantes.append((_v4_label, _make_v4(_v4_h)))
        for _label, _fn in _variantes:
            _pos = {}
            _rets = {}
            _turn = 0
            for _d in _all_dates:
                _day = _df[_df["date"] == _d].set_index("symbol")
                _sig = _fn(_day)
                if _d in _rebal or not _pos:
                    _cand = _day.loc[_sig].sort_values(_rank_col, ascending=False)
                    if _pos:
                        _turn += len(_pos)
                    _pos = {s: float(_cand.loc[s, _rank_col]) for s in _cand.index[:30]}
                    _turn += len(_pos)
                _held = [s for s in _pos if s in _day.index]
                _rets[_d] = float(_day.loc[_held, _rank_col].mean()) - 0.5 if _held else 0.0
            _s = pd.Series(_rets).sort_index()
            _cost = (25.0 / 10000.0) * _turn / len(_all_dates)
            _s = _s - _cost / 20
            _exc = _s - 0.02 / 252
            _m, _std = float(_exc.mean()), float(_exc.std())
            _sharpe = float(_m / _std * np.sqrt(252)) if _std > 0 else 0.0
            _cum = (1 + _s).cumprod()
            _dd = float((_cum / _cum.cummax() - 1).min())
            _results[_label] = {"sharpe": _sharpe, "ann_return": _m * 252, "ann_vol": _std * np.sqrt(252), "max_dd": _dd}

        if _results:
            _title_suffix = f" (H{_best_h} + H5)" if _best_h != 5 else f" (H{_best_h} seul)"
            lines.append(f"## 🧪 Backtest Stratégies — Global Rank{_title_suffix}")
            lines.append("")
            _best = max(_results, key=lambda v: _results[v]["sharpe"])
            lines.append("| Variante | Score relatif |")
            lines.append("|----------|---------------|")
            for _l, _m in _results.items():
                _pct = f"{(_m['sharpe'] / _results[_best]['sharpe'] - 1) * 100:+.1f}%" if _l != _best else "🏆 référence"
                lines.append(f"| {_l} | {_pct} |")
            lines.append("")
            _legend = (
                f"> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. "
                f"Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). "
                f"Frais 0.25% A/R inclus. "
                f"V1 = H{_best_h} seul"
            )
            if _best_h != 5:
                _legend += f", V2 = H{_best_h} + H5 rising, V3 = H{_best_h} + H5 < 0.35 (contrarian)."
            else:
                _legend += " (V2/V3 non calculés — H5 est déjà le meilleur horizon)."
            if len(_v4_h) >= 1:
                _legend += f" V4 = H{_best_h} + top {len(_v4_h)} horizons ↑ ({','.join(f'H{h}' for h in _v4_h)})."
            lines.append(_legend)
            lines.append("")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 🔥 Oracle Extreme — Qualité du modèle (OOS)
# Miroir de la section « Oracle Extreme » de la page IHM Diagnostic ML
# (ihm/pages/ml_diagnostics.py). Helpers dupliqués (purs, sans streamlit) pour
# éviter une dépendance circulaire, comme les requêtes en tête de fichier.
# ---------------------------------------------------------------------------


def _oracle_split_table(picks: pd.DataFrame) -> dict | None:
    """Table D1-D10 pour une sélection de picks (colonnes ``_dec`` + ``future_return``).

    D1 = bottom 10% (MAUVAIS long), D10 = top 10% (BON long).
    """
    if picks is None or picks.empty:
        return None
    vc = picks["_dec"].value_counts().reindex(range(1, 11), fill_value=0)
    n = len(picks)
    g = picks.groupby("_dec")["future_return"].mean()
    table = pd.DataFrame({
        "Décile réalisé": [f"D{d}" for d in range(1, 11)],
        "% des picks": [100.0 * int(vc[d]) / n for d in range(1, 11)],
        "Retour moyen si LONG": [f"{float(g[d])*100:+.2f}%" if d in g.index else "—" for d in range(1, 11)],
    })
    return {
        "table": table,
        "d1_pct": 100.0 * int(vc[1]) / n,
        "d10_pct": 100.0 * int(vc[10]) / n,
        "d1_ret": float(g[1]) if 1 in g.index else 0.0,
        "d10_ret": float(g[10]) if 10 in g.index else 0.0,
        "mean_ret": float(picks["future_return"].mean()) if "future_return" in picks.columns else 0.0,
        "n": n,
    }


def _oracle_direction_split(df: pd.DataFrame) -> dict | None:
    """Répartition des picks top 10% proba par décile de rendement réalisé.

    D1 = bottom 10% (MAUVAIS long), D10 = top 10% (BON long). Le déséquilibre
    D1/D10 mesure l'ampleur de la pénalité directionnelle (anti-D1) potentielle
    pour un usage LONG du gate Extreme (proba_extreme est agnostique à la direction).
    """
    if "future_return" not in df.columns:
        return None
    sub = df.dropna(subset=["date", "symbol", "proba_extreme", "future_return"]).copy()
    if sub.empty:
        return None
    sub["_dec"] = (
        np.floor(sub.groupby("date")["future_return"].rank(pct=True).clip(upper=1 - 1e-9) * 10)
        .clip(0, 9).astype(int) + 1
    )
    top_parts: list[pd.DataFrame] = []
    for _, g in sub.groupby("date"):
        k = max(1, int(round(len(g) * 0.10)))
        top_parts.append(g.nlargest(k, "proba_extreme"))
    if not top_parts:
        return None
    return _oracle_split_table(pd.concat(top_parts, ignore_index=True))


def _oracle_omniscient_split(df: pd.DataFrame, top_pct: float = 0.10) -> dict | None:
    """Répartition D1-D10 si on retirait PARFAITEMENT les mauvais tops (D1).

    Sélection = top ``top_pct`` par ``proba_extreme`` par jour, PUIS on retire
    les picks qui réaliseront D1 (rendement futur connu → LOOKAHEAD). C'est une
    borne **THÉORIQUE** (non exécutable en live) : le maximum atteignable par
    toute pénalité ou tout entraînement anti-D1. 100% basé sur le réel oracle
    (``future_return``), aucun signal per-symbol.
    """
    if "future_return" not in df.columns:
        return None
    sub = df.dropna(subset=["date", "symbol", "proba_extreme", "future_return"]).copy()
    if sub.empty:
        return None
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
    sub = sub.dropna(subset=["date"])
    sub["_dec"] = (
        np.floor(sub.groupby("date")["future_return"].rank(pct=True).clip(upper=1 - 1e-9) * 10)
        .clip(0, 9).astype(int) + 1
    )
    out_parts: list[pd.DataFrame] = []
    for _, g in sub.groupby("date"):
        k = max(1, int(round(len(g) * top_pct)))
        topk = g.nlargest(k, "proba_extreme")
        kept = topk[topk["_dec"] != 1]  # omniscient : on écarte les D1
        if kept.empty:
            continue
        out_parts.append(kept)
    if not out_parts:
        return None
    return _oracle_split_table(pd.concat(out_parts, ignore_index=True))


def _append_oracle_extreme_quality(
    lines: list[str], engine: Engine, batch_id: str
) -> None:
    """Ajoute la section 🔥 Oracle Extreme — Qualité du modèle (OOS).

    Miroir de la section « Oracle Extreme — Qualité du modèle (OOS) » de la page
    IHM Diagnostic ML (``ihm/pages/ml_diagnostics.py``). Source unique : la table
    ``oracle_extreme_predictions``. Ne rend rien si le batch n'a pas entraîné la
    couche Oracle Extreme (O0) ou si aucune prédiction OOS n'existe.
    """
    # ── Le batch a-t-il entraîné la couche Oracle Extreme (O0) ? ──
    _detail = _safe_query(engine, BATCH_DETAIL_QUERY, {"batch_id": batch_id})
    if _detail.empty:
        return
    _meta_raw = _detail.iloc[0].get("metadata_json")
    try:
        _meta = json.loads(str(_meta_raw)) if _meta_raw and str(_meta_raw) not in ("None", "nan", "") else {}
    except Exception:
        _meta = {}
    if not isinstance(_meta, dict):
        return
    if not (_meta.get("oracle") or _meta.get("oracle_extreme")):
        _co = _meta.get("cli_options") or {}
        if not (isinstance(_co, dict) and bool(_co.get("enable_oracle_model"))):
            return

    # ── Prédictions OOS depuis la table oracle_extreme_predictions ──
    try:
        from modelFactory.oracle.predictions_store import load_oracle_predictions
        oos = load_oracle_predictions(engine, batch_id=batch_id)
    except Exception:
        oos = pd.DataFrame()
    if oos is None or oos.empty:
        return

    need = {"date", "symbol", "proba_extreme"}
    if not need.issubset(oos.columns):
        return

    df = oos.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["proba_extreme"] = pd.to_numeric(df["proba_extreme"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "proba_extreme"])
    if df.empty:
        return

    from modelFactory.oracle.train import (
        decile_monotonicity,
        precision_recall_at_top_pct,
        roc_auc,
    )

    # ── Couverture ──
    n_dates = int(df["date"].dt.normalize().nunique())
    n_symbols = int(df["symbol"].nunique())
    n_rows = len(df)
    dmin, dmax = df["date"].min(), df["date"].max()

    # ── Cible binaire (extrême réalisé) si présente ──
    target_col = next((c for c in ("oracle_extreme10", "target", "y") if c in df.columns), None)
    has_target = target_col is not None and df[target_col].notna().any()

    auc: float | None = None
    pr: dict[str, float | None] = {"precision": None, "recall": None, "n_dates": 0}
    prevalence: float | None = None
    if has_target:
        y = df[target_col].astype(float)
        auc = roc_auc(y.to_numpy(), df["proba_extreme"].to_numpy())
        pr = precision_recall_at_top_pct(df, "proba_extreme", pct=0.10, target_col=target_col)
        yv = y.dropna()
        prevalence = float(yv.mean()) if len(yv) else None
    lift = (pr["precision"] / prevalence) if (pr["precision"] is not None and prevalence) else None

    # ── IC (Spearman) proba_extreme vs future_return, moyen par jour ──
    ic: float | None = None
    if "future_return" in df.columns:
        ics: list[float] = []
        for _, g in df.groupby(df["date"].dt.normalize()):
            g = g.dropna(subset=["proba_extreme", "future_return"])
            if len(g) < 10:
                continue
            try:
                c = g["proba_extreme"].corr(g["future_return"], method="spearman")
                if pd.notna(c):
                    ics.append(float(c))
            except Exception:
                continue
        if ics:
            ic = float(np.mean(ics))

    # ── Calibration : déciles globaux de proba_extreme → taux réalisé ──
    cal = pd.DataFrame()
    if has_target:
        sub = df.dropna(subset=["proba_extreme", target_col]).copy()
        if not sub.empty and sub[target_col].nunique() > 1:
            sub["_q"] = pd.qcut(sub["proba_extreme"].rank(method="first"), 10, labels=False) + 1
            g = sub.groupby("_q").agg(
                mean_proba=("proba_extreme", "mean"),
                actual_rate=(target_col, "mean"),
                n=("proba_extreme", "size"),
            )
            # NB : reset_index() après `g.index = [...]` nommerait la colonne
            # 'index' (le nom '_q' est perdu) → on construit cal directement.
            cal = pd.DataFrame({
                "Décile": [f"D{i}" for i in g.index],
                "P(extrême) prédite": g["mean_proba"].to_numpy(dtype=float),
                "Taux réalisé": g["actual_rate"].to_numpy(dtype=float),
                "N": g["n"].to_numpy(dtype=int),
            })

    # ── Rendement du top décile vs overall (future_return) ──
    top_ret: float | None = None
    overall_ret: float | None = None
    if "future_return" in df.columns:
        fr = df.dropna(subset=["proba_extreme", "future_return"])
        overall_ret = float(fr["future_return"].mean()) if not fr.empty else None
        top_parts: list[pd.DataFrame] = []
        for _, g in fr.groupby(df["date"].dt.normalize()):
            k = max(1, int(round(len(g) * 0.10)))
            top_parts.append(g.nlargest(k, "proba_extreme"))
        if top_parts:
            top_ret = float(pd.concat(top_parts, ignore_index=True)["future_return"].mean())

    # ── Monotonicité décile (Spearman future_return) ──
    mono, _mono_df = decile_monotonicity(df, "proba_extreme")

    # ── Rendu markdown ──
    lines.append("---")
    lines.append("")
    lines.append("## 🔥 Oracle Extreme — Qualité du modèle (OOS)")
    lines.append("")
    lines.append(
        f"_Run : `{batch_id}` · OOS {dmin.date()} → {dmax.date()} · "
        f"{n_dates} jours · {n_symbols} symboles · {n_rows:,} lignes_".replace(",", " ")
    )
    lines.append("")
    lines.append("| Métrique | Valeur |")
    lines.append("|:---|:---|")
    lines.append(f"| 🎯 AUC (cible extrême) | `{auc:.3f}` |" if auc is not None else "| 🎯 AUC (cible extrême) | — |")
    lines.append(f"| 📈 IC (proba vs rendement) | `{ic:+.3f}` |" if ic is not None else "| 📈 IC (proba vs rendement) | — |")
    _prev_s = f"{prevalence*100:.1f}%" if prevalence is not None else "—"
    _prec_s = f"{pr['precision']*100:.1f}%" if pr.get("precision") is not None else "—"
    lines.append(f"| Precision@10% (prévalence) | {_prec_s} ({_prev_s}) |")
    lines.append(f"| 🚀 Lift top 10% | `{lift:.2f}x` |" if lift is not None else "| 🚀 Lift top 10% | — |")
    lines.append(f"| 📈 Retour top 10% (OOS) | `{top_ret*100:+.2f}%` |" if top_ret is not None else "| 📈 Retour top 10% (OOS) | — |")
    lines.append(f"| 📉 Retour moyen (OOS) | `{overall_ret*100:+.2f}%` |" if overall_ret is not None else "| 📉 Retour moyen (OOS) | — |")
    lines.append("")

    if not cal.empty:
        lines.append("**Calibration — déciles de `proba_extreme` → taux d'extrême réalisé**")
        lines.append("")
        lines.append("| Décile | P(extrême) prédite | Taux réalisé | N |")
        lines.append("|:---|:---|:---|:---|")
        for _, _r in cal.iterrows():
            lines.append(
                f"| {_r['Décile']} | {float(_r['P(extrême) prédite']):.3f} | "
                f"{float(_r['Taux réalisé']):.1%} | {int(_r['N']):,} |".replace(",", " ")
            )
        lines.append("")

    if mono is not None:
        lines.append(f"**Monotonicité décile (rendement futur)** : Spearman = `{mono:+.3f}`")
        lines.append("")

    _dir_split = _oracle_direction_split(df)
    if _dir_split is not None:
        lines.append("**🧭 Répartition directionnelle des picks top 10% de `proba_extreme`**")
        lines.append("")
        lines.append(_df_to_md(_dir_split["table"]))
        lines.append("")
        lines.append(
            f"_Top 10% du modèle : **{_dir_split['d1_pct']:.1f}%** en **D1** "
            f"(bottom 10% réalisé, MAUVAIS long, retour moyen **{_dir_split['d1_ret']*100:+.1f}%**) vs "
            f"**{_dir_split['d10_pct']:.1f}%** en **D10** (bon long, **{_dir_split['d10_ret']*100:+.1f}%**). "
            f"`proba_extreme` est agnostique à la direction → le déséquilibre D1/D10 quantifie la "
            f"pénalité directionnelle (anti-D1) à appliquer pour un gate LONG._"
        )
        lines.append("")

    # ── Plafond omniscient (anti-D1) : brut vs idéal (filtre D1 parfait) ──
    _ceil = _oracle_omniscient_split(df)
    if _ceil is not None and _dir_split is not None:
        lines.append("**🎯 Plafond omniscient — filtre D1 parfait (brut vs idéal)**")
        lines.append("")
        lines.append("| Métrique | Brut (top 10% proba_extreme) | Plafond (sans D1) |")
        lines.append("|:---|:---|:---|")
        lines.append(f"| % en D1 (mauvais long) | {_dir_split['d1_pct']:.1f}% | {_ceil['d1_pct']:.1f}% |")
        lines.append(f"| % en D10 (bon long) | {_dir_split['d10_pct']:.1f}% | {_ceil['d10_pct']:.1f}% |")
        lines.append(f"| Retour moyen des picks | {_dir_split.get('mean_ret', 0)*100:+.2f}% | {_ceil.get('mean_ret', 0)*100:+.2f}% |")
        lines.append(f"| N picks | {int(_dir_split.get('n', 0)):,} | {int(_ceil.get('n', 0)):,} |".replace(",", " "))
        lines.append("")
        _gain = (_ceil.get("mean_ret", 0) - _dir_split.get("mean_ret", 0)) * 100
        lines.append(
            f"_Plafond omniscient = top 10% par `proba_extreme` en retirant les picks qui "
            f"RÉALISERONT D1 (rendement futur connu) → borne **THÉORIQUE** (lookahead, "
            f"non exécutable en live). 100% basé sur le réel oracle (`future_return`), "
            f"aucun signal per-symbol. Gain de retour moyen = **{_gain:+.2f} pt** : c'est "
            f"le maximum atteignable par tout entraînement/filtre anti-D1._"
        )
        lines.append("")

    if not has_target:
        lines.append("_ℹ️ Colonne cible (`oracle_extreme10`) absente — AUC/precision/calibration non calculées._")
        lines.append("")


# ---------------------------------------------------------------------------
# 🔀 Répartition Oracle — TOP / BOTTOM 10% du modèle dans le vrai Oracle
# Miroir de la page IHM Diagnostic ML (``_render_oracle_distribution``).
# ---------------------------------------------------------------------------

ORACLE_LABELS_DECILE_QUERY = """
    SELECT
        prediction_date,
        symbol,
        oracle_decile
    FROM alpha_trade.global_oracle_labels
    WHERE batch_id = :batch_id
      AND horizon = :horizon
      AND oracle_decile IS NOT NULL
    ORDER BY prediction_date, symbol
"""


def _global_rank_all_query_report(horizon: int) -> str:
    """Rangs globaux du batch (colonne du meilleur horizon), miroir page IHM."""
    _h = int(horizon)
    return (
        "SELECT `date`, symbol, global_rank_%d AS global_rank_best "
        "FROM alpha_trade.global_rank_history "
        "WHERE batch_id = :batch_id AND global_rank_%d IS NOT NULL "
        "ORDER BY `date`, symbol" % (_h, _h)
    )


def _report_best_horizon(detail_df: pd.DataFrame) -> int:
    """Meilleur horizon du Global Ranking pour ce batch (metadata, défaut H20)."""
    if detail_df.empty:
        return 20
    raw = detail_df.iloc[0].get("metadata_json")
    if raw is None or str(raw) in ("None", "nan", ""):
        return 20
    try:
        data = json.loads(str(raw))
        gr = data.get("global_ranking") if isinstance(data, dict) else None
        h = gr.get("best_horizon") if isinstance(gr, dict) else None
        h = int(h) if h else 20
        return h if h in (3, 5, 10, 15, 20) else 20
    except Exception:
        return 20


def _oracle_distribution_md(sel: pd.DataFrame, title: str) -> list[str]:
    """Tableau markdown D1..D10 + Total pour une sélection (colonne ``oracle_decile``)."""
    out: list[str] = []
    if sel.empty:
        out.append(f"**{title}** — aucune ligne sélectionnée.")
        return out
    counts = sel["oracle_decile"].value_counts().reindex(range(1, 11), fill_value=0)
    total = int(len(sel))
    out.append(f"**{title}** — {total:,} lignes".replace(",", " "))
    out.append("")
    out.append("| Décile Oracle | Nb titres | % |")
    out.append("|:---|:---|:---|")
    for d in range(1, 11):
        _n = int(counts[d])
        out.append(f"| D{d} | {_n:,} | {100.0 * _n / total:.1f}% |".replace(",", " "))
    out.append(f"| **Total** | **{total:,}** | **100.0%** |".replace(",", " "))
    return out


def _append_one_oracle_distribution(
    lines: list[str],
    engine: Engine,
    batch_id: str,
    model_df: pd.DataFrame,
    *,
    horizon: int,
    label: str,
) -> None:
    """Croise TOP/BOTTOM 10% d'un modèle avec les déciles du vrai Oracle (H{horizon}).

    ``model_df`` doit avoir les colonnes ``date``, ``symbol``, ``score``.
    """
    labels_df = _safe_query(
        engine, ORACLE_LABELS_DECILE_QUERY,
        {"batch_id": batch_id, "horizon": int(horizon)},
    )
    if labels_df.empty:
        lines.append(
            f"_ℹ️ Vrai Oracle non calculé (H{horizon}) pour ce batch — répartition indisponible._"
        )
        lines.append("")
        return

    labels = labels_df.copy()
    labels["date"] = pd.to_datetime(labels["prediction_date"], errors="coerce")
    labels["symbol"] = labels["symbol"].astype(str).str.strip()
    labels["oracle_decile"] = pd.to_numeric(labels["oracle_decile"], errors="coerce")

    m = model_df.copy()
    m["date"] = pd.to_datetime(m["date"], errors="coerce")
    m["symbol"] = m["symbol"].astype(str).str.strip()
    m["score"] = pd.to_numeric(m["score"], errors="coerce")
    merged = m.merge(labels[["date", "symbol", "oracle_decile"]], on=["date", "symbol"], how="inner")
    merged = merged.dropna(subset=["oracle_decile", "score"])
    merged["oracle_decile"] = merged["oracle_decile"].astype(int)

    if merged.empty:
        lines.append(
            f"_ℹ️ Aucune intersection entre les prédictions {label} et les labels Oracle (H{horizon})._"
        )
        lines.append("")
        return

    def _split_top_bottom(df: pd.DataFrame, pct: float = 0.10) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Sélection symétrique : k = pct% des lignes par date, top et bottom."""
        top_parts: list[pd.DataFrame] = []
        bottom_parts: list[pd.DataFrame] = []
        for _, g in df.groupby("date", sort=False):
            k = max(1, int(round(len(g) * pct)))
            top_parts.append(g.nlargest(k, "score"))
            bottom_parts.append(g.nsmallest(k, "score"))
        if not top_parts:
            return pd.DataFrame(), pd.DataFrame()
        return pd.concat(top_parts, ignore_index=True), pd.concat(bottom_parts, ignore_index=True)

    top_sel, bottom_sel = _split_top_bottom(merged)

    lines.append(
        f"_Croisé avec le vrai Oracle (`global_oracle_labels`, H{horizon}) : "
        f"**D1** = pire 10% réalisé … **D10** = meilleur 10% réalisé._"
    )
    lines.append("")
    lines.extend(_oracle_distribution_md(top_sel, "🟢 TOP 10% du modèle → déciles Oracle"))
    lines.append("")
    lines.extend(_oracle_distribution_md(bottom_sel, "🔴 BOTTOM 10% du modèle → déciles Oracle"))
    lines.append("")


def _append_oracle_distribution(
    lines: list[str], engine: Engine, batch_id: str
) -> None:
    """Ajoute la section 🔀 Répartition Oracle — TOP / BOTTOM 10% du modèle.

    Miroir de la page IHM Diagnostic ML (``_render_oracle_distribution``) : pour
    chaque modèle disponible du batch (Global Ranking puis Oracle Extreme), on
    croise ses TOP/BOTTOM 10% avec les déciles du vrai Oracle
    (``global_oracle_labels``) et on rend la répartition D1..D10. Dans le rapport
    (statique), on affiche les deux modèles au lieu de boutons interactifs.
    """
    _detail = _safe_query(engine, BATCH_DETAIL_QUERY, {"batch_id": batch_id})
    if _detail.empty:
        return
    best_h = _report_best_horizon(_detail)

    # ── Modèles disponibles ──
    global_df = _safe_query(
        engine, _global_rank_all_query_report(best_h), {"batch_id": batch_id}
    )
    has_global = not global_df.empty

    _meta_raw = _detail.iloc[0].get("metadata_json")
    try:
        _meta = json.loads(str(_meta_raw)) if _meta_raw and str(_meta_raw) not in ("None", "nan", "") else {}
    except Exception:
        _meta = {}
    has_oracle = False
    if isinstance(_meta, dict) and (_meta.get("oracle") or _meta.get("oracle_extreme")):
        has_oracle = True
    elif isinstance(_meta, dict):
        _co = _meta.get("cli_options") or {}
        has_oracle = isinstance(_co, dict) and bool(_co.get("enable_oracle_model"))
    oracle_oos = pd.DataFrame()
    if has_oracle:
        try:
            from modelFactory.oracle.predictions_store import load_oracle_predictions
            oracle_oos = load_oracle_predictions(engine, batch_id=batch_id)
        except Exception:
            oracle_oos = pd.DataFrame()
        has_oracle = oracle_oos is not None and not oracle_oos.empty

    if not has_global and not has_oracle:
        return

    lines.append("---")
    lines.append("")
    lines.append("## 🔀 Répartition Oracle — TOP / BOTTOM 10% du modèle")
    lines.append("")
    lines.append(f"_Horizons du vrai Oracle — 🌐 Modèle global : H{best_h} · 🔥 Oracle Extreme : H20_")
    lines.append("")

    # ── Modèle global ──
    if has_global:
        lines.append("### 🌐 Modèle global")
        lines.append("")
        _g = global_df[["date", "symbol", "global_rank_best"]].copy()
        _g["score"] = _g["global_rank_best"]
        _append_one_oracle_distribution(
            lines, engine, batch_id, _g, horizon=best_h, label="Modèle global"
        )
        lines.append("")

    # ── Modèle Oracle Extreme ──
    if has_oracle:
        lines.append("### 🔥 Modèle Oracle Extreme")
        lines.append("")
        date_col = next(
            (c for c in ("prediction_date", "date", "entry_date", "asof_date") if c in oracle_oos.columns),
            None,
        )
        if date_col is not None and "symbol" in oracle_oos.columns and "proba_extreme" in oracle_oos.columns:
            _o = oracle_oos[[date_col, "symbol", "proba_extreme"]].copy()
            _o["date"] = pd.to_datetime(_o[date_col], errors="coerce")
            _o["score"] = pd.to_numeric(_o["proba_extreme"], errors="coerce")
            _o = _o.dropna(subset=["date", "symbol", "score"])
            _append_one_oracle_distribution(
                lines, engine, batch_id, _o, horizon=20, label="Modèle Oracle Extreme"
            )
        lines.append("")


# ---------------------------------------------------------------------------
# 📅 Périodes de prédictions du batch
# Miroir de la page IHM Diagnostic ML (``_render_prediction_periods``).
# ---------------------------------------------------------------------------

GLOBAL_RANK_COVERAGE_QUERY = """
    SELECT MIN(date) AS min_date, MAX(date) AS max_date,
           COUNT(DISTINCT date) AS nb_dates, COUNT(DISTINCT symbol) AS nb_symbols
    FROM alpha_trade.global_rank_history
    WHERE batch_id = :batch_id
"""

PRED_RUNS_FOR_BATCH_QUERY = """
    SELECT
        mp.run_id AS run_id,
        r.symbol AS run_symbol,
        COUNT(mp.prediction_date) AS n_rows,
        COUNT(DISTINCT mp.symbol) AS nb_symbols,
        MIN(mp.prediction_date) AS min_date,
        MAX(mp.prediction_date) AS max_date,
        COUNT(DISTINCT mp.prediction_date) AS nb_dates
    FROM alpha_trade.model_predictions AS mp
    JOIN alpha_trade.model_training_run AS r
        ON r.run_id = mp.run_id
    WHERE r.batch_id = :batch_id
      AND r.status = 'completed'
    GROUP BY mp.run_id, r.symbol
    ORDER BY mp.run_id
"""

ORACLE_TABLE_PERIODS_QUERY = """
    SELECT MIN(prediction_date) AS min_date,
           MAX(prediction_date) AS max_date,
           COUNT(DISTINCT prediction_date) AS nb_dates,
           COUNT(DISTINCT symbol) AS nb_symbols
    FROM alpha_trade.oracle_extreme_predictions
    WHERE batch_id = :batch_id
"""

_GICS_SECTORS = {
    "Communication Services", "Consumer Discretionary", "Consumer Staples",
    "Energy", "Financials", "Health Care", "Industrials",
    "Information Technology", "Materials", "Real Estate", "Utilities",
}


def _report_trains_oracle(detail_df: pd.DataFrame) -> bool:
    """Détecte si le batch a entraîné la couche Oracle Extreme (O0)."""
    if detail_df.empty:
        return False
    raw = detail_df.iloc[0].get("metadata_json")
    try:
        _meta = json.loads(str(raw)) if raw and str(raw) not in ("None", "nan", "") else {}
    except Exception:
        _meta = {}
    if not isinstance(_meta, dict):
        return False
    if _meta.get("oracle") or _meta.get("oracle_extreme"):
        return True
    _co = _meta.get("cli_options") or {}
    return isinstance(_co, dict) and bool(_co.get("enable_oracle_model"))


def _oracle_periods_report(engine: Engine, batch_id: str) -> list[dict]:
    """Périodes des prédictions Oracle Extreme du batch — TABLE uniquement."""
    out: list[dict] = []
    try:
        _tbl = _safe_query(engine, ORACLE_TABLE_PERIODS_QUERY, {"batch_id": batch_id})
        if not _tbl.empty:
            _r = _tbl.iloc[0]
            _mn = pd.Timestamp(_r["min_date"])
            _mx = pd.Timestamp(_r["max_date"])
            out.append({"Type": "🔥 Oracle extreme",
                        "Période": f"{_mn.date()} → {_mx.date()}",
                        "Jours": int(_r["nb_dates"] or 0),
                        "Symboles": int(_r["nb_symbols"] or 0),
                        "Détail": "table oracle_extreme_predictions"})
    except Exception:
        pass
    return out


def _append_prediction_periods(
    lines: list[str], engine: Engine, batch_id: str
) -> None:
    """Ajoute la section 📅 Périodes de prédictions du batch.

    Miroir de la page IHM Diagnostic ML (``_render_prediction_periods``) : résume
    les périodes où le batch a des prédictions par type de modèle
    (global / per-symbol / per-sector / oracle extreme), avec détail par
    secteur et par run Oracle si disponible.
    """

    def _fmt(d) -> str:
        if d is None:
            return "—"
        try:
            return str(pd.Timestamp(d).date())
        except Exception:
            return str(d)

    summary: list[dict] = []
    sector_rows: list[dict] = []
    oracle_rows: list[dict] = []

    # ── 1. Modèle global (Global Ranking) ──
    gr = _safe_query(engine, GLOBAL_RANK_COVERAGE_QUERY, {"batch_id": batch_id})
    if not gr.empty and gr.iloc[0].get("min_date") is not None:
        g = gr.iloc[0]
        summary.append({
            "Type": "🌐 Modèle global (Global Ranking)",
            "Période": f"{_fmt(g['min_date'])} → {_fmt(g['max_date'])}",
            "Jours": int(g["nb_dates"] or 0),
            "Symboles": int(g["nb_symbols"] or 0),
            "Détail": "global_rank_history (rangs H3→H20)",
        })

    # ── 2. model_predictions par run (synth / per-symbol / per-sector) ──
    runs = _safe_query(engine, PRED_RUNS_FOR_BATCH_QUERY, {"batch_id": batch_id})
    synth = None
    sym_min = None
    sym_max = None
    sym_days = 0
    sym_syms = 0
    sym_n = 0
    if not runs.empty:
        for _, r in runs.iterrows():
            rsym = str(r["run_symbol"] or "").strip()
            rid = str(r["run_id"] or "")
            dmin = pd.Timestamp(r["min_date"]) if r["min_date"] is not None else None
            dmax = pd.Timestamp(r["max_date"]) if r["max_date"] is not None else None
            jours = int(r["nb_dates"] or 0)
            syms = int(r["nb_symbols"] or 0)
            if rsym == "__GLOBAL_RANK_SYNTH__" or rid.endswith("_globalrank_synth"):
                synth = {"Période": f"{_fmt(dmin)} → {_fmt(dmax)}", "Jours": jours, "Symboles": syms}
            elif rsym in _GICS_SECTORS:
                sector_rows.append({"Secteur": rsym, "Période": f"{_fmt(dmin)} → {_fmt(dmax)}",
                                    "Jours": jours, "Symboles": syms})
            elif rsym == "__ORACLE_SYNTH__" or rid.endswith("_oracle_synth"):
                # Run miroir Oracle → model_predictions (oracle_synth) : déjà couvert
                # par la section « Oracle extreme » — NE PAS compter comme per-symbol.
                pass
            else:
                sym_n += 1
                if dmin is not None and (sym_min is None or dmin < sym_min):
                    sym_min = dmin
                if dmax is not None and (sym_max is None or dmax > sym_max):
                    sym_max = dmax
                sym_days = max(sym_days, jours)
                sym_syms += syms

    if synth is not None:
        _g = next((s for s in summary if s["Type"].startswith("🌐")), None)
        if _g is not None:
            _g["Détail"] = _g["Détail"] + f" + cascade synth ({synth['Jours']}j)"
        else:
            summary.append({"Type": "🌐 Modèle global (cascade)", "Période": synth["Période"],
                            "Jours": synth["Jours"], "Symboles": synth["Symboles"],
                            "Détail": f"run {batch_id}_globalrank_synth"})

    if sym_n > 0:
        summary.append({"Type": "📈 Per-symbol",
                        "Période": f"{_fmt(sym_min)} → {_fmt(sym_max)}",
                        "Jours": sym_days, "Symboles": sym_syms,
                        "Détail": f"{sym_n} modèles par ticker"})
    else:
        summary.append({"Type": "📈 Per-symbol", "Période": "—", "Jours": "", "Symboles": "",
                        "Détail": "non entraîné dans ce batch"})

    if sector_rows:
        s_min = min(pd.Timestamp(r["Période"].split(" → ")[0]) for r in sector_rows)
        s_max = max(pd.Timestamp(r["Période"].split(" → ")[1]) for r in sector_rows)
        summary.append({"Type": "🗂️ Per-sector",
                        "Période": f"{s_min.date()} → {s_max.date()}",
                        "Jours": max(r["Jours"] for r in sector_rows),
                        "Symboles": sum(r["Symboles"] for r in sector_rows),
                        "Détail": f"{len(sector_rows)} secteurs (voir détail)"})
    else:
        summary.append({"Type": "🗂️ Per-sector", "Période": "—", "Jours": "", "Symboles": "",
                        "Détail": "non entraîné dans ce batch"})

    # ── 3. Oracle extreme ──
    _detail = _safe_query(engine, BATCH_DETAIL_QUERY, {"batch_id": batch_id})
    oracle_trained = _report_trains_oracle(_detail)
    if oracle_trained:
        oracle_rows = _oracle_periods_report(engine, batch_id)
    if oracle_rows:
        _valid = [o for o in oracle_rows if "→" in o["Période"] and not o["Période"].startswith(("—", "?"))]
        if _valid:
            _latest = _valid[-1]
            _last_run = str(_latest.get("Détail", "")).split("/")[-1]
            summary.append({"Type": "🔥 Oracle extreme",
                            "Période": _latest["Période"],
                            "Jours": _latest.get("Jours", ""),
                            "Symboles": _latest.get("Symboles", ""),
                            "Détail": f"{len(oracle_rows)} run(s) — dernier : {_last_run}"})
        else:
            summary.append({"Type": "🔥 Oracle extreme", "Période": "—", "Jours": "", "Symboles": "",
                            "Détail": "artefacts sans période exploitable"})
    else:
        summary.append({"Type": "🔥 Oracle extreme", "Période": "—", "Jours": "", "Symboles": "",
                        "Détail": "non entraîné dans ce batch" if not oracle_trained else "aucun artefact"})

    # ── Rendu markdown ──
    lines.append("---")
    lines.append("")
    lines.append("## 📅 Périodes de prédictions du batch")
    lines.append("")
    lines.append("| Type | Période | Jours | Symboles | Détail |")
    lines.append("|:---|:---|:---|:---|:---|")
    for row in summary:
        lines.append(
            f"| {row['Type']} | {row['Période']} | {row['Jours']} | {row['Symboles']} | {row['Détail']} |"
        )
    lines.append("")
    if sector_rows:
        lines.append("### 🗂️ Détail par secteur")
        lines.append("")
        lines.append("| Secteur | Période | Jours | Symboles |")
        lines.append("|:---|:---|:---|:---|")
        for r in sector_rows:
            lines.append(f"| {r['Secteur']} | {r['Période']} | {r['Jours']} | {r['Symboles']} |")
        lines.append("")
    if oracle_rows:
        lines.append("### 🔥 Détail Oracle extreme (runs)")
        lines.append("")
        lines.append("| Type | Période | Jours | Symboles | Détail |")
        lines.append("|:---|:---|:---|:---|:---|")
        for r in oracle_rows:
            lines.append(f"| {r['Type']} | {r['Période']} | {r['Jours']} | {r['Symboles']} | {r['Détail']} |")
        lines.append("")


def _build_regime_table(engine: Engine, batch_id: str) -> pd.DataFrame:
    """Construit le tableau diagnostic par régime de marché pour un batch.

    Fonctionne pour tous les target_mode (ternaire, regression, binaire).
    """
    all_json_df = _safe_query(engine, ALL_WF_JSON_QUERY, {"batch_id": batch_id})
    if all_json_df.empty:
        return pd.DataFrame()

    # Parser les folds WF depuis metrics_json
    folds_data: list[dict] = []
    for _, row in all_json_df.iterrows():
        blob = row.get("metrics_json")
        if blob is None:
            continue
        try:
            if isinstance(blob, bytes):
                blob = blob.decode("utf-8")
            wf_data = (json.loads(blob) if isinstance(blob, str) else blob).get("walk_forward", {})
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
        return pd.DataFrame()

    folds_df = pd.DataFrame(folds_data)

    # Agréger par split_index
    agg = folds_df.groupby(["split_index", "oos_start", "oos_end"], dropna=False).agg(
        nb_symbols=("f1_macro", "count"),
        f1_macro=("f1_macro", "mean"),
        f1_short=("f1_short", "mean"),
        f1_flat=("f1_flat", "mean"),
        f1_long=("f1_long", "mean"),
        action_rate=("action_rate", "mean"),
    ).reset_index().sort_values("oos_start")

    if agg.empty:
        return pd.DataFrame()

    # Récupérer SPY et VIX
    spy_df = _safe_query(engine, SPY_QUERY)
    vix_df = _safe_query(engine, VIX_QUERY)

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

    # Classifier les régimes
    valid_vix = [v for v in vix_values if v is not None]
    median_vix = float(pd.Series(valid_vix).median()) if valid_vix else 20.0

    def _safe_regime(sr: float | None, vx: float | None) -> str:
        if sr is None or vx is None:
            return "—"
        return _REGIME_LABELS.get(_classify_regime(sr, vx, median_vix), _classify_regime(sr, vx, median_vix))

    agg["regime"] = [_safe_regime(sr, vx) for sr, vx in zip(spy_returns, vix_values)]

    # Formater
    display = agg.rename(columns={
        "split_index": "Split",
        "oos_start": "Début OOS",
        "oos_end": "Fin OOS",
        "nb_symbols": "Nb symboles",
        "f1_macro": "F1 macro",
        "f1_short": "F1 short",
        "f1_flat": "F1 flat",
        "f1_long": "F1 long",
        "action_rate": "Tx action",
        "spy_return_pct": "SPY %",
        "avg_vix": "VIX moy",
        "regime": "Régime",
    })

    for col in ["F1 macro", "F1 short", "F1 flat", "F1 long"]:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and x is not None else "—")
    for col in ["Tx action", "SPY %", "VIX moy"]:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and x is not None else "—")

    cols = ["Split", "Début OOS", "Fin OOS", "Régime", "F1 macro", "F1 short", "F1 flat", "F1 long",
            "Tx action", "SPY %", "VIX moy", "Nb symboles"]
    display = display[[c for c in cols if c in display.columns]]
    return display


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
    reg_df = _safe_query(engine, REG_BY_SPLIT_QUERY, {"batch_id": batch_id})
    reg_top_df = _safe_query(engine, REG_TOP_QUERY, {"batch_id": batch_id})
    reg_worst_df = _safe_query(engine, REG_WORST_QUERY, {"batch_id": batch_id})

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

        # ── 🏆 Champion Global Model ──
        _meta_raw3 = row.get("metadata_json")
        if _meta_raw3 and str(_meta_raw3) not in ("None", "nan", ""):
            try:
                _meta3 = json.loads(str(_meta_raw3))
                _gr3 = _meta3.get("global_ranking") if isinstance(_meta3, dict) else None
                _champ_by_h3 = _gr3.get("champion_by_horizon") if isinstance(_gr3, dict) else None
                if _champ_by_h3 and isinstance(_champ_by_h3, dict) and _champ_by_h3:
                    from collections import Counter
                    _cnt3 = Counter(_champ_by_h3.values())
                    _majority3 = _cnt3.most_common(1)[0][0]
                    _h_det3 = ", ".join(f"H{k}={v}" for k, v in sorted(_champ_by_h3.items(), key=lambda x: int(x[0])))
                    lines.append(f"- **🏆 Champion Global** : {_majority3} ({_h_det3}) — score composite 55% IC + 30% IR + 15% positifs")
            except Exception:
                pass

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
                                     f"market cap ∈ [${_th.get('min_market_cap', '—'):,.0f}, ${_th.get('max_market_cap', '—'):,.0f}], "
                                     f"range High-Low ≤ {_th.get('max_avg_high_low_range_pct', '—')}%, "
                                     f"spread bid-ask ≤ {_th.get('max_spread_bps', '—')} bps")
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

    # ── Périodes de prédictions du batch ──
    _append_prediction_periods(lines, engine, batch_id)

    # ═══════════════════════════════════════════════════════════════
    # 🟢 GLOBAL MODEL — Ranking, Backtest, Champion
    # ═══════════════════════════════════════════════════════════════

    # ── Global Ranking Horizon Details ──
    _meta_raw = detail_df.iloc[0].get("metadata_json") if not detail_df.empty else None
    _append_global_ranking_horizon_details(lines, str(_meta_raw) if _meta_raw is not None else None)

    # ── Backtest Stratégies Global Rank ──
    _batch_id = detail_df.iloc[0].get("batch_id") if not detail_df.empty else None
    _append_backtest_results(lines, str(_batch_id) if _batch_id is not None else None, str(_meta_raw) if _meta_raw is not None else None)

    # ── Répartition Oracle — TOP / BOTTOM 10% du modèle ──
    _append_oracle_distribution(lines, engine, batch_id)

    # ── Oracle Extreme — Qualité du modèle (OOS) ──
    _append_oracle_extreme_quality(lines, engine, batch_id)

    # ── Per-Symbol Cross-Sectional IC — retiré ──

    # ═══════════════════════════════════════════════════════════════
    # 🔵 PER-SYMBOL / PER-SECTOR — Métriques d'entraînement
    # ═══════════════════════════════════════════════════════════════

    lines.append("---")
    lines.append("")
    lines.append("## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement")
    lines.append("")

    # ── Statut champion (per-symbol / per-sector) ──
    _append_champion_status(lines, champion_df, champion_by_model_df)

    # ── Métriques par horizon (si multi-horizon) ──
    horizon_df = _safe_query(engine, HORIZON_LIST_QUERY, {"batch_id": batch_id})
    if not horizon_df.empty:
        f1_h_df = _safe_query(engine, F1_BY_HORIZON_QUERY, {"batch_id": batch_id})
        if not f1_h_df.empty:
            lines.append("## 📊 Métriques par Horizon (WF)")
            lines.append("")
            # Rename columns for readability
            _h_display = f1_h_df.rename(columns={
                "horizon": "Horizon", "f1_macro": "F1 macro",
                "f1_short": "F1 short", "f1_long": "F1 long", "dir_acc": "Dir Acc",
            })
            lines.append(_df_to_md(_h_display))

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

    # ── Métriques régression (uniquement si batch regression) ──
    _is_reg_report = False
    try:
        _meta_raw3 = detail_df.iloc[0].get("metadata_json") if not detail_df.empty else None
        if isinstance(_meta_raw3, str) and _meta_raw3.strip():
            _meta3 = json.loads(str(_meta_raw3))
            _tm3 = str(_meta3.get("cli_options", {}).get("target_mode") or _meta3.get("target_mode") or "")
            _is_reg_report = _tm3 == "regression"
    except Exception:
        pass

    if _is_reg_report:
        lines.append("## 📊 Métriques Régression par split")
        lines.append("")
        if not reg_df.empty:
            _styled = reg_df.copy()
            for col in ["avg_mse", "avg_dir_acc"]:
                if col in _styled.columns:
                    _styled[col] = _styled[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
            lines.append(_df_to_md(_styled))
        else:
            lines.append("_Aucune métrique de régression disponible._")
            lines.append("")

        lines.append("## 🏆 Top 10 meilleurs `directional_accuracy` (WF)")
        lines.append("")
        lines.append(_df_to_md(reg_top_df))

        lines.append("## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)")
        lines.append("")
        lines.append(_df_to_md(reg_worst_df))

    # ── Diagnostic par régime de marché (tous modes) ──
    regime_df = _build_regime_table(engine, batch_id)
    if not regime_df.empty:
        lines.append("## 📅 Diagnostic par régime de marché — Walk-Forward")
        lines.append("")
        lines.append(_df_to_md(regime_df))

    return "\n".join(lines)
