"""E6-A3 — Construction labels Y3 (path-success) — VERSION OPTIMISÉE pool O0.

Optimisation clé : ne simuler QUE les (symbol, date) du pool Oracle O0
(dataset E2 + O0 OOS, ~400 symboles / 326k lignes), PAS les 12 718 symboles
du cache complet. Réduit le travail ~30x.

Vectorisation par symbole : matrices numpy du futur (H20) au lieu de boucles
jour-par-jour en Python pour la détection TP/stop.

Politique gelée (H20) :
  stop = 3.5*ATR ; TP = min(4*ATR, 13%) ; trailing LONG 7% (activation 0 R) ; short sans trailing.

Usage :
    python -m scripts.e6_build_path_labels_v2
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
O0_OOS = Path("artifacts/models/oracle/oracle-wf-20260820025255/oos_predictions.parquet")
E2_DATASET = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OUT = Path("artifacts/models/oracle/e6_path_labels.parquet")

HORIZON = 20
STOP_MULT = 3.5
TP_ATR_MULT = 4.0
TP_MAX_PCT = 0.13
TRAILING_PCT_LONG = 0.07
ATR_WINDOW = 20


def _atr_np(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """ATR Wilder vectorisé."""
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    # EWM (alpha=1/20, adjust=False) ~ tr.ewm(alpha=1/w).mean()
    alpha = 1.0 / ATR_WINDOW
    out = np.empty_like(tr, dtype=float)
    out[0] = tr[0]
    for i in range(1, len(tr)):
        out[i] = alpha * tr[i] + (1 - alpha) * out[i - 1]
    return out


def simulate_symbol(
    sym_high: np.ndarray, sym_low: np.ndarray, sym_close: np.ndarray,
    sym_dates: np.ndarray, symbol: str,
) -> list[dict]:
    """Simule tous les chemins futurs H20 d'un symbole (vectorisé par date)."""
    n = len(sym_high)
    if n <= HORIZON:
        return []
    atr = _atr_np(sym_high, sym_low, sym_close)
    n_entries = n - HORIZON

    rows: list[dict] = []
    for i in range(n_entries):
        a = atr[i]
        entry = sym_close[i]
        if not (np.isfinite(a) and a > 0 and np.isfinite(entry) and entry > 0):
            continue

        fut_h = sym_high[i + 1:i + 1 + HORIZON]
        fut_l = sym_low[i + 1:i + 1 + HORIZON]
        fut_c = sym_close[i + 1:i + 1 + HORIZON]

        # ── LONG ──
        stop_l = entry - STOP_MULT * a
        tp_l = min(entry + TP_ATR_MULT * a, entry * (1 + TP_MAX_PCT))
        peak, trailing = 0.0, 0.0
        l_ok, l_reason, l_ret, l_mfe, l_mae = 0, "eod", 0.0, 0.0, 0.0
        for j in range(HORIZON):
            h, l, c = fut_h[j], fut_l[j], fut_c[j]
            if h >= entry:
                peak = max(peak, h)
                trailing = peak * (1 - TRAILING_PCT_LONG)
            eff_stop = trailing if trailing > entry else stop_l
            l_mae = min(l_mae, (l - entry) / entry)
            l_mfe = max(l_mfe, (h - entry) / entry)
            if l <= eff_stop:
                l_ok, l_reason, l_ret = 0, "stop", (eff_stop - entry) / entry
                break
            if h >= tp_l:
                l_ok, l_reason, l_ret = 1, "tp", (tp_l - entry) / entry
                break
            if trailing > entry and c <= trailing:
                l_ok, l_reason, l_ret = 0, "trailing", (c - entry) / entry
                break
        else:
            l_ok, l_reason, l_ret = (1 if fut_c[-1] > entry else 0), "eod", (fut_c[-1] - entry) / entry

        # ── SHORT ──
        stop_s = entry + STOP_MULT * a
        tp_s = max(entry - TP_ATR_MULT * a, entry * (1 - TP_MAX_PCT))
        s_ok, s_reason, s_ret, s_mfe, s_mae = 0, "eod", 0.0, 0.0, 0.0
        for j in range(HORIZON):
            h, l, c = fut_h[j], fut_l[j], fut_c[j]
            s_mfe = max(s_mfe, (entry - l) / entry)
            s_mae = min(s_mae, (entry - h) / entry)
            if h >= stop_s:
                s_ok, s_reason, s_ret = 0, "stop", (stop_s - entry) / entry
                break
            if l <= tp_s:
                s_ok, s_reason, s_ret = 1, "tp", (tp_s - entry) / entry
                break
        else:
            s_ok, s_reason, s_ret = (1 if entry > fut_c[-1] else 0), "eod", (entry - fut_c[-1]) / entry

        rows.append({
            "symbol": symbol, "date": sym_dates[i],
            "atr20": float(a), "entry": float(entry),
            "y3_long": int(l_ok), "y3_long_reason": l_reason,
            "y3_long_ret": float(l_ret), "y3_long_mfe": float(l_mfe), "y3_long_mae": float(l_mae),
            "y3_short": int(s_ok), "y3_short_reason": s_reason,
            "y3_short_ret": float(s_ret), "y3_short_mfe": float(s_mfe), "y3_short_mae": float(s_mae),
        })
    return rows


