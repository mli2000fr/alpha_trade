"""Read-only, allowlisted registry of CN_A ML research campaigns.

Never query the US training tables or infer a serving-ready model from a
research verdict. A report is usable only with its matching local protocol.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGNS = {
    "sprint10b_oracle": {
        "label": "Sprint 10-B · Oracle amplitude",
        "kind": "oracle",
        "report": "artifacts/cn/oracle/sprint10b/sprint10b_oracle_summary.json",
        "protocol": "config/research_cn/sprint10b_oracle.yaml",
        "status": "COMPLETE_RESEARCH_ONLY",
    },
    "sprint10c_ranking": {
        "label": "Sprint 10-C · Ranking D1–D10",
        "kind": "ranking",
        "report": "artifacts/cn/ranking/sprint10c/sprint10c_global_ranking_summary.json",
        "protocol": "config/research_cn/sprint10c_global_ranking.yaml",
        "status": "COMPLETE_RESEARCH_ONLY",
    },
    "sprint11a_directional": {
        "label": "Sprint 11-A · Diagnostic directionnel",
        "kind": "directional",
        "report": "artifacts/cn/directional/sprint11a/sprint11a-a43c1071751aa8a6/report.json",
        "protocol": "config/research_cn/sprint11a_directional_diagnostic.yaml",
        "status": "EXPLORATORY_RESEARCH_ONLY",
    },
    "sprint11b_cost_stress": {
        "label": "Sprint 11-B · Stress de coûts indicatif",
        "kind": "cost_stress",
        "report": "artifacts/cn/directional/sprint11b/sprint11b-a4e1a03943871cb2/report.json",
        "protocol": "config/research_cn/sprint11b_veto_economic.yaml",
        "status": "INDICATIVE_COST_STRESS_ONLY",
    },
}


def load_campaign(campaign_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    """Validate both research files, then expose only display-safe metrics."""
    if campaign_id not in CAMPAIGNS:
        raise ValueError("Campagne CN inconnue")
    spec = CAMPAIGNS[campaign_id]
    report_path = root / spec["report"]
    protocol_path = root / spec["protocol"]
    protocol_bytes = protocol_path.read_bytes()
    protocol = yaml.safe_load(protocol_bytes)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(protocol, dict) or not isinstance(report, dict):
        raise ValueError("Rapport ou protocole CN invalide")
    if (
        protocol.get("market_code") != "CN_A"
        or report.get("market_code") != "CN_A"
        or report.get("status") != spec["status"]
        or report.get("protocol_sha256") != hashlib.sha256(protocol_bytes).hexdigest()
        or report.get("serving_enabled") is not False
        or report.get("backtest_executed") is not False
    ):
        raise ValueError("Contrat CN invalide : marché, statut, protocole ou serving")
    if spec["kind"] in ("oracle", "ranking") and report.get("missing") != []:
        raise ValueError("Folds CN manquants dans la campagne")

    results = report.get("results")
    if not isinstance(results, dict) or not results:
        raise ValueError("Résultats CN absents")
    horizons = tuple(int(value) for value in protocol.get("horizons", protocol.get("source_horizons", ())))
    if not horizons or set(results) != {str(horizon) for horizon in horizons}:
        raise ValueError("Horizons CN incohérents avec le protocole")
    semesters = tuple(protocol.get("test_semesters") or ())
    if not semesters:
        raise ValueError("Périodes OOS CN absentes du protocole")
    return {
        "id": campaign_id,
        "label": spec["label"],
        "kind": spec["kind"],
        "status": report["status"],
        "market_code": "CN_A",
        "serving_enabled": False,
        "period": f"{semesters[0]} → {semesters[-1]}",
        "semesters": semesters,
        "horizons": horizons,
        "feature_profile": protocol.get("feature_profile", protocol.get("source_feature_profile", "CN price-only")),
        "protocol_sha256": report["protocol_sha256"],
        "code_sha256": report.get("code_sha256"),
        "label_audit_sha256": report.get("label_audit_sha256"),
        "report_path": report_path,
        "protocol_path": protocol_path,
        "results": results,
        "fold_records": len(report.get("folds") or ()),
        "folds": report.get("folds") or (),
    }


def list_campaigns(*, root: Path = ROOT) -> list[dict[str, str]]:
    """Keep invalid/missing campaigns visible as unavailable, never substitute US."""
    rows = []
    for campaign_id, spec in CAMPAIGNS.items():
        try:
            campaign = load_campaign(campaign_id, root=root)
            state = campaign["status"]
            reason = ""
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, yaml.YAMLError) as exc:
            state = "INDISPONIBLE"
            reason = str(exc)
        rows.append({"id": campaign_id, "campagne": spec["label"], "état": state, "raison": reason})
    return rows


def model_metrics(campaign: dict[str, Any], horizon: int, model: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One model/horizon OOS summary plus its semester-level stability."""
    if campaign["kind"] not in ("oracle", "ranking") or horizon not in campaign["horizons"]:
        raise ValueError("Modèle ou horizon CN invalide")
    result = campaign["results"][str(horizon)][model]
    if campaign["kind"] == "oracle":
        metric = result["model"]
        summary = {
            "AUC": metric["auc"],
            "Précision TOP20 (%)": 100 * metric["precision_top20"],
            "Lift TOP20": metric["lift_top20"],
            "Sessions OOS": metric["sessions"],
            "Folds": result["folds"],
            "Semestres positifs": result["positive_semesters"],
            "Couverture labels minimale (%)": 100 * result["minimum_matured_label_coverage"],
        }
    else:
        metric = result["oracle_top20"]["model"]
        summary = {
            "IC dans Oracle TOP20": metric["ic_spearman_mean"],
            "Précision symétrique D1/D10 (%)": 100 * metric["symmetric_tail_precision"],
            "D1 parmi TOP (%)": 100 * metric["wrong_d1_in_top"],
            "D10 parmi BOTTOM (%)": 100 * metric["wrong_d10_in_bottom"],
            "Sessions OOS": metric["sessions"],
            "Folds": result["folds"],
            "Semestres positifs": result["positive_semesters"],
            "Couverture labels minimale (%)": 100 * result["minimum_matured_label_coverage"],
        }
    if (
        not result["fold_sessions_valid"]
        or result["folds"] != len(campaign["semesters"])
        or set(result["per_semester"]) != set(campaign["semesters"])
    ):
        raise ValueError("Stabilité des folds CN non vérifiable")
    fold_rows = [
        {"Semestre OOS": semester, "Uplift vs baseline (%)": 100 * result["per_semester"][semester]}
        for semester in campaign["semesters"]
    ]
    return summary, fold_rows


