"""Phase 5 per-sector — interactions conditionnelles (short_score x regime, etc.).

Hypothese : les signaux PIT testes en Phase 0bis etaient instables en signe
(short_score negatif en 2019, positif en 2025H1). On teste :
  1. Segmentation par regime (bull / bear / neutre / bull_strict) des scores
     les plus prometteurs : S_short_score, B4_relmom20, S_fund_pe_ratio_pct,
     S_fund_eps_growth_yoy_pct.
  2. Scores d'interaction (evalues globalement) :
       X_val_mom   = (1 - pe_pct) * rel_mom20      (sous-evalue ET momentum relatif +)
       X_epsg_mom  = eps_growth_yoy * rel_mom20    (croissance ET momentum)
       X_short_mom = short_score * rel_mom20       (short_score x mom20)

Regimes (comme l'analyse Global Ranking) :
  bull        = SPY > SMA200
  bear        = SPY < SMA200 * 0.98
  neutre      = sinon
  bull_strict = bull ET ret60 > +3 %

Metriques : IC Spearman relatif par date + spread quintile net de couts.
Zones : WF (start -> holdout-start) et HOLDOUT (holdout-start -> end),
agregees par zone (pas de demi-annees, pour garder le rapport lisible).

Usage : python scripts/per_sector_interactions.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.per_sector_baselines import (  # noqa: E402
    HORIZONS,
    SPREAD_COST,
    ROUND_TRIP_BPS,
    _adjusted_close,
    _fmt_table,
    _read_universe,
    add_baseline_scores,
    add_sector_medians,
    build_panel,
    evaluate_period,
    parse_args,
)
from scripts.per_sector_baselines_signals import add_signal_scores  # noqa: E402

LOGGER = logging.getLogger("per_sector_interactions")

INTERACTION_SCORES = ["B4_relmom20", "S_short_score", "S_short_score_rel",
                      "S_fund_pe_ratio_pct", "S_fund_eps_growth_yoy_pct",
                      "X_val_mom", "X_epsg_mom", "X_short_mom"]
REGIMES = ("all", "bull", "bear", "neutre", "bull_strict")


def add_regime(panel: pd.DataFrame, engine, start: str, end: str) -> pd.DataFrame:
    """Ajoute spy_close/sma200/ret60, regime et bull_strict au panel."""
    from modelFactory.data_loader import load_benchmark_bars
    spy = load_benchmark_bars(engine, "SPY", start_date=pd.Timestamp(start).date(),
                              end_date=pd.Timestamp(end).date())
    if spy.empty:
        LOGGER.warning("pas de barres SPY -> regime indisponible")
        panel["regime"] = "neutre"
        panel["bull_strict"] = False
        return panel
    close = _adjusted_close(spy).reset_index(drop=True)
    spy_df = pd.DataFrame({
        "date": pd.to_datetime(spy["date"]).reset_index(drop=True),
        "spy_close": close,
        "spy_sma200": close.rolling(200).mean(),
        "spy_ret60": close.pct_change(60),
    })
    panel = panel.merge(spy_df, on="date", how="left")
    panel["regime"] = np.where(
        panel["spy_close"] > panel["spy_sma200"], "bull",
        np.where(panel["spy_close"] < panel["spy_sma200"] * 0.98, "bear", "neutre"))
    panel["bull_strict"] = (
        (panel["spy_close"] > panel["spy_sma200"]) & (panel["spy_ret60"] > 0.03))
    return panel


def add_interaction_scores(panel: pd.DataFrame) -> list[str]:
    """Ajoute les scores d'interaction au panel."""
    # rank percentile intra-date du momentum relatif et de l'eps growth
    rel_mom_r = panel.groupby("date")["rel_mom20"].rank(pct=True)
    cheap = 1.0 - panel["S_fund_pe_ratio_pct"].fillna(0.5)
    epsg = panel["S_fund_eps_growth_yoy_pct"].fillna(0.5)
    panel["X_val_mom"] = cheap * rel_mom_r
    panel["X_epsg_mom"] = epsg * rel_mom_r
    panel["X_short_mom"] = panel["S_short_score"] * rel_mom_r
    return ["X_val_mom", "X_epsg_mom", "X_short_mom"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    _fh = logging.FileHandler(Path("logs") / "interactions_progress.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(_fh)
    args = parse_args()
    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    symbols = _read_universe(args.universe)
    panel = build_panel(engine, symbols, pd.Timestamp(args.start).date(),
                        pd.Timestamp(args.end).date(), args.buffer_days)
    panel = add_sector_medians(panel, args.min_sector_size)
    add_baseline_scores(panel, args.seed)
    panel, signal_cols = add_signal_scores(panel, engine, args.start, args.end)
    _ = signal_cols
    panel = add_regime(panel, engine, args.start, args.end)
    interaction_cols = add_interaction_scores(panel)
    score_cols = [c for c in INTERACTION_SCORES if c in panel.columns]
    score_cols = list(dict.fromkeys(score_cols + [c for c in interaction_cols if c in panel.columns]))
    LOGGER.info("scores actifs (%d) : %s", len(score_cols), ", ".join(score_cols))

    start_ts, hold_ts, end_ts = (pd.Timestamp(args.start), pd.Timestamp(args.holdout_start),
                                 pd.Timestamp(args.end))
    wf_zone = panel[(panel["date"] >= start_ts) & (panel["date"] < hold_ts)]
    hold_zone = panel[(panel["date"] >= hold_ts) & (panel["date"] <= end_ts)]

    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("PHASE 5 — INTERACTIONS CONDITIONNELLES (regime x signal, val x mom)")
    lines.append(f"univers: {args.universe} ({len(symbols)} symboles)")
    lines.append(f"zones : WF {args.start} -> {args.holdout_start} (exclu) | "
                 f"HOLDOUT {args.holdout_start} -> {args.end}")
    lines.append(f"couts : aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> "
                 f"spread net = gross - {SPREAD_COST*10_000:.0f} bps")
    lines.append("regimes : bull = SPY>SMA200 | bear = SPY<SMA200*0.98 | "
                 "neutre = sinon | bull_strict = bull ET ret60>+3%")
    lines.append("")

    for zone_name, zone_df in (("WALK-FORWARD", wf_zone), ("HOLDOUT GELE", hold_zone)):
        lines.append("=" * 100)
        lines.append(f"ZONE : {zone_name}")
        lines.append("=" * 100)
        for reg in REGIMES:
            if reg == "all":
                sub_panel = zone_df
            elif reg == "bull_strict":
                sub_panel = zone_df[zone_df["bull_strict"]]
            else:
                sub_panel = zone_df[zone_df["regime"] == reg]
            if sub_panel.empty:
                continue
            LOGGER.info("evaluation %s regime=%s ...", zone_name, reg)
            rows = evaluate_period(sub_panel, zone_df["date"].min(), zone_df["date"].max(),
                                   score_cols, max(args.min_date_size, 15))
            if not rows:
                continue
            df = pd.DataFrame(rows)
            lines.append("")
            lines.append(f"--- REGIME {reg.upper()} (dates={sub_panel['date'].nunique()}) ---")
            for h in HORIZONS:
                sub = df[df["horizon"] == h]
                if sub.empty:
                    continue
                sub = sub.drop(columns=["horizon"])
                lines.append(f"[H{h}] IC relatif (Spearman/date vs rel_return) + spread quintile")
                lines.append(_fmt_table(sub))
                lines.append("")
            LOGGER.info("evaluation %s regime=%s OK", zone_name, reg)

    lines.append("")
    lines.append("Lecture : ic_mean = IC relatif moyen | ic_pos_pct = % dates IC>0 | "
                 "spread_net_bps = spread top-bottom net de 102 bps.")
    lines.append("Seuil d'interet : ic_mean > 0.02, ic_pos_pct > 60 %, spread_net_bps > 0, "
                 "STABLE entre zone WF et holdout pour un meme regime.")

    out = "\n".join(lines)
    print(out)
    out_path = Path("logs") / f"per_sector_interactions_{args.start}_{args.end}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
