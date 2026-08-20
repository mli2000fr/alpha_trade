"""D1d — Direction ABSOLUE conditionnelle aux extrêmes (pool Oracle predicted extreme).

Point conceptuel : on teste maintenant le SIGNE du rendement H20 (UP/DOWN absolu),
PAS le côté relatif (TOP10 vs BOTTOM10 cross-sectionnel). Pour LONG/SHORT, ce qui
compte c'est future_return_h20 > 0 vs < 0.

Pool = Oracle predicted extreme (oracle_rank >= 0.9, top décile P_top) exactement comme E0/D1/D1b.
Target : UP = future_return_h20 > 0 ; DOWN = future_return_h20 < 0 ; return == 0 exclu.
Aucun seuil optimisé. Aucun modèle ML — diagnostic univarié uniquement.

Features PIT par feature :
  short_score, trend_score, weekly_trend_score, relative_strength_index,
  historical_range_score, high_52w_proximity, vcp_score, total_score (stock_scores_history PIT ffill)
  global_rank_20 (parquet Oracle, percentile 0..1, 1 = meilleur B25)
  sentiment_net_mean_1d (ticker_daily_sentiment_features, contrôle)

Par feature x période (2022/2023/2024/2025/2026H1/ALL) : AUC UP vs DOWN, mean/median UP vs DOWN,
effect size (Cohen d), coverage. Orientation économique attendue :
  trend_score ↑ -> UP ; short_score ↑ -> DOWN ; sentiment ↑ -> UP ; global_rank_20 ↑ -> UP (relatif!)
  historical_range -> à mesurer.
Pour short_score : AUC < 0.5 est un BON résultat bearish (inverser l'interprétation).

Gate strict (comme D0/D1/D1b) : AUC hors [0.47, 0.53] ET signe/effect stable 2022->2026H1 -> D2 ;
sinon NO-GO branche direction.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

ROOT = Path(__file__).resolve().parents[1]
TOP_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"
OUT = ROOT / "artifacts" / "d1d_direction_absolue.md"

try:
    from sklearn.metrics import roc_auc_score
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]

# Features + orientation économique attendue du signe (mean UP - mean DOWN)
#   "+" : feature ↑ -> UP ;  "-" : feature ↑ -> DOWN ;  "?" : à mesurer
SCORE_FEATURES = [
    ("short_score", "-"),
    ("trend_score", "+"),
    ("weekly_trend_score", "+"),
    ("relative_strength_index", "+"),
    ("historical_range_score", "?"),
    ("high_52w_proximity", "+"),
    ("vcp_score", "+"),
    ("total_score", "+"),
]


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
    df = pd.read_parquet(TOP_PQ)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["period"] = np.where(df["year"] < 2026, df["year"].astype(str), "2026H1")
    df["oracle_rank"] = df.groupby("date")["proba_top"].rank(pct=True)

    # Pool Oracle predicted extreme (top décile P_top)
    pool = df[df["oracle_rank"] >= 0.9].copy()

    # Target direction ABSOLUE : UP = >0, DOWN = <0, exclut ==0
    pool["direction"] = np.where(pool["future_return"] > 0, 1, np.where(pool["future_return"] < 0, 0, np.nan))
    dirsub = pool.dropna(subset=["direction"]).copy()
    dirsub["direction"] = dirsub["direction"].astype(int)
    print(f"Pool Oracle extrême: {len(pool):,} | direction UP/DOWN (absolu, ==0 exclu): {len(dirsub):,} "
          f"(UP {int((dirsub['direction']==1).sum())} / DOWN {int((dirsub['direction']==0).sum())}) "
          f"[exclu zero: {int(pool['direction'].isna().sum())}]")

    # ── Charger stock_scores_history PIT (forward-fill) ──
    eng = get_sqlalchemy_engine()
    score_cols = [f for f, _ in SCORE_FEATURES]
    with eng.connect() as c:
        avail = {r[0] for r in c.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='alpha_trade' "
            "AND TABLE_NAME='stock_scores_history'")).fetchall()}
    avail_cols = [f for f in score_cols if f in avail]
    missing = [f for f in score_cols if f not in avail]
    if missing:
        print(f"  [warn] colonnes absentes stock_scores_history: {missing}")
    dmin = pool["date"].min().date()
    dmax = pool["date"].max().date()
    with eng.connect() as c:
        s = pd.read_sql(text(
            f"SELECT snapshot_date, symbol, {', '.join(avail_cols)} FROM stock_scores_history "
            "WHERE snapshot_date BETWEEN :d1 AND :d2"
        ), c, params={"d1": dmin, "d2": dmax}, parse_dates=["snapshot_date"])
    s["symbol"] = s["symbol"].astype(str)
    print(f"stock_scores_history: {len(s):,} lignes | {s['snapshot_date'].min().date()} -> {s['snapshot_date'].max().date()}")

    # ── Charger sentiment PIT (contrôle) sur (symbol, date) ──
    symbols = sorted(pool["symbol"].astype(str).unique().tolist())
    sent_parts = []
    for i in range(0, len(symbols), 500):
        chunk = symbols[i:i + 500]
        ph = ",".join(f":s{j}" for j in range(len(chunk)))
        params = {f"s{j}": sym for j, sym in enumerate(chunk)}
        params["d1"] = dmin
        params["d2"] = dmax
        with eng.connect() as c:
            part = pd.read_sql(text(
                f"SELECT symbol, trade_date, sentiment_net_mean_1d FROM ticker_daily_sentiment_features "
                f"WHERE symbol IN ({ph}) AND trade_date BETWEEN :d1 AND :d2"
            ), c, params=params, parse_dates=["trade_date"])
        sent_parts.append(part)
    sent = pd.concat(sent_parts, ignore_index=True) if sent_parts else pd.DataFrame(columns=["symbol", "trade_date"])
    sent["symbol"] = sent["symbol"].astype(str)
    print(f"sentiment: {len(sent):,} lignes sentiment_net_mean_1d")

    # ── Merge PIT forward-fill par (symbol, snapshot_date <= date) ──
    swide = s.pivot_table(index="snapshot_date", columns="symbol", values=avail_cols).sort_index()
    pool_dates = sorted(pool["date"].unique())
    m = dirsub.copy()
    for f in avail_cols:
        wide = swide[f].reindex(pool_dates).ffill()
        s_long = wide.stack()
        m[f] = [s_long.get((d, sym), np.nan) for d, sym in zip(m["date"], m["symbol"])]
    # sentiment : merge sur date exacte (PIT au jour)
    sent["trade_date"] = pd.to_datetime(sent["trade_date"])
    sent_map = sent.drop_duplicates(["symbol", "trade_date"]).set_index(["symbol", "trade_date"])["sentiment_net_mean_1d"]
    m["sentiment_net_mean_1d"] = [sent_map.get((sym, d), np.nan) for sym, d in zip(m["symbol"], m["date"])]
    print(f"Merge PIT: {len(m):,} | cov short_score: {m['short_score'].notna().mean()*100:.1f}% | "
          f"cov total_score: {m['total_score'].notna().mean()*100:.1f}% | "
          f"cov global_rank_20: {m['global_rank_20'].notna().mean()*100:.1f}% | "
          f"cov sentiment: {m['sentiment_net_mean_1d'].notna().mean()*100:.1f}%")

    # ── Features à tester : scores + global_rank_20 + sentiment contrôle ──
    # global_rank_20 : percentile 0..1, 1 = meilleur B25 -> orientation attendue "+"
    features = [(f, exp) for f, exp in SCORE_FEATURES if f in avail_cols]
    features += [("global_rank_20", "+"), ("sentiment_net_mean_1d", "+")]

    md: list[str] = [
        "# D1d — Direction ABSOLUE conditionnelle aux extrêmes (pool Oracle predicted extreme)",
        "",
        f"Pool = Oracle predicted extreme (top décile P_top, {len(pool):,} obs).",
        f"Target direction ABSOLUE : UP = H20 return > 0 ({int((dirsub['direction']==1).sum())}), "
        f"DOWN = H20 return < 0 ({int((dirsub['direction']==0).sum())}), ==0 exclu ({int(pool['direction'].isna().sum())}).",
        "Aucun seuil optimisé, aucun modèle ML — diagnostic univarié. ",
        "Orientation attendue : trend_score/high_52w/vcp/total/global_rank_20/sentiment ↑ -> UP (+) ; short_score ↑ -> DOWN (-) ; historical_range à mesurer.",
        "",
    ]

    # Couverture par période
    md.append("## Couverture par période")
    md.append("")
    md.append("| période | N | cov short_score | cov total_score | cov grank20 | cov sentiment |")
    md.append("|---|---|---|---|---|---|")
    for p in PERIODS:
        sub = m if p == "ALL" else m[m["period"] == p]
        md.append(f"| {p} | {len(sub):,} | {sub['short_score'].notna().mean()*100:.1f}% | "
                  f"{sub['total_score'].notna().mean()*100:.1f}% | "
                  f"{sub['global_rank_20'].notna().mean()*100:.1f}% | "
                  f"{sub['sentiment_net_mean_1d'].notna().mean()*100:.1f}% |")
    md.append("")

    # AUC par feature x période
    md.append("## AUC (UP vs DOWN) par feature x période")
    md.append("")
    md.append("| feature | " + " | ".join(PERIODS) + " |")
    md.append("|" + "---|" * (len(PERIODS) + 1) + "|")
    sign_rows: dict[str, list[int]] = {}
    for f, exp in features:
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
    md.append("## Détail (ALL) — direction UP vs DOWN")
    md.append("")
    md.append("| feature | N | coverage | AUC | AUC orienté | mean UP | mean DOWN | médian UP | médian DOWN | Cohen d | signe (UP-DOWN) | attendu |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for f, exp in features:
        sub = m
        t = sub[sub["direction"] == 1][f]
        b = sub[sub["direction"] == 0][f]
        if t.notna().sum() < 30 or b.notna().sum() < 30:
            md.append(f"| {f} | {len(sub):,} | - | - | - | - | - | - | - | - | - | - |")
            continue
        a = _auc(sub["direction"], sub[f])
        d = _cohen_d(t, b)
        cov = sub[f].notna().mean()
        sign_obs = "+" if (t.mean() - b.mean()) > 0 else "-"
        # AUC orienté : si attendu "+", AUC tel quel ; si attendu "-" (short_score), AUC inversé 1-a
        a_or = a if exp == "+" else (1 - a if exp == "-" else a)
        match = ""
        if exp in ("+", "-"):
            match = "OK" if sign_obs == exp else "INVERSÉ"
        md.append(f"| {f} | {len(sub):,} | {cov*100:.1f}% | {_fmt(a)} | {_fmt(a_or)} | "
                  f"{t.mean():+.4f} | {b.mean():+.4f} | {t.median():+.4f} | {b.median():+.4f} | "
                  f"{_fmt(d)} | {sign_obs} | {exp} {match} |")

    # Stabilité + gate
    md.append("")
    md.append("## Stabilité du signe + gate (AUC orienté > 0.53 ET signe stable)")
    md.append("")
    md.append("| feature | signe par période | stable ? | AUC ALL orienté | gate |")
    md.append("|---|---|---|---|---|")
    passed = []
    for f, exp in features:
        signs = sign_rows.get(f, [])
        sub = m
        a = _auc(sub["direction"], sub[f])
        exp_int = 1 if exp == "+" else -1
        # AUC orienté vers l'hypothèse attendue
        a_or = a if exp == "+" else (1 - a if exp == "-" else a)
        stable = signs and len(signs) == len(PERIODS) - 1 and len(set(signs)) == 1
        orient_ok = stable and signs[0] == exp_int
        ok = stable and orient_ok and not np.isnan(a_or) and a_or > 0.53
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
        md.append(f"| {f} | {' '.join(cells)} | {'OUI' if stable else 'NON'} | {_fmt(a_or)} | {gate} |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nRapport:", OUT)
    print("\n--- RESUME D1d (direction absolue UP vs DOWN, pool Oracle extrême) ---")
    for f, exp in features:
        sub = m
        a = _auc(sub["direction"], sub[f])
        a_or = a if exp == "+" else (1 - a if exp == "-" else a)
        signs = sign_rows.get(f, [])
        stable = signs and len(signs) == len(PERIODS) - 1 and len(set(signs)) == 1
        exp_int = 1 if exp == "+" else -1
        orient_ok = stable and signs[0] == exp_int
        cov = sub[f].notna().mean() * 100
        print(f"  {f:26s} AUC={_fmt(a):>6s}  AUC_orient={_fmt(a_or):>6s}  cov={cov:5.1f}%  stable={stable}  orient={orient_ok}")
    print(f"\nGate D1d — features AUC orienté>0.53 + signe stable + orientation OK: {passed if passed else 'AUCUN'}")
    if not passed:
        print("=> NO-GO direction absolue (aucun signal directionnel stable dans le pool Oracle extrême).")


if __name__ == "__main__":
    main()
