"""Phase 0 per-sector — benchmark des baselines simples (B0-B5).

Objectif : repondre a la question "existe-t-il deja un alpha intra-sectoriel
trivial ?" avant de toucher au ML.

Pour chaque secteur x date x horizon H3/H5/H10/H15/H20 :
  - future_return_h      = close[t+h]/close[t] - 1 (prix ajuste)
  - relative_return_h    = future_return_h - mediane sectorielle(future_return_h, date)

Baselines (scores par symbole/date) :
  B0_random        score aleatoire (seed fixe)
  B1_mom20/60/120  rendement passe sur 20/60/120 jours
  B2_rev5/10       -ret_5 / -ret_10 (reversal)
  B3_momvol        ret_20 / vol_20
  B4_relmom20      ret_20 - mediane sectorielle(ret_20, date)
  B5_blend         0.5*rel20 + 0.3*rel60 + 0.2*rel120

Metriques (metrique primaire = IC relatif + spread net, PAS le F1) :
  - IC Spearman par date : score vs relative_return_h
    -> IC moyen, IC std, IR = IC/std, % dates positives
  - Spread quintile : moyenne relative_return du top 20% - bottom 20%
    -> brut et net (cout aller-retour 51 bps par jambe = 102 bps pour le
       long-short), % dates a spread positif
  - IC vs future_return BRUT (reference : le score a-t-il du beta absolu ?)

Zones : zone walk-forward (start -> holdout-start) et holdout gele
(holdout-start -> end), decoupees en demi-annees.

Usage :
  python scripts/per_sector_baselines.py \
      --start 2019-01-01 --holdout-start 2024-07-01 --end 2025-12-31 \
      --universe config/ticket_mid_cap_400.txt
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

# Permet de lancer le script depuis n'importe quel CWD
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modelFactory.cross_sectional import load_sector_groups
from modelFactory.data_loader import load_universe_bars

LOGGER = logging.getLogger("per_sector_baselines")
HORIZONS = (3, 5, 10, 15, 20)
ROUND_TRIP_BPS = 51.0          # 1 bps comm + 2 bps slip + spread ~44 bps
SPREAD_COST = 2 * ROUND_TRIP_BPS / 10_000.0   # 2 jambes -> 102 bps


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 0 per-sector baselines B0-B5")
    p.add_argument("--start", default="2019-01-01", help="debut de l'evaluation")
    p.add_argument("--holdout-start", default="2024-07-01",
                   help="debut du holdout gele (zone WF avant, holdout apres)")
    p.add_argument("--end", default="2025-12-31", help="fin de l'evaluation")
    p.add_argument("--universe", default="config/ticket_mid_cap_400.txt")
    p.add_argument("--min-sector-size", type=int, default=3,
                   help="nb min de symboles par (date, secteur) pour la mediane")
    p.add_argument("--min-date-size", type=int, default=40,
                   help="nb min de symboles une date pour calculer IC/spread")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--buffer-days", type=int, default=260,
                   help="jours charges avant --start pour le momentum")
    p.add_argument("--log-file", default=None,
                   help="fichier de sortie (defaut: logs/per_sector_baselines_<start>_<end>.txt)")
    return p.parse_args(argv)


def _read_universe(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    symbols = [s.strip().upper() for s in text.replace("\n", ",").split(",") if s.strip()]
    return list(dict.fromkeys(symbols))


def _adjusted_close(bars: pd.DataFrame) -> pd.Series:
    close = pd.to_numeric(bars["close"], errors="coerce").astype(float)
    if "adj_close" in bars.columns:
        adj = pd.to_numeric(bars["adj_close"], errors="coerce").astype(float)
        ratio = (adj / close.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        ratio = ratio.where(ratio > 0.0, np.nan).fillna(1.0)
        close = close * ratio
    return close


def build_panel(
    engine: Any,
    symbols: list[str],
    start: date,
    end: date,
    buffer_days: int,
) -> pd.DataFrame:
    """Panel (symbol, date) avec retours passes, vol, future returns et secteur."""
    load_start = start - timedelta(days=buffer_days)
    bars = load_universe_bars(engine, symbols, start_date=load_start, end_date=end)
    if bars.empty:
        raise RuntimeError("Aucune barre chargee pour l'univers demande")
    LOGGER.info("bars brutes: %d lignes, %d symboles", len(bars), bars["symbol"].nunique())

    sector_groups = load_sector_groups(engine)
    sym_to_sector: dict[str, str] = {}
    for gics, syms in sector_groups.items():
        for s in syms:
            sym_to_sector[s] = gics
    mapped = [s for s in symbols if s in sym_to_sector]
    LOGGER.info("symboles dans un secteur GICS: %d/%d", len(mapped), len(symbols))
    bars = bars[bars["symbol"].isin(mapped)].copy()

    panel = bars[["symbol", "date"]].copy()
    bars = bars.sort_values(["symbol", "date"]).reset_index(drop=True)
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)

    close = _adjusted_close(bars)
    ret = close.pct_change()
    panel["close"] = close.values
    panel["ret_1"] = ret.values

    g = panel.groupby("symbol", sort=False)
    for w in (5, 10, 20, 60, 120):
        # vectorise : close[t]/close[t-w] - 1 (equivalent au produit des rendements)
        panel[f"ret_{w}"] = g["close"].transform(
            lambda s: s / s.shift(w) - 1.0)
    panel["vol_20"] = g["ret_1"].transform(
        lambda s: s.rolling(20).std() * np.sqrt(252))

    # future returns (brut, prix ajuste) par horizon : close[t+h]/close[t] - 1
    for h in HORIZONS:
        panel[f"fut_h{h}"] = g["close"].transform(
            lambda s: s.shift(-h) / s - 1.0)

    panel["sector"] = panel["symbol"].map(sym_to_sector)
    panel = panel.dropna(subset=["sector"])
    return panel


def add_sector_medians(panel: pd.DataFrame, min_sector_size: int) -> pd.DataFrame:
    """Mediane sectorielle par date pour fut_h{h}, ret_20/60/120.

    Les dates/secteurs avec < min_sector_size symboles sont mis a NaN.
    """
    for h in HORIZONS:
        counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
        med = panel.groupby(["date", "sector"])[f"fut_h{h}"].transform("median")
        panel[f"rel_h{h}"] = panel[f"fut_h{h}"] - med.where(counts >= min_sector_size)
        # version winsorisee 1%/99% intra-date pour le spread (IC = rank-based, brut OK)
        lo = panel.groupby("date")[f"rel_h{h}"].transform(lambda x: x.quantile(0.01))
        hi = panel.groupby("date")[f"rel_h{h}"].transform(lambda x: x.quantile(0.99))
        panel[f"rel_h{h}_w"] = panel[f"rel_h{h}"].clip(lower=lo, upper=hi)
    for w in (20, 60, 120):
        counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
        med = panel.groupby(["date", "sector"])[f"ret_{w}"].transform("median")
        panel[f"rel_mom{w}"] = panel[f"ret_{w}"] - med.where(counts >= min_sector_size)
    return panel


def add_baseline_scores(panel: pd.DataFrame, seed: int) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    panel["B0_random"] = rng.random(len(panel))
    panel["B1_mom20"] = panel["ret_20"]
    panel["B1_mom60"] = panel["ret_60"]
    panel["B1_mom120"] = panel["ret_120"]
    panel["B2_rev5"] = -panel["ret_5"]
    panel["B2_rev10"] = -panel["ret_10"]
    panel["B3_momvol"] = panel["ret_20"] / panel["vol_20"].clip(lower=1e-9)
    panel["B4_relmom20"] = panel["rel_mom20"]
    panel["B5_blend"] = (
        0.5 * panel["rel_mom20"] + 0.3 * panel["rel_mom60"] + 0.2 * panel["rel_mom120"])
    return {c: f"score={c}" for c in
            ["B0_random", "B1_mom20", "B1_mom60", "B1_mom120",
             "B2_rev5", "B2_rev10", "B3_momvol", "B4_relmom20", "B5_blend"]}


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return float(a.rank().corr(b.rank()))


def _ic_stats(group: pd.DataFrame, score_col: str, y_col: str) -> dict[str, float]:
    ic = group[score_col].rank().corr(group[y_col].rank())
    return {"ic": float(ic)}


def evaluate_period(
    panel: pd.DataFrame,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    score_cols: list[str],
    min_date_size: int,
) -> list[dict[str, Any]]:
    """IC relatif par date + spread quintile net pour une periode, tous horizons."""
    zone = panel[(panel["date"] >= period_start) & (panel["date"] <= period_end)]
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        y_col = f"rel_h{h}"
        y_w_col = f"rel_h{h}_w"
        abs_col = f"fut_h{h}"
        sub = zone.dropna(subset=[y_col, "symbol"])
        if sub.empty:
            continue
        # garder les dates avec assez de symboles
        size = sub.groupby("date")["symbol"].transform("nunique")
        sub = sub[size >= min_date_size]
        for sc in score_cols:
            if sc not in sub.columns:
                rows.append({"horizon": h, "score": sc, "n_dates": 0})
                continue
            s = sub.dropna(subset=[sc, y_col])
            if s.empty:
                rows.append({"horizon": h, "score": sc, "n_dates": 0})
                continue
            # garde pour scores clairsemes (ex sentiment) : >= 5 symboles/date
            size2 = s.groupby("date")["symbol"].transform("nunique")
            s = s[size2 >= 5]
            if s.empty:
                rows.append({"horizon": h, "score": sc, "n_dates": 0})
                continue
            ic_by_date = s.groupby("date").apply(
                lambda g: _spearman(g[sc], g[y_col]), include_groups=False)
            abs_by_date = s.groupby("date").apply(
                lambda g: _spearman(g[sc], g[abs_col]), include_groups=False)
            q = s.groupby("date")[sc].transform(
                lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
            s = s.assign(_q=q)
            spread = s.groupby("date").apply(
                lambda g: float(g.loc[g["_q"] == 4, y_w_col].mean()
                                - g.loc[g["_q"] == 0, y_w_col].mean()),
                include_groups=False)
            ic = ic_by_date.dropna()
            spread = spread.dropna()
            rows.append({
                "horizon": h,
                "score": sc,
                "n_dates": int(len(ic)),
                "ic_mean": float(ic.mean()),
                "ic_std": float(ic.std(ddof=0)),
                "ic_ir": float(ic.mean() / ic.std(ddof=0)) if ic.std(ddof=0) > 0 else float("nan"),
                "ic_pos_pct": float((ic > 0).mean() * 100),
                "ic_abs_mean": float(abs_by_date.dropna().mean()),
                "spread_gross_bps": float(spread.mean() * 10_000),
                "spread_net_bps": float((spread.mean() - SPREAD_COST) * 10_000),
                "spread_pos_pct": float((spread > 0).mean() * 100),
            })
    return rows


def _fmt_table(df: pd.DataFrame) -> str:
    return df.to_string(index=False, float_format=lambda x: f"{x:.3f}")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    engine = create_engine(
        "mysql+pymysql://root:root@localhost/alpha_trade", future=True)

    symbols = _read_universe(args.universe)
    LOGGER.info("univers: %d symboles depuis %s", len(symbols), args.universe)

    panel = build_panel(engine, symbols, pd.Timestamp(args.start).date(),
                        pd.Timestamp(args.end).date(), args.buffer_days)
    panel = add_sector_medians(panel, args.min_sector_size)
    add_baseline_scores(panel, args.seed)

    score_cols = ["B0_random", "B1_mom20", "B1_mom60", "B1_mom120",
                  "B2_rev5", "B2_rev10", "B3_momvol", "B4_relmom20", "B5_blend"]

    start_ts, hold_ts, end_ts = (pd.Timestamp(args.start), pd.Timestamp(args.holdout_start),
                                 pd.Timestamp(args.end))
    wf_zone = panel[(panel["date"] >= start_ts) & (panel["date"] < hold_ts)]
    hold_zone = panel[(panel["date"] >= hold_ts) & (panel["date"] <= end_ts)]
    LOGGER.info("zone WF %s -> %s : %d dates ; holdout %s -> %s : %d dates",
                start_ts.date(), (hold_ts - pd.Timedelta(days=1)).date(),
                wf_zone["date"].nunique(), hold_ts.date(), end_ts.date(),
                hold_zone["date"].nunique())

    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("PHASE 0 — BASELINES PER-SECTOR (IC relatif + spread net de couts)")
    lines.append(f"univers: {args.universe} ({len(symbols)} symboles)")
    lines.append(f"zones : WF {args.start} -> {args.holdout_start} (exclu) | "
                 f"HOLDOUT {args.holdout_start} -> {args.end}")
    lines.append(f"couts : aller-retour {ROUND_TRIP_BPS:.0f} bps/jambe -> "
                 f"spread net = gross - {SPREAD_COST*10_000:.0f} bps")
    lines.append(f"seed B0 = {args.seed} | min secteur/date = {args.min_sector_size} "
                 f"| min symboles/date = {args.min_date_size}")
    lines.append("")

    for zone_name, zone_df in (("WALK-FORWARD", wf_zone), ("HOLDOUT GELE", hold_zone)):
        lines.append("=" * 100)
        lines.append(f"ZONE : {zone_name}")
        lines.append("=" * 100)
        # demi-annees
        periods = pd.period_range(zone_df["date"].min(), zone_df["date"].max(), freq="2Q")
        for per in periods:
            rows = evaluate_period(panel, per.start_time, per.end_time,
                                   score_cols, args.min_date_size)
            if not rows:
                continue
            df = pd.DataFrame(rows)
            lines.append("")
            lines.append(f"--- PERIODE {per.start_time.date()} -> {per.end_time.date()} "
                         f"(n_dates par ligne) ---")
            for h in HORIZONS:
                sub = df[df["horizon"] == h]
                if sub.empty:
                    continue
                sub = sub.drop(columns=["horizon"])
                lines.append(f"[H{h}] IC relatif (Spearman/date vs rel_return) + spread quintile")
                lines.append(_fmt_table(sub))
                lines.append("")
    lines.append("")
    lines.append("Lecture : ic_mean = IC relatif moyen | ic_ir = IC/std | "
                 "ic_pos_pct = % dates IC>0 | ic_abs_mean = IC vs rendement brut (beta) | "
                 "spread_net_bps = spread top-bottom net de 102 bps.")
    lines.append("Spread calcule sur rel_return winsorise 1%/99% intra-date ; "
                 "IC calcule sur rel_return brut (rank-based, robuste).")
    lines.append("Caveat : forward returns chevauchants entre dates adjacentes -> "
                 "ic_ir optimiste ; metriques fiables = ic_mean, ic_pos_pct, spread moyen.")
    lines.append("Un alpha exploitable exige : ic_mean > 0 de facon stable "
                 "(ic_pos_pct eleve) ET spread_net_bps > 0.")
    lines.append("Si B4_relmom20/B5_blend battent B0_random : le ML a echoue a apprendre "
                 "un signal simple -> corriger features/target avant tout nouveau modele.")

    out = "\n".join(lines)
    print(out)

    log_file = args.log_file or str(
        Path("logs") / f"per_sector_baselines_{args.start}_{args.end}.txt")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    Path(log_file).write_text(out + "\n", encoding="utf-8")
    LOGGER.info("rapport ecrit dans %s", log_file)


if __name__ == "__main__":
    main()
