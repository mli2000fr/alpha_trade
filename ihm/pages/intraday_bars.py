"""Dedicated US intraday history ingestion, using the existing managed runner."""
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st
from ihm.pages import run_page_if_standalone
from ihm.services.intraday_backfill import build_command,universe_options,DEFAULT_SOURCE,universe_file_label,PROJECT_ROOT
from ihm.services.pipeline_runner import format_command_for_display
from ihm.services.process_registry import (start_managed_run,poll_pipeline_run,stop_pipeline_run,
    read_pipeline_logs,load_pipeline_history,delete_pipeline_history_run)
from service.market.intraday_backfill import build_plan, intraday_defaults


@st.fragment(run_every='3s')
def _progress(run_id,plan_id):
    record=poll_pipeline_run(run_id)
    path=PROJECT_ROOT/'artifacts/intraday_backfill'/plan_id/'progress.json'
    legacy=PROJECT_ROOT/'artifacts/eodhd_intraday_backfill'/plan_id/'progress.json'
    if not path.exists() and legacy.exists():path=legacy
    if path.exists():
        try:
            progress=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            progress={}
        complete=int(progress.get('completed_tasks',0));total=int(progress.get('total_tasks',0))
        st.progress(min(1.,complete/total) if total else 0.,text=f'{complete:,} / {total:,} tranches terminees')
        st.caption(f"Etat : {progress.get('status','—')} · reprise ignorees : {progress.get('skipped',0)}")
        cols=st.columns(4)
        for column,label,key in zip(cols,['Barres recues','Barres persistees','Tranches en echec','Barres rejetees'],
                                    ['received','persisted','failed_tasks','rejected']):
            column.metric(label,int(progress.get(key,0)))
        st.caption('Persistées = barres qualifiées soumises en UPSERT, pas nécessairement nouvelles lignes. Compteurs du plan incluant les tranches déjà terminées.')
        if progress.get('current'):st.write(progress['current'])
        if progress.get('error'):st.error(progress['error'])
    if record:
        st.caption(f"Processus : {record['status']} · run {run_id}")
        stop_col,delete_col=st.columns(2)
        active=record['status'] in ('running','starting','scheduled')
        if stop_col.button('⏹ Arrêter le run',key=f'intraday_stop_{run_id}',disabled=not active):
            if stop_pipeline_run(run_id):st.rerun()
            else:st.error("Le processus n'est plus géré par cette session ; arrêt non effectué.")
        terminal=record['status'] in ('completed','failed','timeout','stopped')
        if delete_col.button('🗑 Supprimer de la liste',key=f'intraday_delete_{run_id}',disabled=not terminal,
                help='Retire uniquement cette exécution de l’historique visible. Barres, logs et reprise conservés.'):
            try:
                removed=delete_pipeline_history_run(run_id,expected_step_key='intraday_backfill')
            except ValueError as exc:st.error(str(exc))
            else:
                if removed:
                    if st.session_state.get('intraday_run_id')==run_id:
                        st.session_state.pop('intraday_run_id',None)
                        st.session_state.pop('intraday_plan_id',None)
                    st.session_state.pop('intraday_history',None)
                    st.rerun()
        with st.expander('Logs du backfill',expanded=True):
            st.caption('INFO = progression, pas une erreur. [stdout]/[stderr] indiquent le flux de sortie, pas la gravité.')
            st.code('\n'.join(read_pipeline_logs(run_id).splitlines()[-100:]),language='text',height=350)
    st.caption(str(path))


