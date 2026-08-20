"""E6-B1 — Calibration OOF de P(long_success) sur le pool Oracle Extreme O0.

RÈGLE (spec user 2026-08-20) : la calibration est un problème STATISTIQUE uniquement.
Aucun seuil trading, aucun choix TOP10/TOP20, aucun tuning PnL pendant B1. Elle sert à
transformer un score utile en probabilité exploitable pour l'EV (E6-B2), pas à améliorer
le ranking.

MÉTHODE STRICTE :
- Pipeline IDENTIQUE à E6 : pool Oracle Extreme O0 (extreme_pool), features O0 (176),
  CatBoost (train_catboost/_proba_catboost), mêmes folds WF, train = GUARD_COL < fold_start.
- Pour chaque fold :
    1. fit CatBoost sur train → probas train in-sample + probas test OOS.
    2. fit Platt (LogisticRegression sur score) et Isotonic (IsotonicRegression)
       UNIQUEMENT sur (proba_train_in_sample, y_train) du fold.
    3. appliquer les deux calibrateurs au test OOS.
- Aucun calibrateur global. Chaque fold est indépendant.
- Trois sorties en parallèle : brut / Platt / isotonic.

MÉTRIQUES (par semestre + global) :
- Brier score ; log-loss ; calibration error (ECE) ; reliability par décile de proba
  (moyenne prédite vs taux observé) ; AUC ranking.
- ⚠️ VÉRIFICATION : Platt et Isotonic sont MONOTONES → AUC doit rester identique au brut.
  Si isotonic change beaucoup le ranking, l'implémentation est suspecte.

Sortie : print + artifacts/models/oracle/e6_b1_calibration.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from scripts.e6_direction_diagnostic import (
    FOLDS,
    GUARD_COL,
    _fit_predict,
    merge_pools,
    roc_auc,
)
from modelFactory.oracle.train import _proba_catboost

OUT = Path("artifacts/models/oracle/e6_b1_calibration.parquet")

VARIANTS = ["raw", "platt", "isotonic"]


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((y - p) ** 2))


def logloss(y: np.ndarray, p: np.ndarray) -> float:
    eps = 1e-12
    p = np.clip(p, eps, 1.0 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (moyenne pondérée |pred - obs| par bin)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    total = 0.0
    n = len(y)
    for b in range(n_bins):
        mask = idx == b
        if mask.sum() == 0:
            continue
        pred_mean = float(p[mask].mean())
        obs_mean = float(y[mask].mean())
        total += (mask.sum() / n) * abs(pred_mean - obs_mean)
    return float(total)


def calibrate_fold(
    df: pd.DataFrame,
    feature_columns: list[str],
    t_start: str,
    t_end: str,
) -> pd.DataFrame | None:
    """Fit CatBoost + calibrateurs sur le train du fold, applique au test OOS."""
    train = df[df[GUARD_COL] < pd.Timestamp(t_start)]
    test = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
    if len(train) < 100 or len(test) < 50:
        return None
    y_tr = train["y3_long"].astype(int)
    y_te = test["y3_long"].astype(int)
    if y_tr.nunique() < 2 or y_te.nunique() < 2:
        return None
    X_tr = train[feature_columns].astype(float)
    X_te = test[feature_columns].astype(float)

    # CatBoost (pipeline identique E6) : probas train in-sample + test OOS
    model, p_test_raw = _fit_predict("catboost", X_tr, y_tr, X_te, y_te)
    p_train_raw = _proba_catboost(model, X_tr)

    # Calibrateurs appris UNIQUEMENT sur le train du fold
    platt = LogisticRegression(max_iter=1000)
    platt.fit(p_train_raw.reshape(-1, 1), y_tr)
    p_test_platt = platt.predict_proba(p_test_raw.reshape(-1, 1))[:, 1]

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(p_train_raw, y_tr)
    p_test_iso = iso.predict(p_test_raw)

    out = test[["date", "symbol", "y3_long"]].copy()
    out["fold_start"] = pd.Timestamp(t_start)
    out["p_raw"] = p_test_raw
    out["p_platt"] = p_test_platt
    out["p_isotonic"] = p_test_iso
    return out


def semester_metrics(oos: pd.DataFrame, target: str = "y3_long") -> pd.DataFrame:
    """Métriques par semestre pour les 3 variantes."""
    oos = oos.copy()
    y = oos[target].astype(int).to_numpy()
    oos["semester"] = oos["date"].dt.year.astype(str) + np.where(oos["date"].dt.month <= 6, "H1", "H2")
    rows = []
    groups = [("GLOBAL", oos)] + [(s, g) for s, g in oos.groupby("semester")]
    for label, g in groups:
        yy = g[target].astype(int).to_numpy()
        row = {"group": label, "n": len(g), "prev": float(yy.mean())}
        for v in VARIANTS:
            pp = g[f"p_{v}"].to_numpy()
            row[f"{v}_brier"] = brier(yy, pp)
            row[f"{v}_logloss"] = logloss(yy, pp)
            row[f"{v}_ece"] = ece(yy, pp)
            row[f"{v}_auc"] = roc_auc(yy, pp) or float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def decile_reliability(oos: pd.DataFrame, target: str = "y3_long") -> pd.DataFrame:
    """Reliability : par décile de proba (moyenne prédite vs taux observé), par variante."""
    rows = []
    for v in VARIANTS:
        d = oos[[target, f"p_{v}"]].dropna().copy()
        d["decile"] = pd.qcut(d[f"p_{v}"], 10, labels=False, duplicates="drop") + 1
        for dec in sorted(d["decile"].unique()):
            sub = d[d["decile"] == dec]
            rows.append({
                "variant": v, "decile": int(dec), "n": len(sub),
                "pred_mean": float(sub[f"p_{v}"].mean()),
                "obs_mean": float(sub[target].mean()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    df, feature_columns = merge_pools()
    pool = df[df["extreme_pool"]].copy()
    pool = pool.dropna(subset=["y3_long"]).copy()
    print(f"pool extrême O0 : {len(pool):,} | features O0: {len(feature_columns)} | prévalence y3_long={pool['y3_long'].mean():.4f}")

    parts = []
    for t_start, t_end in FOLDS:
        print(f"fold {t_start} → {t_end} ...", flush=True)
        r = calibrate_fold(pool, feature_columns, t_start, t_end)
        if r is None:
            print(f"  (skippé)", flush=True)
            continue
        parts.append(r)
        print(f"  test n={len(r)} | AUC raw={roc_auc(r['y3_long'].astype(int).to_numpy(), r['p_raw'].to_numpy()):.4f} "
              f"platt={roc_auc(r['y3_long'].astype(int).to_numpy(), r['p_platt'].to_numpy()):.4f} "
              f"iso={roc_auc(r['y3_long'].astype(int).to_numpy(), r['p_isotonic'].to_numpy()):.4f}", flush=True)
    oos = pd.concat(parts, ignore_index=True)
    print(f"\nOOS total : {len(oos):,} lignes")

    # ── Vérification AUC (monotonicité des calibrateurs) ──
    y = oos["y3_long"].astype(int).to_numpy()
    print("\n=== VÉRIFICATION AUC (monotone → doit rester identique) ===")
    for v in VARIANTS:
        pp = oos[f"p_{v}"].to_numpy()
        print(f"  {v:<10} AUC = {roc_auc(y, pp):.4f}")

    print("\n=== MÉTRIQUES PAR SEMESTRE + GLOBAL ===")
    sem = semester_metrics(oos)
    cols = ["group", "n", "prev"]
    for v in VARIANTS:
        cols += [f"{v}_brier", f"{v}_ece", f"{v}_auc"]
    print(f"  {'group':<8} {'n':>6} {'prev':>6} " + "".join(
        f"{v:>9}{'B/E/A':>24}" for v in VARIANTS))
    print("-" * (8 + 6 + 6 + 33 * len(VARIANTS)))
    for r in sem.itertuples():
        line = f"  {r.group:<8} {r.n:>6} {r.prev:>6.3f} "
        for v in VARIANTS:
            line += f"{getattr(r, v+'_brier'):>9.4f} {getattr(r, v+'_ece'):>7.3f} {getattr(r, v+'_auc'):>7.3f} "
        print(line)

    print("\n=== RELIABILITY PAR DÉCILE (pred vs obs) — global ===")
    dec = decile_reliability(oos)
    for v in VARIANTS:
        sub = dec[dec["variant"] == v].sort_values("decile")
        print(f"\n  {v.upper()}:")
        print(f"    {'dec':>4} {'n':>6} {'pred':>8} {'obs':>8} {'|diff|':>8}")
        for r in sub.itertuples():
            print(f"    {r.decile:>4} {r.n:>6} {r.pred_mean:>8.4f} {r.obs_mean:>8.4f} {abs(r.pred_mean-r.obs_mean):>8.4f}")

    # ── Choix calibrateur sur la calibration OOF (Brier/ECE global) ──
    print("\n=== CHOIX CALIBRATEUR (sur calibration OOF, PAS sur PnL) ===")
    glob = sem[sem["group"] == "GLOBAL"].iloc[0]
    best = min(VARIANTS, key=lambda v: getattr(glob, f"{v}_ece"))
    print(f"  Meilleur ECE global : {best} (ECE={getattr(glob, best+'_ece'):.4f}, "
          f"Brier={getattr(glob, best+'_brier'):.4f}, AUC={getattr(glob, best+'_auc'):.4f})")
    for v in VARIANTS:
        print(f"    {v:<10} ECE={getattr(glob, v+'_ece'):.4f} Brier={getattr(glob, v+'_brier'):.4f} "
              f"logloss={getattr(glob, v+'_logloss'):.4f} AUC={getattr(glob, v+'_auc'):.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    oos.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
