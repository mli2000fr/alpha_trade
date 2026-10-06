"""Sprint 13-B3: preuve additive pour un transfert d'actions détenu.

Ne change ni la base CN ni les preuves A2/B2. Les événements non prouvés
restent censurés dans le replay économique.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_corporate_action_a2 import _audit_gate, _sha_json, classify, load_events
from modelFactory.cn_feature_panel import ROOT

BASE = (ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b2"
        / "evidence-afd10e157ff253b7")
OUTPUT = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b3"
ACTION_ID = 14811
INSTRUMENT_ID = 3815
EX_DATE = date(2022, 9, 23)
SYMBOL = "sz.002112"


def promote(event: dict[str, Any], rows: list[dict[str, Any]], previous: dict[str, Any]) -> dict[str, Any]:
    """Promote only the exact 10转3 event after factor reconciliation."""
    if (event["corporate_action_id"] != ACTION_ID
            or event["instrument_id"] != INSTRUMENT_ID
            or event["ex_date"] != EX_DATE
            or event["provider_symbol"] != SYMBOL
            or previous["corporate_action_id"] != ACTION_ID
            or previous["status"] != "UNRESOLVED"
            or previous["reason"] != "invalid_economic_terms"):
        raise RuntimeError("Événement B3 différent de la preuve gelée")
    result = classify(event, rows)
    if (result["status"] != "EVIDENCED_DISTRIBUTION"
            or result["kind"] != "BONUS_OR_TRANSFER_SHARES"
            or result["cash_per_share_before_tax"] != "0"
            or result["share_ratio"] != "0.300000"
            or result["record_date"] != "2022-09-22"
            or result["source_payload_hash"] != previous["source_payload_hash"]):
        raise RuntimeError("Transfert B3 non réconcilié avec la source et le facteur")
    result["remediation_kind"] = "EXPLICIT_SHARE_ONLY_BLANK_CASH_RECLASSIFIED"
    return result


def build(*, base: Path = BASE, output: Path = OUTPUT) -> dict[str, Any]:
    report = json.loads((base / "report.json").read_text(encoding="utf-8"))
    evidence = json.loads((base / "evidence.json").read_text(encoding="utf-8"))
    if (report["evidence_sha256"] != _sha_json(evidence)
            or not report["preflight"]["all_policies_pass"]):
        raise RuntimeError("Preuve B2 absente ou modifiée")
    indices = [index for index, item in enumerate(evidence)
               if item["corporate_action_id"] == ACTION_ID]
    if len(indices) != 1:
        raise RuntimeError("Action B3 absente ou dupliquée")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Remédiation B3 interdite hors alpha_trade_cn")
            event = dict(conn.execute(text("""
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
                WHERE a.corporate_action_id=:action_id
            """), {"action_id": ACTION_ID}).mappings().one())
    finally:
        engine.dispose()
    source_path = (ROOT / "artifacts" / "cn" / "corporate_actions"
                   / "sprint13a2" / "queries" / "sz_002112-2022.json")
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    if source.get("request") != {"method": "query_dividend_data", "symbol": SYMBOL,
                                  "year": 2022, "yearType": "operate"}:
        raise RuntimeError("Cache BaoStock B3 incompatible")
    old = evidence[indices[0]]
    promoted = promote(event, source["rows"], old)
    evidence[indices[0]] = promoted
    events, sessions, delistings = load_events()
    if len(events) != len(evidence):
        raise RuntimeError("Univers A2 modifié depuis la preuve B2")
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
    updated["statuses"]["EVIDENCED_DISTRIBUTION"] += 1
    updated["statuses"]["UNRESOLVED"] -= 1
    updated["reasons"]["exact_ex_date_terms_and_factor_reconciled"] += 1
    updated["reasons"]["invalid_economic_terms"] -= 1
    updated["resolved_events"] += 1
    updated["unresolved_events"] -= 1
    updated["preflight"] = _audit_gate(dates, sessions, delistings)
    if not updated["preflight"]["all_policies_pass"]:
        raise RuntimeError("Gate de couverture B3 non passé")
    updated["remediation_13b3"] = {
        "parent_evidence_sha256": report["evidence_sha256"],
        "changed_action_ids": [ACTION_ID],
        "source_cache_sha256": hashlib.sha256(source_bytes).hexdigest(),
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
    parser = argparse.ArgumentParser(description="Preuve CN B3 du transfert en actions")
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
