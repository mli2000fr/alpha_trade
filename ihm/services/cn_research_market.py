"""Sprint 14-A: isolated CN_A research view for the existing US operator pages.

No CN action is launched here. In particular, selecting CN_A must never
reuse an unscoped US training, prediction, backtest, or live command.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import streamlit as st

from common.market_context import MarketCode

ROOT = Path(__file__).resolve().parents[2]
DECISION_REPORT = ROOT / "artifacts/cn/economic/sprint13c/decision" / "decision-d1745c4c96351267/report.json"
CN_UNIVERSE = ROOT / "config/univers_cn/canonical_full_2018_2025.txt"
PageKind = Literal["pipeline", "diagnostic", "backtest"]
MARKET_LABELS = {
    MarketCode.US_EQ.value: "🇺🇸 États-Unis — application actuelle",
    MarketCode.CN_A.value: "🇨🇳 Chine A — recherche uniquement",
}


def _render_cn_campaign_diagnostics() -> None:
    """Sprint 14-B: CN artifact diagnostics, independent of US DB and 13-C."""
    from ihm.services.cn_research_registry import (
        directional_fold_metrics,
        directional_metrics,
        list_campaigns,
        load_campaign,
        model_metrics,
    )

    st.subheader("Campagnes ML CN_A — artefacts de recherche")
    campaigns = list_campaigns()
    st.dataframe(campaigns, use_container_width=True, hide_index=True)
    available = [row["id"] for row in campaigns if row["état"] != "INDISPONIBLE"]
    if not available:
        st.error("Aucune campagne CN valide ; aucune donnée US n'est utilisée en remplacement.")
        return
    campaign_id = st.selectbox("Campagne CN", available, key="sprint14b_cn_campaign")
    try:
        campaign = load_campaign(campaign_id)
        horizon = st.selectbox("Horizon CN", campaign["horizons"], key="sprint14b_cn_horizon")
        st.caption(
            f"{campaign['label']} · {campaign['period']} · {campaign['status']} · "
            f"profil {campaign['feature_profile']} · recherche uniquement, aucun serving."
        )
        if campaign["kind"] in ("oracle", "ranking"):
            models = tuple(campaign["results"][str(horizon)])
            model = st.selectbox("Modèle CN", models, key="sprint14b_cn_model")
            summary, folds = model_metrics(campaign, horizon, model)
            st.dataframe([summary], use_container_width=True, hide_index=True)
            st.caption("Stabilité Walk-Forward : uplift OOS par semestre contre la baseline du protocole.")
            st.dataframe(folds, use_container_width=True, hide_index=True)
        else:
            st.caption(
                f"{campaign['fold_records']} enregistrements de folds exploratoires. "
                "Ces résultats ne constituent ni un backtest exécutable ni une confirmation indépendante."
            )
            st.dataframe(directional_metrics(campaign, horizon), use_container_width=True, hide_index=True)
            policy = st.selectbox(
                "Politique CN pour les folds",
                ("oracle_all", "reversal_veto_bottom20", "lightgbm_veto_bottom20"),
                key="sprint14b_cn_policy",
            )
            st.dataframe(directional_fold_metrics(campaign, horizon, policy), use_container_width=True, hide_index=True)
        st.caption(
            f"Provenance : protocole {campaign['protocol_path']} · "
            f"SHA-256 {campaign['protocol_sha256']} · rapport {campaign['report_path']}"
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        st.error(f"Campagne CN indisponible : {exc}")


_POLICIES = (
    "oracle_all",
    "reversal_veto_bottom20",
    "lightgbm_veto_bottom20",
    "momentum_top20_same_universe",
)


def select_market(page: PageKind) -> str:
    """One widget key per page: changing a page cannot mutate another page."""
    return str(
        st.selectbox(
            "Marché",
            options=(MarketCode.US_EQ.value, MarketCode.CN_A.value),
            key=f"sprint14a_{page}_market_code",
            format_func=lambda value: MARKET_LABELS[str(value)],
            help="Le marché US conserve ses commandes. Le marché CN_A est limité aux résultats de recherche.",
        )
    )


def load_cn_research_summary(
    *, report_path: Path = DECISION_REPORT, universe_path: Path = CN_UNIVERSE
) -> dict[str, Any]:
    """Read only CN-scoped, non-serving research artifacts; fail closed."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("experiment") != "cn_sprint13c_fixed_economic_decision_audit"
        or report.get("status") != "COMPLETE_DESCRIPTIVE"
        or report.get("decision") != "NO_PRODUCTION_GO_INSPECTED_OOS"
        or report.get("serving_enabled") is not False
        or report.get("live_enabled") is not False
        or report.get("economic_go_allowed") is not False
        or report.get("previously_inspected_oos_not_independent_holdout") is not True
        or tuple(report.get("policies") or ()) != _POLICIES
    ):
        raise ValueError("Rapport CN de recherche absent, incomplet ou non conforme")
    scenarios = report["scenarios"]
    standard = scenarios["base__cn_a_research"]
    stress = scenarios["base__cn_a_research_stress"]
    if standard["complete_case_cohorts"] > 40 or stress["complete_case_cohorts"] > 40:
        raise ValueError("Couverture CN incohérente")
    universe = [symbol.strip() for symbol in universe_path.read_text(encoding="utf-8").split(",") if symbol.strip()]
    if (
        not universe
        or len(universe) != len(set(universe))
        or any(not symbol.startswith(("sh.", "sz.", "bj.")) for symbol in universe)
    ):
        raise ValueError("Univers de recherche CN invalide")
    rows = []
    for policy in _POLICIES:
        base = standard["policy_metrics_complete_cases"][policy]
        stressed = stress["policy_metrics_complete_cases"][policy]
        rows.append(
            {
                "Politique": policy,
                "Cas comparables": base["n"],
                "Rendement semestriel moyen": base["marked_return_proxy_mean"],
                "Sous coûts stress": stressed["marked_return_proxy_mean"],
                "Drawdown moyen": base["max_drawdown_marked_mean"],
                "Exposition brute moyenne": base["average_gross_exposure_mean"],
            }
        )
    return {
        "market_code": MarketCode.CN_A.value,
        "database_alias": "cn_primary",
        "currency": "CNY",
        "calendar": "CN_A",
        "universe_name": universe_path.name,
        "universe_symbols": len(universe),
        "universe_is_tradable_pit": False,
        "comparable_standard": standard["complete_case_cohorts"],
        "comparable_stress": stress["complete_case_cohorts"],
        "report_path": report_path,
        "rows": rows,
    }


