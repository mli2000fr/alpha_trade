"""Read-only B5 blocked-cell materiality audit; no mixed-evidence PnL.

Targeted replays can prove that a blocked cell becomes technically valid,
but they cannot be combined into a homogeneous performance campaign.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from modelFactory.cn_feature_panel import ROOT

ORIGINAL = (ROOT / "artifacts" / "cn" / "economic" / "sprint13b"
            / "sprint13b-273492bdfbcf1230" / "report.json")
OVERLAYS = (
    ("B3", ROOT / "artifacts" / "cn" / "economic" / "sprint13b"
     / "sprint13b-a2c0b052ac0fdc6b" / "report.json"),
    ("B4", ROOT / "artifacts" / "cn" / "economic" / "sprint13b"
     / "sprint13b-921389b90216f681" / "report.json"),
    ("B4", ROOT / "artifacts" / "cn" / "economic" / "sprint13b"
     / "sprint13b-456bd82b16a044f1" / "report.json"),
)
OUTPUT = ROOT / "artifacts" / "cn" / "economic" / "sprint13b5"
POLICIES = ("oracle_all", "reversal_veto_bottom20", "lightgbm_veto_bottom20")
EXPECTED_EVIDENCE = {
    "original": "afd10e157ff253b7d1268365c66b1dd6d5482d21315c2c20e308002f8a4288b7",
    "B3": "d61c145756ef237d41a5a2148b16b9dd99b1cd38fad4c6caebb8931be8d67a5a",
    "B4": "2e2911cef66c011855510f45581247d285dc644a44f9a829c04ef39d4c45bc39",
    "B5": "d8a633c6830b0dedcbcd486bf39b556d781a8db08cb95a16a828149f059ed285",
}


def analyze(original: dict[str, Any],
            overlays: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Project validity only, enforcing exact keys and OOS source lineage."""
    baseline = original["runs"]
    if len(baseline) != 480:
        raise RuntimeError("La campagne de départ doit contenir 480 cellules")
    projected = {key: bool(row["economic_result_valid"]) for key, row in baseline.items()}
    recovered = Counter()
    touched: set[str] = set()
    for phase, report in overlays:
        if phase not in {"B3", "B4", "B5"}:
            raise RuntimeError("Phase de preuve inconnue")
        if not report["runs"]:
            raise RuntimeError("Replay ciblé vide")
        for key, row in report["runs"].items():
            if key not in baseline or key in touched:
                raise RuntimeError(f"Cellule ciblée absente ou dupliquée : {key}")
            parent = baseline[key]
            if (row["source_predictions_sha256"] != parent["source_predictions_sha256"]
                    or any(row[field] != parent[field] for field in
                           ("semester", "policy", "seed", "scenario", "cost_profile"))):
                raise RuntimeError(f"Lignage de signal modifié : {key}")
            if parent["economic_result_valid"] and not row["economic_result_valid"]:
                raise RuntimeError(f"Régression de validité : {key}")
            if not parent["economic_result_valid"] and row["economic_result_valid"]:
                recovered[phase] += 1
            projected[key] = bool(row["economic_result_valid"])
            touched.add(key)
    cohorts: dict[tuple[str, int, str, str], dict[str, bool]] = defaultdict(dict)
    for key, row in baseline.items():
        cohort = row["semester"], int(row["seed"]), row["scenario"], row["cost_profile"]
        cohorts[cohort][row["policy"]] = projected[key]
    if len(cohorts) != 160 or any(set(rows) != set(POLICIES) for rows in cohorts.values()):
        raise RuntimeError("Appariement Oracle/veto initial incomplet")
    residual = Counter()
    for key, row in baseline.items():
        if projected[key]:
            continue
        if row["unresolved_instruments"]:
            kind = ",".join(f"{identifier}:{reason}" for identifier, reason
                            in sorted(row["unresolved_instruments"].items()))
        elif row["open_lots"]:
            kind = "open_position:" + ",".join(sorted(row["open_lots"]))
        else:
            kind = "other_invalid"
        residual[f"{row['semester']}|{kind}"] += 1
    result = {
        "experiment": "cn_sprint13b5_validity_materiality",
        "projection_only_not_homogeneous_replay": True,
        "performance_aggregated": False,
        "economic_go_allowed": False,
        "original_cells": len(baseline),
        "original_valid": sum(bool(row["economic_result_valid"]) for row in baseline.values()),
        "original_blocked": sum(not bool(row["economic_result_valid"]) for row in baseline.values()),
        "recovered_cells_by_proof": dict(sorted(recovered.items())),
        "projected_valid": sum(projected.values()),
        "projected_blocked": sum(not valid for valid in projected.values()),
        "original_valid_paired_cohorts": sum(
            all(baseline[key]["economic_result_valid"] for key, row in baseline.items()
                if (row["semester"], row["seed"], row["scenario"], row["cost_profile"]) == cohort)
            for cohort in cohorts
        ),
        "projected_valid_paired_cohorts": sum(
            all(rows.values()) for rows in cohorts.values()
        ),
        "total_paired_cohorts": len(cohorts),
        "residual_blockers": dict(sorted(residual.items())),
        "replay_required_for_performance": True,
    }
    if result["projected_valid"] + result["projected_blocked"] != 480:
        raise RuntimeError("Comptage B5 incohérent")
    return result


def run(*, original_path: Path = ORIGINAL,
        overlay_paths: list[tuple[str, Path]] | None = None,
        output_root: Path = OUTPUT) -> dict[str, Any]:
    paths = overlay_paths if overlay_paths is not None else list(OVERLAYS)
    original_bytes = original_path.read_bytes()
    overlay_bytes = [(phase, path, path.read_bytes()) for phase, path in paths]
    original = json.loads(original_bytes)
    if original.get("evidence_sha256") != EXPECTED_EVIDENCE["original"]:
        raise RuntimeError("Preuve de la campagne originale différente")
    overlays = []
    for phase, _, data in overlay_bytes:
        item = json.loads(data)
        if item.get("evidence_sha256") != EXPECTED_EVIDENCE[phase]:
            raise RuntimeError(f"Preuve ciblée {phase} différente")
        overlays.append((phase, item))
    report = analyze(
        original, overlays,
    )
    report["source_sha256"] = {
        "original": hashlib.sha256(original_bytes).hexdigest(),
        "overlays": [
            {"phase": phase, "path": str(path), "sha256": hashlib.sha256(data).hexdigest()}
            for phase, path, data in overlay_bytes
        ],
    }
    digest = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()[:16]
    target = output_root / f"materiality-{digest}"
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(target / "report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit de matérialité B5 sans mélange de PnL")
    parser.add_argument("--original", type=Path, default=ORIGINAL)
    parser.add_argument("--b5-report", action="append", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    overlays = list(OVERLAYS) + [("B5", path) for path in args.b5_report]
    report = run(original_path=args.original, overlay_paths=overlays,
                 output_root=args.output_root)
    print(json.dumps({
        "report_path": report["report_path"],
        "projected_valid": report["projected_valid"],
        "projected_blocked": report["projected_blocked"],
        "projected_valid_paired_cohorts": report["projected_valid_paired_cohorts"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
