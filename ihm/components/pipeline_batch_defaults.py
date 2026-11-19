"""Pipeline's default daily view uses the actual batch launcher, not a UI copy."""
from dataclasses import dataclass
from datetime import UTC, datetime
import json

import streamlit as st

from ihm.services.batch_management import (
    BatchSpec, load_batch_specs, start_batch, us_pipeline_recovery_state,
)
from ihm.services.pipeline_runner import PipelineLaunchOptions


MODE_KEY = 'pipeline_use_us_batch_defaults'


@dataclass(frozen=True)
class BatchDefaults:
    spec: BatchSpec
    options: PipelineLaunchOptions
    steps: tuple
    steps_source: str
    other_accounts: tuple[str, ...]
    skip_reason: str | None


def load_defaults(*, now=None):
    from service.forward_pit.us_pipeline import (
        load_pipeline_policy, session_plan, session_steps,
        fresh_pipeline_options, additional_paper_accounts,
    )
    spec = next(s for s in load_batch_specs() if s.name == 'us_pipeline')
    if spec.raw_config.get('market_code') != 'US_EQ':
        raise ValueError('Configuration us_pipeline réservée au marché US')
    policy = load_pipeline_policy()
    day, skip = session_plan(now or datetime.now(UTC))
    key, steps = session_steps(policy, day)
    options = fresh_pipeline_options(dict(spec.raw_config), policy, day, steps)
    others = additional_paper_accounts(options, policy, steps)
    return BatchDefaults(spec, options, steps, key, others, skip)


def launch(defaults, *, db_config, recovery_date=None, llm_filter_enabled=False):
    """Exact same launcher as Batches; no parallel approximation of 10/11/12."""
    return start_batch(defaults.spec, db_config=db_config, recovery_date=recovery_date,
                       **({'q051_llm_filter':True} if llm_filter_enabled else {}))


def _remember(record):
    from ihm.pages._shared import PENDING_SELECTED_RUN_KEY
    st.session_state[PENDING_SELECTED_RUN_KEY] = record.run_id
    st.success(f'Pipeline lancé en arrière-plan : {record.run_id}. Suivi et logs ci-dessous.')
    st.rerun()