def render():
    st.title('🕒 Barres intraday — backfill US')
    st.info('Alpaca / EODHD → alpha_trade.stock_bars_intraday. Sources séparées, table indépendante des barres journalières.')
    try:defaults=intraday_defaults()
    except ValueError as exc:
        st.error(str(exc));return
    provider=st.selectbox('Fournisseur',('alpaca','eodhd'),index=('alpaca','eodhd').index(defaults['provider']),
        format_func=lambda x:{'alpaca':'Alpaca','eodhd':'EODHD'}[x],key='intraday_provider')
    feed=defaults['alpaca_feed'];account_id=defaults['account_id']
    if provider=='alpaca':
        feed=st.selectbox('Flux Alpaca',('sip',),index=0,key='intraday_feed')
        st.caption(f'Compte Alpaca : {account_id}. SIP historique uniquement ; aucun fallback IEX. Un ancien plan IEX exige un nouveau plan et un vrai téléchargement SIP.')
    else:
        st.caption('EODHD : accès EOD + Intraday ou All-in-One nécessaire ; le forfait EOD seul ne suffit pas.')
    st.caption('Prix bruts non ajustés, heures UTC ; dates et séances New York. Aucune barre manquante remplie. '
        'Données fournisseur à qualifier avant étude de réaction aux news : ce ne sont pas des quotes d’exécution certifiées.')
    yesterday=datetime.now(ZoneInfo('America/New_York')).date()-timedelta(days=1)
    a,b=st.columns(2)
    start=a.date_input('Date de début',value=date(2025,1,1),key='intraday_start')
    end=b.date_input('Date de fin',value=yesterday,max_value=yesterday,key='intraday_end')
    sources=universe_options()
    if not sources:
        st.warning('Aucun fichier univers disponible.');return
    source=st.selectbox('Univers de symboles',sources,index=sources.index(DEFAULT_SOURCE) if DEFAULT_SOURCE in sources else 0,
        format_func=universe_file_label,key='intraday_universe')
    interval=st.selectbox('Intervalle',('5m','1m','1h'),format_func=lambda x:{'5m':'5 minutes','1m':'1 minute','1h':'1 heure'}[x],key='intraday_interval')
    with st.expander('Reprise et limites'):
        days=st.number_input('Jours par tranche',min_value=1,max_value=120,value=30,key='intraday_chunk')
        refresh=st.checkbox('Retélécharger les tranches déjà terminées',value=False,key='intraday_refresh',
            help='Par défaut : reprendre seulement les tranches absentes/en échec. Une retélécharge met à jour sans doublon et archive les réponses.')
        limit=st.number_input('Maximum de tranches ce passage — 0 = toutes',min_value=0,value=0,key='intraday_limit')
    try:
        options=dict(provider=provider,alpaca_feed=feed,account_id=account_id)
        command=build_command(start,end,source,interval,int(days),refresh,int(limit) or None,**options)
        plan=build_plan(start,end,source,interval,int(days),**options)
        command.extend(['--expected-plan-id',plan['plan_id']])
    except (ValueError,FileNotFoundError) as exc:
        st.error(str(exc));return
    st.code(format_command_for_display(command),language='powershell')
    budget=f"environ {plan['estimated_api_credits']:,} crédits API" if provider=='eodhd' else 'appels Alpaca supplémentaires possibles selon pagination'
    st.caption(f"{len(plan['symbols']):,} titres · {plan['tasks']:,} tranches · {budget}, hors retries/reprise. "
        'Écriture SQL par lots de 500 barres ; reprise du même plan et univers inchangé.')
    existing=load_pipeline_history()
    active=any(r.get('step_key')=='intraday_backfill' and r.get('status') in ('running','starting') for r in existing)
    if st.button('Lancer / reprendre le backfill',type='primary',disabled=active,key='intraday_launch'):
        record=start_managed_run(step_key='intraday_backfill',step_label=f'Backfill intraday {provider} — US',command=command)
        st.session_state['intraday_run_id']=record.run_id
        st.session_state['intraday_plan_id']=plan['plan_id']
        st.rerun()
    if active:st.warning('Un backfill intraday est déjà actif. Attendez ou arrêtez-le avant un nouveau lancement.')
    runs=[r for r in existing if r.get('step_key')=='intraday_backfill']
    if runs:
        ids=[r['run_id'] for r in runs]
        current=st.session_state.get('intraday_run_id')
        selected=st.selectbox('Exécution à suivre',ids,index=ids.index(current) if current in ids else 0,
            format_func=lambda rid:f"{rid} — {next(r['status'] for r in runs if r['run_id']==rid)}",key='intraday_history')
        record=next(r for r in runs if r['run_id']==selected)
        if '--expected-plan-id' in record['command']:
            cmd=record['command']
            plan_id=cmd[cmd.index('--expected-plan-id')+1]
        elif selected==current:
            plan_id=st.session_state.get('intraday_plan_id',plan['plan_id'])
        else:
            cmd=record['command']
            try:
                def value(flag):return cmd[cmd.index(flag)+1]
                old=build_plan(date.fromisoformat(value('--start-date')),date.fromisoformat(value('--end-date')),
                    value('--symbol-source'),value('--interval'),int(value('--chunk-days')))
                plan_id=old['plan_id']
            except (ValueError,FileNotFoundError):plan_id=plan['plan_id']
        _progress(selected,plan_id)
    st.caption('Un arrêt laisse les tranches déjà commitées. Le quota/les droits bloquent le passage avec un message explicite ; relancez le même plan pour reprendre.')


run_page_if_standalone(__name__,render)
