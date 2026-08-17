# -*- coding: utf-8 -*-
"""P19 — Pureté intrinsèque du Global Rank B25 (SANS moteur de trading).

Mesure la capacité de classement cross-sectionnelle du rank, indépendamment de
la sélection/risk/protection : IC (Spearman), ICIR, hit rate, déciles, spread
TOP-BOTTOM, et split LONG (top décile) vs SHORT (bottom décile).

Méthode :
- rank utilisé : global_rank_20 (percentile 0-1, haut = meilleur) du batch B25.
- forward return : adj_close[t+20 séances] / adj_close[t] - 1 (source eodhd_eod).
- univers : TOUS les symboles avec un rank à la date (cross-section complète,
  aucun filtre sélection/risk) — c'est le test de pureté du signal.
- IC par date = Spearman(rank, forward_ret) ; agrégé par année.
- déciles par année : forward return moyen par déclie de rank.
- LONG spread = forward return du top décile ; SHORT spread = forward return
  du bottom décile (un bon signal SHORT → négatif) ; TOP-BOTTOM = top - bottom.

⚠️ 2020-2021 (et 2023-2024 H1) sont vraisemblablement PARTIELLEMENT IN-SAMPLE
pour B25 (trainé en 2026-08). Les périodes OOS propres sont 2022+ (et surtout
2026). À interpréter en conséquence.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sqlalchemy as sa
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
B25 = "model-factory-20260811223551-ef2cd0"
ENG = sa.create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)


def load_ranks() -> pd.DataFrame:
    with ENG.connect() as c:
        r = pd.read_sql(
            sa.text(
                "SELECT symbol, `date`, global_rank_5, global_rank_10, global_rank_20 "
                "FROM global_rank_history WHERE batch_id=:b"
            ).bindparams(b=B25),
            c,
        )
    r["date"] = pd.to_datetime(r["date"])
    return r


def load_bars(symbols: list[str]) -> pd.DataFrame:
    syms = sorted(set(symbols))
    with ENG.connect() as c:
        b = pd.read_sql(
            sa.text(
                "SELECT symbol, `date`, adj_close FROM stock_bars_daily "
                "WHERE symbol IN :s AND data_source='eodhd_eod'"
            ).bindparams(sa.bindparam("s", expanding=True)),
            c,
            params={"s": syms},
        )
    b["date"] = pd.to_datetime(b["date"])
    return b


def spearman_ic(grp: pd.DataFrame, rank_col: str, ret_col: str) -> float:
    g = grp[[rank_col, ret_col]].dropna()
    if len(g) < 30:
        return np.nan
    ic, _ = spearmanr(g[rank_col], g[ret_col])
    return ic


def main() -> None:
    ranks = load_ranks()
    symbols = sorted(ranks["symbol"].unique())
    print(f"symboles: {len(symbols)} | lignes rank: {len(ranks):,}")

    bars = load_bars(symbols)
    px = bars.pivot_table(index="date", columns="symbol", values="adj_close")
    px = px.sort_index()
    # forward return sur H séances
    ret = {}
    for h, col in [(20, "global_rank_20"), (10, "global_rank_10"), (5, "global_rank_5")]:
        ret[h] = px.shift(-h) / px - 1.0
    ret5 = ret[5]; ret10 = ret[10]; ret20 = ret[20]

    # fusion rank + forward returns (le pivot garde les symboles comme colonnes)
    df = ranks.merge(
        ret20.reset_index().melt(id_vars="date", var_name="symbol", value_name="fwd20"),
        on=["date", "symbol"], how="left",
    )
    df = df.merge(
        ret10.reset_index().melt(id_vars="date", var_name="symbol", value_name="fwd10"),
        on=["date", "symbol"], how="left",
    )
    df = df.merge(
        ret5.reset_index().melt(id_vars="date", var_name="symbol", value_name="fwd5"),
        on=["date", "symbol"], how="left",
    )
    df["year"] = df["date"].dt.year
    print(f"lignes analysables: {len(df):,}")

    # IC par date pour H20
    ic = (
        df[["date", "year", "global_rank_20", "fwd20"]]
        .dropna()
        .groupby("date")
        .apply(lambda g: pd.Series({"ic20": spearman_ic(g, "global_rank_20", "fwd20")}), include_groups=False)
        .reset_index()
    )
    ic["year"] = ic["date"].dt.year
    ic = ic.dropna(subset=["ic20"])

    print("\n" + "=" * 100)
    print("IC / ICIR / hit rate — global_rank_20 vs forward return 20j (par année)")
    print("=" * 100)
    print(f"{'année':6s} {'dates':>6s} {'IC':>8s} {'IC std':>8s} {'ICIR':>8s} {'hit%':>6s}")
    summary = []
    for y, g in ic.groupby("year"):
        mean_ic = g["ic20"].mean()
        std_ic = g["ic20"].std()
        icir = mean_ic / std_ic if std_ic and not np.isnan(std_ic) else np.nan
        hit = (g["ic20"] > 0).mean() * 100
        summary.append((y, len(g), mean_ic, std_ic, icir, hit))
        print(f"{y:6d} {len(g):6d} {mean_ic:8.4f} {std_ic:8.4f} {icir:8.3f} {hit:6.1f}")
    # total
    mean_ic = ic["ic20"].mean(); std_ic = ic["ic20"].std()
    print(f"{'ALL':6s} {len(ic):6d} {mean_ic:8.4f} {std_ic:8.4f} {mean_ic/std_ic:8.3f} {(ic['ic20']>0).mean()*100:6.1f}")

    # Déciles par année
    print("\n" + "=" * 100)
    print("Déciles — forward return 20j moyen par déclie de global_rank_20 (par année)")
    print("=" * 100)
    d = df[["year", "global_rank_20", "fwd20"]].dropna()
    d["decile"] = pd.qcut(d["global_rank_20"], 10, labels=False)  # 0=bottom .. 9=top
    print(f"{'année':6s} {'D1(btm)':>9s} {'D2':>8s} {'D3':>8s} {'D4':>8s} {'D5':>8s} {'D6':>8s} {'D7':>8s} {'D8':>8s} {'D9':>8s} {'D10(top)':>9s} {'TOP-BOT':>9s}")
    for y, g in d.groupby("year"):
        m = g.groupby("decile")["fwd20"].mean()
        spread = m.get(9, np.nan) - m.get(0, np.nan)
        row = f"{y:6d}" + "".join(f"{m.get(i, np.nan):9.3f}" for i in range(10)) + f"{spread:9.3f}"
        print(row)

    # LONG / SHORT spread par année (top/bottom décile)
    print("\n" + "=" * 100)
    print("LONG spread (top10) vs SHORT spread (bottom10) vs TOP-BOTTOM (H20)")
    print("=" * 100)
    print(f"{'année':6s} {'LONG(top10)':>12s} {'SHORT(btm10)':>12s} {'SHORT profit':>12s} {'TOP-BOT':>9s}")
    for y, g in d.groupby("year"):
        m = g.groupby("decile")["fwd20"].mean()
        top = m.get(9, np.nan); btm = m.get(0, np.nan)
        print(f"{y:6d} {top:12.3f} {btm:12.3f} {-btm:12.3f} {top-btm:9.3f}")


if __name__ == "__main__":
    main()
