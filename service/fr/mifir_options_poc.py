"""Manual file-only POC: Euronext delayed trades + public ESMA FIRDS.

No XLSX, database, scheduler or ML dependency. Not a complete options feed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import uuid
import zipfile

TRADES_PAGE = "https://marketdata.euronext.com/data-reporting-service/trades-file"
TRADES_URL = TRADES_PAGE + "/download/EQUITY_INDEX_DERIVATIVES/PREVIOUS_TRADING_DAY/PAR"
REFERENCE_URL = "https://registers.esma.europa.eu/solr/esma_registers_firds/select"
PILOT = {"FR0000120321": "OR.PA", "FR0000121972": "SU.PA", "FR0000120644": "BN.PA"}
REQUIRED = {"TradingDateTime", "PublicationDateTime", "MifidInstrumentID", "MifidPrice",
            "MifidQuantity", "MifidPriceNotation", "MifidCurrency", "Venue",
            "TradeUniqueIdentifier", "MmtModificationIndicator", "MmtPostTradeDeferral",
            "NumberOfTransactions", "MissingPrice", "VenueOfPublication"}


def now():
    return datetime.now(timezone.utc).isoformat()


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone absent")
    return result.astimezone(timezone.utc)


def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric value") from exc
    if not result.is_finite():
        raise ValueError("Nonfinite value")
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch(url, limit):
    expected = urllib.parse.urlsplit(url).hostname
    if expected not in {"marketdata.euronext.com", "registers.esma.europa.eu"}:
        raise ValueError("Unapproved source host")
    request = urllib.request.Request(url, headers={"User-Agent": "AlphaTrade-Research-POC/1.0"})
    # Verified TLS, no credentials, cookies, bypass or retry on denial.
    with urllib.request.urlopen(request, timeout=60) as response:
        if urllib.parse.urlsplit(response.url).hostname != expected:
            raise ValueError("Unexpected redirect")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("POC size budget exceeded")
        return data, {"url": url, "received_at": now(), "http_status": response.status,
                      "content_type": response.headers.get("Content-Type"),
                      "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def read_trades(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = [i for i in archive.infolist() if i.filename.lower().endswith(".csv")]
        if len(files) != 1 or files[0].file_size > 64_000_000:
            raise ValueError("Unexpected trades ZIP")
        text = archive.read(files[0]).decode("utf-8-sig")
    lines = text.splitlines()
    # Copyright preamble contains commas and is not the CSV header.
    header = next((i for i, line in enumerate(lines) if line.startswith("TradingDateTime,")), None)
    if header is None:
        raise ValueError("CSV header absent")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header:])))
    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError("Trades schema changed")
    rows = list(reader)
    if len(rows) > 100_000 or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("Malformed or oversized CSV")
    return rows, "\n".join(lines[:header])


def query_url(isins):
    if not isins or any(not valid_isin(i) for i in isins):
        raise ValueError("Invalid instrument identifiers")
    if len(isins) > 80:
        raise ValueError("Reference query budget exceeded")
    query = ("type_s:parent AND mic:XMON AND latest_received_flag:1 AND never_published_flag:0 "
             "AND isin:(" + " OR ".join(sorted(isins)) + ")")
    return REFERENCE_URL + "?" + urllib.parse.urlencode({"q": query, "rows": 400, "wt": "json"})


def valid_isin(value):
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
        return False
    expanded = "".join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = 0
    for position, digit in enumerate(reversed(expanded)):
        n = int(digit) * (2 if position % 2 else 1)
        total += n // 10 + n % 10
    return total % 10 == 0


def reference_index(docs):
    grouped = defaultdict(list)
    for doc in docs:
        if doc.get("mic") == "XMON" and doc.get("isin"):
            grouped[doc["isin"]].append(doc)
    resolved, ambiguous = {}, []
    for isin, group in grouped.items():
        unique = {json.dumps(d, sort_keys=True): d for d in group}
        if len(unique) != 1:
            ambiguous.append(isin)
        else:
            resolved[isin] = next(iter(unique.values()))
    return resolved, ambiguous


def option_contract(doc, universe=None):
    universe = PILOT if universe is None else universe
    underlying = doc.get("drv_underlng_isin")
    if not str(doc.get("gnr_cfi_code", "")).startswith("O") or underlying not in universe:
        return None
    side = {"CALL": "CALL", "PUTO": "PUT"}.get(doc.get("drv_option_type"))
    if side is None:
        raise ValueError("Option side absent/unknown")
    if doc["gnr_cfi_code"][:2] != {"CALL": "OC", "PUT": "OP"}[side]:
        raise ValueError("Option side and CFI disagree")
    strike, multiplier = number(doc["drv_sp_prc_value_amount"]), number(doc["drv_price_multiplier"])
    if strike <= 0 or multiplier <= 0 or doc.get("drv_sp_prc_value_sign_flag") != "No":
        raise ValueError("Unqualified strike/multiplier")
    if doc.get("drv_sp_prc_value_curr_code") != "EUR" or doc.get("gnr_notional_curr_code") != "EUR":
        raise ValueError("Unsupported currency")
    expiry = instant(doc["drv_expiry_date"])
    return {"option_isin": doc["isin"], "underlying_isin": underlying,
            "symbol": universe[underlying], "side": side, "source_option_type": doc["drv_option_type"],
            "strike": str(strike), "strike_currency": "EUR", "multiplier": str(multiplier),
            "expiry": expiry.date().isoformat(), "exercise_style": doc.get("drv_option_exercise_style"),
            "delivery_type": doc.get("drv_delivery_type"), "cfi": doc["gnr_cfi_code"],
            "firds_publication_at": doc.get("publication_date"),
            "firds_id": doc.get("id"), "firds_status": doc.get("status"),
            "historical_reference_pit_qualified": False, "adjustment_history_qualified": False}


def analyze(trades, docs, observed_at, universe=None):
    universe = PILOT if universe is None else universe
    reference, ambiguous = reference_index(docs)
    contracts, contract_errors = {}, {}
    traded_isins = {r["MifidInstrumentID"] for r in trades}
    for isin in sorted(traded_isins & reference.keys()):
        try:
            contract = option_contract(reference[isin], universe)
            if contract:
                contracts[isin] = contract
        except (KeyError, ValueError) as exc:
            contract_errors[isin] = str(exc)
    reasons, groups = Counter(), defaultdict(list)
    for row in trades:
        if row["MifidInstrumentID"] not in contracts:
            continue
        if not row["TradeUniqueIdentifier"] or row["Venue"] != "XMON":
            reasons["MISSING_ID_OR_UNEXPECTED_VENUE"] += 1
            continue
        groups[(row["Venue"], row["VenueOfPublication"], row["TradeUniqueIdentifier"])].append(row)
    accepted, rejected = [], []
    for key, group in groups.items():
        unique = {json.dumps(r, sort_keys=True): r for r in group}
        reasons["EXACT_DUPLICATES_REMOVED"] += len(group) - len(unique)
        rows = list(unique.values())
        modifiers = {r["MmtModificationIndicator"] for r in rows}
        reason = None
        if "CANC" in modifiers:
            reason = "CANCELLED_ID"
        elif modifiers != {"-"}:
            reason = "AMENDMENT_OR_UNKNOWN_MODIFIER"
        elif len(rows) != 1:
            reason = "CONFLICTING_TRADE_ID"
        row = rows[0]
        if reason is None:
            try:
                traded, published = instant(row["TradingDateTime"]), instant(row["PublicationDateTime"])
                contract = contracts[row["MifidInstrumentID"]]
                if published < traded or published > instant(observed_at):
                    raise ValueError("TIMESTAMP_INCONSISTENT")
                start = reference[row["MifidInstrumentID"]].get("mrkt_trdng_start_date")
                if (start and traded < instant(start)) or traded.date().isoformat() > contract["expiry"]:
                    raise ValueError("OUTSIDE_CONTRACT_LIFETIME")
                if (row["MmtPostTradeDeferral"] != "-" or row["NumberOfTransactions"] not in {"", "1"}
                        or row["MissingPrice"] not in {"", "-"}):
                    raise ValueError("DEFERRED_AGGREGATED_OR_MISSING_PRICE")
                price, qty = number(row["MifidPrice"]), number(row["MifidQuantity"])
                if price <= 0 or qty <= 0 or row["MifidPriceNotation"] != "MONE" or row["MifidCurrency"] != "EUR":
                    raise ValueError("UNQUALIFIED_PRICE_QUANTITY")
                accepted.append({**row, "contract": contract, "available_at": observed_at,
                                 "quantity_unit_qualified": False, "ml_eligible": False})
            except (ValueError, KeyError) as exc:
                reason = str(exc)
        if reason:
            reasons[reason] += len(group)
            rejected.append({"trade_key": list(key), "reason": reason, "rows": group})
    summaries = {}
    for symbol in universe.values():
        subset = [r for r in accepted if r["contract"]["symbol"] == symbol]
        calls = sum((number(r["MifidQuantity"]) for r in subset if r["contract"]["side"] == "CALL"), Decimal(0))
        puts = sum((number(r["MifidQuantity"]) for r in subset if r["contract"]["side"] == "PUT"), Decimal(0))
        summaries[symbol] = {
            "accepted_trade_rows": len(subset), "traded_option_series": len({r["MifidInstrumentID"] for r in subset}),
            "call_rows": sum(r["contract"]["side"] == "CALL" for r in subset),
            "put_rows": sum(r["contract"]["side"] == "PUT" for r in subset),
            "reported_call_quantity_sum": str(calls), "reported_put_quantity_sum": str(puts),
            "quantity_unit_qualified": False, "put_call_contract_volume_ratio": None}
    return {"input_trade_rows": len(trades), "input_instruments": len(traded_isins),
            "non_isin_instrument_ids": sorted(i for i in traded_isins if not valid_isin(i)),
            "non_isin_trade_rows": sum(not valid_isin(r["MifidInstrumentID"]) for r in trades),
            "reference_matched_instruments": len(traded_isins & reference.keys()),
            "reference_unmatched_instruments": sorted(traded_isins - reference.keys()),
            "ambiguous_reference_isins": ambiguous, "contract_errors": contract_errors,
            "pilot_option_series_identified": len(contracts), "coverage": summaries,
            "all_source_modifiers": dict(Counter(r["MmtModificationIndicator"] for r in trades)),
            "exclusion_counts": dict(reasons), "trade_dates": sorted({r["TradingDateTime"][:10] for r in trades}),
            "contracts": list(contracts.values()), "accepted": accepted, "rejected": rejected}


def run(output_root, *, download_public_poc=False, trades_zip=None, reference_json=None):
    if download_public_poc == bool(trades_zip or reference_json) or (not download_public_poc and not (trades_zip and reference_json)):
        raise ValueError("Choose explicit public download OR both offline evidence files")
    root = output_root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, exist_ok=False)
    report = {"collection_name": "fr_options_mifir_delayed_trades_poc", "status": "RUNNING",
              "started_at": now(), "ml_eligible": False, "canonical": False, "scheduled": False,
              "sources": ["Euronext Delayed Trade Data", "ESMA FIRDS"],
              "terms": [TRADES_PAGE, "https://registers.esma.europa.eu/publication/legalNoticePage"],
              "rights_scope": "INTERNAL_USE_MIFIR_SPECIFIC_TERMS_AND_ESMA_ATTRIBUTION",
              "missing": ["open_interest", "bid_ask_sizes", "full_greeks", "adjustment_history"],
              "historical_pit_qualified": False}
    try:
        if download_public_poc:
            page, receipt = fetch(TRADES_PAGE, 100_000)
            html = page.decode("utf-8")
            if not all(v in html for v in ["EQUITY_INDEX_DERIVATIVES", "PREVIOUS_TRADING_DAY", 'value="PAR"', "trades-file\\/download"]):
                raise ValueError("Public download form changed")
            write_json(root / "source_page_receipt.json", receipt)
            (root / "source_page.html").write_bytes(page)
            data, trade_receipt = fetch(TRADES_URL, 16_000_000)
        else:
            if trades_zip.stat().st_size > 16_000_000:
                raise ValueError("Trades file too large")
            data = trades_zip.read_bytes()
            trade_receipt = {"local_file": str(trades_zip), "received_at": now(), "sha256": hashlib.sha256(data).hexdigest()}
        (root / "trades.zip").write_bytes(data)
        report["trades_receipt"] = trade_receipt
        trades, disclaimer = read_trades(data)
        report["source_disclaimer"] = disclaimer
        docs, receipts = [], []
        report["reference_receipts"] = receipts
        if download_public_poc:
            isins = sorted({r["MifidInstrumentID"] for r in trades if valid_isin(r["MifidInstrumentID"])})
            if len(isins) > 2000:
                raise ValueError("POC reference universe exceeds 2000 traded instruments")
            for offset in range(0, len(isins), 80):
                print(f"FIRDS {offset}/{len(isins)}", flush=True)
                raw, receipt = fetch(query_url(isins[offset:offset + 80]), 4_000_000)
                (root / f"firds-{offset:04d}.json").write_bytes(raw)
                write_json(root / f"firds-{offset:04d}-receipt.json", receipt)
                receipts.append(receipt)
                result = json.loads(raw)["response"]
                if result["numFound"] != len(result["docs"]):
                    raise ValueError("Truncated FIRDS response")
                requested = set(isins[offset:offset + 80])
                if any(d.get("isin") not in requested for d in result["docs"]):
                    raise ValueError("FIRDS query returned instruments not requested")
                docs.extend(result["docs"])
                time.sleep(0.5)
        else:
            if reference_json.stat().st_size > 32_000_000:
                raise ValueError("Reference file too large")
            raw = reference_json.read_bytes()
            docs = json.loads(raw.decode("utf-8"))
            report["reference_input"] = {"local_file": str(reference_json),
                                         "sha256": hashlib.sha256(raw).hexdigest(), "received_at": now()}
            if not isinstance(docs, list):
                raise ValueError("Reference evidence must be a list of raw FIRDS documents")
        write_json(root / "firds_documents.json", docs)
        observed = now()
        result = analyze(trades, docs, observed)
        for key in ["contracts", "accepted", "rejected"]:
            write_json(root / (key + ".json"), result.pop(key))
        report.update(result)
        report["observed_at"] = observed
        report["available_at"] = observed
        report["status"] = ("PARTIAL_OPTIONS_TRADES_POC_CONFIRMED" if all(v["accepted_trade_rows"] for v in report["coverage"].values()) else "PARTIAL_OR_EMPTY_PILOT_COVERAGE")
    except Exception as exc:
        report.update(status="FAILED", error=str(exc), error_type=type(exc).__name__)
        raise
    finally:
        report["finished_at"] = now()
        write_json(root / "report.json", report)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-public-poc", action="store_true")
    parser.add_argument("--trades-zip", type=Path)
    parser.add_argument("--reference-json", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/fr/research/mifir_options_poc"))
    print(run(**vars(parser.parse_args())))


if __name__ == "__main__":
    main()
