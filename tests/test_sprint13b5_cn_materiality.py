"""Validity projection must never be mistaken for homogeneous performance."""

import copy

import pytest

from modelFactory.cn_economic_materiality_13b5 import POLICIES, analyze


def _original():
    runs = {}
    for semester in ("2022H1", "2022H2", "2023H1", "2023H2",
                     "2024H1", "2024H2", "2025H1", "2025H2"):
        for seed in range(5):
            for scenario in ("base", "conservative"):
                for cost in ("cn_a_research", "cn_a_research_stress"):
                    for policy in POLICIES:
                        key = f"{semester}__{policy}__seed{seed}__{scenario}__{cost}"
                        runs[key] = {
                            "semester": semester, "policy": policy,
                            "seed": seed, "scenario": scenario, "cost_profile": cost,
                            "economic_result_valid": True,
                            "source_predictions_sha256": "a" * 64,
                            "unresolved_instruments": {}, "open_lots": {},
                        }
    assert len(runs) == 480
    return {"runs": runs}


def test_recovered_cell_improves_one_pair_without_performance_aggregation():
    original = _original()
    key = next(iter(original["runs"]))
    original["runs"][key]["economic_result_valid"] = False
    original["runs"][key]["unresolved_instruments"] = {"82": "FACTOR_EVENT_UNRESOLVED"}
    overlay = {"runs": {key: dict(original["runs"][key], economic_result_valid=True)}}
    report = analyze(original, [("B5", overlay)])
    assert report["original_valid"] == 479
    assert report["original_valid_paired_cohorts"] == 159
    assert report["projected_valid"] == 480
    assert report["projected_valid_paired_cohorts"] == 160
    assert report["recovered_cells_by_proof"] == {"B5": 1}
    assert report["performance_aggregated"] is False
    assert report["economic_go_allowed"] is False


def test_lineage_change_and_overlapping_overlay_fail_closed():
    original = _original()
    key = next(iter(original["runs"]))
    changed = copy.deepcopy(original["runs"][key])
    changed["source_predictions_sha256"] = "b" * 64
    with pytest.raises(RuntimeError, match="Lignage"):
        analyze(original, [("B5", {"runs": {key: changed}})])
    unchanged = {"runs": {key: original["runs"][key]}}
    with pytest.raises(RuntimeError, match="dupliquée"):
        analyze(original, [("B3", unchanged), ("B5", unchanged)])
