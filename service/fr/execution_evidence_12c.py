"""Qualification partielle de preuves FR, sans blanchir les flags historiques."""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
import yaml
from bs4 import BeautifulSoup

from modelFactory.fr_fold7_rebuild import sha, write_json
from service.fr.economic_qualification_12a import normalize_name, parse_issuer_list
from service.fr.universe_contract_6a import ROOT
from service.fr.yahoo_price_reference_pilot import normalize_chart, verified_tls_context

RULE_SOURCES = {
    "target_calendar": "https://www.ecb.europa.eu/paym/target/consolidation/profuse/shared/pdf/2025.APR_p1_fundamentals.en.pdf",
    "standard_t2": "https://www.euronext.com/en/regulation/t1-programme",
    "argan_2025": "https://www.argan.fr/wp-content/uploads/2025/03/20250321-AG-Argan-2025-Votes-et-plan-de-developpement.pdf",
    "ipsos_2025": "https://www.ipsos.com/sites/default/files/Brochure%20AG%202025%20EN_vFINALE.pdf",
    "virbac_payments": "https://corporate.virbac.com/home/investors/shareholders-area.html",
    "planisware_2025": "https://www.wienerborse.at/en/news/vienna-stock-exchange-news/walt-disney-dividends-global-market-06242025",
}
# Explicit reviewed historical dates. No local French holiday substituted for
# TARGET EUR closure; no generalisation to 2026 or actual broker settlement.
TARGET_CLOSED = {
    2024: {"2024-01-01", "2024-03-29", "2024-04-01", "2024-05-01", "2024-12-25", "2024-12-26"},
    2025: {"2025-01-01", "2025-04-18", "2025-04-21", "2025-05-01", "2025-12-25", "2025-12-26"},
}


def standard_settlement(day: date) -> date:
    """Standard intended T+2, NOT an observation of a settled transaction."""
    if day.year not in TARGET_CLOSED or day.weekday() >= 5 or day.isoformat() in TARGET_CLOSED[day.year]:
        raise ValueError("Date hors calendrier TARGET2024/2025")
    count = 0
    while count < 2:
        day += timedelta(days=1)
        if day.year not in TARGET_CLOSED:
            raise ValueError("Règlement sort du périmètre fiscal qualifié")
        if day.weekday() < 5 and day.isoformat() not in TARGET_CLOSED[day.year]:
            count += 1
    return day


def issuer_match(identity: dict, official_name: str, year: int) -> list[dict]:
    """Exact official ESMA name and ordinary equity; no fuzzy taxable negatives."""
    start, end = f"{year}-01-01", f"{year}-12-31"
    if identity["provider_symbol"] == "URW.PA":
        return []  # stapled instrument: issuer match alone does not qualify base
    rows = sorted([v for m in identity["market_reference"] if m["mic"] == "XPAR" for v in m["versions"]
                   if v["asof_from"] <= end and (v["asof_to"] or "9999") >= start], key=lambda v: v["asof_from"])
    cursor = start
    for row in rows:
        if (max(row["asof_from"], start) != cursor or not row["cfi"].startswith("ES")
                or normalize_name(row["name"]) != normalize_name(official_name)):
            return []
        cursor = (date.fromisoformat(min(row["asof_to"] or end, end)) + timedelta(days=1)).isoformat()
    return rows if cursor > end else []


def collect_source(url: str, output: Path) -> dict:
    with urlopen(url, context=verified_tls_context(), timeout=40) as response:
        raw = response.read(15_000_001)
        if response.status != 200 or len(raw) > 15_000_000:
            raise ValueError("Source vide/inaccessible/trop volumineuse")
    if not raw or (url.endswith(".pdf") and not raw.startswith(b"%PDF")):
        raise ValueError("Format de preuve inattendu")
    output.write_bytes(raw)
    return {"url": url, "path": str(output), "sha256": sha(output),
            "observed_at": datetime.now(UTC).isoformat(), "historical_available_at_backdated": False}


