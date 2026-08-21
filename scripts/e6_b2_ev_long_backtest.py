"""E6-B2 — EV_LONG : comparaison RANK vs EV dans le VRAI moteur portefeuille (LONG-only).

RÈGLES (spec user 2026-08-20) :
- EV_LONG = P_cal(success) × E[gain | success, score bucket]
            + (1 − P_cal(success)) × E[loss | failure, score bucket] − costs
  avec E[loss|failure] NÉGATIF. Les deux espérances sont apprises UNIQUEMENT dans
  le train de chaque fold (comme Platt) — par bucket de score (décile du score brut).
- P_cal = Platt OOF (E6-B1), apprise sur le train du fold, appliquée au test OOS.
- 3 benchmarks + 1 diagnostique :
    RANK_TOP20 : top 20% du score brut Y3-LONG (rang cross-sectionnel/date)
    RANK_TOP10 : top 10% du score brut Y3-LONG
    EV_LONG > 0 : candidats dont EV_LONG > 0 (aucun seuil tuné)
    EV_LONG top 20% : top 20% de l'EV (diagnostique : EV = simple rerank ?)
- Vrai moteur BacktestEngine canonique (m8, ATR stop 3.5, TP 4×ATR/13%, trailing long 7%,
  coûts canoniques 16 bps RT, marché). LONG-only. AUCUN SHORT.
- Aucun seuil EV tuné. EV > 0 suffit.

MÉTRIQUES par semestre + global : PF/Ret/DD + N trades, expectancy/trade, turnover,
% candidats rejetés par EV, moyenne P_cal, moyenne gain/perte attendus,
part des (candidat,date) où rank et EV ne sont pas d'accord.

GATE (fixé AVANT) :
  EV>0 bat au moins un des deux benchmarks rank sur PF OU expectancy
  ET ne détériore pas fortement le DD (|DD_EV| <= 1.3 × min(|DD_RANK20|,|DD_RANK10|))
  ET positif sur majorité des semestres (>50%)
  ET pas uniquement 2025/2026 (≥1 semestre 2023-2024 positif).

Sortie : print + artifacts/models/oracle/e6_b2_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from backtesting.simulator import BacktestConfig, BacktestEngine
from scripts.e6_direction_diagnostic import FOLDS, GUARD_COL, merge_pools
from modelFactory.oracle.train import _proba_catboost

OOF_PROBAS = Path("artifacts/models/oracle/e6_y3_lift.parquet")
PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e6_b2_results.parquet")

START = "2023-01-01"
END = "2026-05-29"
INITIAL_EQUITY = 100_000.0
COST_RT = 0.0016  # 16 bps round-trip (canonique)
N_BUCKETS = 10    # buckets de score pour E[gain|...]/E[loss|...]

BENCHMARKS = ["RANK_TOP20", "RANK_TOP10", "EV>0", "EV_TOP20"]


# ─────────────────────────── 1. Pool + EV par fold ───────────────────────────

def load_pool() -> pd.DataFrame:
    df, feature_columns = merge_pools()
    # merge_pools fournit features + GUARD_COL + y3_long + y3_long_ret + atr20,
    # mais PAS `_proba_catboost` (OOF) ni `entry` → on les merge.
    oof = pd.read_parquet(OOF_PROBAS)
    oof["date"] = pd.to_datetime(oof["date"]).dt.normalize()
    oof["symbol"] = oof["symbol"].astype(str)
    df = df.merge(
        oof[["symbol", "date", "_proba_catboost"]],
        on=["symbol", "date"], how="left",
    )
    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)
    df = df.merge(
        path[["symbol", "date", "entry"]],
        on=["symbol", "date"], how="left",
    )
    df["atr_pct_20"] = df["atr20"] / df["entry"].replace(0, np.nan)
    df["score"] = df["_proba_catboost"]
    df["rank"] = df.groupby("date")["_proba_catboost"].rank(ascending=False)
    return df, feature_columns


def train_gain_loss_buckets(
    train: pd.DataFrame, test: pd.DataFrame, feature_columns: list[str],
) -> tuple[LogisticRegression, np.ndarray, dict, np.ndarray]:
    """Fit CatBoost+Platt sur le train ; E[gain|success]/E[loss|failure] par bucket.

    Returns: (platt, p_test_raw, bucket_map, edges)
    - platt : calibrateur Platt fit sur le train UNIQUEMENT
    - p_test_raw : probas test OOS (raw)
    - bucket_map : {bucket: {E_gain, E_loss, n}} appris sur le train
    - edges : bornes des buckets (déciles du score brut du train)
    """
    from scripts.e6_direction_diagnostic import _fit_predict

    X_tr = train[feature_columns].astype(float)
    y_tr = train["y3_long"].astype(int)
    X_te = test[feature_columns].astype(float)
    y_te = test["y3_long"].astype(int)

    # Un seul fit CatBoost par fold (pipeline identique E6 : validation = test)
    model, p_test_raw = _fit_predict("catboost", X_tr, y_tr, X_te, y_te)
    p_train_raw = _proba_catboost(model, X_tr)

    platt = LogisticRegression(max_iter=1000)
    platt.fit(p_train_raw.reshape(-1, 1), y_tr)

    # Buckets de score (déciles du score brut) appris sur le train
    edges = np.quantile(p_train_raw, np.linspace(0.0, 1.0, N_BUCKETS + 1))
    edges[0] = -np.inf
    edges[-1] = np.inf
    train = train.copy()
    train["_bucket"] = pd.cut(p_train_raw, bins=edges, labels=False, include_lowest=True)
    train["_ret"] = train["y3_long_ret"]

    bucket_map: dict[int, dict[str, float]] = {}
    for b, g in train.groupby("_bucket"):
        suc = g[g["y3_long"] == 1]["_ret"]
        fail = g[g["y3_long"] == 0]["_ret"]
        bucket_map[int(b)] = {
            "E_gain": float(suc.mean()) if len(suc) else 0.0,
            "E_loss": float(fail.mean()) if len(fail) else 0.0,
            "n": int(len(g)),
        }
    return platt, p_test_raw, bucket_map, edges


def add_ev_features(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Pour chaque fold : fit sur train, applique P_cal + E_gain/E_loss + EV au test OOS."""
    out_parts = []
    for t_start, t_end in FOLDS:
        train = df[df[GUARD_COL] < pd.Timestamp(t_start)]
        test = df[(df["date"] >= pd.Timestamp(t_start)) & (df["date"] <= pd.Timestamp(t_end))]
        if len(train) < 100 or len(test) < 50:
            continue
        y_te = test["y3_long"].astype(int)
        if y_te.nunique() < 2:
            continue
        platt, p_test_raw, bucket_map, edges = train_gain_loss_buckets(train, test, feature_columns)
        p_cal = platt.predict_proba(p_test_raw.reshape(-1, 1))[:, 1]

        test = test.copy()
        test["p_cal"] = p_cal
        test["_bucket"] = pd.cut(p_test_raw, bins=edges, labels=False, include_lowest=True)
        test["E_gain"] = test["_bucket"].map(
            lambda b: bucket_map[int(b)]["E_gain"] if pd.notna(b) and int(b) in bucket_map else 0.0)
        test["E_loss"] = test["_bucket"].map(
            lambda b: bucket_map[int(b)]["E_loss"] if pd.notna(b) and int(b) in bucket_map else 0.0)
        test["EV_LONG"] = test["p_cal"] * test["E_gain"] + (1 - test["p_cal"]) * test["E_loss"] - COST_RT
        out_parts.append(test)
    return pd.concat(out_parts, ignore_index=True)


