"""P2-4 — IC par décile × côté prédit sur les prédictions B25 en DB.

Question centrale : le modèle trouve-t-il les GAGNANTS (top du classement)
aussi bien que les PERDANTS (bottom) ? La jambe LONG du backtest ne gagne
rien (−2.2k vs +202k short) — est-ce un problème de ranking asymétrique
ou d'exploitation ?

Calcule, sur la fenêtre backtest 2019-01-02 → 2024-06-28 :
1. IC Rank (Spearman) global par horizon
2. Retour forward excédentaire vs SPY par DÉCILE de rang (monotonie)
3. Hit-rate (P(fwd_excess > 0)) par décile
4. Le tout SPLIT par côté prédit (predicted_side long/short du per-sector)
5. Par année (effet régime)

Usage : python scripts/analyze_p24_decile_side_ic.py
"""
import os
import sys

sys.path.insert(0, r"F:\projets")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

BATCH = "model-factory-20260811223551-ef2cd0"
START = "2019-01-02"
END = "2024-06-28"
HORIZONS = [3, 5, 10, 15, 20]
OUT_DIR = r"F:\projets\artifacts\metrics"
OUT_CSV = os.path.join(OUT_DIR, "p24_decile_side_ic.csv")


def main() -> None:
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True, pool_pre_ping=True)

    # ── 1. Rangs globaux B25 ──
    rank_cols = ", ".join(f"global_rank_{h}" for h in HORIZONS)
    with engine.connect() as conn:
        ranks = pd.read_sql(
            text(
                f"SELECT symbol, `date`, {rank_cols} FROM global_rank_history "
                "WHERE batch_id=:b AND `date` BETWEEN :s AND :e"
            ),
            conn,
            params={"b": BATCH, "s": START, "e": END},
            parse_dates=["date"],
        )
    ranks["symbol"] = ranks["symbol"].astype(str).str.upper()
    ranks["date"] = ranks["date"].dt.normalize()
    print(f"rangs chargés : {len(ranks)} lignes, {ranks['symbol'].nunique()} symboles")

    # ── 2. Closes (symboles de l'univers + SPY) ──
    symbols = sorted(ranks["symbol"].unique().tolist()) + ["SPY"]
    with engine.connect() as conn:
        bars = pd.read_sql(
            text(
                "SELECT symbol, `date`, COALESCE(adj_close, `close`) AS close "
                "FROM stock_bars_daily WHERE symbol IN :syms "
                "AND `date` BETWEEN DATE_SUB(:s, INTERVAL 40 DAY) AND DATE_ADD(:e, INTERVAL 40 DAY)"
            ),
            conn,
            params={"syms": tuple(symbols), "s": START, "e": END},
            parse_dates=["date"],
        )
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars["date"] = bars["date"].dt.normalize()
    print(f"bars chargés : {len(bars)} lignes")

    # ── 3. Returns forward par horizon (pivot par symbole) ──
    piv = bars.pivot_table(index="date", columns="symbol", values="close").sort_index()
    spy = piv["SPY"]
    fwd = {}
    for h in HORIZONS:
        fwd_all = piv.shift(-h) / piv - 1.0
        fwd_spy = spy.shift(-h) / spy - 1.0
        fwd[h] = fwd_all.sub(fwd_spy, axis=0)

    # ── 4. Merge rang + retour forward ──
    for h in HORIZONS:
        f = fwd[h].stack().rename(f"fwd_excess_{h}").reset_index()
        f.columns = ["date", "symbol", f"fwd_excess_{h}"]
        ranks = ranks.merge(f, on=["date", "symbol"], how="left")
    print(f"merge fwd ok : {len(ranks)} lignes")

    # ── 5. Prédictions per-sector B25 (side) ──
    with engine.connect() as conn:
        preds = pd.read_sql(
            text(
                "SELECT mp.symbol, mp.prediction_date, mp.predicted_side, "
                "mp.proba_long, mp.proba_short, mp.created_at "
                "FROM model_predictions mp "
                "JOIN model_training_run tr ON tr.run_id=mp.run_id "
                "WHERE tr.batch_id=:b AND mp.prediction_date BETWEEN :s AND :e"
            ),
            conn,
            params={"b": BATCH, "s": START, "e": END},
            parse_dates=["prediction_date", "created_at"],
        )
    preds["symbol"] = preds["symbol"].astype(str).str.upper()
    preds["prediction_date"] = preds["prediction_date"].dt.normalize()
    preds = preds.sort_values("created_at").drop_duplicates(subset=["symbol", "prediction_date"], keep="last")
    print(f"prédictions B25 : {len(preds)} lignes (side: {preds['predicted_side'].value_counts(dropna=False).to_dict()})")
    ranks = ranks.merge(
        preds[["symbol", "prediction_date", "predicted_side", "proba_long", "proba_short"]],
        left_on=["symbol", "date"], right_on=["symbol", "prediction_date"], how="left",
    )
    ranks["side"] = ranks["predicted_side"].fillna("none")

    # ── 6. Déciles de rang par date ──
    for h in HORIZONS:
        ranks[f"decile_{h}"] = (
            ranks.groupby("date")[f"global_rank_{h}"].rank(pct=True, method="first") * 10
        ).apply(np.ceil).clip(1, 10)
    ranks["year"] = ranks["date"].dt.year

    # ── 7. Analyse ──
    rows = []
    for h in HORIZONS:
        rc, fc = f"global_rank_{h}", f"fwd_excess_{h}"
        dc = f"decile_{h}"
        sub = ranks[[rc, fc, dc, "side", "year"]].dropna(subset=[rc, fc])
        ic_global = sub[[rc, fc]].corr(method="spearman").iloc[0, 1]
        rows.append({"h": h, "scope": "ALL", "decile": np.nan, "side": "all",
                     "n": len(sub), "ic": ic_global, "fwd_mean": sub[fc].mean(),
                     "hit": (sub[fc] > 0).mean()})
        for side in ["long", "short", "none"]:
            s = sub[sub["side"] == side]
            if len(s) < 100:
                continue
            rows.append({"h": h, "scope": "SIDE", "decile": np.nan, "side": side,
                         "n": len(s), "ic": s[[rc, fc]].corr(method="spearman").iloc[0, 1],
                         "fwd_mean": s[fc].mean(), "hit": (s[fc] > 0).mean()})
        g = sub.groupby(dc).agg(n=(fc, "size"), fwd_mean=(fc, "mean"), hit=(fc, lambda x: (x > 0).mean()),
                                ic=(rc, lambda x: x.corr(sub.loc[x.index, fc], method="spearman")))
        for dec, r in g.iterrows():
            rows.append({"h": h, "scope": "DECILE", "decile": dec, "side": "all",
                         "n": r["n"], "ic": r["ic"], "fwd_mean": r["fwd_mean"], "hit": r["hit"]})
        # décile × côté
        for side in ["long", "short"]:
            s = sub[sub["side"] == side]
            if len(s) < 500:
                continue
            gs = s.groupby(dc).agg(n=(fc, "size"), fwd_mean=(fc, "mean"), hit=(fc, lambda x: (x > 0).mean()))
            for dec, r in gs.iterrows():
                rows.append({"h": h, "scope": "DECILE_SIDE", "decile": dec, "side": side,
                             "n": r["n"], "ic": np.nan, "fwd_mean": r["fwd_mean"], "hit": r["hit"]})
        # par année
        gy = sub.groupby("year").agg(n=(fc, "size"), fwd_mean=(fc, "mean"), hit=(fc, lambda x: (x > 0).mean()),
                                     ic=(rc, lambda x: x.corr(sub.loc[x.index, fc], method="spearman")))
        for yr, r in gy.iterrows():
            rows.append({"h": h, "scope": "YEAR", "decile": np.nan, "side": "all",
                         "n": r["n"], "ic": r["ic"], "fwd_mean": r["fwd_mean"], "hit": r["hit"]})

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)

    # ── 8. Affichage ──
    print("\n" + "=" * 90)
    print("IC GLOBAL / PAR CÔTÉ (Spearman rank vs fwd excess vs SPY)")
    print("=" * 90)
    piv_ic = out[out["scope"].isin(["ALL", "SIDE"])].pivot_table(
        index="h", columns="side", values="ic", aggfunc="first")
    print(piv_ic.round(4).to_string())

    print("\n" + "=" * 90)
    print("RETOUR FORWARD MOYEN PAR DÉCILE (H10) — monotonie ?")
    print("=" * 90)
    d10 = out[(out["scope"] == "DECILE") & (out["h"] == 10)].pivot(index="decile", columns="side", values="fwd_mean")
    print((d10 * 100).round(3).to_string())

    print("\n" + "=" * 90)
    print("RETOUR FORWARD MOYEN PAR DÉCILE × CÔTÉ (H10)")
    print("=" * 90)
    ds10 = out[(out["scope"] == "DECILE_SIDE") & (out["h"] == 10)].pivot(index="decile", columns="side", values="fwd_mean")
    print((ds10 * 100).round(3).to_string())

    print("\n" + "=" * 90)
    print("HIT-RATE PAR DÉCILE × CÔTÉ (H10)")
    print("=" * 90)
    hs10 = out[(out["scope"] == "DECILE_SIDE") & (out["h"] == 10)].pivot(index="decile", columns="side", values="hit")
    print((hs10 * 100).round(1).to_string())

    print("\n" + "=" * 90)
    print("IC PAR ANNÉE (H10)")
    print("=" * 90)
    y10 = out[(out["scope"] == "YEAR") & (out["h"] == 10)][["decile", "n", "ic", "fwd_mean", "hit"]]
    print(y10.round(4).to_string(index=False))

    print(f"\n→ {OUT_CSV}")


if __name__ == "__main__":
    main()
