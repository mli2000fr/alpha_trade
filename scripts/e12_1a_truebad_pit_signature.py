"""E12-1A — Signature PIT des TRUE_BAD (erreurs d'entrée), chemin PROD, zero optimisation.

CONTEXTE : E12-A0b a montre que sous PROD, 2026H1 n'est PAS un probleme de stops
prematures mais de TRADES REELLEMENT MAUVAIS des l'entree (TRUE_BAD : MFE futur<3%
ET trade perdant). E12-1A = diagnostic UNIVARIE de features PIT (a l'entree) capables
de separer TRUE_BAD vs TRADEABLE, sur TOUS les semestres (pas seulement 2026H1).

POPULATION : tout le pool Extreme TOP20 (proba_extreme rank>=0.80) 2023-2026,
avec replay du chemin PROD (stop 2.5xATR / TP min(3xATR,7%) / trailing 2.5xATR /
gap filter 3% / couts 16bps). Seed-independant : c'est la population ou un filtre
NO-TRADE s'appliquerait AVANT m8.

CLASSIFICATION (par candidat) :
  TRUE_BAD      : mfe < 3% ET ret < 0        (jamais bouge, et perte)
  MOVED_LOSER   : mfe >= 3% ET ret < 0       (a bouge mais perdu -> lifecycle)
  WINNER        : ret >= 0
  TRADEABLE     = MOVED_LOSER + WINNER (tout sauf TRUE_BAD)

FEATURES PIT (a la date de signal, AUCUN lookahead) :
  - proba_extreme (Oracle O0), atr_pct_20, entry_gap
  - momentum symbol r5/r10/r21, distance SMA20/SMA50
  - marche : SPY r21/vol21, RSP r21, IWM r21
  - breadth : % symbols ret21>0, % au-dessus SMA20 ; dispersion cross-sectionnelle ret21 ;
    volatilite marche = mean ATR% du pool du jour

SORTIE : AUC + medians par bucket + FILTRE ECONOMIQUE (quartile du bas par feature :
%TRUE_BAD retires, couts evites, %WINNERS retires, gains perdus) + stabilite par semestre.
Puis (phase suivante) petit CatBoost seulement si plusieurs signaux stables.

Sortie : print + artifacts/models/oracle/e12_1a_truebad.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.e6_b2_ev_long_backtest import START, END, load_pool

CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e12_1a_truebad.parquet")
COST = 0.0016
MFE_BAD = 0.03
STOP_ATR = 2.5
TP_ATR = 3.0
TP_MAX = 0.07
GAP_MAX = 0.03
MAX_HOLD = 30
INDEXES = ("SPY", "IWM", "RSP")


# ---------------------------------------------------------------------------
# Replay chemin PROD par candidat
# ---------------------------------------------------------------------------

def replay_prod(close_arr: np.ndarray, high_arr: np.ndarray, low_arr: np.ndarray,
                entry_px: float, atr_pct: float, i0: int) -> dict:
    """Replay PROD : stop 2.5xATR / TP min(3xATR,7%) / trailing 2.5xATR (arme J1) /
    intrabar conservative (stop/trailing prioritaire si TP+stop meme barre)."""
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
        if l <= eff_stop:                      # conservative : stop avant TP
            return {"ret": eff_stop / entry_px - 1.0 - COST, "mfe": mfe, "mae": mae,
                    "exit": "stop", "k": k, "exit_close": c}
        if h >= tp:
            return {"ret": tp / entry_px - 1.0 - COST, "mfe": mfe, "mae": mae,
                    "exit": "tp", "k": k, "exit_close": c}
    # fin de fenetre : exit au dernier close
    i = min(i0 + MAX_HOLD, n - 1)
    c = float(close_arr[i])
    mfe = max(mfe, c / entry_px - 1.0 if not np.isnan(c) else mfe)
    mae = min(mae, c / entry_px - 1.0 if not np.isnan(c) else mae)
    return {"ret": c / entry_px - 1.0 - COST, "mfe": mfe, "mae": mae, "exit": "eod", "k": MAX_HOLD, "exit_close": c}


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    # Universe Extreme TOP20
    pool["_pe_pct"] = pool.groupby("date")["proba_extreme"].rank(pct=True)
    cand = pool[pool["_pe_pct"] >= 0.80].copy()
    print(f"candidats Extreme TOP20: {len(cand):,} | {cand['date'].min().date()} -> {cand['date'].max().date()}",
          flush=True)

    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str)
    # pivots sur les symboles du pool + indices
    all_syms = sorted(set(pool["symbol"].unique()) | set(INDEXES))
    b = bars[bars["symbol"].isin(all_syms)]
    close_p = b.pivot_table(index="trade_date", columns="symbol", values="close").sort_index()
    high_p = b.pivot_table(index="trade_date", columns="symbol", values="high").sort_index()
    low_p = b.pivot_table(index="trade_date", columns="symbol", values="low").sort_index()
    open_p = b.pivot_table(index="trade_date", columns="symbol", values="open").sort_index()
    print(f"OHLC pivot: {close_p.shape}", flush=True)

    idx = close_p.index
    pos_map = {d: i for i, d in enumerate(idx)}

    # ── Features par jour (cross-section, PIT, utilise closes <= jour) ──
    # retours 21j par symbole
    ret21 = close_p.pct_change(21)
    sma20 = close_p.rolling(20).mean()
    sma50 = close_p.rolling(50).mean()
    spy = close_p["SPY"].dropna()
    spy_r21 = spy.pct_change(21)
    spy_vol21 = spy.pct_change().rolling(21).std() * np.sqrt(252)
    rsp = close_p["RSP"].dropna()
    rsp_r21 = rsp.pct_change(21)
    iwm = close_p["IWM"].dropna()
    iwm_r21 = iwm.pct_change(21)

    breadth_up = (ret21 > 0).mean(axis=1)
    breadth_sma20 = (close_p > sma20).mean(axis=1)
    xs_disp21 = ret21.std(axis=1)
    mkt_atr = pool.groupby("date")["atr_pct_20"].mean()

    # ── Replay + features par candidat ──
    recs = []
    cand = cand.sort_values(["date", "symbol"]).reset_index(drop=True)
    per_sym_cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
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
        # gap filter PROD : |open_next/close_signal - 1| > 3% -> pas d'entree
        prev_close = float(close_p.iloc[i0][sym]) if sym in close_p.columns else float("nan")
        if np.isfinite(prev_close) and abs(entry_px / prev_close - 1.0) > GAP_MAX:
            continue
        if sym not in per_sym_cache:
            if sym not in close_p.columns:
                continue
            per_sym_cache[sym] = (close_p[sym].to_numpy(), high_p[sym].to_numpy(), low_p[sym].to_numpy())
        ca, ha, la = per_sym_cache[sym]
        out = replay_prod(ca, ha, la, entry_px, atr_pct, i0)
        ret = out["ret"]

        # features symbol (PIT, <= jour)
        px = close_p[sym]
        i = i0
        r5 = px.iloc[i] / px.iloc[i - 5] - 1 if i - 5 >= 0 else float("nan")
        r10 = px.iloc[i] / px.iloc[i - 10] - 1 if i - 10 >= 0 else float("nan")
        r21 = px.iloc[i] / px.iloc[i - 21] - 1 if i - 21 >= 0 else float("nan")
        d20 = px.iloc[i] / sma20.iloc[i][sym] - 1 if i >= 0 and sym in sma20.columns else float("nan")
        d50 = px.iloc[i] / sma50.iloc[i][sym] - 1 if i >= 0 and sym in sma50.columns else float("nan")
        gap = entry_px / prev_close - 1.0 if np.isfinite(prev_close) else float("nan")

        recs.append({
            "symbol": sym, "date": d, "semester": str(d.year) + ("H1" if d.month <= 6 else "H2"),
            "ret": ret, "mfe": out["mfe"], "mae": out["mae"], "exit": out["exit"], "holding": out["k"],
            "proba_extreme": float(r.proba_extreme),
            "atr_pct_20": atr_pct, "entry_gap": gap,
            "sym_r5": r5, "sym_r10": r10, "sym_r21": r21,
            "dist_sma20": d20, "dist_sma50": d50,
            "spy_r21": float(spy_r21.get(d, float("nan"))),
            "spy_vol21": float(spy_vol21.get(d, float("nan"))),
            "rsp_r21": float(rsp_r21.get(d, float("nan"))),
            "iwm_r21": float(iwm_r21.get(d, float("nan"))),
            "breadth_up21": float(breadth_up.get(d, float("nan"))),
            "breadth_sma20": float(breadth_sma20.get(d, float("nan"))),
            "xs_disp21": float(xs_disp21.get(d, float("nan"))),
            "mkt_atr": float(mkt_atr.get(d, float("nan"))),
        })
    t = pd.DataFrame(recs)
    t["TRUE_BAD"] = (t["mfe"] < MFE_BAD) & (t["ret"] < 0)
    t["WINNER"] = t["ret"] >= 0
    t["MOVED_LOSER"] = (t["mfe"] >= MFE_BAD) & (t["ret"] < 0)
    print(f"candidats retenus (hors gap): {len(t):,} | TRUE_BAD={int(t['TRUE_BAD'].sum()):,} "
          f"({100*t['TRUE_BAD'].mean():.1f}%) | WINNER={int(t['WINNER'].sum()):,} "
          f"| MOVED_LOSER={int(t['MOVED_LOSER'].sum()):,}", flush=True)

    # ── Vue par semestre ──
    print("\n" + "=" * 110)
    print("E12-1A  Vue par semestre (pool Extreme TOP20, chemin PROD)")
    print("=" * 110)
    print(f"  {'sem':<8} {'n':>6} {'TRUE_BAD%':>9} {'TB_n':>5} {'TB_sumRet%':>10} "
          f"{'WIN%':>6} {'MOVED_LOS%':>10} {'medMFE':>7} {'medMAE':>7}")
    for sem in sorted(t["semester"].unique()):
        g = t[t["semester"] == sem]
        tb = g[g["TRUE_BAD"]]
        print(f"  {sem:<8} {len(g):>6} {100*g['TRUE_BAD'].mean():>8.1f}% {len(tb):>5} "
              f"{100*tb['ret'].sum():>10.1f} {100*(g['ret']>=0).mean():>5.0f}% "
              f"{100*g['MOVED_LOSER'].mean():>9.0f}% {100*g['mfe'].median():>6.1f}% "
              f"{100*g['mae'].median():>6.1f}%")

    # ── Diagnostic univarie ──
    feats = ["proba_extreme", "atr_pct_20", "entry_gap", "sym_r5", "sym_r10", "sym_r21",
             "dist_sma20", "dist_sma50", "spy_r21", "spy_vol21", "rsp_r21", "iwm_r21",
             "breadth_up21", "breadth_sma20", "xs_disp21", "mkt_atr"]
    print("\n" + "=" * 110)
    print("E12-1A  Diagnostic univarie : AUC + filtre economique (quartile du bas)")
    print("=" * 110)
    print(f"  {'feature':<14} {'AUC':>6} {'dir':>4} | {'Q_bas%TB':>8} {'TB_evit%':>9} "
          f"{'WIN_retire%':>11} {'ratio$':>7} | {'med TB':>9} {'med WIN':>9}")
    rows = []
    for f in feats:
        sub = t[[f, "TRUE_BAD", "ret", "WINNER"]].dropna()
        if len(sub) < 500 or sub["TRUE_BAD"].nunique() < 2:
            continue
        y = sub["TRUE_BAD"].astype(int)
        x = sub[f]
        # AUC direction choisie : signe tel que TRUE_BAD plus bas (med TB < med WIN) => direction -1
        med_tb = float(x[y == 1].median())
        med_win = float(x[y == 0].median())
        sign = -1.0 if med_tb < med_win else 1.0
        xs = (x * sign)
        # AUC mann-whitney
        rk = xs.rank()
        auc = float((rk[y == 1].sum() - len(y[y == 1]) * (len(y[y == 1]) + 1) / 2.0)
                    / (len(y[y == 1]) * len(y[y == 0])))
        # filtre : quartile du bas de x*dir (le plus 'TRUE_BAD' lourd)
        q = xs.quantile(0.25)
        sel = xs <= q
        tb_sel = sub[sel & y.astype(bool)]
        win_sel = sub[sel & sub["WINNER"]]
        tb_evit = float(tb_sel["ret"].sum())
        win_lost = float(win_sel["ret"].sum())
        ratio = abs(tb_evit / win_lost) if abs(win_lost) > 1e-9 else float("inf")
        rows.append({"f": f, "auc": auc, "sign": int(sign),
                     "tb_pct_removed": 100 * tb_sel["ret"].count() / max(len(y[y == 1]), 1),
                     "tb_ret_avoided": tb_evit, "win_ret_lost": win_lost, "ratio": ratio,
                     "med_tb": med_tb, "med_win": med_win})
        print(f"  {f:<14} {auc:>6.3f} {int(sign):>4} | {100*tb_sel['ret'].count()/max(len(y[y==1]),1):>7.0f}% "
              f"{100*tb_evit:>8.1f} {100*win_lost:>10.1f} {ratio:>7.2f} | "
              f"{100*med_tb:>8.2f}% {100*med_win:>8.2f}%")

    # ── Stabilite par semestre (top-5 AUC) ──
    top = sorted(rows, key=lambda r: -r["auc"])[:5]
    print("\n" + "=" * 110)
    print("Stabilite AUC par semestre (top-5 features)")
    print("=" * 110)
    sems = sorted(t["semester"].unique())
    print(f"  {'feature':<14}" + "".join(f"{s:>9}" for s in sems))
    for r0 in top:
        line = f"  {r0['f']:<14}"
        for sem in sems:
            sub = t[(t["semester"] == sem)][[r0["f"], "TRUE_BAD"]].dropna()
            if len(sub) < 100 or sub["TRUE_BAD"].nunique() < 2:
                line += f"{'-':>9}"
                continue
            y = sub["TRUE_BAD"].astype(int)
            xs = sub[r0["f"]] * r0["sign"]
            rk = xs.rank()
            auc = float((rk[y == 1].sum() - len(y[y == 1]) * (len(y[y == 1]) + 1) / 2.0)
                        / (len(y[y == 1]) * len(y[y == 0])))
            line += f"{auc:>9.3f}"
        print(line)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    t.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
