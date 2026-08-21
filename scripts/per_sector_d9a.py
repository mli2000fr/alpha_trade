"""Phase D9-A1 per-sector — combiner la brique DIRECTION (D1) et la brique
MAGNITUDE (D4). Plan GPT post-D1/D4 (2026-08-15).

Variantes (H20, protocole D1 identique, standalone, lecture seule) :
  A0_global  : D1_pred (baseline direction)
  A1_mul     : D1_pred x P_extreme  (P_extreme = percentile intra-date idio_vol60)
  A2_g60/70/80 : gating — D1_pred si P_extreme > seuil, sinon NaN (flat)
  A3_w       : D1_pred x (0.5 + 0.5 P_extreme)  (sizing : ne change jamais le signe)

+ analyse par quintile d'idio_vol60 (Q1-Q5 : mean rel, mean |rel|, P(top), P(bottom))
  → test "pur detecteur d'opportunite" de GPT.

Usage : python scripts/per_sector_d9a.py
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
    evaluate_period,
)
from scripts.per_sector_d1_global import (  # noqa: E402
    ORACLE_NET_HOLDOUT_H20,
    ORACLE_NET_WF_H20,
    _build_cfg,
    _fit_predict_catboost,
    _fold_windows,
    _load_and_prepare,
    _spearman,
)
from scripts.per_sector_d4_dispersion import _beta_idio  # noqa: E402

LOGGER = logging.getLogger("per_sector_d9a")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D9-A1 per-sector : direction x magnitude")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--train-start", default="2016-01-01")
    p.add_argument("--wf-start", default="2019-01-01")
    p.add_argument("--holdout-start", default="2024-07-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--folds", type=int, default=11)
    p.add_argument("--iterations", type=int, default=300)
    p.add_argument("--depth", type=int, default=6)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-sector-size", type=int, default=3)
    p.add_argument("--min-date-size", type=int, default=40)
    p.add_argument("--no-sector-cat", action="store_true", help=argparse.SUPPRESS)
    return p.parse_args()


def _run_d1_folds(df: pd.DataFrame, feat: list[str], args: argparse.Namespace) -> pd.DataFrame:
    """Reproduit les predictions D1 : 11 folds WF + holdout gele (PIT-safe)."""
    wf_start = pd.Timestamp(args.wf_start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)
    preds: list[pd.DataFrame] = []
    for fi, (t0, t1) in enumerate(_fold_windows(args)):
        tr_ok = df[df["date"] < t0].dropna(subset=["rel_h20"])
        te_ok = df[(df["date"] >= t0) & (df["date"] < t1)].dropna(subset=["rel_h20"])
        if len(tr_ok) < 10_000 or len(te_ok) < 1000:
            continue
        y = tr_ok["rel_h20"]
        y = y.clip(lower=y.quantile(0.01), upper=y.quantile(0.99))
        LOGGER.info("D9-A1 fold %d: %s -> %s | train %d test %d", fi, t0.date(), t1.date(),
                    len(tr_ok), len(te_ok))
        p = _fit_predict_catboost(tr_ok[feat], y, te_ok[feat], args)
        preds.append(te_ok[["symbol", "date"]].assign(D1_pred=p))
    train_all = df[df["date"] < hold_start].dropna(subset=["rel_h20"])
    hold = df[(df["date"] >= hold_start) & (df["date"] <= end_ts)]
    y = train_all["rel_h20"]
    y = y.clip(lower=y.quantile(0.01), upper=y.quantile(0.99))
    LOGGER.info("D9-A1 holdout: train %d -> pred %d", len(train_all), len(hold))
    p_hold = _fit_predict_catboost(train_all[feat], y, hold[feat], args)
    preds.append(hold[["symbol", "date"]].assign(D1_pred=p_hold))
    return pd.concat(preds, ignore_index=True)


def _quintile_analysis(zone: pd.DataFrame, min_date_size: int) -> pd.DataFrame:
    sub = zone.dropna(subset=["rel_h20_w", "idio60"]).copy()
    size = sub.groupby("date")["symbol"].transform("nunique")
    sub = sub[size >= min_date_size]
    q = sub.groupby("date")["idio60"].transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    qdir = sub.groupby("date")["rel_h20_w"].transform(
        lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    sub = sub.assign(_q=q, _top=(qdir == 4.0).astype(float),
                     _bot=(qdir == 0.0).astype(float))
    rows = []
    for qi in range(5):
        g = sub[sub["_q"] == qi]
        rows.append({
            "quintile_idio60": f"Q{qi+1}",
            "n": len(g),
            "mean_rel_bps": round(float(g["rel_h20_w"].mean() * 10_000), 1),
            "mean_abs_rel_bps": round(float(g["rel_h20_w"].abs().mean() * 10_000), 1),
            "P_top_pct": round(float(g["_top"].mean() * 100), 1),
            "P_bot_pct": round(float(g["_bot"].mean() * 100), 1),
        })
    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    cfg = _build_cfg(args)

    LOGGER.info("preparation des features ...")
    df, feat, _ = _load_and_prepare(engine, cfg, args)

    # ── brique magnitude : idio_vol60 (residu regression titre ~ secteur) ──
    df["ret_1"] = df["daily_return"]
    df["sector_ret"] = df.groupby(["date", "sector"])["ret_1"].transform("mean")
    reg = df.groupby("symbol", group_keys=False).apply(_beta_idio, include_groups=False)
    df = df.join(reg)
    df["p_ext"] = df.groupby("date")["idio60"].rank(pct=True)
    df["p_ext"] = df["p_ext"].where(df["idio60"].notna())
    LOGGER.info("magnitude pret : idio60 %d non-null", df["idio60"].notna().sum())

    # ── brique direction : reproduire D1 ──
    preds = _run_d1_folds(df, feat, args)
    eval_df = df.merge(preds, on=["symbol", "date"], how="left")
    wf_start = pd.Timestamp(args.wf_start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)
    eval_df = eval_df[eval_df["date"] >= wf_start]

    # ── combinaisons ──
    d1p = eval_df["D1_pred"]
    pe = eval_df["p_ext"]
    eval_df["A0_global"] = d1p
    eval_df["A1_mul"] = d1p * pe
    eval_df["A2_g60"] = d1p.where(pe >= 0.60)
    eval_df["A2_g70"] = d1p.where(pe >= 0.70)
    eval_df["A2_g80"] = d1p.where(pe >= 0.80)
    eval_df["A3_w"] = d1p * (0.5 + 0.5 * pe)

    for h in HORIZONS:
        for col in (f"rel_h{h}", f"rel_h{h}_w", f"fut_h{h}"):
            if col not in eval_df.columns:
                eval_df[col] = np.nan

    score_cols = ["B0_random", "B4_relmom20", "A0_global", "A1_mul",
                  "A2_g60", "A2_g70", "A2_g80", "A3_w"]

    out_lines = [
        "=" * 100,
        "PHASE D9-A1 — DIRECTION (D1) x MAGNITUDE (idio_vol60) [H20]",
        f"cout: aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> net = gross - {SPREAD_COST*10_000:.0f} bps",
        "A0 global seul | A1 P_extreme x D1 | A2 gating P>60/70/80% (NaN = flat) | "
        "A3 sizing D1 x (0.5+0.5P) — ne change jamais le signe",
        "",
    ]

    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        zone = eval_df[(eval_df["date"] >= zs) & (eval_df["date"] <= ze)]
        rows = evaluate_period(zone, zs, ze, score_cols, args.min_date_size)
        rows20 = [r for r in rows if r["horizon"] == 20]
        out_lines.append(f"ZONE : {zone_name}  [H20]  — direction (IC relatif + spread net)")
        out_lines.append(_fmt_table(pd.DataFrame(rows20).drop(columns=["horizon"])))
        by_score = {r["score"]: r for r in rows20}
        if "A0_global" in by_score and "B0_random" in by_score:
            oracle = ORACLE_NET_WF_H20 if zone_name == "WALK-FORWARD" else ORACLE_NET_HOLDOUT_H20
            b0 = by_score["B0_random"]
            out_lines.append("  signal_minus_random (vs B0) : " + " | ".join(
                f"{sc}: {by_score[sc]['spread_net_bps'] - b0['spread_net_bps']:+.0f}"
                for sc in score_cols if sc in by_score and sc != "B0_random"))
            out_lines.append(f"  (oracle net H20 = {oracle:.0f})")
        out_lines.append("")
        out_lines.append(f"ZONE : {zone_name}  — quintiles d'idio_vol60 "
                         "(pur detecteur d'opportunite ?)")
        out_lines.append(_fmt_table(_quintile_analysis(zone, args.min_date_size)))
        out_lines.append("")

    out_lines.append("Lecture : si Q1->Q5 fait monter |rel| ET P(top)/P(bot) ~ 50/50 partout, "
                     "idio_vol60 = detecteur d'opportunite pur (pas directionnel). "
                     "Si un variant depasse A0 sur WF ET holdout en spread net, la combinaison marche.")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / "per_sector_d9a_2019-01-01_2025-12-31.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
