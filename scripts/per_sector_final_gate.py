# -*- coding: utf-8 -*-
"""FINAL per-sector — gate idio_vol60 : train 2016-2024, WF 2019-2024 (seuils
60/70/80 + random control D'ABORD), verification 2025-2026, multi-horizon,
table par symbole. Aucun contact avec le Global Ranking de prod : un seul
CatBoost regression (D1) sur l'univers 400, target rel_h20.

Variants :
  A0_global : D1_pred seul
  A2_g60/70/80 : D1_pred si percentile intra-date idio_vol60 >= seuil (sinon flat)
  RG_g70 : gate aleatoire au meme taux de selection (seed fixe, controle)
  F2_soft : D1_pred * (0.5 + 0.5 * p_ext)  (sizing doux, signe inchange)
  B0_random / B4_relmom20 : references harness

Usage : python scripts/per_sector_final_gate.py
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

from scripts.per_sector_baselines import (  # noqa: E402
    HORIZONS,
    ROUND_TRIP_BPS,
    SPREAD_COST,
    _fmt_table,
    _read_universe,
    evaluate_period,
)
from scripts.per_sector_d1_global import (  # noqa: E402
    _build_cfg,
    _fit_predict_catboost,
    _fold_windows,
    _load_and_prepare,
)
from scripts.per_sector_d4_dispersion import _beta_idio  # noqa: E402

LOGGER = logging.getLogger("per_sector_final")
PRED_CACHE = Path("artifacts/per_sector_cache/final_d1_preds_2026.parquet")
OUT_DIR = Path("artifacts/per_sector_cache")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FINAL per-sector : gate idio_vol60, train 2016-2024, verif 2025-2026")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--train-start", default="2016-01-01")
    p.add_argument("--wf-start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2025-01-01")
    p.add_argument("--end", default="2026-08-14")
    p.add_argument("--folds", type=int, default=12)
    p.add_argument("--iterations", type=int, default=300)
    p.add_argument("--depth", type=int, default=6)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--skip-d1f", action="store_true", help="charger les predictions D1 du cache sans refit")
    p.add_argument("--no-sector-cat", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


def _run_d1_oof(df: pd.DataFrame, feat: list[str], args: argparse.Namespace) -> pd.DataFrame:
    """12 folds WF 2019-2024 + holdout (train < 2025) -> predictions D1, avec cache."""
    if PRED_CACHE.exists():
        LOGGER.info("D1_pred charges depuis le cache %s", PRED_CACHE)
        return pd.read_parquet(PRED_CACHE)
    preds: list[pd.DataFrame] = []
    hold_start = pd.Timestamp(args.holdout_start)
    for fi, (t0, t1) in enumerate(_fold_windows(args)):
        tr = df[df["date"] < t0].dropna(subset=["rel_h20"])
        te = df[(df["date"] >= t0) & (df["date"] < t1)].dropna(subset=["rel_h20"])
        if len(tr) < 10_000 or len(te) < 1_000:
            continue
        y = tr["rel_h20"]
        y = y.clip(lower=y.quantile(0.01), upper=y.quantile(0.99))
        LOGGER.info("FINAL fold %d: %s -> %s | train %d test %d", fi, t0.date(), t1.date(), len(tr), len(te))
        p = _fit_predict_catboost(tr[feat], y, te[feat], args)
        preds.append(te[["symbol", "date"]].assign(D1_pred=p))
    tr_all = df[df["date"] < hold_start].dropna(subset=["rel_h20"])
    hold = df[df["date"] >= hold_start]
    y = tr_all["rel_h20"]
    y = y.clip(lower=y.quantile(0.01), upper=y.quantile(0.99))
    LOGGER.info("FINAL holdout: train %d -> pred %d", len(tr_all), len(hold))
    p_hold = _fit_predict_catboost(tr_all[feat], y, hold[feat], args)
    preds.append(hold[["symbol", "date"]].assign(D1_pred=p_hold))
    out = pd.concat(preds, ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PRED_CACHE, index=False)
    return out


def _build_variants(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    d1p = df["D1_pred"]
    pe = df["p_ext"]
    df["A0_global"] = d1p
    df["A2_g60"] = d1p.where(pe >= 0.60)
    df["A2_g70"] = d1p.where(pe >= 0.70)
    df["A2_g80"] = d1p.where(pe >= 0.80)
    rng = np.random.default_rng(args.seed)
    df["_rnd"] = rng.random(len(df))
    rnd_pct = df.groupby("date")["_rnd"].rank(pct=True)
    df["RG_g70"] = d1p.where(rnd_pct >= 0.70)
    df["F2_soft"] = d1p * (0.5 + 0.5 * pe)
    return df


def _per_symbol_table(zone: pd.DataFrame, zone_name: str) -> pd.DataFrame:
    """Performance par symbole (H20) : jours, mean_rel_bps, win_rate, par variant."""
    sub = zone.dropna(subset=["rel_h20_w", "D1_pred"]).copy()
    rows = []
    for (sym, sec), grp in sub.groupby(["symbol", "sector"]):
        rec = {"zone": zone_name, "symbol": sym, "sector": sec,
               "n_jours": int(len(grp)),
               "mean_rel_bps_all": round(float(grp["rel_h20_w"].mean() * 10_000), 1),
               "win_rate_all": round(float((grp["rel_h20_w"] > 0).mean() * 100), 1)}
        for th in (60, 70, 80):
            sel = grp[grp["p_ext"] >= th / 100.0]
            if len(sel) >= 10:
                rec[f"n_sel_g{th}"] = int(len(sel))
                rec[f"mean_rel_bps_g{th}"] = round(float(sel["rel_h20_w"].mean() * 10_000), 1)
                rec[f"win_rate_g{th}"] = round(float((sel["rel_h20_w"] > 0).mean() * 100), 1)
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    cfg = _build_cfg(args)

    LOGGER.info("preparation des features (lecture seule modelFactory) ...")
    df, feat, _ = _load_and_prepare(engine, cfg, args)
    LOGGER.info("frame pret: %d lignes, %d features", len(df), len(feat))

    # targets multi-horizon H3/H5/H10/H15 (H20 = rel_h20 de _load_and_prepare, conserve)
    g = df.groupby("symbol", sort=False)["close"]
    for h in HORIZONS:
        if h == 20:
            continue
        df[f"fut_h{h}"] = g.transform(lambda s: s.shift(-h) / s - 1.0)
        counts = df.groupby(["date", "sector"])["symbol"].transform("nunique")
        med = df.groupby(["date", "sector"])[f"fut_h{h}"].transform("median")
        df[f"rel_h{h}"] = (df[f"fut_h{h}"] - med).where(counts >= args.min_sector_size)
        lo = df.groupby("date")[f"rel_h{h}"].transform(lambda x: x.quantile(0.01))
        hi = df.groupby("date")[f"rel_h{h}"].transform(lambda x: x.quantile(0.99))
        df[f"rel_h{h}_w"] = df[f"rel_h{h}"].clip(lower=lo, upper=hi)

    # brique amplitude : idio_vol60
    df["ret_1"] = df["daily_return"]
    df["sector_ret"] = df.groupby(["date", "sector"])["ret_1"].transform("mean")
    reg = df.groupby("symbol", group_keys=False).apply(_beta_idio, include_groups=False)
    df = df.join(reg)
    df["p_ext"] = df.groupby("date")["idio60"].rank(pct=True)
    df["p_ext"] = df["p_ext"].where(df["idio60"].notna())
    LOGGER.info("magnitude pret : idio60 %d non-null", df["idio60"].notna().sum())

    # brique direction : D1 OOF (cache)
    if args.skip_d1f and PRED_CACHE.exists():
        preds = pd.read_parquet(PRED_CACHE)
    else:
        preds = _run_d1_oof(df, feat, args)
    df = df.merge(preds, on=["symbol", "date"], how="left")
    df = _build_variants(df, args)
    LOGGER.info("D1_pred %d non-null", df["D1_pred"].notna().sum())

    wf_start = pd.Timestamp(args.wf_start)
    ho_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)
    df = df[df["date"] >= wf_start]

    score_cols = ["B0_random", "B4_relmom20", "A0_global", "A2_g60", "A2_g70", "A2_g80", "RG_g70", "F2_soft"]

    out_lines = [
        "=" * 100,
        "FINAL PER-SECTOR — GATE idio_vol60 [multi-horizon]",
        f"train D1 : {args.train_start} -> 2024 | WF (analyse seuils D'ABORD) : {wf_start.date()} -> {ho_start.date()} "
        f"| verification : {ho_start.date()} -> {end_ts.date()}",
        f"cout {ROUND_TRIP_BPS:.0f} bps/jambe | seuils 60/70/80 + random control RG_g70 | soft sizing F2_soft",
        "",
    ]

    zones = (("WALK-FORWARD (choix du seuil, NE PAS consulter la verif avant)", wf_start, ho_start),
             ("VERIFICATION 2025-2026 (une seule execution, seuil fige sur WF)", ho_start, end_ts))
    zone_frames: dict[str, pd.DataFrame] = {}
    for zone_name, zs, ze in zones:
        zone = df[(df["date"] >= zs) & (df["date"] <= ze)]
        zone_frames[zone_name] = zone
        rows = evaluate_period(zone, zs, ze, score_cols, args.min_date_size)
        tab = pd.DataFrame(rows)
        out_lines.append("=" * 100)
        out_lines.append(f"ZONE : {zone_name}")
        keep = tab[["horizon", "score", "n_dates", "ic_mean", "ic_pos_pct", "spread_net_bps"]].copy()
        keep.columns = ["h", "score", "n_dates", "ic", "ic_pos%", "spread_net_bps"]
        out_lines.append(_fmt_table(keep))
        h20 = {r["score"]: r for r in rows if r["horizon"] == 20}
        b0 = h20.get("B0_random")
        if b0 is not None:
            out_lines.append("  H20 signal_minus_random (vs B0) : " + " | ".join(
                f"{sc}: {h20[sc]['spread_net_bps'] - b0['spread_net_bps']:+.0f}"
                for sc in score_cols if sc in h20 and sc != "B0_random"))
        out_lines.append("")

    # table par symbole (H20) — WF puis verification
    per_symbol_parts = []
    for zone_name in zone_frames:
        t = _per_symbol_table(zone_frames[zone_name], zone_name)
        per_symbol_parts.append(t)
    per_symbol = pd.concat(per_symbol_parts, ignore_index=True)
    csv_path = OUT_DIR / "final_gate_per_symbol.csv"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_symbol.to_csv(csv_path, index=False)
    out_lines.append("=" * 100)
    out_lines.append("TABLE PAR SYMBOLE (H20) — top/bottom 15 par zone, export: " + str(csv_path))
    for zone_name in zone_frames:
        t = per_symbol[per_symbol["zone"] == zone_name].copy()
        t = t.sort_values("mean_rel_bps_g70", ascending=False)
        out_lines.append(f"-- {zone_name} : TOP 15 par mean_rel_bps_g70 --")
        out_lines.append(_fmt_table(t.head(15)[["symbol", "sector", "n_jours", "n_sel_g70",
                                                 "mean_rel_bps_all", "win_rate_all",
                                                 "mean_rel_bps_g70", "win_rate_g70"]]))
        out_lines.append(f"-- {zone_name} : BOTTOM 15 --")
        out_lines.append(_fmt_table(t.tail(15)[["symbol", "sector", "n_jours", "n_sel_g70",
                                                 "mean_rel_bps_all", "win_rate_all",
                                                 "mean_rel_bps_g70", "win_rate_g70"]]))

    out_lines.append("")
    out_lines.append("Protocole : choisir le seuil UNIQUEMENT sur WALK-FORWARD (ic + spread net + "
                     "supériorité sur RG_g70), puis lire la VERIFICATION une seule fois.")
    out_lines.append("GO fort si ic WF et verif > +0.03 + spread net > 0 + gain vs Random reproductible ;")
    out_lines.append("GO conditionnel si ~+0.02 tres stable + spread fort ; STOP si ic ~0, spread < 0, "
                     "gain verif seulement, ou disparition vs random.")

    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / f"per_sector_final_gate_{wf_start.date()}_{end_ts.date()}.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
