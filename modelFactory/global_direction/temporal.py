"""modelFactory/global_direction/temporal.py — Hypothèse temporelle GlobalDirection.

**Question** : la trajectoire J-5/J-10 des features directionnelles porte-t-elle
la direction absente des valeurs statiques à J ?

Discipline identique au harnais DirectionalDataResearch : **diagnostic AVANT
entraînement**, dans le pool Oracle Extreme TOP20% :

- IC Spearman vs décile futur ;
- AUC(D1-D5 vs D6-D10) = AUC_direction, AUC(D1-D3 vs D8-D10), AUC(D1 vs D10) ;
- AUC_amplitude (D1∪D10 vs D2-D9) → ``dir_vs_amp`` (ne pas réapprendre Oracle) ;
- stabilité du signe par fold WF (``stable_folds`` / ``total_folds``) ;
- **comparaison STATIC vs TEMPORAL** : pour chaque feature de base, ``delta_auc`` =
  AUC(feature temporelle) − AUC(feature statique à J).

Sources PIT strict (J..J-10, jamais J+1) :
- 8 features de score : ``stock_scores_history`` — merge_asof backward par symbole
  (dernier snapshot ≤ J) + colonne ``snapshot_age_days`` + rapport de couverture ;
- ``momentum_20`` / ``momentum_60`` : calculés depuis ``stock_bars_daily``
  (adj_close), série quotidienne dense ;
- ``stock_vs_sector_ret_20/60`` : moteur sectoriel existant (sinon loggués
  indisponibles, non inventés).

Dérivées temporelles (PIT) : ``t0``, ``lag_1/3/5/10``, ``delta_1/3/5/10``,
``mean_3/5/10``, ``slope_3/5/10``, ``std_5/10``, + ``positive_fraction_5/10`` et
``sign_change_5`` pour les features signées.

Sortie : ``artifacts/global_direction_temporal_separability.csv`` trié par
stabilité, puis delta_auc, puis AUC directionnelle.

Usage :
    python -m modelFactory.global_direction.temporal --batch-id ... \\
        --start-date 2022-01-01 --end-date 2026-05-29 [--oracle-run oracle-wf-...]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import assemble_pool
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.global_direction.dataset import DECILE_COL
from modelFactory.oracle.train import roc_auc

LOGGER = logging.getLogger(__name__)

# ── Features de base (petit groupe, PAS les 182) ────────────────────────────
SCORE_FEATURES = [
    "sentiment_net_agg", "company_idio_signal_norm", "company_idio_score",
    "sector_impact_agg", "short_score", "relative_strength_index_neutralized",
    "trend_score", "weekly_trend_score",
]
MOMENTUM_FEATURES = ["momentum_20", "momentum_60"]
SECTOR_FEATURES = ["stock_vs_sector_ret_20", "stock_vs_sector_ret_60"]

BASE_FEATURES = SCORE_FEATURES + MOMENTUM_FEATURES + SECTOR_FEATURES

# Transforms : (suffixe, fonction sur la série groupée par symbole, fenêtre)
_LAG_WINDOWS = [1, 3, 5, 10]
_DELTA_WINDOWS = [1, 3, 5, 10]
_MEAN_WINDOWS = [3, 5, 10]
_SLOPE_WINDOWS = [3, 5, 10]
_STD_WINDOWS = [5, 10]
_SIGNED_WINDOWS = [5, 10]
_SIGN_CHANGE_WINDOW = 5


def _temporal_columns(base: str) -> list[str]:
    """Noms des colonnes temporelles dérivées d'une feature de base."""
    cols = [f"{base}__t0"]
    cols += [f"{base}__lag_{w}" for w in _LAG_WINDOWS]
    cols += [f"{base}__delta_{w}" for w in _DELTA_WINDOWS]
    cols += [f"{base}__mean_{w}" for w in _MEAN_WINDOWS]
    cols += [f"{base}__slope_{w}" for w in _SLOPE_WINDOWS]
    cols += [f"{base}__std_{w}" for w in _STD_WINDOWS]
    cols += [f"{base}__pos_frac_{w}" for w in _SIGNED_WINDOWS]
    cols += [f"{base}__sign_change_{_SIGN_CHANGE_WINDOW}"]
    return cols


