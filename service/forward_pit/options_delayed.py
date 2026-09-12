"""Collectes options gratuites, retardées et strictement réservées à la recherche.

Le feed historique Alpaca ne déclare pas sa provenance dans le payload. Il est
donc persisté comme ``UNVERIFIED_OPRA``. Le RSS OCC constitue une notification
officielle prospective, mais pas un substitut au texte détaillé du mémo.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)
ALPACA_DATA_URL = "https://data.alpaca.markets"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
OCC_RSS_URL = "https://infomemo.theocc.com/infomemo-rss"


def _last_trading_day(day: date) -> date:
    from common.market_calendar import is_trading_day
    candidate = day
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_occ_rss(content: str | bytes) -> list[dict[str, Any]]:
    """Normalise le sous-ensemble stable et publiquement exposé du RSS OCC."""
    root = ET.fromstring(content)
    rows: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        categories = [
            (node.text or "").strip() for node in item.findall("category")
            if (node.text or "").strip()
        ]
        match = re.search(r"#?(\d{4,})", title)
        if not match or not any("contract adjustment" in x.lower() for x in categories):
            continue
        published: datetime | None = None
        raw_date = (item.findtext("pubDate") or "").strip()
        if raw_date:
            try:
                parsed = parsedate_to_datetime(raw_date)
                published = parsed.astimezone(UTC).replace(tzinfo=None)
            except (TypeError, ValueError, OverflowError):
                published = None
        old_match = re.search(r"Option Symbols?\s*:\s*([A-Z0-9./-]+)", description, re.I)
        new_match = re.search(r"New(?: Option| Adjusted)? Symbols?\s*:\s*([A-Z0-9./-]+)", description, re.I)
        lowered = description.lower()
        adjustment_type = next((
            label for needle, label in (
                ("reverse split", "REVERSE_SPLIT"), ("merger", "MERGER"),
                ("spin-off", "SPIN_OFF"), ("distribution", "DISTRIBUTION"),
                ("symbol change", "SYMBOL_CHANGE"), ("cash settlement", "CASH_SETTLEMENT"),
                ("liquidation", "LIQUIDATION"), ("consolidation", "CONSOLIDATION"),
            ) if needle in lowered
        ), "OTHER")
        rows.append({
            "memo": match.group(1), "published": published, "effective": None,
            "title": description or title, "category": ",".join(categories),
            "url": link, "adjustment_type": adjustment_type,
            "old_root": old_match.group(1) if old_match else None,
            "new_root": new_match.group(1) if new_match else None,
        })
    return rows


def select_atm_contracts(
    contracts: Iterable[dict[str, Any]], *, spot: float, as_of: date,
    target_dtes: Iterable[int], tolerance_days: int,
) -> list[dict[str, Any]]:
    """Sélection déterministe : un CALL et un PUT ATM par échéance cible."""
    valid: list[dict[str, Any]] = []
    for item in contracts:
        try:
            expiry = date.fromisoformat(str(item.get("expiration_date")))
            strike = float(item.get("strike_price"))
        except (TypeError, ValueError):
            continue
        option_type = str(item.get("type") or "").lower()
        if option_type not in {"call", "put"} or expiry < as_of or strike <= 0:
            continue
        valid.append(item | {"_expiry": expiry, "_strike": strike, "_type": option_type})
    selected: dict[str, dict[str, Any]] = {}
    expiries = sorted({item["_expiry"] for item in valid})
    for target in target_dtes:
        candidates = [x for x in expiries if abs((x - as_of).days - target) <= tolerance_days]
        if not candidates:
            continue
        expiry = min(candidates, key=lambda x: (abs((x - as_of).days - target), x))
        for option_type in ("call", "put"):
            side = [x for x in valid if x["_expiry"] == expiry and x["_type"] == option_type]
            if side:
                winner = min(side, key=lambda x: (abs(x["_strike"] - spot), x["_strike"]))
                selected[str(winner.get("symbol"))] = winner
    return list(selected.values())


def _contract_row(item: dict[str, Any], *, observed: datetime, run_id: str) -> dict[str, Any]:
    from service.forward_pit import batch as shared
    payload = {key: value for key, value in item.items() if not key.startswith("_")}
    return {
        "provider": "alpaca", "contract": item.get("symbol"),
        "underlying": item.get("underlying_symbol"), "root": item.get("root_symbol"),
        "status": item.get("status"), "expiry": item.get("expiration_date"),
        "strike": _float(item.get("strike_price")), "otype": str(item.get("type") or "").upper(),
        "style": item.get("style"), "multiplier": _float(item.get("multiplier")),
        "size": _float(item.get("size")), "oi": _int(item.get("open_interest")),
        "oi_date": item.get("open_interest_date"), "close": _float(item.get("close_price")),
        "close_date": item.get("close_price_date"),
        "deliverables": shared._json(item.get("deliverables") or []),
        "observed": observed, "hash": shared._hash(payload), "run": run_id,
    }


def options_delayed_bars_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool):
    from service.forward_pit import batch as shared
    symbols = shared._collection_symbols(cfg)
    market_tz = ZoneInfo("America/New_York")
    session_date = _last_trading_day(datetime.now(market_tz).date())
    delay = max(16, int(cfg.get("minimum_delay_minutes", 16)))
    end_local = datetime.combine(session_date, datetime.min.time(), market_tz).replace(hour=16)
    if datetime.now(UTC) < end_local.astimezone(UTC) + timedelta(minutes=delay):
        raise RuntimeError(f"Attendre au moins {delay} minutes après la clôture options")
    target_dtes = tuple(int(x) for x in str(cfg.get("target_dtes", "5,10,20")).split(","))
    tolerance = int(cfg.get("dte_tolerance_days", 5))
    timeframe = str(cfg.get("timeframe", "30Min"))
    observed = shared._utcnow()
    key, secret = shared.get_alpaca_credentials()
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    outcome = shared.Outcome(requested=len(symbols))
    prices: dict[str, float] = {}
    contracts: list[dict[str, Any]] = []
    covered_underlyings: set[str] = set()
    with requests.Session() as session, engine.begin() as conn:
        shared._configure_alpaca_session(session, use_system_trust_store=bool(cfg.get("use_system_trust_store", True)))
        for chunk_no, chunk in enumerate(shared._chunks(symbols, int(cfg.get("stock_snapshot_batch_size", 100))), 1):
            payload, status = shared._request_json(session, f"{ALPACA_DATA_URL}/v2/stocks/snapshots", params={"symbols": ",".join(chunk), "feed": "iex"}, headers=headers)
            if not dry:
                shared._raw(conn, run_id, "options_delayed_bars_sync", "alpaca", "/v2/stocks/snapshots", f"chunk:{chunk_no}", payload, status, observed)
            for symbol, item in payload.items() if isinstance(payload, dict) else []:
                price = shared._underlying_price(item) if isinstance(item, dict) else None
                if price:
                    prices[str(symbol).upper()] = price
        for index, symbol in enumerate(symbols, 1):
            spot = prices.get(symbol)
            if not spot:
                outcome.empty += 1
                continue
            min_expiry = session_date + timedelta(days=max(1, min(target_dtes) - tolerance))
            max_expiry = session_date + timedelta(days=max(target_dtes) + tolerance)
            try:
                pages = shared._paginated_json(
                    session, f"{ALPACA_PAPER_URL}/v2/options/contracts",
                    params={"underlying_symbols": symbol, "status": "active", "expiration_date_gte": min_expiry.isoformat(), "expiration_date_lte": max_expiry.isoformat(), "limit": 10000},
                    headers=headers, page_key="next_page_token", max_pages=int(cfg.get("max_contract_pages", 5)),
                    pause_seconds=float(cfg.get("request_interval_seconds", 0.0)),
                )
            except Exception as exc:
                outcome.failed += 1
                outcome.warnings.append(f"{symbol}: catalogue options indisponible ({exc})")
                continue
            available: list[dict[str, Any]] = []
            for page_no, (payload, status) in enumerate(pages, 1):
                if not dry:
                    shared._raw(conn, run_id, "options_delayed_bars_sync", "alpaca", "/v2/options/contracts", f"{symbol}:page:{page_no}", payload, status, observed)
                available.extend(x for x in (payload.get("option_contracts") or []) if isinstance(x, dict))
            chosen = select_atm_contracts(available, spot=spot, as_of=session_date, target_dtes=target_dtes, tolerance_days=tolerance)
            if chosen:
                covered_underlyings.add(symbol)
                contracts.extend(chosen)
            else:
                outcome.empty += 1
            if chosen and not dry:
                conn.execute(text("""INSERT IGNORE INTO stock_option_contract_versions
                    (provider,contract_symbol,underlying_symbol,root_symbol,status,expiration_date,strike,option_type,exercise_style,multiplier,contract_size,open_interest,open_interest_date,close_price,close_price_date,deliverables_json,observed_at,available_at,payload_hash,run_id)
                    VALUES (:provider,:contract,:underlying,:root,:status,:expiry,:strike,:otype,:style,:multiplier,:size,:oi,:oi_date,:close,:close_date,:deliverables,:observed,:observed,:hash,:run)"""), [_contract_row(x, observed=observed, run_id=run_id) for x in chosen])
            if index == 1 or index % 100 == 0:
                LOGGER.info("options_delayed discovery=%s/%s contracts=%s", index, len(symbols), len(contracts))

        start = datetime.combine(session_date, datetime.min.time(), market_tz).replace(hour=9, minute=30).astimezone(UTC).isoformat()
        end = end_local.astimezone(UTC).isoformat()
        for chunk_no, chunk in enumerate(shared._chunks(sorted({str(x["symbol"]) for x in contracts}), int(cfg.get("contract_batch_size", 100))), 1):
            pages = shared._paginated_json(
                session, f"{ALPACA_DATA_URL}/v1beta1/options/bars",
                params={"symbols": ",".join(chunk), "timeframe": timeframe, "start": start, "end": end, "limit": 10000, "sort": "asc"},
                headers=headers, page_key="next_page_token", max_pages=int(cfg.get("max_bar_pages", 20)),
                pause_seconds=float(cfg.get("request_interval_seconds", 0.0)),
            )
            for page_no, (payload, status) in enumerate(pages, 1):
                page_observed = shared._utcnow()
                if not dry:
                    shared._raw(conn, run_id, "options_delayed_bars_sync", "alpaca", "/v1beta1/options/bars", f"chunk:{chunk_no}:page:{page_no}", payload, status, page_observed)
                rows: list[dict[str, Any]] = []
                for contract, items in (payload.get("bars") or {}).items():
                    for item in items if isinstance(items, list) else []:
                        expiry, strike, otype = shared._option_contract_parts(contract)
                        row = {"provider": "alpaca", "feed": "historical_default", "provenance": "UNVERIFIED_OPRA", "underlying": next((str(x.get("underlying_symbol")) for x in contracts if x.get("symbol") == contract), None), "contract": contract, "expiry": expiry, "strike": strike, "otype": otype, "timeframe": timeframe, "ts": shared._dt(item.get("t")), "observed": page_observed, "open": _float(item.get("o")), "high": _float(item.get("h")), "low": _float(item.get("l")), "close": _float(item.get("c")), "volume": _int(item.get("v")), "trades": _int(item.get("n")), "vwap": _float(item.get("vw")), "hash": shared._hash(item), "run": run_id}
                        if row["ts"] and all(row[x] is not None and row[x] > 0 for x in ("open", "high", "low", "close")):
                            rows.append(row)
                outcome.received += len(rows)
                if rows and not dry:
                    result = conn.execute(text("""INSERT IGNORE INTO stock_option_bars_delayed
                        (provider,feed,provenance_status,underlying_symbol,contract_symbol,expiration_date,strike,option_type,timeframe,bar_timestamp,observed_at,available_at,open,high,low,close,volume,trade_count,vwap,payload_hash,run_id)
                        VALUES (:provider,:feed,:provenance,:underlying,:contract,:expiry,:strike,:otype,:timeframe,:ts,:observed,:observed,:open,:high,:low,:close,:volume,:trades,:vwap,:hash,:run)"""), rows)
                    outcome.persisted += max(0, result.rowcount)
    coverage = len(covered_underlyings) / len(symbols) if symbols else 0.0
    outcome.details.update({"session_date": session_date.isoformat(), "timeframe": timeframe, "selected_contracts": len(contracts), "covered_underlyings": len(covered_underlyings), "underlying_coverage": coverage, "provenance_status": "UNVERIFIED_OPRA"})
    if not contracts or not outcome.received:
        raise RuntimeError("Aucune barre d'option Alpaca retardée collectée")
    minimum_coverage = float(cfg.get("min_underlying_coverage", 0.0))
    if coverage < minimum_coverage:
        message = f"Couverture sous-jacents options insuffisante: {coverage:.1%} < {minimum_coverage:.1%}"
        if bool(cfg.get("fail_on_quality_gate", False)):
            raise RuntimeError(message)
        outcome.warnings.append(message)
    return outcome


def option_contract_adjustment_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool):
    from service.forward_pit import batch as shared
    outcome = shared.Outcome(requested=1)
    with requests.Session() as session:
        shared._configure_alpaca_session(session, use_system_trust_store=bool(cfg.get("use_system_trust_store", True)))
        response = session.get(str(cfg.get("rss_url") or OCC_RSS_URL), timeout=45)
        response.raise_for_status()
        observed = shared._utcnow()
        rows = parse_occ_rss(response.content)
    outcome.received = len(rows)
    if not rows:
        raise RuntimeError("Flux RSS OCC sans Contract Adjustment exploitable")
    with engine.begin() as conn:
        if not dry:
            shared._raw(conn, run_id, "option_contract_adjustment_sync", "occ", "/infomemo-rss", "LATEST", response.text, response.status_code, observed)
            params = [row | {"observed": observed, "hash": shared._hash(row), "run": run_id} for row in rows]
            result = conn.execute(text("""INSERT IGNORE INTO option_contract_adjustments
                (provider,occ_memo_number,published_at,effective_at,category,title,source_url,adjustment_type,old_option_root,new_option_root,observed_at,available_at,payload_hash,run_id)
                VALUES ('occ',:memo,:published,:effective,:category,:title,:url,:adjustment_type,:old_root,:new_root,:observed,:observed,:hash,:run)"""), params)
            outcome.persisted = max(0, result.rowcount)
    outcome.details.update({"source": "OCC_RSS", "detail_status": "RSS_METADATA_ONLY_CLOUDFLARE_BLOCKED", "items_in_feed": len(rows)})
    return outcome


def trade_bar_comparison(trades: list[dict[str, Any]], bars: list[dict[str, Any]]) -> dict[str, Any]:
    trade_volume = sum(max(0, _int(x.get("s")) or 0) for x in trades)
    bar_volume = sum(max(0, _int(x.get("v")) or 0) for x in bars)
    notional = sum((_float(x.get("p")) or 0) * max(0, _int(x.get("s")) or 0) for x in trades)
    bar_trade_count = sum(max(0, _int(x.get("n")) or 0) for x in bars)
    raw_vwap = notional / trade_volume if trade_volume else None
    bar_vwap = sum((_float(x.get("vw")) or 0) * max(0, _int(x.get("v")) or 0) for x in bars) / bar_volume if bar_volume else None
    return {
        "trade_count_raw": len(trades), "trade_volume_raw": trade_volume,
        "bar_trade_count": bar_trade_count, "bar_volume": bar_volume,
        "raw_vwap": raw_vwap, "bar_vwap_weighted": bar_vwap,
        "volume_ratio_raw_vs_bars": trade_volume / bar_volume if bar_volume else None,
        "trade_count_ratio_raw_vs_bars": len(trades) / bar_trade_count if bar_trade_count else None,
        "vwap_relative_error": abs(raw_vwap - bar_vwap) / bar_vwap
        if raw_vwap is not None and bar_vwap else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POC trades options Alpaca versus barres")
    parser.add_argument("--trade-poc", action="store_true")
    parser.add_argument("--symbols", default="AAPL,MSFT,NVDA,TSLA,AMD")
    parser.add_argument("--session-date")
    parser.add_argument("--output-dir", default="artifacts/research/options_delayed_trade_poc")
    args = parser.parse_args(argv)
    if not args.trade_poc:
        parser.error("--trade-poc requis")
    from service.forward_pit import batch as shared
    day = date.fromisoformat(args.session_date) if args.session_date else _last_trading_day(datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1))
    key, secret = shared.get_alpaca_credentials(); headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    results: list[dict[str, Any]] = []
    with requests.Session() as session:
        shared._configure_alpaca_session(session, use_system_trust_store=True)
        for underlying in [x.strip().upper() for x in args.symbols.split(",") if x.strip()]:
            stock, _ = shared._request_json(session, f"{ALPACA_DATA_URL}/v2/stocks/{underlying}/bars", params={"timeframe": "1Day", "start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat(), "feed": "iex", "limit": 1}, headers=headers)
            stock_bars = stock.get("bars") or []
            spot = _float(stock_bars[-1].get("c")) if stock_bars else None
            if not spot:
                continue
            contracts_payload, _ = shared._request_json(session, f"{ALPACA_PAPER_URL}/v2/options/contracts", params={"underlying_symbols": underlying, "status": "active", "expiration_date_gte": (day + timedelta(days=5)).isoformat(), "expiration_date_lte": (day + timedelta(days=30)).isoformat(), "limit": 10000}, headers=headers)
            chosen = select_atm_contracts(contracts_payload.get("option_contracts") or [], spot=spot, as_of=day, target_dtes=(10,), tolerance_days=10)
            for contract in chosen:
                symbol = str(contract["symbol"])
                market_tz = ZoneInfo("America/New_York")
                start = datetime.combine(day, datetime.min.time(), market_tz).replace(hour=9, minute=30).astimezone(UTC).isoformat()
                end = datetime.combine(day, datetime.min.time(), market_tz).replace(hour=16).astimezone(UTC).isoformat()
                trade_pages = shared._paginated_json(session, f"{ALPACA_DATA_URL}/v1beta1/options/trades", params={"symbols": symbol, "start": start, "end": end, "limit": 10000, "sort": "asc"}, headers=headers, page_key="next_page_token", max_pages=50)
                bar_pages = shared._paginated_json(session, f"{ALPACA_DATA_URL}/v1beta1/options/bars", params={"symbols": symbol, "timeframe": "1Min", "start": start, "end": end, "limit": 10000, "sort": "asc"}, headers=headers, page_key="next_page_token", max_pages=10)
                trades=[x for p,_ in trade_pages for x in ((p.get("trades") or {}).get(symbol) or [])]; bars=[x for p,_ in bar_pages for x in ((p.get("bars") or {}).get(symbol) or [])]
                results.append({"underlying": underlying, "contract": symbol, "option_type": contract.get("type")} | trade_bar_comparison(trades, bars))
    ratios=[x["volume_ratio_raw_vs_bars"] for x in results if x.get("volume_ratio_raw_vs_bars") is not None]
    count_ratios=[x["trade_count_ratio_raw_vs_bars"] for x in results if x.get("trade_count_ratio_raw_vs_bars") is not None]
    vwap_errors=[x["vwap_relative_error"] for x in results if x.get("vwap_relative_error") is not None]
    median = lambda values: sorted(values)[len(values)//2] if values else None
    comparable = len(ratios)
    consistent = sum(0.95 <= value <= 1.05 for value in ratios)
    decision = "GO_RESEARCH_ONLY" if comparable >= 6 and consistent / comparable >= 0.80 and (median(vwap_errors) or 1.0) <= 0.01 else "NO_GO_OR_MORE_DATA"
    report={"generated_at": datetime.now(UTC).isoformat(), "session_date": day.isoformat(), "provenance_status": "UNVERIFIED_OPRA", "results": results, "summary": {"contracts": len(results), "comparable_contracts": comparable, "median_volume_ratio": median(ratios), "median_trade_count_ratio": median(count_ratios), "median_vwap_relative_error": median(vwap_errors), "volume_ratio_within_5pct": consistent, "decision": decision, "serving_allowed": False}}
    out=Path(args.output_dir)/f"poc-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"; out.mkdir(parents=True, exist_ok=True); (out/"report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"POC terminé: {out / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
