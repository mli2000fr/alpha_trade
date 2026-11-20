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
GPT_KEY = 'pipeline_q051_manual_llm_filter'
GPT_DEFAULT_KEY = 'pipeline_q051_gpt_config_default'


def sync_gpt_default(state, configured):
    """A config change updates the widget; ordinary reruns preserve explicit edits."""
    if state.get(GPT_DEFAULT_KEY) is not configured:
        state[GPT_KEY] = configured
        state[GPT_DEFAULT_KEY] = configured
    state.setdefault(GPT_KEY, configured)


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


def launch(defaults, *, db_config, recovery_date=None, llm_filter_enabled=None):
    """Exact same launcher as Batches; no parallel approximation of 10/11/12."""
    return start_batch(defaults.spec, db_config=db_config, recovery_date=recovery_date,
                       **({'q051_llm_filter':llm_filter_enabled} if llm_filter_enabled is not None else {}))


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
                   'Filtre options désactivé ; GPT/DeepSeek suit le paramètre du batch ci-dessous.')
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
    configured_llm = opts.llm_filter_enabled
    use_llm = configured_llm
    if llm_supported:
        key = GPT_KEY
        sync_gpt_default(st.session_state, configured_llm)
        if not llm_cfg.manual_opt_in_allowed:
            st.session_state[key] = configured_llm
        use_llm = st.checkbox(
            f'🌐 Filtrage {llm_cfg.provider_label} — probabilité de hausse sans SL, recherche Web après per-symbol',
            value=configured_llm, key=key, disabled=blocked or not llm_cfg.manual_opt_in_allowed,
            help='Défaut : config.yaml → us_pipeline.gpt_filter_enabled. Une modification ici ne vaut que pour ce lancement. Les candidats LONG sont analysés avant le risque ; aucun SHORT ni remplacement.')
        st.caption(f'Paramètre du batch : us_pipeline.gpt_filter_enabled = {str(configured_llm).lower()}. '
                   'Le batch planifié et le réglage initial de cette case utilisent cette valeur.')
        if not llm_cfg.manual_opt_in_allowed:
            st.caption('Activation manuelle bloquée par config.yaml → llm_directional_filter.manual_opt_in_allowed.')
        if use_llm:
            st.info(f'{llm_cfg.provider_label} analysera uniquement les candidats LONG sélectionnés, sur l’horizon du modèle. '
                    'Recherche Web et dossier local ; appels API payants uniquement au lancement. '
                    'Vous validerez les titres dans le tableau avant le risque. '
                    'La sélection validée est partagée entre les comptes papier ; protections Winner conservées.')
        if use_llm != configured_llm:
            st.caption('Choix différent du batch pour ce lancement uniquement ; config.yaml reste inchangé.')
    override_requested = use_llm != configured_llm
    if not view.spec.runnable:
        st.warning(f'Le batch us_pipeline est désactivé ou bloqué dans batch.yaml ({view.spec.status}).')
    if active_runs:
        st.warning('Un lancement est déjà actif ; consultez son suivi ci-dessous.')
    if view.skip_reason:
        messages = {'SESSION_NOT_CLOSED': 'La séance US n’est pas encore clôturée.',
                    'NON_TRADING_DAY': 'Aucune séance US à traiter aujourd’hui.'}
        st.caption(messages.get(view.skip_reason, view.skip_reason)
                   + ' Le même contrôle de calendrier que le batch reste appliqué.')
    launch_label = (f'▶️ Lancer le pipeline — avec filtre {llm_cfg.provider_label}' if use_llm
                    else '▶️ Lancer le pipeline — configuration us_pipeline')
    if st.button(launch_label, key='pipeline_launch_us_batch_defaults',
                 type='primary', disabled=blocked or bool(view.skip_reason)):
        try:
            record = launch(view, db_config=db_config,
                            **({'llm_filter_enabled':use_llm} if override_requested else {}))
        except Exception as exc:
            st.error(f'Pipeline non lancé : {exc}')
        else:
            _remember(record)
    recovery = us_pipeline_recovery_state(view.spec)
    if recovery.get('visible'):
        day = recovery['trade_date']
        if st.button(f'↩️ Rattraper la séance {day}', key='pipeline_us_defaults_recovery',
                     disabled=blocked or not recovery.get('eligible') or override_requested):
            try:
                record = launch(view, db_config=db_config, recovery_date=day)
            except Exception as exc:
                st.error(f'Rattrapage non lancé : {exc}')
            else:
                _remember(record)
    if recovery.get('reason'):
        st.caption(recovery['reason'])
    if recovery.get('visible'):
        st.caption('Le rattrapage conserve sa configuration et sa sélection initiales. '
                   'Rétablissez la valeur configurée de la case avant de reprendre un run existant.')
    render_selection(view)
    return view.options


