"""ihm/pages/ml_diagnostics.py — Diagnostic ML (Analyse & Recherche)."""
from __future__ import annotations

import json as _json

import numpy as np
import pandas as pd
import streamlit as st

import shutil as _shutil
from pathlib import Path

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_unavailable
from ihm.services.db import db_available, safe_query, get_engine
from sqlalchemy import text
from ihm.services.ml_artifacts import get_model_artifacts_dir
from modelFactory.report import generate_batch_report


# ---------------------------------------------------------------------------
# Helper — mise en gras des lignes walk-forward dans les tableaux
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Backtest Global Rank (V1/V2/V3) — logique partagée
# ---------------------------------------------------------------------------

_REBALANCE_DAYS = 20
_TOP_PCT = 0.70
_H5_DIP = 0.35
_TRANSACTION_COST_BPS = 25.0
_MAX_POSITIONS = 30


def _run_strategy_backtest(rank_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Exécute les 3 variantes de stratégie sur un DataFrame de rangs.

    Returns:
        dict {variante: {sharpe, ann_return, ann_vol, max_drawdown}}.
    """
    _df = rank_df.sort_values(["date", "symbol"]).copy()
    _df["global_rank_5_prev"] = _df.groupby("symbol")["global_rank_5"].shift(1)
    _all_dates = sorted(_df["date"].unique())
    _rebal_dates = _all_dates[::_REBALANCE_DAYS]
    _results: dict[str, dict[str, float]] = {}

    for _label, _filter_fn in [
        ("V1 — H20 seul", lambda d: d["global_rank_20"] > _TOP_PCT),
        ("V2 — H20 + H5 rising", lambda d: (d["global_rank_20"] > _TOP_PCT) & (d["global_rank_5"] > d["global_rank_5_prev"])),
        ("V3 — H20 + H5 < 0.35", lambda d: (d["global_rank_20"] > _TOP_PCT) & (d["global_rank_5"] < _H5_DIP)),
    ]:
        _positions: dict[str, float] = {}
        _daily_rets = {}
        _turnover = 0
        for _d in _all_dates:
            _day = _df[_df["date"] == _d].set_index("symbol")
            _day_sig = _filter_fn(_day)
            if _d in _rebal_dates or not _positions:
                _candidates = _day.loc[_day_sig].sort_values("global_rank_20", ascending=False)
                if _positions:
                    _turnover += len(_positions)
                _positions = {}
                for _s in _candidates.index[:_MAX_POSITIONS]:
                    _positions[_s] = float(_candidates.loc[_s, "global_rank_20"])
                _turnover += len(_positions)
            _held = [s for s in _positions if s in _day.index]
            _daily_rets[_d] = float(_day.loc[_held, "global_rank_20"].mean()) - 0.5 if _held else 0.0

        _rets = pd.Series(_daily_rets).sort_index()
        _cost = (_TRANSACTION_COST_BPS / 10000.0) * _turnover / len(_all_dates)
        _rets = _rets - _cost / _REBALANCE_DAYS
        _excess = _rets - 0.02 / 252
        _mean = float(_excess.mean())
        _std = float(_excess.std())
        _sharpe = float(_mean / _std * np.sqrt(252)) if _std > 0 else 0.0
        _cum = (1 + _rets).cumprod()
        _dd = float((_cum / _cum.cummax() - 1).min())
        _results[_label] = {
            "sharpe": _sharpe,
            "ann_return": float(_mean * 252),
            "ann_vol": float(_std * np.sqrt(252)),
            "max_drawdown": _dd,
        }

    return _results


def _bold_wf_rows(df: pd.DataFrame):
    """Retourne un Styler pandas avec les lignes walk-forward en gras.

    Détecte la colonne de split (``split_name`` ou ``Split``) et met
    en gras les lignes dont la valeur est ``'wf'`` ou ``'walk_forward'``.
    """
    split_col = None
    for candidate in ("split_name", "Split"):
        if candidate in df.columns:
            split_col = candidate
            break
    if split_col is None:
        return df

    def _row_style(row: pd.Series) -> list[str]:
        val = str(row.get(split_col, ""))
        if val in ("wf", "walk_forward"):
            return ["font-weight: bold"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


# ---------------------------------------------------------------------------
# Requêtes SQL
# ---------------------------------------------------------------------------

# ── Requête SQL
# ---------------------------------------------------------------------------
# Le filtre horizon est injecté dynamiquement par _q() dans _render_batch_detail.
# Voir _horizon_sql et selected_horizon.

HORIZON_LIST_QUERY = """
    SELECT DISTINCT mm.horizon
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr
        ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id
      AND mm.horizon IS NOT NULL
    ORDER BY mm.horizon
"""

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
    WHERE mtr.batch_id = :batch_id
      AND mtr.status = 'completed'
      AND mm.split_name = 'wf'
    GROUP BY wf_f1_macro_bucket
    ORDER BY wf_f1_macro_bucket
"""

# ── Variantes filtrées par champion (selected_model) ──
# Jointure sur (symbol, model_name) + batch_id via model_training_run car
# model_governance.run_id pointe vers le run LSTM, pas celui du champion.
#
# ⚠️ Attention : mg.run_id ≠ mm.run_id quand le champion n'est pas LSTM.
# On joint donc sur (symbol, model_name) + is_selected_model = 1,
# et on vérifie que le run de gouvernance appartient au même batch.

F1_BUCKET_CHAMPION_QUERY = """
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

# ── Variantes champion pour les tableaux WF ──

TOP5_BEST_CHAMPION_QUERY = """
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

TOP5_WORST_CHAMPION_QUERY = """
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

ZERO_F1_SHORT_CHAMPION_QUERY = """
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
        ROUND(mm.directional_accuracy, 4) AS dir_acc
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id AND mtr.status = 'completed'
      AND mm.split_name = 'wf' AND mm.model_name != 'global_model'
    ORDER BY mm.directional_accuracy DESC LIMIT 10
"""

REG_WORST_QUERY = """
    SELECT
        mm.model_name, mm.symbol,
        ROUND(mm.directional_accuracy, 4) AS dir_acc
    FROM alpha_trade.model_metrics AS mm
    JOIN alpha_trade.model_training_run AS mtr ON mtr.run_id = mm.run_id
    WHERE mtr.batch_id = :batch_id AND mtr.status = 'completed'
      AND mm.split_name = 'wf' AND mm.model_name != 'global_model'
    ORDER BY mm.directional_accuracy ASC LIMIT 10
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
      AND mm.model_name != 'global_model'
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

# ── Global Rank History ──

GLOBAL_RANK_BATCHES_QUERY = """
    SELECT DISTINCT batch_id, COUNT(DISTINCT date) AS nb_dates, COUNT(DISTINCT symbol) AS nb_symbols
    FROM alpha_trade.global_rank_history
    GROUP BY batch_id
    ORDER BY batch_id DESC
    LIMIT 50
"""

GLOBAL_RANK_DATE_RANGE_QUERY = """
    SELECT MIN(date) AS min_date, MAX(date) AS max_date, COUNT(DISTINCT date) AS nb_dates
    FROM alpha_trade.global_rank_history
    WHERE batch_id = :batch_id
"""

GLOBAL_RANK_TOP_BOTTOM_QUERY = """
    SELECT
        symbol,
        date,
        global_rank_3,
        global_rank_5,
        global_rank_10,
        ROUND((COALESCE(global_rank_3, 0) + COALESCE(global_rank_5, 0)) / 2.0, 4) AS rank_avg_35,
        batch_id,
        created_at
    FROM alpha_trade.global_rank_history
    WHERE batch_id = :batch_id
      AND date = :date
    ORDER BY rank_avg_35 DESC
"""

GLOBAL_RANK_DATES_FOR_BATCH_QUERY = """
    SELECT DISTINCT date
    FROM alpha_trade.global_rank_history
    WHERE batch_id = :batch_id
    ORDER BY date DESC
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
        "to delete": "❌ À supprimer",
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
    st.dataframe(_bold_wf_rows(sym_df), use_container_width=True, hide_index=True)

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
        st.dataframe(_bold_wf_rows(probas_df), use_container_width=True, hide_index=True)
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


def _render_delete_batch_button(selected_batch: str, artifacts_dir: Path) -> None:
    """Affiche un bouton de suppression compact avec confirmation inline.

    Design : bouton simple → au clic, le bouton est remplacé par une ligne
    « ⚠️ Confirmer ?  [Oui] [Non] » sans bloc d'erreur volumineux.
    """
    from sqlalchemy import text as _text

    engine = get_engine()
    if engine is None:
        return

    # Vérifier le statut du batch (une seule fois)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                _text(
                    "SELECT status FROM alpha_trade.model_training_batch "
                    "WHERE batch_id = :bid LIMIT 1"
                ),
                {"bid": selected_batch},
            ).fetchone()
        batch_status = str(row[0]).strip().lower() if row else None
    except Exception:
        batch_status = None

    if batch_status == "completed":
        st.caption("✅ Batch complété — suppression impossible.")
        return

    confirm_key = f"ml_diag_confirm_delete_batch_{selected_batch}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False

    if not st.session_state[confirm_key]:
        # ── Étape 1 : simple bouton ──
        label = "🗑️ Supprimer ce batch"
        if batch_status is None:
            label = "🗑️ Supprimer (artefacts uniquement)"
        st.button(
            label,
            key=f"ml_diag_delete_btn_{selected_batch}",
            on_click=lambda: st.session_state.__setitem__(confirm_key, True),
        )
        if batch_status is None:
            st.caption("Batch absent de la DB — seuls les artefacts disque seront nettoyés.")
    else:
        # ── Étape 2 : confirmation compacte (1 ligne) ──
        _, c_yes, c_no = st.columns([2, 1, 1])
        with c_yes:
            confirmed = st.button(
                "✅ Oui, supprimer",
                key=f"ml_diag_confirm_btn_{selected_batch}",
                type="primary",
                use_container_width=True,
            )
        with c_no:
            cancelled = st.button(
                "❌ Annuler",
                key=f"ml_diag_cancel_btn_{selected_batch}",
                use_container_width=True,
            )
            if cancelled:
                st.session_state[confirm_key] = False
                st.rerun()

        if confirmed:
            errors: list[str] = []
            # Tables avec batch_id direct
            tables_direct = [
                "model_batch_diagnostics",
                "model_training_run",
                "model_training_batch",
            ]
            # Tables sans batch_id → DELETE via JOIN sur run_id
            tables_via_run = [
                "model_metrics",
                "model_metrics_full",
                "model_governance",
            ]
            try:
                with engine.begin() as conn:
                    for table in tables_direct:
                        conn.execute(
                            _text(f"DELETE FROM alpha_trade.{table} WHERE batch_id = :bid"),
                            {"bid": selected_batch},
                        )
                    for table in tables_via_run:
                        conn.execute(
                            _text(
                                f"DELETE FROM alpha_trade.{table} "
                                f"WHERE run_id IN (SELECT run_id FROM alpha_trade.model_training_run WHERE batch_id = :bid)"
                            ),
                            {"bid": selected_batch},
                        )
                total = len(tables_direct) + len(tables_via_run)
                st.success(f"✅ {total} tables nettoyées en base")
            except Exception as exc:
                errors.append(f"DB: {exc}")

            if artifacts_dir.exists():
                try:
                    _shutil.rmtree(artifacts_dir)
                    st.success(f"✅ Répertoire supprimé")
                except Exception as exc:
                    errors.append(f"Disque: {exc}")

            if errors:
                st.error("Erreurs : " + "; ".join(errors))
            else:
                st.success(f"🗑️ Batch `{selected_batch}` entièrement supprimé.")
                st.session_state.pop(confirm_key, None)
                st.rerun()


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
        col_dl, col_del = st.columns([3, 1])
        with col_dl:
            st.download_button(
                label="📥 Télécharger le rapport (.md)",
                data=generate_batch_report(engine, batch_id),
                file_name=f"{safe_bid}.md",
                mime="text/markdown",
                key=f"dl_{safe_bid}",
            )
        with col_del:
            _current_status = str(batch.get("status", "")).strip().lower()
            if _current_status == "to delete":
                st.info("❌ À supprimer", icon="🗑️")
            else:
                _del_key = f"del_{safe_bid}"
                if st.button("🗑️ TO DELETE", key=_del_key, type="secondary", help="Marque ce batch comme 'TO DELETE'."):
                    st.session_state["_confirm_to_delete"] = batch_id
                if st.session_state.get("_confirm_to_delete") == batch_id:
                    st.warning("Confirmer ?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Oui", key=f"{_del_key}_yes"):
                            _engine = get_engine()
                            if _engine is not None:
                                with _engine.connect() as _conn:
                                    _conn.execute(text("UPDATE model_training_batch SET status = 'TO DELETE' WHERE batch_id = :bid"), {"bid": batch_id})
                                    _conn.commit()
                            st.session_state["_confirm_to_delete"] = None
                            st.success("Batch marqué TO DELETE.")
                            st.rerun()
                    with c2:
                        if st.button("❌ Non", key=f"{_del_key}_no"):
                            st.session_state["_confirm_to_delete"] = None
                            st.rerun()

    row = detail_df.iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Batch ID", str(row.get("batch_id", ""))[:32] + "…" if len(str(row.get("batch_id", ""))) > 32 else str(row.get("batch_id", "")))
        st.metric("Statut", _status_badge(str(row.get("status", ""))))
        st.metric("Source symboles", str(row.get("symbol_source", "")))
        comment_val = row.get("comment")
        st.metric("Commentaire", str(comment_val) if comment_val and str(comment_val) != "None" and str(comment_val) != "nan" else "—")
        st.metric("Démarré le", str(row.get("started_at", "—")))
        st.metric("Terminé le", str(row.get("finished_at", "—")))

    with col2:
        # IC Rank du Global Ranking Model
        ic_val = row.get("ic_rank")
        if ic_val is not None and str(ic_val) not in ("None", "nan", ""):
            ic_display = f"{float(ic_val):.4f}"
            ic_help = "IC Rank (Spearman) du Global Ranking Model — >0.03 = utile, >0.05 = bon"
            st.metric("🎯 IC Rank Global", ic_display, help=ic_help)
        # IC IR (Information Ratio de l'IC)
        _ic_std_val = row.get("ic_rank_std")
        if ic_val is not None and _ic_std_val is not None and str(_ic_std_val) not in ("None", "nan", "") and float(_ic_std_val) > 0:
            _ic_ir = float(ic_val) / float(_ic_std_val)
            st.metric("📈 IC IR (Stabilité)", f"{_ic_ir:.2f}",
                      help="IC Information Ratio = IC Mean / IC Std. >0.5 = bon, >1.0 = exceptionnel. "
                           "Mesure la stabilité du signal dans le temps.")
        # Stacking Global Rank
        _stacking_val = row.get("stacking_enabled")
        if _stacking_val is not None:
            _stacking_bool = bool(int(_stacking_val))
            _stacking_label = "📥 Oui" if _stacking_bool else "📥 Non"
            st.metric("Stacking Global Rank", _stacking_label,
                      help="Le rang global (global_rank_3/5) a été injecté comme feature dans les modèles per-symbol.")

    with col3:
        st.metric("Date début training", str(row.get("training_start_date", "—")))
        st.metric("Date fin training", str(row.get("training_end_date", "—")))
        st.metric("Date univers", str(row.get("universe_date", "—")))
        st.metric("Nb symboles demandés", str(row.get("requested_symbol_count", "—")))
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

    # ── P0-8 (2026-08-07) : bannière batch en cours ──
    _batch_status = str(row.get("status", "")).strip().lower()
    if _batch_status == "running":
        _ic_available = row.get("ic_rank") is not None and str(row.get("ic_rank")) not in ("None", "nan", "")
        if _ic_available:
            st.info(
                "🟨 **Batch en cours d'exécution** — Le Global Ranking est terminé "
                f"(IC Rank = {float(row['ic_rank']):.4f}), l'entraînement per-symbol est en cours. "
                "Les métriques F1 / Directional Accuracy apparaîtront ci-dessous au fur et à mesure."
            )
        else:
            st.info(
                "🟨 **Batch en cours d'exécution** — Le Global Ranking Walk-Forward est en cours "
                "(5 horizons × 6 folds, ~30 min pour 939 symboles). "
                "Les métriques (IC Rank, F1, etc.) apparaîtront automatiquement ci-dessous une fois disponibles. "
                "Rafraîchissez la page (F5) pour voir les mises à jour."
            )
        # ── Afficher le détail global ranking immédiatement si dispo ──
        _render_global_ranking_horizon_details(row)
        st.markdown("")

    # ═══════════════════════════════════════════════════════════════
    # 🟢 GLOBAL MODEL — Ranking, Backtest, Champion
    # ═══════════════════════════════════════════════════════════════

    st.subheader("🔵 Modèle global — Métriques")

    # ── Backtest Global Rank Strategies (V1/V2/V3) ──
    with st.expander("🧪 Backtest Stratégies Global Rank (H20 + H5)", expanded=False):
        _batch_id = str(row["batch_id"])
        _cache_path = Path(get_model_artifacts_dir()) / _batch_id / "global_rank_cache.parquet"
        if _cache_path.exists():
            if st.button("🚀 Lancer le backtest", key=f"backtest_{_batch_id}"):
                try:
                    import numpy as np
                    _rank_df = pd.read_parquet(_cache_path)
                    _rank_df["date"] = pd.to_datetime(_rank_df["date"])
                    _results = _run_strategy_backtest(_rank_df)
                    if _results:
                        st.markdown("### 📊 Classement relatif des stratégies")
                        _best = max(_results, key=lambda v: _results[v]["sharpe"])
                        _rows = []
                        for _v, _m in _results.items():
                            _pct = f"{(_m['sharpe'] / _results[_best]['sharpe'] - 1) * 100:+.1f}%" if _v != _best else "🏆 référence"
                            _rows.append({"Variante": _v, "Score relatif": _pct})
                        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
                        st.success(f"🏆 Meilleure stratégie : **{_best}**")
                        st.caption(
                            "Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. "
                            "Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). "
                            "Frais 0.25% A/R inclus. "
                            "V1 = H20 seul, V2 = H20 + H5 rising, V3 = H20 + H5 < 0.35 (contrarian)."
                        )
                except Exception as _exc:
                    st.error(f"Échec du backtest : {_exc}")
        else:
            st.info(
                "Cache `global_rank_cache.parquet` non trouvé. "
                "Relancez un batch avec la dernière version de `global_ranking.py` pour le générer."
            )

    # ── Global Rank History ──
    _render_global_rank_history(batch_id)
    # ── Global Ranking Horizon Details (seulement si pas déjà affiché pour batch running) ──
    if _batch_status.strip().lower() != "running":
        _render_global_ranking_horizon_details(row)

    # ═══════════════════════════════════════════════════════════════
    # 🔵 PER-SYMBOL / PER-SECTOR — Métriques d'entraînement
    # ═══════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("🔵 Per-Symbol / Per-Sector — Métriques")

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

    # ── Détection mode régression vs classification ──
    # Règle fiable : lire target_mode depuis metadata_json (pas d'heuristique SQL).
    # ⚠️ batch vient de BATCH_LIST_QUERY (colonnes limitées) → utiliser detail_df.
    _target_mode: str = "ternary"
    try:
        _meta_raw = detail_df.iloc[0].get("metadata_json") if not detail_df.empty else None
        if isinstance(_meta_raw, str) and _meta_raw.strip():
            import json
            _meta = json.loads(_meta_raw)
            _target_mode = str(_meta.get("cli_options", {}).get("target_mode") or _meta.get("target_mode") or "ternary")
    except Exception:
        pass
    _is_reg_batch = _target_mode == "regression"
    _has_classif = _target_mode in ("binary", "ternary", "swing_cash")

    # ── Horizon selector (avant les métriques) ──
    horizon_list = safe_query(HORIZON_LIST_QUERY, {"batch_id": batch_id})
    selected_horizon: int | None = None
    _horizon_sql: str = ""
    if not horizon_list.empty:
        _horizons = [None] + [int(h) for h in horizon_list["horizon"].dropna().sort_values()]
        selected_horizon = st.selectbox(
            "Horizon",
            options=_horizons,
            format_func=lambda h: f"H{h}" if h is not None else "Tous les horizons",
            key=f"horizon_{batch_id}",
        )
        if selected_horizon is not None:
            _horizon_sql = " AND mm.horizon = :horizon"

    def _q(sql: str, extra_params: dict | None = None) -> pd.DataFrame:
        """Exécute une requête avec le filtre horizon injecté dynamiquement.

        - ``selected_horizon is None`` (Tous) : pas de filtre → agrégation sur tous les horizons (AVG).
        - ``selected_horizon = 3`` (H3) : filtre ``AND mm.horizon = 3``.
        """
        _sql = sql
        if _horizon_sql:
            # Injecte le filtre horizon avant GROUP BY / ORDER BY / LIMIT
            if "GROUP BY" in _sql:
                _sql = _sql.replace("GROUP BY", f"{_horizon_sql}\n    GROUP BY")
            elif "ORDER BY" in _sql:
                _sql = _sql.replace("ORDER BY", f"{_horizon_sql}\n    ORDER BY")
            elif "LIMIT" in _sql:
                _sql = _sql.replace("LIMIT", f"{_horizon_sql}\n    LIMIT")
        params: dict[str, object] = {"batch_id": batch_id}
        if selected_horizon is not None:
            params["horizon"] = selected_horizon
        if extra_params:
            params.update(extra_params)
        return safe_query(_sql, params)

    # ── Indicateur d'horizon ──
    if not horizon_list.empty:
        if selected_horizon is not None:
            st.caption(f"🔍 Horizon sélectionné : **H{selected_horizon}** — métriques filtrées sur cet horizon uniquement.")
        else:
            st.caption("🔍 **Tous horizons confondus** — chaque métrique est la moyenne (AVG) des 5 horizons H3/H5/H10/H15/H20.")

 

    if _is_reg_batch:
        # ── Bloc régression par split ──
        st.subheader("📊 Métriques Régression par split")
        reg_df = _q(REG_BY_SPLIT_QUERY)
        if reg_df.empty:
            st.info("Aucune métrique de régression disponible.")
        else:
            styled = reg_df.copy()
            for col in ["avg_mse", "avg_dir_acc"]:
                if col in styled.columns:
                    styled[col] = styled[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
            styled = styled.rename(columns={
                "model_name": "Modèle", "split_name": "Split",
                "nb_symbols": "Nb symboles", "avg_mse": "MSE moy", "avg_dir_acc": "Dir Acc",
            })
            st.dataframe(_bold_wf_rows(styled), use_container_width=True, hide_index=True)
        st.markdown("")

        # ── Top / Flop Directional Accuracy ──
        col_top_r, col_worst_r = st.columns(2)
        with col_top_r:
            st.markdown("**🥇 10 meilleurs `directional_accuracy` (WF)**")
            rtop = _q(REG_TOP_QUERY)
            if not rtop.empty:
                st.dataframe(rtop, use_container_width=True, hide_index=True)
            else:
                st.caption("Aucune donnée.")
        with col_worst_r:
            st.markdown("**🥉 10 plus mauvais `directional_accuracy` (WF)**")
            rworst = _q(REG_WORST_QUERY)
            if not rworst.empty:
                st.dataframe(rworst, use_container_width=True, hide_index=True)
            else:
                st.caption("Aucune donnée.")
        st.markdown("")

    # ── Bloc F1 par split ──
    st.subheader("📊 Métriques F1 par split")

    f1_df = _q(F1_BY_SPLIT_QUERY)
    if f1_df.empty:
        st.info("Aucune métrique F1 disponible pour ce batch (vérifiez que les runs sont `completed`).")
    else:
        styled = f1_df.copy()
        for col in ["avg_f1_macro", "avg_f1_short", "avg_f1_flat", "avg_f1_long"]:
            if col in styled.columns:
                styled[col] = styled[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        st.dataframe(_bold_wf_rows(styled), use_container_width=True, hide_index=True)

    st.markdown("")
    # ── Bloc distribution true / pred par split ──
    st.subheader("📊 Distribution true / pred par split")
    tp_df = _q(TRUE_PRED_AGG_QUERY)
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
        st.dataframe(_bold_wf_rows(styled), use_container_width=True, hide_index=True)

    st.markdown("")
    # ── Bloc distribution F1 macro (walk-forward) ──
    st.subheader("📈 Distribution F1 macro — Walk-Forward")

    champion_only_wf = st.checkbox(
        "🏆 Afficher uniquement les champions (1 seul modèle par symbole)",
        value=True,
        key="ml_diag_champion_only_wf",
        help="Si coché, seul le modèle sélectionné comme champion (selected_model) est retenu par symbole. "
             "Sinon, tous les challengers (LSTM, LightGBM, CatBoost, Global) sont affichés — un même symbole peut apparaître plusieurs fois.",
    )

    _bucket_q = F1_BUCKET_CHAMPION_QUERY if champion_only_wf else F1_BUCKET_QUERY
    _best_q = TOP5_BEST_CHAMPION_QUERY if champion_only_wf else TOP5_BEST_F1_QUERY
    _worst_q = TOP5_WORST_CHAMPION_QUERY if champion_only_wf else TOP5_WORST_F1_QUERY
    _zero_q = ZERO_F1_SHORT_CHAMPION_QUERY if champion_only_wf else ZERO_F1_SHORT_QUERY

    bucket_df = _q(_bucket_q)
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
    sub_label = "🏆 Top / Flop symboles — Walk-Forward"
    if champion_only_wf:
        sub_label += " (champions)"
    st.subheader(sub_label)

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
        best_df = _q(_best_q)
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
        worst_df = _q(_worst_q)
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
        zero_df = _q(_zero_q)
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

    # ── Suppression batch (tout en bas du détail) ──
    st.divider()
    artifacts_dir = get_model_artifacts_dir() / batch_id
    _render_delete_batch_button(batch_id, artifacts_dir)


def _render_global_rank_history(batch_id: str) -> None:
    """Affiche les rangs globaux historiques de la table global_rank_history."""
    st.subheader("🌐 Ranks Globaux Historiques (global_rank_history)")

    # ── Vérifier si des données existent pour ce batch ──
    date_range_df = safe_query(GLOBAL_RANK_DATE_RANGE_QUERY, {"batch_id": batch_id})
    if date_range_df.empty or date_range_df.iloc[0]["nb_dates"] == 0:
        st.info(f"Aucun rang global historique trouvé pour le batch `{batch_id}`. Les rangs sont générés via **10. ML Predict → Prédire l'univers sélectionné**.")
        return

    dr = date_range_df.iloc[0]
    st.caption(f"📅 {dr['nb_dates']} dates disponibles — du {str(dr['min_date'])[:10]} au {str(dr['max_date'])[:10]}")

    # ── Sélecteur de date ──
    dates_df = safe_query(GLOBAL_RANK_DATES_FOR_BATCH_QUERY, {"batch_id": batch_id})
    if dates_df.empty:
        st.info("Aucune date trouvée.")
        return

    available_dates = sorted(dates_df["date"].dropna().unique(), reverse=True)
    available_dates_str = [str(d)[:10] for d in available_dates]

    selected_date_str = st.selectbox(
        "📅 Sélectionner une date",
        available_dates_str,
        key=f"global_rank_date_{batch_id}",
    )

    if not selected_date_str:
        return

    # ── Top/Bottom N% ──
    top_pct = st.slider(
        "Top/Bottom %",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        key=f"global_rank_pct_{batch_id}",
        help="Afficher les Top N% et Bottom N% des rangs pour cette date.",
    )

    # ── Requête principale ──
    rank_df = safe_query(
        GLOBAL_RANK_TOP_BOTTOM_QUERY,
        {"batch_id": batch_id, "date": selected_date_str},
    )

    if rank_df.empty:
        st.info(f"Aucun rang pour le {selected_date_str}.")
        return

    n_total = len(rank_df)
    n_cut = max(1, int(n_total * top_pct / 100))

    top_df = rank_df.head(n_cut).copy()
    bottom_df = rank_df.tail(n_cut).copy()

    # ── Stats ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Nb symboles", n_total)
    with c2:
        st.metric("Médiane rank_avg_35", f"{rank_df['rank_avg_35'].median():.4f}" if not rank_df['rank_avg_35'].isna().all() else "—")
    with c3:
        h3_ok = (~rank_df['global_rank_3'].isna()).sum()
        st.metric("H3 renseigné", f"{h3_ok}/{n_total}")
    with c4:
        h5_ok = (~rank_df['global_rank_5'].isna()).sum()
        st.metric("H5 renseigné", f"{h5_ok}/{n_total}")

    st.markdown("")

    # ── Tableaux Top / Bottom côte à côte ──
    col_top, col_bottom = st.columns(2)

    with col_top:
        st.markdown(f"**🟢 Top {top_pct}% ({len(top_df)} symboles)**")
        top_display = top_df[["symbol", "global_rank_3", "global_rank_5", "rank_avg_35"]].copy()
        top_display["rank"] = range(1, len(top_display) + 1)
        top_display = top_display[["rank", "symbol", "global_rank_3", "global_rank_5", "rank_avg_35"]]
        st.dataframe(
            top_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "rank": "#",
                "symbol": "Symbole",
                "global_rank_3": st.column_config.NumberColumn("Rank H3", format="%.4f"),
                "global_rank_5": st.column_config.NumberColumn("Rank H5", format="%.4f"),
                "rank_avg_35": st.column_config.NumberColumn("Avg(H3,H5)", format="%.4f"),
            },
        )

    with col_bottom:
        st.markdown(f"**🔴 Bottom {top_pct}% ({len(bottom_df)} symboles)**")
        bottom_display = bottom_df[["symbol", "global_rank_3", "global_rank_5", "rank_avg_35"]].copy()
        bottom_display = bottom_display.sort_values("rank_avg_35", ascending=True)
        bottom_display["rank"] = range(1, len(bottom_display) + 1)
        bottom_display = bottom_display[["rank", "symbol", "global_rank_3", "global_rank_5", "rank_avg_35"]]
        st.dataframe(
            bottom_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "rank": "#",
                "symbol": "Symbole",
                "global_rank_3": st.column_config.NumberColumn("Rank H3", format="%.4f"),
                "global_rank_5": st.column_config.NumberColumn("Rank H5", format="%.4f"),
                "rank_avg_35": st.column_config.NumberColumn("Avg(H3,H5)", format="%.4f"),
            },
        )

    # ── Export CSV ──
    st.markdown("")
    csv_data = rank_df.to_csv(index=False)
    st.download_button(
        label=f"📥 Télécharger tous les rangs du {selected_date_str} (.csv)",
        data=csv_data,
        file_name=f"global_rank_{batch_id}_{selected_date_str}.csv",
        mime="text/csv",
        key=f"dl_gr_{batch_id}_{selected_date_str}",
    )

    # ── Aide ──
    with st.expander("ℹ️ À propos des rangs globaux", expanded=False):
        st.markdown("""
- **`global_rank_3` / `global_rank_5`** : rang cross-sectional [0, 1] prédit par le Global Ranking Model (LightGBM LambdaRank).
- **1.0** = meilleur rang (top de l'univers), **0.0** = pire rang.
- **`rank_avg_35`** = moyenne arithmétique de H3 et H5 — utilisé par la cascade pour le filtrage.
- Les rangs sont générés via **10. ML Predict → Prédire l'univers sélectionné** et stockés dans la table `global_rank_history`.
- Les données sont écrasées (upsert) à chaque nouvelle prédiction pour la même date + batch.
""")



def _render_global_ranking_horizon_details(row: pd.Series) -> None:
    """Affiche les détails du Global Ranking Model par horizon (IC, decile spread,
    feature importance, splits) depuis metadata_json."""
    _meta_raw = row.get("metadata_json")
    if _meta_raw is None or str(_meta_raw) in ("None", "nan", ""):
        return

    try:
        _meta = _json.loads(str(_meta_raw))
    except Exception:
        return

    _gr = _meta.get("global_ranking")
    if not _gr or not isinstance(_gr, dict):
        return

    _hd = _gr.get("horizon_details")
    if not _hd or not isinstance(_hd, dict):
        return

    st.subheader("🌐 Global Ranking — Détails par Horizon")
    st.caption(
        f"Modèle Catboost — {_gr.get('symbols_count', '?')} symboles, "
        f"{_gr.get('splits_count', '?')} splits walk-forward, "
        f"{_gr.get('pred_rows', '?')} lignes de prédiction"
    )

    # ── Tableau récapitulatif tous horizons ──
    _ic_by_h = _gr.get("ic_by_horizon", {})
    _ds_by_h = _gr.get("decile_spreads", {})

    _summary_rows: list[dict] = []
    for _h_key in sorted(_hd.keys(), key=lambda x: int(x)):
        _h_info = _hd[_h_key]
        _h_ic = _ic_by_h.get(_h_key)
        # IC IR = IC Mean / IC Std (depuis les splits)
        _split_ics = [s.get("ic_rank") for s in _h_info.get("splits", []) if s.get("ic_rank") is not None]
        _h_ic_ir: float | None = None
        if _split_ics and len(_split_ics) > 1:
            import numpy as np
            _arr = np.array(_split_ics, dtype=float)
            if _arr.std() > 0:
                _h_ic_ir = float(_arr.mean() / _arr.std())
        _summary_rows.append({
            "Horizon": f"H{_h_key}",
            "IC Mean": _h_ic,
            "IC IR": round(_h_ic_ir, 2) if _h_ic_ir is not None else "—",
            "Decile Spread": _ds_by_h.get(_h_key),
            "Nb Features": _h_info.get("n_features", "—"),
            "Nb Splits": len(_h_info.get("splits", [])),
        })

    if _summary_rows:
        _sum_df = pd.DataFrame(_summary_rows)
        st.dataframe(
            _sum_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Horizon": "Horizon",
                "IC Mean": st.column_config.NumberColumn("🎯 IC Mean", format="%.4f"),
                "IC IR": "📈 IC IR",
                "Decile Spread": st.column_config.NumberColumn("📊 Decile Spread", format="%.4f"),
                "Nb Features": "Nb Features",
                "Nb Splits": "Nb Splits",
            },
        )

    # ── Détail par horizon (expander) ──
    for _h_key in sorted(_hd.keys(), key=lambda x: int(x)):
        _h_info = _hd[_h_key]
        _ic_val = _ic_by_h.get(_h_key, 0)
        _ds_val = _ds_by_h.get(_h_key, 0)
        _ic_color = "🟢" if _ic_val and _ic_val >= 0.02 else ("🟡" if _ic_val and _ic_val >= 0.01 else "🔴")
        _ds_color = "🟢" if _ds_val and _ds_val >= 0.01 else ("🟡" if _ds_val and _ds_val >= 0.005 else "🔴")

        with st.expander(
            f"H{_h_key}  |  {_ic_color} IC Rank: {_ic_val:.4f}  |  {_ds_color} Decile Spread: {_ds_val:.4f}  |  {_h_info.get('n_features', '—')} features",
            expanded=False,
        ):
            # ── Feature Importance Top10 / Bottom10 ──
            _fi_top10 = _h_info.get("feature_importance_top10", [])
            _fi_bottom10 = _h_info.get("feature_importance_bottom10", [])

            if _fi_top10:
                col_fi1, col_fi2 = st.columns(2)
                with col_fi1:
                    st.markdown("**🔝 Feature Importance — Top 10**")
                    _fi_top_df = pd.DataFrame(_fi_top10)
                    if "importance" in _fi_top_df.columns:
                        _fi_top_df["importance"] = _fi_top_df["importance"].round(1)
                    st.dataframe(
                        _fi_top_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "feature": "Feature",
                            "importance": st.column_config.NumberColumn("Importance", format="%.1f"),
                        },
                    )
                with col_fi2:
                    st.markdown("**🔻 Feature Importance — Bottom 10**")
                    _fi_bot_df = pd.DataFrame(_fi_bottom10)
                    if "importance" in _fi_bot_df.columns:
                        _fi_bot_df["importance"] = _fi_bot_df["importance"].round(1)
                    st.dataframe(
                        _fi_bot_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "feature": "Feature",
                            "importance": st.column_config.NumberColumn("Importance", format="%.1f"),
                        },
                    )

            # ── Tableau des splits ──
            _splits = _h_info.get("splits", [])
            if _splits:
                st.markdown("**📅 Détail par split**")
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
                _sp_df = pd.DataFrame(_split_rows)
                st.dataframe(
                    _sp_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Split": st.column_config.NumberColumn("Split", format="%d"),
                        "Train (début→fin)": "Période Train",
                        "Validation (début→fin)": "Période Validation",
                        "Lignes Train": st.column_config.NumberColumn("Lignes Train", format="%d"),
                        "Lignes Val": st.column_config.NumberColumn("Lignes Val", format="%d"),
                        "IC Rank": st.column_config.NumberColumn("🎯 IC Rank", format="%.4f"),
                    },
                )

            # ── Métriques par split (mini-distribution) ──
            _split_ics = [_sp.get("ic_rank") for _sp in _splits if _sp.get("ic_rank") is not None]
            if _split_ics:
                import numpy as np
                _arr = np.array(_split_ics, dtype=float)
                _col1, _col2, _col3, _col4 = st.columns(4)
                with _col1:
                    st.metric("IC Moyen", f"{_arr.mean():.4f}")
                with _col2:
                    st.metric("IC Std", f"{_arr.std():.4f}")
                with _col3:
                    st.metric("IC Min", f"{_arr.min():.4f}")
                with _col4:
                    st.metric("IC Max", f"{_arr.max():.4f}")


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
    if "batch_id" in display_df.columns and "status" in batches_df.columns:
        # Prefix "❌ " for TO DELETE batches
        _raw_status = batches_df["status"].fillna("").str.strip().str.lower()
        display_df["batch_id"] = display_df.apply(
            lambda r: ("❌ " if _raw_status.loc[r.name] == "to delete" else "") + str(r["batch_id"]),
            axis=1,
        )
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

    # ── Bouton nettoyage batchs ──
    st.divider()
    with st.expander("🧹 Nettoyer les batchs", expanded=False):
        from modelFactory.cleanup_incomplete_batches import cleanup_batches, list_batches
        _include_completed = st.checkbox("🗑️ Inclure les batchs **terminés** (TOUT supprimer)", value=False)
        _candidates = list_batches(include_completed=_include_completed)
        _label = "terminés et non terminés" if _include_completed else "non terminés"
        if _candidates:
            st.warning(f"{len(_candidates)} batch(s) {_label}")
            if st.button("🗑️ Supprimer tous les batchs listés", type="primary"):
                st.session_state["_confirm_cleanup"] = True
            if st.session_state.get("_confirm_cleanup"):
                st.error("⚠️ Cette action est irréversible. Confirmez :")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Oui, supprimer", key="cleanup_confirm"):
                        result = cleanup_batches(dry_run=False, include_completed=_include_completed)
                        st.success(
                            f"✅ {result['deleted_batches']} batch(s), "
                            f"{result['deleted_db_rows']} lignes DB, "
                            f"{result['deleted_dirs']} répertoires."
                        )
                        st.session_state["_confirm_cleanup"] = False
                        st.rerun()
                with col2:
                    if st.button("❌ Annuler", key="cleanup_cancel"):
                        st.session_state["_confirm_cleanup"] = False
                        st.rerun()
        else:
            st.info(f"✅ Aucun batch {_label}.")

    row_index = _selected_row_index(BATCH_TABLE_KEY)
    if row_index is None or row_index >= len(batches_df):
        st.info("👆 Cliquez sur un batch dans le tableau ci-dessus pour afficher son détail et ses métriques.")
        return

    selected_batch = batches_df.iloc[row_index]

    st.divider()
    _render_batch_detail(selected_batch)


if __name__ == "__main__":
    render()