def run(output: Path, qualification: Path, *, collect: bool = True) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    sources = {}
    for key, url in RULE_SOURCES.items():
        if not collect:
            sources[key] = {"status": "NOT_COLLECTED", "url": url}
            continue
        try:
            sources[key] = collect_source(url, output / (key + (".pdf" if url.endswith(".pdf") else ".html")))
            sources[key]["status"] = "ARCHIVED_REVIEWED_REFERENCE"
        except Exception as exc:
            sources[key] = {"status": "UNAVAILABLE", "url": url, "error": f"{type(exc).__name__}: {exc}"}
    identity_path = ROOT / "artifacts/fr/sprint6c_reference/identities.jsonl.gz"
    with gzip.open(identity_path, "rt", encoding="utf-8") as stream:
        identities = [json.loads(line) for line in stream]
    identity_report = json.loads((identity_path.parent / "report.json").read_text(encoding="utf-8"))
    if sha(identity_path) != identity_report["files"]["identities"]["sha256"]:
        raise ValueError("Identités modifiées")
    tax = pd.read_parquet(qualification / "tax_issuer_candidates.parquet")
    qualification_report = json.loads((qualification / "report.json").read_text(encoding="utf-8"))
    by_symbol = {r["provider_symbol"]: r for r in identities}
    lists = {}
    for year in (2024, 2025):
        filename = qualification / f"issuer_list_{year}.html"
        expected = qualification_report["sources"][f"issuer_list_{year}"]["sha256"]
        if sha(filename) != expected:
            raise ValueError("Liste BOFiP modifiée")
        lists[year] = parse_issuer_list(filename.read_text(encoding="utf-8"))
    accepted, reviewed = [], []
    for row in tax.itertuples():
        identity = by_symbol.get(row.symbol)
        match = []
        if identity and identity["isin"] == row.isin:
            for name in lists[row.year]:
                versions = issuer_match(identity, name, row.year)
                if versions:
                    match.append((name, versions))
        if len(match) == 1:
            name, versions = match[0]
            accepted.append({"isin": row.isin, "ticker": row.symbol, "from": f"{row.year}-01-01", "to": f"{row.year}-12-31",
                             "liable": True, "evidence": {"bofip": qualification_report["sources"][f"issuer_list_{row.year}"],
                                "official_issuer_name": name, "esma_identity_sha256": sha(identity_path),
                                "esma_versions": versions, "scope": "ORDINARY_CASH_BUY_RESEARCH_ONLY_NO_EXEMPTION"}})
        reviewed.append({"symbol": row.symbol, "isin": row.isin, "year": row.year,
                         "status": "POSITIVE_ISSUER_IDENTITY_QUALIFIED_RESEARCH" if len(match) == 1 else "UNKNOWN_NOT_EXEMPT"})
    (output / "ttf_eligibility_research.yaml").write_text(yaml.safe_dump({"schema_version": 1, "market_code": "FR_EQ",
                            "unknown_policy": "block", "instruments": accepted}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    pd.DataFrame(reviewed).to_parquet(output / "tax_review.parquet", index=False)
    paths = pd.read_parquet(qualification / "holding_path_qualification.parquet")
    settlements = {}
    for day in sorted(paths.entry_session.unique()):
        try:
            value = standard_settlement(date.fromisoformat(day)).isoformat()
            state = "QUALIFIED_STANDARD_INTENDED_T2_NOT_OBSERVED" if all(sources[k]["status"] == "ARCHIVED_REVIEWED_REFERENCE" for k in ("target_calendar", "standard_t2")) else "RULE_SOURCE_NOT_ARCHIVED"
        except ValueError as exc:
            value, state = None, str(exc)
        settlements[day] = {"date": value, "state": state, "actual_settlement_verified": False,
                            "rule_evidence": {k: sources[k] for k in ("target_calendar", "standard_t2")}}
    write_json(output / "settlements.json", settlements)
    # Corrections are a separate overlay, never an overwrite of archived vendor
    # payloads. Payment terms do not establish full corporate action coverage.
    event_reviews = [
        {"symbol": "ARG.PA", "isin": "FR0010481960", "ex_date": "2025-03-26", "payment_date": "2025-04-17", "gross_cash": "3.30",
         "source": "argan_2025", "state": "AGM_APPROVED_CASH_DEFAULT_WITH_SCRIP_OPTION", "notes": "0.80 capital repayment; no election assumed, no personal tax modelled"},
        {"symbol": "IPS.PA", "isin": "FR0000073298", "ex_date": "2025-07-01", "payment_date": "2025-07-03", "gross_cash": "1.85",
         "source": "ipsos_2025", "state": "ANNOUNCED_TERMS_FINAL_APPROVAL_REQUIRES_CONFIRMATION", "notes": "Full year release is not proof of actual payment"},
        {"symbol": "VIRP.PA", "isin": "FR0000031577", "ex_date": None, "payment_date": "2025-06-26", "gross_cash": "1.45",
         "source": "virbac_payments", "state": "ISSUER_PAYMENT_HISTORY_EX_DATE_STILL_TO_CORROBORATE", "notes": "No ex-date invented from payment minus two"},
        {"symbol": "PLNW.PA", "isin": "FR001400PFU4", "ex_date": "2025-06-24", "payment_date": "2025-06-26", "gross_cash": "0.31",
         "source": "planisware_2025", "state": "EXCHANGE_TERMS_ISIN_MATCHED_IF_SOURCE_ARCHIVED", "notes": "Vienna exchange notice, not complete XPAR corporate actions history"},
    ]
    for event in event_reviews:
        event["evidence"] = sources[event["source"]]
        event["source_archived"] = event["evidence"]["status"] == "ARCHIVED_REVIEWED_REFERENCE"
        event["whole_holding_path_ready"] = False
    write_json(output / "dividend_reviews.json", {"reviews": event_reviews})
    # Extract the exact reviewed table rows, not a guess of payment = ex+T2.
    overrides = []
    if sources["planisware_2025"]["status"] == "ARCHIVED_REVIEWED_REFERENCE":
        soup = BeautifulSoup((output / "planisware_2025.html").read_text(encoding="utf-8"), "html.parser")
        rows = [tr.get_text(" ", strip=True) for tr in soup.find_all("tr") if "FR001400PFU4" in tr.get_text()]
        if len(rows) == 1 and all(token in rows[0] for token in ("PLANISWARE", "0.31", "EUR", "06/24/2025", "06/26/2025")):
            overrides.append({"symbol": "PLNW.PA", "ex_date": "2025-06-24", "payment_date": "2025-06-26",
                              "gross_cash": "0.31", "currency": "EUR", "exact_table_row": rows[0],
                              "evidence": sources["planisware_2025"], "state": "INDEPENDENT_EXCHANGE_EVENT_TERMS_VERIFIED"})
    if sources["virbac_payments"]["status"] == "ARCHIVED_REVIEWED_REFERENCE":
        soup = BeautifulSoup((output / "virbac_payments.html").read_text(encoding="utf-8"), "html.parser")
        rows = [tr.get_text(" ", strip=True) for tr in soup.find_all("tr") if "June 26th, 2025" in tr.get_text()]
        if len(rows) == 1 and "1.45" in rows[0]:
            overrides.append({"symbol": "VIRP.PA", "provider_ex_date_not_officially_verified": "2025-06-24",
                              "payment_date": "2025-06-26", "gross_cash": "1.45", "currency": "EUR", "exact_table_row": rows[0],
                              "evidence": sources["virbac_payments"], "state": "ISSUER_PAYMENT_AMOUNT_ONLY_VERIFIED"})
    write_json(output / "dividend_field_overrides.json", {"overrides": overrides, "archive_modified": False,
                                                           "whole_holding_path_ready": False})
    alternative_prices = []
    bad = paths.loc[paths.provider_state.eq("BLOCKED_PRICE_PATH")]
    for symbol, group in bad.groupby("symbol"):
        cache = ROOT / "artifacts/fr/yahoo_daily_reference/cache" / (hashlib.sha256(symbol.encode()).hexdigest()[:16] + "_2018-01-01_2026-10-01.json")
        if cache.exists():
            envelope = json.loads(cache.read_text(encoding="utf-8"))
            reference, metadata = normalize_chart(envelope["payload"])
        else:
            reference, metadata = {}, {}
        for day in sorted({str(d) for days in group.missing_price_days for d in days}):
            alternative_prices.append({"symbol": symbol, "session": day, "yahoo": reference.get(day),
                                       "yahoo_metadata": metadata, "cache_sha256": sha(cache) if cache.exists() else None,
                                       "state": "ALTERNATIVE_ONLY_REQUIRES_OFFICIAL_PRICE_STATUS" if day in reference else "NO_ALTERNATIVE_IN_CACHE",
                                       "economic_verified": False})
    write_json(output / "missing_price_review.json", {"reviews": alternative_prices})
    write_json(output / "official_price_requests.json", {"requested_pairs": len(alternative_prices),
               "requests": [{"symbol": r["symbol"], "isin": by_symbol[r["symbol"]]["isin"],
                             "mics": by_symbol[r["symbol"]]["mics"], "date": r["session"]}
                            for r in alternative_prices]})
    result = {"status": "PARTIAL_EXECUTION_EVIDENCE_QUALIFICATION", "candidate_paths": len(paths),
              "tax_issuer_years": len(reviewed), "positive_tax_issuer_years": len(accepted),
              "unknown_tax_issuer_years": len(reviewed) - len(accepted),
              "settlement_dates": len(settlements), "settlement_rule_state": "STANDARD_T2_RESEARCH_NOT_OBSERVED_SETTLEMENT",
              "dividend_reviews": len(event_reviews), "missing_price_instrument_days": len(alternative_prices),
              "independently_reviewed_dividend_overlays": len(overrides),
              "paths_promoted_to_ready": 0, "sources": sources,
              "qualification_report_sha256": sha(qualification / "report.json"),
              "implementation_sha256": sha(Path(__file__)), "net_pnl": None,
              "remaining_blockers": ["NEGATIVE_OR_ALIAS_TAX_IDENTITY_MAPPING", "FULL_CA_COVERAGE", "OFFICIAL_MISSING_PRICES_AND_EXECUTION_STATUS"],
              "canonical_writes": False, "serving_enabled": False, "models_refit": 0, "confirmation_2026_evaluated": False}
    write_json(output / "report.json", result)
    return result
