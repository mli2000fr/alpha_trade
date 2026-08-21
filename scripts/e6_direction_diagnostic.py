"""E6 — Diagnostic directionnel conditionnel à Oracle Extreme O0.

Protocole GELÉ (retour opérateur 2026-08-20) :
- Modèle PRINCIPAL : CatBoostClassifier ; CHALLENGER : LightGBMClassifier.
- Classification BINAIRE uniquement (pas de LSTM, pas de régression, pas de ternaire).
- Mêmes folds WF, mêmes features PIT pour les deux modèles.
- AUC / balanced accuracy / Brier / permutation null / stabilité semestrielle.
- AUCUNE optimisation d'hyperparamètres sur les périodes testées.
- But : déterminer si une information directionnelle/path-dependent EXISTE,
  pas trouver le meilleur modèle.

Cibles :
- E6-A1 : Y1 = future_return_H20 > 0 (pool = extrêmes prédits O0 top-10%)
- E6-A2 : Y2 = Oracle TOP(1) vs BOTTOM(0) (vrais extrêmes oracle_pct_rank>=0.90 vs <=0.10)
- E6-A3 : Y3-LONG = P(long_success) ; Y3-SHORT = P(short_success)
          (pool = extrêmes prédits O0, politique d'exécution gelée)

Usage :
    python -m scripts.e6_direction_diagnostic
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

from modelFactory.oracle.dataset import GUARD_COL
from modelFactory.oracle.train import _proba_catboost, roc_auc, train_catboost, train_lightgbm

O0_OOS = Path("artifacts/models/oracle/oracle-wf-20260820025255/oos_predictions.parquet")
E2_DATASET = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")

# Features O0 : expert + xs_ranks, SANS global_rank_20 (spec E6 §5)
_NON_FEATURE = {
    "date", "symbol", "oracle_extreme10", "future_return",
    "oracle_pct_rank", "oracle_decile", GUARD_COL, "global_rank_20",
}

SEMESTERS = [
    ("2022-01-01", "2022-06-30"), ("2022-07-01", "2022-12-31"),
    ("2023-01-01", "2023-06-30"), ("2023-07-01", "2023-12-31"),
    ("2024-01-01", "2024-06-30"), ("2024-07-01", "2024-12-31"),
    ("2025-01-01", "2025-06-30"), ("2025-07-01", "2025-12-31"),
    ("2026-01-01", "2026-05-29"),
]

FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-05-29"),
]

MODELS = ["catboost", "lightgbm"]


def balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tp = float(((y_true == 1) & (y_pred == 1)).sum())
    tn = float(((y_true == 0) & (y_pred == 0)).sum())
    pos = float((y_true == 1).sum())
    neg = float((y_true == 0).sum())
    rec_pos = tp / pos if pos > 0 else 0.0
    rec_neg = tn / neg if neg > 0 else 0.0
    return float((rec_pos + rec_neg) / 2.0)


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((np.asarray(y_true, dtype=float) - np.asarray(y_prob, dtype=float)) ** 2))


def permutation_null(y_true: np.ndarray, y_prob: np.ndarray, n_perm: int = 30, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(y_prob, dtype=float)
    aucs = []
    for _ in range(n_perm):
        y_shuf = rng.permutation(y)
        a = roc_auc(y_shuf, p)
        if a is not None:
            aucs.append(a)
    if not aucs:
        return {"mean": None, "std": None, "p95": None}
    arr = np.asarray(aucs)
    return {"mean": float(arr.mean()), "std": float(arr.std()), "p95": float(np.percentile(arr, 95))}


def load_feature_pool() -> tuple[pd.DataFrame, list[str]]:
    from modelFactory.oracle.dataset import expert_feature_columns

    df = pd.read_parquet(E2_DATASET)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df[GUARD_COL] = pd.to_datetime(df[GUARD_COL]).dt.normalize()
    expert = [c for c in expert_feature_columns() if c in df.columns]
    xs = [c for c in df.columns if c.endswith("_xs_rank")]
    feature_columns = [c for c in expert + xs if c not in _NON_FEATURE]
    return df, feature_columns


def load_o0_pool() -> pd.DataFrame:
    o = pd.read_parquet(O0_OOS)
    o["date"] = pd.to_datetime(o["date"]).dt.normalize()
    o["_rk"] = o.groupby("date")["proba_extreme"].rank(pct=True)
    o["extreme_pool"] = o["_rk"] >= 0.90
    return o


def merge_pools() -> tuple[pd.DataFrame, list[str]]:
    df, feature_columns = load_feature_pool()
    o0 = load_o0_pool()
    df = df.merge(
        o0[["date", "symbol", "proba_extreme", "extreme_pool", "fold_start"]],
        on=["date", "symbol"], how="inner",
    )
    df = df[df[GUARD_COL] > df["date"]]

    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    df = df.merge(
        path[["symbol", "date", "y3_long", "y3_long_ret", "y3_short", "y3_short_ret", "atr20"]],
        on=["symbol", "date"], how="left",
    )
    return df, feature_columns


def _fit_predict(model_name: str, X_tr, y_tr, X_te, y_te) -> tuple[Any, np.ndarray]:
    if model_name == "catboost":
        model = train_catboost(X_tr, y_tr, X_te, y_te)
        return model, _proba_catboost(model, X_te)
    model = train_lightgbm(X_tr, y_tr, X_te, y_te)
    return model, model.predict(X_te)


def run_wf(df: pd.DataFrame, feature_columns: list[str], target: str, pop_name: str) -> dict:
    per_fold: dict[str, list[dict]] = {m: [] for m in MODELS}
    for t_start, t_end in FOLDS:
        train = df[df[GUARD_COL] < pd.Timestamp(t_start)]
        test = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
        if len(train) < 100 or len(test) < 50:
            continue
        y_tr = train[target].astype(int)
        y_te = test[target].astype(int)
        if y_tr.nunique() < 2 or y_te.nunique() < 2:
            continue
        X_tr = train[feature_columns].astype(float)
        X_te = test[feature_columns].astype(float)
        test = test.copy()
        for m in MODELS:
            _, proba = _fit_predict(m, X_tr, y_tr, X_te, y_te)
            test[f"_proba_{m}"] = proba
            per_fold[m].append({
                "fold_start": t_start,
                "test": test.copy(),
                "proba": proba,
                "y": y_te.to_numpy(),
            })

    results: dict[str, dict] = {}
    for m in MODELS:
        folds = per_fold[m]
        if not folds:
            results[m] = {"n_total": 0}
            continue
        sem_rows = []
        for s_start, s_end in SEMESTERS:
            parts = []
            for r in folds:
                sub = r["test"]
                sub = sub[(sub["date"] >= pd.Timestamp(s_start)) & (sub["date"] <= pd.Timestamp(s_end))]
                if not sub.empty:
                    parts.append(sub)
            if not parts:
                sem_rows.append({"semester": s_start[:7], "n": 0})
                continue
            sem = pd.concat(parts).dropna(subset=[f"_proba_{m}"])
            if len(sem) < 30:
                sem_rows.append({"semester": s_start[:7], "n": int(len(sem))})
                continue
            yy = sem[target].astype(int).to_numpy()
            pp = sem[f"_proba_{m}"].to_numpy()
            sem_rows.append({
                "semester": s_start[:7],
                "n": int(len(sem)),
                "auc": roc_auc(yy, pp),
                "bal_acc": balanced_accuracy(yy, (pp > 0.5).astype(int)),
                "brier": brier_score(yy, pp),
                "prev": float(yy.mean()),
            })
        all_y = np.concatenate([r["y"] for r in folds])
        all_p = np.concatenate([r["proba"] for r in folds])
        null = permutation_null(all_y, all_p)
        aucs = [s.get("auc") for s in sem_rows if s.get("auc") is not None]
        stab = 100.0 * sum(1 for a in aucs if a > 0.5) / len(aucs) if aucs else None
        results[m] = {
            "pop": pop_name,
            "semesters": sem_rows,
            "overall_auc": roc_auc(all_y, all_p),
            "overall_bal_acc": balanced_accuracy(all_y, (all_p > 0.5).astype(int)),
            "overall_brier": brier_score(all_y, all_p),
            "overall_prev": float(all_y.mean()),
            "n_total": len(all_y),
            "null": null,
            "sem_stability_pct": stab,
        }
    return results


def print_report(results: dict[str, dict], title: str) -> None:
    print(f"\n{'='*80}\n{title}\n{'='*80}")
    for m in MODELS:
        r = results[m]
        if r.get("n_total", 0) == 0:
            print(f"  [{m}] no data")
            continue
        n = r["null"]
        z = (r["overall_auc"] - n["mean"]) / n["std"] if n.get("std") else float("nan")
        print(f"\n  [{m}] OVERALL: AUC={r['overall_auc']:.4f} bal_acc={r['overall_bal_acc']:.4f} "
              f"Brier={r['overall_brier']:.4f} prev={r['overall_prev']:.3f} n={r['n_total']}")
        print(f"      PERM NULL: mean={n['mean']:.4f} std={n['std']:.4f} p95={n['p95']:.4f} "
              f"(z={z:.2f}) | stabilité semestrielle (AUC>0.5): {r['sem_stability_pct']:.0f}%")
    print(f"\n  {'semester':<10}" + "".join(f"{m:>22}" for m in MODELS))
    print("  " + "-" * 68)
    for i, s in enumerate(results["catboost"]["semesters"]):
        row = f"  {s['semester']:<10}"
        for m in MODELS:
            ss = results[m]["semesters"][i]
            if ss.get("n", 0) == 0:
                row += f"{'n=0':>22}"
            else:
                row += f"AUC {ss.get('auc') or float('nan'):.3f} | n={ss['n']:>5}".rjust(22)
        print(row)


def main() -> None:
    print("=== E6-A0 — Dataset audit (pool O0, PIT, semestres) ===")
    df, feature_columns = merge_pools()
    print(f"Features O0: {len(feature_columns)} (global_rank_20 exclu: {'global_rank_20' not in feature_columns})")
    print(f"Lignes totales: {len(df)} | pool extrême O0 (top-10%): {int(df['extreme_pool'].sum())} "
          f"({100*df['extreme_pool'].mean():.1f}%)")
    print(f"y3_long dispo: {df['y3_long'].notna().sum()} | y3_short dispo: {df['y3_short'].notna().sum()}")
    pool = df[df["extreme_pool"]].copy()
    pool["y1"] = (pool["future_return"] > 0).astype(int)
    y2 = df[(df["oracle_pct_rank"] >= 0.90) | (df["oracle_pct_rank"] <= 0.10)].copy()
    y2["y2"] = (y2["oracle_pct_rank"] >= 0.90).astype(int)
    pool_y3 = pool.dropna(subset=["y3_long", "y3_short"]).copy()

    print(f"[Y1 pool extrême] n={len(pool)} prev(up)={pool['y1'].mean():.3f}")
    print(f"[Y2 vrais extrêmes] n={len(y2)} prev(TOP)={y2['y2'].mean():.3f}")
    print(f"[Y3 pool extrême] n={len(pool_y3)} prev(long succ)={pool_y3['y3_long'].mean():.4f} "
          f"prev(short succ)={pool_y3['y3_short'].mean():.4f}")

    print_report(run_wf(pool, feature_columns, "y1", "Y1"), "E6-A1 — Y1 direction H20 (pool extrême O0)")
    print_report(run_wf(y2, feature_columns, "y2", "Y2"), "E6-A2 — Y2 TOP vs BOTTOM (vrais extrêmes)")
    print_report(run_wf(pool_y3, feature_columns, "y3_long", "Y3-LONG"),
                 "E6-A3 — Y3 LONG path-success (pool extrême O0)")
    print_report(run_wf(pool_y3, feature_columns, "y3_short", "Y3-SHORT"),
                 "E6-A3 — Y3 SHORT path-success (pool extrême O0)")

    print("\n=== E6-A4 — SYNTHÈSE (verdict terminal vs tradable, CatBoost vs LightGBM) ===")


if __name__ == "__main__":
    main()