def _slope(series: pd.Series, window: int) -> pd.Series:
    """Pente par différence finie sur la fenêtre : (v_t − v_{t−k}) / k."""
    return (series - series.shift(window)) / float(window)


# ── Sources ──────────────────────────────────────────────────────────────────

def load_bars_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Panel quotidien (symbol, date, adj_close) depuis ``stock_bars_daily``."""
    start = (pd.Timestamp(start_date) - pd.Timedelta(days=25)).date().isoformat()
    placeholders = ",".join(["%s"] * len(symbols))
    query = f"""
        SELECT symbol, date, adj_close
        FROM stock_bars_daily
        WHERE symbol IN ({placeholders}) AND date >= %s AND date <= %s
        ORDER BY symbol, date
    """
    df = pd.read_sql(query, engine, params=(*symbols, start, end_date))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.dropna(subset=["date", "symbol", "adj_close"])


def load_score_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Features de score depuis ``stock_scores_history`` (snapshots).

    Retourne (symbol, snapshot_date, *SCORE_FEATURES) — SANS fusion PIT ici
    (le merge_asof sur le calendrier bars est fait dans ``build_panel``).
    """
    present = [c for c in SCORE_FEATURES if c in _score_history_columns(engine)]
    if not present:
        return pd.DataFrame()
    start = (pd.Timestamp(start_date) - pd.Timedelta(days=25)).date().isoformat()
    placeholders = ",".join(["%s"] * len(symbols))
    cols = ", ".join(present)
    query = f"""
        SELECT symbol, snapshot_date, {cols}
        FROM stock_scores_history
        WHERE symbol IN ({placeholders}) AND snapshot_date >= %s AND snapshot_date <= %s
    """
    df = pd.read_sql(query, engine, params=(*symbols, start, end_date))
    if df.empty:
        return df
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    for c in present:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["snapshot_date", "symbol"])


def _score_history_columns(engine: Any) -> list[str]:
    try:
        cols = pd.read_sql("SHOW COLUMNS FROM stock_scores_history", engine)
        return list(cols["Field"])
    except Exception:
        return []


def load_sector_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> tuple[pd.DataFrame, list[str]]:
    """Features sectorielles stock_vs_sector_ret_20/60 (moteur existant)."""
    from modelFactory.global_direction.dataset import build_sector_features
    try:
        frame, new_cols = build_sector_features(
            engine, symbols,
            start_date=start_date, end_date=end_date,
            base_cols=[],
        )
    except Exception as exc:
        LOGGER.warning("Sector panel indisponible : %s", exc)
        return pd.DataFrame(), []
    if frame is None or frame.empty:
        return pd.DataFrame(), []
    keep = [c for c in SECTOR_FEATURES if c in frame.columns]
    if not keep:
        return pd.DataFrame(), []
    return frame[["symbol", "date"] + keep], keep