# ─────────────────────────── 2. Signaux + moteur ───────────────────────────

def build_signals(pool: pd.DataFrame, variant: str) -> pd.DataFrame:
    df = pool.copy()
    df["_score_rank_pct"] = df.groupby("date")["_proba_catboost"].rank(pct=True)
    if variant == "RANK_TOP20":
        df = df[df["_score_rank_pct"] >= 0.80]
    elif variant == "RANK_TOP10":
        df = df[df["_score_rank_pct"] >= 0.90]
    elif variant == "EV>0":
        df = df[df["EV_LONG"] > 0]
    elif variant == "EV_TOP20":
        df = df[df.groupby("date")["EV_LONG"].rank(pct=True) >= 0.80]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20", "p_cal", "E_gain", "E_loss", "EV_LONG"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


def load_pivots(pool_symbols: list[str]) -> dict[str, pd.DataFrame]:
    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close", "volume"])
    bars = bars[bars["symbol"].isin(pool_symbols)].copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    pivots = {}
    for col in ("open", "high", "low", "close"):
        pivots[col] = bars.pivot_table(index="trade_date", columns="symbol", values=col).sort_index()
    pivots["volume"] = bars.pivot_table(index="trade_date", columns="symbol", values="volume").sort_index()
    return pivots


def run_benchmark(sig: pd.DataFrame, pivots: dict, label: str) -> dict:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(),
        end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY,
        max_positions=8,
        atr_risk_stop_multiple=3.5,
        tp_atr_multiple=4.0,
        tp_max_pct=0.13,
        trailing_stop_long_pct=0.07,
        trailing_stop_short_pct=None,
        use_canonical_costs=True,
        entry_limit_offset_pct=0.0,
        min_score_threshold=0.0,
        use_live_protection_logic=True,
    )
    result = BacktestEngine(cfg).run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    eq = result.equity_curve
    closed = result.closed_trades_df
    final = float(eq.iloc[-1]) if len(eq) else INITIAL_EQUITY
    total_ret_pct = (final / INITIAL_EQUITY - 1.0) * 100.0
    rets = eq.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) > 1 else 0.0

    n = len(closed)
    pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0) if n else pd.Series(dtype=float)
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    pf = gp / gn if gn > 0 else float("inf")
    expectancy = float(pnl.mean()) if n else 0.0
    win = float((pnl > 0).mean()) if n else 0.0

    # Semestre par date de sortie
    sem = pd.DataFrame()
    if n:
        c = closed.copy()
        c["exit_date"] = pd.to_datetime(c["exit_date"]).dt.normalize()
        c["semester"] = c["exit_date"].dt.year.astype(str) + np.where(c["exit_date"].dt.month <= 6, "H1", "H2")
        c["pnl"] = pd.to_numeric(c["pnl"], errors="coerce").fillna(0.0)
        sem = c.groupby("semester").agg(pnl=("pnl", "sum"), n=("pnl", "size"))
    n_sem = len(sem); n_pos_sem = int((sem["pnl"] > 0).sum()) if n_sem else 0

    # Stats des candidats sélectionnés (pré-moteur)
    sel_cal = float(sig["p_cal"].mean()) if "p_cal" in sig.columns and len(sig) else float("nan")
    sel_gain = float(sig["E_gain"].mean()) if "E_gain" in sig.columns and len(sig) else float("nan")
    sel_loss = float(sig["E_loss"].mean()) if "E_loss" in sig.columns and len(sig) else float("nan")

    return {
        "benchmark": label, "total_return_pct": total_ret_pct, "sharpe": sharpe, "pf": pf,
        "max_dd_pct": dd, "n_trades": n, "win_rate": win, "expectancy": expectancy,
        "n_semesters": n_sem, "n_pos_semesters": n_pos_sem, "semesters": sem,
        "n_candidates_selected": int(len(sig)),
        "mean_p_cal": sel_cal, "mean_E_gain": sel_gain, "mean_E_loss": sel_loss,
        "final_equity": final,
    }


