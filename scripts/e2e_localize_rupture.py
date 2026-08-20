"""E2-E — Localiser précisément la rupture du signal Oracle Extreme.

Aucun retraining/tuning/seuil/backtest. Utilise le dataset O1 gelé + parquet OOS.

1. Trimestres COMPLETS 2024Q1->2026Q2 (AUC/P@10/AP/N) pour dater la rupture.
2. Concept drift : pour chaque feature O1 prioritaire, relation univariée avec
   oracle_extreme10 sur 2022-24 vs 2025-26H1 (AUC univariée, Spearman, taux
   d'extrêmes par quintile, diff Q5-Q1, signe).
3. (SHAP : non disponibles proprement -> on utilise corrélation feature/proba comme proxy)
4. Audit regime_bull_market : définition + distribution dans 4 contextes.
5. Décomposition P@10 : TOP vs BOTTOM par trimestre (DÉCISIF pour la direction).
6. Verdict : concept drift seulement si la relation feature->target change.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.train import roc_auc

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
OUT = Path("artifacts/models/oracle/e2e_rupture.md")

QUARTERS = ["2024Q1", "2024Q2", "2024Q3", "2024Q4",
            "2025Q1", "2025Q2", "2025Q3", "2025Q4",
            "2026Q1", "2026Q2"]
FEATURES = ["momentum_20", "relative_strength_20", "range_position_20", "rsi_14",
            "market_volatility_20", "market_return_20", "market_trend_strength_50",
            "momentum_20_x_bull", "relative_strength_20_x_bull", "rsi_14_x_bull",
            "rolling_volatility_20", "global_rank_20", "volume_ratio_20", "drawdown_20"]


def _auc(y, s) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 50 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    return roc_auc(y, s) or float("nan")


def _spearman(a: pd.Series, b: pd.Series) -> float:
    m = a.notna() & b.notna()
    a, b = a[m], b[m]
    if len(a) < 50:
        return float("nan")
    return float(a.corr(b, method="spearman"))


def _p10(df: pd.DataFrame) -> float:
    precs = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=["proba_extreme", "oracle_extreme10"])
        if len(g) < 20:
            continue
        n_top = max(1, int(np.ceil(len(g) * 0.10)))
        top = g.nlargest(n_top, "proba_extreme")
        precs.append(float(top["oracle_extreme10"].mean()))
    return float(np.mean(precs)) if precs else float("nan")


def _ap(y, s) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 50 or len(np.unique(y)) < 2:
        return float("nan")
    order = np.argsort(-s)
    y = y[order]
    tp = np.cumsum(y)
    prec = tp / (np.arange(len(y)) + 1)
    rec = tp / tp[-1] if tp[-1] > 0 else np.zeros_like(tp)
    return float(np.sum(prec * np.diff(np.concatenate([[0.0], rec]))))


def main() -> None:
    ds = pd.read_parquet(DATA)
    oos = pd.read_parquet(OOS)
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    m = ds.merge(oos[["date", "symbol", "proba_extreme"]], on=["date", "symbol"], how="inner")
    m["quarter"] = m["date"].dt.year.astype(str) + "Q" + m["date"].dt.quarter.astype(str)
    m["period"] = np.where(m["date"].dt.year < 2025, "2022-24", "2025-26H1")

    md: list[str] = ["# E2-E — Localisation précise de la rupture Oracle Extreme", ""]

    # ═════════ 1. Trimestres complets ═════════
    md.append("## 1. Métriques par trimestre COMPLET (2024Q1 -> 2026Q2)")
    md.append("")
    md.append("| trim | N | prev% | AUC | AP | P@10 | recall@10 |")
    md.append("|---|---|---|---|---|---|---|")
    print("=== 1. Trimestres complets ===")
    print(f"{'trim':<8}{'N':>8}{'prev%':>7}{'AUC':>7}{'AP':>7}{'P@10':>7}{'rec@10':>7}")
    for q in QUARTERS:
        sub = m[m["quarter"] == q]
        if sub.empty:
            md.append(f"| {q} | - | - | - | - | - | - |")
            continue
        y = sub["oracle_extreme10"].to_numpy()
        s = sub["proba_extreme"].to_numpy()
        auc = _auc(y, s)
        ap = _ap(y, s)
        p10 = _p10(sub)
        prev = sub["oracle_extreme10"].mean()
        md.append(f"| {q} | {len(sub):,} | {prev*100:.1f} | {auc:.3f} | {ap:.3f} | {p10*100:.1f} | - |")
        print(f"{q:<8}{len(sub):>8,}{prev*100:>7.1f}{auc:>7.3f}{ap:>7.3f}{p10*100:>7.1f}")

    # ═════════ 5. Décomposition P@10 TOP vs BOTTOM (décisive) ═════════
    md.append("")
    md.append("## 5. Décomposition P@10 : TOP vs BOTTOM par trimestre")
    md.append("")
    md.append("| trim | P@10_total | P@10_TOP | P@10_BOTTOM | part_TOP | part_BOTTOM |")
    md.append("|---|---|---|---|---|---|")
    print("\n=== 5. Décomposition P@10 TOP vs BOTTOM ===")
    print(f"{'trim':<8}{'P@10_tot':>9}{'P@10_TOP':>9}{'P@10_BOT':>9}{'part_TOP':>9}{'part_BOT':>9}")
    p10_decomp = {}
    for q in QUARTERS:
        sub = m[m["quarter"] == q]
        if sub.empty:
            continue
        precs_tot, precs_top, precs_bot = [], [], []
        for _, g in sub.groupby("date"):
            g = g.dropna(subset=["proba_extreme", "oracle_extreme10", "oracle_pct_rank"])
            if len(g) < 20:
                continue
            n_top = max(1, int(np.ceil(len(g) * 0.10)))
            top = g.nlargest(n_top, "proba_extreme")
            precs_tot.append(float(top["oracle_extreme10"].mean()))
            # TOP = vrai TOP10 (pct_rank>=0.90), BOTTOM = vrai BOTTOM10 (pct_rank<=0.10)
            precs_top.append(float((top["oracle_pct_rank"] >= 0.90).mean()))
            precs_bot.append(float((top["oracle_pct_rank"] <= 0.10).mean()))
        t = float(np.mean(precs_tot)) if precs_tot else float("nan")
        tp_ = float(np.mean(precs_top)) if precs_top else float("nan")
        bt_ = float(np.mean(precs_bot)) if precs_bot else float("nan")
        p10_decomp[q] = (t, tp_, bt_)
        md.append(f"| {q} | {t*100:.1f} | {tp_*100:.1f} | {bt_*100:.1f} | "
                  f"{tp_/t*100 if t else float('nan'):.1f} | {bt_/t*100 if t else float('nan'):.1f} |")
        print(f"{q:<8}{t*100:>9.1f}{tp_*100:>9.1f}{bt_*100:>9.1f}"
              f"{(tp_/t*100 if t else float('nan')):>9.1f}{(bt_/t*100 if t else float('nan')):>9.1f}")

    # ═════════ 2. Concept drift : relation feature->target sur 2 périodes ═════════
    md.append("")
    md.append("## 2. Concept drift : relation feature -> oracle_extreme10 (2022-24 vs 2025-26H1)")
    md.append("")
    md.append("| feature | AUC_2224 | AUC_2526 | Spear_2224 | Spear_2526 | Q5-Q1_2224 | Q5-Q1_2526 | signe_2224 | signe_2526 | drift_relation |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    print("\n=== 2. Concept drift (relation feature->target) ===")
    for f in FEATURES:
        if f not in m.columns:
            continue
        row = []
        rel_drift = False
        for pg in ["2022-24", "2025-26H1"]:
            sub = m[m["period"] == pg]
            a = _auc(sub["oracle_extreme10"], sub[f])
            sp = _spearman(sub[f], sub["oracle_extreme10"])
            # taux d'extrêmes par quintile de feature -> diff Q5-Q1
            q = sub.dropna(subset=[f, "oracle_extreme10"]).copy()
            if len(q) > 100:
                q["_q"] = pd.qcut(q[f], 5, labels=False, duplicates="drop")
                gq = q.groupby("_q")["oracle_extreme10"].mean()
                if len(gq) >= 2:
                    d = float(gq.iloc[-1] - gq.iloc[0])
                else:
                    d = float("nan")
            else:
                d = float("nan")
            row.append((a, sp, d))
        a1, sp1, d1 = row[0]
        a2, sp2, d2 = row[1]
        sign1 = "pos" if (sp1 or 0) > 0.02 else ("neg" if (sp1 or 0) < -0.02 else "~0")
        sign2 = "pos" if (sp2 or 0) > 0.02 else ("neg" if (sp2 or 0) < -0.02 else "~0")
        # drift de relation : changement de signe OU |AUC1-AUC2|>0.05 OU |d1-d2|>0.03
        if sign1 != sign2 or abs(a1 - a2) > 0.05 or abs(d1 - d2) > 0.03:
            rel_drift = True
        md.append(f"| {f} | {a1:.3f} | {a2:.3f} | {sp1:.3f} | {sp2:.3f} | {d1:.4f} | {d2:.4f} | "
                  f"{sign1} | {sign2} | {'OUI' if rel_drift else 'non'} |")
        print(f"  {f:<32} AUC {a1:.3f}->{a2:.3f}  Spear {sp1:+.3f}->{sp2:+.3f}  Q5Q1 {d1:+.4f}->{d2:+.4f}  {'DRIFT' if rel_drift else 'ok'}")

    # ═════════ 4. Audit regime_bull_market ═════════
    md.append("")
    md.append("## 4. Audit regime_bull_market (= benchmark_close > sma200)")
    md.append("")
    md.append("| contexte | N | mean(regime_bull_market) |")
    md.append("|---|---|---|")
    print("\n=== 4. regime_bull_market ===")
    # a) distribution dans tout l'univers OOS avant sélection
    all_uni = m.copy()
    md.append(f"| tout l'univers OOS | {len(all_uni):,} | {all_uni['regime_bull_market'].mean():.3f} |")
    print(f"  tout univers OOS: mean={all_uni['regime_bull_market'].mean():.3f}")
    # b) dans le TOP10 Oracle (pred_top)
    all_uni["oracle_rank"] = all_uni.groupby("date")["proba_extreme"].rank(pct=True)
    top10 = all_uni[all_uni["oracle_rank"] >= 0.90]
    md.append(f"| TOP10 Oracle | {len(top10):,} | {top10['regime_bull_market'].mean():.3f} |")
    print(f"  TOP10 Oracle: mean={top10['regime_bull_market'].mean():.3f}")
    # c) par période
    for pg in ["2022-24", "2025-26H1"]:
        sub = all_uni[all_uni["period"] == pg]
        md.append(f"| univers {pg} | {len(sub):,} | {sub['regime_bull_market'].mean():.3f} |")
        print(f"  univers {pg}: mean={sub['regime_bull_market'].mean():.3f}")
    # d) par trimestre (cœur : montrer que ce n'est pas constant partout)
    md.append("")
    md.append("| trim | mean(regime_bull_market) univers | mean(TOP10 Oracle) |")
    md.append("|---|---|---|")
    for q in QUARTERS:
        sub = all_uni[all_uni["quarter"] == q]
        if sub.empty:
            continue
        t10 = sub[sub["oracle_rank"] >= 0.90]
        md.append(f"| {q} | {sub['regime_bull_market'].mean():.3f} | {t10['regime_bull_market'].mean():.3f} |")
        print(f"  {q}: univers={sub['regime_bull_market'].mean():.3f} top10={t10['regime_bull_market'].mean():.3f}")

    # ═════════ 6. Verdict ═════════
    md.append("")
    md.append("## 6. Verdict")
    md.append("")
    md.append("(à compléter par synthèse — voir console)")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nrapport:", OUT)


if __name__ == "__main__":
    main()
