"""Phase D8 per-sector — Global + alpha x residuel sectoriel (plan GPT post-D1/D4).

Hypothese : le secteur doit CORRIGER les erreurs du Global, pas reapprendre
les rendements : residuel = rel - global_prediction.

Protocole (standalone, lecture seule, H20) :
  - Par fold WF : split chrono du train en sub-train (80 %) / sub-val (20 %).
    Global fit sur sub-train -> g_va (OOF sub-val) et g_te (test).
    Modele residuel (CatBoost, meme features + secteur) fit sur sub-val avec
    target = rel_va - g_va (quantiles clips train sub-val) -> r_te.
    final = g_te + alpha*r_te, alpha in {0, .1, .25, .5, .75, 1}.
  - Holdout gele : meme procedure avec tout le passe (<= 2024-07-01).
  - alpha choisi sur WF uniquement (max spread_net), reporte sur holdout.

Usage : python scripts/per_sector_d8_residual.py
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
    _build_cfg,
    _fit_predict_catboost,
    _fold_windows,
    _load_and_prepare,
)

LOGGER = logging.getLogger("per_sector_d8")
ALPHAS = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D8 per-sector : Global + alpha x residuel")
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


def _residual_block(train: pd.DataFrame, predict_df: pd.DataFrame,
                    feat: list[str], args: argparse.Namespace) -> pd.DataFrame:
    """Global sur sub-train, residuel sur sub-val (OOF), final = g + a*r."""
    train = train.dropna(subset=["rel_h20"]).sort_values("date").reset_index(drop=True)
    cut = int(len(train) * 0.8)
    sub_tr, sub_va = train.iloc[:cut], train.iloc[cut:]
    if len(sub_va) < 5_000:
        sub_tr, sub_va = train.iloc[: max(1, len(train) - 5_000)], train.iloc[-5_000:]

    y_tr = sub_tr["rel_h20"]
    y_tr = y_tr.clip(lower=y_tr.quantile(0.01), upper=y_tr.quantile(0.99))
    g_va = _fit_predict_catboost(sub_tr[feat], y_tr, sub_va[feat], args)
    g_pred = _fit_predict_catboost(sub_tr[feat], y_tr, predict_df[feat], args)

    resid = (sub_va["rel_h20"] - g_va).rename("resid")
    resid = resid.clip(lower=resid.quantile(0.01), upper=resid.quantile(0.99))
    r_pred = _fit_predict_catboost(sub_va[feat], resid, predict_df[feat], args)

    out = predict_df[["symbol", "date"]].copy()
    for a in ALPHAS:
        out[f"D8_a{int(a*100):03d}"] = g_pred + a * r_pred
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    cfg = _build_cfg(args)

    LOGGER.info("preparation des features ...")
    df, feat, _ = _load_and_prepare(engine, cfg, args)

    wf_start = pd.Timestamp(args.wf_start)
    hold_start = pd.Timestamp(args.holdout_start)
    end_ts = pd.Timestamp(args.end)

    preds: list[pd.DataFrame] = []
    for fi, (t0, t1) in enumerate(_fold_windows(args)):
        train = df[df["date"] < t0]
        test = df[(df["date"] >= t0) & (df["date"] < t1)]
        if len(train) < 10_000 or len(test) < 1000:
            continue
        LOGGER.info("D8 fold %d: %s -> %s | train %d test %d", fi, t0.date(), t1.date(),
                    len(train), len(test))
        preds.append(_residual_block(train, test, feat, args))

    train_all = df[df["date"] < hold_start]
    hold = df[(df["date"] >= hold_start) & (df["date"] <= end_ts)]
    LOGGER.info("D8 holdout: train %d -> pred %d", len(train_all), len(hold))
    preds.append(_residual_block(train_all, hold, feat, args))

    oos = pd.concat(preds, ignore_index=True)
    eval_df = df.merge(oos, on=["symbol", "date"], how="left")
    eval_df = eval_df[eval_df["date"] >= wf_start]
    for h in HORIZONS:
        for col in (f"rel_h{h}", f"rel_h{h}_w", f"fut_h{h}"):
            if col not in eval_df.columns:
                eval_df[col] = np.nan

    score_cols = ["B0_random", "B4_relmom20"] + [f"D8_a{int(a*100):03d}" for a in ALPHAS]

    out_lines = [
        "=" * 100,
        "PHASE D8 — GLOBAL + alpha x RESIDUEL SECTORIEL [H20]",
        "residuel = rel - global_prediction (le secteur corrige le Global, OOF sub-val)",
        f"alphas = {ALPHAS} | cout {ROUND_TRIP_BPS:.0f} bps/jambe | choix alpha sur WF uniquement",
        "",
    ]
    wf_net: dict[str, float] = {}
    for zone_name, (zs, ze) in (("WALK-FORWARD", (wf_start, hold_start)),
                                ("HOLDOUT GELE", (hold_start, end_ts))):
        zone = eval_df[(eval_df["date"] >= zs) & (eval_df["date"] <= ze)]
        rows = evaluate_period(zone, zs, ze, score_cols, args.min_date_size)
        rows20 = [r for r in rows if r["horizon"] == 20]
        out_lines.append(f"ZONE : {zone_name}  [H20]")
        out_lines.append(_fmt_table(pd.DataFrame(rows20).drop(columns=["horizon"])))
        out_lines.append("")
        if zone_name == "WALK-FORWARD":
            wf_net = {r["score"]: r["spread_net_bps"] for r in rows20}

    chosen = max((s for s in wf_net if s.startswith("D8_")), key=lambda s: wf_net[s])
    out_lines.append(f"ALPHA CHOISI SUR WF (max spread_net) : {chosen} "
                     f"(net WF = {wf_net[chosen]:+.0f} bps) — a verifier sur holdout.")
    out_lines.append("Critere GPT : spread net > 0 WF ET holdout + meilleur que "
                     f"D8_a000 (global seul, net WF = {wf_net.get('D8_a000', float('nan')):+.0f} bps).")
    report = "\n".join(out_lines)
    print(report)
    out_path = Path("logs") / "per_sector_d8_residual_2019-01-01_2025-12-31.txt"
    out_path.write_text(report + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
