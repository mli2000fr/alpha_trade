"""P1-5 (étape 3) — PnL du backtest B25 par régime de marché.

Attribue chaque trade au régime de son jour d'entrée (régime SPY
bull/range/vol/bear + drawdown SPY vs max 252j + dispersion cross-sectionnelle)
et agrège le PnL net, le win-rate, la contribution long/short et la courbe
d'equity journalière par régime.

A/B post-hoc (approximation 1er ordre, sans réallocation de capital) :
- Filtre "haute dispersion" : on exclut les trades entrés en high_disp
- Filtre "régime vol" : on exclut les trades entrés en régime vol
- Filtre "SPY drawdown profond" : on exclut les trades entrés quand SPY < -10%

Usage : python scripts/analyze_pnl_by_regime_b25.py
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, r"F:\projets")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

RUN_DIR = r"F:\projets\artifacts\backtesting\b25_p15_step3"
IC_CSV = r"F:\projets\artifacts\metrics\ic_by_regime_b25_daily.csv"
OUT_DIR = r"F:\projets\artifacts\metrics"


def _load_spy_drawdown(engine) -> pd.DataFrame:
    """Drawdown SPY vs max roulant 252 séances + close."""
    from sqlalchemy import text

    with engine.connect() as conn:
        spy = pd.read_sql(
            text(
                "SELECT `date` AS trade_date, COALESCE(adj_close, `close`) AS spy_close "
                "FROM stock_bars_daily WHERE symbol='SPY' AND data_source='eodhd_eod' "
                "AND `date` BETWEEN :s AND :e ORDER BY `date`"
            ),
            conn,
            params={"s": date(2017, 1, 1), "e": date(2024, 6, 28)},
        )
    spy["d"] = pd.to_datetime(spy["trade_date"], utc=False).dt.date
    spy["spy_peak252"] = spy["spy_close"].rolling(252, min_periods=20).max()
    spy["spy_dd"] = spy["spy_close"] / spy["spy_peak252"] - 1.0
    spy["spy_dd_bucket"] = pd.cut(
        spy["spy_dd"],
        bins=[-np.inf, -0.10, -0.02, np.inf],
        labels=["dd_deep", "dd_shallow", "dd_none"],
    )
    return spy[["d", "spy_close", "spy_dd", "spy_dd_bucket"]]


def main() -> None:
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True, pool_pre_ping=True)

    trades_path = os.path.join(RUN_DIR, "trades.csv")
    equity_path = os.path.join(RUN_DIR, "equity_curve.csv")
    if not os.path.exists(trades_path):
        raise SystemExit(f"trades.csv introuvable dans {RUN_DIR} — le backtest a-t-il terminé ?")

    trades = pd.read_csv(trades_path)
    print(f"trades.csv : {len(trades)} lignes")
    trades["entry_d"] = pd.to_datetime(trades["entry_date"], utc=False).dt.date
    trades["exit_d"] = pd.to_datetime(trades["exit_date"], utc=False).dt.date
    trades["pnl"] = pd.to_numeric(trades["pnl"], errors="coerce")

    # ── 1. Régimes + dispersion depuis l'analyse IC (mêmes définitions) ──
    ic = pd.read_csv(IC_CSV)
    ic["d"] = pd.to_datetime(ic["d"], utc=False).dt.date
    reg = ic[["d", "market_regime", "dispersion", "disp_regime"]].drop_duplicates("d")

    # ── 2. Drawdown SPY + régime pour TOUTES les séances de trading ──
    from backtesting.screener_diagnostics._impl import classify_market_regimes

    spy_dd = _load_spy_drawdown(engine)
    spy_bars = spy_dd[["d", "spy_close"]].rename(columns={"d": "trade_date", "spy_close": "close"})
    spy_bars["symbol"] = "SPY"
    all_dates = sorted(set(trades["entry_d"]) | set(trades["exit_d"]))
    regime_full = classify_market_regimes(spy_bars, benchmark_symbol="SPY", trade_dates=all_dates)
    regime_full["d"] = pd.to_datetime(regime_full["trade_date"], utc=False).dt.date
    dates_df = regime_full[["d", "market_regime"]].merge(
        spy_dd[["d", "spy_dd", "spy_dd_bucket"]], on="d", how="left"
    )

    reg_disp = reg[["d", "dispersion", "disp_regime"]].rename(columns={"d": "entry_d"})
    trades = trades.merge(dates_df, left_on="entry_d", right_on="d", how="left").drop(columns=["d"])
    trades = trades.merge(reg_disp, on="entry_d", how="left")

    # ── 3. Métriques par régime (niveau trade) ──
    print("\n" + "=" * 110)
    print("PNL PAR RÉGIME — B25 (5+5 bps) — attribution au jour d'entrée")
    print("=" * 110)

    def _trade_stats(sub: pd.DataFrame) -> dict:
        side = sub["side"].astype(str).str.lower()
        long_pnl = sub.loc[side == "buy", "pnl"].sum()
        short_pnl = sub.loc[side == "sell", "pnl"].sum()
        return {
            "trades": len(sub),
            "pnl_net": round(float(sub["pnl"].sum()), 0),
            "pnl_moyen": round(float(sub["pnl"].mean()), 0),
            "win_rate_pct": round(float((sub["pnl"] > 0).mean() * 100), 1),
            "pnl_long": round(float(long_pnl), 0),
            "pnl_short": round(float(short_pnl), 0),
            "n_long": int((side == "buy").sum()),
            "n_short": int((side == "sell").sum()),
        }

    rows = []
    for name, sub in [("GLOBAL", trades)]:
        rows.append({"axe": name, **_trade_stats(sub)})
    for name, sub in trades.groupby("market_regime", dropna=False):
        rows.append({"axe": f"regime_{name}", **_trade_stats(sub)})
    for name, sub in trades.groupby("disp_regime", dropna=False):
        rows.append({"axe": f"{name}", **_trade_stats(sub)})
    for name, sub in trades.groupby("spy_dd_bucket", dropna=False, observed=True):
        rows.append({"axe": f"spy_{name}", **_trade_stats(sub)})
    for name, sub in trades.groupby(["market_regime", "disp_regime"], dropna=False):
        rows.append({"axe": f"regime×disp {name[0]}/{name[1]}", **_trade_stats(sub)})

    print(pd.DataFrame(rows).to_string(index=False))

    # ── 4. Equity journalière par régime ──
    print("\nEQUITY QUOTIDIENNE PAR RÉGIME :")
    if os.path.exists(equity_path):
        eq = pd.read_csv(equity_path)
        eq.columns = ["trade_date", "portfolio_value"] if len(eq.columns) == 2 else eq.columns
        eq["d"] = pd.to_datetime(eq["trade_date"], utc=False).dt.date
        eq["ret"] = eq["portfolio_value"].pct_change(fill_method=None)
        eq_dates = sorted(set(eq["d"].tolist()))
        regime_eq = classify_market_regimes(spy_bars, benchmark_symbol="SPY", trade_dates=eq_dates)
        regime_eq["d"] = pd.to_datetime(regime_eq["trade_date"], utc=False).dt.date
        dates_eq = regime_eq[["d", "market_regime"]].merge(
            spy_dd[["d", "spy_dd", "spy_dd_bucket"]], on="d", how="left"
        )
        eq = eq.merge(dates_eq, on="d", how="left")

        eq_rows = []
        for name, sub in [("GLOBAL", eq)]:
            r = sub["ret"].dropna()
            dd = (sub["portfolio_value"] / sub["portfolio_value"].cummax() - 1).min()
            eq_rows.append(
                {
                    "axe": name,
                    "jours": len(sub),
                    "ret_jour_moy": round(float(r.mean() * 100), 3),
                    "vol_jour": round(float(r.std() * 100), 3),
                    "sharpe_ann": round(float(r.mean() / r.std() * np.sqrt(252)), 2) if r.std() > 0 else np.nan,
                    "max_dd_pct": round(float(dd * 100), 1),
                }
            )
        for name, sub in eq.groupby("market_regime", dropna=False):
            r = sub["ret"].dropna()
            dd = (sub["portfolio_value"] / sub["portfolio_value"].cummax() - 1).min()
            eq_rows.append(
                {
                    "axe": f"regime_{name}",
                    "jours": len(sub),
                    "ret_jour_moy": round(float(r.mean() * 100), 3) if len(r) else np.nan,
                    "vol_jour": round(float(r.std() * 100), 3) if len(r) else np.nan,
                    "sharpe_ann": round(float(r.mean() / r.std() * np.sqrt(252)), 2) if (len(r) and r.std() > 0) else np.nan,
                    "max_dd_pct": round(float(dd * 100), 1) if len(sub) else np.nan,
                }
            )
        for name, sub in eq.groupby("spy_dd_bucket", dropna=False, observed=True):
            r = sub["ret"].dropna()
            eq_rows.append(
                {
                    "axe": f"spy_{name}",
                    "jours": len(sub),
                    "ret_jour_moy": round(float(r.mean() * 100), 3) if len(r) else np.nan,
                    "vol_jour": round(float(r.std() * 100), 3) if len(r) else np.nan,
                    "sharpe_ann": round(float(r.mean() / r.std() * np.sqrt(252)), 2) if (len(r) and r.std() > 0) else np.nan,
                    "max_dd_pct": round(float(dd * 100), 1) if len(sub) else np.nan,
                }
            )
        print(pd.DataFrame(eq_rows).to_string(index=False))
    else:
        print("equity_curve.csv absent — métriques journalières ignorées.")

    # ── 5. A/B post-hoc (approximation trade-level, sans réallocation) ──
    print("\n" + "=" * 110)
    print("A/B POST-HOC — exclusion de trades (approximation 1er ordre, capital non réalloué)")
    print("=" * 110)
    base = trades["pnl"].sum()
    variants = {
        "baseline (tous trades)": trades,
        "sans high_disp": trades[trades["disp_regime"] != "high_disp"],
        "sans régime vol": trades[trades["market_regime"] != "vol"],
        "sans dd_deep (SPY<-10%)": trades[trades["spy_dd_bucket"] != "dd_deep"],
        "sans vol OU high_disp": trades[(trades["market_regime"] != "vol") & (trades["disp_regime"] != "high_disp")],
    }
    ab_rows = []
    for name, sub in variants.items():
        removed = len(trades) - len(sub)
        ab_rows.append(
            {
                "variante": name,
                "trades": len(sub),
                "trades_retirés": removed,
                "pnl_net": round(float(sub["pnl"].sum()), 0),
                "win_rate_pct": round(float((sub["pnl"] > 0).mean() * 100), 1),
                "pnl_moyen_trade": round(float(sub["pnl"].mean()), 0),
                "variation_vs_base_pct": round(float((sub["pnl"].sum() / base - 1) * 100), 1) if base else np.nan,
            }
        )
    print(pd.DataFrame(ab_rows).to_string(index=False))

    # ── 6. Sauvegarde ──
    os.makedirs(OUT_DIR, exist_ok=True)
    trades.to_csv(os.path.join(OUT_DIR, "pnl_by_regime_b25_trades_tagged.csv"), index=False)
    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "pnl_by_regime_b25_summary.csv"), index=False)
    pd.DataFrame(ab_rows).to_csv(os.path.join(OUT_DIR, "pnl_by_regime_b25_ab.csv"), index=False)
    print(f"\nSauvegardé dans {OUT_DIR}")


if __name__ == "__main__":
    main()
