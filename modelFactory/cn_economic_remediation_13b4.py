"""Sprint 13-B4: reconcile held shareholder rights with issuer buyback dilution.

This is ex-post PnL evidence, not a PIT feature. It does not alter the CN
database, general factor tolerance, trading signals, or B2/B3 evidence.
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
from modelFactory.cn_corporate_action_a2 import TOLERANCE, _audit_gate, _sha_json, classify, load_events
from modelFactory.cn_feature_panel import ROOT

BASE = (ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b3"
        / "evidence-d61c145756ef237d")
OUTPUT = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b4"
SPECS: dict[int, dict[str, Any]] = {
    19014: {
        "instrument_id": 4827, "symbol": "sz.003010", "ex_date": date(2024, 6, 13),
        "record_date": "2024-06-12", "cash": "0.3", "shares": "0.400000",
        "total_shares": 122329340, "eligible_shares": 114591433,
        "issued_shares": 45836573,
        "issuer_url": "https://static.cninfo.com.cn/finalpage/2024-06-05/1220256283.PDF",
        "issuer_published_at": "2024-06-05",
    },
    19015: {
        "instrument_id": 4827, "symbol": "sz.003010", "ex_date": date(2025, 6, 9),
        "record_date": "2025-06-06", "cash": "0.5", "shares": "0.400000",
        "total_shares": 164030506, "eligible_shares": 158643606,
        "issued_shares": 63457442,
        "issuer_url": "https://disc.static.szse.cn/download/disc/disk03/finalpage/2025-08-20/11eb9df5-71c7-4f9a-8f17-23e4bcb263e8.PDF",
        "issuer_published_at": "2025-08-20",
    },
    24005: {
        "instrument_id": 6043, "symbol": "sz.301042", "ex_date": date(2024, 5, 27),
        "record_date": "2024-05-24", "cash": "1.2", "shares": "0.000000",
        "total_shares": 69738577, "eligible_shares": 67648943,
        "issued_shares": 0,
        "issuer_url": "https://static.cninfo.com.cn/finalpage/2025-04-25/1223276657.PDF",
        "issuer_published_at": "2025-04-25",
    },
}


def promote(event: dict[str, Any], rows: list[dict[str, Any]],
            previous: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Require exact rights plus issuer-adjusted factor reconciliation."""
    if (event["corporate_action_id"] != previous["corporate_action_id"]
            or event["instrument_id"] != spec["instrument_id"]
            or event["provider_symbol"] != spec["symbol"]
            or event["ex_date"] != spec["ex_date"]
            or previous["status"] != "UNRESOLVED"
            or previous["reason"] != "factor_terms_mismatch"
            or spec["eligible_shares"] >= spec["total_shares"]
            or spec["eligible_shares"] <= 0):
        raise RuntimeError("Événement B4 différent des preuves gelées")
    result = classify(event, rows)
    if (result["reason"] != "factor_terms_mismatch"
            or result["cash_per_share_before_tax"] != spec["cash"]
            or result["share_ratio"] != spec["shares"]
            or result["record_date"] != spec["record_date"]
            or result["source_payload_hash"] != previous["source_payload_hash"]):
        raise RuntimeError("Droits B4 incompatibles avec la source BaoStock")
    total = Decimal(spec["total_shares"])
    eligible = Decimal(spec["eligible_shares"])
    issued = Decimal(spec["issued_shares"])
    if abs(issued - eligible * Decimal(spec["shares"])) >= 1:
        raise RuntimeError("Émission B4 incompatible avec les droits par action")
    prior = Decimal(result["prior_raw_close"])
    observed = Decimal(result["observed_factor_ratio"])
    diluted_cash = Decimal(spec["cash"]) * eligible / total
    expected = prior * (1 + issued / total) / (prior - diluted_cash)
    error = abs(expected - observed) / expected
    if error > TOLERANCE:
        raise RuntimeError("Facteur B4 non réconcilié après dilution officielle")
    result.update({
        "status": "EVIDENCED_DISTRIBUTION",
        "reason": "official_issuer_buyback_dilution_reconciles_factor",
        "kind": "CASH_AND_SHARES" if issued else "CASH_DIVIDEND",
        "remediation_kind": "ISSUER_ELIGIBLE_VS_TOTAL_SHARES",
        "official_issuer_url": spec["issuer_url"],
        "official_issuer_published_at": spec["issuer_published_at"],
        "issuer_total_shares": spec["total_shares"],
        "issuer_eligible_shares": spec["eligible_shares"],
        "issuer_issued_shares": spec["issued_shares"],
        "issuer_diluted_cash_per_total_share": str(diluted_cash),
        "issuer_adjusted_expected_factor_ratio": str(expected),
        "issuer_adjusted_factor_relative_error": str(error),
        "original_factor_mismatch_retained": True,
    })
    return result


