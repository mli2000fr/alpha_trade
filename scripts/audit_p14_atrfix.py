"""Audit du run corrigé ihm2526_p14_atrfix (P14 + marché + TP ATR actif)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RUN_DIR = Path(r"F:\projets\artifacts\backtesting\ihm2526_p14_atrfix")
AUDIT_LOG = RUN_DIR / "trade_audit_log.csv"
OUT = sys.stdout


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def main() -> None:
    df = pd.read_csv(AUDIT_LOG, low_memory=False)
    p(f"Événements : {len(df)} | {df['event_type'].value_counts().to_dict()}")

    # 1. Entrées — correctif pullback
    entries = df[df["event_type"] == "entry_opened"].copy()
    entries["fill_diff_bps"] = (
        (entries["entry_price"] - entries["signal_fill_price"]) / entries["signal_fill_price"] * 1e4
    )
    n_pullback = int(((entries["fill_diff_bps"].abs() - 100.0).abs() < 0.5).sum())
    p(f"\nENTRÉES : {len(entries)} (longs={(entries['side']=='buy').sum()}, "
      f"shorts={(entries['side']=='sell').sum()})")
    p(f"  écart médian vs open : {entries['fill_diff_bps'].median():+.1f} bps")
    p(f"  entrées encore à ±100 bps (pullback) : {n_pullback}")

    # 2. Sorties — répartition + TP
    exits = df[df["event_type"] == "exit_closed"].copy()
    p(f"\nSORTIES : {len(exits)} | raisons : {exits['exit_reason'].value_counts().to_dict()}")
    sign = exits["side"].map({"buy": 1.0, "sell": -1.0})
    exits["ret"] = (exits["exit_price"] / exits["entry_price"] - 1.0) * sign
    tp = exits[exits["exit_reason"] == "take_profit"]
    if len(tp):
        p(f"  take_profit : n={len(tp)}  ret min={tp['ret'].min():+.1%} "
          f"médiane={tp['ret'].median():+.1%} max={tp['ret'].max():+.1%}")
    ts = exits[exits["exit_reason"] == "trailing_stop"]
    if len(ts):
        p(f"  trailing_stop : n={len(ts)}  ret min={ts['ret'].min():+.1%} "
          f"médiane={ts['ret'].median():+.1%} max={ts['ret'].max():+.1%}")

    # 3. Rejets / NaN / force-close
    rej = df[df["event_type"] == "entry_rejected"]
    p(f"\nREJETS : {len(rej)} | {rej['rejection_reason'].value_counts().to_dict() if len(rej) else '—'}")
    p(f"  force_close : {int((df['exit_reason']=='force_close').sum())}")
    for c in ["entry_price", "exit_price", "replay_exit_price"]:
        p(f"  NaN {c} : {int(df[c].isna().sum())}")

    # 4. Coût d'entrée
    c = (entries["entry_price"] / entries["signal_fill_price"] - 1.0)
    p(f"\nCOÛT ENTRÉE médian : {c.abs().median()*1e4:.1f} bps "
      f"(longs {(c[entries['side']=='buy'].median()*1e4):+.1f}, "
      f"shorts {(c[entries['side']=='sell'].median()*1e4):+.1f})")

    # 5. Décomposition par année
    ec = pd.read_csv(RUN_DIR / "equity_curve.csv")
    ec["trade_date"] = pd.to_datetime(ec["trade_date"])
    e2025 = ec[ec["trade_date"] <= "2025-12-31"]
    y2025 = float(e2025.iloc[-1]["portfolio_value"]) / float(ec.iloc[0]["portfolio_value"]) - 1.0
    y2026 = float(ec.iloc[-1]["portfolio_value"]) / float(e2025.iloc[-1]["portfolio_value"]) - 1.0
    p(f"\nANNÉES : 2025 = {y2025:+.2%} | 2026 YTD = {y2026:+.2%} | "
      f"total = {float(ec.iloc[-1]['portfolio_value'])/float(ec.iloc[0]['portfolio_value'])-1.0:+.2%}")


if __name__ == "__main__":
    main()