def render(*, db_config, active_runs):
    try:
        view = load_defaults()
    except Exception as exc:
        st.error(f'Configuration us_pipeline indisponible : {exc}')
        st.caption('Le lancement reste bloqué ; aucun ancien réglage personnalisé n’est substitué.')
        return
    opts = view.options
    st.info('Valeurs par défaut communes avec le batch us_pipeline. Le lancement utilise son orchestration '
            'complète : collectes, sélection, risque, watcher avant exécution et autres comptes papier configurés.')
    st.caption(f'Séance US : {opts.trade_date} · mode : {opts.execution_mode.upper()} · '
               f'comptes : {", ".join((opts.account_id or "default", *view.other_accounts))}. '
               'Le compte choisi dans la barre latérale ne remplace pas les comptes du batch.')
    st.caption('Étapes : ' + ' → '.join(s.num for s in view.steps)
               + f' · source : config.yaml / us_pipeline.{view.steps_source}.')
    if opts.q051_paper_enabled:
        from common.q051_paper import reference, settings
        p = reference(opts.q051_profile_id)
        current = settings()
        selection, winner = p['selection'], p['winner']
        st.markdown(f'**{p["reference"]}** · modèle `{opts.ml_predict_batch_id}`')
        st.write(f'TOP {selection["oracle_fraction"]:.0%} Oracle → jusqu’à {selection["long_top_n"]} LONG par titre ; '
                 f'score > {selection["min_long_probability"]:.2f}, AUC ≥ {selection["min_long_auc"]:.2f}. '
                 f'Anti-SL {"activé" if selection.get("apply_anti_sl", True) else "désactivé"}.')
        st.write(f'SL {winner["stop_loss_pct"]:.0%} ; '
                 f'TP {"désactivé" if winner["take_profit_pct"] is None else str(winner["take_profit_pct"])} ; '
                 f'trailing {"désactivé" if winner["trailing_stop_pct"] is None else str(winner["trailing_stop_pct"])} ; '
                 f'{winner["confirmation_bars"]} confirmation(s) 5 min ; '
                 f'sortie à l’ouverture de la {winner["horizon_sessions"] + 1}e séance. '
                 f'Entrées {current["entry_time_in_force"].upper()}, sorties {current["exit_time_in_force"].upper()}.')
        st.caption('Capital réel de chaque compte pour les quantités ; profil de risque versionné commun. '
                   'Filtre options désactivé ; GPT/DeepSeek reste facultatif ci-dessous.')
    else:
        st.caption(f'Filtre GPT/DeepSeek : {"activé" if opts.llm_filter_enabled else "désactivé"} ; '
                   f'filtre options : {"activé" if opts.options_filter_enabled else "désactivé"}.')
    with st.expander('Détails de la configuration commune'):
        from dataclasses import asdict
        values = asdict(opts)
        # Selection IDs are generated at the real launch; no preview ID is reusable.
        values.pop('q051_run_id', None)
        st.json(dict(source='config.yaml + batch.yaml', options=values))
    blocked = bool(active_runs) or not view.spec.runnable
    from service.llm_directional.config import load_filter_config
    llm_cfg = load_filter_config()
    llm_supported = opts.q051_paper_enabled and opts.account_id == 'default' and opts.execution_mode == 'paper'
    use_llm = False
    if llm_supported:
        key = 'pipeline_q051_manual_llm_filter'
        if not llm_cfg.manual_opt_in_allowed:
            st.session_state[key] = False
        use_llm = st.checkbox(
            f'🌐 Filtrage {llm_cfg.provider_label} — {llm_cfg.mode_label} après le classement LONG per-symbol',
            value=False, key=key, disabled=blocked or not llm_cfg.manual_opt_in_allowed,
            help='Option pour ce lancement manuel uniquement. Les candidats LONG sont analysés avant le risque ; aucun SHORT ni remplacement. Le batch planifié conserve sa configuration.')
        if not llm_cfg.manual_opt_in_allowed:
            st.caption('Activation manuelle bloquée par config.yaml → llm_directional_filter.manual_opt_in_allowed.')
        if use_llm:
            st.info(f'{llm_cfg.provider_label} analysera uniquement les candidats LONG sélectionnés, sur l’horizon du modèle. '
                    'Appels API payants uniquement au lancement. SL, quantités et sortie Winner conservés. '
                    'La sélection finale est partagée entre les comptes papier.')
    if not view.spec.runnable:
        st.warning(f'Le batch us_pipeline est désactivé ou bloqué dans batch.yaml ({view.spec.status}).')
    if active_runs:
        st.warning('Un lancement est déjà actif ; consultez son suivi ci-dessous.')
    if view.skip_reason:
        messages = {'SESSION_NOT_CLOSED': 'La séance US n’est pas encore clôturée.',
                    'NON_TRADING_DAY': 'Aucune séance US à traiter aujourd’hui.'}
        st.caption(messages.get(view.skip_reason, view.skip_reason)
                   + ' Le même contrôle de calendrier que le batch reste appliqué.')
    launch_label = (f'▶️ Lancer le pipeline — avec filtre {llm_cfg.provider_label} manuel' if use_llm
                    else '▶️ Lancer le pipeline — configuration us_pipeline')
    if st.button(launch_label, key='pipeline_launch_us_batch_defaults',
                 type='primary', disabled=blocked or bool(view.skip_reason)):
        try:
            record = launch(view, db_config=db_config, **({'llm_filter_enabled':True} if use_llm else {}))
        except Exception as exc:
            st.error(f'Pipeline non lancé : {exc}')
        else:
            _remember(record)
    recovery = us_pipeline_recovery_state(view.spec)
    if recovery.get('visible'):
        day = recovery['trade_date']
        if st.button(f'↩️ Rattraper la séance {day}', key='pipeline_us_defaults_recovery',
                     disabled=blocked or not recovery.get('eligible') or use_llm):
            try:
                record = launch(view, db_config=db_config, recovery_date=day)
            except Exception as exc:
                st.error(f'Rattrapage non lancé : {exc}')
            else:
                _remember(record)
    if recovery.get('reason'):
        st.caption(recovery['reason'])
    if use_llm and recovery.get('visible'):
        st.caption('Le rattrapage conserve sa sélection scellée. Désactivez cette option pour reprendre ce run existant.')
    render_selection(view)
    return view.options


