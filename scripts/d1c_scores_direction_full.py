"""D1c — Scores stock_scores_history comme discriminateur de direction sur l'ENSEMBLE des symboles.

Différence vs D1b : on ne restreint PAS au pool Oracle extrême (top décile P_top).
Ici le pool = TOUT l'univers du jour (~400 sym/jour) : on teste si les scores séparent
les vrais TOP10 (décile 10 du rendement futur H20 cross-sectionnel) des vrais BOTTOM10
(décile 1), sur l'ensemble des titres, D2-D9 exclus.

Le raisonnement : si les scores ne discriminent même pas la direction sur l'ensemble
des symboles (cas le plus "facile" : on compare les extrêmes réels de tout l'univers),
alors aucun espoir dans le pool Oracle extrême. On compare aussi la stabilité
temporelle (2022 -> 2026), avec 2026 scindé en Q1/Q2 (2026H2 non dispo : données
jusqu'à 2026-05-29).

Gate strict : AUC > 0.5 ET signe stable sur toutes les périodes ET orientation correcte.
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
OUT = ROOT / "artifacts" / "d1c_scores_direction_full.md"

try:
    from sklearn.metrics import roc_auc_score
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

# Périodes : 2022..2025 entières, 2026 scindé Q1/Q2 (pas de H2 dispo)
PERIODS = ["2022", "2023", "2024", "2025", "2026Q1", "2026Q2", "ALL"]

SCORE_FEATURES = [
    "historical_range_score",
    "total_score",
    "final_score_sentiment",
    "selection_rank",
    "short_score",
    "raw_final_score",
    "normalized_total_score",
]

# Orientation attendue (signe de mean TOP - mean BOT) :
EXPECTED_SIGN = {
    "historical_range_score": "+",
    "total_score": "+",
    "final_score_sentiment": "+",
    "selection_rank": "-",  # rang 1 = meilleur => TOP a un rang plus faible
    "short_score": "-",     # haut = baissier => BOTTOM
    "raw_final_score": "+",
    "normalized_total_score": "+",
}


def _period_of(dt: pd.Timestamp) -> str:
    y = dt.year
    if y < 2026:
        return str(y)
    return f"2026Q{1 if dt.month <= 3 else 2}"


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
    df["period"] = df["date"].map(_period_of)

    # vrais déciles cross-sectionnels sur TOUT l'univers du jour
    df["true_rank"] = df.groupby("date")["future_return"].rank(pct=True)
    df["true_decile"] = (df["true_rank"] * 10).clip(0, 9).astype(int) + 1

    # Pool = TOUT l'univers (pas de restriction Oracle)
    dirsub = df[df["true_decile"].isin([1, 10])].copy()
    dirsub["direction"] = (dirsub["true_decile"] == 10).astype(int)
    print(f"Univers total: {len(df):,} | direction TOP/BOTTOM (tous déciles): {len(dirsub):,} "
          f"(TOP {int((dirsub['direction']==1).sum())} / BOT {int((dirsub['direction']==0).sum())})")

    # Charger stock_scores_history PIT (forward-fill)
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        avail = [r[0] for r in c.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='alpha_trade' "
            "AND TABLE_NAME='stock_scores_history'")).fetchall()]
    avail = set(avail)
    feats = [f for f in SCORE_FEATURES if f in avail]
    dmin = df["date"].min().date()
    dmax = df["date"].max().date()
    with eng.connect() as c:
        s = pd.read_sql(text(
            f"SELECT snapshot_date, symbol, {', '.join(feats)} FROM stock_scores_history "
            "WHERE snapshot_date BETWEEN :d1 AND :d2"
        ), c, params={"d1": dmin, "d2": dmax}, parse_dates=["snapshot_date"])
    s["symbol"] = s["symbol"].astype(str)
    print(f"stock_scores_history: {len(s):,} lignes | {s['snapshot_date'].min().date()} -> {s['snapshot_date'].max().date()}")

    # Merge PIT forward-fill par (symbol, snapshot_date<=date)
    swide = s.pivot_table(index="snapshot_date", columns="symbol", values=feats).sort_index()
    pool_dates = sorted(df["date"].unique())
    m = dirsub.copy()
    for f in feats:
        wide = swide[f].reindex(pool_dates).ffill()
        s_long = wide.stack()
        m[f] = [s_long.get((d, sym), np.nan) for d, sym in zip(m["date"], m["symbol"])]
    print(f"Merge PIT: {len(m):,} | cov short_score: {m['short_score'].notna().mean()*100:.1f}% | "
          f"cov total_score: {m['total_score'].notna().mean()*100:.1f}%")

    md: list[str] = [
        "# D1c — Scores stock_scores_history : direction sur l'ENSEMBLE des symboles",
        "",
        f"Pool = TOUT l'univers du jour ({len(df):,} obs, ~400 sym/jour), PAS restreint au pool Oracle extrême.",
        f"Direction : vrai TOP10 ({int((dirsub['direction']==1).sum())}) vs vrai BOTTOM10 ({int((dirsub['direction']==0).sum())}), D2-D9 exclus.",
        "2026 scindé Q1/Q2 (2026H2 indisponible : prédictions jusqu'au 2026-05-29).",
        "Gate strict : AUC > 0.5 ET signe stable sur toutes les périodes ET orientation correcte.",
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
    md.append("## Détail (ALL) — direction TOP vs BOTTOM (ensemble des symboles)")
    md.append("")
    md.append("| feature | N | coverage | AUC | mean TOP | mean BOT | médian TOP | médian BOT | Cohen d | signe moyen (TOP-BOT) | attendu |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for f in feats:
        sub = m
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
    md.append("| feature | signe par période | stable ? | orientation attendue | AUC ALL | gate |")
    md.append("|---|---|---|---|---|---|")
    passed = []
    for f in feats:
        signs = sign_rows.get(f, [])
        sub = m
        a = _auc(sub["direction"], sub[f])
        stable = signs and len(signs) == len(PERIODS) - 1 and len(set(signs)) == 1
        exp = EXPECTED_SIGN.get(f)
        exp_int = 1 if exp == "+" else -1
        orient_ok = stable and signs[0] == exp_int
        ok = stable and orient_ok and not np.isnan(a) and a > 0.5
        if ok:
            passed.append(f)
        cells = []
        for p in PERIODS:
            subp = m if p == "ALL" else m[m["period"] == p]
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
    print("\n--- RESUME D1c (ensemble des symboles) ---")
    for f in feats:
        sub = m
        a = _auc(sub["direction"], sub[f])
        signs = sign_rows.get(f, [])
        stable = signs and len(signs) == len(PERIODS) - 1 and len(set(signs)) == 1
        exp = EXPECTED_SIGN.get(f)
        exp_int = 1 if exp == "+" else -1
        orient_ok = stable and signs[0] == exp_int
        cov = sub[f].notna().mean() * 100
        print(f"  {f:28s} AUC={_fmt(a):>6s}  cov={cov:5.1f}%  stable={stable}  orient={orient_ok}")
    print(f"\nGate D1c — features AUC>0.5 + signe stable + orientation OK: {passed if passed else 'AUCUN'}")
    if not passed:
        print("=> NO-GO direction sur l'ensemble des symboles.")


if __name__ == "__main__":
    main()
