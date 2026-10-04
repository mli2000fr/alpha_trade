"""Read-only US 2025 ATR/Oracle overlap and strong-news association audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.extreme_gate import compute_extreme_gate

LOG = logging.getLogger(__name__)


def overlap(panel: pd.DataFrame, atr_column: str) -> tuple[pd.DataFrame, dict]:
    """Same observable intersection for both rankings; no future target used."""
    data = panel.dropna(subset=[atr_column, "proba_extreme"]).copy()
    if data.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate symbol/date")
    data = compute_extreme_gate(data)
    data["atr_top20"] = data.groupby("date")[atr_column].rank(pct=True).ge(.8)
    data["intersection"] = data.atr_top20 & data.extreme_gate
    daily = data.groupby("date").agg(
        universe=("symbol", "size"), atr_top=("atr_top20", "sum"),
        oracle_top=("extreme_gate", "sum"), shared=("intersection", "sum"))
    daily["overlap_fraction"] = daily.shared / daily.atr_top
    daily["jaccard"] = daily.shared / (daily.atr_top + daily.oracle_top - daily.shared)
    summary = {"symbol_days": len(data), "dates": len(daily),
               "atr_top_symbol_days": int(daily.atr_top.sum()),
               "oracle_top_symbol_days": int(daily.oracle_top.sum()),
               "shared_symbol_days": int(daily.shared.sum()),
               "pooled_overlap": float(daily.shared.sum() / daily.atr_top.sum()),
               "median_daily_overlap": float(daily.overlap_fraction.median()),
               "min_daily_overlap": float(daily.overlap_fraction.min()),
               "max_daily_overlap": float(daily.overlap_fraction.max()),
               "days_at_least_90pct": int(daily.overlap_fraction.ge(.9).sum())}
    return data, {"summary": summary, "daily": daily.reset_index()}


def news_windows(panel: pd.DataFrame, news: pd.DataFrame, sessions: list) -> tuple[pd.DataFrame, list[dict]]:
    """T=J+lag; positive lag is future news, never a predictive feature."""
    data = panel.copy()
    index = {pd.Timestamp(day): i for i, day in enumerate(sorted(sessions))}
    data["session"] = data.date.map(index)
    daily = news.groupby(["symbol", "date"]).agg(
        positive=("positive_score", "max"), negative=("negative_score", "max"),
        articles=("article_id", "nunique")).reset_index()
    daily["session"] = daily.date.map(index)
    rows = []
    for side in ("positive", "negative"):
        eligible = daily[daily[side].gt(.9) & daily.session.notna()]
        for lag in range(-3, 4):
            keys = set(zip(eligible.symbol, (eligible.session - lag).astype(int), strict=True))
            data[f"{side}_lag{lag}"] = [
                (symbol, int(session)) in keys for symbol, session in zip(data.symbol, data.session, strict=True)]
        for label, lags in [("before_only", range(-3, 0)), ("same_session", [0]),
                            ("before_and_same", range(-3, 1)), ("after_only", range(1, 4)),
                            ("symmetric", range(-3, 4))] + [(f"lag_{lag}", [lag]) for lag in range(-3, 4)]:
            mask = data[[f"{side}_lag{lag}" for lag in lags]].any(axis=1)
            chosen = data[mask]
            hits = int(chosen.extreme_gate.sum())
            base = float(data.extreme_gate.mean())
            row = {"side": side, "window": label, "symbol_days_with_strong_news": len(chosen),
                   "oracle_top_symbol_days_with_strong_news": hits,
                   "p_oracle_top_given_strong_news": hits / len(chosen) if len(chosen) else None,
                   "p_strong_news_given_oracle_top": hits / int(data.extreme_gate.sum()),
                   "oracle_base_rate": base,
                   "enrichment_over_base": (hits / len(chosen)) / base if len(chosen) else None,
                   "unique_symbols": int(chosen.symbol.nunique()),
                   "predictive_window": max(lags) <= 0,
                   "mean_abs_return_h20": None,
                   "positive_return_fraction_h20": None,
                   "valid_returns_h20": 0}
            if "return_h20" in chosen:
                realized = chosen.return_h20.dropna()
                row.update(mean_abs_return_h20=float(realized.abs().mean()) if len(realized) else None,
                           positive_return_fraction_h20=float(realized.gt(0).mean()) if len(realized) else None,
                           valid_returns_h20=len(realized))
            rows.append(row)
    return data, rows


def run(batch: str, universe: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)

    def progress(phase, **values):
        LOG.info("phase=%s %s", phase, values)
        (output / "progress.json").write_text(json.dumps({"phase": phase, **values}), encoding="utf-8")

    symbols = sorted({x.strip().upper() for x in universe.read_text(encoding="utf-8-sig").split(",") if x.strip()})
    root = Path("artifacts/models/oracle/champions") / batch
    profile = json.loads((root / "feature_profile.json").read_text(encoding="utf-8"))
    meta = json.loads((root / "oracle_champions.json").read_text(encoding="utf-8"))
    if profile.get("oracle_horizon") != 20:
        raise ValueError("Expected trained H20 Oracle")
    # 2025 is after every fold start of this batch. Never select a future fold.
    candidates = [m for m in meta if m["t_start"] <= "2024-12-20"]
    model_meta = max(candidates, key=lambda m: m["t_start"])
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text("SELECT DATABASE()")).scalar() != "alpha_trade":
            raise ValueError("US database alpha_trade required")
        # Shared feature loader currently does not select between sources.
        query = text("SELECT symbol,date FROM stock_bars_daily WHERE symbol IN :syms "
                     "AND date BETWEEN '2021-12-01' AND '2026-02-15' "
                     "GROUP BY symbol,date HAVING COUNT(*)>1 LIMIT 1").bindparams(bindparam("syms", expanding=True))
        if conn.execute(query, {"syms": symbols}).first():
            raise ValueError("Multiple bar sources per symbol/date: canonical source must be resolved first")
    progress("FEATURES", requested_symbols=len(symbols))
    frame = build_feature_matrix(engine, symbols, start_date="2024-12-20", end_date="2026-02-15",
                                 generator_options=profile["generator_options"])
    if frame.empty or frame.duplicated(["symbol", "date"]).any():
        raise ValueError("Empty or duplicate feature panel")
    frame["date"] = pd.to_datetime(frame.date).dt.normalize()
    frame = frame.sort_values(["symbol", "date"])
    sessions = sorted(frame.loc[frame.date.between("2024-12-20", "2026-01-15"), "date"].unique())
    # Ex-post price response only, never entered into Oracle or the top gate.
    frame["return_h20"] = frame.groupby("symbol").adj_close.shift(-20) / frame.adj_close - 1
    price_endpoint = frame.groupby("symbol").date.shift(-20)
    # Reject paths with missing market sessions (20 bars need not be 20 sessions).
    all_sessions = {date: i for i, date in enumerate(sorted(frame.date.unique()))}
    contiguous = price_endpoint.map(all_sessions) - frame.date.map(all_sessions)
    frame.loc[contiguous.ne(20), "return_h20"] = np.nan
    chosen = frame[frame.date.between("2025-01-01", "2025-12-31")].copy()
    features = model_meta["feature_columns"]
    if set(features) - set(chosen.columns):
        raise ValueError("Missing trained features")
    progress("ORACLE_INFERENCE", rows=len(chosen), fold=model_meta["t_start"])
    model = lgb.Booster(model_file=str(root / model_meta["model_file"]))
    chosen["proba_extreme"] = model.predict(chosen[features].astype(float), num_threads=4)
    panel = chosen[["date", "symbol", "proba_extreme", "atr_14_norm", "atr20_pct", "return_h20"]]
    panel.to_parquet(output / "oracle_atr_panel.parquet", index=False)
    progress("NEWS_LOAD", rows=len(panel))
    query = text("""SELECT nts.article_id,nts.symbol,nr.effective_trade_date AS date,
        nts.positive_score,nts.negative_score,nr.published_at_utc,nts.created_at AS scored_at
        FROM news_ticker_sentiment nts JOIN news_raw nr ON nr.article_id=nts.article_id
        WHERE nts.symbol IN :syms AND nr.effective_trade_date BETWEEN '2024-12-20' AND '2026-01-15'
        AND nts.inference_status='success'""").bindparams(bindparam("syms", expanding=True))
    parts = []
    with engine.connect() as conn:
        for offset in range(0, len(symbols), 400):
            parts.append(pd.read_sql(query, conn, params={"syms": symbols[offset:offset+400]}))
    news = pd.concat(parts, ignore_index=True)
    news["date"] = pd.to_datetime(news.date).dt.normalize()
    news.to_parquet(output / "news_observations.parquet", index=False)
    progress("ANALYSIS", news_rows=len(news))
    comparisons = {}
    for atr in ("atr_14_norm", "atr20_pct"):
        gated, result = overlap(panel, atr)
        result["daily"].to_parquet(output / f"overlap_{atr}.parquet", index=False)
        comparisons[atr] = result["summary"]
    enriched, associations = news_windows(gated, news, sessions)
    enriched.to_parquet(output / "symbol_day_windows.parquet", index=False)
    years = news[news.date.dt.year.eq(2025)]
    report = {"status": "COMPLETED_DESCRIPTIVE_NOT_CAUSAL", "year": 2025, "oracle_horizon": 20,
              "batch_id": batch, "universe_path": str(universe),
              "universe_sha256": hashlib.sha256(universe.read_bytes()).hexdigest(),
              "requested_symbols": len(symbols), "predicted_symbols": int(panel.symbol.nunique()),
              "model_fold_used": model_meta["t_start"],
              "model_sha256": hashlib.sha256((root / model_meta["model_file"]).read_bytes()).hexdigest(),
              "atr_overlap": comparisons, "sentiment_associations": associations,
              "news_2025_rows": len(years), "news_2025_symbols": int(years.symbol.nunique()),
              "news_2025_strong_positive_rows": int(years.positive_score.gt(.9).sum()),
              "news_2025_strong_negative_rows": int(years.negative_score.gt(.9).sum()),
              "scored_after_2025_rows": int(pd.to_datetime(years.scored_at).gt("2025-12-31 23:59:59").sum()),
              "notes": ["J +/- 3 means effective US trading sessions, not calendar days",
                        "Both rankings recalculated on the common observed universe; average-rank ties >=80th percentile",
                        "News maximum per symbol/session >0.9, article duplicates do not weight symbol-days",
                        "Future news lags are retrospective association, not a tradable predictor",
                        "Missing news is not proof of no news; no-news symbol-days remain in base rate",
                        "Sentiment confidence is not probability of future price increase/decrease",
                        "Current static universe creates historical selection bias",
                        "Historical scoring/ingestion PIT is not certified; created_at is exported",
                        "H20 price response is adjusted close-to-close, no fees/exits/portfolio"],
              "sql_writes": False, "models_retrained": False}
    (output / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    progress("COMPLETED")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--universe", type=Path, default=Path("config/univers/univers_filtred_tradable.txt"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        result = run(args.batch_id, args.universe, args.output)
        print(json.dumps(result, default=str))
    except Exception as exc:
        if args.output.exists():
            (args.output / "failure.json").write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
        raise
