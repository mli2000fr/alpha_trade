from __future__ import annotations

import argparse
import logging
from datetime import date

import requests

from common.utils import configure_root_logging
from database.selector_reference import list_active_tradable_symbols, upsert_quote_snapshots
from service.alpaca.clientAlpaca import fetch_latest_quotes

LOGGER = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 200


def _compute_spread_bps(bid_price: float | None, ask_price: float | None) -> float | None:
    if bid_price is None or ask_price is None:
        return None
    if bid_price <= 0 or ask_price <= 0:
        return None
    mid = (bid_price + ask_price) / 2.0
    if mid <= 0:
        return None
    return ((ask_price - bid_price) / mid) * 10_000.0


def sync_latest_quotes(limit: int | None = None, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size doit être supérieur ou égal à 1.")

    symbols = list_active_tradable_symbols(limit=limit)
    summary = {"symbols": len(symbols), "rows_upserted": 0}
    if not symbols:
        return summary

    session = requests.Session()
    try:
        for start in range(0, len(symbols), batch_size):
            batch = symbols[start:start + batch_size]
            payload = fetch_latest_quotes(batch, session=session)
            rows: list[dict[str, object]] = []
            for symbol in batch:
                quote = payload.get(symbol)
                if not quote:
                    continue
                bid_price = float(quote["bp"]) if quote.get("bp") is not None else None
                ask_price = float(quote["ap"]) if quote.get("ap") is not None else None
                rows.append(
                    {
                        "symbol": symbol,
                        "quote_date": date.today(),
                        "quote_timestamp": quote.get("t"),
                        "bid_price": bid_price,
                        "ask_price": ask_price,
                        "bid_size": float(quote["bs"]) if quote.get("bs") is not None else None,
                        "ask_size": float(quote["as"]) if quote.get("as") is not None else None,
                        "spread_bps": _compute_spread_bps(bid_price, ask_price),
                    }
                )
            summary["rows_upserted"] += upsert_quote_snapshots(rows)
            LOGGER.info(
                "Sync latest quotes | batch=%s-%s symbols=%s rows_upserted=%s",
                start + 1,
                start + len(batch),
                len(batch),
                summary["rows_upserted"],
            )
    finally:
        session.close()

    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise les latest quotes Alpaca dans stock_quote_snapshots")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximum de symboles")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Taille de batch pour l'appel latest quotes")
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/sync_latest_quotes.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = _build_arg_parser().parse_args()
    sync_latest_quotes(limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    main()

