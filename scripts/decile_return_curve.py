"""Courbe de rendement par décile (H10/H20) sur l'univers ML du run 20260817_205031_2a2836d1.

Répond à : « le ranking ML est-il économiquement utile ? »
- Pour chaque jour, rendements futurs RÉELS de tous les symboles de l'univers ML (~399).
- Classement en déciles D1 (pire futur) … D10 (meilleur futur).
- Table : rendement moyen de chaque décile (univers entier) = "opportunité disponible".
- Puis : rendement moyen des trades ML (longs/shorts) par décile.
- D10 - D1 = spread du ranking.
- Capture ratio = (ML - random) / (Oracle - random).
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
    # 1. Univers ML par jour
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

    # 2. Prix
    syms = sorted(set(preds["symbol"]))
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

    # 3. Déciles univers : collecte (decile, fwd_ret) sur toutes les paires symbole-jour
    uni_by_day = {d: sorted(set(g["symbol"])) for d, g in preds.groupby("trade_date")}
    # trades ML (longs/shorts) par jour
    trades = pd.read_csv(RUN_DIR / "trades.csv", low_memory=False)
    trades["signal_date"] = pd.to_datetime(trades["signal_date"], errors="coerce").dt.normalize()
    trades = trades[trades["side"].isin(["buy", "sell"])]

    for h in HORIZONS:
        uni_dec = {k: [] for k in range(1, 11)}
        ml_long = {k: [] for k in range(1, 11)}
        ml_short = {k: [] for k in range(1, 11)}
        all_returns: list[float] = []
        for d, symlist in uni_by_day.items():
            if d not in close.index:
                continue
            ref_idx = close.index.get_indexer([d], method="nearest")[0]
            fwd_idx = ref_idx + h
            if fwd_idx >= len(close):
                continue
            ref = close.iloc[ref_idx]
            fwd = close.iloc[fwd_idx]
            ret = (fwd / ref - 1.0).replace([np.inf, -np.inf], np.nan)
            ret = ret[symlist].dropna()
            if len(ret) < 20:
                continue
            ret_sorted = ret.sort_values()
            n = len(ret_sorted)
            # déciles : D1 = pires rendements, D10 = meilleurs
            dec_series = pd.Series(
                np.clip(np.ceil((ret_sorted.rank(method="first") / n) * 10), 1, 10).astype(int),
                index=ret_sorted.index,
            )
            for sym, dec in dec_series.items():
                uni_dec[int(dec)].append(float(ret_sorted[sym]))
                all_returns.append(float(ret_sorted[sym]))
            # trades ML du jour
            day_trades = trades[trades["signal_date"] == d]
            for r in day_trades.itertuples(index=False):
                if r.symbol not in dec_series.index:
                    continue
                dec = int(dec_series[r.symbol])
                rv = float(ret_sorted[r.symbol])
                if r.side == "buy":
                    ml_long[dec].append(rv)
                else:
                    ml_short[dec].append(rv)

        p(f"\n=== COURBE DE RENDEMENT PAR DÉCILE — H{h} ===")
        p(f"{'Décile':<8}{'N univers':>10}{'Ret univers':>12}{'N long ML':>10}{'Ret long ML':>12}{'N short ML':>11}{'Ret short ML':>13}")
        for k in range(1, 11):
            u = np.asarray(uni_dec[k])
            l = np.asarray(ml_long[k])
            s = np.asarray(ml_short[k])
            def f(a):
                return f"{a.mean()*100:+.2f}%" if a.size else "  —  "
            p(f"D{k:<7}{len(u):>10}{f(u):>12}{len(l):>10}{f(l):>12}{len(s):>11}{f(s):>13}")
        u_all = np.mean(all_returns)
        p(f"\n  Moyenne univers (random long/short) = {u_all*100:+.2f}%  (n={len(all_returns)})")
        d10 = np.mean(uni_dec[10]); d1 = np.mean(uni_dec[1])
        p(f"  Spread D10 - D1 = {(d10-d1)*100:+.2f} pts | D10={d10*100:+.2f}% D1={d1*100:+.2f}%")
        # trades ML combinés
        all_ml = (np.concatenate([ml_long[k] for k in range(1, 11)]) if any(ml_long[k] for k in range(1,11)) else np.array([]))
        all_ms = (np.concatenate([ml_short[k] for k in range(1, 11)]) if any(ml_short[k] for k in range(1,11)) else np.array([]))
        ml_net = 0.0
        if all_ml.size: ml_net += all_ml.mean()
        if all_ms.size: ml_net += -all_ms.mean()  # short gagne si retour négatif
        n_ml = all_ml.size + all_ms.size
        p(f"  Trades ML (n={n_ml}) : long +{all_ml.mean()*100:+.2f}% / short −{all_ms.mean()*100:+.2f}% "
          f"→ book net {ml_net*100:+.2f}% (par entrée)")
        # Oracle plafond (même composition long/short que le book ML)
        w_long = all_ml.size / n_ml if n_ml else 0.0
        w_short = 1.0 - w_long
        oracle_net = w_long * d10 + w_short * (-d1)
        random_net = w_long * u_all + w_short * (-u_all)
        cap = (ml_net - random_net) / (oracle_net - random_net) if (oracle_net - random_net) != 0 else float("nan")
        p(f"  Oracle plafond (même mix long/short, wL={w_long:.0%}) = {oracle_net*100:+.2f}%")
        p(f"  Random (même mix) = {random_net*100:+.2f}%")
        p(f"  CAPTURE RATIO du ML = {cap*100:.0f}%  (ML capte {cap*100:.0f}% de l'alpha oracle-random)")


if __name__ == "__main__":
    main()
