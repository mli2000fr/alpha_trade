"""Human-readable migration progress, auto refreshed without rerendering forms."""
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from ihm.services import migration_runner as jobs
from service.migration.tracking import LABELS


def amount(value):
    value=float(value or 0)
    for unit in ('o','Kio','Mio','Gio','Tio'):
        if value<1024 or unit=='Tio':return f'{value:,.1f} {unit}'
        value/=1024


def duration(seconds):
    seconds=max(0,int(seconds));hours,remainder=divmod(seconds,3600);minutes,seconds=divmod(remainder,60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def elapsed(tracking,active):
    if active:
        try:return (datetime.now(timezone.utc)-datetime.fromisoformat(tracking['started_at'])).total_seconds()
        except (KeyError,ValueError):pass
    return tracking.get('elapsed_seconds',0)


@st.fragment(run_every=2)
def render_migration_progress(paths):
    if not paths:
        st.caption('Aucune opération à suivre.');return
    selected=st.selectbox('Opération à suivre',paths,key='t56_follow')
    state=jobs.job_state(selected);tracking=state.get('tracking') or {}
    worker=state.get('progress') or {};status=worker.get('status')
    if not tracking:
        legacy=state.get('operation_progress') or worker
        phase=legacy.get('phase') or legacy.get('status')
        tracking=dict(legacy,label=LABELS.get(phase,'Opération en cours'),percent=100 if status=='FINISHED' else 0)
    active=status in ('STARTING','STARTED','WAITING_FOR_TARGET_STOP','BUILDING_PYTHON')
    if state.get('worker_ended_without_result'):
        active=False;st.error('Le processus ne fonctionne plus et aucun résultat final n’a été reçu. Vérifier les derniers événements avant toute reprise.')
    label=tracking.get('label') or 'Préparation du suivi'
    percent=max(0.,min(100.,float(tracking.get('percent',0))))
    st.progress(percent/100,text=f'{percent:.0f} % — {label}')
    st.caption('Progression globale estimée par étapes ; elle ne représente pas une estimation du temps restant. Actualisation automatique toutes les 2 secondes.')
    a,b,c=st.columns(3)
    a.metric('Temps écoulé',duration(elapsed(tracking,active)))
    b.metric('Base / package',tracking.get('database') or tracking.get('package') or '—')
    transferred=tracking.get('processed_bytes')
    total=tracking.get('total_bytes')
    c.metric('Volume de l’étape',amount(transferred)+(f' / {amount(total)}' if total else '') if transferred is not None else '—')
    if total and transferred is not None:
        st.progress(min(1.,transferred/total),text='Volume traité dans cette étape')
    if tracking.get('files_total'):
        what='tables' if tracking.get('unit')=='tables' else 'fichiers'
        st.caption(f"{tracking.get('files_done',0):,} / {tracking['files_total']:,} {what}")
    if tracking.get('item'):st.caption('En cours : '+tracking['item'])
    if tracking.get('unit') in ('octets SQL','octets compressés'):st.caption('Compteur : '+tracking['unit'])
    if tracking.get('updated_at'):
        try:
            last=datetime.fromisoformat(tracking['updated_at']).astimezone(ZoneInfo('Europe/Paris')).strftime('%H:%M:%S')
            st.caption('Dernier avancement enregistré à '+last+' (Paris).')
        except ValueError:pass
    if status=='FAILED':st.error(worker.get('message') or 'Opération échouée. Consulter les derniers événements et le rapport.')
    elif status=='CANCELED':st.warning('Opération interrompue. Consulter le journal pour le résultat du retour arrière éventuel.')
    elif status=='FINISHED':
        if tracking.get('warning'):st.warning('Données restaurées ; la construction de l’environnement Python reste à vérifier.')
        else:st.success(label)
    result=state.get('result') or {}
    if result.get('folder') and result.get('status')=='COMPLETE':
        from ihm.components.migration_command import render_restore_command
        render_restore_command(result['folder'])
    lines=[]
    for event in state.get('events',[]):
        try:stamp=datetime.fromisoformat(event['updated_at']).astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m %H:%M:%S')
        except (KeyError,ValueError):stamp='—'
        lines.append(stamp+' | '+event.get('message',''))
    st.caption('Journal des étapes — horaires de Paris, dernières lignes')
    text='\n'.join(lines) or 'Le journal sera disponible dès le démarrage du worker.'
    with st.container(height=280):st.code(text,language=None)
    st.download_button('Télécharger les dernières lignes du journal',text,file_name='migration-journal.txt',mime='text/plain',key='t56_download_log')
    st.caption('Journal complet : '+str(Path(selected)/'events.jsonl'))
    with st.expander('Détails techniques et rapport'):
        st.json({k:v for k,v in state.items() if k!='events'})
    if active:
        if st.button('Demander l’arrêt à un point sûr',key='t56_cancel'):
            (Path(selected)/'cancel.request').touch();st.info('Arrêt demandé ; les services du PC source restent actifs.')
    if selected==st.session_state.get('t56_job') and 'fingerprint' in result and st.session_state.get('t56_plan')!=result:
        st.session_state['t56_plan']=result;st.rerun()
