"""CN research selection must never enter legacy US command paths."""

import json

import pytest

from ihm.pages import backtesting, ml_diagnostics, pipeline
from ihm.services import cn_research_market


def _research_report():
    policies = list(cn_research_market._POLICIES)
    metrics = {
        policy: {
            "n": 34,
            "marked_return_proxy_mean": -0.02,
            "max_drawdown_marked_mean": -0.18,
            "average_gross_exposure_mean": 0.67,
        }
        for policy in policies
    }
    return {
        "experiment": "cn_sprint13c_fixed_economic_decision_audit",
        "status": "COMPLETE_DESCRIPTIVE",
        "decision": "NO_PRODUCTION_GO_INSPECTED_OOS",
        "serving_enabled": False,
        "live_enabled": False,
        "economic_go_allowed": False,
        "previously_inspected_oos_not_independent_holdout": True,
        "policies": policies,
        "scenarios": {
            "base__cn_a_research": {
                "complete_case_cohorts": 34,
                "policy_metrics_complete_cases": metrics,
            },
            "base__cn_a_research_stress": {
                "complete_case_cohorts": 33,
                "policy_metrics_complete_cases": metrics,
            },
        },
    }


def _artifact_paths(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_research_report()), encoding="utf-8")
    universe_path = tmp_path / "universe.txt"
    universe_path.write_text("sh.600000,sz.000001", encoding="utf-8")
    return report_path, universe_path


def test_market_widget_defaults_us_and_is_scoped_per_page(monkeypatch):
    seen = []

    def selectbox(_label, **kwargs):
        seen.append(kwargs)
        return kwargs["options"][0]

    monkeypatch.setattr(cn_research_market.st, "selectbox", selectbox)
    assert cn_research_market.select_market("pipeline") == "US_EQ"
    assert cn_research_market.select_market("diagnostic") == "US_EQ"
    assert seen[0]["key"] != seen[1]["key"]
    assert seen[0]["options"] == ("US_EQ", "CN_A")


def test_cn_summary_reads_only_scoped_artifacts(tmp_path):
    report_path, universe_path = _artifact_paths(tmp_path)
    summary = cn_research_market.load_cn_research_summary(report_path=report_path, universe_path=universe_path)
    assert summary["market_code"] == "CN_A"
    assert summary["database_alias"] == "cn_primary"
    assert summary["currency"] == "CNY"
    assert summary["universe_is_tradable_pit"] is False
    assert summary["comparable_standard"] == 34
    assert summary["comparable_stress"] == 33
    assert summary["universe_symbols"] == 2
    assert len(summary["rows"]) == 4


def test_cn_summary_rejects_serving_report_and_us_universe(tmp_path):
    report_path, universe_path = _artifact_paths(tmp_path)
    original = _research_report()
    original["serving_enabled"] = True
    report_path.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="non conforme"):
        cn_research_market.load_cn_research_summary(report_path=report_path, universe_path=universe_path)
    original["serving_enabled"] = False
    report_path.write_text(json.dumps(original), encoding="utf-8")
    universe_path.write_text("AAPL,MSFT", encoding="utf-8")
    with pytest.raises(ValueError, match="Univers"):
        cn_research_market.load_cn_research_summary(report_path=report_path, universe_path=universe_path)


@pytest.mark.parametrize(
    ("page", "kind", "us_entry"),
    [
        (pipeline, "pipeline", "_build_launch_options"),
        (backtesting, "backtest", "get_runtime_db_config"),
        (ml_diagnostics, "diagnostic", "db_available"),
    ],
)
def test_cn_render_returns_before_any_us_launch(monkeypatch, page, kind, us_entry):
    observed = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Le chemin US ne doit pas être exécuté sous CN_A")

    monkeypatch.setattr(page.st, "header", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "select_market", lambda chosen: "CN_A")
    monkeypatch.setattr(page, "render_cn_research_view", lambda chosen: observed.append(chosen))
    monkeypatch.setattr(page, us_entry, forbidden)
    page.render()
    assert observed == [kind]
