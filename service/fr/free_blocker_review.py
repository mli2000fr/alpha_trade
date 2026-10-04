"""Strict, manually reviewed fiscal aliases; no implied negative tax decisions."""
from __future__ import annotations

import gzip
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pandas as pd
import yaml

from modelFactory.fr_fold7_rebuild import sha, write_json
from service.fr.economic_qualification_12a import normalize_name, parse_issuer_list
from service.fr.execution_evidence_12c import collect_source, issuer_match
from service.fr.universe_contract_6a import ROOT


def alias_versions(identity: dict, alias: dict, official_name: str, year: int) -> list[dict]:
    if identity["provider_symbol"] != alias["symbol"] or identity["isin"] != alias["isin"]:
        return []
    if normalize_name(official_name) not in {normalize_name(n) for n in alias["fiscal_names"]}:
        return []
    reviewed = deepcopy(identity)
    permitted = {normalize_name(n) for n in alias["esma_names"]}
    for market in reviewed["market_reference"]:
        for version in market["versions"]:
            if normalize_name(version["name"]) in permitted:
                version["reviewed_original_name"] = version["name"]
                version["name"] = official_name
    return issuer_match(reviewed, official_name, year)


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    previous = ROOT / "artifacts/fr/research/execution_evidence_12c/qualification-20261004-v4"
    qualification = ROOT / "artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2"
    config_path = ROOT / "config/research_fr/ttf_alias_review_20261004.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    (output / "reviewed_alias_manifest.yaml").write_bytes(config_path.read_bytes())
    if config["schema_version"] != 1 or len({r["symbol"] for r in config["aliases"]}) != len(config["aliases"]):
        raise ValueError("Ambiguous reviewed alias manifest")
    sources = {}

    def fetch(alias):
        key, url = alias["symbol"], alias["url"]
        try:
            row = collect_source(url, output / (key + (".pdf" if url.endswith(".pdf") else ".html")))
            if not url.endswith(".pdf") and alias["isin"] not in Path(row["path"]).read_text(encoding="utf-8", errors="replace"):
                raise ValueError("ISIN absent de la source d'identité archivée")
            return key, {**row, "status": "ARCHIVED_MANUAL_IDENTITY_REVIEW_NOT_PRICE_FEED"}
        except Exception as exc:
            return key, {"url": url, "status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=3) as pool:
        sources.update(pool.map(fetch, config["aliases"]))
    identity_path = ROOT / "artifacts/fr/sprint6c_reference/identities.jsonl.gz"
    expected = json.loads((identity_path.parent / "report.json").read_text(encoding="utf-8"))["files"]["identities"]["sha256"]
    if sha(identity_path) != expected:
        raise ValueError("Identity archive changed")
    with gzip.open(identity_path, "rt", encoding="utf-8") as stream:
        identities = {r["provider_symbol"]: r for r in map(json.loads, stream)}
    qr = json.loads((qualification / "report.json").read_text(encoding="utf-8"))
    lists = {}
    for year in (2024, 2025):
        path = qualification / f"issuer_list_{year}.html"
        if sha(path) != qr["sources"][f"issuer_list_{year}"]["sha256"]:
            raise ValueError("BOFiP archive changed")
        lists[year] = parse_issuer_list(path.read_text(encoding="utf-8"))
    aliases = {r["symbol"]: r for r in config["aliases"]}
    tax = pd.read_parquet(previous / "tax_review.parquet")
    eligibility = yaml.safe_load((previous / "ttf_eligibility_research.yaml").read_text(encoding="utf-8"))
    reviews, additions = [], []
    for row in tax.itertuples():
        if row.status != "UNKNOWN_NOT_EXEMPT":
            continue
        identity, alias = identities[row.symbol], aliases.get(row.symbol)
        matched = []
        if alias and identity["isin"] == row.isin:
            for name in lists[row.year]:
                versions = alias_versions(identity, alias, name, row.year)
                if versions:
                    matched.append((name, versions))
        good = len(matched) == 1 and sources.get(row.symbol, {}).get("status", "").startswith("ARCHIVED")
        if good:
            name, versions = matched[0]
            evidence = {"bofip": qr["sources"][f"issuer_list_{row.year}"], "official_issuer_name": name,
                        "esma_identity_sha256": expected, "esma_versions": versions,
                        "manual_alias_manifest_sha256": sha(config_path), "issuer_identity_source": sources[row.symbol],
                        "scope": "POSITIVE_ORDINARY_CASH_BUY_RESEARCH_ONLY_NO_EXEMPTION"}
            additions.append({"isin": row.isin, "ticker": row.symbol, "from": f"{row.year}-01-01",
                              "to": f"{row.year}-12-31", "liable": True, "evidence": evidence})
            tax.loc[(tax.symbol == row.symbol) & (tax.year == row.year), "status"] = "POSITIVE_REVIEWED_ALIAS_QUALIFIED_RESEARCH"
        reason = ("QUALIFIED_POSITIVE_ALIAS" if good else "IDENTITY_SOURCE_NOT_ARCHIVED" if matched
                  else "COMPOSITE_INSTRUMENT_SCOPE" if row.symbol == "URW.PA"
                  else "FOREIGN_ISSUER_SCOPE_PROOF_REQUIRED" if not row.isin.startswith("FR")
                  else "NO_REVIEWED_ANNUAL_LIST_MATCH_NOT_EXEMPT")
        reviews.append({"symbol": row.symbol, "isin": row.isin, "year": int(row.year),
                        "resolved": good, "reason": reason, "matched_official_names": [m[0] for m in matched],
                        "source": sources.get(row.symbol), "negative_liability_inferred": False})
    eligibility["instruments"].extend(additions)
    keys = [(r["isin"], r["from"], r["to"]) for r in eligibility["instruments"]]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate tax intervals")
    (output / "ttf_eligibility_research.yaml").write_text(yaml.safe_dump(eligibility, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tax.to_parquet(output / "tax_review.parquet", index=False)
    write_json(output / "review_of_97_cases.json", {"reviews": reviews})
    write_json(output / "remaining_tax_requests.json", {"requests": [r for r in reviews if not r["resolved"]]})
    report = {"status": "PARTIAL_FREE_FISCAL_REMEDIATION_NOT_ECONOMIC_GO", "reviewed_unknown_cases": len(reviews),
              "new_positive_alias_cases": len(additions), "positive_tax_cases": len(eligibility["instruments"]),
              "remaining_unknown_cases": sum(tax.status.eq("UNKNOWN_NOT_EXEMPT")), "negative_cases_inferred": 0,
              "sources": sources, "canonical_writes": False, "paths_promoted_to_ready": 0, "paid_requests_sent": 0,
              "input_hashes": {str(p): sha(p) for p in (identity_path, config_path, previous / "tax_review.parquet",
                                                       previous / "ttf_eligibility_research.yaml")}}
    write_json(output / "report.json", report)
    return report