def main() -> None:
    print("=== Load pool Oracle O0 (symbols+dates) ===", flush=True)
    # Le pool = les (symbol, date) du dataset E2 (features déjà alignées)
    e2 = pd.read_parquet(E2_DATASET, columns=["symbol", "date"])
    e2["date"] = pd.to_datetime(e2["date"]).dt.normalize()
    pool_dates = set(zip(e2["symbol"].astype(str), e2["date"]))
    pool_symbols = sorted(e2["symbol"].astype(str).unique())
    print(f"pool: {len(pool_dates)} (symbol,date) | {len(pool_symbols)} symbols", flush=True)

    print("=== Load OHLCV cache ===", flush=True)
    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "high", "low", "close"])
    bars = bars[bars["symbol"].isin(pool_symbols)].copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    bars = bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    print(f"cache filtré: {len(bars)} rows | {bars['symbol'].nunique()} symbols", flush=True)

    all_rows: list[dict] = []
    total_sym = len(pool_symbols)
    for s_idx, symbol in enumerate(pool_symbols):
        if s_idx % 100 == 0:
            print(f"  symbol {s_idx}/{total_sym} ({symbol}) rows_so_far={len(all_rows)}", flush=True)
        sym_df = bars[bars["symbol"] == symbol].sort_values("trade_date")
        if sym_df.empty or len(sym_df) <= HORIZON:
            continue
        dates = sym_df["trade_date"].to_numpy()
        rows = simulate_symbol(
            sym_df["high"].to_numpy(dtype=float),
            sym_df["low"].to_numpy(dtype=float),
            sym_df["close"].to_numpy(dtype=float),
            dates, symbol,
        )
        # Filtrer aux dates du pool Oracle (économie mémoire + cohérence)
        rows = [r for r in rows if (r["symbol"], pd.Timestamp(r["date"])) in pool_dates]
        if rows:
            all_rows.extend(rows)

    out = pd.DataFrame(all_rows)
    out.to_parquet(OUT, index=False)
    print(f"\nSaved {len(out)} rows -> {OUT}", flush=True)
    print(f"y3_long mean={out['y3_long'].mean():.4f} | y3_short mean={out['y3_short'].mean():.4f}", flush=True)
    print(f"y3_long reasons: {out['y3_long_reason'].value_counts().to_dict()}", flush=True)
    print(f"y3_short reasons: {out['y3_short_reason'].value_counts().to_dict()}", flush=True)


if __name__ == "__main__":
    main()
