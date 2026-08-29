"""Chantier research-only — dip_temporal_pattern_feasibility (2026-08-27).

Étude de faisabilité : la trajectoire complète des features sur J-5...J
permet-elle de distinguer les bons DIP des mauvais DIP mieux que la valeur
statique à J (M0) ou les simples deltas (M1) ?

Périmètre STRICT (inchangé) :
- Setup N4/X2 gelé : global_rank_20 >= 0.90 pendant 4 séances consécutives
  ET ret_4 <= -2%. Aucun tuning N/X. Aucun changement PROD/risk/portfolio.
- Univers principal : DIP N4/X2 AND allow_new_entries == True à J
  (close_only / cash_only EXCLUS, tableau de contrôle séparé).
- Batch Global Rank explicite : model-factory-20260811223551-ef2cd0.
- Toutes les features PIT à chaque séance (aucun usage de données > J).

Représentations comparées :
- M0  snapshot statique          : f[J]
- M1  snapshot + deltas          : f[J] + delta_3 + delta_5
- M2  séquence aplatie           : f[J-5] ... f[J]  (6 lags)
- M3  séquence relative          : f[J-5] + (f[t]-f[J-5]) pour t=J-4..J

Modèles : LogisticRegression L2 (C=0.1) sur M0..M3, nested/WF chronologique
avec purge/embargo H20. LightGBM conservateur (T1) uniquement si gain OOS clair.

Usage (étapes, pour robustesse) :
    python -m modelFactory.dip_research.dip_temporal_pattern_feasibility --stage events
    python -m modelFactory.dip_research.dip_temporal_pattern_feasibility --stage panel
    python -m modelFactory.dip_research.dip_temporal_pattern_feasibility --stage coverage
    python -m modelFactory.dip_research.dip_temporal_pattern_feasibility --stage models
    python -m modelFactory.dip_research.dip_temporal_pattern_feasibility --stage report
Ajouter ``--smoke`` pour un test rapide (sous-ensemble minuscule).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as _sstats

from modelFactory.dip_research import dip_context_pattern_analysis as _dc
from modelFactory.dip_research.dip_context_pattern_analysis import (
    _auc_rank,
    _compute_bars_features,
    _compute_breadth_ranks,
    _compute_sector_features,
    assert_events,
    build_dip_events,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "dip_temporal"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
ANAL_DIR = ARTIFACTS_DIR
LOGGER = None  # pas de logger : on utilise _plog (fichier utf-8)

# ── Setup gelé (réutilisé du chantier précédent) ──
BATCH_ID = _dc.BATCH_ID
RANK_COL = _dc.RANK_COL
HORIZON = _dc.HORIZON
START = _dc.START
END = _dc.END

# Fenêtres temporelles (panel) — plus larges que le chantier précédent pour
# garantir l'historique 252j (pos_52w) / 200j (sma200) des événements 2022+.
T_BARS_START = "2020-06-01"
T_BARS_END = "2026-03-01"
T_UNI_BARS_START = "2021-06-01"   # univers breadth (sma50/sma200 suffisent)

# Trajectoire : J-5 ... J (6 observations)
N_LAG = 5
LAGS = list(range(N_LAG, -1, -1))  # [5,4,3,2,1,0] (0 = J)

# ── Seuils / paramètres de l'étude ──
COVERAGE_GATE = 0.50        # % séquences complètes minimum sinon NO-GO DATA COVERAGE
MAX_FEATURES = 12           # dimensions de base (<= 12)
CORR_DROP = 0.80            # seuil de redondance |corr| (un représentant/cluster)
N_FOLDS = 5                 # folds chronologiques
PURGE_DAYS = 30             # purge/embargo compatible H20 (≈ 20 séances + buffer)
LR_C = 0.1                  # régularisation L2 fixée (pas de sweep massif)
N_PERM = 300                # permutations (pipeline complet) ; 30 en smoke
GAIN_MIN = 0.02             # gain AUC absolu requis (L2/L3 vs L0/L1)
MIN_TRAIN = 200             # taille minimale de train par fold

# ── Dimensions candidates (priorité du chantier, section 3) ──
TEMP_CANDIDATES: list[tuple[str, str]] = [
    ("pb_ratio", "fundamentals"),
    ("pos_52w", "position/range"),
    ("dist_52w_high", "position/range"),
    ("dist_52w_low", "position/range"),
    ("ret60", "momentum"),
    ("dist_sma50", "distance-SMA"),
    ("dist_sma100", "distance-SMA"),
    ("sector_breadth", "sector"),
    ("sector_ret20", "sector"),
    ("breadth_above_sma50", "breadth/regime"),
    ("spy_dist_sma200", "market-relative"),
    ("vix", "macro"),
    ("ten_y", "macro"),
    ("yield_10y_5d_pct", "macro"),
    ("atr14_pct", "volatility"),
    ("vol_z20", "volume"),
]
PANEL_COLS = [f for f, _ in TEMP_CANDIDATES]

# ── Descripteurs de forme (section 8, définitions fixes) ──
SHAPE_DESCRIPTORS = [
    "slope_5", "curvature_5", "max_drawdown_in_feature", "max_rebound_in_feature",
    "n_up_steps", "n_down_steps", "monotonicity_ratio", "last2_vs_first2",
]


def _quiet() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _plog(msg: str) -> None:
    with open(ARTIFACTS_DIR / "run.log", "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg, flush=True)


# ═══════════════════════════════════════════════════════════════════════════
# STAGE EVENTS — événements DIP N4/X2 (réutilise le chantier précédent)
# ═══════════════════════════════════════════════════════════════════════════

def run_events(engine: Any, *, smoke: bool = False) -> None:
    events = build_dip_events(engine)
    assert_events(events)
    events.to_csv(ARTIFACTS_DIR / "events.csv", index=False)
    _plog(f"events sauvegardés: {ARTIFACTS_DIR / 'events.csv'} ({len(events)} rows)")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE PANEL — panneau quotidien PIT + extraction des fenêtres J-5..J
# ═══════════════════════════════════════════════════════════════════════════

def _load_market_features(engine: Any, bs: str, be: str, uni_start: str, top_n: int) -> pd.DataFrame:
    """Contexte marché + breadth sur la fenêtre [uni_start, be] (PIT par date)."""
    # Monkeypatch temporaire des fenêtres du module précédent (constantes lues
    # à l'appel) puis restauration.
    _s0, _b0, _e0 = _dc.START, _dc._BARS_START, _dc._BARS_END
    try:
        _dc.START = uni_start
        _dc._BARS_START = bs
        _dc._BARS_END = be
        mkt = _dc._compute_market_features(engine)
    finally:
        _dc.START, _dc._BARS_START, _dc._BARS_END = _s0, _b0, _e0
    breadth, _rt, uni = _compute_breadth_ranks(engine, top_n, uni_start, be)
    mkt = mkt.merge(breadth, on="date", how="left")
    return mkt, uni


def build_daily_panel(engine: Any, symbols: list[str], *, smoke: bool = False) -> pd.DataFrame:
    """Panneau quotidien (date, symbol) des features candidates, PIT.

    Fenêtres toutes trailing (rolling min_periods) — aucun usage de données > J.
    """
    if smoke:
        bs, be, uni_start, top_n = "2023-01-01", "2024-10-01", "2022-06-01", 200
    else:
        bs, be, uni_start, top_n = T_BARS_START, T_BARS_END, T_UNI_BARS_START, 3000
    symbols = [s for s in symbols if s and str(s) != "nan"]
    if not symbols:
        return pd.DataFrame()

    # ── Bars des symboles DIP (fenêtre large pour 252j/200j) ──
    _in = ",".join(["%s"] * len(symbols))
    bars = pd.read_sql(
        f"SELECT symbol, date, open, high, low, close, adj_close, volume FROM stock_bars_daily "
        f"WHERE data_source='eodhd_eod' AND symbol IN ({_in}) AND date BETWEEN %s AND %s",
        engine, params=tuple(symbols + [bs, be]),
    )
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars[bars["symbol"].isin(symbols)]
    bars = bars.dropna(subset=["date", "symbol", "adj_close"]).drop_duplicates(subset=["symbol", "date"])
    _plog(f"panel bars DIP: {len(bars)} lignes, {bars['symbol'].nunique()} symboles")
    feat = _compute_bars_features(bars)
    _plog(f"features bars OK ({feat.shape[0]} lignes)")

    # ── Contexte marché + breadth (par date) ──
    mkt, uni = _load_market_features(engine, bs, be, uni_start, top_n)
    feat = feat.merge(mkt, on="date", how="left")
    _plog("contexte marché + breadth OK")

    # ── Secteur (par (sector_name, date)) ──
    meta_sec, sec, svs = _compute_sector_features(engine, uni)
    feat = feat.merge(meta_sec, on="symbol", how="left")
    feat = feat.merge(svs, on=["date", "symbol"], how="left")
    feat = feat.merge(
        sec[["date", "sector_name", "sector_ret20", "sector_breadth"]],
        on=["date", "sector_name"], how="left",
    )
    _plog("secteur OK")

    # ── Fondamentaux PIT (asof par symbole, direction backward) ──
    fund = pd.read_sql(
        "SELECT symbol, trade_date, pb_ratio FROM stock_fundamentals_daily "
        "WHERE trade_date BETWEEN %s AND %s",
        engine, params=(uni_start, be),
    )
    fund["trade_date"] = pd.to_datetime(fund["trade_date"]).dt.normalize()
    fund["symbol"] = fund["symbol"].astype(str).str.upper()
    fund = fund.dropna(subset=["pb_ratio"]).rename(columns={"trade_date": "fdate"})
    if len(fund):
        feat = feat.sort_values("date").reset_index(drop=True)
        feat = pd.merge_asof(
            feat, fund.sort_values("fdate"),
            left_on="date", right_on="fdate", by="symbol", direction="backward",
        ).drop(columns=["fdate"], errors="ignore")
    else:
        feat["pb_ratio"] = np.nan
    _plog("fondamentaux PIT (asof) OK")

    # ── Réduire aux colonnes candidates ──
    keep = ["symbol", "date"] + [c for c in PANEL_COLS if c in feat.columns]
    feat = feat[keep].replace([np.inf, -np.inf], np.nan)
    return feat.sort_values(["symbol", "date"]).reset_index(drop=True)


def _shape_metrics(x: np.ndarray) -> dict[str, float]:
    """Descripteurs de forme simples sur la séquence x[0..5] (section 8)."""
    x = np.asarray(x, dtype=float)
    out: dict[str, float] = {}
    if np.isnan(x).any() or len(x) < 6:
        for d in SHAPE_DESCRIPTORS:
            out[d] = np.nan
        return out
    out["slope_5"] = (x[5] - x[0]) / 5.0
    out["curvature_5"] = x[5] - 2.0 * x[3] + x[1]  # 2e différence finie (pas 2)
    rmax = np.maximum.accumulate(x)
    rmin = np.minimum.accumulate(x)
    out["max_drawdown_in_feature"] = float(np.max(rmax - x))
    out["max_rebound_in_feature"] = float(np.max(x - rmin))
    up = int((np.diff(x) > 0).sum())
    down = int((np.diff(x) < 0).sum())
    out["n_up_steps"] = up
    out["n_down_steps"] = down
    out["monotonicity_ratio"] = max(up, down) / 5.0
    out["last2_vs_first2"] = float(np.mean(x[4:6]) - np.mean(x[0:2]))
    return out


def run_panel(engine: Any, *, smoke: bool = False) -> None:
    if smoke:
        _plog("== SMOKE PANEL ==")
    events = pd.read_csv(ARTIFACTS_DIR / "events.csv", parse_dates=["signal_date"])
    events["symbol"] = events["symbol"].astype(str).str.upper()
    if smoke:
        _win = events[(events["signal_date"] >= "2024-06-01") & (events["signal_date"] <= "2024-09-01")]
        events = _win.sample(n=min(40, len(_win)), random_state=0) if len(_win) else events.head(12)
    symbols = sorted(events["symbol"].unique())
    _plog(f"panel : {len(events)} événements, {len(symbols)} symboles")
    panel = build_daily_panel(engine, symbols, smoke=smoke)
    if panel.empty:
        raise RuntimeError("panel vide")

    # ── Extraction des fenêtres J-5..J par événement (séances de trading) ──
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    panel["_pos"] = panel.groupby("symbol").cumcount()
    pos_map = dict(zip(zip(panel["symbol"], panel["date"]), panel["_pos"]))

    cols = [f for f in PANEL_COLS if f in panel.columns]
    ev_cols = [c for c in ["signal_date", "symbol", "global_rank_20", "ret_4",
                           "future_return_H20", "future_return_oracle", "oracle_decile"]
               if c in events.columns]
    rows: list[dict[str, Any]] = []
    n_incomplete = 0
    for _, e in events.iterrows():
        sym, j = str(e["symbol"]), pd.Timestamp(e["signal_date"]).normalize()
        pos = pos_map.get((sym, j))
        if pos is None or pos < N_LAG:
            n_incomplete += 1
            continue
        win = panel.iloc[pos - N_LAG:pos + 1]
        if len(win) != 6:
            n_incomplete += 1
            continue
        r: dict[str, Any] = {c: e[c] for c in ev_cols}
        r["n_seq_obs"] = 6
        r["seq_complete"] = True
        for f in cols:
            vals = win[f].to_numpy(dtype=float)
            # colonnes f_lagK (K = décalage : lag0 = J, lag5 = J-5)
            for k in range(N_LAG, -1, -1):
                r[f"{f}_lag{k}"] = vals[N_LAG - k]
            r[f"{f}_delta_3"] = vals[-1] - vals[-4] if not np.isnan(vals).any() else np.nan
            r[f"{f}_delta_5"] = vals[-1] - vals[0] if not np.isnan(vals).any() else np.nan
            # descripteurs de forme
            for d, v in _shape_metrics(vals).items():
                r[f"{f}__{d}"] = v
        rows.append(r)
    out = pd.DataFrame(rows)
    _plog(f"fenêtres extraites: {len(out)} (incomplètes/ignorées: {n_incomplete})")
    # complétude : séquence complète uniquement si les 6 obs des features sont là
    for f in cols:
        lag_cols = [f"{f}_lag{k}" for k in LAGS]
        out[f"{f}_seq_complete"] = out[lag_cols].notna().all(axis=1)
    out["seq_complete"] = out[[f"{f}_seq_complete" for f in cols]].all(axis=1)
    out.to_csv(ARTIFACTS_DIR / "temporal_features.csv", index=False)
    _plog(f"saved: temporal_features.csv ({len(out)} lignes, {out.shape[1]} cols)")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE COVERAGE — audit de couverture temporelle (section 4) + sélection
# ═══════════════════════════════════════════════════════════════════════════

def _load_temporal(engine: Any) -> pd.DataFrame:
    df = pd.read_csv(ARTIFACTS_DIR / "temporal_features.csv", parse_dates=["signal_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.replace([np.inf, -np.inf], np.nan)
    return df


def _prod_universe(engine: Any, df: pd.DataFrame) -> pd.DataFrame:
    """Univers PROD : allow_new_entries == True à J (exclut close_only/cash_only)."""
    mac = pd.read_sql(
        "SELECT trade_date, mode, allow_new_entries FROM stock_macro_indicators_daily", engine
    )
    mac["trade_date"] = pd.to_datetime(mac["trade_date"]).dt.normalize()
    mac = mac.drop_duplicates("trade_date")
    df = df.copy()
    df["regime_mode"] = df["signal_date"].map(dict(zip(mac["trade_date"], mac["mode"])))
    df["allow_new_entries"] = df["signal_date"].map(dict(zip(mac["trade_date"], mac["allow_new_entries"])))
    df["allow_new_entries"] = df["allow_new_entries"].where(
        df["allow_new_entries"].notna(),
        (~df["regime_mode"].isin(["close_only", "cash_only"])).astype(int),
    ).astype(bool)
    return df


def _select_features(df: pd.DataFrame) -> list[str]:
    """Sélection <= 12 dimensions : priorité du chantier, un représentant par
    cluster fortement corrélé (|corr| >= CORR_DROP sur le snapshot J = lag0)."""
    lag0 = {f: f"{f}_lag0" for f, _ in TEMP_CANDIDATES}
    candidates = [f for f, _ in TEMP_CANDIDATES if lag0[f] in df.columns]
    cov = df[[lag0[f] for f in candidates]].notna().mean()
    # priorité : ordre du chantier ; coverage J >= COVERAGE_GATE requise
    kept: list[str] = []
    for f in candidates:
        if len(kept) >= MAX_FEATURES:
            break
        if cov[lag0[f]] < COVERAGE_GATE:
            _plog(f"  - {f}: coverage J={cov[lag0[f]]:.1%} < {COVERAGE_GATE:.0%} → exclu")
            continue
        if not kept:
            kept.append(f)
            continue
        # redondance : |corr| avec les features déjà gardées (snapshot J)
        cols = [lag0[g] for g in kept] + [lag0[f]]
        vals = df[cols].replace([np.inf, -np.inf], np.nan)
        corr = vals.corr().abs().loc[[lag0[g] for g in kept], lag0[f]]
        if corr.max() >= CORR_DROP:
            _plog(f"  - {f}: corr max {corr.max():.2f} >= {CORR_DROP:.2f} → redondant, exclu")
            continue
        kept.append(f)
    _plog(f"sélection finale: {len(kept)} dimensions {kept}")
    return kept


def run_coverage(engine: Any, *, smoke: bool = False) -> list[str]:
    if smoke:
        _plog("== SMOKE COVERAGE ==")
    df = _load_temporal(engine)
    df = _prod_universe(engine, df)
    # tableau de contrôle des exclus
    ex = df[~df["allow_new_entries"]].copy()
    if len(ex):
        ctl = []
        for reg, g in ex.groupby("regime_mode"):
            f = g["future_return_H20"].dropna()
            srt = f.sort_values()
            n5 = max(1, int(len(f) * 0.05))
            ctl.append({"regime": reg, "n_DIP": len(g), "mean_H20": f.mean() if len(f) else np.nan,
                        "P_gt0": (f > 0).mean() if len(f) else np.nan,
                        "BAD5": srt.head(n5).mean() if len(f) else np.nan,
                        "GOOD5": srt.tail(n5).mean() if len(f) else np.nan})
        pd.DataFrame(ctl).to_csv(ARTIFACTS_DIR / "temporal_regime_control.csv", index=False)
        _plog(f"contrôle régimes exclus: {len(ctl)} lignes")
    main = df[df["allow_new_entries"]].reset_index(drop=True)
    _plog(f"univers PROD (allow_new_entries=True): {len(main)} événements")

    # ── Audit de couverture (section 4) ──
    n_total = len(main)
    rows = []
    for f, _fam in TEMP_CANDIDATES:
        if f"{f}_lag0" not in main.columns:
            continue
        row = {"feature": f}
        for k in LAGS:
            row[f"coverage_J{-k}" if k else "coverage_J"] = main[f"{f}_lag{k}"].notna().mean()
        row["complete_sequence_rate"] = main[f"{f}_seq_complete"].mean()
        row["n_complete"] = int(main[f"{f}_seq_complete"].sum())
        rows.append(row)
    cov_df = pd.DataFrame(rows)
    cov_df["complete_sequence_rate"] = cov_df["complete_sequence_rate"].astype(float)
    cov_df["coverage_J"] = cov_df["coverage_J"].astype(float)
    cov_df = cov_df.sort_values("complete_sequence_rate", ascending=False)
    cov_df.to_csv(ARTIFACTS_DIR / "temporal_coverage.csv", index=False)

    n_complete_all = int(main["seq_complete"].sum())
    pct_complete = n_complete_all / n_total if n_total else 0.0
    _plog(f"COVERAGE: n_events_total={n_total} n_complete_sequences={n_complete_all} "
          f"pct_complete={pct_complete:.1%}")
    _plog(f"saved: temporal_coverage.csv")

    # ── Sélection des dimensions (section 3) ──
    feats = _select_features(main)
    inv = pd.DataFrame([{"feature": f, "family": dict(TEMP_CANDIDATES).get(f, "?"),
                         "coverage_J": float(main[f"{f}_lag0"].notna().mean()),
                         "complete_sequence_rate": float(main[f"{f}_seq_complete"].mean())}
                        for f in feats])
    inv.to_csv(ARTIFACTS_DIR / "temporal_feature_inventory.csv", index=False)
    _plog(f"saved: temporal_feature_inventory.csv ({len(feats)} features)")

    # ── Gate de couverture (section 4) ──
    if n_complete_all == 0:
        _plog("COVERAGE: aucune séquence complète → NO-GO DATA COVERAGE")
        raise SystemExit(1)
    _plog("COVERAGE OK" if pct_complete >= COVERAGE_GATE else
          f"COVERAGE FAIBLE ({pct_complete:.1%} < {COVERAGE_GATE:.0%}) — décision à voir avec la sélection")
    return feats


# ═══════════════════════════════════════════════════════════════════════════
# STAGE MODELS — trajectoires, formes, M0..M3, nested/WF, métriques, permutation
# ═══════════════════════════════════════════════════════════════════════════

def _build_reps(seq: pd.DataFrame, feats: list[str]) -> dict[str, pd.DataFrame]:
    """Construit M0/M1/M2/M3 à partir des colonnes f_lagK (K=0..5)."""
    reps: dict[str, pd.DataFrame] = {}
    # M0 — snapshot statique f[J]
    M0 = pd.DataFrame({f"{f}__J": seq[f"{f}_lag0"] for f in feats})
    reps["M0"] = M0
    # M1 — snapshot + delta_3 + delta_5
    M1 = pd.DataFrame()
    for f in feats:
        M1[f"{f}__J"] = seq[f"{f}_lag0"]
        M1[f"{f}__d3"] = seq[f"{f}_delta_3"]
        M1[f"{f}__d5"] = seq[f"{f}_delta_5"]
    reps["M1"] = M1
    # M2 — séquence aplatie (ordre chronologique J-5..J)
    M2 = pd.DataFrame()
    for f in feats:
        for k in LAGS:
            M2[f"{f}__lag{k}"] = seq[f"{f}_lag{k}"]
    reps["M2"] = M2
    # M3 — séquence relative au point de départ : niveau J-5 + chemins f[t]-f[J-5]
    M3 = pd.DataFrame()
    for f in feats:
        M3[f"{f}__lvl"] = seq[f"{f}_lag5"]
        for k in range(N_LAG - 1, -1, -1):
            M3[f"{f}__p{k}"] = seq[f"{f}_lag{k}"] - seq[f"{f}_lag5"]
    reps["M3"] = M3
    return reps


def _chrono_folds(dates: np.ndarray, n_folds: int = N_FOLDS, purge_days: int = PURGE_DAYS,
                  min_train: int = MIN_TRAIN):
    """Folds chronologiques strictement croissants (expanding train) + purge.

    Train = tous les événements avant le fold (purge de `purge_days` avant la
    frontière pour ne pas contaminer via les labels H20). Les folds sans train
    suffisant (début de période) sont ignorés.
    """
    order = np.argsort(dates, kind="stable")
    n = len(dates)
    edges = [int(round(n * k / n_folds)) for k in range(1, n_folds)]
    folds = []
    start = 0
    for e in edges + [n]:
        folds.append(order[start:e])
        start = e
    out = []
    for vi, v_idx in enumerate(folds):
        v_start = dates[v_idx].min()
        tr = np.concatenate(folds[:vi]) if vi > 0 else np.array([], dtype=int)
        if len(tr) < min_train or len(v_idx) < 30:
            continue
        keep = np.array([i for i in tr if (v_start - dates[i]).astype("timedelta64[D]").astype(int) > purge_days])
        if len(keep) < min_train:
            continue
        out.append((keep, np.asarray(v_idx, dtype=int)))
    return out


def _fit_predict(rep_train: pd.DataFrame, rep_val: pd.DataFrame, y_tr: np.ndarray,
                 model: str = "lr", rng: np.random.Generator | None = None) -> np.ndarray:
    """Fit scaler/imputer sur TRAIN uniquement, prédit sur VALIDATION."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    Xtr = rep_train.to_numpy(dtype=float)
    Xte = rep_val.to_numpy(dtype=float)
    imp = SimpleImputer(strategy="median")
    sc = StandardScaler()
    Xtr = sc.fit_transform(imp.fit_transform(Xtr))
    Xte = sc.transform(imp.transform(Xte))
    if model == "lr":
        clf = LogisticRegression(C=LR_C, max_iter=2000)
        clf.fit(Xtr, y_tr)
        return clf.predict_proba(Xte)[:, 1], clf
    # LightGBM conservateur (T1)
    import lightgbm as lgb
    clf = lgb.LGBMClassifier(
        n_estimators=300, learning_rate=0.03, max_depth=2, num_leaves=7,
        min_child_samples=100, reg_alpha=1.0, reg_lambda=1.0, colsample_bytree=0.7,
        subsample=0.8, subsample_freq=1, random_state=0, verbose=-1,
    )
    clf.fit(Xtr, y_tr)
    return clf.predict_proba(Xte)[:, 1], clf


