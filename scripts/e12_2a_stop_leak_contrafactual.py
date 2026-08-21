"""E12-2A — Stop-leak global contrefactuel (chemin PROD, pool Extreme TOP20, zero tuning).

QUESTION : parmi les pertes trailing_stop / initial_stop, quelle part etait
inevitable (TRUE_LOSER) et quelle part aurait finalement atteint le TP PROD si on
avait laisse respirer le trade (PREMATURE_STOP) ?

POPULATION : tous les candidats Extreme TOP20 (proba_extreme rank>=0.80) 2023-2026,
replay chemin PROD (stop 2.5xATR / TP min(3xATR,7%) / trailing 2.5xATR / gap 3% / 16bps),
comme E12-1A. Seed-independant. Distingue trailing_stop vs initial_stop.

SORTIES demandees (par type de stop et par semestre) :
  n, PnL (sum ret%), realized return, MFE_before_stop, MAE_before_stop,
  ret J+5/J+10/J+20 apres sortie, future MFE apres sortie,
  would_hit_TP (TP PROD min(3xATR,7%)), delai stop->TP, MAE additionnelle necessaire.

CLASSIFICATION (seuils PRE-FIXES, 4 categories mutuellement exclusives) :
  PREMATURE_STOP     : apres le stop, le chemin atteint le TP PROD (J+20)
  PARTIAL_RECOVERY   : pas TP, mais future MFE apres sortie >= +5%
  REVERSAL_AFTER_MFE : pas TP, future MFE < 5%, MAIS mfe_before_stop >= +5%
  TRUE_LOSER         : reste mauvais (future MFE < 5%, mfe_before < 5%)

CONTREFACTUEL NET (stops elargis de dW xATR sur le stop initial ET le trailing) :
  pour chaque stop-trade, re-simuler depuis l'entree avec stop plus large :
    - s'il atteint desormais le TP  -> gain recuperable (PREMATURE)
    - sinon il sort plus bas        -> perte supplementaire (TRUE_LOSER/REVERSAL/PARTIAL)
  NET = somme(gains recuperables) - somme(pertes supplementaires), par semestre.

GATE (pre-fixe) : on ne teste des stops plus larges (E12-2B) que si les PREMATURE_STOP
representent une part economiquement significative ET que le NET contrefactuel > 0 sur
plusieurs semestres (cout sur les true losers < gain sur les premature).

Sortie : print + artifacts/models/oracle/e12_2a_stop_leak.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.e6_b2_ev_long_backtest import START, END, load_pool

CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e12_2a_stop_leak.parquet")
COST = 0.0016
STOP_ATR = 2.5
TP_ATR = 3.0
TP_MAX = 0.07
GAP_MAX = 0.03
MAX_HOLD = 30
FWD = 20          # fenetre forward apres sortie (jours ouvres)
PARTIAL_TH = 0.05  # future MFE >= 5% = forte recuperation
MFE_REV_TH = 0.05  # mfe_before_stop >= 5% = avait deja bouge
WIDENS = (0.5, 1.0, 1.5, 2.0)  # elargissement du stop (xATR) - diagnostic pur


def replay_prod(close_arr, high_arr, low_arr, entry_px, atr_pct, i0):
    """Replay PROD. Retourne (exit_type, ret, mfe, mae, k, exit_px). exit_type in
    {'tp','trailing','initial','eod'}. Conservative : stop avant TP dans la meme barre."""
    tp = entry_px * (1.0 + min(TP_ATR * atr_pct, TP_MAX))
    stop = entry_px * (1.0 - STOP_ATR * atr_pct)
    tr_dist = STOP_ATR * atr_pct
    peak = entry_px
    mfe = 0.0
    mae = 0.0
    n = len(close_arr)
    for k in range(1, min(MAX_HOLD, n - i0)):
        i = i0 + k
        h = float(high_arr[i]); l = float(low_arr[i]); c = float(close_arr[i])
        if np.isnan(h) or np.isnan(l) or np.isnan(c):
            continue
        peak = max(peak, h)
        tr_level = peak * (1.0 - tr_dist)
        eff_stop = max(stop, tr_level)
        mfe = max(mfe, h / entry_px - 1.0)
        mae = min(mae, l / entry_px - 1.0)
        if l <= eff_stop:
            etype = "trailing" if tr_level > stop else "initial"
            return etype, eff_stop / entry_px - 1.0 - COST, mfe, mae, k, eff_stop
        if h >= tp:
            return "tp", tp / entry_px - 1.0 - COST, mfe, mae, k, tp
    i = min(i0 + MAX_HOLD, n - 1)
    c = float(close_arr[i])
    mfe = max(mfe, c / entry_px - 1.0 if not np.isnan(c) else mfe)
    mae = min(mae, c / entry_px - 1.0 if not np.isnan(c) else mae)
    return "eod", c / entry_px - 1.0 - COST, mfe, mae, MAX_HOLD, c


def replay_wider(close_arr, high_arr, low_arr, entry_px, atr_pct, i0, dw):
    """Re-sim avec stop (initial + trailing) elargi de dw xATR. Retourne (etype, ret, k)."""
    tp = entry_px * (1.0 + min(TP_ATR * atr_pct, TP_MAX))
    stop = entry_px * (1.0 - (STOP_ATR + dw) * atr_pct)
    tr_dist = (STOP_ATR + dw) * atr_pct
    peak = entry_px
    n = len(close_arr)
    for k in range(1, min(MAX_HOLD, n - i0)):
        i = i0 + k
        h = float(high_arr[i]); l = float(low_arr[i])
        if np.isnan(h) or np.isnan(l):
            continue
        peak = max(peak, h)
        tr_level = peak * (1.0 - tr_dist)
        eff_stop = max(stop, tr_level)
        if l <= eff_stop:
            return ("trailing" if tr_level > stop else "initial"), eff_stop / entry_px - 1.0 - COST, k
        if h >= tp:
            return "tp", tp / entry_px - 1.0 - COST, k
    i = min(i0 + MAX_HOLD, n - 1)
    c = float(close_arr[i])
    return "eod", c / entry_px - 1.0 - COST, MAX_HOLD


def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    pool["_pe_pct"] = pool.groupby("date")["proba_extreme"].rank(pct=True)
    cand = pool[pool["_pe_pct"] >= 0.80].copy()
    print(f"candidats Extreme TOP20: {len(cand):,}", flush=True)

    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str)
    syms = sorted(pool["symbol"].unique())
    b = bars[bars["symbol"].isin(syms)]
    close_p = b.pivot_table(index="trade_date", columns="symbol", values="close").sort_index()
    high_p = b.pivot_table(index="trade_date", columns="symbol", values="high").sort_index()
    low_p = b.pivot_table(index="trade_date", columns="symbol", values="low").sort_index()
    idx = close_p.index
    pos_map = {d: i for i, d in enumerate(idx)}
    print(f"OHLC pivot: {close_p.shape}", flush=True)

    cache: dict[str, tuple] = {}
    recs = []
    cand = cand.sort_values(["date", "symbol"]).reset_index(drop=True)
    for r in cand.itertuples(index=False):
        sym = r.symbol
        d = r.date
        entry_px = float(r.entry) if pd.notna(r.entry) else float("nan")
        atr_pct = float(r.atr_pct_20) if pd.notna(r.atr_pct_20) else float("nan")
        if not np.isfinite(entry_px) or not np.isfinite(atr_pct) or atr_pct <= 0:
            continue
        i0 = pos_map.get(d)
        if i0 is None:
            continue
        prev_close = float(close_p.iloc[i0][sym]) if sym in close_p.columns else float("nan")
        if np.isfinite(prev_close) and abs(entry_px / prev_close - 1.0) > GAP_MAX:
            continue
        if sym not in cache:
            if sym not in close_p.columns:
                continue
            cache[sym] = (close_p[sym].to_numpy(), high_p[sym].to_numpy(), low_p[sym].to_numpy())
        ca, ha, la = cache[sym]
        etype, ret, mfe, mae, k, exit_px = replay_prod(ca, ha, la, entry_px, atr_pct, i0)
        if etype not in ("trailing", "initial"):
            continue  # E12-2A ne s'interesse qu'aux stops
        ei = i0 + k
        # forward apres sortie (J+5/10/20) + future MFE + would_hit_TP
        tp_lvl = entry_px * (1.0 + min(TP_ATR * atr_pct, TP_MAX))
        r5 = r10 = r20 = f_mfe_exit = f_high_entry = float("nan")
        hit_tp = 0
        delay = float("nan")
        add_mae = float("nan")
        best_high = -1.0
        # min low sur entry..exit (deja <= stop par construction) puis sur la fenetre forward
        best_low = 1e18
        for kk in range(0, k + 1):
            j = i0 + kk
            if j >= len(la):
                break
            ll = float(la[j])
            if not np.isnan(ll):
                best_low = min(best_low, ll)
        for kk in range(1, FWD + 1):
            j = ei + kk
            if j >= len(ca):
                break
            cc = float(ca[j]); hh = float(ha[j]); ll = float(la[j])
            if np.isnan(cc) or np.isnan(hh) or np.isnan(ll):
                continue
            best_low = min(best_low, ll)
            if kk == 5:
                r5 = cc / exit_px - 1.0
            if kk == 10:
                r10 = cc / exit_px - 1.0
            if kk == 20:
                r20 = cc / exit_px - 1.0
            best_high = max(best_high, hh)
            if hh >= tp_lvl and hit_tp == 0:
                hit_tp = 1
                delay = kk
                break
        f_mfe_exit = (best_high / exit_px - 1.0) if best_high > 0 else float("nan")
        f_high_entry = (best_high / entry_px - 1.0) if best_high > 0 else float("nan")
        add_mae = (best_low / entry_px - 1.0) if best_low < 1e17 else float("nan")

        # classification (seuils pre-fixes)
        if hit_tp == 1:
            cat = "PREMATURE_STOP"
        elif (f_mfe_exit if np.isfinite(f_mfe_exit) else 0.0) >= PARTIAL_TH:
            cat = "PARTIAL_RECOVERY"
        elif mfe >= MFE_REV_TH:
            cat = "REVERSAL_AFTER_MFE"
        else:
            cat = "TRUE_LOSER"

        # contrefactuel stops elargis
        cf = {}
        for dw in WIDENS:
            e2, r2, _ = replay_wider(ca, ha, la, entry_px, atr_pct, i0, dw)
            cf[dw] = r2 - ret   # gain si >0 (flip vers TP), perte si <0

        recs.append({"symbol": sym, "date": d, "semester": str(d.year) + ("H1" if d.month <= 6 else "H2"),
                     "etype": etype, "cat": cat, "ret": ret, "mfe": mfe, "mae": mae,
                     "r5": r5, "r10": r10, "r20": r20, "f_mfe_exit": f_mfe_exit,
                     "f_high_entry": f_high_entry, "hit_tp": hit_tp, "delay": delay,
                     "add_mae": add_mae, **{f"cf_{dw}": cf[dw] for dw in WIDENS}})
    t = pd.DataFrame(recs)
    print(f"stop-trades: {len(t):,} | trailing={int((t['etype']=='trailing').sum()):,} "
          f"| initial={int((t['etype']=='initial').sum()):,}", flush=True)

    # ── Table 1 : par type de stop (global + par semestre) ──
    print("\n" + "=" * 130)
    print("E12-2A  Table 1 : stops par type et par semestre (sum ret%, medians)")
    print("=" * 130)
    print(f"  {'sem':<8} {'type':<9} {'n':>5} {'PnL%':>8} {'retR':>7} {'medMFE':>7} {'medMAE':>7} "
          f"{'J+5%':>7} {'J+10%':>7} {'J+20%':>7} {'fMFE_exit':>9} {'%hitTP':>7} {'delai':>6} {'addMAE':>7}")
    for sem in sorted(t["semester"].unique()):
        for et in ("trailing", "initial"):
            g = t[(t["semester"] == sem) & (t["etype"] == et)]
            if g.empty:
                continue
            print(f"  {sem:<8} {et:<9} {len(g):>5} {100*g['ret'].sum():>8.0f} "
                  f"{100*g['ret'].mean():>6.2f}% {100*g['mfe'].median():>6.1f}% "
                  f"{100*g['mae'].median():>6.1f}% {100*g['r5'].median():>6.2f}% "
                  f"{100*g['r10'].median():>6.2f}% {100*g['r20'].median():>6.2f}% "
                  f"{100*g['f_mfe_exit'].median():>8.1f}% {100*g['hit_tp'].mean():>6.0f}% "
                  f"{g['delay'].median():>5.0f} {100*g['add_mae'].median():>6.1f}%")
    g = t
    print(f"  {'TOUT':<8} {'trailing':<9} {int((g['etype']=='trailing').sum()):>5} "
          f"{100*g[g['etype']=='trailing']['ret'].sum():>8.0f}")
    print(f"  {'TOUT':<8} {'initial':<9} {int((g['etype']=='initial').sum()):>5} "
          f"{100*g[g['etype']=='initial']['ret'].sum():>8.0f}")

    # ── Table 2 : classification ──
    print("\n" + "=" * 130)
    print("E12-2A  Table 2 : classification (seuils pre-fixes), par semestre")
    print("=" * 130)
    cats = ["PREMATURE_STOP", "PARTIAL_RECOVERY", "REVERSAL_AFTER_MFE", "TRUE_LOSER"]
    print(f"  {'sem':<8}" + "".join(f"{c:>24}" for c in cats))
    for sem in sorted(t["semester"].unique()):
        g = t[t["semester"] == sem]
        row = f"  {sem:<8}"
        for c in cats:
            sub = g[g["cat"] == c]
            row += f" {len(sub):>4} ({100*len(sub)/len(g):>4.0f}% {100*sub['ret'].sum():>7.0f}%)"
        print(row)
    g = t
    row = f"  {'TOUT':<8}"
    for c in cats:
        sub = g[g["cat"] == c]
        row += f" {len(sub):>4} ({100*len(sub)/len(g):>4.0f}% {100*sub['ret'].sum():>7.0f}%)"
    print(row)

    # ── Table 3 : contrefactuel net (stops elargis) ──
    print("\n" + "=" * 130)
    print("E12-2A  Table 3 : contrefactuel NET = gains recuperables - pertes supplementaires")
    print("=" * 130)
    print("  (sum ret% sur les stop-trades ; >0 = elargir le stop serait net positif)")
    print(f"  {'sem':<8}" + "".join(f"{f'+{dw}xATR':>14}" for dw in WIDENS))
    for sem in sorted(t["semester"].unique()):
        g = t[t["semester"] == sem]
        row = f"  {sem:<8}"
        for dw in WIDENS:
            row += f"{100*g[f'cf_{dw}'].sum():>14.0f}"
        print(row)
    row = f"  {'TOUT':<8}"
    for dw in WIDENS:
        row += f"{100*t[f'cf_{dw}'].sum():>14.0f}"
    print(row)

    # Zoom 2026H1
    g26 = t[t["semester"] == "2026H1"]
    print("\n  Zoom 2026H1 :")
    for c in cats:
        sub = g26[g26["cat"] == c]
        print(f"    {c:<20} n={len(sub):>4} | PnL%={100*sub['ret'].sum():>8.0f} | "
              f"medMFE={100*sub['mfe'].median():.1f}% medMAE={100*sub['mae'].median():.1f}% "
              f"| %hitTP={100*sub['hit_tp'].mean():.0f}% | addMAE={100*sub['add_mae'].median():.1f}%")

    # ── Gate ──
    print("\n" + "=" * 130)
    print("GATE (pre-fixe) pour ouvrir E12-2B")
    print("=" * 130)
    pre = t[t["cat"] == "PREMATURE_STOP"]
    prem_share = 100 * len(pre) / max(len(t), 1)
    prem_pnl = float(pre["ret"].sum())
    tot_pnl = float(t["ret"].sum())
    nets = {dw: float(t[f"cf_{dw}"].sum()) for dw in WIDENS}
    best_dw = max(nets, key=nets.get)
    pos_sems = sum(1 for sem in t["semester"].unique()
                   if float(t[t["semester"] == sem][f"cf_{best_dw}"].sum()) > 0)
    n_sems = t["semester"].nunique()
    print(f"  PREMATURE_STOP : part={prem_share:.1f}% | PnL recuperable potentiel={100*prem_pnl:.0f}% "
          f"(vs PnL total stops {100*tot_pnl:.0f}%)")
    print(f"  meilleur elargissement diagnostique : {best_dw}xATR -> NET={100*nets[best_dw]:.0f}% "
          f"(>0 = rentable) | semestres positifs : {pos_sems}/{n_sems}")
    if nets[best_dw] > 0 and pos_sems >= int(np.ceil(n_sems / 2)):
        print("  -> GATE PASSE : les premature stops sont economiquement significatifs et le")
        print("     contrefactuel est net positif sur la majorite des semestres. E12-2B justifie.")
    else:
        print("  -> GATE ECHOUE : elargir les stops ne recupere pas les premature stops sans")
        print("     pertes plus lourdes sur les true losers. Fermer la piste exits.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    t.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
