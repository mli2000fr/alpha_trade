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
        mm.model_name, mm.symbol,
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
        mm.model_name, mm.symbol,
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

    # ── Infos modèle (champion ou fixe) ──
    _model_label = "CatBoost"  # fallback
    _champion_by_h = _gr.get("champion_by_horizon")
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
            # Détecter si le mode champion est actif (colonnes ic_rank_*)
            _has_split_champion = any(
                k.startswith("ic_rank_") and k != "ic_rank"
                for _sp in _splits for k in (_sp or {}).keys()
            )
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
                    "IC Rank": _sp.get("ic_rank"),
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
) -> None:
    """Ajoute la section backtest stratégies Global Rank (V1/V2/V3)."""
    if not batch_id:
        return
    _cache = Path("artifacts") / "models" / batch_id / "global_rank_cache.parquet"
    if not _cache.exists():
        return
    try:
        import numpy as np
        _df = pd.read_parquet(_cache)
        _df["date"] = pd.to_datetime(_df["date"])
        _df["global_rank_5_prev"] = _df.groupby("symbol")["global_rank_5"].shift(1)
        _all_dates = sorted(_df["date"].unique())
        _rebal = _all_dates[::20]
        _results = {}
        for _label, _fn in [
            ("V1 — H20 seul", lambda d: d["global_rank_20"] > 0.70),
            ("V2 — H20 + H5 rising", lambda d: (d["global_rank_20"] > 0.70) & (d["global_rank_5"] > d["global_rank_5_prev"])),
            ("V3 — H20 + H5 < 0.35", lambda d: (d["global_rank_20"] > 0.70) & (d["global_rank_5"] < 0.35)),
        ]:
            _pos = {}
            _rets = {}
            _turn = 0
            for _d in _all_dates:
                _day = _df[_df["date"] == _d].set_index("symbol")
                _sig = _fn(_day)
                if _d in _rebal or not _pos:
                    _cand = _day.loc[_sig].sort_values("global_rank_20", ascending=False)
                    if _pos:
                        _turn += len(_pos)
                    _pos = {s: float(_cand.loc[s, "global_rank_20"]) for s in _cand.index[:30]}
                    _turn += len(_pos)
                _held = [s for s in _pos if s in _day.index]
                _rets[_d] = float(_day.loc[_held, "global_rank_20"].mean()) - 0.5 if _held else 0.0
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
            lines.append("## 🧪 Backtest Stratégies — Global Rank")
            lines.append("")
            _best = max(_results, key=lambda v: _results[v]["sharpe"])
            lines.append("| Variante | Score relatif |")
            lines.append("|----------|---------------|")
            for _l, _m in _results.items():
                _pct = f"{(_m['sharpe'] / _results[_best]['sharpe'] - 1) * 100:+.1f}%" if _l != _best else "🏆 référence"
                lines.append(f"| {_l} | {_pct} |")
            lines.append("")
            lines.append(
                "> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. "
                "Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). "
                "Frais 0.25% A/R inclus. "
                "V1 = H20 seul, V2 = H20 + H5 rising, V3 = H20 + H5 < 0.35 (contrarian)."
            )
            lines.append("")
    except Exception:
        pass


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

    # ═══════════════════════════════════════════════════════════════
    # 🟢 GLOBAL MODEL — Ranking, Backtest, Champion
    # ═══════════════════════════════════════════════════════════════

    # ── Statut champion ──
    _append_champion_status(lines, champion_df, champion_by_model_df)

    # ── Global Ranking Horizon Details ──
    _meta_raw = detail_df.iloc[0].get("metadata_json") if not detail_df.empty else None
    _append_global_ranking_horizon_details(lines, str(_meta_raw) if _meta_raw is not None else None)

    # ── Backtest Stratégies Global Rank ──
    _batch_id = detail_df.iloc[0].get("batch_id") if not detail_df.empty else None
    _append_backtest_results(lines, str(_batch_id) if _batch_id is not None else None)

    # ── Per-Symbol Cross-Sectional IC — retiré ──

    # ═══════════════════════════════════════════════════════════════
    # 🔵 PER-SYMBOL / PER-SECTOR — Métriques d'entraînement
    # ═══════════════════════════════════════════════════════════════

    lines.append("---")
    lines.append("")
    lines.append("## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement")
    lines.append("")

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