def render_cn_research_view(page: PageKind) -> None:
    """Show only CN evidence; never call a US launcher or query its tables."""
    st.warning(
        "CN_A — recherche uniquement. Le Sprint 13-C n'a pas validé de politique économique ; "
        "entraînement, prédiction servable, backtest opérateur et live CN ne sont pas activés sur cette page."
    )
    if page == "diagnostic":
        _render_cn_campaign_diagnostics()
    try:
        summary = load_cn_research_summary()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        st.error(f"Résultats CN indisponibles : {exc}")
        return
    st.caption(
        f"Marché {summary['market_code']} · base {summary['database_alias']} · "
        f"devise {summary['currency']} · calendrier {summary['calendar']}."
    )
    st.caption(
        f"Univers de recherche : {summary['universe_name']} ({summary['universe_symbols']} codes historiques). "
        "Ce fichier n'est pas un univers négociable PIT."
    )
    if page == "pipeline":
        st.info(
            "Les étapes ML/Predict US restent masquées ici. Les batchs CN seront sélectionnables dans un sprint ultérieur."
        )
    elif page == "backtest":
        st.info(
            "Les replays CN historiques sont consultables ci-dessous ; le formulaire backtest US ne peut pas lancer un run CN."
        )
    else:
        st.info("Ces chiffres proviennent d'artefacts CN figés, et non des tables de métriques US.")
    st.subheader("Sprint 13-C — comparaison économique CN_A")
    st.caption(
        f"Cohortes appariées : {summary['comparable_standard']}/40 au coût standard, "
        f"{summary['comparable_stress']}/40 sous stress ; périodes OOS déjà inspectées."
    )
    st.dataframe(summary["rows"], use_container_width=True, hide_index=True)
    st.caption(f"Rapport de provenance : {summary['report_path']}")
