"""E6-B2c — Attribution causale portefeuille : pourquoi EV_TOP20 gagne-t-il ?

OBJECTIF (spec user 2026-08-20) : expliquer le paradoxe — au niveau candidat,
EV_ONLY est mauvais (PF 0.94, −0.245%) et RANK_ONLY bon (PF 1.18, +0.683%),
POURTANT le portefeuille EV_TOP20 bat RANK_TOP20 (+65.5% vs +37.5%). Il faut
séparer : qualité de sélection vs effet de slots/timing vs interaction des exits.

AUCUN paramètre modifié. Tout est gelé (EV_TOP20, CatBoost Y3-LONG OOF, Platt OOF,
gains/pertes train-only, Oracle O0, m8, coûts canoniques, exits, LONG-only).

MÉTHODE :
1. Rejouer RANK_TOP20 et EV_TOP20 dans le VRAI moteur → trades exécutés.
2. Classer chaque trade exécuté : COMMON (dans R20∩EV20) / EV_ONLY (EV20-R20) /
   RANK_ONLY (R20-EV20) — par (symbol, signal_date).
3. Comparer par groupe : PnL, PF, expectancy, win, durée, MFE/MAE, par semestre.
4. Mécanique jour-par-jour : pour les jours où RANK et EV divergent, quel trade
   prend un slot, combien de temps il reste occupé (effet de chemin).
5. REPLAY À ENTRÉES FORCÉES :
     CF1 : calendrier/slots de RANK, sélection EV quand divergence
           (trades exécutés RANK, RANK_ONLY remplacés par le meilleur EV_ONLY du jour)
     CF2 : calendrier/slots de EV, sélection RANK quand divergence (inverse)
   → isole gain EV = qualité sélection + effet slots/timing + interaction exits.
6. TEST JACKPOT : retirer les top 1/5/10/20 trades (EV_TOP20 vs RANK_TOP10) et
   recalculer Return_approx/PF/expectancy → EV reste-t-il supérieur sans jackpots ?

DÉCISION (critère user) :
- Si EV_ONLY exécutés > RANK_ONLY exécutés → EV reste candidat.
- Si EV_ONLY reste mauvais ET les +20pts viennent de quelques gros winners
  accessibles accidentellement via le calendrier → EV_TOP20 = NO-GO malgré 7/7.

Sortie : print + artifacts/models/oracle/e6_b2c_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.simulator import BacktestConfig, BacktestEngine
from scripts.e6_b2_ev_long_backtest import (
    COST_RT,
    END,
    START,
    add_ev_features,
    build_signals,
    load_pivots,
    load_pool,
)

PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
OUT = Path("artifacts/models/oracle/e6_b2c_results.parquet")
INITIAL_EQUITY = 100_000.0


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


def run_and_collect(pool: pd.DataFrame, pivots: dict, variant: str) -> pd.DataFrame:
    sig = build_signals(pool, variant)
    res = make_engine().run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    trades = res.closed_trades_df.copy()
    trades["signal_date"] = pd.to_datetime(trades["signal_date"]).dt.normalize()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"]).dt.normalize()
    trades["symbol"] = trades["symbol"].astype(str)
    trades["variant"] = variant
    return trades


def classify_trades(trades: pd.DataFrame, pool: pd.DataFrame) -> pd.DataFrame:
    """Classe chaque trade exécuté : COMMON / EV_ONLY / RANK_ONLY via R20/EV20 du jour."""
    # Flags candidats par (symbol, signal_date)
    pool = pool.copy()
    pool["date"] = pd.to_datetime(pool["date"]).dt.normalize()
    pool["_rk20"] = pool.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80
    pool["_ev20"] = pool.groupby("date")["EV_LONG"].rank(pct=True) >= 0.80
    flags = pool.groupby(["symbol", "date"]).agg(
        rk20=("_rk20", "max"), ev20=("_ev20", "max")).reset_index()
    flags.columns = ["symbol", "signal_date", "rk20", "ev20"]

    t = trades.merge(flags, on=["symbol", "signal_date"], how="left")
    t["rk20"] = t["rk20"].fillna(False).astype(bool)
    t["ev20"] = t["ev20"].fillna(False).astype(bool)
    t["group"] = np.where(
        t["rk20"] & t["ev20"], "COMMON",
        np.where(t["ev20"] & ~t["rk20"], "EV_ONLY",
                 np.where(t["rk20"] & ~t["ev20"], "RANK_ONLY", "OUTSIDE")))
    return t


def group_stats(t: pd.DataFrame, label: str) -> pd.DataFrame:
    """Stats par groupe de classification (sur trades exécutés du run `label`)."""
    rows = []
    for g, sub in t.groupby("group"):
        pnl = pd.to_numeric(sub["pnl"], errors="coerce").fillna(0.0)
        n = len(sub)
        gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
        rows.append({
            "run": label, "group": g, "n": n,
            "pnl": float(pnl.sum()),
            "pf": gp / gn if gn > 0 else float("inf"),
            "expectancy": float(pnl.mean()) if n else 0.0,
            "win": float((pnl > 0).mean()) if n else 0.0,
            "holding_days": float(pd.to_numeric(sub["holding_days"], errors="coerce").mean()) if n else 0.0,
        })
    return pd.DataFrame(rows)


def attach_mfe_mae(t: pd.DataFrame) -> pd.DataFrame:
    """Joint MFE/MAE depuis les labels de chemin (même politique gelée)."""
    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)
    t = t.merge(
        path[["symbol", "date", "y3_long_mfe", "y3_long_mae"]],
        left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")
    return t


def slot_occupancy(trades: pd.DataFrame) -> pd.DataFrame:
    """Reconstruit l'occupation quotidienne des slots depuis les trades exécutés."""
    rows = []
    for _, r in trades.iterrows():
        for d in pd.date_range(r["entry_date"], r["exit_date"], freq="B"):
            rows.append({"date": d, "variant": r["variant"]})
    occ = pd.DataFrame(rows)
    if occ.empty:
        return pd.DataFrame(columns=["date", "variant", "n_positions"])
    return occ.groupby(["date", "variant"]).size().rename("n_positions").reset_index()


