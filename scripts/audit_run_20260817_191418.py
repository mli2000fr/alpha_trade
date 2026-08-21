"""Audit du backtest IHM 20260817_191418_068cb285 (P14 + marché + overlays).

Vérifie :
1. Le correctif pullback : toutes les entrées doivent être à l'open (pas de ±1%).
2. Les sorties (TP/trailing/SL) et leur cohérence.
3. Les rejets, NaN, force-close, coûts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RUN_DIR = Path(
    r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_191418_068cb285\artifacts"
)
AUDIT_LOG = RUN_DIR / "trade_audit_log.csv"

OUT = sys.stdout


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def main() -> None:
    df = pd.read_csv(AUDIT_LOG, low_memory=False)
    p(f"Événements totaux : {len(df)}")
    p(f"Types d'événements : {df['event_type'].value_counts().to_dict()}")

    # ── 1. Entrées : vérifier que entry_price ≈ open (pas de pullback ±1%) ──
    entries = df[df["event_type"] == "entry_opened"].copy()
    p(f"\n=== 1. ENTRÉES ({len(entries)}) — vérification du correctif pullback ===")
    p(f"  Longs: {(entries['side']=='buy').sum()} | Shorts: {(entries['side']=='sell').sum()}")

    # diff entre le prix de remplissage (open) et l'entry_price appliqué
    entries["fill_diff_bps"] = (
        (entries["entry_price"] - entries["signal_fill_price"])
        / entries["signal_fill_price"] * 1e4
    )
    p("  Écart entry_price vs open (signal_fill_price), en bps :")
    p(f"    min={entries['fill_diff_bps'].min():+.1f}  "
      f"médiane={entries['fill_diff_bps'].median():+.1f}  "
      f"max={entries['fill_diff_bps'].max():+.1f}  "
      f"moy={entries['fill_diff_bps'].mean():+.1f}")
    # Les ±100 bps exacts (signature de l'ancien pullback) ne doivent plus exister
    n_pullback = int(((entries["fill_diff_bps"].abs() - 100.0).abs() < 0.5).sum())
    p(f"  Entrées encore à ±100 bps exacts (ancien pullback) : {n_pullback}")
    # Entrées aberrantes (>50 bps d'écart avec l'open)
    outliers = entries[entries["fill_diff_bps"].abs() > 50.0]
    p(f"  Entrées avec écart > 50 bps vs open : {len(outliers)}")
    if len(outliers):
        cols = ["event_date", "symbol", "side", "signal_fill_price", "entry_price", "fill_diff_bps"]
        p(outliers[cols].head(20).to_string(index=False))

    # ── 2. Sorties ──
    exits = df[df["event_type"] == "exit_closed"].copy()
    p(f"\n=== 2. SORTIES ({len(exits)}) ===")
    p(f"  Raisons de sortie : {exits['exit_reason'].value_counts().to_dict()}")

    # TP : quel % réellement appliqué ? (détecte si TP 12% fixe vs ATR)
    tp = exits[exits["exit_reason"] == "take_profit"].copy()
    p(f"\n  TP (take_profit) : {len(tp)} trades")
    if len(tp):
        tp["ret"] = np_sign(tp["side"], tp["exit_price"], tp["entry_price"])
        p(f"    rendement TP : min={tp['ret'].min():+.1%} "
          f"médiane={tp['ret'].median():+.1%} max={tp['ret'].max():+.1%}")
        p(f"    exemples : " + "; ".join(
            f"{s}({r:+.1%})" for s, r in tp[["symbol", "ret"]].head(8).itertuples(index=False)
        ))

    # ── 3. Rejets / anomalies ──
    p(f"\n=== 3. ANOMALIES ===")
    rej = df[df["event_type"] == "entry_rejected"]
    p(f"  entry_rejected : {len(rej)}")
    if len(rej):
        p(f"    raisons : {rej['rejection_reason'].value_counts().to_dict()}")

    # NaN / inf dans les prix
    price_cols = ["entry_price", "exit_price", "replay_exit_price", "signal_fill_price",
                  "replay_take_profit_price", "replay_initial_stop_price"]
    nan_cells = {c: int(df[c].isna().sum()) for c in price_cols if c in df.columns}
    p(f"  NaN par colonne prix : {nan_cells}")
    inf_cells = {c: int((df[c].abs() == float("inf")).sum()) for c in price_cols if c in df.columns}
    p(f"  Inf par colonne prix : {inf_cells}")

    # force close
    p(f"  force_close_exits : {int((df['exit_reason']=='force_close').sum())}")

    # ── 4. Coûts (entrée) ──
    p(f"\n=== 4. COÛTS D'ENTRÉE ===")
    if len(entries):
        c = (entries["entry_price"] / entries["signal_fill_price"] - 1.0)
        buy = c[entries["side"] == "buy"] * 1e4
        sell = c[entries["side"] == "sell"] * 1e4
        p(f"  Coût long (bps, entry vs open) : médiane={buy.median():+.1f}")
        p(f"  Coût short (bps, entry vs open) : médiane={sell.median():+.1f}")


def np_sign(side, exit_px, entry_px):
    """Retour en % pour long/short."""
    return (exit_px / entry_px - 1.0) * side.map({"buy": 1.0, "sell": -1.0})


if __name__ == "__main__":
    main()
