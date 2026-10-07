"""The CN research registry is explicit, PIT-labelled and never falls back to US."""

import hashlib
import json

import pytest

from ihm.services import cn_research_registry as registry


def _campaign_files(tmp_path, monkeypatch, *, market="CN_A", serving=False):
    spec = {
        "label": "Oracle CN test",
        "kind": "oracle",
        "report": "artifacts/cn/oracle/report.json",
        "protocol": "config/research_cn/oracle.yaml",
        "status": "COMPLETE_RESEARCH_ONLY",
    }
    monkeypatch.setattr(registry, "CAMPAIGNS", {"oracle_test": spec})
    protocol_path = tmp_path / spec["protocol"]
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_text(
        f"market_code: {market}\nhorizons: [20]\ntest_semesters: [2024H1, 2024H2]\nfeature_profile: cn_price_v1\n",
        encoding="utf-8",
    )
    report = {
        "market_code": market,
        "status": "COMPLETE_RESEARCH_ONLY",
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "serving_enabled": serving,
        "backtest_executed": False,
        "missing": [],
        "results": {
            "20": {
                "lightgbm": {
                    "model": {"auc": 0.68, "precision_top20": 0.38, "lift_top20": 1.9, "sessions": 120},
                    "folds": 2,
                    "positive_semesters": 2,
                    "minimum_matured_label_coverage": 0.98,
                    "fold_sessions_valid": True,
                    "per_semester": {"2024H1": 0.04, "2024H2": 0.03},
                }
            }
        },
    }
    report_path = tmp_path / spec["report"]
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return protocol_path, report_path, report


def test_registry_reads_cn_only_and_exposes_fold_stability(tmp_path, monkeypatch):
    _campaign_files(tmp_path, monkeypatch)
    campaign = registry.load_campaign("oracle_test", root=tmp_path)
    assert campaign["market_code"] == "CN_A"
    assert campaign["period"] == "2024H1 → 2024H2"
    summary, folds = registry.model_metrics(campaign, 20, "lightgbm")
    assert summary["Folds"] == 2
    assert summary["Précision TOP20 (%)"] == 38
    assert [row["Semestre OOS"] for row in folds] == ["2024H1", "2024H2"]
    assert registry.list_campaigns(root=tmp_path)[0]["état"] == "COMPLETE_RESEARCH_ONLY"


@pytest.mark.parametrize(("market", "serving"), [("US_EQ", False), ("CN_A", True)])
def test_registry_refuses_us_or_serving_artifact(tmp_path, monkeypatch, market, serving):
    _campaign_files(tmp_path, monkeypatch, market=market, serving=serving)
    with pytest.raises(ValueError, match="Contrat CN invalide"):
        registry.load_campaign("oracle_test", root=tmp_path)
    assert registry.list_campaigns(root=tmp_path)[0]["état"] == "INDISPONIBLE"


def test_registry_refuses_protocol_drift_and_missing_folds(tmp_path, monkeypatch):
    protocol_path, report_path, report = _campaign_files(tmp_path, monkeypatch)
    protocol_path.write_text(protocol_path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Contrat CN invalide"):
        registry.load_campaign("oracle_test", root=tmp_path)
    report["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    report["missing"] = ["2024H2"]
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="Folds CN manquants"):
        registry.load_campaign("oracle_test", root=tmp_path)


def test_registry_missing_campaign_is_visible_but_not_selectable(tmp_path, monkeypatch):
    _campaign_files(tmp_path, monkeypatch)
    (tmp_path / "artifacts/cn/oracle/report.json").unlink()
    rows = registry.list_campaigns(root=tmp_path)
    assert rows[0]["état"] == "INDISPONIBLE"
    with pytest.raises(ValueError, match="Campagne CN inconnue"):
        registry.load_campaign("../../artifacts/us", root=tmp_path)


def test_registry_refuses_incomplete_semester_evidence(tmp_path, monkeypatch):
    _, report_path, report = _campaign_files(tmp_path, monkeypatch)
    report["results"]["20"]["lightgbm"]["per_semester"].pop("2024H2")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    campaign = registry.load_campaign("oracle_test", root=tmp_path)
    with pytest.raises(ValueError, match="Stabilité des folds"):
        registry.model_metrics(campaign, 20, "lightgbm")


def test_directional_fold_evidence_rejects_duplicates():
    campaign = {
        "kind": "directional",
        "horizons": (20,),
        "semesters": ("2024H1", "2024H2"),
        "folds": [
            {
                "horizon": 20,
                "semester": semester,
                "overall": {"oracle_all": {"evaluated": 100, "d1": 30, "d10": 10, "return_sum": 2.0}},
            }
            for semester in ("2024H1", "2024H2")
        ],
    }
    rows = registry.directional_fold_metrics(campaign, 20, "oracle_all")
    assert len(rows) == 2
    assert rows[0]["D1 (%)"] == 30
    campaign["folds"].append(campaign["folds"][0])
    with pytest.raises(ValueError, match="Folds directionnels CN incomplets"):
        registry.directional_fold_metrics(campaign, 20, "oracle_all")