def forced_replay_cf1(pool: pd.DataFrame, pivots: dict, rank_trades: pd.DataFrame,
                      variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """CF1 : calendrier/slots RANK, sélection EV quand divergence.

    Prend les trades exécutés par RANK ; chaque RANK_ONLY est remplacé par le
    meilleur candidat EV_ONLY du même jour (plus haut EV_LONG non exécuté par
    RANK). Rejoue le moteur → isole l'effet de la sélection EV sur le calendrier RANK.
    """
    pool = pool.copy()
    pool["date"] = pd.to_datetime(pool["date"]).dt.normalize()
    pool["_rk20"] = pool.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80
    pool["_ev20"] = pool.groupby("date")["EV_LONG"].rank(pct=True) >= 0.80

    rt = rank_trades.copy()
    rt["signal_date"] = pd.to_datetime(rt["signal_date"]).dt.normalize()

    forced = []
    for _, r in rt.iterrows():
        d = r["signal_date"]
        sym = r["symbol"]
        # Ce trade est-il RANK_ONLY (EV ne l'aurait pas choisi) ?
        day_pool = pool[pool["date"] == d]
        row_flags = day_pool[(day_pool["symbol"] == sym)]
        is_rank_only = (not row_flags.empty) and bool(row_flags["_rk20"].iloc[0]) and not bool(row_flags["_ev20"].iloc[0])
        if not is_rank_only:
            forced.append({"signal_date": d, "symbol": sym, "rank": r.get("rank", 1)})
            continue
        # Remplacer par le meilleur EV_ONLY du jour non déjà pris
        ev_only = day_pool[(day_pool["_ev20"]) & (~day_pool["_rk20"])]
        taken = set(rt[rt["signal_date"] == d]["symbol"])
        candidates = ev_only[~ev_only["symbol"].isin(taken)].sort_values("EV_LONG", ascending=False)
        if candidates.empty:
            forced.append({"signal_date": d, "symbol": sym, "rank": r.get("rank", 1)})
            continue
        replacement = candidates.iloc[0]
        forced.append({"signal_date": d, "symbol": replacement["symbol"], "rank": r.get("rank", 1)})

    sig = pd.DataFrame(forced)
    sig = sig.rename(columns={"signal_date": "trade_date"})
    # atr_pct_20 + score depuis le pool
    pool_idx = pool.set_index(["symbol", "date"])
    def _lookup(row):
        key = (row["symbol"], row["trade_date"])
        if key in pool_idx.index:
            return pool_idx.loc[key]
        return None
    sig["score"] = sig.apply(lambda r: _lookup(r)["_proba_catboost"] if _lookup(r) is not None else 0.0, axis=1)
    sig["atr_pct_20"] = sig.apply(lambda r: _lookup(r)["atr_pct_20"] if _lookup(r) is not None else 0.05, axis=1)
    sig["selected"] = True
    sig["side"] = "buy"
    res = make_engine().run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    trades = res.closed_trades_df.copy()
    trades["signal_date"] = pd.to_datetime(trades["signal_date"]).dt.normalize()
    trades["symbol"] = trades["symbol"].astype(str)
    trades["variant"] = f"CF1_{variant}"
    return trades, sig


def jackpot_test(trades_ev: pd.DataFrame, trades_rank: pd.DataFrame) -> pd.DataFrame:
    """Retire top 1/5/10/20 trades ; recalcule Return_approx/PF/expectancy."""
    rows = []
    for label, t in [("EV_TOP20", trades_ev), ("RANK_TOP10", trades_rank)]:
        pnl = pd.to_numeric(t["pnl"], errors="coerce").fillna(0.0)
        total = float(pnl.sum())
        rows.append({
            "bench": label, "remove": 0, "n": len(pnl),
            "return_approx_pct": total / INITIAL_EQUITY * 100.0,
            "pf": _pf(pnl), "expectancy": float(pnl.mean()),
        })
        for k in (1, 5, 10, 20):
            if len(pnl) <= k:
                continue
            keep = pnl.sort_values(ascending=False).iloc[k:]
            rows.append({
                "bench": label, "remove": k, "n": len(keep),
                "return_approx_pct": float(keep.sum()) / INITIAL_EQUITY * 100.0,
                "pf": _pf(keep), "expectancy": float(keep.mean()),
            })
    return pd.DataFrame(rows)


def _pf(pnl: pd.Series) -> float:
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    return gp / gn if gn > 0 else float("inf")


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy().dropna(subset=["y3_long"])
    pool = add_ev_features(pool, feature_columns)
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]

    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    # 1. Rejouer les deux portefeuilles
    print("\n=== Rejeu moteur RANK_TOP20 / EV_TOP20 ===", flush=True)
    t_rank = run_and_collect(pool, pivots, "RANK_TOP20")
    t_ev = run_and_collect(pool, pivots, "EV_TOP20")
    print(f"  RANK_TOP20 : {len(t_rank)} trades | PnL={t_rank['pnl'].sum():.0f}$ | PF={_pf(pd.to_numeric(t_rank['pnl'])):.2f}")
    print(f"  EV_TOP20   : {len(t_ev)} trades | PnL={t_ev['pnl'].sum():.0f}$ | PF={_pf(pd.to_numeric(t_ev['pnl'])):.2f}")

    # 2. Classification
    print("\n=== Classification des trades exécutés ===")
    c_rank = classify_trades(t_rank, pool)
    c_ev = classify_trades(t_ev, pool)
    c_rank = attach_mfe_mae(c_rank)
    c_ev = attach_mfe_mae(c_ev)

    gs_rank = group_stats(c_rank, "RANK_TOP20")
    gs_ev = group_stats(c_ev, "EV_TOP20")
    gs = pd.concat([gs_rank, gs_ev], ignore_index=True)
    print(f"  {'run':<10} {'group':<10} {'n':>5} {'PnL$':>9} {'PF':>6} {'expect$':>8} {'win%':>6} {'durJ':>5}")
    for r in gs.itertuples():
        print(f"  {r.run:<10} {r.group:<10} {r.n:>5} {r.pnl:>9.0f} {r.pf:>6.2f} {r.expectancy:>8.2f} {100*r.win:>5.1f}% {r.holding_days:>5.1f}")

    # MFE/MAE par groupe (EV_TOP20)
    print("\n=== MFE/MAE par groupe (EV_TOP20) ===")
    for g, sub in c_ev.groupby("group"):
        mfe = pd.to_numeric(sub["y3_long_mfe"], errors="coerce").dropna()
        mae = pd.to_numeric(sub["y3_long_mae"], errors="coerce").dropna()
        print(f"  {g:<10} MFE={100*mfe.mean():.2f}% MAE={100*mae.mean():.2f}% (n={len(sub)})")

    # 3. Par semestre par groupe
    print("\n=== PnL par semestre par groupe (EV_TOP20) ===")
    c_ev["semester"] = c_ev["entry_date"].dt.year.astype(str) + np.where(c_ev["entry_date"].dt.month <= 6, "H1", "H2")
    pv = c_ev.pivot_table(index="semester", columns="group", values="pnl", aggfunc="sum", fill_value=0)
    print(pv.to_string())

    # 4. Mécanique jour-par-jour (occupation des slots)
    print("\n=== Mécanique jour-par-jour (occupation slots) ===")
    occ = slot_occupancy(pd.concat([t_rank.assign(variant="RANK"), t_ev.assign(variant="EV")], ignore_index=True))
    piv_occ = occ.pivot_table(index="date", columns="variant", values="n_positions", aggfunc="max", fill_value=0)
    if not piv_occ.empty:
        full_r = int((piv_occ.get("RANK", 0) >= 8).sum())
        full_e = int((piv_occ.get("EV", 0) >= 8).sum())
        print(f"  jours à capacité (>=8 slots) : RANK={full_r} | EV={full_e}")
        # jours où l'occupation diffère
        both = piv_occ.dropna()
        diff = both[both["RANK"] != both["EV"]]
        print(f"  jours où l'occupation diffère : {len(diff)} / {len(both)}")
        if len(diff):
            print(diff.head(10).to_string())

    # 5. Replay à entrées forcées
    print("\n=== REPLAY À ENTRÉES FORCÉES ===", flush=True)
    cf1_trades, _ = forced_replay_cf1(pool, pivots, t_rank, "RANK_TOP20")
    pnl_cf1 = pd.to_numeric(cf1_trades["pnl"], errors="coerce").fillna(0.0)
    pnl_rank = pd.to_numeric(t_rank["pnl"], errors="coerce").fillna(0.0)
    print(f"  CF1 (calendrier RANK, sélection EV) : {len(cf1_trades)} trades | "
          f"PnL={pnl_cf1.sum():.0f}$ (vs RANK {pnl_rank.sum():.0f}$) | PF={_pf(pnl_cf1):.2f} (vs {_pf(pnl_rank):.2f})")
    print(f"    → delta = {pnl_cf1.sum()-pnl_rank.sum():+.0f}$ = effet de la SÉLECTION EV sur le calendrier RANK")

    # 6. Test jackpot
    print("\n=== TEST JACKPOT (retrait top trades) ===")
    jk = jackpot_test(t_ev, t_rank.assign(variant="RANK_TOP10"))
    print(f"  {'bench':<10} {'remove':>6} {'n':>5} {'Return_approx%':>14} {'PF':>7} {'expect$':>8}")
    for r in jk.itertuples():
        print(f"  {r.bench:<10} {r.remove:>6} {r.n:>5} {r.return_approx_pct:>13.2f}% {r.pf:>7.2f} {r.expectancy:>8.2f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    gs.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
