"""E0 + E0b + D0 — Extreme Model / Direction Discriminator (aucun entraînement).

Exploite UNIQUEMENT les prédictions WF causales existantes :
  - TOP   : artifacts/models/oracle/oracle-wf-20260818021140/oos_predictions.parquet (proba_top, global_rank_20)
  - BOTTOM: artifacts/models/oracle/oracle-wf-20260818035339/oos_predictions.parquet (proba_bottom, global_rank_20)
Join (date, symbol) → corr(P_top, P_bottom) et metrics d'extrêmes.

E0  : l'ancien Oracle TOP est-il un détecteur stable de true_extreme = TOP10 OR BOTTOM10 ?
E0b : Oracle BOTTOM est-il redondant conditionnellement à Oracle TOP ?
D0  : dans le pool Oracle TOP10, B25 (global_rank_20) discrimine-t-il vrai TOP10 vs vrai BOTTOM10 ?

Périodes : 2022, 2023, 2024, 2025, 2026H1, ALL.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOP_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"
BOT_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818035339" / "oos_predictions.parquet"
OUT = ROOT / "artifacts" / "extreme_direction_e0_d0.md"

try:
    from sklearn.metrics import average_precision_score, roc_auc_score
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]


def _auc(y, s) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 20 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    if _HAS_SKLEARN:
        try:
            return float(roc_auc_score(y, s))
        except Exception:
            pass
    # fallback rank AUC (Mann-Whitney)
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(len(s)) + 1
    pos = ranks[y == 1]
    neg = ranks[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float((pos.sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _ap(y, s) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 20 or len(np.unique(y)) < 2:
        return float("nan")
    if _HAS_SKLEARN:
        try:
            return float(average_precision_score(y, s))
        except Exception:
            pass
    return float("nan")


def _fmt(x) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def _load() -> pd.DataFrame:
    top = pd.read_parquet(TOP_PQ)
    bot = pd.read_parquet(BOT_PQ)
    top["date"] = pd.to_datetime(top["date"])
    bot["date"] = pd.to_datetime(bot["date"])
    df = top.merge(bot[["date", "symbol", "proba_bottom"]], on=["date", "symbol"], how="left")
    df["year"] = df["date"].dt.year
    df["period"] = np.where(df["year"] < 2026, df["year"].astype(str), "2026H1")
    df["oracle_rank"] = df.groupby("date")["proba_top"].rank(pct=True)
    df["bottom_rank"] = df.groupby("date")["proba_bottom"].rank(pct=True)
    df["true_rank"] = df.groupby("date")["future_return"].rank(pct=True)
    df["true_decile"] = (df["true_rank"] * 10).clip(0, 9).astype(int) + 1
    df["true_extreme10"] = ((df["true_decile"] == 1) | (df["true_decile"] == 10)).astype(int)
    return df


def main() -> None:
    df = _load()
    md: list[str] = [
        "# Extreme Model + Direction Discriminator — E0 / E0b / D0",
        "",
        f"Source : TOP/BOTTOM WF causal (join (date,symbol), {len(df):,} obs). Aucun entraînement.",
        "",
        "Target : `true_extreme10` = vrai décile D1 OU D10 (≈20 % de l'univers par jour).",
        "",
    ]

    # ── E0 — Oracle TOP / BOTTOM comme détecteur d'extrêmes ──
    md.append("## E0 — Oracle TOP (proba_top) comme détecteur de true_extreme10")
    md.append("")
    md.append("| période | N | base extrêmes | AUC(TOP) | AP(TOP) | AUC(BOTTOM) | AP(BOTTOM) | AUC moyen score=(Ptop+Pbot)/2 |")
    md.append("|---|---|---|---|---|---|---|---|")
    for p in PERIODS:
        s = df if p == "ALL" else df[df["period"] == p]
        y = s["true_extreme10"]
        auc_t = _auc(y, s["proba_top"])
        ap_t = _ap(y, s["proba_top"])
        auc_b = _auc(y, s["proba_bottom"])
        ap_b = _ap(y, s["proba_bottom"])
        combo = (s["proba_top"] + s["proba_bottom"]) / 2
        auc_c = _auc(y, combo)
        md.append(f"| {p} | {len(s):,} | {y.mean()*100:.1f}% | {_fmt(auc_t)} | {_fmt(ap_t)} | "
                  f"{_fmt(auc_b)} | {_fmt(ap_b)} | {_fmt(auc_c)} |")
    md.append("")
    md.append("### E0 — taux d'extrêmes par décile de score Oracle TOP (proba_top)")
    md.append("")
    md.append("| période | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Q9 | Q10 |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for p in PERIODS:
        s = df if p == "ALL" else df[df["period"] == p]
        s2 = s.copy()
        s2["q"] = (s2["oracle_rank"] * 10).clip(0, 9).astype(int) + 1
        rates = s2.groupby("q")["true_extreme10"].mean()
        md.append("| %s | " % p + " | ".join(f"{rates.get(q, 0)*100:.0f}%" for q in range(1, 11)) + " |")
    md.append("")

    # ── E0b — redondance BOTTOM ──
    md.append("## E0b — Oracle BOTTOM est-il redondant ?")
    md.append("")
    md.append("| période | corr(Ptop,Pbot) | Jaccard TOP10s | overlap % |")
    md.append("|---|---|---|---|")
    for p in PERIODS:
        s = df if p == "ALL" else df[df["period"] == p]
        corr = s[["proba_top", "proba_bottom"]].corr(method="spearman").iloc[0, 1]
        set_t = set(s[s["oracle_rank"] >= 0.9].index)
        set_b = set(s[s["bottom_rank"] >= 0.9].index)
        inter = len(set_t & set_b)
        union = len(set_t | set_b)
        jac = inter / union if union else float("nan")
        ov = inter / len(set_t) if set_t else float("nan")
        md.append(f"| {p} | {corr:+.3f} | {_fmt(jac)} | {ov*100:.1f}% |")
    md.append("")
    md.append("### E0b — précision/rappel true_extreme par ensemble (ALL)")
    md.append("")
    md.append("| ensemble | n | precision extrême | recall extrême |")
    md.append("|---|---|---|---|")
    s = df
    ext_idx = set(s[s["true_extreme10"] == 1].index)
    sets = {
        "A = TOP seul": s[s["oracle_rank"] >= 0.9].index,
        "B = BOTTOM seul": s[s["bottom_rank"] >= 0.9].index,
        "C = intersection": s[(s["oracle_rank"] >= 0.9) & (s["bottom_rank"] >= 0.9)].index,
        "D = union": s[(s["oracle_rank"] >= 0.9) | (s["bottom_rank"] >= 0.9)].index,
    }
    for name, idx in sets.items():
        n = len(idx)
        if n == 0:
            continue
        prec = len(set(idx) & ext_idx) / n
        rec = len(set(idx) & ext_idx) / len(ext_idx) if ext_idx else float("nan")
        md.append(f"| {name} | {n:,} | {prec*100:.1f}% | {rec*100:.1f}% |")
    md.append("")

    # ── D0 — B25 (global_rank_20) comme discriminateur TOP vs BOTTOM dans le pool Oracle TOP10 ──
    md.append("## D0 — B25 (global_rank_20) discrimine-t-il le signe dans le pool Oracle TOP10 ?")
    md.append("")
    md.append("Pool = Oracle predicted TOP10 (`oracle_rank >= 0.9`). Parmi lui, direction : "
              "1 = vrai TOP10, 0 = vrai BOTTOM10 (D2-D9 exclus). AUC plus élevé = meilleure séparation du signe.")
    md.append("")
    md.append("| période | n pool | n direction | base TOP | AUC(rank→TOP) | mean rank TOP | mean rank BOT | médian rank TOP | médian rank BOT |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for p in PERIODS:
        s = df if p == "ALL" else df[df["period"] == p]
        pool = s[s["oracle_rank"] >= 0.9]
        d = pool[pool["true_decile"].isin([1, 10])].copy()
        if len(d) < 30:
            md.append(f"| {p} | {len(pool):,} | {len(d):,} | - | - | - | - | - | - |")
            continue
        d["direction"] = (d["true_decile"] == 10).astype(int)
        auc = _auc(d["direction"], d["global_rank_20"])
        t = d[d["direction"] == 1]["global_rank_20"]
        b = d[d["direction"] == 0]["global_rank_20"]
        md.append(f"| {p} | {len(pool):,} | {len(d):,} | {d['direction'].mean()*100:.1f}% | {_fmt(auc)} | "
                  f"{t.mean():.3f} | {b.mean():.3f} | {t.median():.3f} | {b.median():.3f} |")
    md.append("")
    md.append("### D0 — buckets de global_rank_20 dans le pool Oracle TOP10 (ALL)")
    md.append("")
    md.append("| bucket rank | n | vrai TOP10 | vrai BOTTOM10 | EDR |")
    md.append("|---|---|---|---|---|")
    s = df
    pool = s[s["oracle_rank"] >= 0.9].copy()
    pool["rb"] = pd.qcut(pool["global_rank_20"].rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)])
    for q in [f"Q{i}" for i in range(1, 6)]:
        g = pool[pool["rb"] == q]
        top = float((g["true_decile"] == 10).mean())
        bot = float((g["true_decile"] == 1).mean())
        edr = top / bot if bot > 0 else float("nan")
        md.append(f"| {q} | {len(g):,} | {top*100:.1f}% | {bot*100:.1f}% | {_fmt(edr)} |")
    md.append("")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("Rapport écrit:", OUT)
    # Résumé console ASCII
    print("\n--- E0 (AUC extrême) + D0 (AUC direction B25) ---")
    for p in PERIODS:
        s = df if p == "ALL" else df[df["period"] == p]
        auc_t = _auc(s["true_extreme10"], s["proba_top"])
        pool = s[s["oracle_rank"] >= 0.9]
        d = pool[pool["true_decile"].isin([1, 10])]
        auc_d = _auc((d["true_decile"] == 10).astype(int), d["global_rank_20"]) if len(d) >= 30 else float("nan")
        print(f"{p:6s} | AUC extreme TOP={_fmt(auc_t)} | AUC direction B25={_fmt(auc_d)}")


if __name__ == "__main__":
    main()
