"""modelFactory/global_direction/persistent_top10_dip_portfolio.py — Phase 2 portefeuille.

Backtest de portefeuille des signaux DIP avec **lifecycle PROD inchangé**
(sizing / TP / stop / coûts / max_positions / CP / breaker / force-close) :
``BacktestEngine`` + ``BacktestConfig`` répliquant les paramètres de la commande
pipeline PROD de référence.

Variantes (configurations pré-enregistrées, AUCUN sweep) :
- P0      = TOP10 global_rank (sans filtre DIP) — BASE
- P1      = persistent TOP10 (N=4) ET ret_4 <= −2%  (DIP)
- P1b     = persistent TOP10 (N=4) ET ret_4 <= −3%  (challenger pré-identifié)
- P2      = P1 + veto close_only (aucune entrée si régime du jour == close_only)

Signal calculé au close J ; entrée selon le contrat d'exécution PROD (J+1 open).

Mesures : CAGR/total return, Sharpe, Sortino, MaxDD, PF, win rate, médiane/moyenne
de trade, nb trades exécutés, exposure, turnover, capital utilization + attributs
de signaux (raw DIP, épisodes uniques, rejets, entrées/mois, % jours sous-rempli)
+ attribution par régime d'entrée (normal/cash_only/capital_preservation/close_only).

NB : P2 ne doit PAS être déclaré « validé OOS » sur 2022-24 (le veto a été
découvert sur ces mêmes données).

Usage :
    python -m modelFactory.global_direction.persistent_top10_dip_portfolio --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from backtesting.simulator import BacktestConfig, BacktestEngine
from backtesting.trading_constraints import build_current_trading_constraints
from backtesting.risk_overlay import (
    DrawdownCircuitBreaker,
    RiskOverlayConfig,
    SectoralCapConfig,
    SizingConfig,
    RegimeFilterConfig,
    BullStrictConfig,
)
from risk_management.config import RiskConfig
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.oracle.dataset import load_oracle_targets

LOGGER = logging.getLogger(__name__)

RANK_COL = "global_rank_20"
TOP10 = 0.90
N_DIP = 4
X_DIP = 0.02
X_DIP_B = 0.03

_FOLD_CUTS = [pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01"),
              pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")]


def _load_regime_map() -> dict[pd.Timestamp, str]:
    m: dict[pd.Timestamp, str] = {}
    rfile = Path("regime_marche/regime.ttx")
    if not rfile.exists():
        return m
    with open(rfile, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i == 0 or not line.strip():
                continue
            parts = line.strip().split(",", 3)
            if len(parts) < 3:
                continue
            try:
                s = pd.Timestamp(parts[0].strip()).normalize()
                e = pd.Timestamp(parts[1].strip()).normalize()
                rg = str(parts[2]).strip().lower()
                cur = s
                while cur <= e:
                    m[cur] = rg
                    cur += pd.Timedelta(days=1)
            except Exception:
                continue
    return m


def load_regime_map_db(engine: Any) -> dict[pd.Timestamp, str]:
    """Date (normalisée) → mode depuis ``stock_macro_indicators_daily``.

    Source de vérité du régime PROD (alimentée en continu, couvre 2026) —
    ``mode`` + ``allow_new_entries`` du jour. Les dates absentes de la table
    retombent sur ``regime.ttx`` (rétro-compat 2020-2025).
    """
    m = _load_regime_map()  # base ttx (dates absentes de la table)
    try:
        df = pd.read_sql(
            "SELECT trade_date, mode, allow_new_entries FROM stock_macro_indicators_daily "
            "ORDER BY trade_date",
            engine,
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
        for _, r in df.iterrows():
            td = r["trade_date"]
            if pd.isna(td):
                continue
            mode = str(r.get("mode") or "").strip().lower()
            allow = bool(r.get("allow_new_entries"))
            if not mode:
                continue
            # Si allow_new_entries=False et mode pas déjà bloquant, on force
            # close_only/cash_only selon le mode (parité avec regime PROD).
            m[pd.Timestamp(td).normalize()] = mode
    except Exception as exc:  # noqa: BLE001 — non bloquant
        LOGGER.warning("load_regime_map_db échoué (%s) — fallback ttx seul", exc)
    return m


def build_signals(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Signaux par variante : trade_date, symbol, selected, rank + contexte."""
    rank = pd.read_sql(
        f"SELECT symbol, date, {RANK_COL} FROM global_rank_history WHERE date BETWEEN %s AND %s",
        engine, params=(start_date, end_date),
    )
    rank["date"] = pd.to_datetime(rank["date"], errors="coerce").dt.normalize()
    rank["symbol"] = rank["symbol"].astype(str).str.upper()

    lb = (pd.Timestamp(start_date) - pd.Timedelta(days=20)).date().isoformat()
    bars = pd.read_sql(
        "SELECT symbol, date, close, adj_close FROM stock_bars_daily WHERE date BETWEEN %s AND %s",
        engine, params=(lb, end_date),
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "close"])

    df = rank.merge(bars[["symbol", "date", "adj_close"]], on=["date", "symbol"], how="left")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df["top10"] = (df[RANK_COL] >= TOP10).astype(int)
    g_close = df.groupby("symbol")["adj_close"]
    df["ret_4"] = df["adj_close"] / g_close.shift(N_DIP) - 1.0
    df["persist_4"] = df.groupby("symbol")["top10"].transform(
        lambda x: x.rolling(N_DIP, min_periods=N_DIP).min())
    reg_map = _load_regime_map()
    df["regime"] = df["date"].map(reg_map).fillna("unknown")

    out: dict[str, pd.DataFrame] = {}
    base = df[(df["top10"] == 1)].copy()
    dip2 = df[(df["persist_4"] == 1) & (df["ret_4"] <= -X_DIP)].copy()
    dip3 = df[(df["persist_4"] == 1) & (df["ret_4"] <= -X_DIP_B)].copy()
    dip2_no_close = dip2[dip2["regime"] != "close_only"].copy()

    def _sig(frame: pd.DataFrame, name: str) -> pd.DataFrame:
        s = pd.DataFrame({
            "trade_date": frame["date"],
            "symbol": frame["symbol"],
            "selected": True,
            "rank": frame[RANK_COL].astype(float),
            # score = global_rank (>= 0.90) : passe le seuil PROD min_score_threshold=0.7
            # (Quick Win 2) sans modifier le lifecycle.
            "score": frame[RANK_COL].astype(float),
            "regime": frame["regime"].values,
        })
        s["variant"] = name
        return s

    return pd.concat([
        _sig(base, "P0"),
        _sig(dip2, "P1"),
        _sig(dip3, "P1b"),
        _sig(dip2_no_close, "P2"),
    ], ignore_index=True)


