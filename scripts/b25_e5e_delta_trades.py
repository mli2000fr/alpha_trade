"""E5-E — Diagnostic causal: ΔPnL(4x13 − 3x7) par trade, joint par séquence d'entrées.

Approche :
- Charge les trades fermés (replay_exit_reason notna) des runs 3x7 et 4x13.
- Match par (symbol, side, seq) où seq = nième entrée ordonnée par entry_date.
  Les entrées sont identiques entre les deux politiques (même cascade/risk) —
  seules les SORTIES diffèrent (TP 7% vs 13%). Delta = PnL(4x13) - PnL(3x7).
- Calcule des features PIT (connues à l'entrée) par trade.
- Agrége ΔPnL par régime PIT, et par période — pour voir si le pattern
  2024H1 se retrouve ailleurs (gate anti-overfit).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "f:/projets")

ROOT = Path("artifacts/backtesting")
OHLCV_CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")

RUNS = {
    "2022": {"3x7": "cmp_b25_h20_2022_postfix_tp_m8", "4x13": "cmp_b25_h20_2022_tp4x13_m8"},
    "2023": {"3x7": "cmp_b25_h20_2023h1_postfix_tp_m8", "4x13": "cmp_b25_h20_2023h1_tp4x13_m8"},
    "2024": {"3x7": "cmp_b25_h20_2024h1_postfix_tp_m8", "4x13": "cmp_b25_h20_2024h1_tp4x13_m8"},
    "2025": {"3x7": "cmp_b25_h20_2025_postfix_tp_m8", "4x13": "cmp_b25_h20_2025_tp4x13_m8"},
    "2026": {"3x7": "cmp_b25_h20_2026_postfix_tp_m8", "4x13": "cmp_b25_h20_2026_tp4x13_m8"},
}
PERIOD_LABEL = {"2022": "2022", "2023": "2023 H1", "2024": "2024 H1", "2025": "2025", "2026": "2026 H1"}


def load_trades(period: str, variant: str) -> pd.DataFrame:
    name = RUNS[period][variant]
    df = pd.read_csv(ROOT / name / "trade_audit_log.csv")
    df = df[df["replay_exit_reason"].notna()].copy()
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    if "replay_exit_date" in df.columns:
        df["exit_date"] = pd.to_datetime(df["replay_exit_date"])
    elif "exit_date" in df.columns:
        df["exit_date"] = pd.to_datetime(df["exit_date"])
    else:
        df["exit_date"] = df["entry_date"]
    # Agréger par cohorte (symbol, side, entry_date) : somme PnL de toutes les
    # entrées du même jour — évite le matching instance fragile des réentrées.
    agg = (
        df.groupby(["symbol", "side", "entry_date"], as_index=False)
        .agg(
            pnl=("pnl", "sum"),
            return_pct=("return_pct", "mean"),
            holding_days=("holding_days", "mean"),
            n_entries=("pnl", "size"),
            exit_reason=("replay_exit_reason", lambda s: s.mode().iloc[0] if len(s) else ""),
            sector=("sector", "first"),
        )
    )
    agg = agg.sort_values(["symbol", "side", "entry_date"]).reset_index(drop=True)
    return agg


def load_bars() -> dict[str, pd.DataFrame]:
    df = pd.read_parquet(OHLCV_CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    out = {}
    for sym, g in df.groupby("symbol"):
        out[sym] = g.sort_values("trade_date").reset_index(drop=True)
    return out


def compute_pit_features(entry_date: pd.Timestamp, symbol: str, bars: dict[str, pd.DataFrame]) -> dict:
    """Features connues à la date d'entrée (fermeture J-1 / ouverture J)."""
    feats: dict[str, float] = {}

    def _series(sym: str):
        b = bars.get(sym)
        return b if b is not None and len(b) else None

    # SPY features
    spy = _series("SPY")
    if spy is not None:
        spy_pre = spy[spy["trade_date"] <= entry_date]
        c = spy_pre["close"]
        if len(c) >= 60:
            spy_ret5 = c.iloc[-1] / c.iloc[-6] - 1
            spy_ret20 = c.iloc[-1] / c.iloc[-21] - 1
            spy_ret60 = c.iloc[-1] / c.iloc[-61] - 1
            sma50 = c.iloc[-50:].mean()
            sma200 = c.iloc[-200:].mean()
            vol20 = c.iloc[-20:].pct_change().std()
            feats["spy_ret_5"] = spy_ret5
            feats["spy_ret_20"] = spy_ret20
            feats["spy_ret_60"] = spy_ret60
            feats["spy_above_sma50"] = 1.0 if c.iloc[-1] > sma50 else 0.0
            feats["spy_above_sma200"] = 1.0 if c.iloc[-1] > sma200 else 0.0
            feats["spy_sma50_gap"] = c.iloc[-1] / sma50 - 1
            feats["spy_vol20"] = vol20

    # ATR + momentum du titre
    b = _series(symbol)
    if b is not None:
        pre = b[b["trade_date"] <= entry_date]
        if len(pre) >= 20:
            h, l, c = pre["high"].astype(float), pre["low"].astype(float), pre["close"].astype(float)
            tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
            atr20 = tr.iloc[-20:].mean()
            atr_pct = atr20 / c.iloc[-1] if c.iloc[-1] else np.nan
            mom20 = c.iloc[-1] / c.iloc[-21] - 1
            mom60 = c.iloc[-1] / c.iloc[-61] - 1 if len(pre) >= 61 else np.nan
            vol20 = c.iloc[-20:].pct_change().std()
            sma50 = c.iloc[-50:].mean() if len(pre) >= 50 else np.nan
            feats["atr_pct_20"] = atr_pct
            feats["mom_20"] = mom20
            feats["mom_60"] = mom60
            feats["vol20"] = vol20
            feats["above_sma50"] = 1.0 if (c.iloc[-1] > sma50 and not pd.isna(sma50)) else 0.0
            feats["ret_5"] = c.iloc[-1] / c.iloc[-6] - 1 if len(pre) >= 6 else np.nan

    return feats


