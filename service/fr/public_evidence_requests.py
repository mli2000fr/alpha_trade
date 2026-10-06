"""Public evidence pass and bounded independent-evidence request, research only.

No automatic promotion: an issuer announcement is not a complete action feed,
and an archived PDF is not automatically a verified economic fact.
"""
from __future__ import annotations

import gzip
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from modelFactory.fr_fold7_rebuild import sha, write_json
from service.fr.execution_evidence_12c import collect_source
from service.fr.universe_contract_6a import ROOT

PUBLIC_SOURCES = {
    "lectra_dividend": "https://www.lectra.com/fr/investisseurs/information-actionnaires/dividende",
    "ses_agm": "https://www.ses.com/press-release/ses-announces-annual-general-meeting-voting-results",
    "ses_paid": "https://www.ses.com/press-release/ses-q1-2025-results",
    "abc_agm": "https://www.abc-arbitrage.com/wp-content/uploads/2025/06/ABCA-CP-AG-2025-compte-rendu-assemblee-generale-VF.docx.pdf",
    "abc_calendar": "https://www.abc-arbitrage.com/fr/agenda-date/",
    "argan_agm_no_www": "https://argan.fr/wp-content/uploads/2025/03/20250321-AG-Argan-2025-Votes-et-plan-de-developpement.pdf",
    "argan_scrip": "https://www.argan.fr/dividende-en-actions-2025-evolution-du-capital/",
    "stif_proposal": "https://investir.stif.fr/wp-content/uploads/2025/03/20250327_STIF_RA2024_VDef-1.pdf",
    "opmobility_proposal": "https://www.opmobility.com/wp-content/uploads/2025/03/opmobility-deu-2024-fr.pdf",
    "robertet_votes": "https://www.robertet.com/wp-content/uploads/2025/12/ACTUS-0-16359-robertet-resultat-du-vote_ag-4-juin-2025.pdf",
    "robertet_resolutions": "https://www.robertet.com/wp-content/uploads/2025/12/ACTUS-0-16121-robertet-sa-agm-2025-texte-des-resolutions.pdf",
    "vetoquinol_proposal": "https://www.vetoquinol.com/fr/publication/6009/view",
    "jacquet_calendar": "https://www.jacquetmetals.com/fichiers/communiques/2025/JM_CP_T125_FR.pdf",
    "ipsos_paid": "https://ml-eu.globenewswire.com/Resource/Download/95074133-74a4-4290-b4da-9b2f33b86559",
    "stif_balo": "https://investir.stif.fr/wp-content/uploads/2025/04/202504162501055.pdf",
}

