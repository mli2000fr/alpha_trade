"""P2-1 (incrément 1) — Attribution trade-level d'un backtest (générique).

- PnL par secteur GICS × côté (long/short), efficience (pnl/notional), win rate
- Concentration d'exposition vs concentration de PnL (leviers de sizing)
- A/B sizing post-hoc : equal (baseline) vs rank-weighted (top du classement
  journalier surpondéré) — métriques PnL total, win rate, Sharpe/DD de la
  courbe de PnL cumulé (ordre d'exit)
- Dérivation des multiplicateurs sectoriels depuis l'efficience combinée
  (règle : ≥+150bps→1.25 ; +50..+150→1.10 ; ±50→1.00 ; −150..−50→0.75 ; ≤−150→0.50)
  et écriture du JSON consommé par ``--sector-multipliers-json``.

Usage :
    python -m modelFactory.analyze_p21_attribution --run-dir artifacts/backtesting/mon_run
    python -m modelFactory.analyze_p21_attribution --run-dir artifacts/backtesting/mon_run --out-json config/p21_sector_multipliers.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from modelFactory.cross_sectional import _load_sector_mapping

DEFAULT_RUN_DIR = r"F:\projets\artifacts\backtesting\b25_p15_step3"
DEFAULT_OUT_JSON = r"F:\projets\config\p21_sector_multipliers.json"
OUT_DIR = r"F:\projets\artifacts\metrics"


def factor_for(eff_bps: float) -> float:
    """Facteur sectoriel depuis l'efficience en bps (règle P2-1 inc.3)."""
    if eff_bps >= 150:
        return 1.25
    if eff_bps >= 50:
        return 1.10
    if eff_bps >= -50:
        return 1.00
    if eff_bps >= -150:
        return 0.75
    return 0.50


def _variant_stats(trades: pd.DataFrame, label: str, w: pd.Series) -> dict:
    """Métriques d'une variante de sizing (pnl_i × w_i / mean(w))."""
    scale = w / w.mean() if w.mean() > 0 else np.ones(len(w))
    pnl = trades["pnl"] * scale
    ordered = trades.assign(pnl_v=pnl.values).sort_values("exit_date")["pnl_v"].cumsum()
    dd = (ordered - ordered.cummax()).min()
    daily = trades.assign(pnl_v=pnl.values).groupby("exit_date")["pnl_v"].sum()
    r = daily / 100_000.0
    sharpe = float(r.mean() / r.std(ddof=0) * np.sqrt(252)) if r.std(ddof=0) > 0 else np.nan
    return {
        "variante": label,
        "pnl_total": round(float(pnl.sum()), 0),
        "win_rate_pct": round(float(((pnl > 0).sum() / len(pnl)) * 100), 1),
        "pnl_moyen_trade": round(float(pnl.mean()), 0),
        "sharpe_pnl_journalier": round(sharpe, 2),
        "max_dd_approx_pct": round(float(dd / 100_000 * 100), 1),
    }