def _pivot(bars: pd.DataFrame, col: str) -> pd.DataFrame:
    return bars.pivot_table(index="trade_date", columns="symbol", values=col, aggfunc="last")


def load_ohlcv_pivots(engine: Any, start_date: str, end_date: str, symbols: list[str]) -> dict[str, pd.DataFrame]:
    lb = (pd.Timestamp(start_date) - pd.Timedelta(days=25)).date().isoformat()
    ph = ",".join(["%s"] * len(symbols))
    df = pd.read_sql(
        f"SELECT symbol, date, open, high, low, close, volume FROM stock_bars_daily "
        f"WHERE symbol IN ({ph}) AND date BETWEEN %s AND %s",
        engine, params=(*symbols, lb, end_date),
    )
    df["trade_date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return {c: _pivot(df.dropna(subset=[c]), c) for c in ["open", "high", "low", "close", "volume"]}


def build_config(start_date: str, end_date: str) -> BacktestConfig:
    """Réplique les paramètres de la commande pipeline PROD de référence."""
    return BacktestConfig(
        start_date=pd.Timestamp(start_date).date(), end_date=pd.Timestamp(end_date).date(),
        initial_equity=4000.0,
        risk_config=RiskConfig(account_equity=4000.0, max_positions=20, allow_fractional_shares=True),
        profit_taker_pct=0.0,
        trailing_stop_pct=0.0,
        use_live_protection_logic=True,
        atr_risk_stop_multiple=2.5,
        tp_atr_multiple=3.0,
        tp_max_pct=0.07,
        use_canonical_costs=True,
        commission_bps=1.0,
        slippage_bps=2.0,
        margin_interest_rate_annual=0.075,
        max_positions=20,
        trading_constraints=build_current_trading_constraints(
            account_type="margin", swing_only=False, cash_settlement_days=1),
        execution_timing="next_open",
        risk_overlay=RiskOverlayConfig(
            sizing=SizingConfig(mode="equal_weight", min_weight_pct=0.0, max_weight_pct=0.0,
                                sector_multipliers=None, sector_map=None),
            regime_filter=RegimeFilterConfig(enabled=False, sma_window=0, bear_threshold=0.0),
            bull_strict=BullStrictConfig(enabled=False, mode="no_shorts", sma_window=200,
                                         ret_window=60, ret_threshold=0.03),
            sectoral_cap=SectoralCapConfig(enabled=True, max_sector_exposure_pct=0.50),
            drawdown_breaker=DrawdownCircuitBreaker(
                enabled=True, max_dd_pct=0.15, recovery_pct=0.92,
                rolling_peak_window_days=126, degraded_entry_allocation_pct=0.0,
                regime_ramp_up_enabled=False, regime_ramp_up_pct_per_day=0.0,
                regime_ramp_up_max_pct=0.0, regime_ramp_up_peak_window_days=5,
                policy="b0", spy_regime_map=None,
                force_close_on_breaker=False, force_close_pct=0.50,
                force_close_losers_on_breaker=False,
                research_force_close_at_dd_pct=None, research_force_close_side=None,
            ),
            target_annual_vol=0.13,
        ),
    )


def _enrich_atr(signals: pd.DataFrame, pivots: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """atr_pct_20 PIT à la date du signal (miroir du fix CLI prod)."""
    s = signals.copy()
    s["atr_pct_20"] = np.nan
    try:
        atr_usd = BacktestEngine._compute_atr(pivots["high"], pivots["low"], pivots["close"], window=20)
        atr_pct = atr_usd / pivots["close"].replace(0, np.nan)
        missing = s["atr_pct_20"].isna()
        dates = pd.to_datetime(s.loc[missing, "trade_date"]).dt.normalize()
        syms = s.loc[missing, "symbol"].astype(str)
        cols = [c for c in atr_pct.columns if c in set(syms)]
        if cols:
            st = atr_pct[cols].stack()
            st.index = st.index.set_names(["date", "symbol"])
            look = st.reindex(pd.MultiIndex.from_arrays([dates, syms]))
            s.loc[missing, "atr_pct_20"] = look.to_numpy()
    except Exception as exc:  # noqa: BLE001 — non bloquant
        LOGGER.warning("atr_pct_20 fallback OHLCV échoué : %s", exc)
    return s


def run_variant(engine: Any, signals: pd.DataFrame, pivots: dict[str, pd.DataFrame],
                start_date: str, end_date: str, name: str) -> dict[str, Any]:
    cfg = build_config(start_date, end_date)
    eng = BacktestEngine(cfg)
    signals = _enrich_atr(signals, pivots)
    res = eng.run(
        open_df=pivots["open"], close=pivots["close"], high=pivots["high"], low=pivots["low"],
        volume=pivots.get("volume"), signals_df=signals,
    )
    return {"name": name, "config": cfg, "result": res, "signals": signals}


def _metrics(res: Any, raw_signals: pd.DataFrame, reg_map: dict[pd.Timestamp, str],
             variant: str) -> dict[str, Any]:
    eq = res.equity_curve
    trades = res.closed_trades_df.copy() if res.closed_trades_df is not None and not res.closed_trades_df.empty \
        else pd.DataFrame()
    init = 4000.0
    final = res.final_value()
    n_days = max(1, int(len(eq)))
    years = n_days / 252.0
    total_ret = final / init - 1.0
    cagr = (final / init) ** (1.0 / years) - 1.0 if final > 0 else -1.0
    daily = eq.pct_change().dropna()
    sharpe = float(daily.mean() / daily.std() * np.sqrt(252)) if len(daily) > 1 and daily.std() > 0 else None
    downside = daily[daily < 0]
    sortino = float(daily.mean() / downside.std() * np.sqrt(252)) if len(downside) > 1 and downside.std() > 0 else None
    dd = (eq / eq.cummax() - 1.0)
    maxdd = float(dd.min()) if len(dd) else None
    if not trades.empty:
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] < 0]
        pf = float(wins["pnl"].sum() / abs(losses["pnl"].sum())) if len(losses) and losses["pnl"].sum() != 0 else None
        win_rate = float((trades["pnl"] > 0).mean())
        med_trade = float(trades["return_pct"].median())
        avg_trade = float(trades["return_pct"].mean())
        n_trades = int(len(trades))
    else:
        pf = win_rate = med_trade = avg_trade = None
        n_trades = 0
    # exposure / turnover / capital utilization
    if not trades.empty and "entry_date" in trades.columns and "exit_date" in trades.columns:
        in_market = pd.Series(0, index=eq.index, dtype=float)
        for _, t in trades.iterrows():
            mask = (eq.index >= pd.Timestamp(t["entry_date"])) & (eq.index <= pd.Timestamp(t["exit_date"]))
            in_market[mask] += 1.0
        exposure = float((in_market > 0).mean())
        avg_slots = float(in_market.mean())
        cap_util = float((in_market / 20.0).mean())
    else:
        exposure = avg_slots = cap_util = None
    # stats signaux
    raw_n = int(len(raw_signals))
    if not trades.empty and "symbol" in trades.columns:
        unique_entries = int(trades["symbol"].nunique())
        executed_months = n_trades / max(1.0, len(pd.to_datetime(trades["entry_date"]).dt.to_period("M").unique()))
    else:
        unique_entries = 0
        executed_months = None
    # % jours portfolio underfilled (< 20 positions)
    underfilled = None
    if not trades.empty and "entry_date" in trades.columns:
        underfilled = float((in_market < 20).mean())
    m = {
        "variant": variant, "total_return": total_ret, "cagr": cagr,
        "sharpe": sharpe, "sortino": sortino, "maxdd": maxdd,
        "pf": pf, "win_rate": win_rate, "median_trade_pct": med_trade,
        "avg_trade_pct": avg_trade, "n_trades": n_trades,
        "exposure": exposure, "avg_open_slots": avg_slots, "cap_utilization": cap_util,
        "raw_signals": raw_n, "unique_entries": unique_entries,
        "executed_entries_month": executed_months, "pct_days_underfilled": underfilled,
    }
    # attribution par régime d'entrée
    if not trades.empty and "entry_date" in trades.columns:
        td = trades.copy()
        td["entry_date"] = pd.to_datetime(td["entry_date"]).dt.normalize()
        td["regime"] = td["entry_date"].map(reg_map).fillna("unknown")
        for rg, g in td.groupby("regime"):
            w = g[g["pnl"] > 0]; l = g[g["pnl"] < 0]
            pf_r = float(w["pnl"].sum() / abs(l["pnl"].sum())) if len(l) and l["pnl"].sum() != 0 else None
            m[f"regime_{rg}_n"] = int(len(g))
            m[f"regime_{rg}_avg_pnl"] = float(g["pnl"].mean())
            m[f"regime_{rg}_pf"] = pf_r
            m[f"regime_{rg}_win"] = float((g["pnl"] > 0).mean())
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description="persistent_top10_dip portfolio (Phase 2).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--out", default="artifacts/persistent_top10_dip_portfolio.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()
    reg_map = _load_regime_map()

    all_signals = build_signals(engine, batch_id, args.start_date, args.end_date)
    symbols = sorted(all_signals["symbol"].unique())
    pivots = load_ohlcv_pivots(engine, args.start_date, args.end_date, symbols)
    LOGGER.info("symboles OHLCV : %d ; signaux totaux : %d", len(symbols), len(all_signals))

    rows: list[dict[str, Any]] = []
    for name in ["P0", "P1", "P1b", "P2"]:
        sig = all_signals[all_signals["variant"] == name][["trade_date", "symbol", "selected", "rank", "score"]]
        sig = sig[sig["symbol"].isin(pivots["close"].columns)].copy()
        LOGGER.info("=== Variante %s : %d signaux bruts ===", name, len(sig))
        r = run_variant(engine, sig, pivots, args.start_date, args.end_date, name)
        m = _metrics(r["result"], sig, reg_map, name)
        rows.append(m)
        pd.set_option("display.width", 260); pd.set_option("display.max_columns", None)
        print(pd.DataFrame([m]).to_string(index=False))

    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(f"\n→ CSV : {args.out}")


if __name__ == "__main__":
    main()
