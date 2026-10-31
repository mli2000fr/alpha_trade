"""T5.6 — complete, encrypted backup and portable restore."""
from datetime import datetime,timezone
from pathlib import Path

import streamlit as st

from ihm.services import migration_runner as jobs
from service.migration import environment,inventory
from service.migration.mysql import Connection,DATABASES
from dataclasses import asdict
from ihm.components.migration_command import render_restore_command


def _launch(request,parent=None):
    try:
        path=jobs.start_job(request,job_parent=parent)
        st.session_state['t56_job']=path
        st.session_state['t56_follow']=path
        st.session_state['t56_jobs']=list(dict.fromkeys([path,*st.session_state.get('t56_jobs',[])]))[:20]
        st.session_state['t56_clear_secrets']=True
        st.rerun()
    except (ValueError,OSError) as exc:st.error(str(exc))


def render_migration_panel():
    if st.session_state.pop('t56_clear_secrets',False):
        for name in ('t56_password','t56_password_confirm','t56_db_password'):st.session_state[name]=''
    root=jobs.PROJECT_ROOT
    st.subheader('T5.6 — Sauvegarde complète et restauration sur un autre PC')
    st.caption('Trois bases US/FR/CN, code actuel, modèles, configuration, archives et variables d’environnement de l’application. Tous les packages sont chiffrés.')
    st.info('La sauvegarde laisse le PC source fonctionner. Seule la restauration impose de fermer les services et de désactiver les tâches planifiées du PC cible. Rien ne redémarre automatiquement.')
    st.caption('Barres de progression et journal en direct dans l’onglet « Suivi et packages ».')
    password=st.text_input('Mot de passe de sauvegarde (12 caractères minimum)',type='password',key='t56_password')
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
            try:
                entries=inventory.scan(root)
                st.session_state['t56_inventory_result']={
                    'packages':[dict(package=k,fichiers=len(v),octets=sum(f['size'] for f in v)) for k,v in entries.items()],
                    'variables':environment.capture(root,[f['path'] for v in entries.values() for f in v])['variables']}
            except (ValueError,OSError) as exc:st.error(str(exc))
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
        if st.button('Vérifier les packages sans restaurer',key='t56_verify',disabled=not folder or len(password)<12):
            _launch(dict(action='verify',folder=folder,password=password))
        user=st.text_input('Utilisateur MySQL local cible (pour les trois bases)',value='root',key='t56_db_user')
        db_password=st.text_input('Mot de passe MySQL cible',type='password',key='t56_db_password')
        connections={n:asdict(Connection(user=user,password=db_password)) for n in DATABASES}
        context=dict(folder=folder,target=target,user=user,mysqldump=dump,mysql=mysql)
        if st.button('Prévisualiser la restauration',key='t56_plan',disabled=not folder or len(password)<12 or not db_password):
            st.session_state.pop('t56_plan',None)
            st.session_state['t56_plan_context']=context
            _launch(dict(action='plan',folder=folder,target=target,password=password,connections=connections,mysqldump=dump,mysql=mysql))
        job=st.session_state.get('t56_job')
        state=jobs.job_state(job) if job else {}
        plan=state.get('result')
        if plan and 'fingerprint' in plan:
            st.session_state['t56_plan']=plan
        plan=st.session_state.get('t56_plan')
        if plan and context==st.session_state.get('t56_plan_context'):
            st.json(plan)
            st.warning('La restauration remplace les trois bases et les fichiers gérés, après sauvegarde chiffrée de l’existant. Aucun mélange avec les anciens modèles. Un .venv existant doit être renommé manuellement ; il est préservé.')
            ready=st.checkbox('Je confirme le projet cible et le remplacement des trois bases après sauvegarde de l’existant',key='t56_replace')
            rebuild=st.checkbox('Recréer un nouvel environnement Python avec les versions sauvegardées',value=True,key='t56_rebuild')
            if st.button('Restaurer après fermeture des services du PC cible',key='t56_restore',disabled=not ready or len(password)<12 or not db_password):
                stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                report=Path(folder).resolve()/'journaux'/('restauration-'+stamp)
                _launch(dict(action='restore',folder=folder,target=target,password=password,connections=connections,
                    mysqldump=dump,mysql=mysql,approved_plan=plan['fingerprint'],report_dir=str(report),rebuild_venv=rebuild),
                    parent=Path(folder).resolve()/'journaux'/'jobs')
        st.caption('Le worker attend jusqu’à 15 minutes la fermeture des processus du PC cible. Le PC source n’est jamais arrêté. Les journaux et verrous métier sont conservés pour éviter les doublons d’ordres.')
    with follow_tab:
        if st.button('Actualiser le suivi',key='t56_refresh'):st.rerun()
        paths=[p for p in st.session_state.get('t56_jobs',[]) if (Path(p)/'progress.json').is_file()]
        stored=root/'backups'/'migration_jobs'
        if stored.is_dir():paths=list(dict.fromkeys([*paths,*[str(p) for p in sorted(stored.iterdir(),reverse=True) if p.is_dir()]]))[:30]
        if paths:
            from ihm.components.migration_progress import render_migration_progress
            render_migration_progress(paths)
        st.dataframe(jobs.catalog(root/'backups'/'migrations'),hide_index=True)
        from ihm.components.migration_cleanup import render_migration_cleanup
        render_migration_cleanup(root)
    if (root/'.alpha_trade_restore_pending.json').exists():
        st.warning('Ce projet a été restauré : vérifier les comptes, chemins, données et ordres avant une reprise manuelle. Ce message est informatif et ne bloque pas le moteur opérationnel.')