# Human-reviewed source facts. Ex-dates never inferred from payment minus T+2.
# Source access and semantic review are separate states, as are proposals/payment.
REVIEWS = [
    {"symbol": "ABCA.PA", "source": "abc_agm", "ex_date": "2025-07-08", "payment_date": "2025-07-10", "cash": "0.04", "state": "APPROVED_TERMS", "remaining": "gross/net terminology; independent complete coverage", "vendor_conflict": "paymentDate=2025-07-01 precedes ex-date"},
    {"symbol": "ARG.PA", "source": "argan_agm_no_www", "ex_date": "2025-03-26", "payment_date": "2025-04-17", "cash": "3.30", "state": "APPROVED_TERMS_SCRIP_CASH_DEFAULT", "remaining": "archive access; 0.80 capital repayment; no election assumed"},
    {"symbol": "LSS.PA", "source": "lectra_dividend", "ex_date": None, "payment_date": "2025-05-05", "cash": "0.40", "state": "APPROVED_ANNOUNCED_PAYMENT", "remaining": "official ex-date; full coverage"},
    {"symbol": "SESG.PA", "source": "ses_agm", "ex_date": None, "payment_date": "2024-10-17", "cash": "0.25", "state": "REPORTED_PAID_A_SHARE", "remaining": "FDR/class matching, ex-date and foreign withholding; full coverage"},
    {"symbol": "SESG.PA", "source": "ses_paid", "ex_date": None, "payment_date": "2025-04-17", "cash": "0.25", "state": "REPORTED_PAID_A_SHARE", "remaining": "FDR/class matching, ex-date and foreign withholding; full coverage"},
    {"symbol": "ALSTI.PA", "source": "stif_proposal", "ex_date": None, "payment_date": None, "cash": "0.59", "state": "PROPOSAL_ONLY", "remaining": "final AGM approval, ex-date, payment date"},
    {"symbol": "OPM.PA", "source": "opmobility_proposal", "ex_date": None, "payment_date": "2025-05-02", "cash": "0.36", "state": "PROPOSAL_BALANCE_NOT_TOTAL_ANNUAL_060", "remaining": "final approval; official ex-date"},
    {"symbol": "VETO.PA", "source": "vetoquinol_proposal", "ex_date": None, "payment_date": None, "payment_deadline": "2025-06-06", "cash": "0.89", "state": "PROPOSED_PAYMENT_NO_LATER_THAN", "remaining": "final approval, ex-date, actual/scheduled exact payment"},
    {"symbol": "JCQ.PA", "source": "jacquet_calendar", "ex_date": None, "payment_date": "2025-07-03", "cash": None, "state": "ANNOUNCED_CALENDAR_ONLY", "remaining": "approved amount and official ex-date"},
    {"symbol": "RBT.PA", "source": "robertet_resolutions", "ex_date": None, "payment_date": "2025-07-01", "cash": "10.00", "state": "RESOLUTION_TERMS_VOTE_DOCUMENT_ARCHIVED_SEPARATELY", "remaining": "link resolution 3 to vote outcome, exact instrument class and official ex-date; full coverage"},
    {"symbol": "IPS.PA", "source": "ipsos_paid", "ex_date": None, "payment_date": "2025-07-03", "cash": "1.85", "state": "REPORTED_PAID_SEMESTER_2025_SECTION_6_4_6", "remaining": "official ex-date; net/gross terminology and complete coverage; webpage title incorrectly says 2024, document itself says June 2025"},
    {"symbol": "ALSTI.PA", "source": "stif_balo", "ex_date": None, "payment_date": "2025-06-02", "cash": "0.59", "state": "PROPOSED_TERMS_BALO_2501055_20250416", "remaining": "final AGM approval and official ex-date; proposed payment is not proof of actual payment"},
]


def request_packet(paths: pd.DataFrame, tax: pd.DataFrame, identities: list[dict], events: list[dict]) -> dict:
    """Exact population, including unselected candidates; no return-based pruning."""
    by_symbol = {row["provider_symbol"]: row for row in identities}
    symbols = sorted(paths.symbol.unique())
    if set(symbols) - by_symbol.keys():
        raise ValueError("Missing identity for request population")
    coverage = []
    for (symbol, fold), group in paths.groupby(["symbol", "fold"], sort=True):
        identity = by_symbol[symbol]
        coverage.append({"symbol": symbol, "isin": identity["isin"], "mics": identity["mics"],
                         "fold": int(fold), "from": min(group.entry_session), "to": max(group.exit_session),
                         "candidate_paths": len(group), "scope": "COMPLETE_ACTION_COVERAGE_INCLUDING_NO_EVENT_DAYS"})
    unknowns = []
    for row in tax.loc[tax.status.eq("UNKNOWN_NOT_EXEMPT")].itertuples():
        identity = by_symbol[row.symbol]
        unknowns.append({"symbol": row.symbol, "isin": row.isin, "year": int(row.year),
                         "mics": identity["mics"], "esma_names": sorted({v["name"] for m in identity["market_reference"]
                             for v in m["versions"] if v["asof_from"] <= f"{row.year}-12-31"
                             and (v["asof_to"] or "9999") >= f"{row.year}-01-01"}),
                         "state": "UNKNOWN_NOT_EXEMPT", "route": "PUBLIC_IDENTITY_REVIEW_FIRST_NOT_PAID_PRICE_REQUEST"})
    prices = []
    for symbol, group in paths.loc[paths.provider_state.eq("BLOCKED_PRICE_PATH")].groupby("symbol"):
        for day in sorted({str(d) for days in group.missing_price_days for d in days}):
            prices.append({"symbol": symbol, "isin": by_symbol[symbol]["isin"], "mics": by_symbol[symbol]["mics"],
                           "session": day, "state": "PUBLIC_NO_OPEN_ZERO_VOLUME_EXECUTION_REJECTION_REQUIRED" if symbol == "ARTO.PA"
                           and day == "2024-10-10" else "OFFICIAL_OHLC_VOLUME_STATUS_REQUIRED",
                           "request_paid_price": not (symbol == "ARTO.PA" and day == "2024-10-10")})
    event_requests = []
    for item in events:
        symbol = item["symbol"]
        if symbol not in symbols:
            continue
        event_requests.append({**item, "isin": by_symbol[symbol]["isin"], "mics": by_symbol[symbol]["mics"],
                               "request": "independent event terms and provenance; vendor fields are leads only"})
    return {"coverage": coverage, "tax": unknowns, "prices": prices, "events": event_requests}