def build(*, base: Path = BASE, output: Path = OUTPUT) -> dict[str, Any]:
    report = json.loads((base / "report.json").read_text(encoding="utf-8"))
    evidence = json.loads((base / "evidence.json").read_text(encoding="utf-8"))
    if (report["evidence_sha256"] != _sha_json(evidence)
            or not report["preflight"]["all_policies_pass"]):
        raise RuntimeError("Preuve B3 absente ou modifiée")
    indices = {item["corporate_action_id"]: index for index, item in enumerate(evidence)}
    if len(indices) != len(evidence) or not set(SPECS).issubset(indices):
        raise RuntimeError("Actions B4 absentes ou dupliquées")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Remédiation B4 interdite hors alpha_trade_cn")
            rows = conn.execute(text("""
                SELECT a.corporate_action_id,a.instrument_id,a.ex_date,
                       a.factor_value,a.previous_factor_value,a.source_payload_hash,
                       p.provider_symbol,
                       (SELECT b.`close` FROM stock_bars_daily b
                        WHERE b.instrument_id=a.instrument_id AND b.market_code='CN_A'
                          AND b.`date`<a.ex_date ORDER BY b.`date` DESC LIMIT 1) previous_close
                FROM cn_corporate_actions a
                JOIN instrument_provider_symbols p ON p.instrument_id=a.instrument_id
                  AND p.provider='baostock' AND p.valid_from<=a.ex_date
                  AND (p.valid_to IS NULL OR p.valid_to>=a.ex_date)
                WHERE a.corporate_action_id IN (19014,19015,24005)
            """)).mappings().all()
    finally:
        engine.dispose()
    if len(rows) != len(SPECS):
        raise RuntimeError("Mapping BaoStock B4 incomplet ou ambigu")
    source_hashes: dict[str, str] = {}
    for db_row in rows:
        event = dict(db_row)
        action_id = event["corporate_action_id"]
        spec = SPECS[action_id]
        source_path = (ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13a2"
                       / "queries" / f"{spec['symbol'].replace('.', '_')}-{spec['ex_date'].year}.json")
        source_bytes = source_path.read_bytes()
        source = json.loads(source_bytes)
        if source.get("request") != {"method": "query_dividend_data",
                                      "symbol": spec["symbol"],
                                      "year": spec["ex_date"].year,
                                      "yearType": "operate"}:
            raise RuntimeError("Cache BaoStock B4 incompatible")
        evidence[indices[action_id]] = promote(event, source["rows"],
                                               evidence[indices[action_id]], spec)
        source_hashes[str(action_id)] = hashlib.sha256(source_bytes).hexdigest()
    events, sessions, delistings = load_events()
    if len(events) != len(evidence):
        raise RuntimeError("Univers A2 modifié depuis la preuve B3")
    unresolved_ids = {item["corporate_action_id"] for item in evidence
                      if item["status"] == "UNRESOLVED"}
    dates: dict[int, list[date]] = defaultdict(list)
    for item in events:
        if item["corporate_action_id"] in unresolved_ids:
            dates[int(item["instrument_id"])].append(item["ex_date"])
    updated = dict(report)
    updated["evidence_sha256"] = _sha_json(evidence)
    updated["statuses"] = dict(report["statuses"])
    updated["reasons"] = dict(report["reasons"])
    updated["statuses"]["EVIDENCED_DISTRIBUTION"] += len(SPECS)
    updated["statuses"]["UNRESOLVED"] -= len(SPECS)
    updated["reasons"]["official_issuer_buyback_dilution_reconciles_factor"] = len(SPECS)
    updated["reasons"]["factor_terms_mismatch"] -= len(SPECS)
    updated["resolved_events"] += len(SPECS)
    updated["unresolved_events"] -= len(SPECS)
    updated["preflight"] = _audit_gate(dates, sessions, delistings)
    if not updated["preflight"]["all_policies_pass"]:
        raise RuntimeError("Gate de couverture B4 non passé")
    updated["remediation_13b4"] = {
        "parent_evidence_sha256": report["evidence_sha256"],
        "changed_action_ids": sorted(SPECS),
        "source_cache_sha256": source_hashes,
        "official_issuer_urls": {str(key): item["issuer_url"] for key, item in SPECS.items()},
        "other_unresolved_events_untouched": True,
        "canonical_database_modified": False,
        "ex_post_pnl_evidence_not_signal_feature": True,
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
    parser = argparse.ArgumentParser(description="Preuve CN B4 des droits malgré actions rachetées")
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = build(base=args.base, output=args.output)
    print(json.dumps({"evidence_sha256": report["evidence_sha256"],
                      "resolved_events": report["resolved_events"],
                      "path": str(Path(report["artifact_dir"]) / "evidence.json")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
