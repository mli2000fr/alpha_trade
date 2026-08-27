"""Chantier diagnostic — dip_context_pattern_analysis (2026-08-27).

Objectif : identifier, au moment du signal DIP N4/X2 (date J), quelles features
PIT différencient les bons DIP (rebond) des mauvais DIP (poursuite de baisse).

Périmètre STRICT :
- Setup N4/X2 gelé : global_rank_20 >= 0.90 pendant 4 séances consécutives
  ET ret_4 <= -2%. Aucun tuning de N/X. Aucun modèle ML. Aucun changement
  risk/PROD.
- Batch Global Rank explicite : model-factory-20260811223551-ef2cd0.
- Toutes les features PIT à J (aucun leakage futur).

Usage (étapes, pour robustesse) :
    python -m modelFactory.dip_research.dip_context_pattern_analysis --stage events
    python -m modelFactory.dip_research.dip_context_pattern_analysis --stage features
    python -m modelFactory.dip_research.dip_context_pattern_analysis --stage analyses
    python -m modelFactory.dip_research.dip_context_pattern_analysis --stage report
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "dip_context"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

LOGGER = logging.getLogger(__name__)

# ── Setup gelé ──
BATCH_ID = "model-factory-20260811223551-ef2cd0"
RANK_COL = "global_rank_20"
TOP10 = 0.90
N_DIP = 4
X_DIP = 0.02
HORIZON = 20
START = "2022-01-01"
END = "2025-12-31"

# Plage de bars nécessaire : J-4 (ret_4) et J+H (forward) autour de la période.
_BARS_START = "2021-10-01"
_BARS_END = "2026-03-01"


def _quiet() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _plog(msg: str) -> None:
    """Journalise dans un fichier utf-8 (fiable même si stdout est redirigé)."""
    with open(ARTIFACTS_DIR / "run.log", "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
    print(msg, flush=True)


def build_dip_events(engine: Any) -> pd.DataFrame:
    """Construit les événements DIP N4/X2 (signal_date J, symbol) + labels.

    Assertions :
    - unique(signal_date, symbol)
    - un seul batch
    - aucun duplicate multi-batch
    """
    rank = pd.read_sql(
        f"SELECT symbol, date, {RANK_COL} FROM global_rank_history "
        "WHERE batch_id=%s AND date BETWEEN %s AND %s",
        engine, params=(BATCH_ID, START, END),
    )
    rank["date"] = pd.to_datetime(rank["date"]).dt.normalize()
    rank["symbol"] = rank["symbol"].astype(str).str.upper()

    bars = pd.read_sql(
        "SELECT symbol, date, adj_close FROM stock_bars_daily "
        "WHERE data_source='eodhd_eod' AND date BETWEEN %s AND %s",
        engine, params=(_BARS_START, _BARS_END),
    )
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "adj_close"])
    bars = bars.drop_duplicates(subset=["symbol", "date"])

    df = rank.merge(bars[["symbol", "date", "adj_close"]], on=["date", "symbol"], how="inner")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    g = df.groupby("symbol")
    df["top10"] = (df[RANK_COL] >= TOP10).astype(int)
    df["ret_4"] = df["adj_close"] / g["adj_close"].shift(N_DIP) - 1.0
    df["persist_4"] = g["top10"].transform(
        lambda x: x.rolling(N_DIP, min_periods=N_DIP).min()
    )
    # Forward H20 (label) — calcul direct bars (PIT label, pas une feature).
    df["future_return_H20"] = g["adj_close"].shift(-HORIZON) / df["adj_close"] - 1.0

    events = df[(df["persist_4"] == 1) & (df["ret_4"] <= -X_DIP)].copy()
    events = events.rename(columns={"date": "signal_date"})
    events = events[["signal_date", "symbol", RANK_COL, "ret_4", "future_return_H20"]].copy()
    events["batch_id"] = BATCH_ID

    # ── Labels oracle (decile cross-sectionnel du pool, PIT) ──
    labels = pd.read_sql(
        "SELECT prediction_date, symbol, future_return, oracle_decile "
        "FROM global_oracle_labels WHERE batch_id=%s AND horizon=%s",
        engine, params=(BATCH_ID, HORIZON),
    )
    labels["prediction_date"] = pd.to_datetime(labels["prediction_date"]).dt.normalize()
    labels["symbol"] = labels["symbol"].astype(str).str.upper()
    labels = labels.rename(columns={"prediction_date": "signal_date", "future_return": "future_return_oracle"})
    events = events.merge(labels, on=["signal_date", "symbol"], how="left")

    return events


def assert_events(events: pd.DataFrame) -> None:
    n0 = len(events)
    # 1) unique(signal_date, symbol)
    dup = events.duplicated(subset=["signal_date", "symbol"]).sum()
    assert dup == 0, f"duplicats (signal_date,symbol): {dup}"
    # 2) un seul batch
    batches = events["batch_id"].unique().tolist()
    assert len(batches) == 1 and batches[0] == BATCH_ID, f"batchs multiples: {batches}"
    # 3) forward non nul (label dispo)
    n_fwd = int(events["future_return_H20"].notna().sum())
    print(f"assertions OK : n={n0} | uniques={events[['signal_date','symbol']].drop_duplicates().shape[0]} "
          f"| batch={batches} | fwd H20 dispo={n_fwd} ({n_fwd/n0:.1%})")
    # par année
    ev = events.copy()
    ev["year"] = ev["signal_date"].dt.year
    print("événements par année:")
    print(ev.groupby("year").size().to_string())


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2 — Feature engineering (PIT à J)
# ═══════════════════════════════════════════════════════════════════════════

# Inventaire des features : (feature, family, source)
FEATURE_META: list[dict[str, str]] = []


def _reg(feature: str, family: str, source: str) -> None:
    FEATURE_META.append({"feature_name": feature, "family": family, "source": source})


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _compute_bars_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Features par symbole depuis stock_bars_daily (PIT, fenêtres ≤ J)."""
    bars = bars.sort_values(["symbol", "date"]).reset_index(drop=True)
    df = bars.copy()
    df["ret1"] = df["adj_close"] / df.groupby("symbol", sort=False)["adj_close"].shift(1) - 1
    g = df.groupby("symbol", sort=False)
    for w in (5, 10, 20, 60):
        df[f"ret{w}"] = df["adj_close"] / g["adj_close"].shift(w) - 1
    # ATR14 (moyenne simple du True Range sur 14)
    prev_close = g["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    df["atr14"] = tr.groupby(df["symbol"].values).transform(
        lambda x: x.rolling(14, min_periods=14).mean()
    )
    df["atr14_pct"] = df["atr14"] / df["close"]
    for w in (10, 20, 60):
        df[f"rvol{w}"] = g["ret1"].transform(lambda x: x.rolling(w, min_periods=w).std())
    df["vol_ratio_10_60"] = df["rvol10"] / df["rvol60"]
    df["atr_expand_5"] = df["atr14"] / g["atr14"].shift(5) - 1
    df["rvol_expand_5"] = df["rvol10"] / g["rvol10"].shift(5) - 1
    # SMAs / distance
    for w in (20, 50, 100, 200):
        df[f"sma{w}"] = g["close"].transform(lambda x: x.rolling(w, min_periods=w).mean())
        df[f"dist_sma{w}"] = df["close"] / df[f"sma{w}"] - 1
    df["sma50_slope_5"] = df["sma50"] / g["sma50"].shift(5) - 1
    df["sma200_slope_5"] = df["sma200"] / g["sma200"].shift(5) - 1
    # EMA / MACD normalisé
    df["ema12"] = g["close"].transform(lambda x: _ema(x, 12))
    df["ema26"] = g["close"].transform(lambda x: _ema(x, 26))
    df["macd_norm"] = df["ema12"] / df["ema26"] - 1
    df["dist_ema20"] = df["close"] / g["close"].transform(lambda x: _ema(x, 20)) - 1
    # Volume / liquidité
    v_mean20 = g["volume"].transform(lambda x: x.rolling(20, min_periods=20).mean())
    v_std20 = g["volume"].transform(lambda x: x.rolling(20, min_periods=20).std())
    df["vol_z20"] = (df["volume"] - v_mean20) / v_std20
    v_mean5 = g["volume"].transform(lambda x: x.rolling(5, min_periods=5).mean())
    df["vol_ratio_1_5"] = df["volume"] / v_mean5 - 1
    df["vol_ratio_5_20"] = v_mean5 / v_mean20 - 1
    df["dollar_vol_20"] = (df["volume"] * df["close"]).groupby(df["symbol"].values).transform(
        lambda x: x.rolling(20, min_periods=20).mean()
    )
    # Support / range
    for w in (20, 60):
        hi = g["high"].transform(lambda x: x.rolling(w, min_periods=w).max())
        lo = g["low"].transform(lambda x: x.rolling(w, min_periods=w).min())
        df[f"pos_{w}"] = (df["close"] - lo) / (hi - lo)
        df[f"range_{w}_pct"] = (hi - lo) / lo
    hi252 = g["high"].transform(lambda x: x.rolling(252, min_periods=252).max())
    lo252 = g["low"].transform(lambda x: x.rolling(252, min_periods=252).min())
    df["pos_52w"] = (df["close"] - lo252) / (hi252 - lo252)
    df["dist_52w_high"] = df["close"] / hi252 - 1
    df["dist_52w_low"] = df["close"] / lo252 - 1
    return df


