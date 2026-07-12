"""Publish a full-quality tradable universe after objective data syncs."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from common.capital_presets import (
    DEFAULT_CAPITAL_PRESET_KEY,
    build_selector_config_kwargs_from_preset,
    require_capital_preset,
)
from common.market_calendar import nyse_session_dates
from common.tradable_universe import UniverseMember, begin_universe_run, fail_universe_run, publish_universe_run
from database.connection import get_sqlalchemy_engine


def _require_tables(engine: Engine) -> None:
    required = {
        "tradable_universe_runs",
        "tradable_universe_history",
        "stock_quote_snapshots",
        "stock_earnings_calendar",
        "stock_metadata",
    }
    available = set(inspect(engine).get_table_names())
    missing = sorted(required - available)
    if missing:
        raise RuntimeError(f"Tables requises absentes: {', '.join(missing)}")


def _load_source_scope(engine: Engine, snapshot_date: date, preset_key: str) -> tuple[dict[str, object], pd.DataFrame]:
    with engine.connect() as connection:
        run = connection.execute(
            text(
                """
                SELECT universe_run_id, config_fingerprint, rows_expected, rows_written
                FROM tradable_universe_runs
                WHERE snapshot_date = :snapshot_date
                  AND capital_preset_key = :preset_key
                  AND status = 'completed'
                  AND is_canonical = 1
                  AND rows_written = rows_expected
                ORDER BY finished_at DESC
                LIMIT 1
                """
            ),
            {"snapshot_date": snapshot_date, "preset_key": preset_key},
        ).mappings().first()
        if run is None:
            raise RuntimeError(
                f"Aucun snapshot screener complet exact pour preset={preset_key} date={snapshot_date}."
            )
        frame = pd.read_sql(
            text(
                """
                SELECT symbol, is_tradable, tradability_reason_code,
                       tradability_reasons_json, history_days, bars_available,
                       data_source, close_price, adv_usd, atr_pct_20
                FROM tradable_universe_history
                WHERE universe_run_id = :run_id
                ORDER BY symbol
                """
            ),
            connection,
            params={"run_id": run["universe_run_id"]},
        )
    return dict(run), frame


def _load_objective_context(
    engine: Engine,
    symbols: list[str],
    snapshot_date: date,
    blackout_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame, set[str]]:
    if not symbols:
        return pd.DataFrame(), pd.DataFrame(), set()
    symbol_params = {f"symbol_{index}": symbol for index, symbol in enumerate(symbols)}
    placeholders = ", ".join(f":symbol_{index}" for index in range(len(symbols)))
    with engine.connect() as connection:
        quotes = pd.read_sql(
            text(
                f"""
                SELECT symbol, spread_bps
                FROM stock_quote_snapshots
                WHERE quote_date = :snapshot_date
                  AND symbol IN ({placeholders})
                """
            ),
            connection,
            params={"snapshot_date": snapshot_date, **symbol_params},
        )
        metadata = pd.read_sql(
            text(
                f"""
                SELECT symbol, market_cap
                FROM stock_metadata
                WHERE symbol IN ({placeholders})
                """
            ),
            connection,
            params=symbol_params,
        )
        earnings_rows = connection.execute(
            text(
                f"""
                SELECT DISTINCT symbol
                FROM stock_earnings_calendar
                WHERE earnings_date BETWEEN :start_date AND :end_date
                  AND symbol IN ({placeholders})
                """
            ),
            {
                "start_date": snapshot_date - timedelta(days=max(blackout_days, 0)),
                "end_date": snapshot_date + timedelta(days=max(blackout_days, 0)),
                **symbol_params,
            },
        ).scalars().all()
    return quotes, metadata, {str(symbol).strip().upper() for symbol in earnings_rows}


def publish_full_tradable_universe(
    engine: Engine,
    *,
    snapshot_date: date,
    capital_preset_key: str = DEFAULT_CAPITAL_PRESET_KEY,
) -> str:
    """Publish an immutable full-quality run from the exact screener run."""
    _require_tables(engine)
    preset = require_capital_preset(capital_preset_key)
    thresholds = build_selector_config_kwargs_from_preset(preset)
    source_run, scope = _load_source_scope(engine, snapshot_date, preset.key)
    symbols = scope["symbol"].astype(str).str.strip().str.upper().tolist()
    quotes, metadata, earnings_blackout_symbols = _load_objective_context(
        engine,
        symbols,
        snapshot_date,
        int(thresholds["earnings_blackout_days"]),
    )
    quote_map = quotes.assign(symbol=quotes["symbol"].astype(str).str.upper()).set_index("symbol")["spread_bps"].to_dict() if not quotes.empty else {}
    market_cap_map = metadata.assign(symbol=metadata["symbol"].astype(str).str.upper()).set_index("symbol")["market_cap"].to_dict() if not metadata.empty else {}

    members: list[UniverseMember] = []
    for row in scope.to_dict(orient="records"):
        symbol = str(row["symbol"]).strip().upper()
        reasons = list(json.loads(row.get("tradability_reasons_json") or "[]"))
        source_tradable = bool(row.get("is_tradable"))
        spread = pd.to_numeric(quote_map.get(symbol), errors="coerce")
        market_cap = pd.to_numeric(market_cap_map.get(symbol), errors="coerce")
        earnings_blackout = symbol in earnings_blackout_symbols
        if not source_tradable:
            reason = str(row.get("tradability_reason_code") or "source_not_tradable")
        elif pd.isna(spread):
            reason = "quote_unavailable"
            reasons.append(reason)
        elif float(spread) > float(thresholds["max_spread_bps"]):
            reason = "spread_above_maximum"
            reasons.append(reason)
        elif pd.isna(market_cap):
            reason = "market_cap_unavailable"
            reasons.append(reason)
        elif float(market_cap) < float(thresholds["min_market_cap"]):
            reason = "market_cap_below_minimum"
            reasons.append(reason)
        elif earnings_blackout:
            reason = "earnings_blackout"
            reasons.append(reason)
        else:
            reason = "tradable"
        is_tradable = source_tradable and reason == "tradable"
        members.append(
            UniverseMember(
                symbol=symbol,
                is_tradable=is_tradable,
                tradability_reason_code=reason,
                tradability_reasons=tuple(dict.fromkeys(str(value) for value in reasons if str(value))),
                history_days=int(row["history_days"]) if pd.notna(row.get("history_days")) else None,
                bars_available=bool(row["bars_available"]) if pd.notna(row.get("bars_available")) else None,
                data_source=str(row["data_source"]) if pd.notna(row.get("data_source")) else None,
                close_price=float(row["close_price"]) if pd.notna(row.get("close_price")) else None,
                adv_usd=float(row["adv_usd"]) if pd.notna(row.get("adv_usd")) else None,
                spread_bps=float(spread) if pd.notna(spread) else None,
                market_cap=float(market_cap) if pd.notna(market_cap) else None,
                atr_pct_20=float(row["atr_pct_20"]) if pd.notna(row.get("atr_pct_20")) else None,
                earnings_blackout=earnings_blackout,
                data_quality_grade="full",
            )
        )

    fingerprint_payload = {
        "source_run_id": source_run["universe_run_id"],
        "source_fingerprint": source_run["config_fingerprint"],
        "preset_key": preset.key,
        "thresholds": {
            "max_spread_bps": thresholds["max_spread_bps"],
            "min_market_cap": thresholds["min_market_cap"],
            "earnings_blackout_days": thresholds["earnings_blackout_days"],
        },
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    run_id = begin_universe_run(
        engine,
        snapshot_date=snapshot_date,
        capital_preset_key=preset.key,
        config_fingerprint=fingerprint,
        rows_expected=len(members),
        data_quality_grade="full",
    )
    try:
        publish_universe_run(engine, run_id, members)
    except Exception as exc:
        fail_universe_run(engine, run_id, str(exc))
        raise
    return run_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publie l'univers tradable PIT complet après quotes et earnings.")
    parser.add_argument("--trade-date", type=date.fromisoformat, default=None)
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    parser.add_argument("--capital-preset-key", default=DEFAULT_CAPITAL_PRESET_KEY)
    args = parser.parse_args(argv)
    if (args.start_date is None) != (args.end_date is None):
        parser.error("--start-date et --end-date doivent être fournis ensemble.")
    if args.trade_date is not None and args.start_date is not None:
        parser.error("Utilisez soit --trade-date, soit --start-date/--end-date.")

    snapshot_dates = (
        nyse_session_dates(args.start_date, args.end_date)
        if args.start_date is not None and args.end_date is not None
        else [args.trade_date or date.today()]
    )
    engine = get_sqlalchemy_engine()
    run_ids: list[str] = []
    missing_source_dates: list[str] = []
    for snapshot_date in snapshot_dates:
        try:
            run_ids.append(
                publish_full_tradable_universe(
                    engine,
                    snapshot_date=snapshot_date,
                    capital_preset_key=args.capital_preset_key,
                )
            )
        except RuntimeError as exc:
            if not str(exc).startswith("Aucun snapshot screener complet exact"):
                raise
            missing_source_dates.append(snapshot_date.isoformat())

    status = "completed" if not missing_source_dates else "incomplete_missing_screener_snapshots"
    print(
        json.dumps(
            {
                "status": status,
                "snapshots_published": len(run_ids),
                "universe_run_ids": run_ids,
                "missing_screener_snapshot_dates": missing_source_dates,
                "data_quality_grade": "full",
            }
        )
    )
    if missing_source_dates:
        print(
            "Publication incomplète : exécutez d'abord le Stock Screener PIT pour les dates manquantes, "
            "par exemple `python -m screener.stock_screener --trade-date YYYY-MM-DD`.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())