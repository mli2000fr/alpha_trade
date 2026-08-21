"""Phase D4 per-sector — determinants de la dispersion (plan GPT post-D3, 2026-08-15).

Hypothese : la dispersion future intra-sectorielle (D0 : plafond enorme) est-elle
predictible par des variables de volatilite/dispersion/volume observables a t,
INDEPENDAMMENT de la direction ?

Deux volets :
1. Oracle direction vs magnitude (experience prioritaire GPT) : avec |rel_h20|
   comme score (O_mag), quelle part des extremes directionnels (top/bottom
   quintile de rel) est capturee par le quintile top-|rel| ? (p_extreme).
   Base hasard = 40 %. Si p_extreme ~ 100 %, l'architecture 2 etages
   amplitude -> direction est viable.
2. ~16 signaux de dispersion/vol/volume testes UN PAR UN (H20 uniquement) :
   - IC relatif (direction) + spread net 102 bps (harness)
   - IC magnitude : Spearman(score, |rel_h20|) par date
   - mag spread : |rel| top quintile - bottom quintile (par le score)
   - p_extreme : % du top quintile du score dans les quintiles directionnels
     extremes (base 40 %)

Standalone, lecture seule modelFactory. Usage : python scripts/per_sector_d4_dispersion.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modelFactory.cross_sectional import load_sector_groups  # noqa: E402
from modelFactory.data_loader import load_universe_bars  # noqa: E402
from scripts.per_sector_baselines import (  # noqa: E402
    HORIZONS,
    ROUND_TRIP_BPS,
    SPREAD_COST,
    _adjusted_close,
    _fmt_table,
    _read_universe,
    evaluate_period,
)

LOGGER = logging.getLogger("per_sector_d4")
H = 20


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D4 per-sector : determinants de la dispersion")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2024-07-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--buffer-days", type=int, default=360)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _rel_sector(panel: pd.DataFrame, col: str, min_sec: int) -> pd.Series:
    """col - mediane sectorielle (date, secteur), NaN si < min_sec titres."""
    counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
    med = panel.groupby(["date", "sector"])[col].transform("median")
    return (panel[col] - med).where(counts >= min_sec)


def _beta_idio(grp: pd.DataFrame) -> pd.DataFrame:
    r = grp["ret_1"]
    sr = grp["sector_ret"]
    cov = r.rolling(60).cov(sr)
    var = sr.rolling(60).var()
    beta = (cov / var.clip(lower=1e-12)).fillna(0.0)
    resid = r - beta * sr
    idio60 = resid.rolling(60).std() * np.sqrt(252)
    idio20 = resid.rolling(20).std() * np.sqrt(252)
    r2 = 1.0 - resid.rolling(60).var() / r.rolling(60).var().clip(lower=1e-12)
    return pd.DataFrame({"beta60": beta, "idio60": idio60,
                         "idio20": idio20, "r2_60": r2})


def _build_panel(engine, args: argparse.Namespace) -> pd.DataFrame:
    symbols = _read_universe(args.universe)
    start = pd.Timestamp(args.start).date() - timedelta(days=args.buffer_days)
    end = pd.Timestamp(args.end).date()
    bars = load_universe_bars(engine, symbols, start_date=start, end_date=end)
    sector_map: dict[str, str] = {}
    for gics, syms in load_sector_groups(engine).items():
        for s in syms:
            sector_map[s] = gics
    bars = bars[bars["symbol"].map(sector_map).notna()]
    bars = bars.sort_values(["symbol", "date"]).reset_index(drop=True)

    panel = bars[["symbol", "date", "open", "high", "low", "volume"]].copy()
    close = _adjusted_close(bars)
    panel["close"] = close.values
    panel["sector"] = panel["symbol"].map(sector_map)

    g = panel.groupby("symbol", sort=False)
    panel["ret_1"] = g["close"].transform(lambda s: s.pct_change(fill_method=None))
    panel["sector_ret"] = panel.groupby(["date", "sector"])["ret_1"].transform("mean")

    for w in (20, 60, 120):
        panel[f"ret_{w}"] = g["close"].transform(lambda s: s / s.shift(w) - 1.0)
    for w in (20, 60, 120):
        panel[f"vol_{w}"] = g["ret_1"].transform(
            lambda s: s.rolling(w).std() * np.sqrt(252))

    # ATR 14 normalise par close
    prev_c = g["close"].transform(lambda s: s.shift(1))
    tr = np.maximum.reduce([
        (panel["high"] - panel["low"]).abs(),
        (panel["high"] - prev_c).abs(),
        (panel["low"] - prev_c).abs(),
    ])
    panel["atr14"] = panel.assign(_tr=tr).groupby("symbol", sort=False)["_tr"].transform(
        lambda s: s.rolling(14).mean())
    panel["atr14_n"] = panel["atr14"] / panel["close"]

    # beta / idio-vol / R2 (regression roulante titre ~ secteur)
    reg = panel.groupby("symbol", group_keys=False).apply(_beta_idio, include_groups=False)
    panel = panel.join(reg)
    panel["idio_share"] = panel["idio20"] / panel["vol_20"].clip(lower=1e-9)
    panel["beta_dist"] = (panel["beta60"] - 1.0).abs()

    # volume / amplitude / gap / semi-vol
    panel["vr20"] = panel["volume"] / g["volume"].transform(
        lambda s: s.rolling(20).mean()).clip(lower=1.0)
    panel["range20"] = panel.assign(
        _rg=(panel["high"] - panel["low"]) / panel["close"]
    ).groupby("symbol", sort=False)["_rg"].transform(lambda s: s.rolling(20).mean())
    gap = panel["open"] / prev_c - 1.0
    panel["gapfreq20"] = gap.abs().gt(0.02).groupby(panel["symbol"]).transform(
        lambda s: s.rolling(20).mean())
    r = panel["ret_1"]
    up = r.where(r > 0, 0.0)
    dn = r.where(r < 0, 0.0)
    panel["up_vol20"] = up.groupby(panel["symbol"]).transform(
        lambda s: (s ** 2).rolling(20).mean() ** 0.5) * np.sqrt(252)
    panel["dn_vol20"] = dn.groupby(panel["symbol"]).transform(
        lambda s: (s ** 2).rolling(20).mean() ** 0.5) * np.sqrt(252)
    panel["ud_ratio"] = panel["up_vol20"] / panel["dn_vol20"].clip(lower=1e-9)

    # dispersion historique : std du rendement relatif au secteur
    relret = panel["ret_1"] - panel["sector_ret"]
    panel["disp20"] = relret.groupby(panel["symbol"]).transform(
        lambda s: s.rolling(20).std() * np.sqrt(252))

    # target H20 (relative return) + winsorisee
    panel["fut_h20"] = g["close"].transform(lambda s: s.shift(-H) / s - 1.0)
    med = panel.groupby(["date", "sector"])["fut_h20"].transform("median")
    counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
    panel["rel_h20"] = (panel["fut_h20"] - med).where(counts >= args.min_sector_size)
    lo = panel.groupby("date")["rel_h20"].transform(lambda x: x.quantile(0.01))
    hi = panel.groupby("date")["rel_h20"].transform(lambda x: x.quantile(0.99))
    panel["rel_h20_w"] = panel["rel_h20"].clip(lower=lo, upper=hi)
    panel["abs_rel_h20"] = panel["rel_h20_w"].abs()

    # scores
    ms = args.min_sector_size
    panel["S_vol20_rel"] = _rel_sector(panel, "vol_20", ms)
    panel["S_vol60_rel"] = _rel_sector(panel, "vol_60", ms)
    panel["S_vol120_rel"] = _rel_sector(panel, "vol_120", ms)
    panel["S_atr_rel"] = _rel_sector(panel, "atr14_n", ms)
    panel["S_beta60"] = panel["beta60"]
    panel["S_beta_dist"] = panel["beta_dist"]
    panel["S_idio20"] = panel["idio20"]
    panel["S_idio60"] = panel["idio60"]
    panel["S_r2_60"] = panel["r2_60"]
    panel["S_idio_share"] = panel["idio_share"]
    panel["S_vr20_abs"] = panel["vr20"]
    panel["S_vr20_rel"] = _rel_sector(panel, "vr20", ms)
    panel["S_range20_rel"] = _rel_sector(panel, "range20", ms)
    panel["S_gapfreq20"] = panel["gapfreq20"]
    panel["S_ud_ratio"] = panel["ud_ratio"]
    panel["S_disp_rel"] = _rel_sector(panel, "disp20", ms)

    panel["B0_random"] = np.random.default_rng(args.seed).random(len(panel))
    med20 = panel.groupby(["date", "sector"])["ret_20"].transform("median")
    panel["B4_relmom20"] = (panel["ret_20"] - med20).where(counts >= ms)
    panel["O_mag"] = panel["abs_rel_h20"]  # oracle amplitude (anticausal, diagnostic)
    return panel


SIGNAL_COLS = [
    "S_vol20_rel", "S_vol60_rel", "S_vol120_rel", "S_atr_rel", "S_beta60",
    "S_beta_dist", "S_idio20", "S_idio60", "S_r2_60", "S_idio_share",
    "S_vr20_abs", "S_vr20_rel", "S_range20_rel", "S_gapfreq20", "S_ud_ratio",
    "S_disp_rel",
]


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank()))


def _mag_eval(zone: pd.DataFrame, score_cols: list[str], min_date_size: int) -> pd.DataFrame:
    sub = zone.dropna(subset=["rel_h20_w", "symbol"]).copy()
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_date_size]
    qdir = sub.groupby("date")["rel_h20_w"].transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    sub["_ext"] = qdir.isin([0.0, 4.0]).astype(float)
    rows = []
    for sc in score_cols:
        s = sub.dropna(subset=[sc])
        if s.empty:
            rows.append({"score": sc, "mag_ic": np.nan, "mag_ic_pos": np.nan,
                         "mag_spread_bps": np.nan, "p_extreme": np.nan})
            continue
        qs = s.groupby("date")[sc].transform(
            lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
        s = s.assign(_top=(qs == 4.0).astype(float), _bot=(qs == 0.0).astype(float))
        ic = s.groupby("date").apply(
            lambda grp: _spearman(grp[sc], grp["abs_rel_h20"]), include_groups=False)
        spread = s.groupby("date").apply(
            lambda grp: float(grp.loc[grp["_top"] == 1.0, "abs_rel_h20"].mean()
                              - grp.loc[grp["_bot"] == 1.0, "abs_rel_h20"].mean()),
            include_groups=False)
        p_ext = s.groupby("date").apply(
            lambda grp: float(grp.loc[grp["_top"] == 1.0, "_ext"].mean()),
            include_groups=False)
        ic = ic.dropna()
        spread = spread.dropna()
        p_ext = p_ext.dropna()
        rows.append({
            "score": sc,
            "mag_ic": round(float(ic.mean()), 3) if len(ic) else np.nan,
            "mag_ic_pos": round(float((ic > 0).mean() * 100), 1) if len(ic) else np.nan,
            "mag_spread_bps": round(float(spread.mean() * 10_000), 0) if len(spread) else np.nan,
            "p_extreme": round(float(p_ext.mean() * 100), 1) if len(p_ext) else np.nan,
        })
    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    LOGGER.info("construction du panel (bars + features) ...")
    panel = _build_panel(engine, args)
    LOGGER.info("panel pret: %d lignes, %d secteurs", len(panel), panel["sector"].nunique())

    # horizons absents -> NaN pour le harness (D4 = H20 uniquement)
    for h in HORIZONS:
        for col in (f"rel_h{h}", f"rel_h{h}_w", f"fut_h{h}"):
            if col not in panel.columns:
                panel[col] = np.nan

    wf_start = pd.Timestamp(args.start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)
    score_cols = ["B0_random", "B4_relmom20", "O_mag"] + SIGNAL_COLS

    out_lines = [
        "=" * 100,
        "PHASE D4 — DETERMINANTS DE LA DISPERSION : vol / idio-vol / beta / volume (H20)",
        f"univers: {args.universe} | zones: WF {args.start} -> {args.holdout_start} (exclu) | "
        f"HOLDOUT {args.holdout_start} -> {args.end}",
        f"cout: aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> spread net = gross - {SPREAD_COST*10_000:.0f} bps",
        "O_mag = |rel_h20| (oracle amplitude, anticausal, diagnostic) | p_extreme = % du top quintile "
        "du score dans les quintiles directionnels extremes (base hasard = 40 %)",
        "",
    ]

    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        zone = panel[(panel["date"] >= zs) & (panel["date"] <= ze)]
        LOGGER.info("evaluation %s (direction) ...", zone_name)
        rows = evaluate_period(zone, zs, ze, score_cols, args.min_date_size)
        rows20 = [r for r in rows if r["horizon"] == 20]
        out_lines.append("=" * 100)
        out_lines.append(f"ZONE : {zone_name}  [H20]  — direction (IC relatif + spread net)")
        out_lines.append(_fmt_table(pd.DataFrame(rows20).drop(columns=["horizon"])))
        LOGGER.info("evaluation %s (magnitude) ...", zone_name)
        mag = _mag_eval(zone, score_cols, args.min_date_size)
        out_lines.append("")
        out_lines.append(f"ZONE : {zone_name}  [H20]  — magnitude (IC vs |rel| + spread |rel| + p_extreme)")
        out_lines.append(_fmt_table(mag))
        out_lines.append("")

    out_lines.append("Lecture : une variable est interessante si (a) direction : ic_mean > +0.02, "
                     "ic_pos_pct > 60 %, spread_net > 0 ; et/ou (b) magnitude : mag_ic > 0.03, "
                     "p_extreme > 50 % (vs 40 % hasard). Stable WF -> holdout, sans dependre d'un secteur.")
    out_lines.append("Si une variable predit la magnitude mais pas la direction -> architecture 2 etages (D9 GPT).")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / f"per_sector_d4_dispersion_{args.start}_{args.end}.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