def _compute_beta126(dip_bars: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    """Beta PIT vs SPY : 126j (cov/var) et 20j."""
    spy_r = spy.rename(columns={"ret1": "spy_ret1"})[["date", "spy_ret1"]]
    spy_r = spy_r.sort_values("date").reset_index(drop=True)
    spy_var126 = (
        spy_r.set_index("date")["spy_ret1"].pow(2).rolling(126, min_periods=126).mean()
        - spy_r.set_index("date")["spy_ret1"].rolling(126, min_periods=126).mean().pow(2)
    )
    spy_var20 = (
        spy_r.set_index("date")["spy_ret1"].pow(2).rolling(20, min_periods=20).mean()
        - spy_r.set_index("date")["spy_ret1"].rolling(20, min_periods=20).mean().pow(2)
    )
    m = dip_bars[["symbol", "date", "ret1"]].merge(spy_r, on="date", how="left")
    m = m.sort_values(["symbol", "date"]).reset_index(drop=True)
    g = m.groupby("symbol", sort=False)
    m["e_rs"] = (m["ret1"] * m["spy_ret1"]).groupby(m["symbol"].values).transform(
        lambda x: x.rolling(126, min_periods=126).mean()
    )
    m["e_r"] = m["ret1"].groupby(m["symbol"].values).transform(
        lambda x: x.rolling(126, min_periods=126).mean()
    )
    m["e_s"] = m["spy_ret1"].groupby(m["symbol"].values).transform(
        lambda x: x.rolling(126, min_periods=126).mean()
    )
    m["cov126"] = m["e_rs"] - m["e_r"] * m["e_s"]
    m["spy_var126"] = m["date"].map(spy_var126)
    m["beta126"] = m["cov126"] / m["spy_var126"]
    # beta20
    m["e_rs20"] = (m["ret1"] * m["spy_ret1"]).groupby(m["symbol"].values).transform(
        lambda x: x.rolling(20, min_periods=20).mean()
    )
    m["e_r20"] = m["ret1"].groupby(m["symbol"].values).transform(
        lambda x: x.rolling(20, min_periods=20).mean()
    )
    m["e_s20"] = m["spy_ret1"].groupby(m["symbol"].values).transform(
        lambda x: x.rolling(20, min_periods=20).mean()
    )
    m["spy_var20"] = m["date"].map(spy_var20)
    m["beta20"] = (m["e_rs20"] - m["e_r20"] * m["e_s20"]) / m["spy_var20"]
    return m[["symbol", "date", "beta126", "beta20"]]


def _compute_market_features(engine: Any) -> pd.DataFrame:
    """Contexte marché : SPY (bars) + VIX/yield/régime (macro, PIT asof)."""
    spy = pd.read_sql(
        "SELECT date, close, adj_close, volume FROM stock_bars_daily "
        "WHERE symbol='SPY' AND data_source='eodhd_eod' AND date BETWEEN %s AND %s",
        engine, params=(_BARS_START, _BARS_END),
    )
    spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
    spy = spy.sort_values("date").reset_index(drop=True)
    spy["ret1"] = spy["adj_close"].pct_change()
    for w in (5, 20, 60):
        spy[f"spy_ret{w}"] = spy["adj_close"] / spy["adj_close"].shift(w) - 1
    for w in (50, 200):
        spy[f"spy_sma{w}"] = spy["close"].rolling(w, min_periods=w).mean()
        spy[f"spy_dist_sma{w}"] = spy["close"] / spy[f"spy_sma{w}"] - 1
    spy["spy_sma50_slope_5"] = spy["spy_sma50"] / spy["spy_sma50"].shift(5) - 1
    spy_out = spy[["date", "spy_ret5", "spy_ret20", "spy_ret60",
                   "spy_dist_sma50", "spy_dist_sma200", "spy_sma50_slope_5"]].copy()

    macro = pd.read_sql(
        "SELECT trade_date, vix, vix9d, vix3m, vxn, rvx, move, ten_y, yield_10y_5d_pct, "
        "mode, risk_multiplier, vix_curve_inverted FROM stock_macro_indicators_daily "
        "WHERE trade_date BETWEEN %s AND %s",
        engine, params=(START, _BARS_END),
    )
    macro["trade_date"] = pd.to_datetime(macro["trade_date"]).dt.normalize()
    macro = macro.sort_values("trade_date").reset_index(drop=True)
    macro["vix_chg5"] = macro["vix"] / macro["vix"].shift(5) - 1
    macro["vix_ratio_9_3m"] = macro["vix9d"] / macro["vix3m"] - 1
    macro = macro.rename(columns={
        "trade_date": "date", "vix": "vix", "vix9d": "vix9d", "vix3m": "vix3m",
        "vxn": "vxn", "rvx": "rvx", "move": "move", "ten_y": "ten_y",
        "yield_10y_5d_pct": "yield_10y_5d_pct", "mode": "regime_mode",
        "risk_multiplier": "risk_multiplier", "vix_curve_inverted": "vix_curve_inverted",
    })
    mkt = spy_out.merge(macro, on="date", how="outer").sort_values("date")
    return mkt


def _load_universe_bars(engine: Any, top_n: int = 3000, bars_start: str = _BARS_START, bars_end: str = _BARS_END) -> pd.DataFrame:
    """Univers pour breadth/ranks : top-N par market_cap (≈ univers liquide)."""
    meta = pd.read_sql(
        "SELECT symbol, market_cap FROM stock_metadata WHERE market_cap IS NOT NULL", engine
    )
    meta["symbol"] = meta["symbol"].astype(str).str.upper()
    meta = meta.dropna(subset=["market_cap"]).sort_values("market_cap", ascending=False)
    top = meta.head(top_n)["symbol"].tolist()
    _in = ",".join(["%s"] * len(top))
    _params = list(top) + [bars_start, bars_end]
    bars = pd.read_sql(
        f"SELECT symbol, date, close, adj_close, volume FROM stock_bars_daily "
        f"WHERE data_source='eodhd_eod' AND symbol IN ({_in}) AND date BETWEEN %s AND %s",
        engine, params=tuple(_params),
    )
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars[bars["symbol"].isin(top)]
    bars = bars.dropna(subset=["date", "symbol", "adj_close"]).drop_duplicates(subset=["symbol", "date"])
    return bars.sort_values(["symbol", "date"]).reset_index(drop=True)


def _compute_breadth_ranks(engine: Any, top_n: int = 3000, bars_start: str = _BARS_START, bars_end: str = _BARS_END):
    """Breadth (par date) + rangs cross-sectionnels (ret20, rvol20, atr, trend)."""
    uni = _load_universe_bars(engine, top_n, bars_start, bars_end)
    g = uni.groupby("symbol", sort=False)
    uni["ret1"] = uni["adj_close"] / g["adj_close"].shift(1) - 1
    uni["ret20"] = uni["adj_close"] / g["adj_close"].shift(20) - 1
    uni["rvol20"] = g["ret1"].transform(lambda x: x.rolling(20, min_periods=20).std())
    uni["sma50"] = g["close"].transform(lambda x: x.rolling(50, min_periods=50).mean())
    uni["sma200"] = g["close"].transform(lambda x: x.rolling(200, min_periods=200).mean())
    uni["above_sma50"] = (uni["close"] > uni["sma50"]).astype(float)
    uni["above_sma200"] = (uni["close"] > uni["sma200"]).astype(float)
    uni["trend_dist"] = uni["close"] / uni["sma50"] - 1
    uni["ret1_pos"] = (uni["ret1"] > 0).astype(float)
    uni["ret20_pos"] = (uni["ret20"] > 0).astype(float)

    # Breadth quotidienne (moyennes cross-sectionnelles)
    broad_cols = ["above_sma50", "above_sma200", "ret1_pos", "ret20_pos"]
    breadth = uni.groupby("date")[broad_cols].mean().add_prefix("breadth_")
    breadth["breadth_rvol_hi"] = uni.groupby("date")["rvol20"].apply(
        lambda x: (x > x.median()).mean()
    )
    breadth = breadth.reset_index()

    # Rangs cross-sectionnels (percentile dans l'univers, par date) pour DIP
    rank_feats = {"ret20": "mom20_xs", "rvol20": "rvol20_xs", "trend_dist": "trend_xs"}
    rank_tables = {}
    for src, name in rank_feats.items():
        rt = uni[["date", "symbol", src]].dropna(subset=[src]).copy()
        rt[name] = rt.groupby("date")[src].rank(pct=True)
        rank_tables[name] = rt[["date", "symbol", name]]
    return breadth, rank_tables, uni


def _compute_sector_features(engine: Any, uni: pd.DataFrame):
    """Mapping secteur + returns sectoriels égaux-pondérés + stock_vs_sector + breadth."""
    meta = pd.read_sql(
        "SELECT symbol, provider_sector, sector FROM stock_metadata", engine
    )
    meta["symbol"] = meta["symbol"].astype(str).str.upper()
    meta["sector_name"] = meta["provider_sector"].fillna(meta["sector"])
    meta = meta.dropna(subset=["sector_name"])[["symbol", "sector_name"]]
    meta = meta.drop_duplicates(subset=["symbol"])

    u = uni[["date", "symbol", "ret1", "ret20", "above_sma50"]].merge(meta, on="symbol", how="left")
    u = u.dropna(subset=["sector_name"])
    sec = u.groupby(["date", "sector_name"])[["ret1", "ret20", "above_sma50"]].mean().reset_index()
    sec = sec.rename(columns={"ret1": "sector_ret1", "ret20": "sector_ret20",
                              "above_sma50": "sector_breadth"})
    sec["sector_rank_ret20"] = sec.groupby("date")["sector_ret20"].rank(pct=True)

    svs = uni[["date", "symbol", "ret20"]].merge(meta, on="symbol", how="left")
    svs = svs.merge(sec[["date", "sector_name", "sector_ret20", "sector_rank_ret20"]],
                    on=["date", "sector_name"], how="left")
    svs["stock_vs_sector_ret20"] = svs["ret20"] - svs["sector_ret20"]
    svs = svs[["date", "symbol", "stock_vs_sector_ret20", "sector_rank_ret20"]]
    return meta, sec, svs


def build_features(engine: Any, events: pd.DataFrame, *, smoke: bool = False) -> pd.DataFrame:
    """Construit le panneau de features PIT aligné sur (signal_date, symbol).

    ``smoke=True`` : sous-ensemble minuscule (quelques symboles, fenêtre courte,
    petit univers) pour valider le pipeline en quelques secondes.
    """
    if smoke:
        # Événements DIP tombant dans la fenêtre bars du smoke (2024 été)
        events = events[
            (events["signal_date"] >= "2024-06-01") & (events["signal_date"] <= "2024-09-01")
        ].head(8).copy()
        bs, be, top_n = "2024-05-01", "2024-10-01", 80
        _plog("== SMOKE MODE ==")
    else:
        bs, be, top_n = _BARS_START, _BARS_END, 3000
    dip_symbols = sorted(events["symbol"].unique())
    if dip_symbols:
        _in = ",".join(["%s"] * len(dip_symbols))
        # Ordre SQL : BETWEEN (2) d'abord, puis IN(...)
        _params = tuple([bs, be] + list(dip_symbols))
        _where_sym = f" AND symbol IN ({_in})"
    else:
        _params = (bs, be)
        _where_sym = ""
    bars = pd.read_sql(
        f"SELECT symbol, date, open, high, low, close, adj_close, volume FROM stock_bars_daily "
        f"WHERE data_source='eodhd_eod' AND date BETWEEN %s AND %s{_where_sym}",
        engine, params=tuple(_params),
    )
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars[bars["symbol"].isin(dip_symbols)]
    bars = bars.dropna(subset=["date", "symbol", "adj_close"]).drop_duplicates(subset=["symbol", "date"])

    print(f"bars DIP: {len(bars)} rows, {bars['symbol'].nunique()} symboles")
    feat = _compute_bars_features(bars)
    _plog(f"features bars OK ({feat.shape[0]} lignes, {feat.shape[1]} cols)")

    # SPY + macro
    spy_ret = pd.read_sql(
        "SELECT date, adj_close FROM stock_bars_daily WHERE symbol='SPY' AND data_source='eodhd_eod' AND date BETWEEN %s AND %s",
        engine, params=(bs, be),
    )
    spy_ret["date"] = pd.to_datetime(spy_ret["date"]).dt.normalize()
    spy_ret["ret1"] = spy_ret["adj_close"].pct_change()
    spy_ret = spy_ret.sort_values("date")
    beta = _compute_beta126(feat[["symbol", "date", "ret1"]], spy_ret)
    feat = feat.merge(beta, on=["symbol", "date"], how="left")
    _plog("beta OK")

    mkt = _compute_market_features(engine)
    feat = feat.merge(mkt, on="date", how="left")
    _plog("contexte marché OK")

    # Breadth + rangs cross-sectionnels (univers liquide)
    breadth, rank_tables, uni = _compute_breadth_ranks(engine, top_n, bs, be)
    feat = feat.merge(breadth, on="date", how="left")
    for name, rt in rank_tables.items():
        feat = feat.merge(rt, on=["date", "symbol"], how="left")
    _plog("breadth + rangs OK")

    # Secteur
    meta_sec, sec, svs = _compute_sector_features(engine, uni)
    feat = feat.merge(meta_sec, on="symbol", how="left")
    feat = feat.merge(svs, on=["date", "symbol"], how="left")
    feat = feat.merge(
        sec[["date", "sector_name", "sector_ret20", "sector_breadth"]],
        on=["date", "sector_name"], how="left",
    )
    _plog("secteur OK")

    # Aligner sur les événements DIP (signal_date = J, jointure (date, symbol))
    _ev_cols = ["signal_date", "symbol", "global_rank_20", "ret_4",
                "future_return_H20", "future_return_oracle", "oracle_decile"]
    out = events[[c for c in _ev_cols if c in events.columns]].merge(
        feat.rename(columns={"date": "fdate"}),
        left_on=["signal_date", "symbol"], right_on=["fdate", "symbol"], how="left",
    )
    out = out.drop(columns=["fdate"], errors="ignore")
    _plog(f"alignement events OK ({out.shape[0]} lignes)")

    # ── Sentiment ticker (PIT, trade_date = signal J) ──
    sent = pd.read_sql(
        "SELECT symbol, trade_date, news_count_5d, news_count_10d, sentiment_net_mean_5d, "
        "sentiment_net_mean_10d, sentiment_net_sum_5d, major_event_flag, "
        "major_event_day_count_10d, after_close_news_count FROM ticker_daily_sentiment_features "
        "WHERE trade_date BETWEEN %s AND %s",
        engine, params=(START, END),
    )
    sent["trade_date"] = pd.to_datetime(sent["trade_date"]).dt.normalize()
    sent["symbol"] = sent["symbol"].astype(str).str.upper()
    sent = sent.rename(columns={"trade_date": "sdate"})
    out = out.merge(sent, left_on=["signal_date", "symbol"], right_on=["sdate", "symbol"], how="left")
    out = out.drop(columns=["sdate"], errors="ignore")
    _plog("sentiment ticker OK")

    # ── Sentiment secteur (PIT) ──
    sent_sec = pd.read_sql(
        "SELECT sector, trade_date, sector_sentiment_net_mean_5d, sector_impact_score_5d, "
        "macro_event_intensity_5d, sector_positive_ratio FROM sector_daily_sentiment_features "
        "WHERE trade_date BETWEEN %s AND %s",
        engine, params=(START, END),
    )
    sent_sec["trade_date"] = pd.to_datetime(sent_sec["trade_date"]).dt.normalize()
    sent_sec = sent_sec.rename(columns={"trade_date": "ssec_date"})
    out = out.merge(
        sent_sec.rename(columns={"sector": "ssec"}),
        left_on=["signal_date", "sector_name"], right_on=["ssec_date", "ssec"], how="left",
    )
    out = out.drop(columns=["ssec_date", "ssec"], errors="ignore")
    _plog("sentiment secteur OK")

    # ── Fondamentaux (PIT asof trade_date) ──
    fund = pd.read_sql(
        "SELECT symbol, trade_date, beta, pe_ratio, forward_pe, pb_ratio, ps_ratio, "
        "dividend_yield, roe, net_margin, debt_to_equity, eps_growth_yoy, "
        "revenue_growth_yoy, market_cap FROM stock_fundamentals_daily "
        "WHERE trade_date BETWEEN %s AND %s",
        engine, params=(START, END),
    )
    fund["trade_date"] = pd.to_datetime(fund["trade_date"]).dt.normalize()
    fund["symbol"] = fund["symbol"].astype(str).str.upper()
    fund = fund.rename(columns={"trade_date": "fdate", "beta": "beta_f", "market_cap": "market_cap_f"})
    asof_cols = ["beta_f", "pe_ratio", "forward_pe", "pb_ratio", "ps_ratio",
                 "dividend_yield", "roe", "net_margin", "debt_to_equity",
                 "eps_growth_yoy", "revenue_growth_yoy", "market_cap_f"]
    out = pd.merge_asof(
        out.sort_values("signal_date"),
        fund[["fdate", "symbol"] + asof_cols].sort_values("fdate"),
        left_on="signal_date", right_on="fdate", by="symbol", direction="backward",
    )
    out = out.drop(columns=["fdate"], errors="ignore")
    _plog("fondamentaux joints (asof)")

    # ── Earnings (jours jusqu'au prochain résultat, PIT) ──
    ear = pd.read_sql(
        "SELECT symbol, earnings_date FROM stock_earnings_calendar "
        "WHERE earnings_date BETWEEN %s AND %s",
        engine, params=(START, "2026-03-31"),
    )
    ear["earnings_date"] = pd.to_datetime(ear["earnings_date"]).dt.normalize()
    ear["symbol"] = ear["symbol"].astype(str).str.upper()
    nxt = pd.merge_asof(
        out.sort_values("signal_date"),
        ear[["symbol", "earnings_date"]].rename(columns={"earnings_date": "next_earnings"}).sort_values("next_earnings"),
        left_on="signal_date", right_on="next_earnings", by="symbol", direction="forward",
    )
    out["days_to_next_earnings"] = (nxt["next_earnings"] - out["signal_date"]).dt.days
    out["earnings_blackout"] = (out["days_to_next_earnings"] <= 5).astype(float)
    _plog("earnings joints")

    # Idiosyncratique (résidu simple)
    out["idio_ret20"] = out["ret20"] - out["beta126"] * out["spy_ret20"]
    out["stock_vs_market_20"] = out["ret20"] - out["spy_ret20"]

    # ── Filtre final : ne garder que les features de l'inventaire + clés/labels ──
    _register_meta()
    _feature_names = [m["feature_name"] for m in FEATURE_META]
    _base = ["signal_date", "symbol", "global_rank_20", "ret_4", "sector_name",
             "future_return_H20", "future_return_oracle", "oracle_decile", "batch_id"]
    _keep = [c for c in _base + _feature_names if c in out.columns]
    _drop = sorted(set(out.columns) - set(_keep))
    if _drop:
        _plog(f"colonnes exclues (non-features/redondantes, {len(_drop)}): {_drop}")
    return out[_keep]


def _register_meta() -> None:
    """Déclare l'inventaire (family/source) pour le rapport."""
    if FEATURE_META:
        return
    fam = {
        "atr14_pct": ("volatility/ATR", "bars"), "rvol10": ("volatility/ATR", "bars"),
        "rvol20": ("volatility/ATR", "bars"), "rvol60": ("volatility/ATR", "bars"),
        "vol_ratio_10_60": ("volatility/ATR", "bars"), "atr_expand_5": ("volatility/ATR", "bars"),
        "rvol_expand_5": ("volatility/ATR", "bars"),
        "ret1": ("momentum", "bars"), "ret5": ("momentum", "bars"), "ret10": ("momentum", "bars"),
        "ret20": ("momentum", "bars"), "ret60": ("momentum", "bars"),
        "dist_sma20": ("distance SMA/EMA", "bars"), "dist_sma50": ("distance SMA/EMA", "bars"),
        "dist_sma100": ("distance SMA/EMA", "bars"), "dist_sma200": ("distance SMA/EMA", "bars"),
        "dist_ema20": ("distance SMA/EMA", "bars"), "macd_norm": ("trend", "bars"),
        "sma50_slope_5": ("trend", "bars"), "sma200_slope_5": ("trend", "bars"),
        "vol_z20": ("volume/liquidity", "bars"), "vol_ratio_1_5": ("volume/liquidity", "bars"),
        "vol_ratio_5_20": ("volume/liquidity", "bars"), "dollar_vol_20": ("volume/liquidity", "bars"),
        "pos_20": ("support/range", "bars"), "pos_60": ("support/range", "bars"),
        "range_20_pct": ("support/range", "bars"), "range_60_pct": ("support/range", "bars"),
        "pos_52w": ("support/range", "bars"), "dist_52w_high": ("support/range", "bars"),
        "dist_52w_low": ("support/range", "bars"),
        "beta126": ("beta/systematic", "bars+SPY"), "beta20": ("beta/systematic", "bars+SPY"),
        "spy_ret5": ("market-relative", "SPY"), "spy_ret20": ("market-relative", "SPY"),
        "spy_ret60": ("market-relative", "SPY"), "spy_dist_sma50": ("market-relative", "SPY"),
        "spy_dist_sma200": ("market-relative", "SPY"), "spy_sma50_slope_5": ("market-relative", "SPY"),
        "vix": ("macro", "macro"), "vix_chg5": ("macro", "macro"),
        "vix_ratio_9_3m": ("macro", "macro"), "vxn": ("macro", "macro"),
        "rvx": ("macro", "macro"), "move": ("macro", "macro"),
        "ten_y": ("macro", "macro"), "yield_10y_5d_pct": ("macro", "macro"),
        "regime_mode": ("breadth/regime", "macro"), "risk_multiplier": ("breadth/regime", "macro"),
        "vix_curve_inverted": ("macro", "macro"),
        "breadth_above_sma50": ("breadth/regime", "univers"), "breadth_above_sma200": ("breadth/regime", "univers"),
        "breadth_ret1_pos": ("breadth/regime", "univers"), "breadth_ret20_pos": ("breadth/regime", "univers"),
        "breadth_rvol_hi": ("breadth/regime", "univers"),
        "mom20_xs": ("cross-sectional", "univers"), "rvol20_xs": ("cross-sectional", "univers"),
        "trend_xs": ("cross-sectional", "univers"),
        "stock_vs_sector_ret20": ("sector-relative", "bars+meta"),
        "sector_rank_ret20": ("sector-relative", "bars+meta"),
        "sector_ret20": ("sector-relative", "bars+meta"), "sector_breadth": ("sector-relative", "bars+meta"),
        "news_count_5d": ("sentiment", "news"), "news_count_10d": ("sentiment", "news"),
        "sentiment_net_mean_5d": ("sentiment", "news"), "sentiment_net_mean_10d": ("sentiment", "news"),
        "sentiment_net_sum_5d": ("sentiment", "news"), "major_event_flag": ("sentiment", "news"),
        "major_event_day_count_10d": ("sentiment", "news"), "after_close_news_count": ("sentiment", "news"),
        "sector_sentiment_net_mean_5d": ("sentiment", "sector news"), "sector_impact_score_5d": ("sentiment", "sector news"),
        "macro_event_intensity_5d": ("sentiment", "sector news"), "sector_positive_ratio": ("sentiment", "sector news"),
        "beta_f": ("fundamentals", "fund"), "pe_ratio": ("fundamentals", "fund"),
        "forward_pe": ("fundamentals", "fund"), "pb_ratio": ("fundamentals", "fund"),
        "ps_ratio": ("fundamentals", "fund"), "dividend_yield": ("fundamentals", "fund"),
        "roe": ("fundamentals", "fund"), "net_margin": ("fundamentals", "fund"),
        "debt_to_equity": ("fundamentals", "fund"), "eps_growth_yoy": ("fundamentals", "fund"),
        "revenue_growth_yoy": ("fundamentals", "fund"), "market_cap_f": ("fundamentals", "fund"),
        "days_to_next_earnings": ("earnings/events", "earnings calendar"),
        "earnings_blackout": ("earnings/events", "earnings calendar"),
        "idio_ret20": ("company idiosyncratic", "bars+SPY"),
        "stock_vs_market_20": ("company idiosyncratic", "bars+SPY"),
        "global_rank_20": ("cross-sectional", "rank_history"),
    }
    for f, (family, source) in fam.items():
        _reg(f, family, source)


# ═══════════════════════════════════════════════════════════════════════════
# STAGE ANALYSES — sections 4 à 13 du chantier
# ═══════════════════════════════════════════════════════════════════════════

from scipy import stats as _sstats

COV_THRESHOLD = 0.60
N_PERM = 500
ANAL_DIR = ARTIFACTS_DIR / "analyses"
ANAL_DIR.mkdir(parents=True, exist_ok=True)


def _load_panel():
    df = pd.read_csv(ARTIFACTS_DIR / "features.csv", parse_dates=["signal_date"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df = df.replace([np.inf, -np.inf], np.nan)
    inv = pd.read_csv(ARTIFACTS_DIR / "feature_inventory.csv")
    fam = dict(zip(inv["feature_name"], inv["family"]))
    return df, fam


def _feature_set(df: pd.DataFrame, fam: dict[str, str]) -> list[str]:
    feats = []
    for f in fam:
        if f not in df.columns:
            continue
        s = df[f]
        if not pd.api.types.is_numeric_dtype(s):
            continue
        if s.notna().mean() < COV_THRESHOLD:
            continue
        if s.nunique() <= 1:
            continue
        feats.append(f)
    return feats


def _auc_rank(y: np.ndarray, score: np.ndarray) -> float:
    """AUC via Mann-Whitney : P(score|y=1 > score|y=0)."""
    y = np.asarray(y); score = np.asarray(score, dtype=float)
    pos = y == 1
    n1 = int(pos.sum()); n0 = int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return np.nan
    r = _sstats.rankdata(score)
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _group_stats(s1: pd.Series, s2: pd.Series) -> dict:
    a = s1.dropna().to_numpy(dtype=float)
    b = s2.dropna().to_numpy(dtype=float)
    d = {"n1": int(len(a)), "n2": int(len(b))}
    if len(a) == 0 or len(b) == 0:
        return d
    d["mean1"], d["mean2"] = a.mean(), b.mean()
    d["median1"], d["median2"] = np.median(a), np.median(b)
    d["std1"], d["std2"] = a.std(ddof=1), b.std(ddof=1)
    d["p25_1"], d["p75_1"] = np.percentile(a, 25), np.percentile(a, 75)
    d["p25_2"], d["p75_2"] = np.percentile(b, 25), np.percentile(b, 75)
    d["delta_mean"] = d["mean1"] - d["mean2"]
    d["delta_median"] = d["median1"] - d["median2"]
    sp = np.sqrt((d["std1"] ** 2 + d["std2"] ** 2) / 2)
    d["cohens_d"] = d["delta_mean"] / sp if sp > 0 else np.nan
    d["mw_p"] = _sstats.mannwhitneyu(a, b, alternative="two-sided").pvalue
    d["ks_D"] = _sstats.ks_2samp(a, b).statistic
    return d


def _run_analyses(smoke: bool = False) -> None:
    df, fam = _load_panel()
    n_perm = 50 if smoke else N_PERM
    if smoke:
        _plog("== SMOKE ANALYSES ==")

    # ── Univers PROD : allow_new_entries == True à J ──
    # PROD ne peut PAS ouvrir de position en close_only/cash_only. Ces événements
    # sont EXCLUS du training/métriques, et détaillés dans un tableau de contrôle.
    from database.connection import get_sqlalchemy_engine as _gse
    _ane = pd.read_sql(
        "SELECT trade_date, allow_new_entries FROM stock_macro_indicators_daily", _gse()
    )
    _ane["trade_date"] = pd.to_datetime(_ane["trade_date"]).dt.normalize()
    _ane_map = dict(zip(_ane["trade_date"], _ane["allow_new_entries"]))
    df["allow_new_entries"] = df["signal_date"].map(_ane_map)
    df["allow_new_entries"] = df["allow_new_entries"].where(
        df["allow_new_entries"].notna(),
        (~df["regime_mode"].isin(["close_only", "cash_only"])).astype(int),
    ).astype(bool)

    # Tableau de contrôle des événements exclus (close_only / cash_only)
    ex = df[~df["allow_new_entries"]].copy()
    if len(ex):
        ctl_rows = []
        for reg, g in ex.groupby("regime_mode"):
            f = g["future_return_H20"].dropna()
            srt = f.sort_values()
            n5 = max(1, int(len(f) * 0.05))
            ctl_rows.append({
                "regime": reg, "n_DIP": len(g), "mean_H20": f.mean() if len(f) else np.nan,
                "P_gt0": (f > 0).mean() if len(f) else np.nan,
                "BAD5": srt.head(n5).mean() if len(f) else np.nan,
                "GOOD5": srt.tail(n5).mean() if len(f) else np.nan,
            })
        ctl = pd.DataFrame(ctl_rows)
        ctl.to_csv(ANAL_DIR / "regime_control_excluded.csv", index=False)
        _plog(f"contrôle régimes exclus écrits: {len(ctl)} lignes")
    df = df[df["allow_new_entries"]].reset_index(drop=True)
    _plog(f"univers PROD (allow_new_entries=True): {len(df)} événements")

    feats = _feature_set(df, fam)
    _plog(f"features analysées: {len(feats)} (couverture ≥ {COV_THRESHOLD:.0%}), perm={n_perm}")
    pd.DataFrame([{"feature": f, "family": fam.get(f, "?")} for f in feats]).to_csv(
        ANAL_DIR / "features_kept.csv", index=False)

    # ── Labels ──
    fwd = df["future_return_H20"]
    win_mask = fwd > 0
    loss_mask = fwd <= 0
    vg_mask = df["oracle_decile"].isin([8, 9, 10])
    vb_mask = df["oracle_decile"].isin([1, 2, 3])

    rows_wl, rows_ex = [], []
    for f in feats:
        s = df[f]
        w = s[win_mask]; l = s[loss_mask]
        gw = _group_stats(w, l)
        # AUC WIN vs LOSS (mêmes lignes que le score non-null)
        m = s.notna() & fwd.notna()
        auc = _auc_rank((fwd[m] > 0).astype(int).to_numpy(), s[m].to_numpy(dtype=float))
        rows_wl.append({
            "feature": f, "family": fam.get(f, "?"),
            "n_win": gw.get("n1", 0), "n_loss": gw.get("n2", 0),
            "win_mean": gw.get("mean1"), "loss_mean": gw.get("mean2"),
            "win_median": gw.get("median1"), "loss_median": gw.get("median2"),
            "win_std": gw.get("std1"), "loss_std": gw.get("std2"),
            "p25_win": gw.get("p25_1"), "p75_win": gw.get("p75_1"),
            "p25_loss": gw.get("p25_2"), "p75_loss": gw.get("p75_2"),
            "delta_mean": gw.get("delta_mean"), "delta_median": gw.get("delta_median"),
            "cohens_d": gw.get("cohens_d"), "mw_p": gw.get("mw_p"), "ks_D": gw.get("ks_D"),
            "auc_win_loss": auc, "dir_auc_win_loss": max(auc, 1 - auc),
        })
        # EXTREME (D8-10 vs D1-3)
        gv = df.loc[vg_mask, f]; gb = df.loc[vb_mask, f]
        ge = _group_stats(gv, gb)
        m2 = df["oracle_decile"].isin([1, 2, 3, 8, 9, 10]) & s.notna()
        auc2 = _auc_rank((df.loc[m2, "oracle_decile"] >= 8).astype(int).to_numpy(),
                         df.loc[m2, f].to_numpy(dtype=float))
        rows_ex.append({
            "feature": f, "family": fam.get(f, "?"),
            "n_good": ge.get("n1", 0), "n_bad": ge.get("n2", 0),
            "good_mean": ge.get("mean1"), "bad_mean": ge.get("mean2"),
            "good_median": ge.get("median1"), "bad_median": ge.get("median2"),
            "good_std": ge.get("std1"), "bad_std": ge.get("std2"),
            "p25_good": ge.get("p25_1"), "p75_good": ge.get("p75_1"),
            "p25_bad": ge.get("p25_2"), "p75_bad": ge.get("p75_2"),
            "delta_mean": ge.get("delta_mean"), "delta_median": ge.get("delta_median"),
            "cohens_d": ge.get("cohens_d"), "mw_p": ge.get("mw_p"), "ks_D": ge.get("ks_D"),
            "auc_extreme": auc2, "dir_auc_extreme": max(auc2, 1 - auc2),
        })
    wl = pd.DataFrame(rows_wl).sort_values("dir_auc_win_loss", ascending=False)
    ex = pd.DataFrame(rows_ex).sort_values("dir_auc_extreme", ascending=False)
    wl.to_csv(ANAL_DIR / "stats_win_loss.csv", index=False)
    ex.to_csv(ANAL_DIR / "stats_extreme.csv", index=False)
    _plog(f"stats WIN/LOSS + EXTREME écrites ({len(wl)} features)")

    # ── IC (Spearman avec future_return_H20) + quantiles + stabilité ──
    ic_rows, q_rows = [], []
    for f in feats:
        m = df[f].notna() & fwd.notna()
        if m.sum() < 100:
            ic_rows.append({"feature": f, "ic_h20": np.nan, "n": int(m.sum())})
            continue
        ic = _sstats.spearmanr(df.loc[m, f], fwd[m]).statistic
        ic_rows.append({"feature": f, "ic_h20": float(ic), "n": int(m.sum())})
        # Quantiles (quintiles)
        try:
            qcut = pd.qcut(df.loc[m, f], 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        tmp = df.loc[m, ["signal_date", f]].copy()
        tmp["q"] = qcut
        tmp["fwd"] = fwd[m]
        tmp["d"] = df.loc[m, "oracle_decile"]
        for qi in range(5):
            sub = tmp[tmp["q"] == qi]
            if len(sub) == 0:
                continue
            d1 = (sub["d"] == 1).mean(); d10 = (sub["d"] == 10).mean()
            srt = sub["fwd"].sort_values()
            n5 = max(1, int(len(sub) * 0.05))
            q_rows.append({
                "feature": f, "quintile": qi + 1, "n": len(sub),
                "fwd_mean": sub["fwd"].mean(), "fwd_median": sub["fwd"].median(),
                "p_positive": (sub["fwd"] > 0).mean(), "d1_rate": d1, "d10_rate": d10,
                "bad5": srt.head(n5).mean(), "good5": srt.tail(n5).mean(),
            })
    ic_df = pd.DataFrame(ic_rows).sort_values("ic_h20", key=lambda x: x.abs(), ascending=False)
    ic_df.to_csv(ANAL_DIR / "ic_h20.csv", index=False)
    q_df = pd.DataFrame(q_rows)
    q_df.to_csv(ANAL_DIR / "quantiles.csv", index=False)
    _plog("IC + quantiles écrits")

    # Monotonicité : Spearman(quintile, fwd_mean)
    mono = []
    for f in feats:
        sub = q_df[q_df["feature"] == f]
        if len(sub) >= 3:
            mono.append({"feature": f, "monotonicity": _sstats.spearmanr(sub["quintile"], sub["fwd_mean"]).statistic})
    mono_df = pd.DataFrame(mono)
    mono_df.to_csv(ANAL_DIR / "monotonicity.csv", index=False)

    # ── Stabilité temporelle (par année) ──
    stab_rows = []
    years = sorted(df["signal_date"].dt.year.unique())
    for f in feats:
        dirs = {}
        for y in years:
            yy = df["signal_date"].dt.year == y
            m = yy & df[f].notna() & fwd.notna()
            if m.sum() < 50:
                dirs[y] = np.nan
                continue
            a = _auc_rank((fwd[m] > 0).astype(int).to_numpy(), df.loc[m, f].to_numpy(dtype=float))
            dirs[y] = 1 if a > 0.5 else (-1 if a < 0.5 else 0)
        overall_auc = wl.set_index("feature").loc[f, "auc_win_loss"]
        overall_sign = 1 if overall_auc > 0.5 else (-1 if overall_auc < 0.5 else 0)
        sig = [d for d in dirs.values() if d != 0 and not pd.isna(d)]
        stab_rows.append({
            "feature": f, **{f"dir_{y}": dirs.get(y) for y in years},
            "overall_sign": overall_sign,
            "sign_stability": float(np.mean([d == overall_sign for d in sig])) if sig else np.nan,
        })
    stab_df = pd.DataFrame(stab_rows)
    stab_df.to_csv(ANAL_DIR / "stability_by_year.csv", index=False)
    _plog("stabilité temporelle écrite")

    # ── Q1 vs Q2 2025 ──
    q1 = df[(df["signal_date"] >= "2025-01-01") & (df["signal_date"] < "2025-04-01")]
    q2 = df[(df["signal_date"] >= "2025-04-01") & (df["signal_date"] < "2025-07-01")]
    wl_auc = wl.set_index("feature")["auc_win_loss"].to_dict()
    q12_rows = []
    for f in feats:
        a = q1[f].dropna().to_numpy(dtype=float); b = q2[f].dropna().to_numpy(dtype=float)
        if len(a) < 20 or len(b) < 20:
            continue
        sp = np.sqrt((a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2) / 2)
        std_diff = (a.mean() - b.mean()) / sp if sp > 0 else np.nan
        auc12 = _auc_rank(np.concatenate([np.ones(len(a)), np.zeros(len(b))]),
                          np.concatenate([a, b]))
        predicts = abs(wl_auc.get(f, 0.5) - 0.5) >= 0.05  # dir_auc >= 0.55
        diff12 = abs(std_diff) >= 0.3 if not pd.isna(std_diff) else False
        if diff12 and predicts:
            t = "TYPE_A"
        elif diff12 and not predicts:
            t = "TYPE_B"
        elif not diff12 and predicts:
            t = "TYPE_C"
        else:
            t = "NOISE"
        q12_rows.append({
            "feature": f, "family": fam.get(f, "?"),
            "q1_mean": a.mean(), "q2_mean": b.mean(),
            "standardized_diff": std_diff, "auc_q1_vs_q2": auc12,
            "also_predicts_win_loss": predicts, "type": t,
        })
    q12 = pd.DataFrame(q12_rows).sort_values("standardized_diff", key=lambda x: x.abs(), ascending=False)
    q12.to_csv(ANAL_DIR / "q1_q2_2025.csv", index=False)
    _plog(f"Q1/Q2 2025 écrites ({len(q12)} features)")

    # ── Contexte marché / secteur (WIN vs LOSS) ──
    ctx_feats = [f for f in feats if any(k in f for k in
                 ("spy_", "breadth_", "vix", "yield", "ten_y", "sector_", "stock_vs", "beta"))]
    ctx_rows = []
    for f in ctx_feats:
        m = df[f].notna() & fwd.notna()
        a = _auc_rank((fwd[m] > 0).astype(int).to_numpy(), df.loc[m, f].to_numpy(dtype=float))
        ctx_rows.append({"feature": f, "family": fam.get(f, "?"), "auc_win_loss": a,
                         "win_mean": df.loc[win_mask & df[f].notna(), f].mean(),
                         "loss_mean": df.loc[loss_mask & df[f].notna(), f].mean()})
    ctx_df = pd.DataFrame(ctx_rows).sort_values("auc_win_loss")
    ctx_df.to_csv(ANAL_DIR / "context_market.csv", index=False)
    _plog("contexte marché écrit")

    # ── Redondance (clusters corr >= 0.80) ──
    corr = df[feats].corr().abs()
    used, clusters = set(), []
    for f in feats:
        if f in used:
            continue
        members = [g for g in feats if g not in used and corr.loc[f, g] >= 0.80]
        used.update(members)
        clusters.append(members)
    cl_rows = []
    for i, cl in enumerate(clusters):
        for g in cl:
            cl_rows.append({"feature": g, "correlation_cluster": i + 1})
    cl_df = pd.DataFrame(cl_rows)
    cl_df.to_csv(ANAL_DIR / "redundancy_clusters.csv", index=False)
    _plog(f"redondance : {len(clusters)} clusters (corr≥0.80)")

    # ── Multiple testing (permutation, max dir-AUC) ──
    rng = np.random.default_rng(42)
    m = fwd.notna()
    y = (fwd[m] > 0).astype(int).to_numpy()
    X = np.column_stack([df.loc[m, f].to_numpy(dtype=float) for f in feats])
    null_max = []
    for _ in range(n_perm):
        yp = rng.permutation(y)
        aucs = []
        for j in range(X.shape[1]):
            col = X[:, j]
            ok = ~np.isnan(col)
            if ok.sum() < 100 or len(np.unique(col[ok])) <= 1:
                continue
            aucs.append(_auc_rank(yp[ok], col[ok]))
        dirs = [max(a, 1 - a) for a in aucs if not np.isnan(a)]
        null_max.append(max(dirs) if dirs else 0.5)
    null_max = np.array(null_max)
    p95 = np.percentile(null_max, 95)
    perm_rows = []
    for j, f in enumerate(feats):
        col = X[:, j]
        ok = ~np.isnan(col)
        if ok.sum() < 100:
            continue
        a = _auc_rank(y[ok], col[ok])
        perm_rows.append({"feature": f, "dir_auc_win_loss": max(a, 1 - a),
                          "perm_pvalue": float(np.mean(null_max >= max(a, 1 - a))),
                          "null_p95": float(p95)})
    perm_df = pd.DataFrame(perm_rows).sort_values("dir_auc_win_loss", ascending=False)
    perm_df.to_csv(ANAL_DIR / "permutation.csv", index=False)
    _plog(f"permutation faite (null_p95={p95:.3f})")

    # ── Score de robustesse + livrable ──
    wl_i = wl.set_index("feature")
    ex_i = ex.set_index("feature")
    ic_i = ic_df.set_index("feature")
    st_i = stab_df.set_index("feature")
    mono_i = mono_df.set_index("feature")["monotonicity"].to_dict()
    perm_i = perm_df.set_index("feature")["perm_pvalue"].to_dict()
    cl_map = cl_df.set_index("feature")["correlation_cluster"].to_dict()
    master = []
    for f in feats:
        cov = df[f].notna().mean()
        dauc_wl = wl_i.loc[f, "dir_auc_win_loss"] if f in wl_i.index else np.nan
        dauc_ex = ex_i.loc[f, "dir_auc_extreme"] if f in ex_i.index else np.nan
        ic = ic_i.loc[f, "ic_h20"] if f in ic_i.index else np.nan
        sign_stab = st_i.loc[f, "sign_stability"] if f in st_i.index else np.nan
        mono = mono_i.get(f, np.nan)
        pp = perm_i.get(f, np.nan)
        cl = cl_map.get(f)
        # direction (sens de l'AUC WIN/LOSS)
        a = wl_i.loc[f, "auc_win_loss"] if f in wl_i.index else np.nan
        direction = "HIGH->WIN" if a > 0.5 else ("HIGH->LOSS" if a < 0.5 else "flat")
        score = 0.0
        score += (abs(dauc_wl - 0.5) / 0.5) * 0.25
        score += min(abs(ic) / 0.08, 1.0) * 0.20
        score += (sign_stab if not pd.isna(sign_stab) else 0) * 0.20
        score += (abs(mono) if not pd.isna(mono) else 0) * 0.15
        score += (0.20 if pp < 0.05 else (0.10 if pp < 0.20 else 0.0)) * 0.10
        score += (0.10 if cl == 1 else 0.05) * 0.10
        # verdict
        if pp is not None and not pd.isna(pp) and pp < 0.05 and abs(dauc_wl - 0.5) >= 0.06 and (sign_stab or 0) >= 0.6:
            verdict = "STRONG_CANDIDATE"
        elif abs(dauc_wl - 0.5) >= 0.04 or abs(ic) >= 0.03:
            verdict = "WEAK_CANDIDATE"
        elif cl is not None and cl != 1:
            verdict = "REDUNDANT"
        elif not pd.isna(sign_stab) and sign_stab < 0.5:
            verdict = "UNSTABLE"
        else:
            verdict = "NO_SIGNAL"
        master.append({
            "feature": f, "family": fam.get(f, "?"), "coverage": cov, "direction": direction,
            "auc_win_loss": a, "dir_auc_win_loss": dauc_wl, "auc_extreme": dauc_ex,
            "ic_h20": ic, "sign_stability": sign_stab, "monotonicity": mono,
            "permutation_pvalue": pp, "correlation_cluster": cl, "robustness_score": score,
            "verdict": verdict,
        })
    master_df = pd.DataFrame(master).sort_values("robustness_score", ascending=False)
    master_df.to_csv(ANAL_DIR / "master_deliverable.csv", index=False)
    _plog("livrable principal écrit")
    _build_report(master_df, wl, ex, q12, ctx_df, null_max, q_df, feats,
                  n_events=len(df), control_path=str(ANAL_DIR / "regime_control_excluded.csv"))
    _plog("rapport final écrit")


def _build_report(master, wl, ex, q12, ctx, null_max, q_df, feats, n_events=None,
                  control_path=None) -> None:
    md = []
    md.append("# Chantier `dip_context_pattern_analysis` — Rapport final (2026-08-27)")
    md.append("")
    n_tot = len(pd.read_csv(ARTIFACTS_DIR / "events.csv"))
    uni = f" (univers PROD `allow_new_entries=True` : {n_events})" if n_events else ""
    md.append(f"Dataset : {n_tot} événements DIP N4/X2 (batch `ef2cd0`, 2022-2025, N4/X2 gelés). "
              f"Analyses sur l'univers `allow_new_entries=True`{uni}. "
              f"Features : {len(feats)} après couverture ≥60%.")
    md.append("")
    md.append("### Événements EXCLUS (close_only / cash_only — PROD ne peut pas ouvrir)")
    md.append("")
    if control_path:
        try:
            ctl = pd.read_csv(control_path)
            md.append("Tableau de contrôle : `regime_control_excluded.csv`")
            md.append("")
            md.append(ctl.to_markdown(index=False))
        except Exception:
            md.append("(tableau de contrôle indisponible)")
    md.append("")
    md.append("## Top 15 features par score de robustesse")
    md.append("")
    cols = ["feature", "family", "direction", "auc_win_loss", "auc_extreme", "ic_h20",
            "sign_stability", "monotonicity", "permutation_pvalue", "verdict"]
    md.append(master.head(15)[cols].to_markdown(index=False))
    md.append("")
    md.append("## Contexte marché/secteur — WIN vs LOSS (AUC, le plus bas = contexte faible → LOSS)")
    md.append("")
    md.append(ctx.sort_values("auc_win_loss").head(15)[
        ["feature", "family", "auc_win_loss", "win_mean", "loss_mean"]].to_markdown(index=False))
    md.append("")
    md.append("## Q1 vs Q2 2025 — top 15 différences standardisées (TYPE_A/B/C)")
    md.append("")
    md.append(q12.sort_values("standardized_diff", key=lambda x: x.abs(), ascending=False).head(15)[
        ["feature", "family", "q1_mean", "q2_mean", "standardized_diff", "type"]].to_markdown(index=False))
    md.append("")
    md.append("## Multiple testing (permutation)")
    md.append("")
    md.append(f"- {N_PERM} permutations, null p95 du max dir-AUC = {np.percentile(null_max,95):.3f}.")
    md.append(f"- Features dépassant le bruit (dir-AUC ≥ null p95) : "
              f"{int((master['dir_auc_win_loss'] >= np.percentile(null_max,95)).sum())}.")
    md.append("")
    md.append("## Verdict features (comptage)")
    md.append("")
    md.append(master["verdict"].value_counts().to_string())
    md.append("")
    md.append("## Réponses aux questions du chantier")
    md.append("")
    md.append("- **Q1 — features qui différencient bons/mauvais DIP ?** Voir top du livrable "
              "(AUC/IC/stabilité/permutation).")
    md.append("- **Q2 — features qui expliquent l'échec Q1 2025 ?** Voir `q1_q2_2025.csv` (TYPE_A).")
    md.append("- **Q3 — fonctionnent-elles hors Q1/Q2 ?** Via sign_stability + AUC hors 2025.")
    md.append("- **Q4 — mauvais DIP = vol expansion / cassure tendance / secteur faible / marché faible / "
              "beta élevé ?** Voir `context_market.csv`.")
    md.append("- **Q5 — ≥5-10 features complémentaires stables ?** Selon verdicts + clusters.")
    md.append("")
    md.append("## Décision (GO/NO-GO vers DipQualityModel)")
    md.append("")
    strong = int((master["verdict"] == "STRONG_CANDIDATE").sum())
    weak = int((master["verdict"] == "WEAK_CANDIDATE").sum())
    above_noise = int((master["dir_auc_win_loss"] >= np.percentile(null_max, 95)).sum())
    md.append(f"- STRONG_CANDIDATE : {strong} | WEAK : {weak} | > bruit permutation : {above_noise}.")
    md.append("- **GO** si plusieurs features STRONG stables, monotones, complémentaires (≠ clusters) "
              "et au-delà du bruit. **NO-GO** si AUC ~hasard, signes instables, résultat porté par Q1/Q2.")
    md.append("")
    (ANAL_DIR / "report.md").write_text("\n".join(md), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE DELTAS — section 10 (dérivés de changement / pente), univers PROD
# ═══════════════════════════════════════════════════════════════════════════

DELTA_SYM_FEATS = ["pos_52w", "dist_52w_high", "dist_52w_low", "pos_60", "ret60",
                   "dist_sma20", "dist_sma50", "dist_sma100"]
DELTA_DATE_FEATS = ["spy_dist_sma200", "vix", "ten_y", "breadth_above_sma50", "breadth_above_sma200"]
DELTA_SEC_FEATS = ["sector_ret20", "sector_breadth"]
DELTA_ALL = DELTA_SYM_FEATS + DELTA_DATE_FEATS + DELTA_SEC_FEATS
PCT_CHANGE_FEATS = {"vix", "ten_y"}


def _prod_universe(engine) -> pd.DataFrame:
    events = pd.read_csv(ARTIFACTS_DIR / "events.csv", parse_dates=["signal_date"])
    events["symbol"] = events["symbol"].astype(str).str.upper()
    mac = pd.read_sql(
        "SELECT trade_date, mode, allow_new_entries FROM stock_macro_indicators_daily", engine
    )
    mac["trade_date"] = pd.to_datetime(mac["trade_date"]).dt.normalize()
    mac = mac.drop_duplicates("trade_date")
    events["regime_mode"] = events["signal_date"].map(dict(zip(mac["trade_date"], mac["mode"])))
    events["allow_new_entries"] = events["signal_date"].map(dict(zip(mac["trade_date"], mac["allow_new_entries"])))
    events["allow_new_entries"] = events["allow_new_entries"].where(
        events["allow_new_entries"].notna(),
        (~events["regime_mode"].isin(["close_only", "cash_only"])).astype(int),
    ).astype(bool)
    return events[events["allow_new_entries"]].reset_index(drop=True)


def _auc_for(y: np.ndarray, score: np.ndarray) -> float:
    return _auc_rank(y, score)


def _run_deltas(engine, smoke: bool = False) -> None:
    n_perm = 50 if smoke else N_PERM
    if smoke:
        _plog("== SMOKE DELTAS ==")
    events = _prod_universe(engine)
    _plog(f"univers PROD: {len(events)} événements")

    # ── Panneau quotidien des 15 features ──
    dip_symbols = sorted(events["symbol"].unique())
    bars = pd.read_sql(
        "SELECT symbol, date, open, high, low, close, adj_close, volume FROM stock_bars_daily "
        "WHERE data_source='eodhd_eod' AND symbol IN ({}) AND date BETWEEN %s AND %s".format(
            ",".join(["%s"] * len(dip_symbols))),
        engine, params=tuple(dip_symbols + [_BARS_START, _BARS_END]),
    )
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.drop_duplicates(subset=["symbol", "date"]).sort_values(["symbol", "date"])
    sym = _compute_bars_features(bars)
    _plog(f"daily symbol features: {len(sym)} lignes")

    mkt = _compute_market_features(engine)
    breadth, _rt, uni = _compute_breadth_ranks(engine, 3000)
    _meta, sec, _svs = _compute_sector_features(engine, uni)
    mkt = mkt.merge(breadth, on="date", how="left")
    mkt = mkt.sort_values("date").reset_index(drop=True)

    # ── Deltas daily ──
    for f in DELTA_SYM_FEATS:
        g = sym.groupby("symbol")[f]
        sym[f"{f}_delta_3"] = g.diff(3)
        sym[f"{f}_delta_5"] = g.diff(5)
        if f in PCT_CHANGE_FEATS:
            sym[f"{f}_pct5"] = g.pct_change(5)
    for f in DELTA_DATE_FEATS:
        mkt[f"{f}_delta_3"] = mkt[f].diff(3)
        mkt[f"{f}_delta_5"] = mkt[f].diff(5)
        if f in PCT_CHANGE_FEATS:
            mkt[f"{f}_pct5"] = mkt[f].pct_change(5, fill_method=None)
    for f in DELTA_SEC_FEATS:
        sec = sec.sort_values(["sector_name", "date"])
        g = sec.groupby("sector_name")[f]
        sec[f"{f}_delta_3"] = g.diff(3)
        sec[f"{f}_delta_5"] = g.diff(5)

    # ── Extraction aux événements DIP ──
    ev = events.copy()
    ev = ev.merge(sym[["date", "symbol"] + [f"{f}_delta_3" for f in DELTA_SYM_FEATS] +
                      [f"{f}_delta_5" for f in DELTA_SYM_FEATS] +
                      [f"{f}_pct5" for f in DELTA_SYM_FEATS if f in PCT_CHANGE_FEATS]],
                  left_on=["signal_date", "symbol"], right_on=["date", "symbol"], how="left")
    ev = ev.drop(columns=["date"], errors="ignore")
    ev = ev.merge(mkt[["date"] + [f"{f}_delta_3" for f in DELTA_DATE_FEATS] +
                      [f"{f}_delta_5" for f in DELTA_DATE_FEATS] +
                      [f"{f}_pct5" for f in DELTA_DATE_FEATS if f in PCT_CHANGE_FEATS]],
                  left_on="signal_date", right_on="date", how="left")
    ev = ev.drop(columns=["date"], errors="ignore")
    sec_map = sec[["date", "sector_name"] + [f"{f}_delta_3" for f in DELTA_SEC_FEATS] +
                  [f"{f}_delta_5" for f in DELTA_SEC_FEATS]]
    # secteur via features.csv (sector_name)
    feats_full = pd.read_csv(ARTIFACTS_DIR / "features.csv", parse_dates=["signal_date"])
    ev = ev.merge(feats_full[["signal_date", "symbol", "sector_name"]], on=["signal_date", "symbol"], how="left")
    ev = ev.merge(sec_map, left_on=["signal_date", "sector_name"], right_on=["date", "sector_name"], how="left")
    ev = ev.drop(columns=["date"], errors="ignore")

    # ── Labels ──
    fwd = ev["future_return_H20"]
    m = fwd.notna()
    y = (fwd[m] > 0).astype(int).to_numpy()
    extreme = ev.loc[m, "oracle_decile"].to_numpy()

    # ── Métriques par dérivé ──
    deriv_cols = [c for c in ev.columns if c.endswith("_delta_3") or c.endswith("_delta_5") or c.endswith("_pct5")]
    rows = []
    for c in deriv_cols:
        s = ev.loc[m, c]
        ok = s.notna()
        if ok.sum() < 200:
            rows.append({"derivative": c, "base_feature": c.rsplit("_delta_3", 1)[0].rsplit("_delta_5", 1)[0].rsplit("_pct5", 1)[0],
                         "coverage": float(ok.mean())})
            continue
        sc = s[ok].to_numpy(dtype=float)
        yy = y[ok]
        auc = _auc_for(yy, sc)
        dir_auc = max(auc, 1 - auc)
        ex_ok = extreme[ok]
        auc_ex = _auc_for((ex_ok >= 8).astype(int), sc)
        ic = _sstats.spearmanr(sc, ev.loc[m, "future_return_H20"].to_numpy()[ok]).statistic
        # stabilité par année (direction du signe de corrélation)
        dirs = []
        for yr in range(2022, 2026):
            yy_ = ev.loc[m, "signal_date"].dt.year == yr
            idx = ok & yy_
            if idx.sum() >= 50:
                dirs.append(1 if _auc_for(y[idx], s[idx].to_numpy(dtype=float)) > 0.5 else -1)
        overall = 1 if auc > 0.5 else -1
        sign_stab = float(np.mean([d == overall for d in dirs])) if dirs else np.nan
        # monotonicité quantiles
        try:
            qcut = pd.qcut(sc, 5, labels=False, duplicates="drop")
            mon = _sstats.spearmanr(qcut, ev.loc[m, "future_return_H20"].to_numpy()[ok]).statistic
        except ValueError:
            mon = np.nan
        rows.append({"derivative": c, "base_feature": c, "auc_win_loss": auc, "dir_auc": dir_auc,
                     "auc_extreme": auc_ex, "ic_h20": float(ic), "sign_stability": sign_stab,
                     "monotonicity": float(mon) if not pd.isna(mon) else np.nan,
                     "coverage": float(ok.mean())})
    deriv = pd.DataFrame(rows)
    # base_feature propre
    def _base(c):
        for b in DELTA_ALL:
            if c.startswith(b):
                return b
        return c
    deriv["base_feature"] = deriv["derivative"].map(_base)
    deriv = deriv.sort_values("dir_auc", ascending=False)
    deriv.to_csv(ANAL_DIR / "deltas_metrics.csv", index=False)
    _plog(f"métriques dérivés écrites ({len(deriv)})")

    # ── Permutation (max dir-AUC sur les dérivés) ──
    rng = np.random.default_rng(7)
    cols = [c for c in deriv_cols if ev.loc[m, c].notna().sum() >= 200]
    X = np.column_stack([ev.loc[m, c].to_numpy(dtype=float) for c in cols])
    null_max = []
    for _ in range(n_perm):
        yp = rng.permutation(y)
        aucs = []
        for j in range(X.shape[1]):
            col = X[:, j]; ok = ~np.isnan(col)
            if ok.sum() < 200 or len(np.unique(col[ok])) <= 1:
                continue
            aucs.append(max(_auc_for(yp[ok], col[ok]), 0.5))
        null_max.append(max([a for a in aucs if not np.isnan(a)]) if aucs else 0.5)
    null_max = np.array(null_max)
    p95 = np.percentile(null_max, 95)
    perm_map = {}
    for c in cols:
        ok = ~np.isnan(X[:, cols.index(c)])
        a = _auc_for(y[ok], X[:, cols.index(c)][ok])
        perm_map[c] = float(np.mean(null_max >= max(a, 1 - a)))
    deriv["perm_pvalue"] = deriv["derivative"].map(perm_map)
    deriv["null_p95"] = float(p95)
    deriv.to_csv(ANAL_DIR / "deltas_metrics.csv", index=False)
    _plog(f"permutation dérivés faite (null_p95={p95:.3f})")

    # ── Régression logistique nested/WF : static vs static+delta ──
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    static_cols = [f for f in DELTA_ALL if f in feats_full.columns]
    Xs = feats_full[["signal_date", "symbol"] + static_cols].merge(
        ev[["signal_date", "symbol"]], on=["signal_date", "symbol"], how="inner")
    Xs = Xs.merge(ev[["signal_date", "symbol"] + deriv_cols], on=["signal_date", "symbol"], how="left")
    Xs = Xs.merge(events[["signal_date", "symbol", "future_return_H20"]], on=["signal_date", "symbol"], how="left")
    Xs = Xs.sort_values("signal_date").reset_index(drop=True)
    Xs = Xs.replace([np.inf, -np.inf], np.nan)
    mm = Xs["future_return_H20"].notna()
    y_lr = (Xs.loc[mm, "future_return_H20"] > 0).astype(int).to_numpy()
    dates = Xs.loc[mm, "signal_date"].to_numpy()
    # folds chronologiques (5)
    qs = np.quantile(np.arange(len(y_lr)), [0.2, 0.4, 0.6, 0.8])
    bounds = [np.sort(dates)[int(q * (len(dates) - 1))] for q in [0.2, 0.4, 0.6, 0.8]]
    folds = []
    prev = pd.Timestamp.min
    for b in bounds + [pd.Timestamp.max]:
        mask = (dates >= prev) & (dates < b)
        if mask.sum() > 0:
            folds.append(np.where(mask)[0])
        prev = b
    # features utilisables (coverage >= 50% dans l'échantillon LR)
    feat_static = [c for c in static_cols if Xs.loc[mm, c].notna().mean() >= 0.5]
    delta_candidates = [c for c in deriv_cols if Xs.loc[mm, c].notna().mean() >= 0.5]
    # sélection des deltas ADD potentiels : perm p<0.2 et stabilité>=0.5
    add_pool = deriv[(deriv["perm_pvalue"] < 0.2) & (deriv["sign_stability"] >= 0.5)]["derivative"].tolist()
    add_pool = [c for c in add_pool if c in Xs.columns]
    scaler = StandardScaler()
    lr_rows = []
    fold_sign = {c: [] for c in add_pool}
    for i, fold in enumerate(folds):
        tr = np.setdiff1d(np.arange(len(y_lr)), fold)
        if len(tr) < 200 or len(fold) < 50:
            continue
        Xtr_s = Xs.loc[mm].iloc[tr][feat_static].to_numpy(dtype=float)
        Xte_s = Xs.loc[mm].iloc[fold][feat_static].to_numpy(dtype=float)
        Xtr_s = scaler.fit_transform(np.nan_to_num(Xtr_s, nan=0.0))
        Xte_s = scaler.transform(np.nan_to_num(Xte_s, nan=0.0))
        lr = LogisticRegression(max_iter=2000)
        lr.fit(Xtr_s, y_lr[tr])
        auc_s = _auc_for(y_lr[fold], lr.predict_proba(Xte_s)[:, 1])
        # static + deltas ADD
        feats_add = feat_static + [c for c in add_pool]
        Xtr_d = Xs.loc[mm].iloc[tr][feats_add].to_numpy(dtype=float)
        Xte_d = Xs.loc[mm].iloc[fold][feats_add].to_numpy(dtype=float)
        Xtr_d = scaler.fit_transform(np.nan_to_num(Xtr_d, nan=0.0))
        Xte_d = scaler.transform(np.nan_to_num(Xte_d, nan=0.0))
        lr2 = LogisticRegression(max_iter=2000)
        lr2.fit(Xtr_d, y_lr[tr])
        auc_d = _auc_for(y_lr[fold], lr2.predict_proba(Xte_d)[:, 1])
        lr_rows.append({"fold": i, "n_tr": int(len(tr)), "n_te": int(len(fold)),
                        "auc_static": auc_s, "auc_static_plus_delta": auc_d})
        # signe des coefs delta
        for j, c in enumerate(add_pool):
            fold_sign[c].append(np.sign(lr2.coef_[0][len(feat_static) + j]))
    lr_df = pd.DataFrame(lr_rows)
    lr_df.to_csv(ANAL_DIR / "logreg_static_vs_delta.csv", index=False)
    _plog("régression logistique nested/WF écrite")

    # ── Verdict ADD/REDUNDANT/NO_SIGNAL/UNSTABLE ──
    wf = lr_df["auc_static"].mean() if len(lr_df) else np.nan
    wf_plus = lr_df["auc_static_plus_delta"].mean() if len(lr_df) else np.nan
    add_rows = []
    for c in add_pool:
        perm_p = perm_map.get(c, np.nan)
        stab = deriv.set_index("derivative").loc[c, "sign_stability"] if c in deriv.set_index("derivative").index else np.nan
        signs = fold_sign.get(c, [])
        maj_sign = abs(sum(signs)) / len(signs) if signs else np.nan
        auc_d = deriv.set_index("derivative").loc[c, "dir_auc"] if c in deriv.set_index("derivative").index else np.nan
        if (perm_p < 0.05) and (maj_sign >= 0.6) and (wf_plus > wf + 1e-4):
            verdict = "ADD"
        elif perm_p >= 0.2 or (not pd.isna(stab) and stab < 0.5):
            verdict = "UNSTABLE" if (not pd.isna(stab) and stab < 0.5) else "NO_SIGNAL"
        else:
            verdict = "REDUNDANT"
        add_rows.append({"derivative": c, "dir_auc": auc_d, "perm_pvalue": perm_p,
                         "sign_stability": stab, "fold_majority_sign": maj_sign,
                         "verdict": verdict})
    add_df = pd.DataFrame(add_rows).sort_values("dir_auc", ascending=False)
    add_df.to_csv(ANAL_DIR / "deltas_verdicts.csv", index=False)
    _plog(f"verdicts dérivés: {add_df['verdict'].value_counts().to_dict()} | "
          f"WF static={wf:.4f} vs static+delta={wf_plus:.4f}")


def main() -> None:
    _quiet()
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="events", choices=["events", "features", "analyses", "deltas", "report"])
    parser.add_argument("--smoke", action="store_true", help="smoke test rapide (sous-ensemble minuscule)")
    args = parser.parse_args()

    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()

    if args.stage == "events":
        events = build_dip_events(engine)
        assert_events(events)
        events.to_csv(ARTIFACTS_DIR / "events.csv", index=False)
        print(f"saved: {ARTIFACTS_DIR / 'events.csv'} ({len(events)} rows)")

    elif args.stage == "features":
        events = pd.read_csv(ARTIFACTS_DIR / "events.csv", parse_dates=["signal_date"])
        events["symbol"] = events["symbol"].astype(str).str.upper()
        feats = build_features(engine, events, smoke=args.smoke)
        if not args.smoke:
            feats.to_csv(ARTIFACTS_DIR / "features.csv", index=False)
            _register_meta()
            pd.DataFrame(FEATURE_META).to_csv(ARTIFACTS_DIR / "feature_inventory.csv", index=False)
            print(f"saved: {ARTIFACTS_DIR / 'features.csv'} ({len(feats)} rows, {feats.shape[1]} cols)")
            print(f"inventaire: {len(FEATURE_META)} features")
        else:
            print("SMOKE OK — shape:", feats.shape)
            print("colonnes:", [c for c in feats.columns if c not in ("signal_date", "symbol")][:8], "...")

    elif args.stage == "analyses":
        _run_analyses(smoke=args.smoke)
        print("analyses terminées — voir artifacts/dip_context/analyses/")

    elif args.stage == "deltas":
        _run_deltas(engine, smoke=args.smoke)
        print("deltas (section 10) terminés — voir artifacts/dip_context/analyses/")

    elif args.stage == "report":
        # régénère uniquement le rapport depuis les CSV déjà produits
        from pathlib import Path as _P
        master = pd.read_csv(ANAL_DIR / "master_deliverable.csv")
        wl = pd.read_csv(ANAL_DIR / "stats_win_loss.csv")
        ex = pd.read_csv(ANAL_DIR / "stats_extreme.csv")
        q12 = pd.read_csv(ANAL_DIR / "q1_q2_2025.csv")
        ctx = pd.read_csv(ANAL_DIR / "context_market.csv")
        q_df = pd.read_csv(ANAL_DIR / "quantiles.csv")
        perm = pd.read_csv(ANAL_DIR / "permutation.csv")
        null_max = np.array([perm["null_p95"].iloc[0]])
        feats = master["feature"].tolist()
        _build_report(master, wl, ex, q12, ctx, null_max, q_df, feats)
        print("rapport régénéré")

    else:
        raise NotImplementedError(f"stage {args.stage} à implémenter")


if __name__ == "__main__":
    main()