def run(output: Path, qualification: Path, evidence: Path, *, collect: bool = True) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    sources = {}

    def fetch(item):
        key, url = item
        if not collect:
            return key, {"status": "NOT_COLLECTED", "url": url}
        try:
            is_pdf = url.endswith(".pdf") or key == "ipsos_paid"
            path = output / (key + (".pdf" if is_pdf else ".html"))
            row = collect_source(url, path)
            if is_pdf and not path.read_bytes().startswith(b"%PDF"):
                raise ValueError("Expected PDF archive")
            return key, {**row, "status": "ARCHIVED_NOT_AUTOMATICALLY_QUALIFIED"}
        except Exception as exc:
            return key, {"url": url, "status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=3) as pool:
        sources.update(pool.map(fetch, PUBLIC_SOURCES.items()))
    identity_path = ROOT / "artifacts/fr/sprint6c_reference/identities.jsonl.gz"
    identity_report = json.loads((identity_path.parent / "report.json").read_text(encoding="utf-8"))
    if sha(identity_path) != identity_report["files"]["identities"]["sha256"]:
        raise ValueError("Identity archive changed")
    with gzip.open(identity_path, "rt", encoding="utf-8") as stream:
        identities = [json.loads(line) for line in stream]
    paths = pd.read_parquet(qualification / "holding_path_qualification.parquet")
    tax = pd.read_parquet(evidence / "tax_review.parquet")
    events = json.loads((qualification / "corporate_events.json").read_text(encoding="utf-8"))["events"]
    packet = request_packet(paths, tax, identities, events)
    for key, rows in packet.items():
        write_json(output / f"requests_{key}.json", {"requests": rows})
    # Preserve every exact holding window, not only the envelope requested from a supplier.
    paths[["fold", "research_uid", "symbol", "entry_session", "exit_session"]].to_parquet(output / "exact_holding_windows.parquet", index=False)
    reviews = [{**r, "evidence": sources[r["source"]], "whole_holding_path_ready": False,
                "eligible_for_automatic_overlay": False} for r in REVIEWS]
    write_json(output / "public_event_reviews.json", {"reviews": reviews})
    report = {"status": "BOUNDED_PUBLIC_PASS_REQUEST_PACKET_NOT_ECONOMIC_GO", "candidate_paths": len(paths),
              "symbols": paths.symbol.nunique(), "coverage_intervals": len(packet["coverage"]),
              "tax_unknown_issuer_years": len(packet["tax"]), "tax_unknown_symbols": len({r["symbol"] for r in packet["tax"]}),
              "official_price_pairs_to_request": sum(r["request_paid_price"] for r in packet["prices"]),
              "public_no_open_execution_cases": sum(not r["request_paid_price"] for r in packet["prices"]),
              "provider_event_leads": len(packet["events"]), "reviewed_public_facts": len(reviews),
              "sources": sources, "paths_promoted_to_ready": 0, "net_pnl": None, "canonical_writes": False,
              "paid_requests_sent": 0, "all_free_sources_exhausted": False,
              "input_hashes": {str(p): sha(p) for p in [identity_path, qualification / "holding_path_qualification.parquet",
                               qualification / "corporate_events.json", evidence / "tax_review.parquet"]}}
    report["output_hashes"] = {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    write_json(output / "report.json", report)
    return report
