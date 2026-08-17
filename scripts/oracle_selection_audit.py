"""Analyse ORACLE du backtest 20260817_205031_2a2836d1.

Question : le modèle trouve-t-il les achats/ventes "oracle" ?
Pour chaque entrée (long/short), le symbole était-il dans le TOP 10% (long) /
BOTTOM 10% (short) des rendements futurs RÉELS de l'univers ML ce jour-là ?

- Univers oracle   = symboles avec prédiction ML (model_predictions, run_id
                     model-factory-20260811223551-ef2cd0_globalrank_synth)
                     sur le signal_date -> pool où la cascade top-10% opère
- Rendement futur  = adj_close[D+H] / adj_close[D] - 1  (H = 10, 20 jours ouvrés)
- Oracle long      = top 10% des rendements futurs (décile 10)
- Oracle short     = bottom 10% des rendements futurs (décile 1)
- Baseline hasard  = 10% (un pick aléatoire de l'univers)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, create_engine, text

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
RUN_DIR = Path(
    r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_205031_2a2836d1\artifacts"
)
BATCH_RUN_ID = "model-factory-20260811223551-ef2cd0_globalrank_synth"
HORIZONS = (10, 20)
OUT = sys.stdout


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def main() -> None:
    # 1. Trades : chaque ligne = une entrée (round-trip) du pipeline
    trades = pd.read_csv(RUN_DIR / "trades.csv", low_memory=False)
    trades["signal_date"] = pd.to_datetime(trades["signal_date"], errors="coerce").dt.normalize()
    trades = trades.dropna(subset=["signal_date"])
    trades = trades[trades["side"].isin(["buy", "sell"])]
    p(f"Entrées : {len(trades)} (longs={(trades['side']=='buy').sum()}, "
      f"shorts={(trades['side']=='sell').sum()})")

    # 2. Univers ML : symboles prédits par jour (model_predictions)
    with ENGINE.connect() as conn:
        preds = pd.read_sql(
            text(
                "SELECT symbol, prediction_date AS trade_date "
                "FROM model_predictions "
                "WHERE run_id = :r AND prediction_date BETWEEN :s AND :e"
            ),
            conn,
            params={"r": BATCH_RUN_ID, "s": "2025-01-01", "e": "2026-05-31"},
            parse_dates=["trade_date"],
        )
    preds["trade_date"] = pd.to_datetime(preds["trade_date"]).dt.normalize()
    p(f"Univers ML : {len(preds)} prédictions, {preds['symbol'].nunique()} symboles, "
      f"{preds['trade_date'].nunique()} jours")

    # 3. Prix adj_closes pour les symboles de l'univers
    syms = sorted(set(preds["symbol"]) | set(trades["symbol"]))
    with ENGINE.connect() as conn:
        bars = pd.read_sql(
            text(
                "SELECT symbol, `date` AS trade_date, "
                "COALESCE(adj_close, close) AS px "
                "FROM stock_bars_daily "
                "WHERE symbol IN :syms AND `date` BETWEEN :s AND :e"
            ).bindparams(bindparam("syms", expanding=True)),
            conn,
            params={"syms": syms, "s": "2025-01-01", "e": "2026-08-15"},
            parse_dates=["trade_date"],
        )
    close = bars.pivot_table(index="trade_date", columns="symbol", values="px", aggfunc="last")
    close = close.sort_index().ffill()
    p(f"Prix chargés : {len(close)} jours, {close.shape[1]} symboles")

    # 4. Univers par jour
    uni_by_day = {d: set(g["symbol"]) for d, g in preds.groupby("trade_date")}

    # 5. Boucle par trade -> position oracle
    summary: dict[int, dict] = {h: {"longs": [], "shorts": [], "ldec": [], "sdec": []}
                                for h in HORIZONS}
    detail_rows = []
    skipped = 0
    for r in trades.itertuples(index=False):
        d = r.signal_date
        uni = uni_by_day.get(d)
        if not uni or r.symbol not in uni:
            skipped += 1
            continue
        if d not in close.index:
            skipped += 1
            continue
        ref_idx = close.index.get_indexer([d], method="nearest")[0]
        ref = close.iloc[ref_idx]
        for h in HORIZONS:
            fwd_idx = ref_idx + h
            if fwd_idx >= len(close):
                skipped += 1
                continue
            ret = (close.iloc[fwd_idx] / ref - 1.0).replace([np.inf, -np.inf], np.nan)
            ret = ret[list(uni)].dropna()
            if len(ret) < 20:
                skipped += 1
                continue
            pct_rank = float((ret <= ret[r.symbol]).mean())
            decile = int(min(10, max(1, np.ceil(pct_rank * 10))))
            if r.side == "buy":
                summary[h]["longs"].append(1.0 if pct_rank >= 0.90 else 0.0)
                summary[h]["ldec"].append(decile)
            else:
                summary[h]["shorts"].append(1.0 if pct_rank <= 0.10 else 0.0)
                summary[h]["sdec"].append(decile)
            detail_rows.append({
                "symbol": r.symbol, "side": r.side, "signal_date": d.date().isoformat(),
                "horizon": h, "pct_rank": pct_rank, "decile": decile,
                "universe_size": int(len(ret)),
                "fwd_ret": float(ret[r.symbol]) if pd.notna(ret[r.symbol]) else None,
            })
    p(f"Trades non évaluables (hors univers/jour ou fenêtre manquante) : {skipped}")

    pd.DataFrame(detail_rows).to_csv(RUN_DIR / "oracle_per_trade.csv", index=False)

    # 6. Rapports
    for h in HORIZONS:
        s = summary[h]
        p(f"\n=== ORACLE — horizon H{h} (univers ML ~{np.mean([len(v) for v in uni_by_day.values()]):.0f} syms/jour) ===")
        for side, label, dec_key in (
            ("longs", "LONG  (oracle = top 10% futurs)", "ldec"),
            ("shorts", "SHORT (oracle = bottom 10% futurs)", "sdec"),
        ):
            vals = np.asarray(s[side])
            if not vals.size:
                p(f"  {label} : aucun trade évaluable")
                continue
            dec = np.asarray(s[dec_key])
            in_oracle = vals.mean() * 100.0
            hist = np.bincount(dec, minlength=11)[1:]
            p(f"  {label} : n={len(vals)} | DANS l'oracle : {in_oracle:.1f}% "
              f"(baseline aléatoire = 10.0%)")
            p(f"    déciles futurs (D1=pire … D10=meilleur) : "
              + " ".join(f"D{i+1}:{hist[i]}" for i in range(10)))
            p(f"    médiane décile : {np.median(dec):.0f} | "
              f"% dans top/bottom 20% : {(100.0 * ((dec>=9) if side=='longs' else (dec<=2))).mean():.1f}%")
        p(f"  décile médian global longs={np.median(s['ldec']):.0f} "
          f"(shorts={np.median(s['sdec']):.0f}) n={len(s['ldec'])}/{len(s['sdec'])}")

    p(f"\nDétail par trade : {RUN_DIR / 'oracle_per_trade.csv'}")


if __name__ == "__main__":
    main()
