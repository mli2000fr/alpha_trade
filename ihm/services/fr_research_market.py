"""Sprint 14-A: France research consultation; no legacy launcher or DB access."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import streamlit as st

from service.fr.research_catalog_14a import CATALOG, economic_rows, load_campaign


@st.fragment(run_every="5s")
def _render_replay_panel(page: str) -> None:
    from ihm.services.backtesting_registry import (
        start_backtesting_run, load_backtesting_history, list_active_backtesting_runs_by_kind,
        get_backtesting_run_record, read_backtesting_logs, stop_backtesting_run,
    )
    from ihm.services.backtesting_runner import format_command_for_display
    from ihm.services.fr_replay_launch import build_fr_replay_command, FRResearchReplayOptions, OUTPUT_PARENT
    from service.fr.research_replay_14b import latest_progress_event
    from service.fr.exploitable_scope_12e import sha

    st.subheader("Lancer un replay FR — une cellule figée")
    st.caption("Archives locales uniquement : aucun entraînement, SQL, téléchargement ou ordre. Ce rejeu reproduit le développement déjà inspecté ; ce n'est pas une nouvelle confirmation.")
    fold = st.selectbox("Fold FR", (6, 7), key=f"fr14_{page}_fold")
    policy = st.selectbox("Politique FR", ("oracle_top20_long", "atr_top20_long", "uniform_control_long"), key=f"fr14_{page}_policy")
    variant = st.selectbox("Variante pré-enregistrée", ("baseline", "delay_1", "cap_10pct", "delay_1_cap_10pct"), key=f"fr14_{page}_variant")
    tax = st.selectbox("Fiscalité inconnue — hypothèse", ("unknown_taxed", "unknown_untaxed"), key=f"fr14_{page}_tax")
    cost = st.selectbox("Scénario de coûts FR", ("nominal", "stress_execution_x2"), key=f"fr14_{page}_cost")
    options = FRResearchReplayOptions(fold=fold, policy=policy, variant=variant, tax_scenario=tax, cost_scenario=cost)
    preview = replace(options, output_root=str(OUTPUT_PARENT / "preview" / "artifacts"))
    st.code(format_command_for_display(build_fr_replay_command(preview)))
    st.caption("Commande indicative : l'IHM attribue un ID et une sortie uniques lors du lancement. Capital, univers, classement, horizon et coûts sont ceux du protocole figé ; pas de sélection de dates 2026.")
    active = list_active_backtesting_runs_by_kind("fr-research-replay")
    if active:
        st.info(f"Replay France actif : {active[0]['run_id']}")
    if st.button("Lancer le replay France", type="primary", disabled=bool(active), key=f"fr14_{page}_launch"):
        try:
            with st.spinner("Contrôle des archives et des empreintes FR…"):
                record = start_backtesting_run("fr-research-replay", "FR_EQ — replay exploratoire EUR", options, db_config=None)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            st.error(f"Replay non lancé : {exc}")
        else:
            st.success(f"Run FR créé : {record.run_id}")
            st.rerun()

    history = [r for r in load_backtesting_history() if r.get("run_kind") == "fr-research-replay"]
    if not history:
        st.caption("Aucun replay FR historisé pour le moment.")
        return
    st.dataframe([{"Run FR": r["run_id"], "État": r["status"], "Début": r["executed_at"],
                   "Fin": r.get("finished_at"), "Code retour": r.get("returncode")} for r in history[:30]],
                 width="stretch", hide_index=True)
    run_id = st.selectbox("Run France à consulter", [r["run_id"] for r in history[:30]], key=f"fr14_{page}_run")
    record = get_backtesting_run_record(run_id)
    if not record or record.get("run_kind") != "fr-research-replay":
        st.error("Run incompatible ou introuvable")
        return
    status = record.get("status")
    if status in ("starting", "running") and st.button("Arrêter ce run FR", key=f"fr14_{page}_stop"):
        if stop_backtesting_run(run_id):
            st.warning("Arrêt demandé ; aucune reprise automatique.")
            st.rerun()
    journal = read_backtesting_logs(run_id, "all", tail_lines=100)
    event = latest_progress_event(journal)
    stage = event["stage"] if event else "preflight"
    milestones = {"preflight": (0, "Contrôle des archives"), "loading": (1, "Chargement des candidats et tapes"),
                  "replaying": (2, "Replay du portefeuille"), "report_written": (3, "Rapport écrit")}
    if status == "completed":
        st.progress(1.0, text="Processus terminé — consulter la reproduction ci-dessous")
    elif status in ("failed", "stopped", "timeout"):
        st.error(f"Run FR : {status}. Consulter les logs ; pas de performance validée.")
    else:
        step, label = milestones.get(stage, (0, "Initialisation"))
        st.progress(step / 4, text=f"Jalon {step}/4 : {label}")
    st.caption("Actualisation toutes les 5 secondes. Barre de jalons observés, pas estimation du temps restant.")
    st.caption(f"Durée observée : {float(record.get('duration_seconds') or 0):.1f} secondes.")
    with st.expander("Logs FR — stdout/stderr", expanded=status == "failed"):
        st.code(journal or "Processus lancé ; aucune ligne reçue pour l'instant.")
    root = (OUTPUT_PARENT / run_id / "artifacts").resolve()
    if not root.is_relative_to(OUTPUT_PARENT.resolve()):
        st.error("Chemin du run hors périmètre FR")
        return
    if status == "completed":
        try:
            report = json.loads((root / "report.json").read_text(encoding="utf-8"))
            if (report.get("market_code") != "FR_EQ" or report.get("serving_enabled") is not False
                    or report.get("exact_archive_reproduction") is not True
                    or report.get("economic_go_allowed") is not False
                    or report.get("protocol_sha256") != sha(root / "protocol.json")
                    or report.get("ledger_sha256") != sha(root / "ledger.json")):
                raise ValueError("Contrat ou empreintes du résultat FR invalides")
            st.success("Cellule reproduite à l'identique — toujours exploratoire, aucun GO économique.")
            st.json(report["metrics"])
            st.download_button("Télécharger ce run FR_EQ (EUR)", json.dumps(report, ensure_ascii=False, indent=2),
                               file_name=f"FR_EQ_EUR_{run_id}.json", mime="application/json", key=f"fr14_{page}_run_export")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.error(f"Résultat FR indisponible/non vérifié : {exc}")


def render_fr_research_view(page: str) -> None:
    from ihm.services.fr_operations_view_18 import render_operations_preparation
    render_operations_preparation(page)
    st.warning(
        "FR_EQ — recherche uniquement. Politique LONG H5 : NO-GO exploratoire ; "
        "validation économique stricte bloquée. Aucun paper, live ou serving activé."
    )
    st.caption("Base alpha_trade_fr · devise EUR · calendrier XPAR · horizon Oracle H5. Aucun historique US/CN n'est mélangé.")
    st.caption("Sources : archives EODHD et réparations documentées du protocole. Univers historique qualifié limité, pas totalité des titres cotés. Références du replay : ATR TOP20 et contrôle uniforme ; aucun alpha contre un indice total-return qualifié n'est annoncé.")
    if page == "pipeline":
        st.info("Les étapes US sont masquées. Consultation des campagnes et lancement d'une cellule FR exploratoire figée ci-dessous.")
    if page == "backtest":
        st.info("Résultats du replay fournisseur exploratoire, pas une validation économique stricte. Les folds sont des portefeuilles indépendants ; ne pas additionner leurs rendements.")
    choices = [key for key, (_, _, kind) in CATALOG.items()
               if page != "backtest" or kind == "economic"]
    selected = st.selectbox("Campagne France", choices, key=f"fr14_{page}_campaign",
                            format_func=lambda key: CATALOG[key][0])
    try:
        campaign = load_campaign(selected)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Campagne FR indisponible : {exc}. Aucun remplacement par une campagne US.")
        return
    st.subheader(campaign["label"])
    st.caption(f"État : {campaign['status']} · rapport : {campaign['report_path']} · SHA-256 {campaign['report_sha256']}")
    st.code(f"python -m service.fr.research_catalog_14a --campaign {selected}")
    if campaign["kind"] == "economic":
        rows = economic_rows(campaign)
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption("Commission, spread, slippage et taxes sont séparés en EUR. Spread/slippage : hypothèses, pas quotes/fills vérifiés. Inconnus fiscaux : scénarios, pas exonérations prouvées.")
        st.caption("Fold 6 : entrées 2024-07-29→2025-01-23 ; fold 7 : 2025-01-24→2025-07-23. Confirmation 2026 non consultée.")
    else:
        report = campaign["report"]
        st.json({key: value for key, value in report.items() if key not in ("config", "folds")})
        with st.expander("Folds et métriques détaillés"):
            st.json(report.get("folds", []))
    with st.expander("Manifeste / sources / univers / profil / règles figées"):
        st.json(campaign["manifest"])
    st.download_button("Télécharger le diagnostic FR_EQ (EUR)",
                       json.dumps(campaign, ensure_ascii=False, indent=2),
                       file_name=f"FR_EQ_EUR_{selected}.json", mime="application/json",
                       key=f"fr14_export_{page}")
    st.caption("Historique contrôlé : campagnes explicitement référencées, pas sélection automatique du dernier dossier. Source absente ou contrat incompatible : arrêt de la consultation.")
    if page in ("pipeline", "backtest"):
        _render_replay_panel(page)
