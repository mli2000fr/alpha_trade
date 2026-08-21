# -*- coding: utf-8 -*-
"""Validation shadow d'un modèle candidat vs le champion (B25).

Compare deux batches de rangs/prédictions SANS toucher au stack de production
(P14/m8 restent gelés). Réponse à la question :
  "Le refit produit-il un comportement raisonnable et cohérent avec B25,
   sans dégradation évidente du signal ?"

Usage:
  python -m scripts.shadow_model_validation \
      --ref model-factory-20260811223551-ef2cd0 \
      --cand model-factory-20260813231851-bb2e76 \
      --start 2026-01-02 --end 2026-07-10

Indicateurs calculés (par date puis moyennés) :
  - corrélation Spearman des global_rank_20 (ref vs cand), par date
  - turnover du TOP 10% (fraction de l'univers où le top10% diffère)
  - % de titres "nouveaux" dans le top10% candidat absents du top10% ref
  - corrélation des probas per-symbol (proba_long / flat / short)
  - IC (Spearman rank vs fwd20) du candidat — et delta vs ref
  - équilibre LONG/SHORT (top/bottom) & distribution des probas
  - divergences importantes : symboles où ref et cand sont opposés
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

LOGGER = logging.getLogger("shadow_model_validation")

DB_URL = "mysql+pymysql://root:root@localhost/alpha_trade"


def _connect():
    return create_engine(DB_URL, future=True)


def _load_ranks(eng, batch_id: str, start: date, end: date) -> pd.DataFrame:
    q = text(
        """
        SELECT date, symbol, global_rank_20, global_rank_10, global_rank_5
        FROM global_rank_history
        WHERE batch_id = :b AND date BETWEEN :s AND :e
        """
    )
    df = pd.read_sql(q, eng, params={"b": batch_id, "s": start, "e": end})
    return df


def _load_predictions(eng, batch_id: str, start: date, end: date) -> pd.DataFrame:
    q = text(
        """
        SELECT prediction_date, symbol, predicted_proba, proba_long, proba_flat, proba_short
        FROM model_predictions
        WHERE run_id = :r AND prediction_date BETWEEN :s AND :e
        """
    )
    df = pd.read_sql(q, eng, params={"r": f"{batch_id}_globalrank_synth", "s": start, "e": end})
    return df


def _load_forward_returns(eng, start: date, end: date, horizon: int = 20) -> pd.DataFrame:
    """Rendement forward (horizon séances) depuis stock_bars_daily (eodhd_eod).

    Pour chaque (date, symbol), calcule le rendement à `horizon` séances
    (dernier adj_close disponible dans la fenêtre suivante).
    """
    q = text(
        """
        SELECT date, symbol, adj_close
        FROM stock_bars_daily
        WHERE data_source = 'eodhd_eod' AND date BETWEEN :s AND :e
        """
    )
    df = pd.read_sql(q, eng, params={"s": start, "e": end})
    if df.empty:
        return df
    df = df.sort_values(["symbol", "date"])
    fr = []
    for sym, g in df.groupby("symbol"):
        g = g.reset_index(drop=True)
        fwd = g["adj_close"].shift(-horizon)
        fr.append(pd.DataFrame({"date": g["date"], "symbol": sym, "fwd_ret": fwd / g["adj_close"] - 1.0}))
    out = pd.concat(fr, ignore_index=True)
    return out.dropna(subset=["fwd_ret"])


def _compute_ic(ranks: pd.DataFrame, fwd: pd.DataFrame, rank_col: str = "global_rank_20") -> float | None:
    """IC moyen (Spearman rank vs fwd_ret) par date, pondéré équitablement."""
    m = pd.merge(ranks, fwd, on=["date", "symbol"])
    ics = []
    for _, g in m.groupby("date"):
        if g[rank_col].nunique() > 2 and g["fwd_ret"].nunique() > 2:
            ic = g[rank_col].corr(g["fwd_ret"], method="spearman")
            if pd.notna(ic):
                ics.append(ic)
    return float(np.mean(ics)) if ics else None


@dataclass
class ShadowModelReport:
    ref_batch: str
    cand_batch: str
    start: str
    end: str
    n_dates: int
    n_symbols_total: int
    rank_corr_median: float | None
    rank_corr_mean: float | None
    top10_turnover_mean: float | None
    top10_new_symbols_mean: float | None
    proba_corr_long: float | None
    proba_corr_short: float | None
    ic_ref: float | None
    ic_cand: float | None
    ic_delta: float | None
    long_count_ref: int | None
    long_count_cand: int | None
    short_count_ref: int | None
    short_count_cand: int | None
    proba_long_mean_ref: float | None
    proba_long_mean_cand: float | None
    n_opposed: int
    opposed_symbols: list[dict]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def validate_shadow(ref_batch: str, cand_batch: str, start: date, end: date) -> ShadowModelReport:
    eng = _connect()
    with eng.connect():
        ref_r = _load_ranks(eng, ref_batch, start, end)
        cand_r = _load_ranks(eng, cand_batch, start, end)
        ref_p = _load_predictions(eng, ref_batch, start, end)
        cand_p = _load_predictions(eng, cand_batch, start, end)
        # fenêtre forward étendue de `horizon` séances pour capturer le fwd_ret
        fwd = _load_forward_returns(eng, start, date.fromordinal(end.toordinal() + 40), horizon=20)

    warnings: list[str] = []

    # ---- Corrélation des rangs (par date) ----
    m = pd.merge(ref_r, cand_r, on=["date", "symbol"], suffixes=("_ref", "_cand"))
    rank_corrs = []
    if len(m):
        for d, g in m.groupby("date"):
            if g["global_rank_20_ref"].nunique() > 2 and g["global_rank_20_cand"].nunique() > 2:
                c = g["global_rank_20_ref"].corr(g["global_rank_20_cand"], method="spearman")
                if pd.notna(c):
                    rank_corrs.append(c)
    rank_corr_median = float(np.median(rank_corrs)) if rank_corrs else None
    rank_corr_mean = float(np.mean(rank_corrs)) if rank_corrs else None

    # ---- Turnover TOP 10% + nouveaux titres ----
    top10_turn, top10_new = [], []
    for d, g in m.groupby("date"):
        if g["global_rank_20_ref"].nunique() < 10:
            continue
        top_ref = set(g.loc[g["global_rank_20_ref"] >= 0.90, "symbol"])
        top_cand = set(g.loc[g["global_rank_20_cand"] >= 0.90, "symbol"])
        if top_ref and top_cand:
            top10_turn.append(len(top_ref ^ top_cand) / len(top_ref | top_cand))
            top10_new.append(len(top_cand - top_ref) / len(top_cand))
    top10_turnover_mean = float(np.mean(top10_turn)) if top10_turn else None
    top10_new_mean = float(np.mean(top10_new)) if top10_new else None

    # ---- Corrélation des probas ----
    pm = pd.merge(ref_p, cand_p, on=["prediction_date", "symbol"], suffixes=("_ref", "_cand"))
    proba_corr_long = None
    proba_corr_short = None
    if len(pm):
        pl = pm[["proba_long_ref", "proba_long_cand"]].dropna()
        ps = pm[["proba_short_ref", "proba_short_cand"]].dropna()
        if len(pl) > 10:
            proba_corr_long = float(pl["proba_long_ref"].corr(pl["proba_long_cand"]))
        if len(ps) > 10:
            proba_corr_short = float(ps["proba_short_ref"].corr(ps["proba_short_cand"]))

    # ---- IC réel (rank vs fwd_ret) ref vs cand ----
    ic_ref = _compute_ic(ref_r, fwd)
    ic_cand = _compute_ic(cand_r, fwd)
    ic_delta = (ic_cand - ic_ref) if (ic_ref is not None and ic_cand is not None) else None

    # ---- Équilibre LONG/SHORT (top/bottom 10%) ----
    def _side_counts(df: pd.DataFrame) -> tuple[int, int]:
        long_n = short_n = 0
        for _, g in df.groupby("date"):
            if g["global_rank_20"].nunique() < 10:
                continue
            long_n += int((g["global_rank_20"] >= 0.90).sum())
            short_n += int((g["global_rank_20"] <= 0.10).sum())
        return long_n, short_n

    lr, sr = _side_counts(ref_r)
    lc, sc = _side_counts(cand_r)

    proba_long_mean_ref = float(ref_p["proba_long"].mean()) if len(ref_p) else None
    proba_long_mean_cand = float(cand_p["proba_long"].mean()) if len(cand_p) else None

    # ---- Divergences importantes (rank opposé : ref top10% / cand bottom10% ou inverse) ----
    opposed = []
    if len(m):
        for _, row in m.iterrows():
            r, c = row["global_rank_20_ref"], row["global_rank_20_cand"]
            if (r >= 0.90 and c <= 0.10) or (r <= 0.10 and c >= 0.90):
                opposed.append(
                    {
                        "date": str(row["date"])[:10],
                        "symbol": row["symbol"],
                        "rank_ref": round(float(r), 3),
                        "rank_cand": round(float(c), 3),
                    }
                )
        opposed = opposed[:50]

    if rank_corr_median is not None and rank_corr_median < 0.7:
        warnings.append(
            f"Corrélation médiane des rangs {rank_corr_median:.3f} < 0.70 : divergence structurelle majeure ref/cand"
        )
    if top10_turnover_mean is not None and top10_turnover_mean > 0.6:
        warnings.append(
            f"Turnover TOP10% {top10_turnover_mean:.2f} > 0.60 : le candidat chamboule fortement la sélection"
        )
    if len(opposed) >= 100:
        warnings.append(f"{len(opposed)} divergences opposées ref/cand : signal inversé possible")
    if ic_ref is not None and ic_cand is not None and ic_cand < ic_ref - 0.02:
        warnings.append(
            f"IC candidat {ic_cand:.3f} < IC ref {ic_ref:.3f} (delta {ic_delta:.3f} < -0.02) : dégradation du signal"
        )

    return ShadowModelReport(
        ref_batch=ref_batch,
        cand_batch=cand_batch,
        start=str(start),
        end=str(end),
        n_dates=int(m["date"].nunique()) if len(m) else 0,
        n_symbols_total=int(m["symbol"].nunique()) if len(m) else 0,
        rank_corr_median=rank_corr_median,
        rank_corr_mean=rank_corr_mean,
        top10_turnover_mean=top10_turnover_mean,
        top10_new_symbols_mean=top10_new_mean,
        proba_corr_long=proba_corr_long,
        proba_corr_short=proba_corr_short,
        ic_ref=ic_ref,
        ic_cand=ic_cand,
        ic_delta=ic_delta,
        long_count_ref=lr,
        long_count_cand=lc,
        short_count_ref=sr,
        short_count_cand=sc,
        proba_long_mean_ref=proba_long_mean_ref,
        proba_long_mean_cand=proba_long_mean_cand,
        n_opposed=len(opposed),
        opposed_symbols=opposed,
        warnings=warnings,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validation shadow d'un modèle candidat vs B25")
    ap.add_argument("--ref", required=True, help="batch_id de référence (champion B25)")
    ap.add_argument("--cand", required=True, help="batch_id candidat (ex: B25-future)")
    ap.add_argument("--start", default="2026-01-02")
    ap.add_argument("--end", default="2026-07-10")
    ap.add_argument("--out", default=None, help="chemin JSON du rapport")
    args = ap.parse_args(argv)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    report = validate_shadow(args.ref, args.cand, start, end)

    print("=" * 78)
    print(f"SHADOW MODEL VALIDATION — ref={args.ref}")
    print(f"cand={args.cand}  |  {args.start} → {args.end}")
    print("=" * 78)
    data = report.to_dict()
    for k in [
        "n_dates",
        "n_symbols_total",
        "rank_corr_median",
        "rank_corr_mean",
        "top10_turnover_mean",
        "top10_new_symbols_mean",
        "proba_corr_long",
        "proba_corr_short",
        "long_count_ref",
        "long_count_cand",
        "short_count_ref",
        "short_count_cand",
        "proba_long_mean_ref",
        "proba_long_mean_cand",
        "n_opposed",
    ]:
        print(f"  {k:<22}: {data.get(k)}")
    print("-" * 78)
    if report.warnings:
        print("  ⚠️ WARNINGS:")
        for w in report.warnings:
            print(f"     - {w}")
    else:
        print("  ✅ Aucun warning : candidat cohérent avec le champion")
    if report.opposed_symbols:
        print("  Exemples de divergences opposées (top10%<->bottom10%):")
        for o in report.opposed_symbols[:10]:
            print(f"     {o['date']} {o['symbol']:6s} ref={o['rank_ref']} cand={o['rank_cand']}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        report.to_json(out)
        print(f"\n  Rapport écrit: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
