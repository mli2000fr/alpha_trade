"""Vérifie si le TP ATR (min(3*ATR, 7%)) est réellement appliqué dans les runs pipeline.

Compare les rendements des sorties take_profit entre :
- le run IHM 20260817_191418_068cb285 (flags ATR présents)
- pb_ctl_2026 (benchmark « pile gelée », flags ATR présents)
- ihm2526_pb0 (TP12/TS7 fixe explicite, sans flags ATR)

Si le TP ATR était actif, les TP seraient <= ~7% (+ gap). Si ~12%+, c'est le TP fixe 12%.
Vérifie aussi les 6 entrées à fort écart vs les opens réels en base.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

RUNS = {
    "ihm_191418": Path(r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_191418_068cb285\artifacts"),
    "pb_ctl_2026": Path(r"F:\projets\artifacts\backtesting\pb_ctl_2026"),
    "ihm2526_pb0": Path(r"F:\projets\artifacts\backtesting\ihm2526_pb0"),
}

OUT = sys.stdout


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def main() -> None:
    # ── 1. TP% par run ──
    p("=== RENDEMENTS DES SORTIES take_profit PAR RUN ===")
    for name, d in RUNS.items():
        log = d / "trade_audit_log.csv"
        if not log.exists():
            p(f"  {name}: PAS DE trade_audit_log")
            continue
        df = pd.read_csv(log, low_memory=False)
        exits = df[(df["event_type"] == "exit_closed") & (df["exit_reason"] == "take_profit")]
        if len(exits) == 0:
            p(f"  {name}: 0 take_profit")
            continue
        sign = exits["side"].map({"buy": 1.0, "sell": -1.0})
        ret = (exits["exit_price"] / exits["entry_price"] - 1.0) * sign
        p(f"  {name}: n_tp={len(exits)}  ret_min={ret.min():+.1%} "
          f"ret_médiane={ret.median():+.1%} ret_max={ret.max():+.1%}")
        # trailing stops aussi (TS 7% vs ATR)
        ts = exits = df[(df["event_type"] == "exit_closed") & (df["exit_reason"] == "trailing_stop")]
        sign2 = ts["side"].map({"buy": 1.0, "sell": -1.0})
        ret2 = (ts["exit_price"] / ts["entry_price"] - 1.0) * sign2
        p(f"      trailing_stop: n={len(ts)} ret_min={ret2.min():+.1%} "
          f"ret_médiane={ret2.median():+.1%} ret_max={ret2.max():+.1%}")

    # ── 2. Les 6 entrées à fort écart vs opens réels (base) ──
    p("\n=== ENTRÉES À FORT ÉCART vs OPEN RÉEL (base stock_bars_daily) ===")
    d = RUNS["ihm_191418"]
    df = pd.read_csv(d / "trade_audit_log.csv", low_memory=False)
    entries = df[df["event_type"] == "entry_opened"].copy()
    entries = entries[entries["signal_fill_price"].notna()].copy()
    entries["diff_bps"] = (entries["entry_price"] / entries["signal_fill_price"] - 1.0) * 1e4
    outliers = entries[entries["diff_bps"].abs() > 50.0]
    if not len(outliers):
        p("  aucun outlier > 50 bps")
        return
    rows = []
    from sqlalchemy import text

    with ENGINE.connect() as conn:
        for r in outliers.itertuples(index=False):
            q = conn.execute(
                text(
                    "SELECT open, high, low, close FROM stock_bars_daily "
                    "WHERE symbol=:s AND date=:d"
                ),
                {"s": r.symbol, "d": str(r.event_date)},
            ).first()
            if q:
                rows.append({
                    "date": r.event_date, "symbol": r.symbol, "side": r.side,
                    "open_db": q[0], "fill_price": r.signal_fill_price,
                    "entry_price": r.entry_price, "diff_bps": round(r.diff_bps, 1),
                    "high_db": q[1], "low_db": q[2],
                })
    df2 = pd.DataFrame(rows)
    if len(df2):
        p(df2.to_string(index=False))
    else:
        p("  aucune correspondance en base pour les outliers")


if __name__ == "__main__":
    main()