@st.fragment(run_every='5s')
def render_selection(view):
    """Display the actual sealed daily selection, not the bundle's generic defaults."""
    if not view.options.q051_paper_enabled:
        return
    from service.q051_paper.pipeline import ARTIFACTS
    opts = view.options
    matches = []
    for path in ARTIFACTS.glob('q051-*/selection.json'):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if (record.get('status') == 'COMPLETED' and record.get('batch_id') == opts.ml_predict_batch_id
                    and record.get('strategy_profile') == opts.q051_profile_id):
                matches.append((record.get('cutoff', ''), path, record))
        except (OSError, ValueError):
            continue
    with st.expander('10. ML Predict — sélection du parcours quotidien', expanded=True):
        from ihm.components.probability_selection import render_demo
        render_demo()
        path,record=_render_archived_prediction(matches,opts)
    from ihm.components.pipeline_batch_results import render_account_stages
    render_account_stages(view,path,record)


def _render_archived_prediction(matches,opts):
    from service.q051_paper.pipeline import digest
    if not matches:
        st.info(f'Aucune sélection quotidienne terminée pour la séance {opts.trade_date} et ce profil.')
        return None,None
    matches.sort(key=lambda item:item[0],reverse=True)
    # Keep the exact dated proposal accessible when approval crosses midnight.
    index=st.selectbox('Sélection du parcours à consulter',range(len(matches)),
        format_func=lambda i:f'{matches[i][2]["trade_date"]} · {matches[i][2]["run_id"]}',
        key='pipeline_us_defaults_proposal') if len(matches)>1 else 0
    _,path,record=matches[index]
    try:
        seal=json.loads((path.parent/'seal.json').read_text(encoding='utf-8'))
        if (seal['report_sha256']!=digest(path)
                or record['selection_sha256']!=digest(path.parent/'selection.parquet')):
            raise ValueError('Empreinte de la sélection incompatible')
        import pandas as pd
        frame=pd.read_parquet(path.parent/'selection.parquet')
        st.caption(f'Sélection archivée : {record["run_id"]} · séance {record["trade_date"]} · cutoff {record["cutoff"]}. '
                   'Retenu ne signifie ni approuvé par le risque, ni acheté.')
        oracle_score='proba_extreme' if 'proba_extreme' in frame else 'oracle_score'
        names={'symbol':'Symbole','oracle_rank':'Rang Oracle',oracle_score:'Score Oracle',
               'long_probability':'Score LONG','long_auc':'AUC LONG',
               'rank':'Rang LONG','selected':'Retenu','reason':'Motif'}
        if record.get('llm_filter'):
            names.update(llm_direction_score='Score GPT/DeepSeek /10',llm_decision='Avis LLM',
                         llm_evidence_quality='Qualité des preuves LLM',llm_blockers='Motifs LLM')
            info=record['llm_filter']
            st.caption(f'Filtre LLM : {info.get("run_id") or "aucun candidat à analyser"} · '
                       f'H{info["horizon"]} · {len(info["selected"])} évaluable(s) sur {info["requested"]}.')
        from service.llm_directional.prompts import PROBABILITY_VERSION
        if record.get('llm_filter',{}).get('protocol')==PROBABILITY_VERSION:
            from ihm.components.probability_selection import render as render_probability
            render_probability(path.parent,record,frame)
        else:
            st.dataframe(frame[[k for k in names if k in frame]].rename(columns=names),
                         hide_index=True,use_container_width=True)
        return path,record
    except (OSError,ValueError,KeyError) as exc:
        st.warning(f'Sélection archivée indisponible : {exc}')
        return None,None
