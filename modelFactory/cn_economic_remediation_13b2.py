"""Sprint 13-B2: version de preuve A2 séparée, sans altérer le référentiel.

Promeut deux distributions dont les termes et le facteur concordent,
et une troisième dont les termes sont confirmés par l'émetteur malgré
un facteur fournisseur contradictoire. Les autres positions restent
bloquées dans le replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_corporate_action_a2 import _audit_gate, _sha_json, classify, load_events
from modelFactory.cn_feature_panel import ROOT

BASE = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13a2"
OUTPUT = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13b2"
SHARE_ONLY_ID = 18481  # sz.002919, 2023-05-31: transfert d'actions sans cash
DATE_SHIFT_ID = 19141  # sz.003038: ex-date source 2022-03-29, facteur daté 2022-03-30
FILING_ID = 20367  # sz.300327: termes confirmés par le rapport annuel de l'émetteur
FILING_URL = "https://static.cninfo.com.cn/finalpage/2023-03-30/1216261135.PDF"


def build(*, base: Path = BASE, output: Path = OUTPUT) -> dict:
    original = json.loads((base / "report.json").read_text(encoding="utf-8"))
    evidence = json.loads((base / "evidence.json").read_text(encoding="utf-8"))
    if (not original["complete"] or original["groups_cached"] != original["groups_total"]
            or original["event_count"] != len(evidence)
            or original["evidence_sha256"] != _sha_json(evidence)
            or not original["preflight"]["all_policies_pass"]):
        raise RuntimeError("Preuve A2 de départ incomplète ou modifiée")
    indices = {item["corporate_action_id"]: index for index, item in enumerate(evidence)}
    if (len(indices) != len(evidence)
            or evidence[indices[SHARE_ONLY_ID]]["reason"] != "invalid_economic_terms"
            or evidence[indices[DATE_SHIFT_ID]]["reason"] != "no_exact_ex_date"
            or evidence[indices[FILING_ID]]["reason"] != "factor_terms_mismatch"):
        raise RuntimeError("Événements B2 absents ou non conformes à l'audit initial")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Remédiation B2 interdite hors alpha_trade_cn")
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
                WHERE a.corporate_action_id IN (:share_id,:date_id,:filing_id)
            """), {"share_id": SHARE_ONLY_ID, "date_id": DATE_SHIFT_ID,
                     "filing_id": FILING_ID}).mappings().all()
            prior_date_shift = conn.execute(text("""
                SELECT `close` FROM stock_bars_daily
                WHERE market_code='CN_A' AND instrument_id=4856
                  AND `date`='2022-03-28'
            """)).scalar_one()
    finally:
        engine.dispose()
    if (len(rows) != 3 or {row["corporate_action_id"] for row in rows}
            != {SHARE_ONLY_ID, DATE_SHIFT_ID, FILING_ID}):
        raise RuntimeError("Événement B2 absent ou mapping BaoStock ambigu")
    source_hashes = {}
    for source_row in rows:
        event = dict(source_row)
        identifier = event["corporate_action_id"]
        source_path = base / "queries" / f"{event['provider_symbol'].replace('.', '_')}-{event['ex_date'].year}.json"
        source_bytes = source_path.read_bytes()
        source = json.loads(source_bytes)
        if source.get("request") != {"method": "query_dividend_data",
                                     "symbol": event["provider_symbol"],
                                     "year": event["ex_date"].year,
                                     "yearType": "operate"}:
            raise RuntimeError("Cache BaoStock B2 incompatible avec la requête attendue")
        if identifier == DATE_SHIFT_ID:
            if (event["instrument_id"] != 4856 or event["ex_date"] != date(2022, 3, 30)
                    or prior_date_shift is None):
                raise RuntimeError("Chronologie du décalage B2 incompatible")
            event["ex_date"] = date(2022, 3, 29)
            event["previous_close"] = prior_date_shift
        amended = classify(event, source["rows"])
        if amended["source_payload_hash"] != evidence[indices[identifier]]["source_payload_hash"]:
            raise RuntimeError("Termes B2 non prouvés par la source et le facteur")
        if identifier == FILING_ID:
            # Le facteur BaoStock est contradictoire (2.738 observé contre
            # 1.109 théorique). Les TERMES et la date sont attestés séparément
            # par le rapport annuel officiel de l'émetteur, pp. 39 et 54.
            # Ce document a été publié en 2023 : preuve ex-post de PnL,
            # jamais feature ou filtre disponible au signal de mai 2022.
            if (event["instrument_id"] != 5243 or event["ex_date"] != date(2022, 5, 31)
                    or amended["reason"] != "factor_terms_mismatch"
                    or amended["cash_per_share_before_tax"] != "0.48"
                    or amended["share_ratio"] != "0.100000"
                    or amended["record_date"] != "2022-05-30"
                    or amended["payment_date"] != "2022-05-31"):
                raise RuntimeError("Termes officiels 300327 incompatibles")
            amended["status"] = "EVIDENCED_DISTRIBUTION"
            amended["reason"] = "official_issuer_filing_confirms_terms_factor_vendor_mismatch"
            amended["kind"] = "CASH_AND_SHARES"
            amended["official_filing_url"] = FILING_URL
            amended["official_filing_published_at"] = "2023-03-30"
            amended["factor_vendor_mismatch_retained"] = True
        elif amended["status"] != "EVIDENCED_DISTRIBUTION":
            raise RuntimeError("Termes B2 non prouvés par la source et le facteur")
        elif identifier == SHARE_ONLY_ID:
            if (amended["kind"] != "BONUS_OR_TRANSFER_SHARES"
                    or amended["cash_per_share_before_tax"] != "0"
                    or amended["share_ratio"] != "0.300000"):
                raise RuntimeError("Distribution sans cash B2 incompatible")
        else:
            if (amended["kind"] != "CASH_AND_SHARES"
                    or amended["cash_per_share_before_tax"] != "0.3"
                    or amended["share_ratio"] != "0.200000"):
                raise RuntimeError("Distribution à ex-date décalée B2 incompatible")
            amended["canonical_ex_date"] = "2022-03-30"
            amended["remediation_kind"] = "SOURCE_EX_DATE_ONE_SESSION_EARLIER"
        evidence[indices[identifier]] = amended
        source_hashes[str(identifier)] = hashlib.sha256(source_bytes).hexdigest()
    report = dict(original)
    report["evidence_sha256"] = _sha_json(evidence)
    report["statuses"] = dict(original["statuses"])
    report["reasons"] = dict(original["reasons"])
    report["statuses"]["EVIDENCED_DISTRIBUTION"] += 3
    report["statuses"]["UNRESOLVED"] -= 3
    report["reasons"]["exact_ex_date_terms_and_factor_reconciled"] += 2
    report["reasons"]["official_issuer_filing_confirms_terms_factor_vendor_mismatch"] = 1
    report["reasons"]["invalid_economic_terms"] -= 1
    report["reasons"]["no_exact_ex_date"] -= 1
    report["reasons"]["factor_terms_mismatch"] -= 1
    report["resolved_events"] += 3
    report["unresolved_events"] -= 3
    events, sessions, delistings = load_events()
    if len(events) != len(evidence):
        raise RuntimeError("Univers d'événements A2 modifié depuis l'audit")
    unresolved_ids = {item["corporate_action_id"] for item in evidence
                      if item["status"] == "UNRESOLVED"}
    dates: dict[int, list[date]] = defaultdict(list)
    for item in events:
        if item["corporate_action_id"] in unresolved_ids:
            dates[int(item["instrument_id"])].append(item["ex_date"])
    report["preflight"] = _audit_gate(dates, sessions, delistings)
    if not report["preflight"]["all_policies_pass"]:
        raise RuntimeError("Gate de couverture B2 non passé")
    report["remediation_13b2"] = {
        "parent_evidence_sha256": original["evidence_sha256"],
        "changed_action_ids": [SHARE_ONLY_ID, DATE_SHIFT_ID, FILING_ID],
        "source_cache_sha256": source_hashes,
        "reasons": ["share_only_blank_cash_explicit_terms_and_factor_reconciled",
                    "one_session_ex_date_shift_source_terms_and_factor_reconciled",
                    "official_issuer_filing_confirms_terms_factor_vendor_mismatch"],
        "official_filing_url": FILING_URL,
        "factor_discrepancy_not_repaired": True,
        "other_unresolved_events_untouched": True,
        "canonical_database_modified": False,
    }
    destination = output / f"evidence-{report['evidence_sha256'][:16]}"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    (destination / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8",
    )
    report["artifact_dir"] = str(destination)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 13-B2: preuve additive du transfert en actions")
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = build(base=args.base, output=args.output)
    print(json.dumps({"evidence_sha256": report["evidence_sha256"],
                      "resolved_events": report["resolved_events"],
                      "path": str(Path(report["artifact_dir"]) / "evidence.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
