"""Phase 0bis per-sector — baselines "information PIT" existantes.

Complete le harness de Phase 0 (scripts/per_sector_baselines.py) avec des scores
issus de donnees deja en base (PIT par construction) :
  S_sent_net1d / S_sent_net5d          : sentiment net 1d/5d + version relative (mediane secteur)
  S_short / S_normtot / S_trend        : short_score, normalized_total_score, trend_score
                                          du screener + versions relatives
  S_pe_pct / S_roe_pct / S_epsg_pct /
  S_revg_pct                           : percentiles sectoriels par date des
                                          fondamentaux (PIT via forward_fill_fundamentals)

Metriques identiques a la Phase 0 : IC Spearman relatif par date + spread
quintile net de couts, zones WF + holdout gele.

Usage : python scripts/per_sector_baselines_signals.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.per_sector_baselines import (  # noqa: E402
    HORIZONS,
    SPREAD_COST,
    ROUND_TRIP_BPS,
    _fmt_table,
    _read_universe,
    add_baseline_scores,
    add_sector_medians,
    build_panel,
    evaluate_period,
    parse_args,
)

LOGGER = logging.getLogger("per_sector_signals")

SENT_COLS = ["sentiment_net_mean_1d", "sentiment_net_mean_5d"]
SCORE_COLS = ["short_score", "normalized_total_score", "trend_score"]
FUND_COLS = ["pe_ratio", "roe", "eps_growth_yoy", "revenue_growth_yoy"]


def _load_table(engine: Any, table: str, cols: list[str], symbols: list[str],
                date_col: str, start: str, end: str) -> pd.DataFrame:
    in_clause = ",".join(f"'{s}'" for s in sorted(symbols))
    select_cols = list(dict.fromkeys([*cols, date_col]))
    col_list = ", ".join([f"`{c}`" for c in select_cols])
    q = (f"SELECT {col_list} FROM {table} WHERE symbol IN ({in_clause}) "
         f"AND `{date_col}` >= '{start}' AND `{date_col}` <= '{end}'")
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df[date_col])
    return df


def add_signal_scores(panel: pd.DataFrame, engine: Any, start: str, end: str) -> tuple[pd.DataFrame, list[str]]:
    """Ajoute les scores signaux au panel. Retourne (panel modifie, noms de colonnes)."""
    symbols = sorted(panel["symbol"].unique())
    new_cols: list[str] = []

    # ── Sentiment ──
    sent = _load_table(engine, "ticker_daily_sentiment_features",
                       ["symbol"] + SENT_COLS, symbols, "trade_date", start, end)
    if not sent.empty:
        panel = panel.merge(sent, on=["symbol", "date"], how="left")
        for col in SENT_COLS:
            sc = f"S_sent_{col.split('_')[-1]}"
            panel[sc] = panel[col]
            med = panel.groupby(["date", "sector"])[sc].transform("median")
            panel[f"{sc}_rel"] = panel[sc] - med
            new_cols += [sc, f"{sc}_rel"]

    # ── Scores screener ──
    scr = _load_table(engine, "stock_scores_history",
                      ["symbol"] + SCORE_COLS, symbols, "snapshot_date", start, end)
    if not scr.empty:
        panel = panel.merge(scr, on=["symbol", "date"], how="left")
        for col in SCORE_COLS:
            sc = f"S_{col}"
            panel[sc] = panel[col]
            med = panel.groupby(["date", "sector"])[sc].transform("median")
            panel[f"{sc}_rel"] = panel[sc] - med
            new_cols += [sc, f"{sc}_rel"]

    # ── Fondamentaux (percentile sectoriel par date, PIT) ──
    from modelFactory.fundamental_features import (
        load_fundamentals_from_db,
        forward_fill_fundamentals,
    )
    fund = load_fundamentals_from_db(symbols, pd.Timestamp(start), pd.Timestamp(end),
                                     engine=engine)
    if not fund.empty:
        trading_days = pd.DatetimeIndex(sorted(panel["date"].unique()))
        fund_ff = forward_fill_fundamentals(fund, trading_days)
        for col in FUND_COLS:
            if col not in fund_ff.columns:
                continue
            sub = fund_ff[["symbol", "date", col]].rename(columns={col: f"f_{col}"})
            panel = panel.merge(sub, on=["symbol", "date"], how="left")
            sc = f"S_fund_{col}_pct"
            # percentile au sein du secteur a chaque date
            panel[sc] = panel.groupby(["date", "sector"])[f"f_{col}"].transform(
                lambda x: x.rank(pct=True))
            new_cols.append(sc)

    return panel, new_cols


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    _fh = logging.FileHandler(Path("logs") / "signal_run_progress.log", encoding="utf-8")
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
    score_cols = ["B0_random", "B4_relmom20"] + signal_cols
    LOGGER.info("scores actifs (%d) : %s", len(score_cols), ", ".join(score_cols))

    start_ts, hold_ts, end_ts = (pd.Timestamp(args.start), pd.Timestamp(args.holdout_start),
                                 pd.Timestamp(args.end))
    wf_zone = panel[(panel["date"] >= start_ts) & (panel["date"] < hold_ts)]
    hold_zone = panel[(panel["date"] >= hold_ts) & (panel["date"] <= end_ts)]

    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("PHASE 0bis — BASELINES SIGNAUX PIT (sentiment, screener, fondamentaux relatifs)")
    lines.append(f"univers: {args.universe} ({len(symbols)} symboles)")
    lines.append(f"zones : WF {args.start} -> {args.holdout_start} (exclu) | "
                 f"HOLDOUT {args.holdout_start} -> {args.end}")
    lines.append(f"couts : aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> "
                 f"spread net = gross - {SPREAD_COST*10_000:.0f} bps")
    lines.append(f"references : B0_random (harness) et B4_relmom20 (momentum relatif, "
                 f"deja teste = nul)")
    lines.append("")

    for zone_name, zone_df in (("WALK-FORWARD", wf_zone), ("HOLDOUT GELE", hold_zone)):
        lines.append("=" * 100)
        lines.append(f"ZONE : {zone_name}")
        lines.append("=" * 100)
        periods = pd.period_range(zone_df["date"].min(), zone_df["date"].max(), freq="2Q")
        for per in periods:
            LOGGER.info("evaluation %s %s -> %s ...", zone_name, per.start_time.date(), per.end_time.date())
            rows = evaluate_period(panel, per.start_time, per.end_time,
                                   score_cols, args.min_date_size)
            if not rows:
                continue
            df = pd.DataFrame(rows)
            LOGGER.info("evaluation %s %s -> %s OK (%d lignes)", zone_name,
                        per.start_time.date(), per.end_time.date(), len(df))
            lines.append("")
            lines.append(f"--- PERIODE {per.start_time.date()} -> {per.end_time.date()} ---")
            for h in HORIZONS:
                sub = df[df["horizon"] == h]
                if sub.empty:
                    continue
                sub = sub.drop(columns=["horizon"])
                lines.append(f"[H{h}] IC relatif (Spearman/date vs rel_return) + spread quintile")
                lines.append(_fmt_table(sub))
                lines.append("")
    lines.append("")
    lines.append("Lecture : ic_mean = IC relatif moyen | ic_pos_pct = % dates IC>0 | "
                 "spread_net_bps = spread top-bottom net de 102 bps (valeurs winsorisees).")
    lines.append("Seuil d'interet : ic_mean > 0.02 avec ic_pos_pct > 60 % sur la zone WF "
                 "ET confirme sur holdout, spread_net_bps > 0.")

    out = "\n".join(lines)
    print(out)
    out_path = Path("logs") / f"per_sector_baselines_signals_{args.start}_{args.end}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", out_path)


if __name__ == "__main__":
    main()