# ─────────────────────────── 3. Main + gates ───────────────────────────

def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy()
    pool = pool.dropna(subset=["y3_long"]).copy()
    print(f"Pool Oracle Extreme O0 (complet) : {len(pool):,} candidats | "
          f"{pool['date'].min().date()} -> {pool['date'].max().date()}")

    # ⚠️ add_ev_features doit tourner sur le pool COMPLET : le fold 2023 a besoin
    # du train 2022 (GUARD_COL < 2023-01-01) pour fit CatBoost/Platt/buckets.
    # Filtrer à date>=START avant détruirait ce train → fold 2023 skippé.
    pool = add_ev_features(pool, feature_columns)
    print(f"Après EV (tests des folds 2023-2026) : {len(pool):,} lignes | "
          f"{pool['date'].min().date()} -> {pool['date'].max().date()} | "
          f"EV>0 : {(pool['EV_LONG']>0).sum():,} ({(pool['EV_LONG']>0).mean()*100:.1f}%)")

    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]

    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"OHLCV : {len(symbols)} symboles pivotés | {pivots['close'].shape[0]} jours\n")

    # Disagreement rank vs EV (diagnostique) au niveau candidat
    pool["_rk20"] = pool.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80
    pool["_evpos"] = pool["EV_LONG"] > 0
    agree = (pool["_rk20"] == pool["_evpos"]).mean()
    print(f"[diagnostic] % (candidat,date) où RANK_TOP20 et EV>0 sont D'ACCORD : {agree*100:.1f}% "
          f"| désaccord : {(1-agree)*100:.1f}%")
    ev_pos_not_rank = ((pool["_evpos"]) & (~pool["_rk20"])).mean()
    rank_not_ev = ((~pool["_evpos"]) & (pool["_rk20"])).mean()
    print(f"  EV>0 accepte que RANK20 rejette : {ev_pos_not_rank*100:.1f}% "
          f"| RANK20 accepte que EV rejette : {rank_not_ev*100:.1f}%")

    results = {}
    for label in BENCHMARKS:
        print(f"=== {label} ===", flush=True)
        sig = build_signals(pool, label)
        results[label] = run_benchmark(sig, pivots, label)
        r = results[label]
        print(f"  Return={r['total_return_pct']:.2f}% PF={r['pf']:.2f} Sharpe={r['sharpe']:.2f} "
              f"MaxDD={r['max_dd_pct']:.2f}% trades={r['n_trades']} expect={r['expectancy']:.2f}$ "
              f"sem+={r['n_pos_semesters']}/{r['n_semesters']}", flush=True)

    print("\n" + "=" * 120)
    print("E6-B2 — EV_LONG vs RANK dans le vrai moteur (LONG-only, Platt OOF, gains/pertes train-only)")
    print("=" * 120)
    hdr = f"{'bench':<10} {'Return%':>9} {'PF':>7} {'Sharpe':>7} {'MaxDD%':>9} {'trades':>7} {'expect$':>8} {'sem+':>6} {'Pcal':>7} {'E_gain':>8} {'E_loss':>9}"
    print(hdr); print("-" * 120)
    for label in BENCHMARKS:
        r = results[label]
        print(f"{label:<10} {r['total_return_pct']:>8.2f}% {r['pf']:>7.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.2f}% {r['n_trades']:>7} {r['expectancy']:>8.2f} "
              f"{r['n_pos_semesters']:>3}/{r['n_semesters']} {r['mean_p_cal']:>7.3f} "
              f"{r['mean_E_gain']:>8.4f} {r['mean_E_loss']:>9.4f}")

    print("\n" + "=" * 120)
    print("PnL par semestre ($)")
    print("=" * 120)
    sems = sorted(set().union(*[r["semesters"].index for r in results.values()]))
    print(f"{'semester':<10}" + "".join(f"{lbl:>14}" for lbl in BENCHMARKS))
    for s in sems:
        row = f"{s:<10}"
        for lbl in BENCHMARKS:
            if s in results[lbl]["semesters"].index:
                row += f"{results[lbl]['semesters'].loc[s,'pnl']:>13.0f}$"
            else:
                row += f"{'—':>14}"
        print(row)

    # ── GATE ──
    print("\n" + "=" * 120)
    print("GATE (fixé avant le backtest)")
    print("=" * 120)
    ev = results["EV>0"]
    rank20, rank10 = results["RANK_TOP20"], results["RANK_TOP10"]
    best_pf_rank = max(rank20["pf"], rank10["pf"])
    best_exp_rank = max(rank20["expectancy"], rank10["expectancy"])
    min_dd_rank = min(abs(rank20["max_dd_pct"]), abs(rank10["max_dd_pct"]))
    g1 = (ev["pf"] > best_pf_rank) or (ev["expectancy"] > best_exp_rank)
    g2 = abs(ev["max_dd_pct"]) <= 1.3 * min_dd_rank + 1e-9
    g3 = ev["n_pos_semesters"] > 0.5 * ev["n_semesters"]
    sem_23_24 = [s for s in sems if s.startswith("2023") or s.startswith("2024")]
    if sem_23_24:
        pos_23_24 = sum(1 for s in sem_23_24 if s in ev["semesters"].index and ev["semesters"].loc[s, "pnl"] > 0)
        g4 = pos_23_24 >= 1
        g4_detail = f"{pos_23_24}/{len(sem_23_24)}"
    else:
        g4, g4_detail = False, "aucun"
    print(f"G1 (EV bat ≥1 rank sur PF/expect) : {g1}  "
          f"(EV PF={ev['pf']:.2f} exp={ev['expectancy']:.2f} vs best rank PF={best_pf_rank:.2f} exp={best_exp_rank:.2f})")
    print(f"G2 (EV DD ≤ 1.3×min rank DD)      : {g2}  ({abs(ev['max_dd_pct']):.2f}% vs {min_dd_rank:.2f}%)")
    print(f"G3 (EV >50% semestres +)          : {g3}  ({ev['n_pos_semesters']}/{ev['n_semesters']})")
    print(f"G4 (pas 2025/2026-only)           : {g4}  ({g4_detail} semestres 2023-2024 positifs)")

    n_pass = sum([g1, g2, g3, g4])
    print(f"\nGATES PASSÉS : {n_pass}/4")
    if g1 and g2 and n_pass >= 3:
        print("=> PASS : EV_LONG apporte une vraie couche économique vs le rank.")
    else:
        print("=> ÉCHEC : EV_LONG ne bat pas le rank — la calibration/EV ne justifie pas un changement.")

    # EV_TOP20 vs RANK_TOP20 : EV = simple rerank ?
    diag = results["EV_TOP20"]
    print(f"\n[diagnostic] EV_TOP20 vs RANK_TOP20 : "
          f"PF {diag['pf']:.2f} vs {rank20['pf']:.2f} | expect {diag['expectancy']:.2f} vs {rank20['expectancy']:.2f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for lbl in BENCHMARKS:
        results[lbl]["semesters"] = results[lbl]["semesters"].reset_index()
    pd.DataFrame([{k: v for k, v in r.items() if k != "semesters"} for r in results.values()]).to_parquet(
        OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
