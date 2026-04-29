"""Phase 4 EODHD - Audit ratio volume EODHD vs Alpaca-IEX.

Plan ``prompt/iex/plan_eodhd.md`` §6 Phase 4. **Critère go/no-go** :
- ratio médian ``volume_eodhd_eod / volume_alpaca_iex`` in [10, 50] sur S&P 100,
- 0 large cap (mc > 10 G$) rejetée à tort par
  ``min_avg_dollar_volume_20d=30_000_000`` quand on bascule la source.

Pré-requis : Phase 3 a déjà tourné en mode ``--write`` au moins quelques fois,
donc des lignes ``data_source='eodhd_eod'`` cohabitent dans ``stock_bars_daily``
avec les lignes historiques ``data_source='alpaca_iex'``.

Sortie : JSON dans ``artifacts/eodhd_cache/phase4_volume_audit_<TS>.json``.

Usage::

    python scripts/eodhd_phase4_volume_audit.py
    python scripts/eodhd_phase4_volume_audit.py --lookback-days 60
    python scripts/eodhd_phase4_volume_audit.py --symbols AAPL NVDA META
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 60
RATIO_MIN_OK = 10.0
RATIO_MAX_OK = 50.0
LARGE_CAP_USD = 10_000_000_000
MIN_AVG_DOLLAR_VOLUME_20D = 30_000_000

DEFAULT_OUT_DIR = Path("artifacts") / "eodhd_cache"

SP100_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "BRK.B",
    "AVGO", "JPM", "LLY", "UNH", "V", "WMT", "XOM", "MA", "PG", "JNJ", "HD",
    "ORCL", "COST", "BAC", "ABBV", "KO", "MRK", "PEP", "ADBE", "CVX", "CSCO",
    "ACN", "TMO", "MCD", "CRM", "WFC", "ABT", "LIN", "DHR", "NFLX", "TXN",
    "CMCSA", "AMD", "VZ", "DIS", "PM", "INTU", "INTC", "QCOM", "PFE", "AMGN",
    "MS", "T", "CAT", "GS", "RTX", "SPGI", "AXP", "LOW", "BLK", "NEE",
    "BKNG", "C", "MDT", "GE", "BA", "PLD", "TJX", "ISRG", "DE", "UNP",
    "ADP", "VRTX", "LMT", "GILD", "CI", "SBUX", "AMT", "MMC", "BMY", "ELV",
    "MO", "REGN", "NOW", "SCHW", "USB", "PYPL", "ZTS", "BSX", "TGT", "DUK",
    "AON", "ETN", "EOG", "SO", "FDX", "ITW", "WM", "EMR", "PNC", "F",
]


def _fetch_pairs_from_db(session, symbols, start_date, end_date):
    from sqlalchemy import bindparam, text
    sql = text(
        """
        SELECT a.symbol, a.`date`,
               a.volume AS vol_alpaca, e.volume AS vol_eodhd,
               a.close  AS close_alpaca, e.close  AS close_eodhd
        FROM stock_bars_daily AS a
        JOIN stock_bars_daily AS e
          ON e.symbol = a.symbol AND e.`date` = a.`date`
        WHERE a.data_source = 'alpaca_iex'
          AND e.data_source = 'eodhd_eod'
          AND a.symbol IN :symbols
          AND a.`date` BETWEEN :start_date AND :end_date
        """
    ).bindparams(bindparam("symbols", expanding=True))
    rows = session.execute(
        sql, {"symbols": symbols, "start_date": start_date, "end_date": end_date}
    ).mappings().all()
    return [dict(r) for r in rows]


def _fetch_market_caps(session, symbols):
    from sqlalchemy import bindparam, text
    sql = text(
        "SELECT symbol, market_cap FROM stock_metadata "
        "WHERE symbol IN :symbols AND market_cap IS NOT NULL"
    ).bindparams(bindparam("symbols", expanding=True))
    return {
        row["symbol"]: float(row["market_cap"])
        for row in session.execute(sql, {"symbols": symbols}).mappings().all()
    }


def compute_volume_ratios(pairs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in pairs:
        v_a = float(r.get("vol_alpaca") or 0)
        v_e = float(r.get("vol_eodhd") or 0)
        if v_a <= 0:
            continue
        d = r.get("date")
        out.append({
            "symbol": r["symbol"],
            "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
            "vol_alpaca": v_a, "vol_eodhd": v_e, "ratio": v_e / v_a,
        })
    return out


def aggregate_by_symbol(ratios):
    by_symbol: dict[str, list[float]] = {}
    for r in ratios:
        by_symbol.setdefault(r["symbol"], []).append(r["ratio"])
    return {
        sym: {
            "median_ratio": statistics.median(values),
            "p25_ratio": _percentile(values, 25),
            "p75_ratio": _percentile(values, 75),
            "n_days": len(values),
        }
        for sym, values in by_symbol.items() if values
    }


def _percentile(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def compute_avg_dollar_volume_20d(pairs, source: str):
    by_symbol: dict[str, list[tuple[float, float]]] = {}
    for r in pairs:
        if source == "alpaca":
            vol = float(r.get("vol_alpaca") or 0)
            close = float(r.get("close_alpaca") or 0)
        else:
            vol = float(r.get("vol_eodhd") or 0)
            close = float(r.get("close_eodhd") or 0)
        if vol <= 0 or close <= 0:
            continue
        by_symbol.setdefault(r["symbol"], []).append((close, vol))
    out = {}
    for sym, values in by_symbol.items():
        recent = values[-20:]
        out[sym] = sum(c * v for c, v in recent) / len(recent)
    return out


def assess_go_no_go(by_symbol, market_caps, avg_dollar_alpaca, avg_dollar_eodhd):
    ratios = [s["median_ratio"] for s in by_symbol.values() if s["median_ratio"] > 0]
    median_ratio_global = statistics.median(ratios) if ratios else float("nan")

    large_caps_rejected_alpaca: list[str] = []
    large_caps_recovered_eodhd: list[str] = []
    for sym, mc in market_caps.items():
        if mc < LARGE_CAP_USD:
            continue
        a = avg_dollar_alpaca.get(sym, 0.0)
        e = avg_dollar_eodhd.get(sym, 0.0)
        if a < MIN_AVG_DOLLAR_VOLUME_20D:
            large_caps_rejected_alpaca.append(sym)
            if e >= MIN_AVG_DOLLAR_VOLUME_20D:
                large_caps_recovered_eodhd.append(sym)

    ratio_in_band = (
        not _is_nan(median_ratio_global)
        and RATIO_MIN_OK <= median_ratio_global <= RATIO_MAX_OK
    )
    no_large_cap_lost = (
        len(large_caps_rejected_alpaca) - len(large_caps_recovered_eodhd) <= 0
    )
    go = bool(ratio_in_band and no_large_cap_lost)

    return {
        "median_ratio_global": median_ratio_global,
        "ratio_band_target": [RATIO_MIN_OK, RATIO_MAX_OK],
        "ratio_in_band": ratio_in_band,
        "large_caps_total": sum(1 for mc in market_caps.values() if mc >= LARGE_CAP_USD),
        "large_caps_rejected_by_alpaca": large_caps_rejected_alpaca,
        "large_caps_recovered_by_eodhd": large_caps_recovered_eodhd,
        "no_large_cap_lost": no_large_cap_lost,
        "decision": "GO" if go else "NO-GO",
    }


def _is_nan(x):
    return x != x


def _resolve_symbols(arg_symbols, universe_name: str):
    if arg_symbols:
        return [s.strip().upper() for s in arg_symbols if s.strip()]
    if universe_name.lower() == "sp100":
        return SP100_SYMBOLS
    raise ValueError(f"univers inconnu: {universe_name}")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Phase 4 audit ratio volume EODHD/Alpaca.")
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--symbols-from", default="sp100", choices=["sp100"])
    p.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    symbols = _resolve_symbols(args.symbols, args.symbols_from)
    end_date = date.today()
    start_date = end_date - timedelta(days=args.lookback_days)
    LOGGER.info("[phase4-audit] symbols=%d window=%s..%s", len(symbols), start_date, end_date)

    from database.connection import SessionLocal
    session = SessionLocal()
    try:
        pairs = _fetch_pairs_from_db(session, symbols, start_date, end_date)
        market_caps = _fetch_market_caps(session, symbols)
    finally:
        session.close()

    if not pairs:
        LOGGER.warning(
            "[phase4-audit] aucune paire (alpaca_iex, eodhd_eod) trouvee. "
            "Phase 3 (--write) deja executee ?"
        )

    ratios = compute_volume_ratios(pairs)
    by_symbol = aggregate_by_symbol(ratios)
    avg_a = compute_avg_dollar_volume_20d(pairs, "alpaca")
    avg_e = compute_avg_dollar_volume_20d(pairs, "eodhd")
    decision = assess_go_no_go(by_symbol, market_caps, avg_a, avg_e)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": start_date.isoformat(), "end": end_date.isoformat(),
                   "lookback_days": args.lookback_days},
        "symbols_count": len(symbols),
        "pairs_count": len(pairs),
        "ratios_per_symbol": by_symbol,
        "decision": decision,
        "thresholds": {
            "ratio_min_ok": RATIO_MIN_OK,
            "ratio_max_ok": RATIO_MAX_OK,
            "large_cap_usd": LARGE_CAP_USD,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        },
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"phase4_volume_audit_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    LOGGER.info("[phase4-audit] rapport ecrit : %s", out_path)
    print(json.dumps({"decision": decision, "report_path": str(out_path)}, indent=2))
    return 0 if decision["decision"] == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "LARGE_CAP_USD", "MIN_AVG_DOLLAR_VOLUME_20D",
    "RATIO_MAX_OK", "RATIO_MIN_OK", "SP100_SYMBOLS",
    "aggregate_by_symbol", "assess_go_no_go",
    "compute_avg_dollar_volume_20d", "compute_volume_ratios", "main",
]

