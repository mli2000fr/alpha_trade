"""Phase D6 per-sector — fondamentaux comme DETECTEURS DE MAGNITUDE.

Plan GPT post-D5 : question = "les fondamentaux permettent-ils de predire quels
titres vont fortement diverger de leur secteur ?" — AMPLITUDE ONLY d'abord.

Dimensions (une famille = une hypothese) :
  Quality    : roe, roa, net_margin, operating_margin, gross_margin (+ composite)
  Growth     : eps_growth_yoy, revenue_growth_yoy (+ composite)
  Valuation  : pe_ratio, forward_pe, pb_ratio, ps_ratio, ev_to_ebitda (+ composite)
  Balance    : debt_to_equity, current_ratio (+ composite)
Toutes en percentile au sein du secteur a chaque date (PIT : snapshots
forward-filles, valeurs negatives PE/EV -> NaN).

D6-A : mag_ic vs |rel_h20| + P(extreme|top30%) - P(extreme|bottom30%)
       (memes seuils pre-enregistres que D5 : > +0.10 et > +10 pp).
D6-B (decisif) : mag_ic partiel par tercile d'idio_vol60 -> cherche un
       SECOND axe de magnitude INDEPENDANT de l'idio-vol (seuil +0.05).

Standalone, lecture seule modelFactory. Usage : python scripts/per_sector_d6_fundamentals.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modelFactory.fundamental_features import (  # noqa: E402
    forward_fill_fundamentals,
    load_fundamentals_from_db,
)
from scripts.per_sector_d4_dispersion import _build_panel  # noqa: E402
from scripts.per_sector_d5_volume import _mag_a, _mag_b  # noqa: E402

LOGGER = logging.getLogger("per_sector_d6")

FAMILIES: dict[str, dict[str, str]] = {
    "Quality": {
        "F_roe": "ROE", "F_roa": "ROA", "F_net_margin": "net margin",
        "F_op_margin": "operating margin", "F_gross_margin": "gross margin",
        "F_quality_comp": "QUALITY composite",
    },
    "Growth": {
        "F_epsg": "EPS growth yoy", "F_revg": "revenue growth yoy",
        "F_growth_comp": "GROWTH composite",
    },
    "Valuation": {
        "F_pe": "PE", "F_fpe": "forward PE", "F_pb": "P/B", "F_ps": "P/S",
        "F_ev_ebitda": "EV/EBITDA", "F_val_comp": "VALUATION composite",
    },
    "Balance": {
        "F_debt_eq": "debt/equity", "F_cur_ratio": "current ratio",
        "F_balance_comp": "BALANCE composite",
    },
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D6 per-sector : fondamentaux -> magnitude")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2024-07-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--buffer-days", type=int, default=360)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _sector_pct(panel: pd.DataFrame, col: str, min_sec: int) -> pd.Series:
    counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
    pct = panel.groupby(["date", "sector"])[col].transform(lambda x: x.rank(pct=True))
    return pct.where(counts >= min_sec)


def _add_fund_features(panel: pd.DataFrame, engine, args: argparse.Namespace) -> dict[str, str]:
    from scripts.per_sector_baselines import _read_universe
    symbols = sorted(panel["symbol"].unique())
    fund = load_fundamentals_from_db(
        symbols, pd.Timestamp(args.start), pd.Timestamp(args.end), engine=engine)
    if fund.empty:
        LOGGER.warning("aucune donnee fondamentale chargee")
        return {}
    trading_days = pd.DatetimeIndex(sorted(panel["date"].unique()))
    fund_ff = forward_fill_fundamentals(fund, trading_days)
    fund_ff = fund_ff.rename(columns={"trade_date": "date"}) if "date" not in fund_ff.columns else fund_ff
    # valeurs negatives non economiques -> NaN
    for c in ("pe_ratio", "forward_pe", "pb_ratio", "ps_ratio", "ev_to_ebitda"):
        if c in fund_ff.columns:
            fund_ff[c] = fund_ff[c].where(fund_ff[c] > 0)
    merge_cols = [c for c in ("roe", "roa", "net_margin", "operating_margin",
                              "gross_margin", "eps_growth_yoy", "revenue_growth_yoy",
                              "pe_ratio", "forward_pe", "pb_ratio", "ps_ratio",
                              "ev_to_ebitda", "debt_to_equity", "current_ratio")
                  if c in fund_ff.columns]
    merged = panel.merge(fund_ff[["symbol", "date"] + merge_cols],
                         on=["symbol", "date"], how="left")
    # reecrire dans le panel d'origine (pas de rebinding -> colonnes perdues)
    for c in merge_cols:
        panel[c] = merged[c].to_numpy()

    ms = args.min_sector_size
    pct = {}
    for c in ("roe", "roa", "net_margin", "operating_margin", "gross_margin"):
        if c in panel.columns:
            pct[c] = _sector_pct(panel, c, ms)
    if pct:
        panel["F_quality_comp"] = pd.concat(pct.values(), axis=1).mean(axis=1)
        for c, v in pct.items():
            panel[f"F_{c}"] = v
    for c, name in (("eps_growth_yoy", "F_epsg"), ("revenue_growth_yoy", "F_revg")):
        if c in panel.columns:
            panel[name] = _sector_pct(panel, c, ms)
    if "F_epsg" in panel.columns and "F_revg" in panel.columns:
        panel["F_growth_comp"] = panel[["F_epsg", "F_revg"]].mean(axis=1)
    vp = {}
    for c, name in (("pe_ratio", "F_pe"), ("forward_pe", "F_fpe"), ("pb_ratio", "F_pb"),
                    ("ps_ratio", "F_ps"), ("ev_to_ebitda", "F_ev_ebitda")):
        if c in panel.columns:
            panel[name] = _sector_pct(panel, c, ms)
            vp[name] = panel[name]
    if vp:
        panel["F_val_comp"] = pd.concat(vp.values(), axis=1).mean(axis=1)
    for c, name in (("debt_to_equity", "F_debt_eq"), ("current_ratio", "F_cur_ratio")):
        if c in panel.columns:
            panel[name] = _sector_pct(panel, c, ms)
    if "F_debt_eq" in panel.columns and "F_cur_ratio" in panel.columns:
        panel["F_balance_comp"] = panel[["F_debt_eq", "F_cur_ratio"]].mean(axis=1)

    score_cols: dict[str, str] = {}
    for fam, members in FAMILIES.items():
        for key, label in members.items():
            if key in panel.columns:
                score_cols[key] = f"[{fam}] {label}"
    return score_cols


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    LOGGER.info("construction du panel ...")
    panel = _build_panel(engine, args)
    LOGGER.info("chargement fondamentaux ...")
    fund_cols = _add_fund_features(panel, engine, args)
    score_cols = {"S_idio60": "[REF] idio_vol60"}
    score_cols.update(fund_cols)
    LOGGER.info("%d variables fondamentales creees", len(fund_cols))

    wf_start = pd.Timestamp(args.start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)

    out_lines = [
        "=" * 100,
        "PHASE D6 — FONDAMENTAUX comme DETECTEURS DE MAGNITUDE [H20, amplitude only]",
        "variables = percentiles au sein du secteur a chaque date (PIT snapshots forward-filles)",
        "D6-A : mag_ic vs |rel| + P_ext_diff (top30% vs bottom30%, extremes top/bottom 20%)",
        "D6-B (decisif) : mag_ic partiel par tercile d'idio_vol60 -> 2e axe independant ?",
        "",
    ]
    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        zone = panel[(panel["date"] >= zs) & (panel["date"] <= ze)]
        LOGGER.info("D6-A %s ...", zone_name)
        a = _mag_a(zone, score_cols, args.min_date_size)
        out_lines.append("=" * 100)
        out_lines.append(f"ZONE : {zone_name} — D6-A amplitude")
        out_lines.append(a.to_string(index=False))
        out_lines.append("")
        LOGGER.info("D6-B %s ...", zone_name)
        b = _mag_b(zone, score_cols, args.min_date_size)
        out_lines.append(f"ZONE : {zone_name} — D6-B mag_ic partiel par tercile d'idio_vol60")
        out_lines.append(b.to_string(index=False))
        out_lines.append("")

    out_lines.append("Criteres (memes que D5) : mag_ic > +0.10 et p_ext_diff > +10 pp, "
                     "stable WF->holdout, ET mag_ic partiel > +0.05 dans au moins un tercile "
                     "d'idio-vol => 2e brique magnitude INDEPENDANTE de l'idio-vol.")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / f"per_sector_d6_fundamentals_{args.start}_{args.end}.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
