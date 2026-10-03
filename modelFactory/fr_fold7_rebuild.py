"""Reconstruction FR de recherche avec preuves OHLC ciblées, sans écriture SQL."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from modelFactory.fr_eodhd_euronext_sample_audit import decrypt_ajax, parse_reference
from modelFactory.fr_fold7_price_evidence_review import comparison
from service.fr.universe_liquidity_6b import _load_symbol_bars

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
REASON = "INDEPENDENT_PRICE_CORROBORATION_MISSING"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def verified_pairs(ledger_path: Path, collection: Path) -> dict:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    report = json.loads((collection / "report.json").read_text(encoding="utf-8"))
    review = json.loads((collection / "evidence_review.json").read_text(encoding="utf-8"))
    if sha(ledger_path) != review["ledger_sha256"] or sha(collection / "report.json") != review["collection_report_sha256"]:
        raise ValueError("Les sources de preuves ont changé")
    if report.get("tls_verified") is not True:
        raise ValueError("Transport des preuves non vérifié")
    collected = {r["symbol"]: r for r in report["results"]}
    reviewed = {(r["symbol"], r["date"]): r for r in review["results"]}
    cache, approved = {}, {}
    for request in ledger["requests"]:
        symbol, day = request["symbol"], request["date"]
        row = collected[symbol]
        instrument = row["instrument"]
        if (row["collection_status"] != "COMPLETED" or row["isin"] != request["isin"]
                or instrument["product_data"] != f'{request["isin"]}-{instrument["mic"]}'
                or instrument["mic"] not in request["mics"] or row["euronext_adjusted_parameter"] != "Y"):
            raise ValueError(f"Identité/convention de preuve divergente {symbol}")
        if symbol not in cache:
            encrypted = collection / f"{symbol}.encrypted.json"
            html_path = collection / f"{symbol}.history.html"
            html = html_path.read_text(encoding="utf-8")
            if sha(encrypted) != row["euronext_raw_sha256"] or decrypt_ajax(json.loads(encrypted.read_bytes()), instrument["key"]) != html:
                raise ValueError(f"Charge utile de preuve divergente {symbol}")
            cache[symbol] = (parse_reference(html), _load_symbol_bars(ROOT / "artifacts/fr/eodhd/backfill_2016", symbol), sha(html_path))
        reference, bars, html_hash = cache[symbol]
        evidence = reviewed[(symbol, day)]
        if bars.get(day) != request["eodhd"] or html_hash != evidence["source_html_sha256"]:
            raise ValueError(f"Source de prix divergente {symbol}/{day}")
        state = comparison(reference.get(day), bars.get(day))
        if state != evidence["eodhd_state"]:
            raise ValueError(f"Rapprochement divergent {symbol}/{day}")
        if state == "CORROBORATED_OHLC":
            approved[(symbol, day)] = {"isin": request["isin"], "mics": request["mics"], "html_sha256": html_hash,
                                       "observed_at": report["generated_at"], "adjusted": "Y"}
    return approved


def overlay_row(original: dict, proof: dict) -> dict:
    row = copy.deepcopy(original)
    if row["isin"] != proof["isin"] or row["mic"] not in proof["mics"]:
        raise ValueError("Identité du manifeste incompatible avec la preuve")
    if REASON not in row["research_rejection_reasons"]:
        raise ValueError("La preuve ne correspond pas au blocage attendu")
    row["research_rejection_reasons"] = [r for r in row["research_rejection_reasons"] if r != REASON]
    row["strict_rejection_reasons"] = [r for r in row["strict_rejection_reasons"] if r != REASON]
    row["price_corroborated"] = True
    row["price_proof_sources"] = sorted(set(row["price_proof_sources"] + ["EURONEXT_TARGETED_OHLC_RESEARCH_ADJUSTED_Y"]))
    row["research_j1_eligible"] = not row["research_rejection_reasons"]
    row["decision"] = "RESEARCH_J1_ELIGIBLE" if row["research_j1_eligible"] else "REJECTED"
    row["research_evidence_overlay"] = proof
    # A retrospective observation is NOT a historical PIT/corporate-action proof.
    for field in ("historical_pit_verified", "corporate_action_verified", "economic_return_ready", "canonical_strict_eligible"):
        if row[field] is not False:
            raise ValueError(f"Promotion canonique inattendue : {field}")
    return row


def build_overlay(output: Path, ledger: Path, collection: Path) -> dict:
    approved = verified_pairs(ledger, collection)
    source_report = ROOT / "artifacts/fr/sprint5_limited_2018_2026/report.json"
    report = json.loads(source_report.read_text(encoding="utf-8"))
    source_manifest = ROOT / report["manifest"]["path"]
    if sha(source_manifest) != report["manifest"]["sha256"]:
        raise ValueError("Manifeste gelé divergent")
    output.mkdir(parents=True, exist_ok=False)
    manifest = output / "bar_manifest.jsonl.gz"
    counts, research, strict, proofs = Counter(), Counter(), Counter(), Counter()
    years, days, symbols = defaultdict(Counter), defaultdict(set), set()
    seen = set()
    with gzip.open(source_manifest, "rt", encoding="utf-8") as source, gzip.open(manifest, "wt", encoding="utf-8") as sink:
        for line in source:
            row = json.loads(line)
            pair = (row["symbol"], row["session_date"])
            if pair in approved:
                if pair in seen:
                    raise ValueError("Preuve dupliquée dans le manifeste")
                row = overlay_row(row, approved[pair])
                seen.add(pair)
            sink.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            counts["TOTAL_ROWS"] += 1
            counts[row["decision"]] += 1
            years[row["session_date"][:4]][row["decision"]] += 1
            research.update(row["research_rejection_reasons"])
            strict.update(row["strict_rejection_reasons"])
            proofs.update(row["price_proof_sources"] or ["NONE"])
            if row["research_j1_eligible"]:
                symbols.add(row["symbol"])
                days[row["session_date"]].add(row["symbol"])
    if seen != set(approved) or symbols != set(report["research_j1_symbols"]):
        raise ValueError("Couverture des preuves ou univers changé de façon inattendue")
    cross = sorted(map(len, days.values()))
    report.update(generated_at=datetime.now(UTC).isoformat(), counts=dict(counts),
                  research_rejection_reasons=dict(research), strict_rejection_reasons=dict(strict),
                  price_proof_counts=dict(proofs), by_year={y: dict(c) for y, c in years.items()},
                  research_sessions_observed=len(days), research_cross_section={"minimum": min(cross), "median": cross[round((len(cross)-1)*.5)],
                                                                           "p95": cross[round((len(cross)-1)*.95)], "maximum": max(cross)},
                  research_sessions_meeting_minimum_cross_section=sum(n >= report["minimum_symbols_per_session"] for n in cross),
                  manifest={"path": str(manifest.resolve()), "sha256": sha(manifest)})
    report["research_evidence_overlay"] = {"version": "fr_fold7_targeted_ohlc_research_v1", "corroborated_pairs": len(seen),
        "source_report_sha256": sha(source_report), "source_manifest_sha256": sha(source_manifest),
        "ledger_sha256": sha(ledger), "collection_report_sha256": sha(collection / "report.json"),
        "review_sha256": sha(collection / "evidence_review.json"), "implementation_sha256": sha(Path(__file__)),
        "historical_pit_proof": False, "prices_changed": 0, "canonical_writes": False}
    report["limitations"].append("98 targeted OHLC proofs observed retrospectively; adjusted=Y; research J+1 hypothesis only")
    write_json(output / "report.json", report)
    return report


def run(output: Path) -> None:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    ledger = ROOT / "artifacts/fr/research/fold7_repair/price_evidence_requests.json"
    collection = ROOT / "artifacts/fr/research/fold7_repair/euronext_targeted_20261003"

    def config(name: str, changes: dict) -> Path:
        value = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
        value.update(changes)
        path = output / Path(name).name
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        return path

    def stage(name: str) -> None:
        LOGGER.info("Sprint 10-C3 étape %s", name)
        (output / "progress.json").write_text(json.dumps({"stage": name, "updated_at": datetime.now(UTC).isoformat()}), encoding="utf-8")

    stage("manifest")
    build_overlay(output / "source", ledger, collection)
    from service.fr.universe_liquidity_6b import FRLiquidityPolicy, build_liquidity_artifact
    stage("liquidity_6b")
    original = yaml.safe_load((ROOT / "config/universe_fr_s6b.yaml").read_text(encoding="utf-8"))
    contract = original["source_contract"] | {"report_path": str(output / "source/report.json"), "manifest_path": str(output / "source/bar_manifest.jsonl.gz")}
    cfg = config("config/universe_fr_s6b.yaml", {"source_contract": contract})
    build_liquidity_artifact(FRLiquidityPolicy.from_yaml(cfg), output_root=output / "liquidity")
    from service.fr.universe_reference_6c import build_artifact, load_policy
    stage("reference_6c")
    cfg = config("config/universe_fr_s6c.yaml", {"source_report": str(output / "source/report.json"), "liquidity_report": str(output / "liquidity/report.json")})
    build_artifact(load_policy(cfg), output / "reference")
    from modelFactory.fr_feature_panel import build_panel
    stage("features_7a")
    cfg = config("config/features_fr/fr_price_v1.yaml", {"source_liquidity_report": str(output / "liquidity/report.json"), "source_reference_report": str(output / "reference/report.json")})
    panel = build_panel(start=date(2018, 1, 1), end=date(2026, 10, 2), profile_path=cfg, output_root=output / "features")
    from modelFactory.fr_feature_profile_freeze import run as freeze
    stage("features_short")
    cfg = config("config/features_fr/fr_price_short_v1.yaml", {"source_panel": panel["panel_path"], "source_sha256": panel["panel_sha256"]})
    short = freeze(cfg, output / "short")
    from modelFactory.fr_labels import run as labels_run
    stage("labels_8")
    base = str(Path(short["artifact_directory"]) / "panel.parquet")
    cfg = config("config/labels_fr/fr_labels_v1.yaml", {"base_panel": base, "base_sha256": short["panel_sha256"], "liquidity_report": str(output / "liquidity/report.json"), "reference_report": str(output / "reference/report.json")})
    labels = labels_run(cfg, output / "labels")
    from modelFactory.fr_oracle_oof_qualification import run as qualify
    stage("oof_qualification")
    cfg = config("config/research_fr/oracle_oof_qualification_v1.yaml", {"labels_report": str(Path(labels["artifact_directory"]) / "report.json"), "labels_sha256": labels["labels_sha256"], "price_panel": base, "price_sha256": short["panel_sha256"]})
    result = qualify(cfg, output / "qualification")
    write_json(output / "rebuild_report.json", {"qualification": result, "prices_changed": 0, "models_trained": 0, "canonical_writes": False})
    stage("COMPLETED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.output)
