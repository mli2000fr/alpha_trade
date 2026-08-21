"""Preuve que le coût d'exécution vient du spread RÉEL du marché (stock_quote_snapshots),
et non d'un fallback preset/config.

Pour chaque entrée du run 20260817_191418_068cb285 :
  cost_bps = |entry_price/open - 1| * 1e4  = 5 (slippage base) + spread_reel/2
  => spread_implique = 2 * (cost_bps - 5)

On compare spread_implique au spread réel de stock_quote_snapshots (avec ffill),
et on compte combien d'entrées ont réellement utilisé le spread du marché.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
AUDIT_LOG = Path(
    r"F:\projets\artifacts\ihm_backtesting_runs\run\20260817_191418_068cb285\artifacts\trade_audit_log.csv"
)
BASE_SLIPPAGE_BPS = 5.0  # la pénalité d'exécution de base (avant spread/2)
FALLBACK_SPREAD_BPS = 5.0

OUT = sys.stdout


def p(msg: str = "") -> None:
    print(msg, file=OUT)


def main() -> None:
    df = pd.read_csv(AUDIT_LOG, low_memory=False)
    entries = df[df["event_type"] == "entry_opened"].copy()
    entries = entries[entries["signal_fill_price"].notna() & (entries["entry_price"].notna())]
    entries["open"] = entries["signal_fill_price"]

    # coût appliqué en bps (toujours > 0) : 5 + spread/2
    entries["cost_bps"] = (entries["entry_price"] / entries["open"] - 1.0).abs() * 1e4
    entries["spread_implied_bps"] = 2.0 * (entries["cost_bps"] - BASE_SLIPPAGE_BPS)
    entries = entries[entries["spread_implied_bps"] >= 0]

    p(f"Entrées analysées : {len(entries)}")
    p(f"Coût d'entrée médian (bps) : {entries['cost_bps'].median():.1f}")

    # ── Charger tous les spreads réels du marché sur la période ──
    spread_rows = []
    with ENGINE.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT symbol, quote_date, spread_bps FROM stock_quote_snapshots "
                "WHERE quote_date BETWEEN '2025-01-01' AND '2026-05-31' "
                "AND spread_bps IS NOT NULL AND spread_bps >= 0"
            )
        ).all()
    spread_df = pd.DataFrame(rows, columns=["symbol", "quote_date", "spread_bps"])
    spread_df["quote_date"] = pd.to_datetime(spread_df["quote_date"]).dt.normalize()
    p(f"Snapshots de spread bruts chargés : {len(spread_df)}")

    # ffill : pour chaque (symbole, date), dernier spread dispo <= date
    spread_df = spread_df.sort_values(["symbol", "quote_date"])
    ffill_map: dict[tuple[str, pd.Timestamp], float] = {}
    for sym, grp in spread_df.groupby("symbol"):
        dates = grp["quote_date"].values
        vals = grp["spread_bps"].values
        ffill_map.update({(sym, pd.Timestamp(d)): float(v) for d, v in zip(dates, vals)})

    def get_spread(sym: str, d: pd.Timestamp) -> tuple[float, bool]:
        """Retourne (spread, used_real) en reproduisant la logique ffill du loader."""
        key = (sym, d)
        while key not in ffill_map:
            d = d - pd.Timedelta(days=1)
            if d < pd.Timestamp("2025-01-01"):
                return FALLBACK_SPREAD_BPS, False
            key = (sym, d)
        return ffill_map[key], True

    entries["entry_date"] = pd.to_datetime(entries["event_date"]).dt.normalize()
    recs = []
    for r in entries.itertuples(index=False):
        spread_db, used_real = get_spread(r.symbol, r.entry_date)
        recs.append({
            "symbol": r.symbol, "date": r.entry_date.date(),
            "side": r.side, "cost_bps": round(r.cost_bps, 1),
            "spread_implied": round(r.spread_implied_bps, 1),
            "spread_db": round(spread_db, 1),
            "used_real": used_real,
        })
    out = pd.DataFrame(recs)

    # ── Résumé ──
    n_real = int(out["used_real"].sum())
    n_fallback = int((~out["used_real"]).sum())
    p(f"\nEntrées avec spread RÉEL du marché (stock_quote_snapshots) : {n_real} / {len(out)} ({n_real/len(out):.1%})")
    p(f"Entrées avec fallback (pas de snapshot dispo) : {n_fallback} ({n_fallback/len(out):.1%})")

    # corrélation entre spread implicite et spread réel DB
    corr = out["spread_implied"].corr(out["spread_db"])
    p(f"\nCorrélation spread_impliqué vs spread_DB : {corr:.3f}")
    p(f"Médiane spread_impliqué : {out['spread_implied'].median():.1f} bps")
    p(f"Médiane spread_DB (réel marché) : {out['spread_db'].median():.1f} bps")
    p(f"Écart médian |impliqué - DB| : {(out['spread_implied'] - out['spread_db']).abs().median():.1f} bps")

    # les entrées qui auraient pu être du fallback pur (spread ~0 => cost ~5)
    p(f"\nEntrées à coût ≈ 5 bps (spread≈0, suspect fallback) : {int((out['cost_bps'] < 7).sum())}")

    # détail des 6 outliers + quelques entrées normales
    p("\n=== DÉTAIL : 6 outliers (coût>50 bps) ===")
    p(out[out["cost_bps"] > 50].to_string(index=False))
    p("\n=== DÉTAIL : 12 entrées représentatives (coût médian ~7-10 bps) ===")
    p(out[out["cost_bps"].between(7, 11)].head(12).to_string(index=False))

    # exemple d'entrées à spread réel faible (liquide)
    p("\n=== Exemples entrées très liquides (spread réel < 8 bps) ===")
    liq = out[out["spread_db"] < 8].head(8)
    p(liq.to_string(index=False))


if __name__ == "__main__":
    main()
