"""Audit rapide du benchmark OOS 2026 H20 risk : correctif pullback + TP H20."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RUN_DIR = Path(r"F:\projets\artifacts\backtesting\oos2026_p14_h20risk")
OUT = sys.stdout


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def main() -> None:
    df = pd.read_csv(RUN_DIR / "trade_audit_log.csv", low_memory=False)
    entries = df[df["event_type"] == "entry_opened"].copy()
    entries["fill_diff_bps"] = (
        (entries["entry_price"] - entries["signal_fill_price"]) / entries["signal_fill_price"] * 1e4
    )
    n_pullback = int(((entries["fill_diff_bps"].abs() - 100.0).abs() < 0.5).sum())
    p(f"ENTRÉES : {len(entries)} | écart médian vs open : {entries['fill_diff_bps'].median():+.1f} bps "
      f"| entrées à ±100 bps (pullback) : {n_pullback}")

    exits = df[df["event_type"] == "exit_closed"].copy()
    sign = exits["side"].map({"buy": 1.0, "sell": -1.0})
    exits["ret"] = (exits["exit_price"] / exits["entry_price"] - 1.0) * sign
    tp = exits[exits["exit_reason"] == "take_profit"]
    ts = exits[exits["exit_reason"] == "trailing_stop"]
    p(f"SORTIES : {len(exits)} | {exits['exit_reason'].value_counts().to_dict()}")
    if len(tp):
        p(f"  take_profit : n={len(tp)} ret min={tp['ret'].min():+.1%} "
          f"médiane={tp['ret'].median():+.1%} max={tp['ret'].max():+.1%}")
    if len(ts):
        p(f"  trailing    : n={len(ts)} ret min={ts['ret'].min():+.1%} "
          f"médiane={ts['ret'].median():+.1%} max={ts['ret'].max():+.1%}")
    p(f"force_close : {int((df['exit_reason']=='force_close').sum())}")


if __name__ == "__main__":
    main()