@st.fragment(run_every='5s')
def render_selection(view):
    """Display the actual sealed daily selection, not the bundle's generic defaults."""
    if not view.options.q051_paper_enabled:
        return
    from service.q051_paper.pipeline import ARTIFACTS, digest
    opts = view.options
    matches = []
    for path in ARTIFACTS.glob('q051-*/selection.json'):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if (record.get('status') == 'COMPLETED' and record.get('trade_date') == opts.trade_date
                    and record.get('batch_id') == opts.ml_predict_batch_id
                    and record.get('strategy_profile') == opts.q051_profile_id):
                matches.append((record.get('cutoff', ''), path, record))
        except (OSError, ValueError):
            continue
    with st.expander('10. ML Predict — sélection du parcours quotidien', expanded=True):
        if not matches:
            st.info(f'Aucune sélection quotidienne terminée pour la séance {opts.trade_date} et ce profil.')
            return
        _, path, record = max(matches, key=lambda item: item[0])
        try:
            seal = json.loads((path.parent/'seal.json').read_text(encoding='utf-8'))
            if (seal['report_sha256'] != digest(path)
                    or record['selection_sha256'] != digest(path.parent/'selection.parquet')):
                raise ValueError('Empreinte de la sélection incompatible')
            import pandas as pd
            frame = pd.read_parquet(path.parent/'selection.parquet')
            st.caption(f'Sélection archivée : {record["run_id"]} · cutoff {record["cutoff"]}. '
                       'Retenu ne signifie ni approuvé par le risque, ni acheté.')
            oracle_score = 'proba_extreme' if 'proba_extreme' in frame else 'oracle_score'
            names = {'symbol':'Symbole', 'oracle_rank':'Rang Oracle', oracle_score:'Score Oracle',
                     'long_probability':'Score LONG', 'long_auc':'AUC LONG',
                     'rank':'Rang LONG', 'selected':'Retenu', 'reason':'Motif'}
            if record.get('llm_filter'):
                names.update(llm_direction_score='Score GPT/DeepSeek /10', llm_decision='Avis LLM',
                             llm_evidence_quality='Qualité des preuves LLM', llm_blockers='Motifs LLM')
                info = record['llm_filter']
                st.caption(f'Filtre LLM manuel : {info.get("run_id") or "aucun candidat à analyser"} · '
                           f'H{info["horizon"]} · {len(info["selected"])} retenu(s) sur {info["requested"]}.')
            st.dataframe(frame[[k for k in names if k in frame]].rename(columns=names),
                         hide_index=True, use_container_width=True)
        except (OSError, ValueError, KeyError) as exc:
            st.warning(f'Sélection archivée indisponible : {exc}')
            return
    with st.expander('11. Risk Management — décisions par compte', expanded=False):
        accounts = (opts.account_id or 'default', *view.other_accounts)
        account = st.selectbox('Compte à consulter', accounts, key='pipeline_us_defaults_review_account')
        folder = path.parent/'accounts'/account
        try:
            risk_path = folder/'risk.json'
            if not risk_path.is_file():
                st.info(f'Aucune décision du risque publiée pour {account} et cette sélection.')
                return
            risk = json.loads(risk_path.read_text(encoding='utf-8'))
            seal = json.loads((folder/'risk.seal.json').read_text(encoding='utf-8'))
            if (seal['risk_sha256'] != digest(risk_path)
                    or risk['selection_sha256'] != digest(path)
                    or risk['q051_run_id'] != record['run_id'] or risk['account_id'] != account):
                raise ValueError('Décisions du risque incompatibles avec la sélection affichée')
            decisions = pd.DataFrame(risk['decisions'])
            st.caption(f'Risque archivé : {risk["risk_run_id"]} · capital {risk["equity"]:,.2f} $ · '
                       f'{risk["approved_count"]} approuvé(s), {risk["rejected_count"]} refusé(s). '
                       'Une approbation du risque ne prouve pas un remplissage broker.')
            if decisions.empty:
                st.info('Aucune cible de risque pour cette sélection.')
                return
            names = {'symbol':'Symbole','decision':'Décision','reason':'Motif','approved_shares':'Quantité',
                     'entry_price':'Prix de référence','target_notional':'Montant cible','score_used':'Score LONG'}
            st.dataframe(decisions[[k for k in names if k in decisions]].rename(columns=names),
                         hide_index=True,use_container_width=True)
        except (OSError,ValueError,KeyError) as exc:
            st.warning(f'Décisions du risque indisponibles : {exc}')