def directional_metrics(campaign: dict[str, Any], horizon: int) -> list[dict[str, Any]]:
    """Named research policies only; avoid equating fillable proxies with fills."""
    if campaign["kind"] not in ("directional", "cost_stress") or horizon not in campaign["horizons"]:
        raise ValueError("Horizon directionnel CN invalide")
    overall = campaign["results"][str(horizon)]["overall"]
    rows = []
    for policy in ("oracle_all", "reversal_veto_bottom20", "lightgbm_veto_bottom20"):
        metric = overall[policy]
        if campaign["kind"] == "directional":
            rows.append(
                {
                    "Politique": policy,
                    "Évalués": metric["evaluated"],
                    "D1 (%)": 100 * metric["d1_rate"],
                    "D10 (%)": 100 * metric["d10_rate"],
                    "Rendement futur moyen (%)": 100 * metric["mean_future_return"],
                }
            )
        else:
            rows.append(
                {
                    "Politique": policy,
                    "Fillable proxy": metric["fillable_proxy"],
                    "Couverture proxy (%)": 100 * metric["fillable_fraction_selected"],
                    "Rendement net proxy (%)": 100 * metric["mean_net_return_base_proxy"],
                }
            )
    return rows


def directional_fold_metrics(campaign: dict[str, Any], horizon: int, policy: str) -> list[dict[str, Any]]:
    """Per-semester directional evidence; proxy returns are not actual fills."""
    if policy not in ("oracle_all", "reversal_veto_bottom20", "lightgbm_veto_bottom20"):
        raise ValueError("Politique CN inconnue")
    if campaign["kind"] not in ("directional", "cost_stress") or horizon not in campaign["horizons"]:
        raise ValueError("Horizon directionnel CN invalide")
    selected_folds = [item for item in campaign["folds"] if item["horizon"] == horizon]
    folds = {str(item["semester"]): item for item in selected_folds}
    if len(selected_folds) != len(folds) or set(folds) != set(campaign["semesters"]):
        raise ValueError("Folds directionnels CN incomplets")
    rows = []
    for semester in campaign["semesters"]:
        item = folds[semester]
        if campaign["kind"] == "directional":
            metric = item["overall"][policy]
            count = metric["evaluated"]
            rows.append(
                {
                    "Semestre OOS": semester,
                    "Évalués": count,
                    "D1 (%)": 100 * metric["d1"] / count if count else None,
                    "D10 (%)": 100 * metric["d10"] / count if count else None,
                    "Rendement futur moyen (%)": 100 * metric["return_sum"] / count if count else None,
                }
            )
        else:
            metric = item["policies"][policy]
            rows.append(
                {
                    "Semestre OOS": semester,
                    "Fillable proxy": metric["fillable_proxy"],
                    "Rendement net proxy (%)": 100 * metric["mean_net_return_base_proxy"],
                }
            )
    return rows
