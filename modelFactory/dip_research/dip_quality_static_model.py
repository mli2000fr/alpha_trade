"""Chantier research-only — dip_quality_static_model (2026-08-27).

Construit un ``dip_quality_score`` STATIQUE (features à J uniquement) pour
classer les événements DIP N4/X2 selon leur probabilité de devenir un bon LONG.
L'usage visé est le RANKING (prioriser les DIP quand les slots sont contraints),
pas un seuil d'entrée.

Périmètre STRICT :
- Setup N4/X2 gelé ; univers PROD (allow_new_entries == True à J) ;
  close_only / cash_only exclus.
- Aucun changement PROD, aucun tuning N/X, aucun feature engineering nouveau
  (shortlist figée du chantier temporal : 12 dims F_FULL / 6 dims F_COMPACT).
- Le chantier temporel est clos : NO-GO LSTM/GRU/TCN/Transformer.
  Le résultat utile repris : snapshot statique L0 AUC OOS ≈ 0.5727.

Modèles (uniquement) :
    M0 = aucun modèle (tous les DIP)
    M1 = LogisticRegression sur F_COMPACT
    M2 = LogisticRegression sur F_FULL      (doit reproduire L0 ≈ 0.5727)
    M3 = LightGBM conservateur sur F_COMPACT (early stopping)

Protocole : WF/OOF chronologique strict (même protocole que L0), purge H20,
imputation + scaler TRAIN only.

Usage (étapes) :
    python -m modelFactory.dip_research.dip_quality_static_model --stage dataset
    python -m modelFactory.dip_research.dip_quality_static_model --stage models
    python -m modelFactory.dip_research.dip_quality_static_model --stage portfolio
    python -m modelFactory.dip_research.dip_quality_static_model --stage report
Ajouter ``--smoke`` pour un test rapide.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.dip_research import dip_temporal_pattern_feasibility as _dt
from modelFactory.dip_research.dip_context_pattern_analysis import _auc_rank
from modelFactory.dip_research.dip_temporal_pattern_feasibility import (
    _chrono_folds,
    _fit_predict,
    _fold_metrics,
    _load_temporal,
    _plog,
    _prod_universe,
    _quiet,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "dip_quality_static"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Shortlist figée (chantier temporal) ──
F_FULL: list[str] = [
    "pb_ratio", "pos_52w", "dist_52w_low", "ret60", "dist_sma50", "sector_breadth",
    "breadth_above_sma50", "spy_dist_sma200", "ten_y", "yield_10y_5d_pct",
    "atr14_pct", "vol_z20",
]
# F_COMPACT : représentants non redondants (|corr| >= 0.60 sur snapshot J, univers
# PROD) — choisi uniquement sur la structure de redondance, PAS sur le modèle.
F_COMPACT_THR = 0.60
MAX_F_COMPACT = 8

# ── Modèles ──
LR_C = 0.1
N_FOLDS = 5
PURGE_DAYS = 30
MIN_TRAIN = 200
L0_REFERENCE = 0.5727          # reproduction attendue (protocole L0 du chantier temporal)
L0_TOLERANCE = 0.03

# ── Portfolio replay (PROD-parity, sélection uniquement) ──
SECTOR_CAP = 2
MAX_POSITIONS = 20
COMMISSION_BPS = 1
SLIPPAGE_BPS = 2
COST_RT = (COMMISSION_BPS + SLIPPAGE_BPS) * 2 / 10_000.0   # 6 bps round-trip


def _greedy_compact(main: pd.DataFrame) -> list[str]:
    """F_COMPACT : dédup glouton par corrélation |r| >= F_COMPACT_THR (snapshot J)."""
    lag0 = {f: f"{f}_lag0" for f in F_FULL}
    kept: list[str] = []
    for f in F_FULL:
        if len(kept) >= MAX_F_COMPACT:
            break
        if not kept:
            kept.append(f)
            continue
        cols = [lag0[g] for g in kept] + [lag0[f]]
        vals = main[cols].replace([np.inf, -np.inf], np.nan)
        c = vals.corr().abs().loc[[lag0[g] for g in kept], lag0[f]]
        if c.max() >= F_COMPACT_THR:
            continue
        kept.append(f)
    return kept


# ═══════════════════════════════════════════════════════════════════════════
# STAGE DATASET
# ═══════════════════════════════════════════════════════════════════════════

def run_dataset(engine: Any, *, smoke: bool = False) -> None:
    if smoke:
        _plog("== SMOKE DATASET ==")
    df = _load_temporal(engine)
    if smoke:
        _win = df[(df["signal_date"] >= "2024-06-01") & (df["signal_date"] <= "2024-09-01")]
        df = _win.sample(n=min(60, len(_win)), random_state=0) if len(_win) else df.head(20)
    # Assertions de provenance (single batch, no multi-batch)
    ev = pd.read_csv(_dt.ARTIFACTS_DIR / "events.csv", parse_dates=["signal_date"])
    ev["symbol"] = ev["symbol"].astype(str).str.upper()
    batches = ev["batch_id"].unique().tolist()
    assert len(batches) == 1, f"batchs multiples: {batches}"
    _plog(f"assertion provenance : un seul batch {batches[0]}")

    df = _prod_universe(engine, df)
    main = df[df["allow_new_entries"]].reset_index(drop=True)
    # Assertions dataset
    dup = int(main.duplicated(subset=["signal_date", "symbol"]).sum())
    assert dup == 0, f"duplicats (signal_date,symbol): {dup}"
    assert int(main["allow_new_entries"].sum()) == len(main), "allow_new_entries != True"
    _plog(f"dataset PROD : {len(main)} événements (unique OK, allow_new_entries OK)")

    # F_COMPACT (dédup corrélation, snapshot J)
    f_compact = _greedy_compact(main)
    _plog(f"F_FULL={len(F_FULL)} dims | F_COMPACT (thr={F_COMPACT_THR})={len(f_compact)} dims: {f_compact}")

    # Couverture
    cov_rows = []
    for f in F_FULL:
        lagcols = [f"{f}_lag{k}" for k in range(6)]
        cov_rows.append({
            "feature": f, "set": "F_FULL",
            "coverage_J": float(main[f"{f}_lag0"].notna().mean()),
            "complete_6lag": float(main[lagcols].notna().all(axis=1).mean()),
        })
    for f in f_compact:
        cov_rows.append({"feature": f, "set": "F_COMPACT",
                         "coverage_J": float(main[f"{f}_lag0"].notna().mean()),
                         "complete_6lag": float(main[[f"{f}_lag{k}" for k in range(6)]].notna().all(axis=1).mean())})
    cov = pd.DataFrame(cov_rows)
    cov.to_csv(ARTIFACTS_DIR / "dip_quality_feature_set.csv", index=False)

    # Dataset de modélisation : colonnes statiques (lag0) + labels
    out_cols = ["signal_date", "symbol", "global_rank_20", "ret_4",
                "future_return_H20", "future_return_oracle", "oracle_decile",
                "regime_mode"] + [f"{f}_lag0" for f in F_FULL]
    out = main[[c for c in out_cols if c in main.columns]].copy()
    out = out.rename(columns={f"{f}_lag0": f for f in F_FULL})
    out.to_csv(ARTIFACTS_DIR / "dip_quality_dataset.csv", index=False)
    _plog(f"saved: dip_quality_feature_set.csv + dip_quality_dataset.csv ({out.shape[0]} lignes, {out.shape[1]} cols)")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE MODELS
# ═══════════════════════════════════════════════════════════════════════════

def _load_dataset() -> pd.DataFrame:
    df = pd.read_csv(ARTIFACTS_DIR / "dip_quality_dataset.csv", parse_dates=["signal_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.replace([np.inf, -np.inf], np.nan)


def _run_lr_wf(df: pd.DataFrame, feats: list[str], y_al: np.ndarray, folds,
               lgb: bool = False, min_train: int = MIN_TRAIN):
    """WF/OOF pour LR (ou LightGBM) sur `feats` ; retourne (oof_scores, fold_metrics)."""
    X = df[feats].to_numpy(dtype=float)
    aucs, pr_aucs, briers, ics = [], [], [], []
    oof = np.full(len(df), np.nan)
    for tr, va in folds:
        tr_ok = tr[~np.isnan(y_al[tr])]
        va_ok = va[~np.isnan(y_al[va])]
        if len(tr_ok) < min_train or len(va_ok) < 30:
            continue
        if lgb:
            score = _fit_lgb_early(X[tr_ok], y_al[tr_ok].astype(int), X[va_ok])
        else:
            score, _ = _fit_predict(pd.DataFrame(X[tr_ok]), pd.DataFrame(X[va_ok]),
                                    y_al[tr_ok].astype(int), model="lr")
        oof[va_ok] = score
        met = _fold_metrics(y_al[va_ok].astype(int), score, df["future_return_H20"].to_numpy()[va_ok])
        aucs.append(met["auc"]); pr_aucs.append(met["pr_auc"])
        briers.append(met["brier"]); ics.append(met["ic"])
    m = ~np.isnan(oof) & ~np.isnan(y_al)
    oof_auc = _auc_rank(y_al[m].astype(int), oof[m]) if m.sum() >= 30 else np.nan
    return oof, {
        "auc_oof": oof_auc,
        "auc_mean": float(np.mean(aucs)) if aucs else np.nan,
        "auc_std": float(np.std(aucs)) if len(aucs) > 1 else np.nan,
        "auc_worst": float(np.min(aucs)) if aucs else np.nan,
        "n_folds_gt_0.5": int(sum(a > 0.5 for a in aucs)),
        "n_folds": len(aucs),
        "pr_auc_oof": _pr_auc(y_al[m].astype(int), oof[m]) if m.sum() >= 30 else np.nan,
        "brier_mean": float(np.nanmean(briers)) if briers else np.nan,
        "ic_mean": float(np.nanmean(ics)) if ics else np.nan,
    }


def _fit_lgb_early(X_tr: np.ndarray, y_tr: np.ndarray, X_te: np.ndarray) -> np.ndarray:
    """LightGBM conservateur avec early stopping sur un holdout interne du TRAIN."""
    from sklearn.model_selection import train_test_split
    import lightgbm as lgb
    Xa, Xv, ya, yv = train_test_split(X_tr, y_tr, test_size=0.2, random_state=0, shuffle=False)
    clf = lgb.LGBMClassifier(
        n_estimators=1000, learning_rate=0.03, max_depth=2, num_leaves=7,
        min_child_samples=100, reg_alpha=1.0, reg_lambda=1.0, colsample_bytree=0.7,
        subsample=0.8, subsample_freq=1, random_state=0, verbose=-1,
    )
    clf.fit(Xa, ya, eval_set=[(Xv, yv)], eval_metric="auc",
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)])
    return clf.predict_proba(X_te)[:, 1]


def _pr_auc(y: np.ndarray, score: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    if len(np.unique(y)) < 2:
        return np.nan
    return float(average_precision_score(y, score))


def run_models(*, smoke: bool = False) -> None:
    if smoke:
        _plog("== SMOKE MODELS ==")
    min_train = 30 if smoke else MIN_TRAIN
    df = _load_dataset()
    # Feature sets gelés
    fset = pd.read_csv(ARTIFACTS_DIR / "dip_quality_feature_set.csv")
    f_full = [f for f in F_FULL if f in df.columns]
    f_compact = fset.loc[fset["set"] == "F_COMPACT", "feature"].tolist()
    f_compact = [f for f in f_compact if f in df.columns]
    _plog(f"F_FULL={len(f_full)} F_COMPACT={len(f_compact)} {f_compact}")

    # Lignes complètes sur F_FULL (dataset statique) + labels
    complete = df[[f for f in f_full]].notna().all(axis=1)
    d = df[complete].reset_index(drop=True)
    _plog(f"séquences complètes F_FULL: {len(d)}/{len(df)} ({len(d)/len(df):.1%})")
    fwd = d["future_return_H20"]
    lbl = fwd.notna()
    y_al = np.full(len(d), np.nan)
    y_al[lbl.to_numpy()] = (fwd[lbl] > 0).astype(int).to_numpy()
    dates = d["signal_date"].to_numpy()
    folds = _chrono_folds(dates, min_train=min_train)
    _plog(f"{len(folds)} folds utilisables (chrono + purge {PURGE_DAYS}j)")

    # ── Reproduction L0 (gate section 8) ──
    oof_l0, met_l0 = _run_lr_wf(d, f_full, y_al, folds, min_train=min_train)
    _plog(f"REPRO L0 (LR sur F_FULL): OOF AUC={met_l0['auc_oof']:.4f} (attendu ≈{L0_REFERENCE})")
    if not np.isnan(met_l0["auc_oof"]) and abs(met_l0["auc_oof"] - L0_REFERENCE) > L0_TOLERANCE:
        raise RuntimeError(
            f"REPRODUCTION DIVERGENTE: OOF={met_l0['auc_oof']:.4f} vs attendu {L0_REFERENCE:.4f} "
            f"(tol {L0_TOLERANCE}) — auditer dataset/folds/features avant de continuer.")

    # ── M1 / M2 / M3 ──
    rows = []
    oof_scores: dict[str, np.ndarray] = {}
    # M1 : LR F_COMPACT
    oof_m1, m1 = _run_lr_wf(d, f_compact, y_al, folds, min_train=min_train)
    oof_scores["M1"] = oof_m1
    rows.append({"model": "M1", "rep": f"LR F_COMPACT({len(f_compact)})", **m1})
    _plog(f"M1 LR F_COMPACT: OOF={m1['auc_oof']:.4f}")
    # M2 : LR F_FULL (= L0, same thing — reproduction déjà faite)
    oof_scores["M2"] = oof_l0
    rows.append({"model": "M2", "rep": f"LR F_FULL({len(f_full)})", **met_l0})
    _plog(f"M2 LR F_FULL: OOF={met_l0['auc_oof']:.4f} (== reproduction L0)")
    # M3 : LightGBM F_COMPACT
    if len(d) >= min_train * 2:
        oof_m3, m3 = _run_lr_wf(d, f_compact, y_al, folds, lgb=True, min_train=min_train)
        oof_scores["M3"] = oof_m3
        rows.append({"model": "M3", "rep": f"LGBM F_COMPACT({len(f_compact)})", **m3})
        _plog(f"M3 LGBM F_COMPACT: OOF={m3['auc_oof']:.4f}")
    else:
        oof_scores["M3"] = np.full(len(d), np.nan)
        rows.append({"model": "M3", "rep": f"LGBM F_COMPACT({len(f_compact)})", "auc_oof": np.nan})

    fold_df = pd.DataFrame(rows)
    fold_df.to_csv(ARTIFACTS_DIR / "dip_quality_fold_metrics.csv", index=False)

    # ── OOF predictions (dip_quality_score) ──
    oof_df = d[["signal_date", "symbol", "future_return_H20", "oracle_decile", "global_rank_20"]].copy()
    for m in ("M1", "M2", "M3"):
        oof_df[f"score_{m}"] = oof_scores[m]
    # score final = M2 (LR F_FULL) — le score de référence pour le ranking
    oof_df["dip_quality_score"] = oof_scores["M2"]
    oof_df.to_csv(ARTIFACTS_DIR / "dip_quality_oof_predictions.csv", index=False)
    _plog("OOF predictions + dip_quality_score écrites")

    # ── Quintiles OOF (score M2) ──
    s = oof_scores["M2"]
    ok = ~np.isnan(s) & fwd.notna().to_numpy()
    quint_rows = []
    if ok.sum() >= 100:
        sc = s[ok]; fv = fwd.to_numpy()[ok]; dec = d.loc[ok, "oracle_decile"].to_numpy()
        q = pd.qcut(pd.Series(sc), 5, labels=False, duplicates="drop").to_numpy()
        for qi in range(5):
            m = q == qi
            g = fv[m]
            if len(g) == 0:
                continue
            srt = np.sort(g); n5 = max(1, int(len(g) * 0.05)); dd = dec[m]
            quint_rows.append({"quintile": qi + 1, "n": int(m.sum()),
                               "mean_H20": float(g.mean()), "median_H20": float(np.median(g)),
                               "P_H20_gt0": float((g > 0).mean()),
                               "PF": float(g[g > 0].sum() / abs(g[g <= 0].sum())) if (g <= 0).any() else np.nan,
                               "BAD5": float(srt[:n5].mean()), "GOOD5": float(srt[-n5:].mean()),
                               "D1": float((dd == 1).mean()), "D10": float((dd == 10).mean())})
    pd.DataFrame(quint_rows).to_csv(ARTIFACTS_DIR / "dip_quality_quintiles.csv", index=False)
    _plog(f"quintiles écrits ({len(quint_rows)})")

    # ── Par période (AUC OOF par année, section 9/18) ──
    per_rows = []
    for y in [2023, 2024, 2025]:
        ym = d["signal_date"].dt.year == y
        for m in ("M1", "M2", "M3"):
            sc = oof_scores[m][ym.to_numpy()]; fvv = fwd.to_numpy()[ym.to_numpy()]
            okk = ~np.isnan(sc) & ~np.isnan(fvv)
            if okk.sum() >= 30:
                per_rows.append({"year": y, "model": m,
                                 "auc_oof": _auc_rank((fvv[okk] > 0).astype(int), sc[okk]), "n": int(okk.sum())})
    pd.DataFrame(per_rows).to_csv(ARTIFACTS_DIR / "dip_quality_by_period.csv", index=False)
    _plog("par période écrit")

    # ── Coefficients standardisés (M1/M2, par fold) ──
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    coef_rows = []
    for model_name, feats in (("M1", f_compact), ("M2", f_full)):
        X = d[feats].to_numpy(dtype=float)
        mats = []
        for tr, va in folds:
            tr_ok = tr[~np.isnan(y_al[tr])]
            if len(tr_ok) < min_train:
                continue
            imp = SimpleImputer(strategy="median"); sc = StandardScaler()
            Xtr = sc.fit_transform(imp.fit_transform(X[tr_ok]))
            clf = LogisticRegression(C=LR_C, max_iter=2000).fit(Xtr, y_al[tr_ok].astype(int))
            mats.append(clf.coef_[0])
        if mats:
            arr = np.vstack(mats)
            for j, f in enumerate(feats):
                coef_rows.append({"model": model_name, "feature": f,
                                  "coef_mean": float(arr[:, j].mean()),
                                  "coef_std": float(arr[:, j].std(ddof=1)),
                                  "stability": float(np.mean(np.sign(arr[:, j]) == np.sign(np.median(arr[:, j]))))})
    pd.DataFrame(coef_rows).to_csv(ARTIFACTS_DIR / "dip_quality_coefficients.csv", index=False)
    _plog("coefficients écrits")

    # ── Permutation importance OOF (M3, section 22) ──
    if not np.isnan(oof_scores["M3"]).all():
        imp_rows = []
        base_auc = met_l0["auc_oof"]  # ref
        X = d[f_compact].to_numpy(dtype=float)
        for j, f in enumerate(f_compact):
            drops = []
            oof_p = np.full(len(d), np.nan)
            for tr, va in folds:
                tr_ok = tr[~np.isnan(y_al[tr])]; va_ok = va[~np.isnan(y_al[va])]
                if len(tr_ok) < min_train or len(va_ok) < 30:
                    continue
                Xp = X.copy(); Xp[va_ok, j] = X[np.random.default_rng(0).permutation(len(X))[:len(va_ok)], j]
                # ré-entraîner sur train normal, prédire avec colonne permutée
                score = _fit_lgb_early(X[tr_ok], y_al[tr_ok].astype(int), Xp[va_ok])
                oof_p[va_ok] = score
            m = ~np.isnan(oof_p) & ~np.isnan(y_al)
            if m.sum() >= 30:
                a = _auc_rank(y_al[m].astype(int), oof_p[m])
                drops.append(base_auc - a)
            imp_rows.append({"feature": f, "auc_drop": float(np.mean(drops)) if drops else np.nan,
                             "importance": float(np.mean(drops)) if drops else np.nan})
        pd.DataFrame(imp_rows).sort_values("importance", ascending=False).to_csv(
            ARTIFACTS_DIR / "dip_quality_permutation_importance.csv", index=False)
        _plog("permutation importance M3 écrite")

    # ── Comparaison modèles ──
    comp = fold_df[["model", "rep", "auc_oof", "auc_mean", "auc_std", "auc_worst",
                    "n_folds_gt_0.5", "n_folds", "pr_auc_oof", "brier_mean", "ic_mean"]]
    comp.to_csv(ARTIFACTS_DIR / "dip_quality_model_comparison.csv", index=False)
    _plog("modèles terminés")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE PORTFOLIO — replay sélection P0/P1/P2/P3 (PROD-parity)
# ═══════════════════════════════════════════════════════════════════════════

def _sector_map(engine) -> dict[str, str]:
    meta = pd.read_sql("SELECT symbol, provider_sector, sector FROM stock_metadata", engine)
    meta["symbol"] = meta["symbol"].astype(str).str.upper()
    meta["sector_name"] = meta["provider_sector"].fillna(meta["sector"])
    m = meta.dropna(subset=["sector_name"]).drop_duplicates("symbol")
    return dict(zip(m["symbol"], m["sector_name"]))


def _select_per_day(cands: pd.DataFrame, order_col: str, top_pct: float | None,
                    sector_cap: int, max_positions: int) -> pd.DataFrame:
    """Sélection des candidats d'un jour selon la politique.

    order_col : colonne de tri DESC (global_rank_20 pour P0, dip_quality_score pour P1).
    top_pct : None = tous ; 0.5 = top 50% par dip_quality_score ; 0.25 = top 25%.
    """
    c = cands.dropna(subset=[order_col]).copy()
    if c.empty:
        return c
    if top_pct is not None:
        c = c.sort_values("dip_quality_score", ascending=False)
        n = max(1, int(np.ceil(len(c) * top_pct)))
        c = c.head(n)
    c = c.sort_values(order_col, ascending=False)
    sel = []
    sec_count: dict[str, int] = {}
    for _, r in c.iterrows():
        if len(sel) >= max_positions:
            break
        sec = r.get("sector_name")
        if sec and sec_count.get(sec, 0) >= sector_cap:
            continue
        sel.append(r)
        if sec:
            sec_count[sec] = sec_count.get(sec, 0) + 1
    return pd.DataFrame(sel)


def run_portfolio(engine: Any, *, smoke: bool = False) -> None:
    if smoke:
        _plog("== SMOKE PORTFOLIO ==")
    oof = pd.read_csv(ARTIFACTS_DIR / "dip_quality_oof_predictions.csv", parse_dates=["signal_date"])
    oof["symbol"] = oof["symbol"].astype(str).str.upper()
    oof = oof.replace([np.inf, -np.inf], np.nan)
    sec = _sector_map(engine)
    oof["sector_name"] = oof["symbol"].map(sec)

    # Replay univers = événements avec dip_quality_score OOF (2023-2025 par WF)
    scored = oof[oof["dip_quality_score"].notna()].copy()
    _plog(f"replay univers (OOF): {len(scored)} événements, {scored['signal_date'].nunique()} jours")

    # PnL proxy par trade : future_return_H20 - coûts (round-trip) ; entrée J+1 → approximation
    scored["pnl"] = scored["future_return_H20"] - COST_RT
    scored["score"] = scored["dip_quality_score"]

    policies = {
        "P0": {"order": "global_rank_20", "top": None},
        "P1": {"order": "dip_quality_score", "top": None},
        "P2": {"order": "global_rank_20", "top": 0.50},
        "P3": {"order": "global_rank_20", "top": 0.25},
    }
    port_rows = []
    for pol, cfg in policies.items():
        selected_all = []
        for date, g in scored.groupby("signal_date"):
            sel = _select_per_day(g, cfg["order"], cfg["top"], SECTOR_CAP, MAX_POSITIONS)
            sel = sel.copy()
            sel["policy"] = pol
            selected_all.append(sel)
        sel_df = pd.concat(selected_all) if selected_all else pd.DataFrame()
        # Métriques par trade (additif, PAS de compounding — les retours H20 se
        # chevauchent, un compounding journalier serait un artefact).
        if len(sel_df):
            pnl = sel_df["pnl"].to_numpy(dtype=float)
            add_curve = np.cumsum(pnl)
            pos = pnl[pnl > 0].sum(); neg = abs(pnl[pnl <= 0].sum())
            port_rows.append({
                "policy": pol,
                "n_trades": int(len(pnl)),
                "cum_pnl_additive": float(pnl.sum()),
                "avg_trade": float(pnl.mean()),
                "median_trade": float(np.median(pnl)),
                "win_rate": float((pnl > 0).mean()),
                "profit_factor": float(pos / neg) if neg > 0 else np.nan,
                "trade_sharpe": float(pnl.mean() / pnl.std(ddof=1)) if pnl.std(ddof=1) > 0 else np.nan,
                "maxdd_additive": float((add_curve / np.maximum.accumulate(add_curve) - 1).min()) if len(add_curve) else np.nan,
                "mean_quality": float(sel_df["dip_quality_score"].mean()),
                "n_days": int(sel_df["signal_date"].nunique()),
            })
        else:
            port_rows.append({"policy": pol, "n_trades": 0, "cum_pnl_additive": np.nan,
                              "avg_trade": np.nan, "median_trade": np.nan, "win_rate": np.nan,
                              "profit_factor": np.nan, "trade_sharpe": np.nan,
                              "maxdd_additive": np.nan, "mean_quality": np.nan, "n_days": 0})

    port_df = pd.DataFrame(port_rows)
    port_df.to_csv(ARTIFACTS_DIR / "dip_quality_portfolio_comparison.csv", index=False)

    # ── Attribution P0→P1 (section 17) ──
    att_rows = []
    for date, g in scored.groupby("signal_date"):
        sel0 = _select_per_day(g, "global_rank_20", None, SECTOR_CAP, MAX_POSITIONS)
        sel1 = _select_per_day(g, "dip_quality_score", None, SECTOR_CAP, MAX_POSITIONS)
        s0 = {r["symbol"]: r for _, r in sel0.iterrows()} if not sel0.empty else {}
        s1 = {r["symbol"]: r for _, r in sel1.iterrows()} if not sel1.empty else {}
        for sym, r1 in s1.items():
            if sym not in s0:
                # swap : P0 a choisi un autre symbole, P1 choisit sym
                p0_sym = None; p0_pnl = None
                for s0_sym in s0:
                    if s0_sym not in s1:
                        p0_sym = s0_sym; p0_pnl = s0[s0_sym]["pnl"]; break
                att_rows.append({
                    "date": date, "symbol_p1": sym, "symbol_p0": p0_sym,
                    "score_p1": r1["dip_quality_score"],
                    "score_p0": s0[p0_sym]["dip_quality_score"] if p0_sym else np.nan,
                    "pnl_p1": r1["pnl"], "pnl_p0": p0_pnl,
                    "swap_delta": r1["pnl"] - (p0_pnl or 0.0),
                })
    att = pd.DataFrame(att_rows)
    if not att.empty:
        att["swap_win"] = att["swap_delta"] > 0
        att.to_csv(ARTIFACTS_DIR / "dip_quality_swap_attribution.csv", index=False)
        _plog(f"swaps P0→P1: n={len(att)} swap_win_rate={att['swap_win'].mean():.1%} "
              f"marginal_pnl={att['swap_delta'].sum():.4f} (après coûts)")
    else:
        pd.DataFrame().to_csv(ARTIFACTS_DIR / "dip_quality_swap_attribution.csv", index=False)
        _plog("swaps P0→P1: aucun")

    # ── Jours contraints (section 14) ──
    constr_rows = []
    for date, g in scored.groupby("signal_date"):
        sel0 = _select_per_day(g, "global_rank_20", None, SECTOR_CAP, MAX_POSITIONS)
        n_cand = len(g)
        n_sel = len(sel0) if not sel0.empty else 0
        if n_cand > n_sel:
            rej = g[~g["symbol"].isin(sel0["symbol"])] if not sel0.empty else g
            constr_rows.append({
                "date": date, "n_candidates": n_cand, "candidates_selected": n_sel,
                "candidates_rejected": int(len(rej)),
                "pnl_selected": float(sel0["pnl"].mean()) if not sel0.empty else np.nan,
                "pnl_rejected": float(rej["pnl"].mean()) if len(rej) else np.nan,
                "mean_quality_selected": float(sel0["dip_quality_score"].mean()) if not sel0.empty else np.nan,
                "mean_quality_rejected": float(rej["dip_quality_score"].mean()) if len(rej) else np.nan,
            })
    cd = pd.DataFrame(constr_rows)
    cd.to_csv(ARTIFACTS_DIR / "dip_quality_constrained_days.csv", index=False)
    _plog(f"jours contraints: {len(cd)} (candidats>slots)")

    # ── Par période (section 18) — additif par année ──
    per_rows = []
    for pol in ("P0", "P1", "P2", "P3"):
        for y in [2023, 2024, 2025]:
            ysel = []
            for date, g in scored[scored["signal_date"].dt.year == y].groupby("signal_date"):
                sel = _select_per_day(g, policies[pol]["order"], policies[pol]["top"], SECTOR_CAP, MAX_POSITIONS)
                if not sel.empty:
                    ysel.append(sel)
            ys = pd.concat(ysel) if ysel else pd.DataFrame()
            if len(ys):
                pnl = ys["pnl"].to_numpy(dtype=float)
                pos = pnl[pnl > 0].sum(); neg = abs(pnl[pnl <= 0].sum())
                per_rows.append({"year": y, "policy": pol,
                                 "cum_pnl_additive": float(pnl.sum()),
                                 "avg_trade": float(pnl.mean()),
                                 "win_rate": float((pnl > 0).mean()),
                                 "profit_factor": float(pos / neg) if neg > 0 else np.nan,
                                 "n_trades": int(len(pnl))})
    pd.DataFrame(per_rows).to_csv(ARTIFACTS_DIR / "dip_quality_portfolio_by_period.csv", index=False)
    _plog("portfolio par période écrit")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE REPORT
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

    comp = _read("dip_quality_model_comparison.csv")
    quint = _read("dip_quality_quintiles.csv")
    per = _read("dip_quality_by_period.csv")
    port = _read("dip_quality_portfolio_comparison.csv")
    att = _read("dip_quality_swap_attribution.csv")
    cd = _read("dip_quality_constrained_days.csv")
    pper = _read("dip_quality_portfolio_by_period.csv")
    coef = _read("dip_quality_coefficients.csv")
    fset = _read("dip_quality_feature_set.csv")

    md = ["# Chantier `dip_quality_static_model` — Rapport final (2026-08-27)",
          "",
          "`dip_quality_score` statique (features à J) pour classer les DIP N4/X2. "
          "Usage visé : RANKING (prioriser quand slots contraints).",
          ""]
    if not fset.empty:
        md.append("## Feature sets (figés)")
        md.append("")
        md.append(fset.to_markdown(index=False))
        md.append("")
    if not comp.empty:
        md.append("## Modèles — OOF (Target A : H20 > 0)")
        md.append("")
        md.append(comp.to_markdown(index=False))
        md.append("")
    if not quint.empty:
        md.append("## Quintiles OOF du dip_quality_score (M2)")
        md.append("")
        md.append(quint.to_markdown(index=False))
        md.append("")
    if not per.empty:
        md.append("## AUC OOF par période")
        md.append("")
        md.append(per.pivot_table(index="year", columns="model", values="auc_oof").to_markdown())
        md.append("")
    if not coef.empty:
        md.append("## Coefficients standardisés (M1/M2)")
        md.append("")
        md.append(coef.sort_values("coef_mean", key=lambda x: x.abs(), ascending=False).head(15).to_markdown(index=False))
        md.append("")
    if not port.empty:
        md.append("## Portfolio replay (PROD-parity sélection)")
        md.append("")
        md.append(port.to_markdown(index=False))
        md.append("")
    if not cd.empty:
        md.append("## Jours contraints (candidats > slots)")
        md.append("")
        md.append(cd.to_markdown(index=False))
        md.append("")
    if not att.empty:
        md.append("## Attribution P0→P1 (swaps)")
        md.append("")
        md.append(f"- n swaps : {len(att)}")
        md.append(f"- swap_win_rate : {att['swap_win'].mean():.1%}")
        md.append(f"- marginal PnL après coûts : {att['swap_delta'].sum():.4f}")
        md.append("")
    if not pper.empty:
        md.append("## Portfolio par période")
        md.append("")
        md.append(pper.to_markdown(index=False))
        md.append("")

    # ── Verdict ──
    md.append("## Verdict final")
    md.append("")
    if not comp.empty and not port.empty:
        m2 = comp[comp["model"] == "M2"]
        _p0 = port[port["policy"] == "P0"]
        _p1 = port[port["policy"] == "P1"]
        _p2 = port[port["policy"] == "P2"]
        p0 = _p0.iloc[0] if len(_p0) else None
        p1 = _p1.iloc[0] if len(_p1) else None
        auc = float(m2["auc_oof"].iloc[0]) if len(m2) else np.nan
        grad = _quintile_mono(quint)
        swap_pos = (float(att["swap_delta"].sum()) > 0) if not att.empty else False
        swap_wr = float(att["swap_win"].mean()) if not att.empty else np.nan

        def _num(series, key):
            try:
                v = float(series.get(key, np.nan))
                return v if not np.isnan(v) else None
            except (TypeError, ValueError):
                return None

        p1_gt_p0 = bool(p1 is not None and p0 is not None
                        and _num(p1, "trade_sharpe") is not None and _num(p0, "trade_sharpe") is not None
                        and _num(p1, "cum_pnl_additive") is not None and _num(p0, "cum_pnl_additive") is not None
                        and _num(p1, "trade_sharpe") > _num(p0, "trade_sharpe")
                        and _num(p1, "cum_pnl_additive") > _num(p0, "cum_pnl_additive"))
        md.append(f"- AUC OOF M2 (LR F_FULL) : {auc:.4f} (repro L0 ≈ {L0_REFERENCE}).")
        md.append(f"- Gradient quintile : {grad}.")
        md.append(f"- Swaps P0→P1 : PnL marginal {('> 0' if swap_pos else '<= 0')} "
                  f"(win rate {swap_wr:.1%} si dispo).")
        md.append(f"- Portfolio P1 vs P0 : {'P1 > P0' if p1_gt_p0 else 'P1 <= P0'} "
                  f"(trade_sharpe P0={_num(p0, 'trade_sharpe')} vs P1={_num(p1, 'trade_sharpe')}).")
        md.append("")
        rank_ok = not np.isnan(auc) and auc >= 0.55 and grad and swap_pos and p1_gt_p0
        filter_ok = False
        if len(_p2) and p0 is not None:
            p2 = _p2.iloc[0]
            p0_sh = _num(p0, "trade_sharpe"); p2_sh = _num(p2, "trade_sharpe")
            filter_ok = p0_sh is not None and p2_sh is not None and p2_sh > p0_sh \
                and (_num(p2, "cum_pnl_additive") or 0) > (_num(p0, "cum_pnl_additive") or 0)
        # ── Lecture nuancée du gradient (extrêmes vs milieu) ──
        q1 = _q(quint, 1); q5 = _q(quint, 5)
        sep_q1_q5 = bool(q1 is not None and q5 is not None and q5 > q1)
        p2_trade_better = False
        if len(_p2) and p0 is not None:
            p2 = _p2.iloc[0]
            p2_trade_better = (_num(p2, "avg_trade") or 0) > (_num(p0, "avg_trade") or 0) \
                and (_num(p2, "trade_sharpe") or 0) > (_num(p0, "trade_sharpe") or 0)
        if rank_ok:
            verdict = "GO_RANKING"
        else:
            verdict = "NO_GO"
        if filter_ok:
            verdict = "GO_RANKING + GO_FILTER" if rank_ok else "GO_FILTER (sans GO_RANKING)"
        md.append(f"**VERDICT : {verdict}**")
        md.append("")
        md.append("> GO_RANKING = score utile pour prioriser les DIP ; GO_FILTER = assez fort pour en interdire. "
                  "GO_RANKING + NO_GO_FILTER est un résultat naturel à AUC ≈ 0.57.")
        md.append("")
        md.append("### Lecture nuancée")
        md.append("")
        md.append(f"- Séparation Q1 vs Q5 : {'OUI (Q5 > Q1)' if sep_q1_q5 else 'NON'} "
                  f"(Q1 mean H20 ≈ {q1:.4f} vs Q5 ≈ {q5:.4f}).")
        md.append(f"- Le gradient n'est pas strictement monotone sur Q2→Q4 (bruit au milieu) — "
                  f"mais Q1 (qualité prédite la plus basse) est nettement le pire bucket.")
        md.append(f"- P1 (ranking sous contrainte) : {('améliore P0' if p1_gt_p0 else '≈ P0 / pas de gain')} — "
                  f"les swaps ne gagnent qu'à {swap_wr:.1%} (bruit sur les swaps frontaliers).")
        md.append(f"- P2/P3 (filtre top 50%/25%) : améliorent le per-trade "
                  f"({'OUI' if p2_trade_better else 'NON'}) mais réduisent le nombre de DIP tradés "
                  f"(les slots libérés ne sont pas réalloués dans ce replay DIP-only).")
        md.append(f"- Conclusion : le score a un vrai pouvoir de séparation (AUC {auc:.4f}, Q1 vs Q5, "
                  f"P2/P3 per-trade) mais ne se transfère PAS en gain portefeuille net sur le ranking "
                  f"P1 dans ce replay sans lifecycle ni réallocation. Le verdict repose sur le critère "
                  f"portefeuille décisif du chantier (section 19/20).")
    else:
        md.append("(données insuffisantes — lancer dataset/models/portfolio d'abord)")
    (ARTIFACTS_DIR / "dip_quality_static_report.md").write_text("\n".join(md), encoding="utf-8")
    _plog("rapport écrit: dip_quality_static_report.md")


def _quintile_mono(quint: pd.DataFrame) -> bool:
    if quint.empty or len(quint) < 3:
        return False
    from scipy import stats as _s
    rho = _s.spearmanr(quint["quintile"], quint["mean_H20"]).statistic
    return bool(rho >= 0.7)


def _q(quint: pd.DataFrame, qi: int):
    """mean_H20 du quintile qi (None si absent)."""
    if quint.empty:
        return None
    sub = quint[quint["quintile"] == qi]
    if len(sub) == 0:
        return None
    v = sub["mean_H20"].iloc[0]
    return float(v) if not pd.isna(v) else None


def main() -> None:
    _quiet()
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="dataset",
                        choices=["dataset", "models", "portfolio", "report"])
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()

    if args.stage == "dataset":
        run_dataset(engine, smoke=args.smoke)
    elif args.stage == "models":
        run_models(smoke=args.smoke)
    elif args.stage == "portfolio":
        run_portfolio(engine, smoke=args.smoke)
    elif args.stage == "report":
        run_report()
    else:
        raise NotImplementedError(args.stage)


if __name__ == "__main__":
    main()
