"""Bounded read-only Alpaca historical options eligibility POC; no broker orders."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from service.alpaca.accounts import AccountRegistry
from service.alpaca.clientAlpaca import get_alpaca_credentials
from service.forward_pit.batch import _configure_alpaca_session


def run(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    key, secret = get_alpaca_credentials("default")
    account = AccountRegistry.get().resolve("default")
    broker = "https://paper-api.alpaca.markets" if account.mode == "paper" else "https://api.alpaca.markets"
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "account_id": "default",
              "sql_writes": False, "orders_submitted": False, "tests": []}
    with requests.Session() as session:
        _configure_alpaca_session(session, use_system_trust_store=True)
        session.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        # Exact OCC identifiers are diagnostic probes, not a fabricated historical chain.
        probes = [
            ("expired_catalog_2025", broker + "/v2/options/contracts", {
                "underlying_symbols": "AAPL", "status": "inactive", "expiration_date_gte": "2025-01-17",
                "expiration_date_lte": "2025-01-31", "limit": 100}),
            ("historical_bars_default_2025", "https://data.alpaca.markets/v1beta1/options/bars", {
                "symbols": "AAPL250117C00200000,AAPL250117P00200000", "timeframe": "1Day",
                "start": "2025-01-02T00:00:00Z", "end": "2025-01-11T00:00:00Z", "limit": 10000}),
            ("historical_bars_opra_2025", "https://data.alpaca.markets/v1beta1/options/bars", {
                "symbols": "AAPL250117C00200000,AAPL250117P00200000", "timeframe": "1Day", "feed": "opra",
                "start": "2025-01-02T00:00:00Z", "end": "2025-01-11T00:00:00Z", "limit": 10000}),
        ]
        for name, url, params in probes:
            try:
                response = session.get(url, params=params, timeout=40)
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"non_json_body": response.text[:1000]}
                (output / f"{name}.json").write_text(json.dumps({"status": response.status_code,
                    "endpoint": url, "params": params, "payload": payload}, indent=2), encoding="utf-8")
                bars = payload.get("bars") or {}
                item = {"test": name, "http_status": response.status_code,
                        "bar_count": sum(len(x) for x in bars.values()),
                        "contract_count": len(payload.get("option_contracts") or []),
                        "next_page_token_present": bool(payload.get("next_page_token")),
                        "error": payload.get("message") if response.status_code >= 400 else None}
            except requests.RequestException as exc:
                item = {"test": name, "error_type": type(exc).__name__}
            report["tests"].append(item)
            print(json.dumps(item), flush=True)
            time.sleep(.4)
    report["status"] = "ACCESS_CONFIRMED" if any(x.get("bar_count", 0) > 0 for x in report["tests"]) else "HISTORICAL_ACCESS_NOT_CONFIRMED"
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/research/alpaca_options_history/20261010-smoke")
    args = parser.parse_args()
    run(Path(args.output_dir))
