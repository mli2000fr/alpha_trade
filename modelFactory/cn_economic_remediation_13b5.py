"""Sprint 13-B5: event-specific CN economic rights, never PIT signal data.

Two issuer-confirmed cash distributions have contradictory vendor factors.
A third factor reset follows an official ticker change with unchanged holdings.
The evidence is additive and leaves all other unresolved actions censored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_corporate_action_a2 import _audit_gate, _sha_json, classify, load_events
from modelFactory.cn_feature_panel import ROOT

BASE = (ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b4"
        / "evidence-2e2911cef66c0118")
OUTPUT = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b5"

SPECS: dict[int, dict[str, Any]] = {
    16255: {
        "instrument_id": 4201, "symbol": "sz.002443",
        "ex_date": date(2022, 5, 30), "old_reason": "factor_terms_mismatch",
        "cash": "0.4", "shares": "0.000000", "record": "2022-05-27",
        "factor": "4.0738490000", "previous_factor": "1.0578510000",
        "issuer_url": "https://stockn.xueqiu.com/SZ002443/20230421366633.pdf",
        "issuer_published_at": "2023-04-22",
        "remediation_kind": "ISSUER_CASH_TERMS_FACTOR_CONFLICT_RETAINED",
    },
    23221: {
        "instrument_id": 5844, "symbol": "sz.300862",
        "ex_date": date(2025, 12, 12), "old_reason": "factor_terms_mismatch",
        "cash": "0.005", "shares": "0.000000", "record": "2025-12-11",
        "factor": "1.0000000000", "previous_factor": "1.4250280000",
        "issuer_url": (
            "https://disc.static.szse.cn/disc/disk03/finalpage/"
            "2025-12-04/94c9f73c-4b86-4d29-9244-cfe07216b821.PDF"
        ),
        "issuer_published_at": "2025-12-04",
        "remediation_kind": "ISSUER_CASH_TERMS_FACTOR_CONFLICT_RETAINED",
    },
    316: {
        "instrument_id": 82, "symbol": "sz.302132",
        "ex_date": date(2025, 2, 18), "old_reason": "no_exact_ex_date",
        "factor": "5.9756780000", "previous_factor": "1.0000000000",
        "issuer_url": "https://static.cninfo.com.cn/finalpage/2025-02-15/1222544408.PDF",
        "issuer_published_at": "2025-02-15",
        "remediation_kind": "OFFICIAL_TICKER_CHANGE_SAME_HOLDINGS",
    },
}


def promote(event: dict[str, Any], rows: list[dict[str, Any]],
            previous: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Accept only the three pre-identified events and preserve factor conflict."""
    identifier = event["corporate_action_id"]
    if (identifier not in SPECS or spec is not SPECS[identifier]
            or identifier != previous["corporate_action_id"]
            or event["instrument_id"] != spec["instrument_id"]
            or event["provider_symbol"] != spec["symbol"]
            or event["ex_date"] != spec["ex_date"]
            or previous["status"] != "UNRESOLVED"
            or previous["reason"] != spec["old_reason"]
            or str(event["factor_value"]) != spec["factor"]
            or str(event["previous_factor_value"]) != spec["previous_factor"]
            or event["source_payload_hash"] != previous["source_payload_hash"]):
        raise RuntimeError("Événement B5 différent de la preuve gelée")
    prior = Decimal(str(event["previous_close"]))
    opening = Decimal(str(event["event_open"]))
    if prior <= 0 or opening <= 0 or abs(opening / prior - 1) >= Decimal("0.10"):
        raise RuntimeError("Cours bruts B5 incompatibles avec la continuité observée")
    result = classify(event, rows)
    if (result["reason"] != spec["old_reason"]
            or result["source_payload_hash"] != previous["source_payload_hash"]):
        raise RuntimeError("Réponse BaoStock B5 incompatible")
    if identifier == 316:
        if ((spec["ex_date"] - date(2025, 2, 17)).days != 1
                or any(row.get("dividOperateDate") == "2025-02-18" for row in rows)):
            raise RuntimeError("Changement de code B5 non isolé")
        result = dict(previous)
        result.update({
            "status": "EVIDENCED_NON_DISTRIBUTION",
            "reason": "official_ticker_change_no_holder_rights",
            "kind": "TICKER_CHANGE_NO_HOLDER_RIGHTS",
            "cash_per_share_before_tax": "0",
            "share_ratio": "0",
            "official_previous_symbol": "sz.300114",
            "official_effective_date": "2025-02-17",
            "historical_provider_symbol_valid_from_requires_audit": True,
        })
    else:
        if (result["cash_per_share_before_tax"] != spec["cash"]
                or result["share_ratio"] != spec["shares"]
                or result["record_date"] != spec["record"]
                or result["payment_date"] != spec["ex_date"].isoformat()):
            raise RuntimeError("Droits B5 incompatibles avec l'avis de l'émetteur")
        result.update({
            "status": "EVIDENCED_DISTRIBUTION",
            "reason": "official_issuer_cash_rights_vendor_factor_conflict",
            "kind": "CASH_DIVIDEND",
        })
    result.update({
        "remediation_kind": spec["remediation_kind"],
        "official_issuer_url": spec["issuer_url"],
        "official_issuer_published_at": spec["issuer_published_at"],
        "original_factor_mismatch_retained": True,
        "previous_raw_close": str(prior),
        "ex_date_raw_open": str(opening),
        "ex_date_raw_open_gap": str(opening / prior - 1),
        "ex_post_pnl_evidence_not_signal_feature": True,
    })
    return result


