"""D1b — Scores stock_scores_history comme discriminateur de direction dans le pool Oracle extrême.

Même protocole que D1 (sentiment) mais sur les colonnes de score disponibles dans
stock_scores_history (PIT) : historical_range_score, total_score, final_score_sentiment,
selection_rank, short_score.

Pool = Oracle predicted extreme (oracle_rank>=0.9, top décile P_top).
Direction : vrai TOP10 (1) vs vrai BOTTOM10 (0), D2-D9 exclus.
Audit univarié : AUC, mean/median TOP vs BOT, Cohen's d, signe par période + couverture.
Gate strict : AUC>0.5 ET signe stable 2022->2026H1 ET orientation correcte
(short_score : + = baissier -> BOTTOM ; scores long : haut -> TOP).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

ROOT = Path(__file__).resolve().parents[1]
TOP_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"
BOT_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818035339" / "oos_predictions.parquet"
OUT = ROOT / "artifacts" / "d1b_scores_direction.md"

try:
    from sklearn.metrics import roc_auc_score
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]

# Colonnes de score à tester (doivent exister dans stock_scores_history)
SCORE_FEATURES = [
    "historical_range_score",
    "total_score",
    "final_score_sentiment",
    "selection_rank",
    "short_score",
    "raw_final_score",
    "normalized_total_score",
]

# Orientation attendue (sens de la moyenne TOP - moyenne BOT) :
#   "+" : plus haut = plus probable TOP (scores long)
#   "-" : plus bas = plus probable TOP  => pour short_score (haut=baissier=BOTTOM)
EXPECTED_SIGN = {
    "historical_range_score": "+",
    "total_score": "+",
    "final_score_sentiment": "+",
    "selection_rank": "-",  # rang 1 = meilleur => TOP plus bas (rang faible)
    "short_score": "-",     # haut = baissier => BOTTOM
    "raw_final_score": "+",
    "normalized_total_score": "+",
}


def _auc(y, s) -> float:
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 30 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    if _HAS_SKLEARN:
        try:
            return float(roc_auc_score(y, s))
        except Exception:
            pass
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(len(s)) + 1
    pos = ranks[y == 1]
    neg = ranks[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float((pos.sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _cohen_d(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return float("nan")
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.std(ddof=1) ** 2 + (nb - 1) * b.std(ddof=1) ** 2) / (na + nb - 2))
    if sp < 1e-12:
        return float("nan")
    return float((a.mean() - b.mean()) / sp)


def _fmt(x) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def main() -> None:
    top = pd.read_parquet(TOP_PQ)
    bot = pd.read_parquet(BOT_PQ)
    top["date"] = pd.to_datetime(top["date"])
    bot["date"] = pd.to_datetime(bot["date"])
    df = top.merge(bot[["date", "symbol", "proba_bottom"]], on=["date", "symbol"], how="left")
    df["year"] = df["date"].dt.year
    df["period"] = np.where(df["year"] < 2026, df["year"].astype(str), "2026H1")
    df["oracle_rank"] = df.groupby("date")["proba_top"].rank(pct=True)
    df["true_rank"] = df.groupby("date")["future_return"].rank(pct=True)
    df["true_decile"] = (df["true_rank"] * 10).clip(0, 9).astype(int) + 1

    pool = df[df["oracle_rank"] >= 0.9].copy()
    dirsub = pool[pool["true_decile"].isin([1, 10])].copy()
    dirsub["direction"] = (dirsub["true_decile"] == 10).astype(int)
    print(f"Pool Oracle extrême: {len(pool):,} | direction TOP/BOTTOM: {len(dirsub):,} "
          f"(TOP {int((dirsub['direction']==1).sum())} / BOT {int((dirsub['direction']==0).sum())})")

    # Charger stock_scores_history PIT sur (snapshot_date, symbol)
    eng = get_sqlalchemy_engine()
    avail = []
    with eng.connect() as c:
        avail = [r[0] for r in c.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='alpha_trade' "
            "AND TABLE_NAME='stock_scores_history'")).fetchall()]
    avail = set(avail)
    feats = [f for f in SCORE_FEATURES if f in avail]
    print(f"Colonnes dispo: {feats}")
    dmin = pool["date"].min().date()
    dmax = pool["date"].max().date()
    with eng.connect() as c:
        s = pd.read_sql(text(
            f"SELECT snapshot_date, symbol, {', '.join(feats)} FROM stock_scores_history "
            "WHERE snapshot_date BETWEEN :d1 AND :d2"
        ), c, params={"d1": dmin, "d2": dmax}, parse_dates=["snapshot_date"])
    s["symbol"] = s["symbol"].astype(str)
    print(f"stock_scores_history chargé: {len(s):,} lignes | {s['snapshot_date'].min().date()} -> {s['snapshot_date'].max().date()}")

    # ── Merge PIT avec forward-fill (dernier snapshot connu <= date de prédiction) ──
    # stock_scores_history est en snapshots sporadiques (~20 dates/symbole/an),
    # un merge sur date exacte donnerait une couverture artificiellement basse.
    # On construit un pivot symbol x snapshot_date puis ffill par symbole, et on
    # récupère la valeur au jour de prédiction (PIT strict : snapshot <= date).
    score_cols = feats
    # pivot long -> wide par (symbol, snapshot_date)
    swide = s.pivot_table(index="snapshot_date", columns="symbol", values=score_cols)
    # tri chronologique, ffill par symbole (PIT), puis reindex sur les dates du pool
    swide = swide.sort_index()
    pool_dates = sorted(pool["date"].unique())
    m = dirsub.copy()
    for f in score_cols:
        wide = swide[f]  # DataFrame snapshot_date x symbol
        wide = wide.reindex(pool_dates).ffill()
        s_long = wide.stack()  # MultiIndex (date, symbol) -> value
        m[f] = [s_long.get((d, sym), np.nan) for d, sym in zip(m["date"], m["symbol"])]
    print(f"Merge PIT (forward-fill): {len(m):,} | cov short_score: {m['short_score'].notna().mean()*100:.1f}% | "
          f"cov total_score: {m['total_score'].notna().mean()*100:.1f}% | "
          f"cov selection_rank: {m['selection_rank'].notna().mean()*100:.1f}%")

    # Densité des snapshots par symbole (déterminer la granularité réelle)
    snaps_per_sym = s.groupby("symbol").size()
    print(f"Snapshots par symbole: median={snaps_per_sym.median():.0f} min={snaps_per_sym.min()} max={snaps_per_sym.max()} "
          f"({len(snaps_per_sym)} symboles)")
    # nb de dates distinctes de snapshot
    print(f"Dates de snapshot distinctes: {s['snapshot_date'].nunique()}")

    md: list[str] = [
        "# D1b — Scores stock_scores_history comme discriminateur de direction (pool Oracle extrême)",
        "",
        f"Pool = Oracle predicted extreme (top décile P_top, {len(pool):,} obs). "
        f"Direction : vrai TOP10 ({int((dirsub['direction']==1).sum())}) vs vrai BOTTOM10 ({int((dirsub['direction']==0).sum())}), D2-D9 exclus.",
        "Audit univarié. Gate strict : AUC>0.5 ET signe stable ET orientation correcte.",
        "",
    ]

    # Couverture par période
    md.append("## Couverture par période")
    md.append("")
    md.append("| période | N | cov short_score | cov total_score |")
    md.append("|---|---|---|---|")
    for p in PERIODS:
        sub = m if p == "ALL" else m[m["period"] == p]
        md.append(f"| {p} | {len(sub):,} | {sub['short_score'].notna().mean()*100:.1f}% | {sub['total_score'].notna().mean()*100:.1f}% |")
    md.append("")

    # AUC par feature x période
    md.append("## AUC (TOP vs BOTTOM) par feature x période")
    md.append("")
    md.append("| feature | " + " | ".join(PERIODS) + " |")
    md.append("|" + "---|" * (len(PERIODS) + 1) + "|")
    sign_rows = {}
    for f in feats:
        row = []
        signs = []
        for p in PERIODS:
            sub = m if p == "ALL" else m[m["period"] == p]
            sub = sub[sub["true_decile"].isin([1, 10])]
            if len(sub) < 30:
                row.append("-")
                continue
            a = _auc(sub["direction"], sub[f])
            row.append(_fmt(a))
            t = sub[sub["direction"] == 1][f]
            b = sub[sub["direction"] == 0][f]
            if t.notna().sum() >= 10 and b.notna().sum() >= 10:
                signs.append(1 if (t.mean() - b.mean()) > 0 else -1)
        md.append("| " + f + " | " + " | ".join(row) + " |")
        sign_rows[f] = signs

    # Détail ALL
    md.append("")
    md.append("## Détail (ALL) — direction TOP vs BOTTOM")
    md.append("")
    md.append("| feature | N | coverage | AUC | mean TOP | mean BOT | médian TOP | médian BOT | Cohen d | signe moyen (TOP-BOT) | attendu |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for f in feats:
        sub = m[m["true_decile"].isin([1, 10])]
        t = sub[sub["direction"] == 1][f]
        b = sub[sub["direction"] == 0][f]
        if t.notna().sum() < 30 or b.notna().sum() < 30:
            md.append(f"| {f} | {len(sub):,} | - | - | - | - | - | - | - | - |")
            continue
        a = _auc(sub["direction"], sub[f])
        d = _cohen_d(t, b)
        cov = sub[f].notna().mean()
        sign_obs = "+" if (t.mean() - b.mean()) > 0 else "-"
        exp = EXPECTED_SIGN.get(f, "?")
        match = "OK" if sign_obs == exp else ("INVERSÉ" if exp != "?" else "")
        md.append(f"| {f} | {len(sub):,} | {cov*100:.1f}% | {_fmt(a)} | {t.mean():+.4f} | {b.mean():+.4f} | "
                  f"{t.median():+.4f} | {b.median():+.4f} | {_fmt(d)} | {sign_obs} | {exp} {match} |")

    # Stabilité + gate
    md.append("")
    md.append("## Stabilité du signe + gate")
    md.append("")
    md.append("| feature | signe par an (22/23/24/25/26H1) | stable ? | orientation attendue | AUC ALL | gate |")
    md.append("|---|---|---|---|---|---|")
    passed = []
    for f in feats:
        signs = sign_rows.get(f, [])
        sub = m[m["true_decile"].isin([1, 10])]
        a = _auc(sub["direction"], sub[f])
        stable = signs and len(signs) == len(PERIODS) - 1 and len(set(signs)) == 1
        exp = EXPECTED_SIGN.get(f)
        exp_int = 1 if exp == "+" else -1
        orient_ok = stable and signs[0] == exp_int
        ok = stable and orient_ok and not np.isnan(a) and a > 0.5
        if ok:
            passed.append(f)
        # signes par an
        cells = []
        for p in PERIODS:
            subp = m if p == "ALL" else m[m["period"] == p]
            subp = subp[subp["true_decile"].isin([1, 10])]
            t = subp[subp["direction"] == 1][f]
            b = subp[subp["direction"] == 0][f]
            if t.notna().sum() >= 10 and b.notna().sum() >= 10:
                cells.append("+" if (t.mean() - b.mean()) > 0 else "-")
            else:
                cells.append("·")
        gate = "PASSE" if ok else "NON"
        md.append(f"| {f} | {' '.join(cells)} | {'OUI' if stable else 'NON'} | {exp} | {_fmt(a)} | {gate} |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nRapport:", OUT)
    print("\n--- RESUME D1b ---")
    for f in feats:
        sub = m[m["true_decile"].isin([1, 10])]
        a = _auc(sub["direction"], sub[f])
        signs = sign_rows.get(f, [])
        stable = signs and len(signs) == len(PERIODS) - 1 and len(set(signs)) == 1
        exp = EXPECTED_SIGN.get(f)
        exp_int = 1 if exp == "+" else -1
        orient_ok = stable and signs[0] == exp_int
        cov = sub[f].notna().mean() * 100
        print(f"  {f:28s} AUC={_fmt(a):>6s}  cov={cov:5.1f}%  stable={stable}  orient={orient_ok}")
    print(f"\nGate D1b — features AUC>0.5 + signe stable + orientation OK: {passed if passed else 'AUCUN'}")
    if not passed:
        print("=> NO-GO scores directionnels (aucun signal directionnel stable dans stock_scores_history).")


if __name__ == "__main__":
    main()
