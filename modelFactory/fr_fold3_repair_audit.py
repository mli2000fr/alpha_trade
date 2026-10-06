"""Trace les lacunes FR fold 3 jusqu'aux preuves ; ne force aucune admission."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from modelFactory.fr_feature_profile_freeze import FEATURES
from modelFactory.fr_labels_review import phase_mask
from service.fr.esma_firds_download import INDEX_URL, _get_json, _tls_context
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256
from service.fr.universe_liquidity_6b import _iter_manifest


def window_blockers(proofs: dict, symbol: str, days: list[str]) -> list[dict]:
    result = []
    for day in days:
        proof = proofs.get((symbol, day))
        if proof is None:
            result.append({"date": day, "reasons": ["MANIFEST_ROW_MISSING"]})
        elif not proof["research_j1_eligible"]:
            result.append({"date": day, "reasons": proof["research_rejection_reasons"]})
    return result


def probe_official(days: list[str]) -> list[dict]:
    context = _tls_context()
    result = []
    for day in days:
        compact = day.replace("-", "")
        params = urllib.parse.urlencode({"q": f"file_name:DLTINS_{compact}*", "wt": "json", "rows": 100})
        index_url = f"{INDEX_URL}?{params}"
        try:
            response = _get_json(index_url, context)["response"]
            index = {"url": index_url, "num_found": response["numFound"], "documents": response["docs"]}
        except Exception as exc:
            index = {"url": index_url, "error": f"{type(exc).__name__}: {exc}"}
        attempts = []
        # Noms usuels uniquement : ces tests ne démontrent pas l'absence de toute archive.
        for count in [1, 2, 3, 4, 21] if day == "2021-01-04" else [1, 2, 3, 4]:
            url = f"https://firds.esma.europa.eu/firds/DLTINS_{compact}_01of{count:02d}.zip"
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, method="HEAD"), context=context, timeout=10
                ) as r:
                    attempts.append({"url": url, "status": r.status})
            except urllib.error.HTTPError as exc:
                attempts.append({"url": url, "status": exc.code})
            except Exception as exc:
                attempts.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        result.append({"day": day, "checked_at": datetime.now(UTC).isoformat(), "index": index, "head": attempts})
    return result


def audit_bounds(folds: list[dict], fold_id: int, phase: str) -> dict:
    if phase not in ("train", "validation", "test"):
        raise ValueError("Phase d'audit inconnue")
    selected = [f for f in folds if f["fold"] == fold_id]
    if len(selected) != 1:
        raise ValueError("Fold absent ou dupliqué")
    return selected[0]


def run(output_root: Path, probe: bool = False, fold_id: int = 3, phase: str = "train") -> dict:
    output_root = output_root.resolve()
    cfg = yaml.safe_load((ROOT / "config/research_fr/oracle_oof_qualification_v1.yaml").read_text(encoding="utf-8"))
    labels_report = ROOT / cfg["labels_report"]
    labels_path = labels_report.with_name("labels.parquet")
    price_path = ROOT / cfg["price_panel"]
    liquidity_path = ROOT / "artifacts/fr/sprint6b_liquidity/report.json"
    liquidity = json.loads(liquidity_path.read_text(encoding="utf-8"))
    manifest_path = Path(liquidity["source_manifest_path"])
    if _sha256(labels_path) != cfg["labels_sha256"] or _sha256(price_path) != cfg["price_sha256"]:
        raise ValueError("Sources gelées divergentes")
    if _sha256(manifest_path) != liquidity["source_manifest_sha256"]:
        raise ValueError("Manifeste source divergent")
    label_report = json.loads(labels_report.read_text(encoding="utf-8"))
    fold = audit_bounds(label_report["fold_plan"], fold_id, phase)
    price = pd.read_parquet(price_path)
    labels = pd.read_parquet(labels_path)
    labels = labels.loc[
        labels.horizon.eq(5) & labels.decision_session_date.between(fold[f"{phase}_start"], fold[f"{phase}_end"])
    ]
    keys = ["decision_session_date", "research_uid", "provider_symbol"]
    joined = labels.merge(price, on=keys, validate="one_to_one", suffixes=("", "_price"))
    if len(joined) != len(labels):
        raise ValueError("Label sans feature")
    mask = phase_mask(joined, fold, phase, cfg["development_end"])
    counts = (
        joined.loc[mask & joined.profile_row_ready & joined.oracle_extreme.notna()]
        .groupby("decision_session_date")
        .size()
    )
    sessions = [
        s.session_date.isoformat()
        for s in get_market_calendar("FR_EQ").sessions(
            date(2018, 1, 1), date.fromisoformat(fold[f"{phase}_end"]) + timedelta(days=30))
        if s.is_open
    ]
    index = {d: i for i, d in enumerate(sessions)}
    expected = [d for d in sessions if fold[f"{phase}_start"] <= d <= fold[f"{phase}_end"]]
    gaps = [d for d in expected if counts.get(d, 0) < cfg["min_cross_section"]]
    work = joined.loc[joined.decision_session_date.isin(gaps)]
    required = set()
    for row in work.itertuples():
        source_i, decision_i = index[row.source_session_date], index[row.decision_session_date]
        if decision_i != source_i + 1:
            raise ValueError("Disponibilité feature autre que J+1")
        required.update((row.provider_symbol, d) for d in sessions[max(0, source_i - 20) : decision_i + 6])
    proofs = {}
    for row in _iter_manifest(manifest_path):
        key = row["symbol"], row["session_date"]
        if key in required:
            if key in proofs:
                raise ValueError("Preuve source dupliquée")
            proofs[key] = row
    rows, reasons, esma_days = [], Counter(), set()
    complete = np.isfinite(work[list(FEATURES)].to_numpy(dtype=float)).all(axis=1)
    if not np.array_equal(complete, work.profile_complete.to_numpy()):
        raise ValueError("Masque prix divergent des 14 features")
    for row in work.itertuples():
        source_i, decision_i = index[row.source_session_date], index[row.decision_session_date]
        feature = window_blockers(proofs, row.provider_symbol, sessions[max(0, source_i - 20) : source_i + 1])
        path = window_blockers(proofs, row.provider_symbol, sessions[decision_i : decision_i + 6])
        row_reasons = {r for b in feature + path for r in b["reasons"]}
        reasons.update(row_reasons)
        for b in feature + path:
            if "MISSING_DELTA_PUBLICATION_DAY" in b["reasons"]:
                esma_days.add(b["date"])
        missing = [name for name in FEATURES if not np.isfinite(getattr(row, name))]
        rows.append(
            {
                "decision_session_date": row.decision_session_date,
                "research_uid": row.research_uid,
                "provider_symbol": row.provider_symbol,
                "missing_features": missing,
                "profile_row_ready": row.profile_row_ready,
                "path_state": row.path_state,
                "oracle_known": pd.notna(row.oracle_extreme),
                "feature_window_blockers": feature,
                "label_path_blockers": path,
            }
        )
    sources = {
        "labels": cfg["labels_sha256"],
        "price": cfg["price_sha256"],
        "manifest": liquidity["source_manifest_sha256"],
        "liquidity_report": _sha256(liquidity_path),
        "labels_report": _sha256(labels_report),
        "code": _sha256(Path(__file__)),
    }
    network = probe_official(sorted(esma_days)) if probe else []
    fingerprint = _fingerprint({"sources": sources, "fold": fold, "phase": phase, "network": network})
    destination = output_root / f"fr-fold{fold_id}-{phase}-repair-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(rows).to_parquet(destination / "row_diagnostics.parquet", index=False)
    report = {
        "sources": sources,
        "fold": fold,
        "phase": phase,
        "expected_sessions": len(expected),
        "usable_sessions": len(expected) - len(gaps),
        "missing_sessions": gaps,
        "audited_candidate_rows": len(rows),
        "blocker_candidate_row_counts": dict(reasons),
        "esma_missing_days_affecting_windows": sorted(esma_days),
        "official_probes": network,
        "price_mask_recalculation_matches": True,
        "repaired_rows": 0,
        "models_trained": 0,
        "verdict": "BLOCKED_NO_VERIFIED_SOURCE_REPAIR",
        "canonical_writes": False,
        "artifact_dir": str(destination.relative_to(ROOT)),
        "scope": f"Fold{fold_id} {phase} only; no targets/performance from 2026 inspected",
    }
    _atomic_json(destination / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/research/fold3_repair")
    parser.add_argument("--probe-official", action="store_true")
    parser.add_argument("--fold", type=int, default=3)
    parser.add_argument("--phase", choices=("train", "validation", "test"), default="train")
    args = parser.parse_args()
    print(json.dumps(run(args.output_root, args.probe_official, args.fold, args.phase), ensure_ascii=False))


if __name__ == "__main__":
    main()
