"""Sprint 13-C: read-only, paired economic audit of fixed CN_A replays.

The inspected 2022-2025 OOS windows are not an independent holdout.
This module never authorizes serving or live trading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

from modelFactory.cn_feature_panel import ROOT

BASE = ROOT / "artifacts/cn/economic/sprint13b5/full" / "sprint13b-fcc5a4b464c50832/report.json"
MOMENTUM_ROOT = ROOT / "artifacts/cn/economic/sprint13c/momentum"
OUTPUT = ROOT / "artifacts/cn/economic/sprint13c/decision"
ORACLE = "oracle_all"
VETO = ("reversal_veto_bottom20", "lightgbm_veto_bottom20")
MOMENTUM = "momentum_top20_same_universe"
SEMESTERS = tuple(f"{year}H{half}" for year in range(2022, 2026) for half in (1, 2))
SCENARIOS = ("base", "conservative")
COSTS = ("cn_a_research", "cn_a_research_stress")
METRICS = (
    "marked_return_proxy",
    "max_drawdown_marked",
    "average_gross_exposure",
    "turnover_notional_over_initial_capital",
    "sharpe_valid_mark_days_only",
    "sortino_valid_mark_days_only",
    "win_rate_ex_dividend",
    "payoff_ex_dividend",
    "profit_factor_ex_dividend",
    "buy_fills",
    "sell_fills",
    "commission_total_cny",
    "other_costs_total_cny",
)


def _key(semester: str, policy: str, seed: int, scenario: str, cost: str) -> str:
    return f"{semester}__{policy}__seed{seed}__{scenario}__{cost}"


def _cohorts() -> list[tuple[str, int, str, str]]:
    return [
        (s, seed, scenario, cost) for s in SEMESTERS for seed in range(5) for scenario in SCENARIOS for cost in COSTS
    ]


def _metric(row: dict[str, Any], name: str) -> float | None:
    value = row.get(name)
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Métrique non finie : {name}")
    return number


def _verify(report: dict[str, Any], policies: tuple[str, ...], reference: dict[str, Any] | None = None) -> None:
    subset = report["subset"]
    if (
        tuple(subset["semesters"]) != SEMESTERS
        or subset["seeds"] != list(range(5))
        or tuple(subset["scenarios"]) != SCENARIOS
        or tuple(subset["cost_profiles"]) != COSTS
        or tuple(subset["policies"]) != policies
    ):
        raise ValueError("Grille Sprint 13-C incomplète ou différente")
    if (
        report.get("status") not in {"COMPLETE_RESEARCH_ALL_VALID", "COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL"}
        or report.get("serving_enabled") is not False
        or report.get("live_enabled") is not False
        or report.get("economic_go_allowed") is not False
        or report.get("previously_inspected_oos_not_independent_holdout") is not True
    ):
        raise ValueError("Contrat de recherche CN incompatible")
    if reference and any(report.get(field) != reference.get(field) for field in ("protocol_sha256", "evidence_sha256")):
        raise ValueError("Protocole ou preuve B5 non homogène")
    runs = report["runs"]
    expected = {_key(s, p, seed, scenario, cost) for s, seed, scenario, cost in _cohorts() for p in policies}
    if set(runs) != expected:
        raise ValueError("Cellules du replay manquantes ou supplémentaires")
    for s, seed, scenario, cost in _cohorts():
        hashes = {runs[_key(s, p, seed, scenario, cost)]["source_predictions_sha256"] for p in policies}
        if len(hashes) != 1:
            raise ValueError(f"Sources OOS divergentes : {s}/{seed}")
        for p in policies:
            row = runs[_key(s, p, seed, scenario, cost)]
            if (row["semester"], row["policy"], row["seed"], row["scenario"], row["cost_profile"]) != (
                s,
                p,
                seed,
                scenario,
                cost,
            ):
                raise ValueError("Identité de cellule incohérente")
            if row["evidence_sha256"] != report["evidence_sha256"]:
                raise ValueError("Preuve de cellule incohérente")
            if row["economic_result_valid"]:
                for field in ("marked_return_proxy", "max_drawdown_marked", "average_gross_exposure"):
                    if _metric(row, field) is None:
                        raise ValueError(f"Métrique valide absente : {field}")
    if reference:
        for s in SEMESTERS:
            for seed in range(5):
                for scenario in SCENARIOS:
                    for cost in COSTS:
                        a = runs[_key(s, policies[0], seed, scenario, cost)]
                        b = reference["runs"][_key(s, ORACLE, seed, scenario, cost)]
                        if a["source_predictions_sha256"] != b["source_predictions_sha256"]:
                            raise ValueError("Prédictions OOS momentum/Oracle différentes")
        if report["csi300"] != reference["csi300"]:
            raise ValueError("Benchmark contextuel divergent")


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {"n": len(rows)}
    for field in METRICS:
        values = [_metric(row, field) for row in rows]
        finite = [v for v in values if v is not None]
        output[field + "_mean"] = mean(finite) if finite else None
    returns = [_metric(row, "marked_return_proxy") for row in rows]
    output["positive_return_count"] = sum(v > 0 for v in returns if v is not None)
    output["median_semester_return"] = median(returns) if returns else None
    return output


def analyze(base: dict[str, Any], momentum: dict[str, Any] | None = None) -> dict[str, Any]:
    _verify(base, (ORACLE, *VETO))
    if momentum is not None:
        _verify(momentum, (MOMENTUM,), base)
    runs = dict(base["runs"])
    if momentum is not None:
        runs.update(momentum["runs"])
    policies = (ORACLE, *VETO, *((MOMENTUM,) if momentum is not None else ()))
    cohorts = _cohorts()
    invalid = Counter()
    for s, seed, scenario, cost in cohorts:
        for p in policies:
            row = runs[_key(s, p, seed, scenario, cost)]
            if not row["economic_result_valid"]:
                invalid[f"{s}|{p}|{scenario}|{cost}"] += 1
    sections: dict[str, Any] = {}
    for scenario in SCENARIOS:
        for cost in COSTS:
            selected = [(s, seed, scenario, cost) for s in SEMESTERS for seed in range(5)]
            complete = [
                c
                for c in selected
                if all(runs[_key(c[0], p, c[1], scenario, cost)]["economic_result_valid"] for p in policies)
            ]
            rows_by_policy = {
                p: [runs[_key(s, p, seed, scenario, cost)] for s, seed, _, _ in complete] for p in policies
            }
            comparisons: dict[str, Any] = {}
            for p in policies[1:]:
                differences = {
                    s: [
                        _metric(runs[_key(s, p, seed, scenario, cost)], "marked_return_proxy")
                        - _metric(runs[_key(s, ORACLE, seed, scenario, cost)], "marked_return_proxy")
                        for seed in range(5)
                        if (s, seed, scenario, cost) in complete
                    ]
                    for s in SEMESTERS
                }
                flat = [x for values in differences.values() for x in values]
                missing = 40 - len(flat)
                comparisons[p] = {
                    "paired_n": len(flat),
                    "mean_delta_return": mean(flat) if flat else None,
                    "median_delta_return": median(flat) if flat else None,
                    "positive_pairs": sum(x > 0 for x in flat),
                    "negative_pairs": sum(x < 0 for x in flat),
                    "semester_mean_deltas": {s: mean(values) if values else None for s, values in differences.items()},
                    "positive_semesters": sum(mean(v) > 0 for v in differences.values() if v),
                    "missing_cohorts": missing,
                    "missing_mean_delta_to_zero_observed_sum": (-sum(flat) / missing if missing else None),
                }
            sections[f"{scenario}__{cost}"] = {
                "planned_cohorts": 40,
                "complete_case_cohorts": len(complete),
                "excluded_cohorts": [
                    {"semester": s, "seed": seed}
                    for s, seed, _, _ in selected
                    if (s, seed, scenario, cost) not in complete
                ],
                "policy_metrics_complete_cases": {p: _summarize(rows) for p, rows in rows_by_policy.items()},
                "semester_returns_complete_cases": {
                    s: {
                        "n": sum(cohort[0] == s for cohort in complete),
                        "policy_mean_returns": {
                            p: (
                                mean(
                                    _metric(runs[_key(s, p, seed, scenario, cost)], "marked_return_proxy")
                                    for semester, seed, _, _ in complete
                                    if semester == s
                                )
                                if any(cohort[0] == s for cohort in complete)
                                else None
                            )
                            for p in policies
                        },
                    }
                    for s in SEMESTERS
                },
                "oracle_paired_comparisons": comparisons,
            }
    return {
        "experiment": "cn_sprint13c_fixed_economic_decision_audit",
        "status": "COMPLETE_DESCRIPTIVE" if momentum else "AWAITING_HOMOGENEOUS_MOMENTUM",
        "previously_inspected_oos_not_independent_holdout": True,
        "serving_enabled": False,
        "live_enabled": False,
        "economic_go_allowed": False,
        "no_imputation_of_invalid_returns": True,
        "five_seeds_not_independent_market_periods": True,
        "csi300_contextual_not_tradable_benchmark": base["csi300"],
        "base_evidence_sha256": base["evidence_sha256"],
        "protocol_sha256": base["protocol_sha256"],
        "policies": policies,
        "valid_runs_by_policy": {
            p: sum(
                runs[_key(s, p, seed, scenario, cost)]["economic_result_valid"] for s, seed, scenario, cost in cohorts
            )
            for p in policies
        },
        "invalid_cells": dict(sorted(invalid.items())),
        "scenarios": sections,
        "decision": "NO_PRODUCTION_GO_INSPECTED_OOS",
    }


def run(*, base_path: Path = BASE, momentum_path: Path | None = None, output_root: Path = OUTPUT) -> dict[str, Any]:
    base_bytes = base_path.read_bytes()
    momentum_bytes = momentum_path.read_bytes() if momentum_path else None
    report = analyze(json.loads(base_bytes), json.loads(momentum_bytes) if momentum_bytes else None)
    report["source_reports"] = {
        "base": {"path": str(base_path), "sha256": hashlib.sha256(base_bytes).hexdigest()},
        "momentum": (
            {"path": str(momentum_path), "sha256": hashlib.sha256(momentum_bytes).hexdigest()}
            if momentum_bytes
            else None
        ),
    }
    digest = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()[:16]
    destination = output_root / f"decision-{digest}"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 13-C : audit économique CN en lecture seule")
    parser.add_argument("--base-report", type=Path, default=BASE)
    parser.add_argument("--momentum-report", type=Path)
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(base_path=args.base_report, momentum_path=args.momentum_report, output_root=args.output_root)
    print(
        json.dumps(
            {
                "status": report["status"],
                "report_path": report["report_path"],
                "valid_runs_by_policy": report["valid_runs_by_policy"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
