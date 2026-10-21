"""Read-only audit of the quote inputs of one published US universe.

No collection function, publisher, SQL write, order or notification is called.
Optional bounded Alpaca comparisons are archived locally, never persisted in SQL.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text


def spread_bps(bid, ask):
    try:
        bid, ask = float(bid), float(ask)
    except (TypeError, ValueError):
        return None
    if not np.isfinite([bid, ask]).all() or bid <= 0 or ask < bid:
        return None
    return (ask - bid) / ((ask + bid) / 2) * 10000


def stats(series):
    values = pd.to_numeric(series, errors="coerce").dropna()
    return {"count": len(values), **{
        key: (float(values.quantile(q)) if len(values) else None)
        for key, q in [("min", 0), ("p25", .25), ("median", .5),
                       ("p75", .75), ("p95", .95), ("max", 1)]}}


def write_json(path, payload):
    # New output directory is required; never overwrite another audit.
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True,
                               default=str, allow_nan=False), encoding="utf-8")


def select_sample(frame):
    failed = frame.loc[frame.tradability_reason_code.eq("spread_above_maximum")].sort_values(
        ["selected_spread_bps", "symbol"])
    good = frame.loc[frame.is_tradable.eq(1) & frame.quote_date.notna()].sort_values("symbol")
    candidates = ["FMC", "KE"]
    for subset, count in [(failed, 7), (good, 3)]:
        if len(subset):
            candidates.extend(subset.iloc[np.linspace(0, len(subset)-1, count).astype(int)].symbol)
    return [s for s in dict.fromkeys(candidates) if s in set(frame.symbol)][:12]


def compare_feeds(frame, day, output):
    from common.market_calendar import get_nyse_session_bounds
    from common.verified_http import verified_session
    from service.alpaca.accounts import AccountRegistry

    start, end = get_nyse_session_bounds(day)
    if end > datetime.now(timezone.utc) - timedelta(minutes=15):
        raise ValueError("Historical SIP comparison must end at least 15 minutes ago")
    key, secret = AccountRegistry.get().get_credentials("default")
    records = []
    with verified_session() as session:
        for symbol in select_sample(frame):
            source = frame.loc[frame.symbol.eq(symbol)].iloc[0]
            for feed in ("iex", "sip"):
                params = {"start": start.isoformat(), "end": end.isoformat(),
                          "feed": feed, "limit": 1, "sort": "desc"}
                endpoint = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes"
                record = {"symbol": symbol, "feed": feed, "endpoint": endpoint,
                          "params": params, "queried_at_utc": datetime.now(timezone.utc).isoformat()}
                try:
                    response = session.get(endpoint, params=params, headers={
                        "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, timeout=(10, 20))
                    record["http_status"] = response.status_code
                    if response.status_code == 200:
                        payload = response.json()
                        record["payload"] = payload
                        quote = (payload.get("quotes") or [None])[0]
                        if quote:
                            record["spread_bps"] = spread_bps(quote.get("bp"), quote.get("ap"))
                            record["matches_stored_prices"] = bool(
                                quote.get("bp") == source.bid_price and quote.get("ap") == source.ask_price)
                            record["matches_stored_timestamp_second"] = (
                                pd.Timestamp(quote["t"]).floor("s") == source.quote_timestamp)
                            record["matches_stored_timestamp_rounded_second"] = (
                                pd.Timestamp(quote["t"]).round("s") == source.quote_timestamp)
                    else:
                        record["error"] = "HTTP error; no retries or fallback"
                except Exception as exc:
                    # Never save exception text / authenticated request headers.
                    record["error_type"] = type(exc).__name__
                records.append(record)
                print(f"Quote audit {symbol} {feed}: {record.get('http_status', record.get('error_type'))}", flush=True)
                if record.get("http_status") in (401, 403, 429):
                    write_json(output / "provider_comparison.json", records)
                    return records
    write_json(output / "provider_comparison.json", records)
    return records


def run(args):
    from database.connection import get_sqlalchemy_engine
    from common.market_calendar import get_nyse_session_bounds

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    engine = get_sqlalchemy_engine()
    if engine.url.database != "alpha_trade":
        raise ValueError("US audit requires alpha_trade")
    with engine.connect() as connection:
        connection.exec_driver_sql("START TRANSACTION READ ONLY")
        publication = dict(connection.execute(text(
            "SELECT * FROM tradable_universe_runs WHERE universe_run_id=:uid"),
            {"uid": args.universe_run_id}).mappings().one())
        day = publication["snapshot_date"]
        schema = [dict(r) for r in connection.execute(text("SHOW COLUMNS FROM stock_quote_snapshots")).mappings()]
        frame = pd.read_sql(text("""
            SELECT h.symbol,h.is_tradable,h.tradability_reason_code,h.close_price,
                   h.spread_bps AS published_spread_bps,q.quote_date,q.quote_timestamp,
                   q.bid_price,q.ask_price,q.bid_size,q.ask_size,
                   q.spread_bps AS selected_spread_bps,q.last_updated
            FROM tradable_universe_history h
            LEFT JOIN stock_quote_snapshots q ON q.symbol=h.symbol AND q.quote_date=(
                SELECT MAX(q2.quote_date) FROM stock_quote_snapshots q2
                WHERE q2.symbol=h.symbol AND q2.quote_date BETWEEN :minimum AND :day
                  AND q2.spread_bps IS NOT NULL)
            WHERE h.universe_run_id=:uid ORDER BY h.symbol
        """), connection, params={"uid": args.universe_run_id, "day": day,
                                  "minimum": day-timedelta(days=5)})
        connection.rollback()
    frame["recomputed_spread_bps"] = [spread_bps(b, a) for b, a in zip(frame.bid_price, frame.ask_price)]
    frame["quote_timestamp"] = pd.to_datetime(frame.quote_timestamp, utc=True, errors="coerce")
    opening, closing = get_nyse_session_bounds(day)
    frame["seconds_before_close"] = (pd.Timestamp(closing)-frame.quote_timestamp).dt.total_seconds()
    frame["in_requested_rth"] = frame.quote_timestamp.between(opening, closing)
    frame["formula_matches"] = np.isclose(frame.selected_spread_bps, frame.recomputed_spread_bps,
                                          atol=1e-6, rtol=0, equal_nan=False)
    frame["published_matches_current"] = np.isclose(frame.published_spread_bps, frame.selected_spread_bps,
                                                    atol=1e-6, rtol=0, equal_nan=False)
    frame.to_csv(output / "quote_inputs.csv", index=False)
    selected = frame.quote_date.notna()
    failed = frame.tradability_reason_code.eq("spread_above_maximum")
    has_published = frame.published_spread_bps.notna()
    report = {
        "read_only": True, "queried_at_utc": datetime.now(timezone.utc).isoformat(),
        "publication": publication, "quote_schema": schema,
        "selection_rule": "latest non-null spread, quote_date in [snapshot_date-5 calendar days,snapshot_date]",
        "counts": {"universe": len(frame), "tradable": int(frame.is_tradable.sum()),
                   "spread_first_rejection": int(failed.sum()), "selected_quote": int(selected.sum()),
                   "formula_mismatch": int((selected & ~frame.formula_matches).sum()),
                   "published_current_mismatch": int((has_published & ~frame.published_matches_current).sum()),
                   "outside_or_missing_rth": int((selected & ~frame.in_requested_rth).sum()),
                   "nonpositive_or_missing_size": int((selected & ((frame.bid_size.fillna(0)<=0) | (frame.ask_size.fillna(0)<=0))).sum()),
                   "within_last_60_seconds": int((selected & frame.seconds_before_close.between(0,60)).sum()),
                   "older_quote_date": int((selected & frame.quote_date.ne(day)).sum())},
        "reasons": frame.groupby("tradability_reason_code").size().to_dict(),
        "all_selected_spread_bps": stats(frame.selected_spread_bps),
        "rejected_spread_bps": stats(frame.loc[failed,"selected_spread_bps"]),
        "seconds_before_close": stats(frame.seconds_before_close),
        "limitations": ["The quote table has no provider/feed column or sealed original payload.",
                        "Current quote rows are mutable; comparison to the published spread is checked.",
                        "The API comparison is a bounded diagnostic sample, not a new universe qualification.",
                        "No SQL write, publication, risk run or order is performed."],
    }
    if args.compare_feeds:
        records = compare_feeds(frame, day, output)
        report["provider_comparison_requests"] = len(records)
        report["sample"] = [dict(symbol=s, stored_spread_bps=float(frame.loc[frame.symbol.eq(s),"selected_spread_bps"].iloc[0]),
                                  **{feed: next((r.get("spread_bps") for r in records if r["symbol"]==s and r["feed"]==feed), None)
                                     for feed in ("iex","sip")}) for s in dict.fromkeys(r["symbol"] for r in records)]
    write_json(output / "report.json", report)
    print(json.dumps({"output": str(output), "counts": report["counts"], "sample": report.get("sample")}, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-run-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--compare-feeds", action="store_true")
    run(parser.parse_args())