def main() -> None:
    bars = load_bars()
    print(f"bars chargées: {len(bars)} symboles (SPY={'SPY' in bars})")

    all_trades: list[pd.DataFrame] = []
    for period in RUNS:
        a = load_trades(period, "3x7")
        b = load_trades(period, "4x13")
        m = a.merge(b, on=["symbol", "side", "entry_date"], suffixes=("_37", "_413"), how="inner")
        if len(m) == 0:
            print(f"{period}: AUCUN match")
            continue
        m["period"] = period
        m["delta"] = m["pnl_413"] - m["pnl_37"]
        m["side"] = m["side"]
        m["symbol"] = m["symbol"]
        m["sector"] = m["sector_37"]
        m["exit_reason_37"] = m["exit_reason_37"]
        m["exit_reason_413"] = m["exit_reason_413"]
        m["n_entries_37"] = m["n_entries_37"]
        m["n_entries_413"] = m["n_entries_413"]
        print(f"{PERIOD_LABEL[period]}: cohortes_matchées={len(m)} "
              f"delta_sum={m['delta'].sum():.0f} mean={m['delta'].mean():.1f} "
              f"pct_neg={(m['delta'] < 0).mean():.1%}")

        # Features PIT à l'entrée
        pit = []
        for _, row in m.iterrows():
            feats = compute_pit_features(row["entry_date"], row["symbol"], bars)
            pit.append(feats)
        pit_df = pd.DataFrame(pit, index=m.index)
        m = pd.concat([m, pit_df], axis=1)
        all_trades.append(m)

    if not all_trades:
        print("AUCUNE donnée")
        return
    full = pd.concat(all_trades, ignore_index=True)
    out_path = "artifacts/models/oracle/e5e_delta_by_trade.parquet"
    full.to_parquet(out_path, index=False)
    print(f"\nTotal trades matchés: {len(full)} → {out_path}")
    print("Colonnes PIT dispo:", [c for c in full.columns if c not in ("symbol", "side") and "_37" not in c and "_413" not in c][:30])


if __name__ == "__main__":
    main()
