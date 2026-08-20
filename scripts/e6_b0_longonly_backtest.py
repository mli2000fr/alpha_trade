"""E6-B0 — Backtest de validation gelé, LONG-only, par quantiles du score Y3-LONG OOF.

OBJECTIF (spec user, 2026-08-20) : vérifier que l'AUC/lift E6 se transforme en
**monotonie économique** et en amélioration d'expectancy — AVANT de construire E6-B/EV_LONG.

PRINCIPES STRICTS (gelés avant le backtest) :
- Pool = pool Oracle Extreme O0 (extreme_pool, top-10% proba_extreme/date) — inchangé.
- Score de sélection = ``_proba_catboost`` (Y3-LONG) **strictement OOF/WF** : chaque fold
  entraîné sur GUARD_COL < fold_start, prédit uniquement sur son test window (même pipeline
  que E6 via collect_oos_probas). AUCUN score contaminé.
- Rang cross-sectionnel par date : ``long_success_score = rank(_proba_catboost)/n`` intra-date.
- Buckets préfixés (aucun seuil de proba brute) : ALL extreme, TOP50, TOP20, TOP10, TOP5.
- Exits gelés : stop 3.5×ATR, TP min(4×ATR,13%), trailing LONG 7% (activation 0R) — labels
  déjà simulés (y3_long_ret). AUCUNE modification.
- Coûts : DEFAULT_COST_MODEL = 16 bps round-trip (spread 5 + comm 1 + slip 2 par sens).
- Sizing : risk-based, risque fixe par trade (1% du capital au stop = 3.5×ATR), plafonné.
- Aucun tuning, aucun changement de modèle/exits/costs. SHORT ignoré (LONG-only book).

GATES (fixés AVANT de voir les résultats) :
  G1 : expectancy (mean net ret/trade) de TOP10 > pool ALL non filtré.
  G2 : PF de TOP10 > PF de ALL.
  G3 : TOP10 positif sur une nette majorité de semestres (>= 60% des semestres avec mean_ret>0).
  G4 : pas d'explosion du DD (maxDD TOP10 <= ~1.5 × maxDD ALL en sizing risk-based).
  G5 : tendance cohérente TOP20 -> TOP10 (TOP10 >= TOP20 en expectancy, ou au pire équivalent).
  G6 : pas de dépendance 2025/2026 uniquement (TOP10 gagne aussi sur 2023-2024).

Métriques : PnL/trade (expectancy), PF, win rate, DD, n trades, par semestre.
Pattern attendu : ALL < TOP50 < TOP20 < TOP10 (monotonie économique). Top5 = toléré bruité.

Sortie : print + artifacts/models/oracle/e6_b0_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

OOF_PROBAS = Path("artifacts/models/oracle/e6_y3_lift.parquet")
PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
OUT = Path("artifacts/models/oracle/e6_b0_results.parquet")

# ── Paramètres gelés (identiques production / E6) ──
ROUND_TRIP_PCT = 0.0016          # 16 bps (DEFAULT_COST_MODEL)
STOP_MULT = 3.5                   # stop LONG = 3.5 × ATR
RISK_PCT = 0.01                   # risque fixe par trade = 1% du capital au stop
MAX_WEIGHT = 0.25                 # plafond de poids par position (sizing)
CAPITAL = 100_000.0

BUCKETS = [("ALL", 1.0), ("TOP50", 0.50), ("TOP20", 0.20), ("TOP10", 0.10), ("TOP5", 0.05)]


def load_data() -> pd.DataFrame:
    oof = pd.read_parquet(OOF_PROBAS)
    oof["date"] = pd.to_datetime(oof["date"]).dt.normalize()
    oof["symbol"] = oof["symbol"].astype(str)

    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)

    # NB : `y3_long` vient déjà de oof (e6_y3_lift.parquet) — on ne merge que les
    # sorties de chemin (ret/reason/atr/entry) pour éviter un suffixe _x/_y.
    cols = ["symbol", "date", "y3_long_ret", "y3_long_reason", "atr20", "entry"]
    df = oof.merge(path[cols], on=["symbol", "date"], how="inner")
    df = df.dropna(subset=["_proba_catboost", "y3_long_ret", "atr20", "entry"])
    df = df[df["atr20"] > 0]
    # Rang cross-sectionnel par date (score de sélection OOF)
    df["long_success_score"] = df.groupby("date")["_proba_catboost"].rank(pct=True)
    return df


def risk_weight(entry: float, atr20: float) -> float:
    """Poids risk-based : risque RISK_PCT du capital au stop (3.5×ATR), plafonné."""
    stop_dist = STOP_MULT * atr20
    if stop_dist <= 0 or entry <= 0:
        return 0.0
    w = RISK_PCT * entry / stop_dist
    return float(min(w, MAX_WEIGHT))


def build_bucket(df: pd.DataFrame, keep_pct: float) -> pd.DataFrame:
    if keep_pct >= 1.0:
        return df.copy()
    top = df[df["long_success_score"] >= 1.0 - keep_pct].copy()
    return top


def metrics(bucket: pd.DataFrame, label: str) -> dict:
    b = bucket.copy()
    b["net_ret"] = b["y3_long_ret"] - ROUND_TRIP_PCT
    b["weight"] = b.apply(lambda r: risk_weight(r["entry"], r["atr20"]), axis=1)
    b["pnl_unit"] = b["net_ret"] * b["weight"]          # PnL en fraction du capital par unité
    b["semester"] = b["date"].dt.year.astype(str) + np.where(b["date"].dt.month <= 6, "H1", "H2")

    n = len(b)
    gross_pos = b.loc[b["net_ret"] > 0, "net_ret"].sum()
    gross_neg = -b.loc[b["net_ret"] < 0, "net_ret"].sum()
    pf = gross_pos / gross_neg if gross_neg > 0 else float("inf")
    mean_ret = float(b["net_ret"].mean())
    win_rate = float((b["net_ret"] > 0).mean())
    total_pnl_pct = float(b["pnl_unit"].sum())

    # DD (sizing risk-based) sur série par date d'entrée
    daily = b.groupby("date")["pnl_unit"].sum().sort_index()
    equity = daily.cumsum()
    dd = float((equity - equity.cummax()).min()) if len(equity) else 0.0

    # Par semestre (expectancy nette par trade)
    sem = b.groupby("semester").agg(
        n=("net_ret", "size"),
        mean_ret=("net_ret", "mean"),
        pnl_pct=("pnl_unit", "sum"),
        win=("net_ret", lambda s: float((s > 0).mean())),
    )
    pos_sem = int((sem["mean_ret"] > 0).sum())

    return {
        "bucket": label, "n_trades": n,
        "mean_ret_per_trade": mean_ret,
        "pf": pf, "win_rate": win_rate,
        "total_pnl_pct": total_pnl_pct,
        "max_dd_pct": dd,
        "n_semesters": len(sem), "n_pos_semesters": pos_sem,
        "semesters": sem,
    }


def main() -> None:
    df = load_data()
    print(f"Pool Oracle Extreme O0 : {len(df):,} trades potentiels | "
          f"{df['date'].min().date()} -> {df['date'].max().date()}")
    print(f"Prévalence y3_long : {df['y3_long'].mean():.4f}")
    print(f"Coûts round-trip : {ROUND_TRIP_PCT*10000:.0f} bps | sizing : risque {RISK_PCT*100:.0f}%/trade au stop 3.5×ATR\n")

    results = {}
    for label, pct in BUCKETS:
        b = build_bucket(df, pct)
        results[label] = metrics(b, label)

    print("=" * 100)
    print("E6-B0 — LONG-only, score OOF, buckets préfixés (zéro tuning)")
    print("=" * 100)
    print(f"{'bucket':<8} {'n':>7} {'mean_ret/trade':>14} {'PF':>7} {'win%':>7} "
          f"{'totalPnL%':>10} {'maxDD%':>9} {'sem+':>6}")
    print("-" * 100)
    for label, _ in BUCKETS:
        r = results[label]
        print(f"{label:<8} {r['n_trades']:>7} {100*r['mean_ret_per_trade']:>13.3f}% "
              f"{r['pf']:>7.2f} {100*r['win_rate']:>6.1f}% "
              f"{r['total_pnl_pct']:>9.2f}% {100*r['max_dd_pct']:>8.2f}% "
              f"{r['n_pos_semesters']:>3}/{r['n_semesters']}")

    print("\n" + "=" * 100)
    print("Résultat par semestre — mean_ret/trade net (%) [bucket: H1/H2 ...]")
    print("=" * 100)
    sems = sorted(set().union(*[r["semesters"].index for r in results.values()]))
    print(f"{'semester':<10}" + "".join(f"{lbl:>14}" for lbl, _ in BUCKETS))
    for s in sems:
        row = f"{s:<10}"
        for lbl, _ in BUCKETS:
            if s in results[lbl]["semesters"].index:
                row += f"{100*results[lbl]['semesters'].loc[s,'mean_ret']:>13.3f}%"
            else:
                row += f"{'—':>14}"
        print(row)

    # ── GATES (pré-fixés) ──
    print("\n" + "=" * 100)
    print("GATES (fixés avant le backtest)")
    print("=" * 100)
    all_r, t20, t10 = results["ALL"], results["TOP20"], results["TOP10"]
    g1 = t10["mean_ret_per_trade"] > all_r["mean_ret_per_trade"]
    g2 = t10["pf"] > all_r["pf"]
    g3 = t10["n_pos_semesters"] >= 0.60 * t10["n_semesters"]
    g4 = t10["max_dd_pct"] <= 1.5 * abs(all_r["max_dd_pct"]) + 1e-9
    g5 = t10["mean_ret_per_trade"] >= t20["mean_ret_per_trade"] - 1e-9
    # G6 : TOP10 gagne aussi sur 2023-2024 (pas uniquement 2025/2026)
    sem_23_24 = [s for s in sems if s.startswith("2023") or s.startswith("2024")]
    if sem_23_24:
        pos_23_24 = sum(1 for s in sem_23_24 if s in t10["semesters"].index and t10["semesters"].loc[s, "mean_ret"] > 0)
        g6 = pos_23_24 >= 1  # au moins un semestre 2023-2024 positif
        g6_detail = f"{pos_23_24}/{len(sem_23_24)} semestres 2023-2024 positifs"
    else:
        g6, g6_detail = False, "aucun semestre 2023-2024"

    print(f"G1 (TOP10 expectancy > ALL)          : {g1}  "
          f"({100*t10['mean_ret_per_trade']:.3f}% vs {100*all_r['mean_ret_per_trade']:.3f}%)")
    print(f"G2 (TOP10 PF > ALL PF)               : {g2}  "
          f"({t10['pf']:.2f} vs {all_r['pf']:.2f})")
    print(f"G3 (TOP10 >= 60% semestres positifs) : {g3}  "
          f"({t10['n_pos_semesters']}/{t10['n_semesters']})")
    print(f"G4 (TOP10 DD <= 1.5×ALL DD)          : {g4}  "
          f"({100*t10['max_dd_pct']:.2f}% vs {100*all_r['max_dd_pct']:.2f}%)")
    print(f"G5 (TOP10 expectancy >= TOP20)       : {g5}  "
          f"({100*t10['mean_ret_per_trade']:.3f}% vs {100*t20['mean_ret_per_trade']:.3f}%)")
    print(f"G6 (pas 2025/2026-only)              : {g6}  ({g6_detail})")

    n_pass = sum([g1, g2, g3, g4, g5, g6])
    print(f"\nGATES PASSÉS : {n_pass}/6")
    if n_pass >= 5 and g1 and g2 and g3:
        print("=> E6-B devient intéressant : le signal statistique se traduit en alpha monétisable.")
    else:
        print("=> E6-B pas encore justifié : monotonie économique non démontrée.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for lbl, _ in BUCKETS:
        results[lbl]["semesters"] = results[lbl]["semesters"].reset_index()
    pd.DataFrame([{k: v for k, v in r.items() if k != "semesters"} for r in results.values()]).to_parquet(
        OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
