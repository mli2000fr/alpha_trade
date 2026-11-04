"""T5.6 — complete, encrypted backup and portable restore."""
from datetime import datetime,timezone
import json
from pathlib import Path

import streamlit as st

from ihm.services import migration_runner as jobs
from service.migration.mysql import Connection,DATABASES
from dataclasses import asdict
from ihm.components.migration_command import render_restore_command


def _launch(request,parent=None):
    try:
        path=jobs.start_job(request,job_parent=parent)
        st.session_state['t56_job']=path
        st.session_state['t56_follow']=path
        st.session_state['t56_jobs']=list(dict.fromkeys([path,*st.session_state.get('t56_jobs',[])]))[:20]
        if request['action']=='inventory':
            st.session_state['t56_inventory_job']=path
            st.session_state.pop('t56_inventory_result',None)
        elif request['action'] in ('export','restore','restore_files','recover'):
            st.session_state['t56_clear_secrets']=True
        if request['action']=='plan':
            st.session_state['t56_plan_job']=path
        st.rerun()
    except (ValueError,OSError) as exc:st.error(str(exc))


def render_migration_panel():
    # Older versions used this widget key for the resulting plan as well.
    # Discard that stale value before Streamlit creates the button.
    if isinstance(st.session_state.get('t56_plan'),dict):
        st.session_state.pop('t56_plan',None)
    if st.session_state.pop('t56_clear_secrets',False):
        for name in ('t56_password','t56_password_confirm','t56_db_password'):st.session_state[name]=''
    root=jobs.PROJECT_ROOT
    recovered_plan=jobs.latest_completed_plan()
    if recovered_plan:
        _,saved,_=recovered_plan
        for key,field in (('t56_folder','folder'),('t56_target','target'),
                          ('t56_db_user','user'),('t56_dump','mysqldump'),('t56_mysql','mysql')):
            st.session_state.setdefault(key,saved.get(field) or '')
    st.subheader('T5.6 — Sauvegarde complète et restauration sur un autre PC')
    st.caption('Trois bases US/FR/CN, code actuel, modèles, configuration, archives et variables d’environnement de l’application. Tous les packages sont chiffrés.')
    st.info('La sauvegarde laisse le PC source fonctionner. La restauration attend uniquement la fin des batchs actifs du PC cible ; l’IHM peut rester ouverte. Rien ne redémarre automatiquement.')
    st.caption('Barres de progression et journal en direct dans l’onglet « Suivi et packages ».')
    password=st.text_input('Mot de passe des packages — sauvegarde ou restauration (12 caractères minimum)',
        type='password',key='t56_password',help='Pour restaurer, saisir le mot de passe utilisé lors de la création de cette sauvegarde. Il est différent du mot de passe MySQL cible.')
    export_tab,restore_tab,follow_tab=st.tabs(['Créer une sauvegarde','Vérifier / restaurer','Suivi et packages'])
    with export_tab:
        base=root/'backups'/'migrations'
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        output=st.text_input('Nouveau répertoire de sauvegarde',str(base/('alpha-trade-'+stamp)),key='t56_output')
        render_restore_command(output,pending=True)
        confirm=st.text_input('Confirmer le mot de passe',type='password',key='t56_password_confirm')
        dump=st.text_input('Client mysqldump.exe',r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe',key='t56_dump')
        mysql=st.text_input('Client mysql.exe',r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe',key='t56_mysql')
        st.caption('Sauvegarde à chaud : une transaction par base. Les bases et fichiers ne constituent pas un instantané global unique. Un fichier modifié pendant sa lecture peut faire échouer la sauvegarde, sans interrompre le travail du PC source.')
        if st.button('Inventorier les fichiers et les variables',key='t56_inventory'):
            _launch(dict(action='inventory',root=str(root)))
        inventory_job=st.session_state.get('t56_inventory_job')
        if inventory_job and (Path(inventory_job)/'progress.json').is_file():
            from ihm.components.migration_inventory import render_inventory_result
            render_inventory_result(inventory_job)
        result=st.session_state.get('t56_inventory_result')
        if result:
            st.dataframe(result['packages'],hide_index=True)
            with st.expander('Variables : noms, présence et origine (aucune valeur affichée)'):
                st.dataframe(result['variables'],hide_index=True)
        if st.button('Créer les packages chiffrés',key='t56_export',disabled=len(password)<12 or password!=confirm):
            _launch(dict(action='export',root=str(root),output=output,password=password,mysqldump=dump,mysql=mysql))
    with restore_tab:
        folder=st.text_input('Répertoire contenant manifest.json',key='t56_folder')
        render_restore_command(folder)
        target=st.text_input('Projet sur le PC cible',r'C:\AlphaTrade',key='t56_target')
        st.caption('Sur un PC vierge, copier le répertoire complet puis lancer restaurer.ps1. Python et MySQL doivent être installés. Les versions requises sont inscrites dans le manifeste.')
        user=st.text_input('Utilisateur MySQL local cible (pour les trois bases)',value='root',key='t56_db_user')
        db_password=st.text_input('Mot de passe MySQL cible',type='password',key='t56_db_password')
        connections={n:asdict(Connection(user=user,password=db_password)) for n in DATABASES}
        # All input widgets must render before an action can rerun the page;
        # otherwise Streamlit cleans up a later widget's entered password.
        if st.button('Vérifier les packages sans restaurer',key='t56_verify',disabled=not folder or len(password)<12):
            _launch(dict(action='verify',folder=folder,password=password))
        context=dict(folder=folder,target=target,user=user,mysqldump=dump,mysql=mysql)
        missing=restore_preview_requirements(folder,target,password,user,db_password)
        if missing:
            st.info('Pour prévisualiser, renseigner : '+ ' ; '.join(missing)+'.')
        st.caption('La prévisualisation vérifie les packages et le PC cible sans restaurer ni remplacer de données.')
        if st.button('Prévisualiser la restauration',key='t56_plan'):
            if missing:
                st.error('Prévisualisation non lancée : '+ ' ; '.join(missing)+'.')
            else:
                st.session_state.pop('t56_plan_result',None)
                st.session_state.pop('t56_plan_job',None)
                st.session_state['t56_replace']=False
                st.session_state['t56_plan_context']=context
                _launch(dict(action='plan',folder=folder,target=target,password=password,connections=connections,mysqldump=dump,mysql=mysql))
        if not st.session_state.get('t56_plan_job'):
            recovered=jobs.completed_plan_for(context)
            if recovered:
                st.session_state['t56_plan_job'],st.session_state['t56_plan_result']=recovered
                st.session_state['t56_plan_context']=context
        job=st.session_state.get('t56_plan_job')
        state=jobs.job_state(job) if job else {}
        plan=state.get('result')
        if isinstance(plan,dict) and 'fingerprint' in plan:
            st.session_state['t56_plan_result']=plan
        plan=st.session_state.get('t56_plan_result')
        if plan and context==st.session_state.get('t56_plan_context'):
            st.json(plan)
            st.warning('La restauration remplace les trois bases, puis installe les fichiers gérés. Après validation des bases, un échec des fichiers permet de reprendre uniquement leur installation. Un .venv existant doit être renommé manuellement ; il est préservé.')
            ready=st.checkbox('Je confirme le projet cible et le remplacement des trois bases',key='t56_replace')
            rebuild=st.checkbox('Recréer un nouvel environnement Python avec les versions sauvegardées',value=True,key='t56_rebuild')
            skip_existing_backup=st.checkbox('Sauter la sauvegarde de l’existant avant restauration',
                value=False,key='t56_skip_existing_backup')
            if skip_existing_backup:
                st.error('Sans sauvegarde de l’existant, un échec pendant la restauration SQL ne pourra pas revenir automatiquement aux anciennes bases. Après validation SQL, une erreur de fichiers conservera les bases restaurées.')
            restore_missing=[]
            if not ready:restore_missing.append('cocher la confirmation du remplacement des trois bases')
            if len(password)<12:restore_missing.append('ressaisir le mot de passe des packages en haut de la page')
            if not db_password:restore_missing.append('ressaisir le mot de passe MySQL cible')
            if restore_missing:
                st.info('Pour activer « Restaurer », '+ ' ; '.join(restore_missing)+'.')
            if st.button('Restaurer après fermeture des services du PC cible',key='t56_restore',disabled=bool(restore_missing)):
                stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                report=Path(folder).resolve()/'journaux'/('restauration-'+stamp)
                _launch(dict(action='restore',folder=folder,target=target,password=password,connections=connections,
                    mysqldump=dump,mysql=mysql,approved_plan=plan['fingerprint'],report_dir=str(report),
                    rebuild_venv=rebuild,skip_existing_backup=skip_existing_backup),
                    parent=Path(folder).resolve()/'journaux'/'jobs')
        pending_report=jobs.latest_files_pending(folder,target)
        if pending_report:
            st.info('Les trois bases sont validées. L’installation des fichiers peut être relancée sans réimporter les bases.')
            st.caption('Rapport à reprendre : '+pending_report)
            resume_rebuild=st.checkbox('Créer l’environnement Python après installation des fichiers',
                value=True,key='t56_resume_rebuild')
            if st.button('Reprendre uniquement les fichiers et modèles',key='t56_restore_files',
                         disabled=bool(missing)):
                _launch(dict(action='restore_files',folder=folder,target=target,password=password,
                    connections=connections,mysqldump=dump,mysql=mysql,report_dir=pending_report,
                    rebuild_venv=resume_rebuild),parent=Path(folder).resolve()/'journaux'/'jobs')
        st.caption('Le worker attend jusqu’à 15 minutes la fin des batchs actifs du PC cible. Le PC source n’est jamais arrêté. Les journaux et verrous métier sont conservés pour éviter les doublons d’ordres.')
    with follow_tab:
        if st.button('Actualiser le suivi',key='t56_refresh'):st.rerun()
        if recovered_plan:
            st.session_state.setdefault('t56_follow_folder',recovered_plan[1]['folder'])
        follow_folder=st.text_input('Dossier de sauvegarde à suivre après rafraîchissement',
            key='t56_follow_folder',help='Dossier contenant manifest.json ; permet de retrouver les jobs déjà lancés.')
        paths=[p for p in st.session_state.get('t56_jobs',[]) if (Path(p)/'progress.json').is_file()]
        paths.extend(jobs.recent_external_jobs())
        if follow_folder.strip():
            external=Path(follow_folder).expanduser()/'journaux'/'jobs'
            if external.is_dir():
                paths.extend(str(p) for p in sorted(external.iterdir(),reverse=True)
                             if p.is_dir() and (p/'progress.json').is_file())
        stored=root/'backups'/'migration_jobs'
        if stored.is_dir():paths=list(dict.fromkeys([*paths,*[str(p) for p in sorted(stored.iterdir(),reverse=True) if p.is_dir()]]))[:30]
        paths=jobs.order_follow_jobs(paths)[:30]
        if paths and st.session_state.get('t56_follow') not in paths:
            st.session_state['t56_follow']=paths[0]
        if paths:
            from ihm.components.migration_progress import render_migration_progress
            render_migration_progress(paths)
        st.dataframe(jobs.catalog(root/'backups'/'migrations'),hide_index=True)
        from ihm.components.migration_cleanup import render_migration_cleanup
        render_migration_cleanup(root)
    pending=root/'.alpha_trade_restore_pending.json'
    if pending.exists():
        try:reason=json.loads(pending.read_text(encoding='utf-8')).get('reason')
        except (OSError,ValueError,AttributeError):reason=None
        if reason=='FILES_PENDING':
            st.warning('Bases restaurées et validées ; l’installation des fichiers reste à reprendre. Ne pas reprendre l’activité avant sa fin.')
        elif reason=='FILES_ROLLBACK_INCOMPLETE':
            st.error('Bases conservées, mais le retour des fichiers est incomplet. Examiner les dossiers du rapport avant toute nouvelle tentative.')
        elif reason=='RESTORE_FAILED_REVIEW_REQUIRED':
            st.error('Restauration interrompue : la base peut être incomplète. Relancer une restauration complète avant toute reprise opérationnelle.')
        else:
            st.warning('Ce projet a été restauré : vérifier les comptes, chemins, données et ordres avant une reprise manuelle. Ce message est informatif et ne bloque pas le moteur opérationnel.')


def restore_preview_requirements(folder,target,password,user,db_password):
    """Explain unmet prerequisites without exposing or persisting credentials."""
    missing=[]
    if not folder.strip():missing.append('le répertoire contenant manifest.json')
    if len(password)<12:missing.append('le mot de passe des packages en haut de la page (12 caractères minimum)')
    if not target.strip():missing.append('le projet sur le PC cible')
    if not user.strip():missing.append('l’utilisateur MySQL cible')
    if not db_password:missing.append('le mot de passe MySQL cible')
    return missing
