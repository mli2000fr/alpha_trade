"""D1 — Sentiment comme discriminateur de direction dans le pool Oracle extrême.

Hypothèse : le sentiment (ticker_daily_sentiment_features, PIT à D) sépare-t-il les
vrais TOP10 des vrais BOTTOM10 PARMI les observations qu'Oracle juge extrêmes ?

Pool = Oracle predicted extreme : `oracle_rank >= 0.9` (top décile de proba_top).
Direction target (historique) : 1 = vrai TOP10 (true_decile==10), 0 = vrai BOTTOM10
(true_decile==1). D2-D9 EXCLUS du diagnostic de direction (comme D0).

Audit UNIVARIÉ (aucun modèle complexe) par feature × période (2022/2023/2024/2025/2026H1/ALL) :
  N, coverage %, AUC (TOP vs BOTTOM), mean/median TOP, mean/median BOTTOM,
  effect size (Cohen's d), signe (moyenne TOP - moyenne BOTTOM).
Métrique ORIENTATION : le signe (moyenne TOP - moyenne BOTTOM) doit être COHÉRENT
(sentiment + -> TOP, sentiment - -> BOTTOM) et STABLE sur toutes les périodes.

Gate strict : D2 seulement si AUC > 0.5 ET signe stable sur toutes les périodes ;
sinon NO-GO et arrêt de la branche sentiment.
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
OUT = ROOT / "artifacts" / "d1_sentiment_direction.md"

try:
    from sklearn.metrics import roc_auc_score
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

PERIODS = ["2022", "2023", "2024", "2025", "2026H1", "ALL"]

# Features du plan D1 (§12) — seulement celles qui existent dans la table
CANDIDATE_FEATURES = [
    "sentiment_net_mean_1d", "sentiment_net_mean_3d", "sentiment_net_mean_5d",
    "sentiment_net_mean_10d", "sentiment_net_mean_20d",
    "sentiment_confidence_mean_1d",
    "news_count_1d", "news_count_5d", "news_count_20d",
    "major_event_flag",
]

DERIVED = [
    ("sentiment_change_1_5", lambda d: d["sentiment_net_mean_1d"] - d["sentiment_net_mean_5d"]),
    ("sentiment_change_5_20", lambda d: d["sentiment_net_mean_5d"] - d["sentiment_net_mean_20d"]),
    ("sentiment_intensity", lambda d: d["sentiment_net_mean_1d"] * d["sentiment_confidence_mean_1d"] * np.log1p(d["news_count_1d"].fillna(0))),
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


def _fmt_pct(x) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:.1f}%"


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

    # Pool Oracle extrême
    pool = df[df["oracle_rank"] >= 0.9].copy()
    # Direction : TOP vs BOTTOM (D2-D9 exclus)
    dirsub = pool[pool["true_decile"].isin([1, 10])].copy()
    dirsub["direction"] = (dirsub["true_decile"] == 10).astype(int)

    print(f"Pool Oracle extrême: {len(pool):,} obs | direction (TOP/BOTTOM): {len(dirsub):,} "
          f"(TOP {int((dirsub['direction']==1).sum())} / BOT {int((dirsub['direction']==0).sum())})")

    # ── Charger le sentiment PIT pour le pool ──
    eng = get_sqlalchemy_engine()
    symbols = sorted(pool["symbol"].astype(str).unique().tolist())
    dmin = pool["date"].min() - pd.Timedelta(days=0)
    dmax = pool["date"].max()
    avail_cols = []
    with eng.connect() as c:
        cols = [r[0] for r in c.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='alpha_trade' "
            "AND TABLE_NAME='ticker_daily_sentiment_features'")).fetchall()]
    avail_cols = set(cols)
    feats = [f for f in CANDIDATE_FEATURES if f in avail_cols]
    select_cols = ["symbol", "trade_date"] + feats
    print(f"Colonnes sentiment chargées: {feats}")
    # chunks de symboles pour éviter des IN trop longs
    sent_parts = []
    for i in range(0, len(symbols), 500):
        chunk = symbols[i:i + 500]
        placeholders = ",".join(f":s{j}" for j in range(len(chunk)))
        params = {f"s{j}": s for j, s in enumerate(chunk)}
        q = (f"SELECT symbol, trade_date, {', '.join(feats)} FROM ticker_daily_sentiment_features "
             f"WHERE symbol IN ({placeholders}) AND trade_date BETWEEN :d1 AND :d2")
        params["d1"] = dmin.date()
        params["d2"] = dmax.date()
        with eng.connect() as c:
            part = pd.read_sql(text(q), c, params=params, parse_dates=["trade_date"])
        sent_parts.append(part)
    sent = pd.concat(sent_parts, ignore_index=True) if sent_parts else pd.DataFrame(columns=["symbol", "trade_date"])
    sent["symbol"] = sent["symbol"].astype(str)
    sent["trade_date"] = pd.to_datetime(sent["trade_date"])

    # merge sur (symbol, date)
    dirsub["_d"] = pd.to_datetime(dirsub["date"])
    m = dirsub.merge(sent, left_on=["symbol", "_d"], right_on=["symbol", "trade_date"], how="left")
    print(f"Merge sentiment: {len(m):,} lignes | coverage sentiment_net_mean_1d: "
          f"{m['sentiment_net_mean_1d'].notna().mean()*100:.1f}%")

    # features dérivées
    for name, fn in DERIVED:
        try:
            m[name] = fn(m)
        except Exception:
            m[name] = np.nan

    all_feats = feats + [name for name, _ in DERIVED if name in m.columns]

    md: list[str] = [
        "# D1 — Sentiment comme discriminateur de direction (pool Oracle extrême)",
        "",
        f"Pool = Oracle predicted extreme (top décile P_top, {len(pool):,} obs). "
        f"Direction : vrai TOP10 ({int((dirsub['direction']==1).sum())}) vs vrai BOTTOM10 ({int((dirsub['direction']==0).sum())}), D2-D9 exclus.",
        "Aucun modèle complexe — audit univarié. Gate strict : AUC > 0.5 ET signe stable sur toutes les périodes.",
        "",
    ]

    # couverture par période (net_1d) — obligatoire avant toute conclusion
    cov_period = {}
    for p in PERIODS:
        s = m if p == "ALL" else m[m["period"] == p]
        cov_period[p] = (s["sentiment_net_mean_1d"].notna().mean() if len(s) else 0.0)
    md.append("## Couverture sentiment_net_mean_1d (pool extrême) par période")
    md.append("")
    md.append("| période | N pool | coverage net_1d |")
    md.append("|---|---|---|")
    for p in PERIODS:
        s = m if p == "ALL" else m[m["period"] == p]
        md.append(f"| {p} | {len(s):,} | {cov_period[p]*100:.1f}% |")
    md.append("")

    # table par feature × période : AUC + orientation
    md.append("## AUC (TOP vs BOTTOM) par feature × période")
    md.append("")
    md.append("| feature | " + " | ".join(PERIODS) + " |")
    md.append("|" + "---|" * (len(PERIODS) + 1) + "|")
    orientation_report: list[str] = []
    for f in all_feats:
        row_auc = []
        signs = []
        for p in PERIODS:
            s = m if p == "ALL" else m[m["period"] == p]
            s = s[s["true_decile"].isin([1, 10])]
            if len(s) < 30:
                row_auc.append("-")
                continue
            a = _auc(s["direction"], s[f])
            row_auc.append(_fmt(a))
            t = s[s["direction"] == 1][f]
            b = s[s["direction"] == 0][f]
            if t.notna().sum() >= 10 and b.notna().sum() >= 10:
                signs.append(1 if (t.mean() - b.mean()) > 0 else -1)
        md.append("| " + f + " | " + " | ".join(row_auc) + " |")
        # orientation : signe stable ?
        n_pos = signs.count(1)
        n_neg = signs.count(-1)
        stable = (n_pos == len(signs)) or (n_neg == len(signs))
        orientation_report.append((f, signs, stable, n_pos, n_neg))

    # Détail feature par feature : AUC, moyens, médianes, cohen d, signe par période
    md.append("")
    md.append("## Détail par feature (ALL) — direction TOP vs BOTTOM")
    md.append("")
    md.append("| feature | N | coverage | AUC | mean TOP | mean BOT | médian TOP | médian BOT | Cohen d | signe (TOP-BOT) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")
    for f in all_feats:
        s = m[m["true_decile"].isin([1, 10])]
        t = s[s["direction"] == 1][f]
        b = s[s["direction"] == 0][f]
        if t.notna().sum() < 30 or b.notna().sum() < 30:
            md.append(f"| {f} | {len(s):,} | - | - | - | - | - | - | - | - |")
            continue
        a = _auc(s["direction"], s[f])
        d = _cohen_d(t, b)
        cov = s[f].notna().mean()
        md.append(f"| {f} | {len(s):,} | {cov*100:.1f}% | {_fmt(a)} | {t.mean():+.4f} | {b.mean():+.4f} | "
                  f"{t.median():+.4f} | {b.median():+.4f} | {_fmt(d)} | {'+' if (t.mean()-b.mean())>0 else '-'} |")

    # stabilité du signe (orientation) par feature
    md.append("")
    md.append("## Orientation (signe de mean TOP - mean BOT) par feature × période")
    md.append("")
    md.append("| feature | " + " | ".join(PERIODS[:-1]) + " | stable ? |")
    md.append("|" + "---|" * (len(PERIODS) + 1) + "|")
    for f, signs, stable, npos, nneg in orientation_report:
        if not signs:
            md.append(f"| {f} | - | - | - | - | - | NON (insuffisant) |")
            continue
        cells = []
        si = 0
        for p in PERIODS:
            s = m if p == "ALL" else m[m["period"] == p]
            s = s[s["true_decile"].isin([1, 10])]
            t = s[s["direction"] == 1][f]
            b = s[s["direction"] == 0][f]
            if t.notna().sum() >= 10 and b.notna().sum() >= 10:
                cells.append("+" if (t.mean() - b.mean()) > 0 else "-")
            else:
                cells.append("·")
        md.append(f"| {f} | " + " | ".join(cells) + f" | {'OUI' if stable else 'NON'} |")

    # Orientation correcte : pour les features de POLARITÉ (net_mean / change / intensity),
    # le signe doit être POSITIF (sentiment + -> TOP). news/confidence non-polarité -> sans objet.
    polarity_feats = ["sentiment_net_mean_1d", "sentiment_net_mean_3d", "sentiment_net_mean_5d",
                      "sentiment_net_mean_10d", "sentiment_net_mean_20d",
                      "sentiment_change_1_5", "sentiment_change_5_20", "sentiment_intensity"]
    md.append("")
    md.append("## Orientation CORRECTE (polarité : sentiment + -> TOP) — AUC ALL + signe moyen")
    md.append("")
    md.append("| feature | AUC ALL | signe moyen (TOP-BOT) | orientation correcte ? |")
    md.append("|---|---|---|---|")
    for f, signs, stable, npos, nneg in orientation_report:
        s = m[m["true_decile"].isin([1, 10])]
        a = _auc(s["direction"], s[f]) if len(s) >= 30 else float("nan")
        if f in polarity_feats:
            ok = (not np.isnan(a)) and a > 0.5 and npos > nneg
            md.append(f"| {f} | {_fmt(a)} | {'+' if npos > nneg else '-'} | {'OUI' if ok else 'NON'} |")
        else:
            md.append(f"| {f} | {_fmt(a)} | {'+' if npos > nneg else '-'} | (non polarité) |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("\nRapport écrit:", OUT)

    # Résumé console + gate
    print("\n--- RESUME D1 (AUC ALL + signe stable) ---")
    passed = []
    for f, signs, stable, npos, nneg in orientation_report:
        s = m[m["true_decile"].isin([1, 10])]
        a = _auc(s["direction"], s[f]) if len(s) >= 30 else float("nan")
        sig = "STABLE+" if (stable and signs and signs[0] == 1) else ("STABLE-" if (stable and signs and signs[0] == -1) else "INSTABLE")
        if stable and not np.isnan(a) and a > 0.5:
            passed.append(f)
        print(f"  {f:28s} AUC={_fmt(a):>6s}  {sig}")
    print(f"\nGate D1 — features AUC>0.5 ET signe stable: {passed if passed else 'AUCUN'}")
    if not passed:
        print("=> NO-GO branche sentiment (aucun signal directionnel stable). Stop.")


if __name__ == "__main__":
    main()