def build_panel(
    engine: Any,
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    with_derivations: bool = True,
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    """Assemble le panel quotidien PIT des features de base + dérivées temporelles.

    ``with_derivations=False`` : ne calcule QUE les features de base (panel léger,
    pour les diagnostics de conditionnement).

    Returns:
        ``(panel, temporal_cols, meta)`` — ``panel`` indexé sur (date, symbol) du
        calendrier bars ; ``temporal_cols`` = toutes les colonnes dérivées (vide
        si ``with_derivations=False``) ; ``meta`` = couverture/âge des snapshots.
    """
    bars = load_bars_panel(engine, symbols, start_date, end_date)
    if bars.empty:
        raise RuntimeError("Aucune donnée bars.")
    # Calendrier quotidien par symbole = dates bars
    cal = bars[["symbol", "date"]].copy()

    panel = cal.merge(bars, on=["symbol", "date"], how="left")
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    available: list[str] = []

    # Momentum depuis bars (adj_close) — shift intra-symbole
    grp_adj = panel.groupby("symbol")["adj_close"]
    for mom, w in (("momentum_20", 20), ("momentum_60", 60)):
        panel[mom] = panel["adj_close"] / grp_adj.shift(w) - 1.0
        available.append(mom)

    # Score features (merge_asof backward, PIT + age) — par symbole
    scores = load_score_panel(engine, symbols, start_date, end_date)
    score_meta: dict[str, Any] = {}
    if not scores.empty:
        for c in SCORE_FEATURES:
            if c not in scores.columns:
                continue
            vals = pd.Series(np.nan, index=panel.index, dtype=float)
            age = pd.Series(np.nan, index=panel.index, dtype=float)
            for sym in panel["symbol"].unique():
                idx = panel.index[panel["symbol"] == sym]
                left = panel.loc[idx, ["date"]]
                ss = scores[(scores["symbol"] == sym) & scores[c].notna()][
                    ["snapshot_date", c]].sort_values("snapshot_date")
                if ss.empty:
                    continue
                m = pd.merge_asof(left, ss, left_on="date", right_on="snapshot_date",
                                  direction="backward")
                vals.loc[idx] = m[c].to_numpy()
                age.loc[idx] = (left["date"].to_numpy() - m["snapshot_date"].to_numpy()) \
                    .astype("timedelta64[D]").astype(float)
            panel[c] = vals
            panel[f"{c}__age"] = age
            available.append(c)
        age_cols = [f"{c}__age" for c in available if f"{c}__age" in panel.columns]
        if age_cols:
            score_meta["score_snapshot_age_days"] = {
                "median": float(panel[age_cols].stack().median()),
                "p90": float(panel[age_cols].stack().quantile(0.9)),
            }

    # Sector features (try/except)
    sector, sector_cols = load_sector_panel(engine, symbols, start_date, end_date)
    if not sector.empty:
        panel = panel.merge(sector, on=["symbol", "date"], how="left")
        available += [c for c in sector_cols if c in panel.columns]

    # Uniquement les features de base réellement présentes
    base_avail = [c for c in BASE_FEATURES if c in panel.columns]
    for c in BASE_FEATURES:
        if c not in base_avail:
            LOGGER.warning("Feature de base INDISPONIBLE (loggée, non inventée) : %s", c)

    temporal_cols: list[str] = []
    if not with_derivations:
        meta = {
            "base_available": base_avail,
            "score_snapshot_age_days": score_meta.get("score_snapshot_age_days", {}),
            "n_panel_rows": int(len(panel)),
        }
        return panel, temporal_cols, meta

    # Dérivées temporelles — TOUT est intra-symbole (transform / shift)
    for base in base_avail:
        s = panel[base].astype(float)
        grp = panel.groupby("symbol")[base]
        panel[f"{base}__t0"] = s
        for w in _LAG_WINDOWS:
            panel[f"{base}__lag_{w}"] = grp.shift(w)
        for w in _DELTA_WINDOWS:
            panel[f"{base}__delta_{w}"] = s - grp.shift(w)
        for w in _MEAN_WINDOWS:
            panel[f"{base}__mean_{w}"] = grp.transform(lambda x: x.rolling(w, min_periods=1).mean())
        for w in _SLOPE_WINDOWS:
            panel[f"{base}__slope_{w}"] = grp.transform(lambda x: _slope(x, w))
        for w in _STD_WINDOWS:
            panel[f"{base}__std_{w}"] = grp.transform(lambda x: x.rolling(w, min_periods=2).std())
        # Features signées : fraction de jours positifs + changements de signe
        d = s - grp.shift(1)                       # variation quotidienne (intra-symbole)
        pos = (d > 0).astype(float)
        for w in _SIGNED_WINDOWS:
            panel[f"{base}__pos_frac_{w}"] = pos.groupby(panel["symbol"]).transform(
                lambda x: x.rolling(w, min_periods=1).mean())
        flip = (d * d.groupby(panel["symbol"]).shift(1) < 0).astype(float)
        panel[f"{base}__sign_change_{_SIGN_CHANGE_WINDOW}"] = flip.groupby(panel["symbol"]).transform(
            lambda x: x.rolling(_SIGN_CHANGE_WINDOW, min_periods=1).mean())
        temporal_cols += _temporal_columns(base)

    meta = {
        "base_available": base_avail,
        "score_snapshot_age_days": score_meta.get("score_snapshot_age_days", {}),
        "n_panel_rows": int(len(panel)),
    }
    return panel, temporal_cols, meta


# ── Séparabilité (statique vs temporel) ──────────────────────────────────────

def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:
    s = series.astype(float)
    if s.nunique() < 2 or decile.nunique() < 2:
        return None
    try:
        c = s.corr(decile, method="spearman")
        return float(c) if np.isfinite(c) else None
    except Exception:
        return None


def _auc(series: pd.Series, decile: pd.Series, good: tuple = (6, 10), bad: tuple = (1, 5)) -> float | None:
    mask = decile.isin([*bad, *good])
    if mask.sum() < 2:
        return None
    y = np.where(decile[mask].isin(good), 1.0, 0.0)
    s = series[mask].astype(float).to_numpy()
    return roc_auc(y, s)


def _auc_d1_d10(series: pd.Series, decile: pd.Series) -> float | None:
    return _auc(series, decile, good=(10,), bad=(1,))


def _auc_amplitude(series: pd.Series, decile: pd.Series) -> float | None:
    mask = decile.isin([1, 10])
    if mask.sum() < 2:
        return None
    y = np.where(decile[mask].isin([10]), 1.0, 0.0)
    s = series[mask].astype(float).to_numpy()
    return roc_auc(y, s)


def run_separability(pool: pd.DataFrame, base_features: list[str], temporal_cols: list[str]) -> pd.DataFrame:
    """Mesure chaque feature temporelle vs sa version statique, dans le pool.

    Une ligne par (base_feature, temporal_feature) — y compris la ligne
    ``static`` (t0) de chaque base. Colonnes : voir docstring module.
    """
    dec = pool[DECILE_COL].astype(int)
    rows: list[dict[str, Any]] = []
    static_auc: dict[str, float] = {}

    for base in base_features:
        if base not in pool.columns:
            continue
        s0 = pool[base]
        a0 = _auc(s0, dec)
        if a0 is None:
            continue
        static_auc[base] = a0
        rows.append({
            "base_feature": base, "temporal_feature": f"{base}__t0 (statique)",
            "static_auc": a0, "temporal_auc": a0, "delta_auc": 0.0,
            "ic_decile": _ic_spearman(s0, dec),
            "auc_bad5_good5": a0,
            "auc_d1d3_d8d10": _auc(s0, dec, good=(8, 9, 10), bad=(1, 2, 3)),
            "auc_d1_d10": _auc_d1_d10(s0, dec),
            "dir_vs_amp": (a0 - _auc_amplitude(s0, dec)) if _auc_amplitude(s0, dec) is not None else None,
            "stable_folds": None, "total_folds": None,
            "coverage": float(s0.notna().mean()),
            "verdict": "",
        })

    for col in temporal_cols:
        if col not in pool.columns:
            continue
        base = col.split("__")[0]
        if base not in static_auc:
            continue
        s = pool[col]
        auc_d = _auc(s, dec)
        if auc_d is None:
            continue
        # stabilité du signe par fold WF
        stable = 0
        total = 0
        for fold, sub in pool.groupby("fold_start"):
            a_f = _auc(sub[col], sub[DECILE_COL].astype(int))
            if a_f is None:
                continue
            total += 1
            if (a_f > 0.5) == (auc_d > 0.5):
                stable += 1
        amp = _auc_amplitude(s, dec)
        rows.append({
            "base_feature": base, "temporal_feature": col,
            "static_auc": static_auc[base], "temporal_auc": auc_d,
            "delta_auc": auc_d - static_auc[base],
            "ic_decile": _ic_spearman(s, dec),
            "auc_bad5_good5": auc_d,
            "auc_d1d3_d8d10": _auc(s, dec, good=(8, 9, 10), bad=(1, 2, 3)),
            "auc_d1_d10": _auc_d1_d10(s, dec),
            "dir_vs_amp": (auc_d - amp) if amp is not None else None,
            "stable_folds": stable, "total_folds": total,
            "coverage": float(s.notna().mean()),
            "verdict": "",
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Verdict : direction claire > statique, stable, couverture suffisante,
    # direction > amplitude.
    def _verdict(r: pd.Series) -> str:
        if r["total_folds"] is None or r["total_folds"] == 0:
            return "coverage_insuffisante"
        if r["coverage"] < 0.5:
            return "coverage_insuffisante"
        stable_ok = r["stable_folds"] / r["total_folds"] >= 0.6
        dir_ok = (r["temporal_auc"] or 0) >= 0.53
        delta_ok = (r["delta_auc"] or 0) >= 0.015
        amp_ok = (r["dir_vs_amp"] is None) or (r["dir_vs_amp"] or 0) > 0
        if stable_ok and dir_ok and delta_ok and amp_ok:
            return "GO"
        if stable_ok and dir_ok and amp_ok:
            return "candidat_faible"
        return "NO-GO"

    out["verdict"] = out.apply(_verdict, axis=1)
    # Tri : stabilité (desc), puis delta_auc (desc), puis temporal_auc (desc)
    out["_stable_ratio"] = out["stable_folds"] / out["total_folds"].replace(0, np.nan)
    out = out.sort_values(
        ["_stable_ratio", "delta_auc", "temporal_auc"],
        ascending=[False, False, False], na_position="last",
    ).drop(columns=["_stable_ratio"]).reset_index(drop=True)
    return out


def format_report(out: pd.DataFrame, base_features: list[str]) -> str:
    lines = ["=== SÉPARABILITÉ STATIC vs TEMPORAL (pool Oracle TOP20%) ==="]
    lines.append(f"Features de base testées : {len(base_features)} — "
                 f"derivées temporelles : {len(out) - len(base_features)}")
    go = out[out["verdict"] == "GO"]
    cand = out[out["verdict"] == "candidat_faible"]
    lines.append(f"GO : {len(go)} | candidat_faible : {len(cand)} | NO-GO/autre : "
                 f"{len(out) - len(go) - len(cand)}")
    if not go.empty:
        lines.append("\n--- TOP features temporelles GO ---")
        cols = ["base_feature", "temporal_feature", "static_auc", "temporal_auc",
                "delta_auc", "ic_decile", "stable_folds", "total_folds", "coverage", "dir_vs_amp"]
        lines.append(go[cols].to_string(index=False))
    lines.append("\n--- TOP delta_auc (toutes) ---")
    top = out[out["temporal_feature"].str.contains("__t0") == False].head(15)
    lines.append(top[["base_feature", "temporal_feature", "static_auc", "temporal_auc",
                      "delta_auc", "stable_folds", "total_folds", "verdict"]].to_string(index=False))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité temporelle GlobalDirection.")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--oracle-run", default=None)
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--out", default="artifacts/global_direction_temporal_separability.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    engine = get_sqlalchemy_engine()
    pool = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                         pool_pct=args.pool_pct, oracle_run=args.oracle_run)
    if pool.empty:
        raise SystemExit("Pool Oracle vide.")
    symbols = list(pool["symbol"].unique())
    LOGGER.info("pool Oracle top%.0f%% : %d lignes, %d dates, %d symboles",
                args.pool_pct * 100, len(pool), pool["date"].nunique(), len(symbols))

    panel, temporal_cols, meta = build_panel(engine, symbols, args.start_date, args.end_date)
    base_avail = meta["base_available"]
    LOGGER.info("features de base disponibles : %s", base_avail)
    if not base_avail:
        raise SystemExit("Aucune feature de base disponible.")
    LOGGER.info("colonnes temporelles dérivées : %d", len(temporal_cols))

    age_cols_ok = [f"{c}__age" for c in base_avail if f"{c}__age" in panel.columns]
    # NB : on fusionne AUSSI les colonnes de base (statiques) — nécessaires à la
    # comparaison static vs temporal dans run_separability.
    merged = pool.merge(
        panel[["date", "symbol"] + base_avail + temporal_cols + age_cols_ok],
        on=["date", "symbol"], how="left",
    )
    merged = merged.drop_duplicates(subset=["date", "symbol"])

    if meta.get("score_snapshot_age_days"):
        LOGGER.info("Âge médian des snapshots scores : %s j (p90 %s j)",
                    meta["score_snapshot_age_days"].get("median"),
                    meta["score_snapshot_age_days"].get("p90"))

    result = run_separability(merged, base_avail, temporal_cols)
    if result.empty:
        raise SystemExit("Aucune métrique calculable.")
    result.to_csv(args.out, index=False)
    print(f"→ CSV : {args.out} ({len(result)} lignes)")
    print(format_report(result, base_avail))


if __name__ == "__main__":
    main()