def build(*, base: Path = BASE, output: Path = OUTPUT) -> dict[str, Any]:
    report = json.loads((base / "report.json").read_text(encoding="utf-8"))
    evidence = json.loads((base / "evidence.json").read_text(encoding="utf-8"))
    if (report["evidence_sha256"] != _sha_json(evidence)
            or not report["preflight"]["all_policies_pass"]):
        raise RuntimeError("Preuve B4 absente ou modifiée")
    indices = {item["corporate_action_id"]: index for index, item in enumerate(evidence)}
    if len(indices) != len(evidence) or not set(SPECS).issubset(indices):
        raise RuntimeError("Actions B5 absentes ou dupliquées")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Remédiation B5 interdite hors alpha_trade_cn")
            events = conn.execute(text("""
                SELECT a.corporate_action_id,a.instrument_id,a.ex_date,
                       a.factor_value,a.previous_factor_value,a.source_payload_hash,
                       p.provider_symbol,
                       (SELECT b.`close` FROM stock_bars_daily b
                        WHERE b.instrument_id=a.instrument_id AND b.market_code='CN_A'
                          AND b.`date`<a.ex_date ORDER BY b.`date` DESC LIMIT 1) previous_close,
                       (SELECT b.`open` FROM stock_bars_daily b
                        WHERE b.instrument_id=a.instrument_id AND b.market_code='CN_A'
                          AND b.`date`=a.ex_date LIMIT 1) event_open
                FROM cn_corporate_actions a
                JOIN instrument_provider_symbols p ON p.instrument_id=a.instrument_id
                  AND p.provider='baostock' AND p.valid_from<=a.ex_date
                  AND (p.valid_to IS NULL OR p.valid_to>=a.ex_date)
                WHERE a.corporate_action_id IN (316,16255,23221)
            """)).mappings().all()
    finally:
        engine.dispose()
    if len(events) != len(SPECS):
        raise RuntimeError("Mapping BaoStock B5 incomplet ou ambigu")
    source_hashes: dict[str, str] = {}
    for row in events:
        event = dict(row)
        identifier = event["corporate_action_id"]
        spec = SPECS[identifier]
        source_path = (ROOT / "artifacts" / "cn" / "corporate_actions"
                       / "sprint13a2" / "queries"
                       / f"{spec['symbol'].replace('.', '_')}-{spec['ex_date'].year}.json")
        source_bytes = source_path.read_bytes()
        source = json.loads(source_bytes)
        if source.get("request") != {
            "method": "query_dividend_data", "symbol": spec["symbol"],
            "year": spec["ex_date"].year, "yearType": "operate",
        }:
            raise RuntimeError("Cache BaoStock B5 incompatible")
        evidence[indices[identifier]] = promote(event, source["rows"],
                                                evidence[indices[identifier]], spec)
        source_hashes[str(identifier)] = hashlib.sha256(source_bytes).hexdigest()
    canonical_events, sessions, delistings = load_events()
    if len(canonical_events) != len(evidence):
        raise RuntimeError("Univers A2 modifié depuis la preuve B4")
    unresolved_ids = {item["corporate_action_id"] for item in evidence
                      if item["status"] == "UNRESOLVED"}
    dates: dict[int, list[date]] = defaultdict(list)
    for item in canonical_events:
        if item["corporate_action_id"] in unresolved_ids:
            dates[int(item["instrument_id"])].append(item["ex_date"])
    updated = dict(report)
    updated["evidence_sha256"] = _sha_json(evidence)
    updated["statuses"] = dict(report["statuses"])
    updated["reasons"] = dict(report["reasons"])
    updated["statuses"]["EVIDENCED_DISTRIBUTION"] += 2
    updated["statuses"]["EVIDENCED_NON_DISTRIBUTION"] = 1
    updated["statuses"]["UNRESOLVED"] -= 3
    updated["reasons"]["official_issuer_cash_rights_vendor_factor_conflict"] = 2
    updated["reasons"]["official_ticker_change_no_holder_rights"] = 1
    updated["reasons"]["factor_terms_mismatch"] -= 2
    updated["reasons"]["no_exact_ex_date"] -= 1
    updated["resolved_events"] += 3
    updated["unresolved_events"] -= 3
    updated["preflight"] = _audit_gate(dates, sessions, delistings)
    if not updated["preflight"]["all_policies_pass"]:
        raise RuntimeError("Gate de couverture B5 non passé")
    updated["remediation_13b5"] = {
        "parent_evidence_sha256": report["evidence_sha256"],
        "changed_action_ids": sorted(SPECS),
        "source_cache_sha256": source_hashes,
        "official_issuer_urls": {str(key): item["issuer_url"] for key, item in SPECS.items()},
        "other_unresolved_events_untouched": True,
        "canonical_database_modified": False,
        "ex_post_pnl_evidence_not_signal_feature": True,
        "historical_symbol_mapping_302132_requires_audit": True,
    }
    destination = output / f"evidence-{updated['evidence_sha256'][:16]}"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    (destination / "report.json").write_text(
        json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    updated["artifact_dir"] = str(destination)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Preuve B5 des droits et du changement de code CN")
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = build(base=args.base, output=args.output)
    print(json.dumps({
        "evidence_sha256": report["evidence_sha256"],
        "resolved_events": report["resolved_events"],
        "path": str(Path(report["artifact_dir"]) / "evidence.json"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