def _fold_metrics(y_val: np.ndarray, score: np.ndarray, fwd_val: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import average_precision_score, brier_score_loss
    yv = np.asarray(y_val, dtype=int)
    out = {"auc": _auc_rank(yv, score)}
    out["pr_auc"] = float(average_precision_score(yv, score)) if len(np.unique(yv)) > 1 else np.nan
    out["brier"] = float(brier_score_loss(yv, score))
    ok = ~np.isnan(fwd_val)
    if ok.sum() >= 30:
        out["ic"] = float(_sstats.spearmanr(score[ok], fwd_val[ok]).statistic)
    else:
        out["ic"] = np.nan
    return out


def _summarize(aucs: list[float]) -> dict[str, float]:
    a = np.asarray([x for x in aucs if not np.isnan(x)], dtype=float)
    if len(a) == 0:
        return {"mean": np.nan, "median": np.nan, "std": np.nan, "worst": np.nan,
                "n_folds_gt_0.5": 0, "n_folds": 0}
    return {
        "mean": float(a.mean()), "median": float(np.median(a)), "std": float(a.std(ddof=1)),
        "worst": float(a.min()), "n_folds_gt_0.5": int((a > 0.5).sum()), "n_folds": int(len(a)),
    }


def run_models(engine: Any, *, smoke: bool = False) -> None:
    if smoke:
        _plog("== SMOKE MODELS ==")
    n_perm = 30 if smoke else N_PERM
    df = _load_temporal(engine)
    df = _prod_universe(engine, df)
    main = df[df["allow_new_entries"]].reset_index(drop=True)
    if len(main) == 0:
        _plog("univers PROD vide — NO-GO DATA COVERAGE")
        return
    min_train = 30 if smoke else MIN_TRAIN
    feats = pd.read_csv(ARTIFACTS_DIR / "temporal_feature_inventory.csv")["feature"].tolist()
    if not feats:
        feats = _select_features(main)
    _plog(f"modèles sur {len(feats)} dimensions: {feats}")

    # ── Sous-ensemble : séquences complètes sur les features sélectionnées ──
    lag_cols = [f"{f}_lag{k}" for f in feats for k in LAGS]
    complete = main[lag_cols].notna().all(axis=1)
    seq = main[complete].reset_index(drop=True)
    _plog(f"séquences complètes (features retenues): {len(seq)} / {len(main)} "
          f"({len(seq)/len(main):.1%})")
    if len(seq) == 0:
        _plog("aucune séquence complète sur les features retenues — NO-GO DATA COVERAGE")
        return
    if len(seq) < min_train:
        _plog(f"trop peu de séquences complètes ({len(seq)}) — modèles non significatifs")
        return

    fwd = seq["future_return_H20"]
    lbl = fwd.notna()
    yA = (fwd[lbl] > 0).astype(int).to_numpy()
    # Target B : GOOD=D8-10 vs BAD=D1-3 (exclut D4-7)
    mB = seq["oracle_decile"].isin([1, 2, 3, 8, 9, 10]) & seq["future_return_H20"].notna()
    yB = (seq.loc[mB, "oracle_decile"] >= 8).astype(int).to_numpy()

    reps = _build_reps(seq, feats)
    _plog(f"représentations: " + ", ".join(f"{k}={v.shape[1]} inputs" for k, v in reps.items()))

    # ── Folds chronologiques + purge ──
    dates = seq["signal_date"].to_numpy()
    folds = _chrono_folds(dates, min_train=min_train)
    _plog(f"{len(folds)} folds utilisables (chrono + purge {PURGE_DAYS}j)")

    # ── Trajectoires moyennes WIN vs LOSS / GOOD vs BAD (section 7) ──
    paths_rows: list[dict[str, Any]] = []
    for f in feats:
        w = fwd > 0
        l = fwd <= 0
        vg = seq["oracle_decile"].isin([8, 9, 10])
        vb = seq["oracle_decile"].isin([1, 2, 3])
        row = {"feature": f}
        for k in LAGS:
            c = f"{f}_lag{k}"
            row[f"win_mean_J{-k}" if k else "win_mean_J"] = seq.loc[w, c].mean()
            row[f"loss_mean_J{-k}" if k else "loss_mean_J"] = seq.loc[l, c].mean()
            row[f"good_mean_J{-k}" if k else "good_mean_J"] = seq.loc[vg, c].mean()
            row[f"bad_mean_J{-k}" if k else "bad_mean_J"] = seq.loc[vb, c].mean()
            row[f"win_std_J{-k}" if k else "win_std_J"] = seq.loc[w, c].std()
            row[f"loss_std_J{-k}" if k else "loss_std_J"] = seq.loc[l, c].std()
        # divergence progressive : diff W-L à J-5 vs J
        row["divergence_start"] = seq.loc[w, f"{f}_lag5"].mean() - seq.loc[l, f"{f}_lag5"].mean()
        row["divergence_end"] = seq.loc[w, f"{f}_lag0"].mean() - seq.loc[l, f"{f}_lag0"].mean()
        row["divergence_growth"] = row["divergence_end"] - row["divergence_start"]
        paths_rows.append(row)
    paths = pd.DataFrame(paths_rows)
    paths.to_csv(ARTIFACTS_DIR / "temporal_paths_good_bad.csv", index=False)
    _plog("trajectoires moyennes écrites")

    # ── Métriques de forme (section 8) : AUC de chaque descripteur ──
    shape_rows = []
    for f in feats:
        for d in SHAPE_DESCRIPTORS:
            c = f"{f}__{d}"
            if c not in seq.columns:
                continue
            s = seq.loc[lbl, c]
            ok = s.notna()
            if ok.sum() < 100:
                continue
            auc = _auc_rank(yA[ok], s[ok].to_numpy(dtype=float))
            shape_rows.append({"feature": f, "descriptor": d, "auc_win_loss": auc,
                               "dir_auc": max(auc, 1 - auc), "coverage": float(ok.mean())})
    shape_df = pd.DataFrame(shape_rows)
    if not shape_df.empty:
        shape_df = shape_df.sort_values("dir_auc", ascending=False)
    shape_df.to_csv(ARTIFACTS_DIR / "temporal_shape_features.csv", index=False)
    _plog(f"métriques de forme écrites ({len(shape_df)})")

    # ── Boucle modèles M0..M3 (+T1 conditionnel) sur Target A ──
    model_names = ["L0", "L1", "L2", "L3"]
    rep_keys = ["M0", "M1", "M2", "M3"]
    fold_rows: list[dict[str, Any]] = []
    oof: dict[str, np.ndarray] = {}
    coef_store: dict[str, list[np.ndarray]] = {m: [] for m in model_names}
    # Alignement Target A : yA_aligned[i] = label H20>0 si dispo, sinon NaN.
    yA_aligned = np.full(len(seq), np.nan)
    yA_aligned[lbl.to_numpy()] = yA
    for rep, mn in zip(rep_keys, model_names):
        Xrep = reps[rep]
        aucs, pr_aucs, briers, ics = [], [], [], []
        oof_scores = np.full(len(seq), np.nan)
        for tr, va in folds:
            # filtrer les lignes sans label (NaN) dans le fold
            tr_ok = tr[~np.isnan(yA_aligned[tr])]
            va_ok = va[~np.isnan(yA_aligned[va])]
            if len(tr_ok) < min_train or len(va_ok) < 30:
                continue
            y_tr = yA_aligned[tr_ok].astype(int)
            y_va = yA_aligned[va_ok].astype(int)
            score, clf = _fit_predict(Xrep.iloc[tr_ok], Xrep.iloc[va_ok], y_tr, model="lr")
            oof_scores[va_ok] = score
            met = _fold_metrics(y_va, score, fwd.to_numpy()[va_ok])
            aucs.append(met["auc"]); pr_aucs.append(met["pr_auc"])
            briers.append(met["brier"]); ics.append(met["ic"])
            # coefficients standardisés (scaler déjà appliqué) pour M3/M2
            if mn in ("L2", "L3"):
                coef_store[mn].append(clf.coef_[0])
        fold_rows.append({
            "model": mn, "representation": rep,
            **{f"auc_{i}": a for i, a in enumerate(aucs)},
            "auc_mean": float(np.mean(aucs)) if aucs else np.nan,
            "auc_median": float(np.median(aucs)) if aucs else np.nan,
            "auc_std": float(np.std(aucs)) if len(aucs) > 1 else np.nan,
            "auc_worst": float(np.min(aucs)) if aucs else np.nan,
            "n_folds_gt_0.5": int(sum(a > 0.5 for a in aucs)), "n_folds": len(aucs),
            "pr_auc_mean": float(np.nanmean(pr_aucs)) if pr_aucs else np.nan,
            "brier_mean": float(np.nanmean(briers)) if briers else np.nan,
            "ic_mean": float(np.nanmean(ics)) if ics else np.nan,
            "auc_oof": _auc_rank(yA_aligned[~np.isnan(oof_scores)].astype(int), oof_scores[~np.isnan(oof_scores)]),
            "pr_auc_oof": _pr_auc_score(yA_aligned[~np.isnan(oof_scores)].astype(int), oof_scores[~np.isnan(oof_scores)]),
        })
        oof[mn] = oof_scores
        _plog(f"{mn} ({rep}): folds AUC {[round(a,3) for a in aucs]} "
              f"OOF={fold_rows[-1]['auc_oof']:.4f}")
    fold_df = pd.DataFrame(fold_rows)
    fold_df.to_csv(ARTIFACTS_DIR / "temporal_fold_metrics.csv", index=False)

    # ── Target B (AUC par modèle, OOF) — ne pas mélanger A et B ──
    b_rows = []
    for rep, mn in zip(rep_keys, model_names):
        # indices B au sein de seq
        b_idx = np.where(mB.to_numpy())[0]
        # OOF score aux indices B
        s = oof[mn][b_idx]
        yb = yB
        ok = ~np.isnan(s)
        b_rows.append({"model": mn, "auc_oof_targetB": _auc_rank(yb[ok], s[ok]) if ok.sum() >= 30 else np.nan,
                       "n": int(ok.sum())})
    pd.DataFrame(b_rows).to_csv(ARTIFACTS_DIR / "temporal_targetB.csv", index=False)

    # ── Test central de faisabilité (section 14) ──
    auc_oof = {r["model"]: r["auc_oof"] for _, r in fold_df.iterrows()}
    best_static = max(auc_oof.get("L0", np.nan), auc_oof.get("L1", np.nan))
    seq_models = {m: auc_oof.get(m, np.nan) for m in ("L2", "L3")}
    best_seq_m = max(seq_models, key=lambda m: seq_models[m] if not np.isnan(seq_models[m]) else -1)
    best_seq = seq_models[best_seq_m]
    gain = best_seq - best_static if not (np.isnan(best_seq) or np.isnan(best_static)) else np.nan
    _plog(f"TEST CENTRAL: L0={auc_oof.get('L0'):.4f} L1={auc_oof.get('L1'):.4f} "
          f"L2={auc_oof.get('L2'):.4f} L3={auc_oof.get('L3'):.4f} → best_seq({best_seq_m})={best_seq:.4f} "
          f"gain vs static={gain:.4f}")

    # ── OOF predictions (section 15) ──
    oof_df = seq[["signal_date", "symbol", "future_return_H20", "oracle_decile"]].copy()
    for m in model_names:
        oof_df[f"score_{m}"] = oof[m]
    oof_df.to_csv(ARTIFACTS_DIR / "temporal_oof_predictions.csv", index=False)
    _plog("OOF predictions écrites")

    # ── Quintiles du score (section 15) ──
    s_oom = oof[best_seq_m]
    ok = ~np.isnan(s_oom) & fwd.notna().to_numpy()
    quint_rows = []
    if ok.sum() >= 100:
        sc = s_oom[ok]
        fv_all = fwd.to_numpy()[ok]
        d_all = seq.loc[ok, "oracle_decile"].to_numpy()
        try:
            q = pd.qcut(pd.Series(sc), 5, labels=False, duplicates="drop").to_numpy()
        except ValueError as _e:
            _plog(f"quintiles: qcut impossible ({_e}) → skip")
            q = None
        if q is not None:
            for qi in range(5):
                m = q == qi
                fv = fv_all[m]
                if len(fv) == 0:
                    continue
                srt = np.sort(fv)
                n5 = max(1, int(len(fv) * 0.05))
                d = d_all[m]
                quint_rows.append({
                    "quintile": qi + 1, "n": int(m.sum()),
                    "mean_H20": float(fv.mean()), "median_H20": float(np.median(fv)),
                    "P_H20_gt0": float((fv > 0).mean()),
                    "BAD5": float(srt[:n5].mean()), "GOOD5": float(srt[-n5:].mean()),
                    "D1": float((d == 1).mean()), "D10": float((d == 10).mean()),
                })
    pd.DataFrame(quint_rows).to_csv(ARTIFACTS_DIR / "temporal_score_quintiles.csv", index=False)
    _plog(f"quintiles écrits ({len(quint_rows)})")

    # ── Coefficients standardisés (section 16) — L3 (ou L2 si meilleur) ──
    coef_model = best_seq_m
    rep_cols = list(reps[dict(L2="M2", L3="M3")[coef_model]].columns)
    coef_rows = []
    if coef_store.get(coef_model):
        arr = np.vstack(coef_store[coef_model])
        for j, c in enumerate(rep_cols):
            coef_rows.append({
                "feature": c.split("__")[0], "lag": c.split("__")[1] if "__" in c else "-",
                "coefficient_mean": float(arr[:, j].mean()),
                "coefficient_std": float(arr[:, j].std(ddof=1)),
                "stability_across_folds": float(np.mean(np.sign(arr[:, j]) == np.sign(np.median(arr[:, j])))),
            })
    coef_df = pd.DataFrame(coef_rows)
    if not coef_df.empty:
        coef_df = coef_df.sort_values("coefficient_mean", key=lambda x: x.abs(), ascending=False)
    coef_df.to_csv(ARTIFACTS_DIR / "temporal_coefficients.csv", index=False)
    _plog("coefficients écrits")

    # ── Permutation test (section 17) — pipeline complet sur le meilleur modèle ──
    Xrep = reps[dict(L2="M2", L3="M3")[best_seq_m]]
    rng = np.random.default_rng(42)
    null_auc = []
    y_al = yA_aligned.copy()
    obs_idx = ~np.isnan(y_al)
    for p in range(n_perm):
        yp = y_al.copy()
        yp[obs_idx] = rng.permutation(y_al[obs_idx])
        oof_p = np.full(len(seq), np.nan)
        for tr, va in folds:
            tr_ok = tr[~np.isnan(yp[tr])]
            va_ok = va[~np.isnan(yp[va])]
            if len(tr_ok) < min_train or len(va_ok) < 30:
                continue
            sc, _ = _fit_predict(Xrep.iloc[tr_ok], Xrep.iloc[va_ok], yp[tr_ok].astype(int), model="lr")
            oof_p[va_ok] = sc
        m = ~np.isnan(oof_p) & ~np.isnan(yp)
        if m.sum() >= 30:
            null_auc.append(_auc_rank(yp[m].astype(int), oof_p[m]))
    null_auc = np.array(null_auc)
    observed = auc_oof[best_seq_m]
    p_value = float(np.mean(null_auc >= observed)) if len(null_auc) else np.nan
    perm_df = pd.DataFrame({
        "model": [best_seq_m], "observed_oof_auc": [observed],
        "null_mean": [float(np.mean(null_auc)) if len(null_auc) else np.nan],
        "null_p95": [float(np.percentile(null_auc, 95)) if len(null_auc) else np.nan],
        "n_permutations": [len(null_auc)], "empirical_pvalue": [p_value],
    })
    perm_df.to_csv(ARTIFACTS_DIR / "temporal_permutation.csv", index=False)
    _plog(f"permutation {best_seq_m}: observed={observed:.4f} null_mean={np.mean(null_auc):.4f} "
          f"p={p_value:.4f}")

    # ── Analyse par période (section 19) — AUC OOF par année ──
    period_rows = []
    oof_ok = oof_df.copy()
    for y in [2023, 2024, 2025]:
        ym = oof_ok["signal_date"].dt.year == y
        for m in model_names:
            s = oof_ok.loc[ym, f"score_{m}"].to_numpy(dtype=float)
            fv = oof_ok.loc[ym, "future_return_H20"].to_numpy(dtype=float)
            okk = ~np.isnan(s) & ~np.isnan(fv)
            if okk.sum() >= 30:
                period_rows.append({"year": y, "model": m,
                                    "auc_oof": _auc_rank((fv[okk] > 0).astype(int), s[okk]),
                                    "n": int(okk.sum())})
    pd.DataFrame(period_rows).to_csv(ARTIFACTS_DIR / "temporal_by_period.csv", index=False)
    _plog("analyse par période écrite")

    # ── T1 : LightGBM conservateur (section 11), conditionnel ──
    t1_rows = []
    if gain >= GAIN_MIN:
        rep_t1 = dict(L2="M2", L3="M3")[best_seq_m]
        aucs_t1 = []
        for tr, va in folds:
            tr_ok = tr[~np.isnan(yA_aligned[tr])]
            va_ok = va[~np.isnan(yA_aligned[va])]
            if len(tr_ok) < min_train or len(va_ok) < 30:
                continue
            sc, _ = _fit_predict(reps[rep_t1].iloc[tr_ok], reps[rep_t1].iloc[va_ok],
                                 yA_aligned[tr_ok].astype(int), model="lgb")
            aucs_t1.append(_auc_rank(yA_aligned[va_ok].astype(int), sc))
        t1_rows.append({"model": "T1", "representation": rep_t1, "auc_mean": float(np.mean(aucs_t1)),
                        "auc_std": float(np.std(aucs_t1)) if len(aucs_t1) > 1 else np.nan,
                        "n_folds": len(aucs_t1),
                        "n_folds_gt_0.5": int(sum(a > 0.5 for a in aucs_t1))})
        _plog(f"T1 (LightGBM conservateur, {rep_t1}) lancé : {[round(a,3) for a in aucs_t1]}")
    else:
        _plog("T1: gain < GAIN_MIN → non lancé (pas de modèle non linéaire)")
    if t1_rows:
        pd.DataFrame(t1_rows).to_csv(ARTIFACTS_DIR / "temporal_t1.csv", index=False)

    # ── Stash pour le rapport ──
    pd.DataFrame([{
        "gain": gain, "best_seq_model": best_seq_m, "best_seq_auc": best_seq,
        "best_static_auc": best_static,
        "best_seq_folds_gt_0.5": int(fold_df.loc[fold_df["model"] == best_seq_m, "n_folds_gt_0.5"].iloc[0]) if len(fold_df) else 0,
        "best_seq_n_folds": int(fold_df.loc[fold_df["model"] == best_seq_m, "n_folds"].iloc[0]) if len(fold_df) else 0,
        "observed_perm_p": p_value, "null_p95": float(perm_df["null_p95"].iloc[0]) if len(perm_df) else np.nan,
        "n_events_complete": int(len(seq)),
    }]).to_csv(ARTIFACTS_DIR / "temporal_summary.csv", index=False)
    _plog("modèles terminés")


def _pr_auc_score(y: np.ndarray, score: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    if len(np.unique(y)) < 2:
        return np.nan
    return float(average_precision_score(y, score))


# ═══════════════════════════════════════════════════════════════════════════
# STAGE REPORT — rapport de faisabilité + verdict (section 23)
# ═══════════════════════════════════════════════════════════════════════════

def run_report() -> None:
    def _read(name: str) -> pd.DataFrame:
        p = ARTIFACTS_DIR / name
        if not p.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(p)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    fold = _read("temporal_fold_metrics.csv")
    cov = _read("temporal_coverage.csv")
    inv = _read("temporal_feature_inventory.csv")
    paths = _read("temporal_paths_good_bad.csv")
    shape = _read("temporal_shape_features.csv")
    quint = _read("temporal_score_quintiles.csv")
    perm = _read("temporal_permutation.csv")
    period = _read("temporal_by_period.csv")
    summary = _read("temporal_summary.csv")
    t1 = _read("temporal_t1.csv")
    b = _read("temporal_targetB.csv")

    md = ["# Chantier `dip_temporal_pattern_feasibility` — Rapport final (2026-08-27)",
          "",
          "Étude de faisabilité : la **trajectoire J-5→J** des features distingue-t-elle "
          "mieux les bons des mauvais DIP que le snapshot `f[J]` ou les deltas ?",
          ""]
    if not fold.empty:
        md.append("## Modèles — AUC OOS (Target A : H20 > 0)")
        md.append("")
        cols = ["model", "representation", "auc_oof", "auc_mean", "auc_median", "auc_std",
                "auc_worst", "n_folds_gt_0.5", "n_folds", "pr_auc_oof", "brier_mean", "ic_mean"]
        md.append(fold[cols].to_markdown(index=False))
        md.append("")
    if not inv.empty:
        md.append("## Dimensions retenues (section 3)")
        md.append("")
        md.append(inv.to_markdown(index=False))
        md.append("")
    if not cov.empty:
        md.append("## Audit de couverture temporelle (section 4)")
        md.append("")
        md.append(cov.to_markdown(index=False))
        md.append("")
    if not paths.empty:
        md.append("## Trajectoires moyennes — divergence WIN vs LOSS (section 7)")
        md.append("")
        pcols = ["feature", "divergence_start", "divergence_end", "divergence_growth"]
        md.append(paths[pcols].sort_values("divergence_growth", key=lambda x: x.abs(), ascending=False).head(12).to_markdown(index=False))
        md.append("")
    if not shape.empty:
        md.append("## Top métriques de forme (section 8)")
        md.append("")
        md.append(shape.head(15)[["feature", "descriptor", "dir_auc", "auc_win_loss", "coverage"]].to_markdown(index=False))
        md.append("")
    if not quint.empty:
        md.append("## Gradient du score OOS (quintiles, section 15)")
        md.append("")
        md.append(quint.to_markdown(index=False))
        md.append("")
    if not period.empty:
        md.append("## Analyse par période (section 19) — AUC OOS par année")
        md.append("")
        md.append(period.pivot_table(index="year", columns="model", values="auc_oof").to_markdown())
        md.append("")
    if not perm.empty:
        md.append("## Permutation test (section 17)")
        md.append("")
        md.append(perm.to_markdown(index=False))
        md.append("")
    if not t1.empty:
        md.append("## T1 — LightGBM conservateur (section 11, conditionnel)")
        md.append("")
        md.append(t1.to_markdown(index=False))
        md.append("")
    if not b.empty:
        md.append("## Target B (D8-10 vs D1-3, section 2) — AUC OOS")
        md.append("")
        md.append(b.to_markdown(index=False))
        md.append("")

    # ── Verdict final (sections 20/21) ──
    md.append("## Verdict final de faisabilité")
    md.append("")
    if not summary.empty:
        s = summary.iloc[0]
        gain = s.get("gain", np.nan)
        best_seq = s.get("best_seq_auc", np.nan)
        best_static = s.get("best_static_auc", np.nan)
        n_gt = int(s.get("best_seq_folds_gt_0.5", 0) or 0)
        n_f = int(s.get("best_seq_n_folds", 0) or 0)
        p_val = s.get("observed_perm_p", np.nan)
        md.append(f"- Meilleure séquence (`{s.get('best_seq_model','?')}`) : AUC OOS = **{best_seq:.4f}** "
                  f"vs static (L0/L1) = {best_static:.4f} → gain = **{gain:+.4f}** (requis ≥ +{GAIN_MIN}).")
        md.append(f"- Folds > 0.5 : {n_gt}/{n_f}. Permutation : p = {p_val:.4f} (null p95 = "
                  f"{s.get('null_p95', np.nan):.4f}).")
        mono = _quintile_monotonicity(quint)
        md.append(f"- Gradient quintile monotone : {mono}.")
        md.append("")
        go = (
            not np.isnan(gain) and gain >= GAIN_MIN
            and n_f > 0 and n_gt > n_f / 2
            and not np.isnan(p_val) and p_val < 0.05
            and mono
        )
        md.append("### Réponses aux 5 questions du chantier")
        md.append("")
        md.append(f"1. **Les trajectoires J-5→J contiennent-elles plus d'info que `f[J]` ?** "
                  f"{'OUI — ' if go else 'NON — '}gain OOS {gain:+.4f} (best seq {best_seq:.4f} vs static {best_static:.4f}).")
        md.append(f"2. **Quelles dimensions portent cette info ?** Voir `temporal_coefficients.csv` (poids/lags) "
                  f"et `temporal_shape_features.csv`.")
        md.append(f"3. **Signal stable OOS ou phénomène de période ?** Voir `temporal_by_period.csv` "
                  f"({n_gt}/{n_f} folds > 0.5, permutation p={p_val:.4f}).")
        md.append(f"4. **Gradient exploitable GOOD/BAD ?** Voir `temporal_score_quintiles.csv` "
                  f"(monotone : {mono}).")
        md.append(f"5. **Le gain justifie un modèle temporel plus complexe ?** "
                  f"{'OUI — chantier DipTemporalQualityModel (LightGBM/TCN/GRU).' if go else 'NON — stopper, pas de LSTM/Transformer.'}")
        md.append("")
        md.append(f"**VERDICT : {'GO_TEMPORAL_MODEL' if go else 'NO_GO_TEMPORAL_MODEL'}**")
    else:
        md.append("(résumé modèle indisponible — lancer `--stage models` d'abord)")
    (ARTIFACTS_DIR / "temporal_feasibility_report.md").write_text("\n".join(md), encoding="utf-8")
    _plog("rapport écrit: temporal_feasibility_report.md")


def _quintile_monotonicity(quint: pd.DataFrame) -> str:
    if quint.empty or len(quint) < 3:
        return "n/a (trop peu de quintiles)"
    from scipy import stats as _sstats
    rho = _sstats.spearmanr(quint["quintile"], quint["mean_H20"]).statistic
    if rho >= 0.5:
        return f"monotone croissant (rho={rho:.2f})"
    if rho <= -0.5:
        return f"monotone décroissant (rho={rho:.2f})"
    return f"pas monotone (rho={rho:.2f})"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    _quiet()
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="events",
                        choices=["events", "panel", "coverage", "models", "report"])
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()

    if args.stage == "events":
        run_events(engine, smoke=args.smoke)
    elif args.stage == "panel":
        run_panel(engine, smoke=args.smoke)
    elif args.stage == "coverage":
        run_coverage(engine, smoke=args.smoke)
    elif args.stage == "models":
        run_models(engine, smoke=args.smoke)
    elif args.stage == "report":
        run_report()
    else:
        raise NotImplementedError(args.stage)


if __name__ == "__main__":
    main()
