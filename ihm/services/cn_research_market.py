"""Sprint 14-A: isolated CN_A research view for the existing US operator pages.

No CN action is launched here. In particular, selecting CN_A must never
reuse an unscoped US training, prediction, backtest, or live command.
"""

from __future__ import annotations

import json
from dataclasses import replace
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
    MarketCode.FR_EQ.value: "🇫🇷 France — recherche uniquement",
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


@st.fragment(run_every="5s")
def _render_cn_replay_panel() -> None:
    """Launch one frozen CN research cell and show only its own run history."""
    from ihm.services.backtesting_registry import (
        get_backtesting_run_record,
        list_active_backtesting_runs_by_kind,
        load_backtesting_history,
        read_backtesting_logs,
        start_backtesting_run,
        stop_backtesting_run,
    )
    from ihm.services.backtesting_runner import format_command_for_display
    from ihm.services.cn_replay_launch import (
        OUTPUT_PARENT,
        CNResearchReplayOptions,
        build_cn_replay_command,
        replay_choices,
    )
    from ihm.services.cn_replay_worker import latest_progress_event

    st.subheader("Sprint 14-C — Replay CN_A de recherche")
    st.warning(
        "Un seul semestre et une seule cellule du protocole 13-B par lancement. "
        "Fills hypothétiques, OOS déjà inspecté, aucune autorisation de production ou de live."
    )
    try:
        choices = replay_choices()
        semester = st.selectbox("Semestre OOS CN", choices["semesters"], key="sprint14c_cn_semester")
        policy = st.selectbox("Politique CN", choices["policies"], key="sprint14c_cn_policy")
        seed = st.selectbox("Seed figée", choices["seeds"], key="sprint14c_cn_seed")
        scenario = st.selectbox("Scénario de fill", choices["scenarios"], key="sprint14c_cn_scenario")
        cost_profile = st.selectbox("Profil de coûts", choices["cost_profiles"], key="sprint14c_cn_cost")
        options = CNResearchReplayOptions(
            semester=semester, policy=policy, seed=seed, scenario=scenario, cost_profile=cost_profile
        )
        preview = replace(options, output_root=str(OUTPUT_PARENT / "preview" / "artifacts"))
        st.caption(
            "Marché CN_A · base alpha_trade_cn · devise CNY · univers : prédictions Ranking OOS "
            "H20 du semestre sélectionné, non modifiable. Capital/lot/T+1/sortie H20 : protocole 13-A gelé. "
            "La sortie réelle est créée sous un ID de run distinct."
        )
        st.code(format_command_for_display(build_cn_replay_command(preview)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Formulaire CN indisponible : {exc}")
        return

    active = list_active_backtesting_runs_by_kind("cn-research-replay")
    if active:
        st.info(f"Replay CN déjà en cours : {active[0]['run_id']}")
    if st.button(
        "Lancer ce replay CN de recherche",
        key="sprint14c_launch_cn_replay",
        type="primary",
        disabled=bool(active),
    ):
        try:
            with st.spinner("Vérification des prédictions OOS, des preuves et de la base CN…"):
                record = start_backtesting_run(
                    "cn-research-replay", "Replay CN_A de recherche", options, db_config=None
                )
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            st.error(f"Replay CN non lancé : {exc}")
        else:
            st.success(f"Replay CN lancé en arrière-plan : {record.run_id}")
            st.rerun()

    history = [row for row in load_backtesting_history() if row.get("run_kind") == "cn-research-replay"]
    if not history:
        st.caption("Aucun replay CN lancé depuis cette page.")
        return
    st.dataframe(
        [
            {
                "Run CN": row["run_id"],
                "État": row["status"],
                "Début": row["executed_at"],
                "Fin": row.get("finished_at"),
                "Code retour": row.get("returncode"),
            }
            for row in history[:30]
        ],
        use_container_width=True,
        hide_index=True,
    )
    selected_id = st.selectbox("Run CN à examiner", [row["run_id"] for row in history[:30]], key="sprint14c_run_id")
    record = get_backtesting_run_record(selected_id)
    if not record or record.get("run_kind") != "cn-research-replay":
        st.error("Run CN introuvable ou incompatible")
        return
    if (
        record.get("status") in ("running", "starting")
        and st.button("Arrêter ce replay CN", key="sprint14c_stop_cn_replay")
        and stop_backtesting_run(selected_id)
    ):
        st.warning("Arrêt demandé pour le replay CN.")
        st.rerun()
    log_tail = read_backtesting_logs(selected_id, "all", tail_lines=80)
    if not log_tail:
        log_tail = "\n".join(filter(None, (
            read_backtesting_logs(selected_id, "stdout", tail_lines=40),
            read_backtesting_logs(selected_id, "stderr", tail_lines=40),
        )))
    event = latest_progress_event(log_tail)
    stage = str(event.get("stage")) if event else "initializing"
    status = str(record.get("status") or "")
    if status == "completed":
        stage, progress = "completed", 100
    else:
        progress = {"initializing": 5, "replaying": 20,
                    "cell_written": 85, "report_written": 95, "failed": 0}.get(stage, 5)
    if status == "failed":
        st.error("Replay CN en échec : consulter le journal ci-dessous.")
    else:
        st.progress(progress, text={
            "initializing": "Démarrage / vérification des sources CN",
            "replaying": "Replay économique en cours",
            "cell_written": "Cellule calculée · finalisation du rapport",
            "report_written": "Rapport écrit · finalisation du processus",
            "completed": "Replay CN terminé",
        }.get(stage, "Calcul en cours"))
    if status in ("running", "starting"):
        elapsed = int(record.get("duration_seconds") or (event.get("elapsed_seconds", 0) if event else 0))
        st.caption(f"Durée écoulée : {elapsed // 60} min {elapsed % 60:02d} s · actualisation automatique toutes les 5 s. "
                   "La barre indique les étapes observées, pas le temps restant.")
    with st.expander("Journal du replay CN", expanded=status == "failed"):
        st.code(log_tail or "Le processus est lancé ; aucune ligne reçue pour l'instant. Suivi automatique actif.")
    run_root = (OUTPUT_PARENT / selected_id / "artifacts").resolve()
    if OUTPUT_PARENT.resolve() not in run_root.parents:
        return
    for report_path in sorted(run_root.glob("sprint13b-*/report.json"))[:1]:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(report, dict) or not isinstance(report.get("runs"), dict):
            st.error("Rapport CN mal formé : résultats indisponibles.")
            continue
        st.caption(
            f"Rapport : {report_path} · statut {report.get('status')} · "
            f"{len(report['runs'])} cellule(s) calculée(s). "
            "Le statut COMPLETED du processus n'est pas un GO économique."
        )
        for item in report["runs"].values():
            if not isinstance(item, dict):
                st.error("Cellule de replay CN mal formée ; résultat ignoré.")
                continue
            valid = item.get("economic_result_valid") is True
            if not valid:
                st.error(
                    "Résultat économique censuré/invalide : le rendement proxy ne doit pas être interprété. "
                    f"Motif : {item.get('status', 'inconnu')}"
                )
            st.dataframe(
                [
                    {
                        "Semestre": item.get("semester"),
                        "Politique": item.get("policy"),
                        "Valide économiquement": valid,
                        "Rendement proxy (%)": (
                            100 * item["marked_return_proxy"]
                            if valid and isinstance(item.get("marked_return_proxy"), (int, float))
                            else None
                        ),
                        "Capital final (CNY)": item.get("end_equity_cny") if valid else None,
                        "Drawdown proxy (%)": (
                            100 * item["max_drawdown_marked"]
                            if valid and isinstance(item.get("max_drawdown_marked"), (int, float))
                            else None
                        ),
                        "Commissions (CNY)": item.get("commission_total_cny"),
                        "Autres coûts (CNY)": item.get("other_costs_total_cny"),
                        "Achats hypothétiques": item.get("buy_fills"),
                        "Ventes hypothétiques": item.get("sell_fills"),
                    }
                ],
                use_container_width=True,
                hide_index=True,
            )


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
            options=(MarketCode.US_EQ.value, MarketCode.CN_A.value, MarketCode.FR_EQ.value),
            key=f"sprint14a_{page}_market_code",
            format_func=lambda value: MARKET_LABELS[str(value)],
            help="US conserve ses commandes ; CN et FR utilisent des parcours de recherche isolés, sans paper/live.",
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


@st.fragment(run_every="5s")
def _render_cn_fold_panel() -> None:
    """Sprint 14-D: one CN research fold trains and emits OOS predictions."""
    from ihm.services.backtesting_runner import format_command_for_display
    from ihm.services.cn_fold_launch import (
        OUTPUT_PARENT,
        STEP_KEY,
        CNResearchFoldOptions,
        build_cn_fold_command,
        fold_choices,
        start_cn_fold,
    )
    from ihm.services.cn_fold_worker import latest_progress_event
    from ihm.services.process_registry import (
        get_pipeline_run_record,
        list_active_pipeline_runs,
        load_pipeline_history,
        read_pipeline_logs,
        stop_pipeline_run,
    )

    st.subheader("Sprint 14-D — Entraînement et prédiction OOS CN_A")
    st.warning(
        "Un lancement = un fold de recherche 2022–2025, entraîné puis prédit sur le semestre test. "
        "Ce n'est ni une prédiction future/servable, ni un nouveau backtest. Aucun batch US n'est utilisé."
    )
    try:
        task = st.selectbox("Tâche CN", ("oracle", "ranking"), key="sprint14d_task")
        choices = fold_choices(task)
        horizon = st.selectbox("Horizon CN", choices["horizons"], key="sprint14d_horizon")
        semester = st.selectbox("Semestre OOS CN", choices["semesters"], key="sprint14d_semester")
        model = st.selectbox("Modèle CN", choices["models"], key="sprint14d_model")
        options = CNResearchFoldOptions(task=task, horizon=horizon, semester=semester, model=model)
        preview = replace(options, output_root=str(OUTPUT_PARENT / "preview" / "artifacts"))
        st.caption(
            "Marché CN_A · route alpha_trade_cn · sources CN 2018–2025 figées · sortie isolée par lancement. "
            "Ces modules lisent les artefacts CN sans écrire en base."
        )
        if task == "ranking":
            st.caption("Ranking exige deux folds Oracle OOS compatibles, LightGBM et CatBoost, pour le même horizon/semestre.")
        st.code(format_command_for_display(build_cn_fold_command(preview)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Formulaire CN indisponible : {exc}")
        return

    active = [row for row in list_active_pipeline_runs() if row.get("step_key") == STEP_KEY and row.get("is_active")]
    if active:
        st.info(f"Fold CN déjà en cours : {active[0]['run_id']}")
    if st.button("Entraîner et prédire ce fold OOS CN", key="sprint14d_launch", type="primary", disabled=bool(active)):
        try:
            with st.spinner("Vérification du protocole et des sources CN…"):
                record = start_cn_fold(options)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            st.error(f"Fold CN non lancé : {exc}")
        else:
            st.success(f"Fold CN lancé : {record.run_id}")
            st.rerun()

    history = [row for row in load_pipeline_history() if row.get("step_key") == STEP_KEY]
    if not history:
        st.caption("Aucun fold CN lancé depuis cette page.")
        return
    st.dataframe(
        [{"Run CN": row.get("run_id"), "État": row.get("status"),
          "Début": row.get("executed_at"), "Fin": row.get("finished_at"),
          "Code retour": row.get("returncode")} for row in history[:30]],
        use_container_width=True, hide_index=True,
    )
    selected_id = st.selectbox("Fold CN à examiner", [row["run_id"] for row in history[:30]], key="sprint14d_run_id")
    record = get_pipeline_run_record(selected_id)
    if not record or record.get("step_key") != STEP_KEY:
        st.error("Fold CN introuvable ou incompatible")
        return
    if (record.get("status") in ("running", "starting")
            and st.button("Arrêter ce fold CN", key="sprint14d_stop")
            and stop_pipeline_run(selected_id)):
        st.warning("Arrêt demandé pour ce fold CN.")
        st.rerun()
    journal = read_pipeline_logs(selected_id, "all")
    if not journal:
        journal = "\n".join(filter(None, (
            read_pipeline_logs(selected_id, "stdout"), read_pipeline_logs(selected_id, "stderr")
        )))
    event = latest_progress_event(journal)
    stage = str(event.get("stage")) if event else "initializing"
    status = str(record.get("status") or "")
    if status == "completed":
        stage, progress = "completed", 100
    else:
        progress = {"initializing": 5, "sources_verified": 20,
                    "model_written": 85, "report_written": 95,
                    "failed": 0}.get(stage, 5)
    if status == "failed":
        st.error("Fold CN en échec : consulter le journal ci-dessous.")
    else:
        st.progress(progress, text={
            "initializing": "Démarrage / préparation des sources CN",
            "sources_verified": "Sources vérifiées · chargement et entraînement en cours",
            "model_written": "Modèle écrit · évaluation OOS en cours",
            "report_written": "Prédictions et rapport écrits · finalisation",
            "completed": "Fold CN terminé",
        }.get(stage, "Calcul en cours"))
    if status in ("running", "starting"):
        elapsed = int(record.get("duration_seconds") or (event.get("elapsed_seconds", 0) if event else 0))
        st.caption(f"Durée écoulée : {elapsed // 60} min {elapsed % 60:02d} s · actualisation automatique toutes les 5 s. "
                   "La barre marque les étapes observées, pas le temps restant.")
    with st.expander("Journal du fold CN", expanded=status == "failed"):
        st.code(journal[-16000:] or "Le processus est lancé ; aucune ligne reçue pour l'instant. Suivi automatique actif.")
    command = record.get("command") or []
    if not isinstance(command, list) or "--output-root" not in command:
        return
    try:
        root = Path(command[command.index("--output-root") + 1]).resolve()
    except (IndexError, TypeError, ValueError):
        return
    if OUTPUT_PARENT.resolve() not in root.parents or not root.is_dir():
        return
    for report_path in sorted(root.glob("*/h*/*/*/report.json"))[:1]:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            st.error("Rapport du fold CN illisible")
            continue
        if report.get("market_code") != "CN_A" or report.get("status") != "OOS_RESEARCH_ONLY":
            st.error("Rapport du fold CN incompatible")
            continue
        st.caption(f"Rapport : {report_path} · prédictions : {report_path.parent / 'predictions.parquet'}")
        st.dataframe([{"Horizon": report.get("horizon"), "Semestre": report.get("test_semester"),
                       "Modèle": report.get("model_name"), "Statut": report.get("status"),
                       "Serving actif": report.get("serving_enabled")}],
                     use_container_width=True, hide_index=True)
        metrics = report.get("metrics") or {}
        if "precision_uplift" in metrics:
            model_metrics = metrics.get("model") or {}
            baseline_metrics = metrics.get("baseline_atr") or {}
            st.dataframe([{
                "Précision TOP20 modèle": model_metrics.get("precision_top20"),
                "Précision TOP20 ATR": baseline_metrics.get("precision_top20"),
                "Écart de précision": metrics.get("precision_uplift"),
                "Couverture prédictions": metrics.get("prediction_coverage"),
            }], use_container_width=True, hide_index=True)
        elif "oracle_top20" in metrics:
            oracle_metrics = metrics.get("oracle_top20") or {}
            model_metrics = oracle_metrics.get("model") or {}
            st.dataframe([{
                "Précision D10 TOP": model_metrics.get("d10_top_precision"),
                "Précision D1 BOTTOM": model_metrics.get("d1_bottom_precision"),
                "Uplift symétrique": oracle_metrics.get("tail_precision_uplift"),
                "IC moyen": model_metrics.get("ic_spearman_mean"),
                "Couverture prédictions": metrics.get("prediction_coverage"),
            }], use_container_width=True, hide_index=True)


def render_cn_research_view(page: PageKind) -> None:
    """Show only CN evidence; never call a US launcher or query its tables."""
    st.warning(
        "CN_A — recherche uniquement. Le Sprint 13-C n'a pas validé de politique économique ; "
        "prédiction future servable et live CN ne sont pas activés sur cette page."
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
            "Les étapes ML/Predict US restent masquées ici. Seuls les folds CN de recherche et leurs prédictions OOS sont accessibles."
        )
    elif page == "backtest":
        st.info(
            "Le replay CN de recherche possède son propre formulaire et son historique. "
            "Le formulaire backtest US n'est jamais réutilisé."
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
    if page == "backtest":
        _render_cn_replay_panel()
    elif page == "pipeline":
        _render_cn_fold_panel()