def main(run_dir: str, out_json: str | None, min_trades: int) -> None:
    run_name = os.path.basename(os.path.normpath(run_dir))
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True, pool_pre_ping=True)
    trades = pd.read_csv(os.path.join(run_dir, "trades.csv"))
    trades["pnl"] = pd.to_numeric(trades["pnl"], errors="coerce")
    trades["notional"] = trades["quantity"].abs() * pd.to_numeric(trades["entry_price"], errors="coerce")
    trades["side"] = trades["side"].astype(str).str.lower()  # buy=long / sell=short
    trades["exit_date"] = pd.to_datetime(trades["exit_date"], utc=False)

    # ── Secteurs depuis stock_metadata (le champ trades.csv est "Unknown") ──
    sector_map = _load_sector_mapping(engine)
    trades["gics"] = trades["symbol"].astype(str).str.upper().map(sector_map)
    trades["gics"] = trades["gics"].fillna("Unknown")
    print(f"run : {run_dir}")
    print(f"trades : {len(trades)} | secteurs mappés : {(trades['gics'] != 'Unknown').mean():.0%}")

    print("\n" + "=" * 110)
    print(f"P2-1 INC.1 — ATTRIBUTION PAR SECTEUR [{run_name}] (long = buy, short = sell)")
    print("=" * 110)
    rows = []
    for (sector, side), sub in trades.groupby(["gics", "side"], observed=True):
        rows.append(
            {
                "secteur": sector,
                "côté": "LONG" if side == "buy" else "SHORT",
                "trades": len(sub),
                "pnl": round(float(sub["pnl"].sum()), 0),
                "pnl_moyen": round(float(sub["pnl"].mean()), 0),
                "notional_total": round(float(sub["notional"].sum()), 0),
                "efficience_bps": round(float(sub["pnl"].sum() / sub["notional"].sum() * 10_000), 1),
                "win_rate_pct": round(float((sub["pnl"] > 0).mean() * 100), 1),
            }
        )
    attr = pd.DataFrame(rows).sort_values("pnl", ascending=False)
    print(attr.to_string(index=False))

    print("\nCONCENTRATION :")
    conc = (
        trades.groupby("gics", observed=True)
        .agg(notional=("notional", "sum"), pnl=("pnl", "sum"), trades=("pnl", "count"))
        .sort_values("notional", ascending=False)
    )
    conc["notional_pct"] = (conc["notional"] / conc["notional"].sum() * 100).round(1)
    conc["pnl_pct"] = (conc["pnl"] / conc["pnl"].sum() * 100).round(1)
    conc["efficience_bps"] = (conc["pnl"] / conc["notional"] * 10_000).round(1)
    print(conc.to_string())

    # ── Dérivation des multiplicateurs sectoriels (règle P2-1 inc.3) ──
    multipliers: dict[str, float] = {}
    for sector, row in conc.iterrows():
        if sector in {"Unknown", ""} or pd.isna(sector):
            continue
        n_trades = int(row["trades"])
        eff = float(row["efficience_bps"])
        multipliers[str(sector)] = factor_for(eff) if n_trades >= min_trades else 1.0
    multipliers = dict(sorted(multipliers.items(), key=lambda kv: (-kv[1], kv[0])))
    print("\nMULTIPLICATEURS SECTORIELS DÉRIVÉS :")
    for sector, factor in multipliers.items():
        eff = float(conc.loc[sector, "efficience_bps"])
        n_trades = int(conc.loc[sector, "trades"])
        print(f"  {sector:<40} eff={eff:>8.1f} bps  trades={n_trades:>4}  -> x{factor}")
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(multipliers, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\nJSON écrit : {out_json}")

    # ── A/B sizing post-hoc ──
    print("\n" + "=" * 110)
    print("A/B SIZING POST-HOC (trade-level, capital non réalloué)")
    print("=" * 110)
    valid = trades[trades["rank"].notna()].copy()
    print(f"trades avec rank : {len(valid)}")
    variants = [
        _variant_stats(valid, "equal (baseline réel)", pd.Series(np.ones(len(valid)), index=valid.index)),
        _variant_stats(valid, "rank-weighted (top=4)", 5.0 - valid["rank"]),
        _variant_stats(valid, "rank-squared", (5.0 - valid["rank"]) ** 2),
        _variant_stats(valid, "top1-only", (valid["rank"] == 1).astype(float)),
    ]
    print(pd.DataFrame(variants).to_string(index=False))

    os.makedirs(OUT_DIR, exist_ok=True)
    attr_path = os.path.join(OUT_DIR, f"p21_attribution_sector_{run_name}.csv")
    tagged_path = os.path.join(OUT_DIR, f"p21_trades_tagged_{run_name}.csv")
    attr.to_csv(attr_path, index=False)
    trades.to_csv(tagged_path, index=False)
    print(f"\nSauvegardé : {attr_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Attribution sectorielle P2-1 + génération des multiplicateurs.")
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR, help="Dossier de backtest contenant trades.csv")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON, help="Fichier JSON de sortie des multiplicateurs ('' = pas d'écriture)")
    parser.add_argument("--min-trades", type=int, default=0, help="Nb min de trades par secteur pour un facteur ≠ 1.0 (0 = pas de filtre, comme la calibration B25)")
    args = parser.parse_args()
    main(args.run_dir, args.out_json or None, args.min_trades)
