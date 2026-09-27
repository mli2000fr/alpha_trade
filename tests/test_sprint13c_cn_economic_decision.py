"""The decision audit must not promote partial or mixed-evidence replays."""

import pytest

from modelFactory.cn_economic_decision_13c import (
    COSTS,
    MOMENTUM,
    ORACLE,
    SCENARIOS,
    SEMESTERS,
    VETO,
    _cohorts,
    _key,
    analyze,
)


def _report(policies):
    runs = {}
    for s, seed, scenario, cost in _cohorts():
        for policy in policies:
            value = {ORACLE: 0.01, VETO[0]: 0.02, VETO[1]: 0.03, MOMENTUM: 0.005}[policy]
            runs[_key(s, policy, seed, scenario, cost)] = {
                "semester": s,
                "policy": policy,
                "seed": seed,
                "scenario": scenario,
                "cost_profile": cost,
                "source_predictions_sha256": s + "-source",
                "evidence_sha256": "evidence",
                "economic_result_valid": True,
                "marked_return_proxy": value,
                "max_drawdown_marked": -0.1,
                "average_gross_exposure": 0.5,
                "turnover_notional_over_initial_capital": 2.0,
                "sharpe_valid_mark_days_only": 0.3,
                "sortino_valid_mark_days_only": 0.4,
                "win_rate_ex_dividend": 0.5,
                "payoff_ex_dividend": 1.0,
                "profit_factor_ex_dividend": 1.0,
                "buy_fills": 10,
                "sell_fills": 10,
                "commission_total_cny": "50.0",
                "other_costs_total_cny": "0.0",
            }
    return {
        "subset": {
            "semesters": list(SEMESTERS),
            "policies": list(policies),
            "seeds": list(range(5)),
            "scenarios": list(SCENARIOS),
            "cost_profiles": list(COSTS),
        },
        "status": "COMPLETE_RESEARCH_ALL_VALID",
        "serving_enabled": False,
        "live_enabled": False,
        "economic_go_allowed": False,
        "previously_inspected_oos_not_independent_holdout": True,
        "protocol_sha256": "protocol",
        "evidence_sha256": "evidence",
        "csi300": {s: {"raw_price_return": 0.0} for s in SEMESTERS},
        "runs": runs,
    }


def test_complete_case_deltas_and_censoring_remain_descriptive():
    base = _report((ORACLE, *VETO))
    momentum = _report((MOMENTUM,))
    blocked = ("2023H2", 2, "base", COSTS[0])
    for policy in (ORACLE, *VETO):
        base["runs"][_key(blocked[0], policy, blocked[1], blocked[2], blocked[3])]["economic_result_valid"] = False
    result = analyze(base, momentum)
    section = result["scenarios"][f"base__{COSTS[0]}"]
    assert result["status"] == "COMPLETE_DESCRIPTIVE"
    assert section["complete_case_cohorts"] == 39
    assert section["semester_returns_complete_cases"]["2023H2"]["n"] == 4
    assert section["semester_returns_complete_cases"]["2023H2"]["policy_mean_returns"][MOMENTUM] == pytest.approx(0.005)
    assert section["excluded_cohorts"] == [{"semester": "2023H2", "seed": 2}]
    assert section["oracle_paired_comparisons"][VETO[0]]["mean_delta_return"] == pytest.approx(0.01)
    assert section["oracle_paired_comparisons"][VETO[0]]["positive_pairs"] == 39
    assert section["oracle_paired_comparisons"][VETO[0]]["missing_mean_delta_to_zero_observed_sum"] == pytest.approx(
        -0.39
    )
    assert result["economic_go_allowed"] is False
    assert result["no_imputation_of_invalid_returns"] is True


def test_partial_momentum_and_different_evidence_fail_closed():
    base = _report((ORACLE, *VETO))
    momentum = _report((MOMENTUM,))
    key = next(iter(momentum["runs"]))
    del momentum["runs"][key]
    with pytest.raises(ValueError, match="Cellules"):
        analyze(base, momentum)
    momentum = _report((MOMENTUM,))
    momentum["evidence_sha256"] = "old-evidence"
    with pytest.raises(ValueError, match="Protocole ou preuve"):
        analyze(base, momentum)


def test_invalid_result_is_never_used_as_a_return():
    base = _report((ORACLE, *VETO))
    key = _key("2022H1", ORACLE, 0, "base", COSTS[0])
    base["runs"][key]["economic_result_valid"] = False
    base["runs"][key]["marked_return_proxy"] = 999999.0
    result = analyze(base)
    section = result["scenarios"][f"base__{COSTS[0]}"]
    assert section["complete_case_cohorts"] == 39
    assert section["policy_metrics_complete_cases"][ORACLE]["marked_return_proxy_mean"] == pytest.approx(0.01)
    assert result["status"] == "AWAITING_HOMOGENEOUS_MOMENTUM"


def test_mutated_signal_source_and_live_flag_fail_closed():
    base = _report((ORACLE, *VETO))
    key = _key("2022H1", VETO[0], 0, "base", COSTS[0])
    base["runs"][key]["source_predictions_sha256"] = "different"
    with pytest.raises(ValueError, match="Sources OOS"):
        analyze(base)
    base = _report((ORACLE, *VETO))
    base["live_enabled"] = True
    with pytest.raises(ValueError, match="Contrat de recherche"):
        analyze(base)
