"""E11 — Extreme LONG Payoff & Selection Diagnostic (ZERO optimisation).

SPEC user 2026-08-20 (A->B->C->D, diagnostic pur, aucun tuning) :
  - Univers gelee : Oracle O0 -> Extreme TOP20 LONG (proba_extreme top20%),
    memes donnees OOF, memes couts/lifecycle m8 que E10.
  - AUCUN nouveau TP/SL/trailing, AUCUN nouveau selecteur, PAS de SHORT.

E11-A : Expliquer 2026H1 (run representatif seed 7).
  expectancy/PF, MFE/MAE, ratio MFE/MAE, exit reason, duree avant TP/stop,
  MFE avant stop, retour J+3/5/10 apres stop, fraction des stops qui auraient
  ensuite atteint +5/+7/+10/+13%, vraies erreurs (MFE<3%) vs lifecycle (MFE>5/7%).
  Question : 2026H1 = mauvais candidats Extreme, ou bons mouvements mal monetises ?

E11-B : Expliquer la variance des 20 seeds.
  Par seed : PnL, top1/5/10/20 %PnL, gros winners (>10/20%), gros losers,
  PnL 2026H1, overlap des trades (Jaccard) entre meilleur/median/pire seed.
  Puis distribution fat-tail du pool par jour (kurtosis, part du top-1 mover).
  Question : m8 echantillonne-t-il quelques gros movers d'une distribution
  tres fat-tailed ?

E11-C : Test de capacite sans optimisation.
  m8 actuel vs equal-weight de TOUS les candidats Extreme (proxy pool complet).
  Pool equal-weight stable + m8 variable -> concentration/capacite (E12 sizing).
  Pool equal-weight instable -> signal/lifecycle (E12 exits ou NO-TRADE).

E11-D : Attribution exits.
  TP / trailing / initial stop / time_stop : n, PnL$, expectancy, MFE/MAE,
  excursion post-sortie, contribution par semestre. Expliquer la structure
  TP +376k vs trailing -178k vs stop -115k (structure, pas montant exact).

Sortie : print + artifacts/models/oracle/e11_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.simulator import BacktestConfig, BacktestEngine
from scripts.e6_b2_ev_long_backtest import (
    END,
    START,
    load_pivots,
    load_pool,
)

PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e11_results.parquet")
INITIAL_EQUITY = 100_000.0
N_SEEDS = 20
SEED_REP = 7
GOOD_SEMS = ("2023H1", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2")
BAD_SEM = "2026H1"
COST = 0.0016
REASONS = ("take_profit", "trailing_stop", "initial_stop", "time_stop")


# ---------------------------------------------------------------------------
# Moteur / signaux / run (identiques a E10)
# ---------------------------------------------------------------------------

def make_engine() -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY, max_positions=8,
        atr_risk_stop_multiple=3.5, tp_atr_multiple=4.0, tp_max_pct=0.13,
        trailing_stop_long_pct=0.07, trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
    )
    return BacktestEngine(cfg)


def build_signals(pool: pd.DataFrame, lo: float, hi: float, seed: int) -> pd.DataFrame:
    df = pool.copy()
    df["_pe_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df = df[(df["_pe_pct"] >= lo) & (df["_pe_pct"] < hi)]
    rng = np.random.default_rng(seed)
    df["_rand"] = rng.random(len(df))
    df["rank"] = df.groupby("date")["_rand"].rank(ascending=False)
    df["score"] = df["proba_extreme"]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


def run_bt(pool: pd.DataFrame, pivots: dict, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    sig = build_signals(pool, 0.80, 1.01, seed)
    res = make_engine().run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    eq = res.equity_curve
    closed = res.closed_trades_df.copy()
    closed["signal_date"] = pd.to_datetime(closed["signal_date"]).dt.normalize()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"]).dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"]).dt.normalize()
    closed["symbol"] = closed["symbol"].astype(str)
    closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
    closed["return_pct"] = pd.to_numeric(closed["return_pct"], errors="coerce").fillna(0.0)
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    closed["holding"] = (closed["exit_date"] - closed["entry_date"]).dt.days
    return closed, eq


def attach_path(closed: pd.DataFrame, path: pd.DataFrame) -> pd.DataFrame:
    c = closed.merge(path[["symbol", "date", "y3_long_mfe", "y3_long_mae"]],
                     left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")
    c["mfe"] = pd.to_numeric(c["y3_long_mfe"], errors="coerce")
    c["mae"] = pd.to_numeric(c["y3_long_mae"], errors="coerce")
    return c


# ---------------------------------------------------------------------------
# Retours / excursion post-sortie (cache OHLC)
# ---------------------------------------------------------------------------

def post_exit_info(closed: pd.DataFrame, px_close: pd.DataFrame, px_high: pd.DataFrame) -> pd.DataFrame:
    """Retour J+3/5/10 (close-to-close) + max HIGH J+1..J+10 apres la sortie."""
    rows: list[dict] = []
    for sym, g in closed.groupby("symbol"):
        if sym not in px_close.columns:
            continue
        cc = px_close[sym].dropna()
        hh = px_high[sym].reindex(cc.index).ffill()
        idx = cc.index
        for _, r in g.iterrows():
            pos = idx.searchsorted(r["exit_date"], side="left")
            if pos >= len(idx):
                continue
            if idx[pos] != r["exit_date"]:
                if pos == 0:
                    continue
                pos -= 1
            base = float(cc.iloc[pos])
            if base <= 0:
                continue
            row = {"symbol": sym, "exit_date": r["exit_date"], "semester": r["semester"],
                   "exit_reason": r["exit_reason"], "pnl": r["pnl"]}
            for k in (3, 5, 10):
                j = pos + k
                row[f"ret_J{k}"] = float(cc.iloc[j] / base - 1.0) if j < len(idx) else float("nan")
            hi = -1.0
            for j in range(pos + 1, min(pos + 11, len(idx))):
                v = float(hh.iloc[j])
                if not np.isnan(v):
                    hi = max(hi, v)
            row["fwd_hi"] = hi if hi > 0 else float("nan")
            for th in (5, 7, 10, 13):
                row[f"hit_{th}"] = int(1) if (not np.isnan(row["fwd_hi"]) and row["fwd_hi"] >= base * (1 + th / 100.0)) else int(0)
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# E11-A : expliquer 2026H1
# ---------------------------------------------------------------------------

def _pf(ser: pd.Series) -> float:
    gp = float(ser[ser > 0].sum())
    gn = float(-ser[ser < 0].sum())
    return gp / gn if gn > 0 else float("inf")


def _ratio(g: pd.DataFrame) -> float:
    mf = g["mfe"].median()
    return abs(g["mae"].median() / mf) if mf and not np.isnan(mf) else float("nan")


def section_A(c: pd.DataFrame, post: pd.DataFrame) -> None:
    print("\n" + "=" * 132)
    print("E11-A  EXPLIQUER 2026H1  (run representatif EXTREME_TOP20 seed %d)" % SEED_REP)
    print("=" * 132)

    # A0. Vue d'ensemble par semestre
    print("\n  A0. Vue d'ensemble par semestre :")
    hdr = (f"  {'sem':<8} {'n':>4} {'PnL$':>9} {'Exp$':>7} {'PF':>5} {'medMFE%':>8} "
           f"{'medMAE%':>8} {'MAE/MFE':>7} {'medDurJ':>7} | {'TP%':>5} {'tr%':>5} {'st%':>5} {'tme%':>5}")
    print(hdr)
    print("-" * len(hdr))
    for sem in sorted(c["semester"].unique()):
        g = c[c["semester"] == sem]
        d = {"sem": sem, "n": len(g), "pnl": g["pnl"].sum(), "exp": g["pnl"].mean(),
             "pf": _pf(g["pnl"]), "mfe": 100 * g["mfe"].median(), "mae": 100 * g["mae"].median(),
             "ratio": _ratio(g), "dur": g["holding"].median()}
        for r in REASONS:
            d[r] = 100 * (g["exit_reason"] == r).mean()
        print(f"  {sem:<8} {d['n']:>4} {d['pnl']:>9.0f} {d['exp']:>7.0f} {d['pf']:>5.2f} "
              f"{d['mfe']:>7.2f}% {d['mae']:>7.2f}% {d['ratio']:>7.2f} {d['dur']:>7.1f} | "
              f"{d['take_profit']:>4.0f}% {d['trailing_stop']:>4.0f}% {d['initial_stop']:>4.0f}% {d['time_stop']:>4.0f}%")

    # A1. Duree avant TP vs avant stop, par semestre
    print("\n  A1. Duree (jours) avant TP vs avant stop, par semestre :")
    print(f"  {'sem':<8} {'medDur TP':>10} {'medDur stop':>12} {'nTP':>4} {'nStop':>6}")
    for sem in sorted(c["semester"].unique()):
        g = c[c["semester"] == sem]
        tp = g[g["exit_reason"] == "take_profit"]["holding"]
        st = g[g["exit_reason"].isin(["initial_stop", "trailing_stop"])]["holding"]
        print(f"  {sem:<8} {tp.median():>10.1f} {st.median():>12.1f} {len(tp):>4} {len(st):>6}")

    # A2. Fausses alertes, vraies erreurs, probleme lifecycle par semestre
    print("\n  A2. Qualite des entrees (run seed %d) :" % SEED_REP)
    print(f"  {'sem':<8} {'FA(<2%)':>7} {'FA%':>5} {'PnL_FA$':>9} | "
          f"{'err<3%':>6} {'PnL$':>8} | {'lf>5%':>6} {'PnL$':>8} | {'lf>7%':>6} {'PnL$':>8}")
    for sem in sorted(c["semester"].unique()):
        g = c[c["semester"] == sem]
        fa = g[g["mfe"] < 0.02]
        err = g[(g["pnl"] < 0) & (g["mfe"] < 0.03)]
        lf5 = g[(g["pnl"] < 0) & (g["mfe"] >= 0.05)]
        lf7 = g[(g["pnl"] < 0) & (g["mfe"] >= 0.07)]
        print(f"  {sem:<8} {len(fa):>7} {100*len(fa)/len(g):>4.0f}% {fa['pnl'].sum():>9.0f} | "
              f"{len(err):>6} {err['pnl'].sum():>8.0f} | "
              f"{len(lf5):>6} {lf5['pnl'].sum():>8.0f} | "
              f"{len(lf7):>6} {lf7['pnl'].sum():>8.0f}")

    # A3. Stops : MFE avant stop, duree, retour post-sortie, "auraient atteint +k%"
    stops = c[c["exit_reason"].isin(["initial_stop", "trailing_stop"])].copy()
    pst = post[post["exit_reason"].isin(["initial_stop", "trailing_stop"])].copy()
    m = stops.merge(pst, on=["symbol", "exit_date", "semester", "exit_reason", "pnl"], how="left")
    print("\n  A3. Stops (initial+trailing) : MFE avant stop / post-sortie / auraient atteint +k% :")
    print(f"  {'groupe':<9} {'n':>4} {'medMFE%':>8} {'medDurJ':>8} {'J+3%':>7} {'J+5%':>7} "
          f"{'J+10%':>8} {'%J10>0':>7} | {'+5%':>5} {'+7%':>5} {'+10%':>6} {'+13%':>6}")
    for label, mask in [("GOOD", m["semester"].isin(GOOD_SEMS)), ("2026H1", m["semester"] == BAD_SEM),
                        ("TOUT", pd.Series(True, index=m.index))]:
        g = m[mask]
        if g.empty or g["mfe"].isna().all():
            continue
        print(f"  {label:<9} {len(g):>4} {100*g['mfe'].median():>7.2f}% {g['holding'].median():>8.1f} "
              f"{100*g['ret_J3'].median():>6.2f}% {100*g['ret_J5'].median():>6.2f}% "
              f"{100*g['ret_J10'].median():>7.2f}% {100*(g['ret_J10']>0).mean():>6.0f}% | "
              f"{100*g['hit_5'].mean():>4.0f}% {100*g['hit_7'].mean():>4.0f}% "
              f"{100*g['hit_10'].mean():>5.0f}% {100*g['hit_13'].mean():>5.0f}%")

    # A4. Winners coupes avant maturation (MFE>=8% mais PnL<0)
    print("\n  A4. Winners coupes avant maturation (MFE >= +8% mais PnL < 0) par reason :")
    wc = c[(c["mfe"] >= 0.08) & (c["pnl"] < 0)]
    if wc.empty:
        print("  (aucun)")
    else:
        print(f"  {'reason':<16} {'n':>4} {'PnL$':>9} {'medMFE%':>8} {'medMAE%':>8}")
        for reason, g in wc.groupby("exit_reason"):
            print(f"  {reason:<16} {len(g):>4} {g['pnl'].sum():>9.0f} "
                  f"{100*g['mfe'].median():>7.2f}% {100*g['mae'].median():>7.2f}%")


# ---------------------------------------------------------------------------
# E11-B : expliquer la variance des 20 seeds
# ---------------------------------------------------------------------------

def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return float("nan")
    return len(a & b) / len(a | b)


def section_B(per_seed: list[dict], pool: pd.DataFrame) -> None:
    print("\n" + "=" * 132)
    print("E11-B  EXPLIQUER LA VARIANCE DES %d SEEDS" % N_SEEDS)
    print("=" * 132)

    # B1. Table par seed
    recs = []
    for p in per_seed:
        c, eq = p["closed"], p["eq"]
        pnl = c["pnl"]
        total = float(pnl.sum())
        gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
        pf = gp / gn if gn > 0 else float("inf")
        ret = (float(eq.iloc[-1]) / INITIAL_EQUITY - 1.0) * 100.0
        srt = pnl.sort_values(ascending=False)
        recs.append({"seed": p["seed"], "pnl": total, "ret": ret, "pf": pf, "n": len(c),
                     "top1": 100 * srt.head(1).sum() / total if total else 0.0,
                     "top5": 100 * srt.head(5).sum() / total if total else 0.0,
                     "top10": 100 * srt.head(10).sum() / total if total else 0.0,
                     "top20": 100 * srt.head(20).sum() / total if total else 0.0,
                     "nW10": int((c["return_pct"] > 10).sum()),
                     "nW20": int((c["return_pct"] > 20).sum()),
                     "nL10": int((c["return_pct"] < -10).sum()),
                     "s26": float(c[c["semester"] == BAD_SEM]["pnl"].sum())})
    dfr = pd.DataFrame(recs)
    print("\n  B1. Metriques par seed (EXTREME_TOP20, m8) :")
    print(f"  {'seed':>4} {'PnL$':>9} {'Ret%':>7} {'PF':>5} {'n':>4} {'top1%':>6} {'top5%':>6} "
          f"{'top10%':>7} {'top20%':>7} {'W>10':>5} {'W>20':>5} {'L<-10':>6} {'s26$':>9}")
    for _, r in dfr.iterrows():
        print(f"  {int(r['seed']):>4} {r['pnl']:>9.0f} {r['ret']:>7.1f} {r['pf']:>5.2f} {int(r['n']):>4} "
              f"{r['top1']:>5.0f}% {r['top5']:>5.0f}% {r['top10']:>6.0f}% {r['top20']:>6.0f}% "
              f"{int(r['nW10']):>5} {int(r['nW20']):>5} {int(r['nL10']):>6} {r['s26']:>9.0f}")
    med = dfr.median()
    print(f"  {'med':>4} {med['pnl']:>9.0f} {med['ret']:>7.1f} {med['pf']:>5.2f} {med['n']:>4.0f} "
          f"{med['top1']:>5.0f}% {med['top5']:>5.0f}% {med['top10']:>6.0f}% {med['top20']:>6.0f}% "
          f"{med['nW10']:>5.0f} {med['nW20']:>5.0f} {med['nL10']:>6.0f} {med['s26']:>9.0f}")
    print(f"  {f'seeds 2026H1 positifs : {(dfr["s26"]>0).mean()*100:.0f}%'}")
    print(f"  {f'dispersion Ret : P10={dfr["ret"].quantile(0.10):.0f}% P90={dfr["ret"].quantile(0.90):.0f}%'}"
          f" (etendue {dfr['ret'].quantile(0.90)-dfr['ret'].quantile(0.10):.0f} pts)")

    # B2. Overlap des trades entre meilleur / median / pire seed (Jaccard sur (symbol, entry_date))
    print("\n  B2. Overlap des trades (Jaccard sur symbol x entry_date) :")
    order = dfr.sort_values("pnl").reset_index(drop=True)
    worst = order.iloc[0]["seed"]
    meds = order.iloc[len(order) // 2]["seed"]
    best = order.iloc[-1]["seed"]
    sets = {}
    for p in per_seed:
        sets[p["seed"]] = set(zip(p["closed"]["symbol"], p["closed"]["entry_date"]))
    print(f"  meilleur seed={int(best)} (PnL={order.iloc[-1]['pnl']:.0f}$) | "
          f"median seed={int(meds)} (PnL={order.iloc[len(order)//2]['pnl']:.0f}$) | "
          f"pire seed={int(worst)} (PnL={order.iloc[0]['pnl']:.0f}$)")
    for a, b in [(best, meds), (best, worst), (meds, worst)]:
        print(f"      seed {int(a)} vs seed {int(b)} : Jaccard={_jaccard(sets[a], sets[b]):.3f} "
              f"(n={len(sets[a])} / {len(sets[b])})")

    # B3. Distribution fat-tail des outcomes des candidats par jour (tout le pool, sans m8)
    df = pool.copy()
    df["_pe_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    p20 = df[df["_pe_pct"] >= 0.80].copy()
    p20["_net"] = p20["y3_long_ret"] - COST
    grp = p20.groupby("date")["_net"]
    n_days = grp.size()
    kurt = grp.apply(lambda x: float(x.kurt()) if len(x) > 3 else float("nan"))
    top1_share = grp.apply(lambda x: float(abs(x.max()) / x.abs().sum()) if x.abs().sum() > 0 else float("nan"))
    print("\n  B3. Distribution des outcomes des candidats par jour (pool TOP20 complet, pas de m8) :")
    print(f"      nb candidats/jour : mean={n_days.mean():.0f} | median={n_days.median():.0f}")
    print(f"      kurtosis (excess) des outcomes/jour : mean={kurt.mean():.1f} | median={kurt.median():.1f} "
          f"(>3 = fat-tailed)")
    print(f"      part du top-1 mover dans la somme abs des outcomes du jour : mean={100*top1_share.mean():.0f}%")
    print(f"      jours ou le top-1 fait >50% de la somme abs : {100*(top1_share>0.5).mean():.0f}%")
    print(f"      jours ou le top-1 fait >30% de la somme abs : {100*(top1_share>0.3).mean():.0f}%")


# ---------------------------------------------------------------------------
# E11-C : test de capacite (m8 vs equal-weight pool complet)
# ---------------------------------------------------------------------------

def _sem_equity_returns(eq: pd.Series) -> dict:
    idx = pd.to_datetime(eq.index)
    sem = idx.year.astype(str) + np.where(idx.month <= 6, "H1", "H2")
    vals, sems = [], []
    for sm in sorted(set(sem)):
        vals.append(float(eq[sem == sm].iloc[-1]))
        sems.append(sm)
    out, prev = {}, INITIAL_EQUITY
    for sm, v in zip(sems, vals):
        out[sm] = v / prev - 1.0
        prev = v
    return out


def section_C(pool: pd.DataFrame, per_seed: list[dict]) -> None:
    print("\n" + "=" * 132)
    print("E11-C  TEST DE CAPACITE : m8 vs equal-weight du pool Extreme TOP20 complet")
    print("=" * 132)

    # Equal-weight pool : moyenne quotidienne des returns candidats (net couts)
    df = pool.copy()
    df["_pe_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    p20 = df[df["_pe_pct"] >= 0.80].copy()
    p20["_net"] = p20["y3_long_ret"] - COST
    ew_daily = p20.groupby("date")["_net"].mean().sort_index()
    idx = pd.DatetimeIndex(ew_daily.index)
    ew_sem = idx.year.astype(str) + np.where(idx.month <= 6, "H1", "H2")
    ew_by_sem = ew_daily.groupby(ew_sem).sum()
    ew_cum = ew_daily.cumsum()
    ew_dd = float((ew_cum - ew_cum.cummax()).min() * 100.0)
    ew_total = float(ew_cum.iloc[-1] * 100.0)
    print(f"\n  Equal-weight POOL (moyenne quotidienne des returns candidats, net couts 16bps) :")
    print(f"      retour cumule total = {ew_total:.1f}% | jours positifs={(ew_daily>0).mean()*100:.0f}% "
          f"| MaxDD proxy = {ew_dd:.1f}%")

    # m8 : equity returns par semestre, distribution sur seeds
    sem_rows = []
    for p in per_seed:
        for sm, r in _sem_equity_returns(p["eq"]).items():
            sem_rows.append({"seed": p["seed"], "semester": sm, "ret": r * 100.0})
    dfs = pd.DataFrame(sem_rows)
    # MaxDD m8 distribution
    dd_vals = []
    for p in per_seed:
        eq = p["eq"]
        dd_vals.append(float(((eq / eq.cummax()) - 1.0).min() * 100.0))
    dd_arr = np.array(dd_vals)
    print(f"  m8 : MaxDD median sur seeds = {np.median(dd_arr):.1f}% "
          f"(P10={np.percentile(dd_arr,10):.1f} P90={np.percentile(dd_arr,90):.1f})")
    med_ret = np.median([p['eq'].iloc[-1]/INITIAL_EQUITY-1 for p in per_seed]) * 100
    print(f"  m8 : retour total median sur seeds = {med_ret:.1f}%")

    print("\n  Comparaison par semestre :")
    print(f"  {'sem':<8} {'EW pool%':>9} {'m8 med%':>9} {'m8 P10':>8} {'m8 P90':>8} {'m8 %pos':>8}")
    sems = sorted(set(dfs["semester"]) | set(ew_by_sem.index))
    for sm in sems:
        ew = float(ew_by_sem.get(sm, 0.0) * 100.0)
        sub = dfs[dfs["semester"] == sm]["ret"]
        if sub.empty:
            continue
        print(f"  {sm:<8} {ew:>9.1f} {sub.median():>9.1f} {sub.quantile(0.10):>8.1f} "
              f"{sub.quantile(0.90):>8.1f} {100*(sub>0).mean():>7.0f}%")

    # Lecture pre-fixee
    ew_26 = float(ew_by_sem.get(BAD_SEM, 0.0) * 100.0)
    m8_26 = dfs[dfs["semester"] == BAD_SEM]["ret"]
    print("\n  LECTURE (pre-fixee) :")
    if ew_26 > 0:
        print(f"  → pool equal-weight 2026H1 = {ew_26:+.1f}% (positif) alors que m8 2026H1 est mauvais "
              f"({m8_26.median():+.1f}% median) → le signal Extreme reste bon en 2026H1 ; "
              f"le probleme est la SELECTION m8 (concentration/capacite).")
    else:
        print(f"  → pool equal-weight 2026H1 = {ew_26:+.1f}% (negatif) → le signal Extreme/lifecycle "
              f"lui-meme se degrade en 2026H1, pas seulement la selection.")


# ---------------------------------------------------------------------------
# E11-D : attribution exits
# ---------------------------------------------------------------------------

def section_D(c: pd.DataFrame, post: pd.DataFrame, per_seed: list[dict]) -> None:
    print("\n" + "=" * 132)
    print("E11-D  ATTRIBUTION EXITS : TP / trailing / initial stop / time_stop")
    print("=" * 132)

    # D1. Par reason x semestre (run representatif seed 7)
    print("\n  D1. Contribution par reason x semestre (seed %d), PnL$ :" % SEED_REP)
    sems = sorted(c["semester"].unique())
    print(f"  {'reason':<16}" + "".join(f"{'':>6}{s:>11}" for s in sems) + f"{'':>6}{'TOTAL':>11}")
    for reason in REASONS:
        line = f"  {reason:<16}"
        tot = 0.0
        for sm in sems:
            g = c[(c["exit_reason"] == reason) & (c["semester"] == sm)]
            line += f"{g['pnl'].sum():>17.0f}"
            tot += g["pnl"].sum()
        line += f"{tot:>17.0f}"
        print(line)
    line = f"  {'n trades':<16}"
    tot = 0
    for sm in sems:
        line += f"{int((c['semester'] == sm).sum()):>17}"
        tot += int((c["semester"] == sm).sum())
    line += f"{tot:>17}"
    print(line)

    # D2. Metriques par reason (seed 7)
    pst = post[["symbol", "exit_date", "exit_reason", "ret_J3", "ret_J5", "ret_J10"]]
    c2 = c.merge(pst, on=["symbol", "exit_date", "exit_reason"], how="left")
    print("\n  D2. Metriques par reason (seed %d) :" % SEED_REP)
    print(f"  {'reason':<16} {'n':>4} {'PnL$':>10} {'Exp$':>8} {'win%':>6} {'medMFE%':>8} "
          f"{'medMAE%':>8} {'medDurJ':>8} {'J+3%':>7} {'J+5%':>7} {'J+10%':>8}")
    for reason in REASONS:
        g = c2[c2["exit_reason"] == reason]
        if g.empty:
            continue
        print(f"  {reason:<16} {len(g):>4} {g['pnl'].sum():>10.0f} {g['pnl'].mean():>8.0f} "
              f"{100*(g['pnl']>0).mean():>5.0f}% {100*g['mfe'].median():>7.2f}% "
              f"{100*g['mae'].median():>7.2f}% {g['holding'].median():>8.1f} "
              f"{100*g['ret_J3'].median():>6.2f}% {100*g['ret_J5'].median():>6.2f}% "
              f"{100*g['ret_J10'].median():>7.2f}%")

    # D3. Structure moyenne sur les 20 seeds (TP vs trailing vs stop)
    print("\n  D3. Structure PnL par reason, moyenne sur les %d seeds :" % N_SEEDS)
    agg = {r: [] for r in REASONS}
    for p in per_seed:
        cl = p["closed"]
        for reason in REASONS:
            agg[reason].append(float(cl[cl["exit_reason"] == reason]["pnl"].sum()))
    print(f"  {'reason':<16} {'mean PnL$':>10} {'median PnL$':>12} {'% seeds positifs':>17}")
    for reason in REASONS:
        a = np.array(agg[reason])
        print(f"  {reason:<16} {a.mean():>10.0f} {np.median(a):>12.0f} {100*(a>0).mean():>16.0f}%")

    print("\n  STRUCTURE OBSERVEE (seed %d) : TP +%.0fk vs trailing %.0fk vs initial stop %.0fk "
          "(le montant varie selon le seed, la structure non)" % (
              SEED_REP,
              c[c['exit_reason']=='take_profit']['pnl'].sum()/1000,
              c[c['exit_reason']=='trailing_stop']['pnl'].sum()/1000,
              c[c['exit_reason']=='initial_stop']['pnl'].sum()/1000))


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)

    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)

    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "high", "close"])
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    px_close = bars.pivot_table(index="trade_date", columns="symbol", values="close").sort_index()
    px_high = bars.pivot_table(index="trade_date", columns="symbol", values="high").sort_index()

    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms",
          flush=True)
    print(f"seeds: {N_SEEDS} runs EXTREME_TOP20 (seed 0..{N_SEEDS-1}) ; diagnostic payoff sur seed {SEED_REP}",
          flush=True)

    per_seed: list[dict] = []
    for seed in range(N_SEEDS):
        closed, eq = run_bt(pool, pivots, seed)
        per_seed.append({"seed": seed, "closed": closed, "eq": eq})
        if seed % 5 == 0:
            print(f"  seed {seed} done | PnL={closed['pnl'].sum():.0f}$", flush=True)

    c_rep = attach_path(per_seed[SEED_REP]["closed"], path)
    post_rep = post_exit_info(c_rep, px_close, px_high)

    print(f"\nrun representatif (seed {SEED_REP}): {len(c_rep)} trades | "
          f"PnL={c_rep['pnl'].sum():.0f}$ | "
          f"sem+={(c_rep.groupby('semester')['pnl'].sum()>0).sum()}/{c_rep['semester'].nunique()}", flush=True)

    section_A(c_rep, post_rep)
    section_B(per_seed, pool)
    section_C(pool, per_seed)
    section_D(c_rep, post_rep, per_seed)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = c_rep.merge(post_rep, on=["symbol", "exit_date", "semester", "exit_reason", "pnl"], how="left")
    out.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
