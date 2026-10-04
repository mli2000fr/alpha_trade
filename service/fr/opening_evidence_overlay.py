"""Verified research-only bridge from archived Euronext evidence to rejection."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

from modelFactory.fr_eodhd_euronext_sample_audit import parse_reference
from modelFactory.fr_fold7_rebuild import sha, write_json
from service.fr.euronext_delisted_reference import decrypt_ajax
from service.fr.universe_contract_6a import ROOT


def qualify_no_open(row: dict) -> None:
    if any(row.get(k) is not None for k in ("open", "high", "low")) or row.get("volume") != 0:
        raise ValueError("Absence de transaction non démontrée")
    if row.get("close") != 9550:
        raise ValueError("Clôture portée Artois inattendue")


def run(output: Path) -> dict:
    source = ROOT / "artifacts/fr/research/execution_evidence_12c/missing-prices-euronext-20261004"
    report = json.loads((source / "report.json").read_text(encoding="utf-8"))
    rows = [r for r in report["results"] if r["symbol"] == "ARTO.PA"]
    if len(rows) != 1 or rows[0]["collection_status"] != "COMPLETED":
        raise ValueError("Preuve Artois absente/ambiguë")
    item = rows[0]
    if item["isin"] != "FR0000076952" or item["instrument"]["mic"] != "XPAR":
        raise ValueError("Identité de preuve différente")
    raw = source / "ARTO.PA.encrypted.json"
    if sha(raw) != item["euronext_raw_sha256"]:
        raise ValueError("Réponse Euronext modifiée")
    html = decrypt_ajax(json.loads(raw.read_bytes()), item["instrument"]["key"])
    bars = parse_reference(html)
    if set(bars) != {"2024-10-10"}:
        raise ValueError("Dates de preuve inattendues")
    qualify_no_open(bars["2024-10-10"])
    identity_path = ROOT / "artifacts/fr/sprint6c_reference/identities.jsonl.gz"
    expected = json.loads((identity_path.parent / "report.json").read_text(encoding="utf-8"))["files"]["identities"]["sha256"]
    if sha(identity_path) != expected:
        raise ValueError("Identités modifiées")
    with gzip.open(identity_path, "rt", encoding="utf-8") as stream:
        identity = [r for r in map(json.loads, stream) if r["provider_symbol"] == "ARTO.PA"]
    if len(identity) != 1 or identity[0]["isin"] != item["isin"]:
        raise ValueError("Identité de recherche absente/ambiguë")
    paths_path = ROOT / "artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2/holding_path_qualification.parquet"
    paths = pd.read_parquet(paths_path)
    affected = paths.loc[paths.symbol.eq("ARTO.PA") & paths.provider_state.eq("BLOCKED_PRICE_PATH")].copy()
    affected["no_open_entry_rejection_proof"] = affected.entry_session.eq("2024-10-10")
    affected["economic_return_ready_after_review"] = False
    evidence = {"source_report": str(source / "report.json"), "source_report_sha256": sha(source / "report.json"),
                "raw_path": str(raw), "raw_sha256": sha(raw), "isin": item["isin"], "mic": "XPAR",
                "scope": "OPENING_EXECUTION_REJECTION_ONLY_NOT_HOLDING_VALUATION", "identity_sha256": expected}
    overlay = {"schema_version": 1, "market_code": "FR_EQ", "symbol": "ARTO.PA", "isin": item["isin"],
               "research_uid": identity[0]["research_uid"], "session": "2024-10-10", "open": None,
               "opening_execution": {"status": "NO_OPENING_TRANSACTION", "evidence": evidence},
               "observed_table": bars["2024-10-10"], "intended_consumer": "portfolio_replay_12b entry rejection",
               "automatic_tape_application": False, "not_an_executable_price": True}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "opening_rejection_overlay.json", overlay)
    affected.to_parquet(output / "affected_path_review.parquet", index=False)
    result = {"status": "VERIFIED_NO_OPEN_REJECTION_OVERLAY_NOT_ECONOMIC_GO", "affected_paths": len(affected),
              "entry_rejection_paths": int(affected.no_open_entry_rejection_proof.sum()),
              "other_holding_paths_still_blocked": int((~affected.no_open_entry_rejection_proof).sum()),
              "paths_promoted_to_ready": 0, "canonical_writes": False, "backtest_run": False,
              "input_hashes": {str(paths_path): sha(paths_path), str(raw): sha(raw)}}
    write_json(output / "report.json", result)
    return result
