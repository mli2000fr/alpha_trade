"""E2-D — Performance conditionnelle + analyse TP/FP/FN Oracle Extreme.

Jointures :
- dataset O1 (features, artifacts/models/oracle/e2_feature_dataset.parquet) ;
- parquet OOS gelé (proba_extreme, oracle_extreme10, global_rank_20) ;
- SPY bars (tendance 6m + vol réalisée 60j) pour segmenter par régime de marché ;
- stock_metadata.provider_sector (PIT via snapshot le plus récent <= date).

Axes :
1. P@10 / AUC par régime (SPY trend up/down, vol élevée/basse, secteur).
2. TP/FP/FN du TOP10 Oracle entre 2022-24 et 2025-26 : comparaison des features
   moyennes des vrais extrêmes bien classés vs confondus.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_benchmark_bars
from modelFactory.oracle.train import roc_auc

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
OUT = Path("artifacts/models/oracle/e2_conditional.md")
BATCH = "model-factory-20260811223551-ef2cd0"


def _p10(df: pd.DataFrame, score_col: str = "proba_extreme") -> float:
    precs = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=[score_col, "oracle_extreme10"])
        if len(g) < 20:
            continue
        n_top = max(1, int(np.ceil(len(g) * 0.10)))
        top = g.nlargest(n_top, score_col)
        precs.append(float(top["oracle_extreme10"].mean()))
    return float(np.mean(precs)) if precs else float("nan")


def _auc_seg(df: pd.DataFrame) -> float:
    if len(df) < 30:
        return float("nan")
    return roc_auc(df["oracle_extreme10"].to_numpy(), df["proba_extreme"].to_numpy()) or float("nan")


def _seg_report(df: pd.DataFrame) -> dict:
    return {
        "N": int(len(df)),
        "prev": df["oracle_extreme10"].mean() if len(df) else float("nan"),
        "P@10": _p10(df),
        "AUC": _auc_seg(df),
    }


def main() -> None:
    ds = pd.read_parquet(DATA)
    oos = pd.read_parquet(OOS)
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    ds["symbol"] = ds["symbol"].astype(str)
    oos["symbol"] = oos["symbol"].astype(str)

    # fusionner features + proba
    m = ds.merge(oos[["date", "symbol", "proba_extreme", "global_rank_20"]],
                 on=["date", "symbol"], how="inner")
    print(f"fusionné: {len(m):,} lignes | {m['date'].min().date()} -> {m['date'].max().date()}")
    m["period_group"] = np.where(m["date"].dt.year < 2025, "2022-24", "2025-26")

    # ── Régime SPY : tendance 6m + vol 60j ──
    engine = get_sqlalchemy_engine()
    spy = load_benchmark_bars(engine, "SPY", start_date="2021-06-01", end_date="2026-05-29")
    spy = spy.sort_values("date").reset_index(drop=True)
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
    spy["spy_ret_126"] = spy["adj_close"].pct_change(126)
    spy["spy_vol_60"] = spy["adj_close"].pct_change().rolling(60).std() * np.sqrt(252)
    spy["regime_trend"] = np.where(spy["spy_ret_126"] > 0, "trend_up", "trend_down")
    spy["regime_vol"] = np.where(spy["spy_vol_60"] > spy["spy_vol_60"].median(), "vol_high", "vol_low")
    spy = spy[["date", "spy_ret_126", "spy_vol_60", "regime_trend", "regime_vol"]].dropna()
    m = m.merge(spy, on="date", how="left")

    # ── Secteur (PIT : dernier snapshot stock_metadata <= date) ──
    with engine.connect() as c:
        meta = pd.read_sql(text(
            "SELECT symbol, provider_sector, market_cap, last_updated FROM stock_metadata "
            "WHERE provider_sector IS NOT NULL AND provider_sector != ''"
        ), c)
    meta["symbol"] = meta["symbol"].astype(str)
    meta["last_updated"] = pd.to_datetime(meta["last_updated"]).dt.normalize()
    m = m.merge(meta[["symbol", "provider_sector", "market_cap"]], on="symbol", how="left")
    m["sector"] = m["provider_sector"].fillna("Unknown")

    # ═════════ 1. P@10 / AUC par régime ═════════
    md = ["# E2-D — Performance conditionnelle Oracle Extreme", ""]
    md.append("## 1. Par régime de marché (SPY)")
    md.append("")
    md.append("| segment | N | prev% | P@10 | AUC |")
    md.append("|---|---|---|---|---|")
    for key, g in m.groupby("regime_trend"):
        r = _seg_report(g)
        md.append(f"| trend={key} | {r['N']:,} | {r['prev']*100:.1f} | {r['P@10']*100:.1f} | {r['AUC']:.3f} |")
    for key, g in m.groupby("regime_vol"):
        r = _seg_report(g)
        md.append(f"| vol={key} | {r['N']:,} | {r['prev']*100:.1f} | {r['P@10']*100:.1f} | {r['AUC']:.3f} |")

    # croisé trend x vol
    md.append("")
    md.append("| trend x vol | N | P@10 | AUC |")
    md.append("|---|---|---|---|")
    for key, g in m.groupby(["regime_trend", "regime_vol"]):
        r = _seg_report(g)
        md.append(f"| {key[0]}/{key[1]} | {r['N']:,} | {r['P@10']*100:.1f} | {r['AUC']:.3f} |")

    # ═════════ 2. P@10 par secteur (top 12) ═════════
    md.append("")
    md.append("## 2. P@10 par secteur (top 12 en N)")
    md.append("")
    md.append("| secteur | N | P@10 | AUC |")
    md.append("|---|---|---|---|")
    sec_n = m.groupby("sector").size().sort_values(ascending=False)
    for sec in sec_n.index[:12]:
        g = m[m["sector"] == sec]
        r = _seg_report(g)
        md.append(f"| {sec[:40]} | {r['N']:,} | {r['P@10']*100:.1f} | {r['AUC']:.3f} |")

    # ═════════ 3. TP/FP/FN du TOP10 Oracle, 2022-24 vs 2025-26 ═════════
    md.append("")
    md.append("## 3. TOP10 Oracle : vrais positifs / faux positifs / faux négatifs")
    md.append("")
    # reconstituer le TOP10 Oracle par date
    m["oracle_rank"] = m.groupby("date")["proba_extreme"].rank(pct=True)
    m["pred_top"] = m["oracle_rank"] >= 0.90
    m["TP"] = m["pred_top"] & (m["oracle_extreme10"] == 1)
    m["FP"] = m["pred_top"] & (m["oracle_extreme10"] == 0)
    m["FN"] = (~m["pred_top"]) & (m["oracle_extreme10"] == 1)

    md.append("| période | TP | FP | FN | prec@10 | recall@10 |")
    md.append("|---|---|---|---|---|---|")
    for pg, g in m.groupby("period_group"):
        tp = int(g["TP"].sum()); fp = int(g["FP"].sum()); fn = int(g["FN"].sum())
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn) if tp + fn else float("nan")
        md.append(f"| {pg} | {tp:,} | {fp:,} | {fn:,} | {prec*100:.1f} | {rec*100:.1f} |")

    # Features moyennes des TP vs FN (vrais extrêmes bien classés vs confondus)
    md.append("")
    md.append("## 4. Features des vrais extrêmes : TP (bien classés) vs FN (confondus)")
    md.append("")
    md.append("| feature | TP_2022-24 | FN_2022-24 | TP_2025-26 | FN_2025-26 |")
    md.append("|---|---|---|---|---|")
    feature_cols = ["market_volatility_20", "market_return_20", "market_trend_strength_50",
                    "regime_bull_market", "rolling_volatility_20", "relative_strength_20",
                    "momentum_20", "rsi_14", "range_position_20", "distance_high_20",
                    "distance_low_20", "drawdown_20", "global_rank_20", "volume_ratio_20",
                    "atr_14_norm"]
    for f in feature_cols:
        if f not in m.columns:
            continue
        cells = []
        for pg in ["2022-24", "2025-26"]:
            g = m[(m["period_group"] == pg)]
            tp = g[g["TP"]][f].median()
            fn = g[g["FN"]][f].median()
            cells.append(f"{tp:.4f}" if pd.notna(tp) else "-")
            cells.append(f"{fn:.4f}" if pd.notna(fn) else "-")
        md.append(f"| {f} | " + " | ".join(cells) + " |")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("rapport:", OUT)

    # console
    print("\n--- régime ---")
    for key, g in m.groupby("regime_trend"):
        r = _seg_report(g)
        print(f"  trend={key:<10} N={r['N']:>7,} P@10={r['P@10']*100:5.1f} AUC={r['AUC']:.3f}")
    for key, g in m.groupby("regime_vol"):
        r = _seg_report(g)
        print(f"  vol={key:<10} N={r['N']:>7,} P@10={r['P@10']*100:5.1f} AUC={r['AUC']:.3f}")
    print("\n--- TP/FP/FN ---")
    for pg, g in m.groupby("period_group"):
        tp = int(g["TP"].sum()); fp = int(g["FP"].sum()); fn = int(g["FN"].sum())
        print(f"  {pg}: TP={tp:,} FP={fp:,} FN={fn:,}")


if __name__ == "__main__":
    main()
