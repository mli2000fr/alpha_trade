"""UI for path amplitude, with SQL inference distinct from training-fold OOF."""
import pandas as pd
import streamlit as st

from ihm.services.oracle_path_diagnostics import period_rows,top_k_rows


def render_periods(view,sql):
    rows=period_rows(view,sql)
    horizon=(view.get('protocol') or {}).get('horizon',20)
    st.caption(f'Oracle parcours H{horizon} : prédictions SQL et tests OOF du training sont deux sources distinctes, jamais fusionnées.')
    if rows:st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if not (sql.get('coverage') or {}).get('n_rows') and not sql.get('errors'):
        st.info("Aucune prédiction SQL pour ce batch : cela n'efface pas ses tests OOF. Lancer ML Predict pour alimenter les scores servis.")
    for message in sql.get('errors',[]):st.warning(message)
    n=int((sql.get('coverage') or {}).get('n_rows') or 0)
    lineage=sql.get('matching_lineage_rows')
    if n and lineage is not None:
        if lineage==n:st.success(f'Filiation parcours cohérente sur {n:,} prédictions SQL (fold, poids, profil, cible et disponibilité).')
        else:st.error(f'Filiation parcours incomplète ou incohérente : {lineage:,}/{n:,} lignes correspondent au contrat. Ne pas les considérer servables.')
    if not rows:st.info('Aucune période vérifiable disponible ; consulter les erreurs ou la progression du training.')


def _number(value,fmt='.3f'):
    try:return format(float(value),fmt) if pd.notna(value) else '—'
    except (ValueError,TypeError):return '—'


def render_directional_metrics(view,summary):
    rows=summary.get('metrics_rows') or []
    st.markdown('**Mesures par titre — LONG / SHORT**')
    if not rows:
        progress=summary.get('diagnostic_progress') or {}
        if progress.get('status')=='RUNNING':
            done,total=progress.get('completed',0),progress.get('total',0)
            st.info(f'Diagnostics en cours : {done:,}/{total:,} titres. Aucun réentraînement ni backtest de portefeuille.')
        else:st.info('Diagnostics non calculés pour cet ancien batch. Les prochains entraînements les enregistrent automatiquement.')
        return
    frame=pd.DataFrame(rows)
    labels={'oos':'Test hors échantillon','oos_nonoverlap':'Test hors échantillon — fenêtres sans chevauchement',
        'calibration':'Calibration — non indépendante','train':'Entraînement — non indépendant'}
    stage=st.selectbox('Échantillon des métriques per-symbol',list(labels),format_func=labels.get,
        key=f"diag_path_metric_stage_{view['batch_id']}")
    available=frame[frame['Échantillon'].eq(stage)&frame.Observations.gt(0)]
    years=sorted(frame['Année d’utilisation'].unique().tolist(),reverse=True)
    default=int(available['Année d’utilisation'].max()) if len(available) else years[0]
    left,right=st.columns(2)
    year=left.selectbox('Année évaluée',years,index=years.index(default),
        key=f"diag_path_metric_year_{view['batch_id']}_{stage}")
    side=right.selectbox('Direction évaluée',['LONG','SHORT'],key=f"diag_path_metric_side_{view['batch_id']}")
    selected=frame[frame['Échantillon'].eq(stage)&frame['Année d’utilisation'].eq(year)&frame.Direction.eq(side)]
    usable=selected[selected.Observations.gt(0)]
    if usable.empty:
        st.info(f'Aucun résultat arrivé à maturité disponible pour le test {year} dans les données de cet entraînement. '
            'Un modèle entraîné pour cette année peut exister sans avoir encore été évalué dessus.')
    else:
        cols=st.columns(3)
        cols[0].metric('Titres avec observations évaluées',len(usable))
        cols[1].metric('AUC médiane par titre',_number(usable.AUC.median()))
        cols[2].metric('Exactitude médiane — seuil 0,5',_number(usable['Exactitude — seuil 0,5'].median(),'.1%'))
        st.caption(f"AUC calculable pour {int(usable.AUC.notna().sum()):,}/{len(usable):,} titres évalués ; "
            'une seule classe ne permet pas de calculer une AUC.')
        st.dataframe(selected.style.format({'AUC':'{:.3f}','Exactitude — seuil 0,5':'{:.1%}',
            'Exactitude équilibrée':'{:.1%}','Précision des scores ≥ 0,5':'{:.1%}',
            'Fréquence de gains dans les labels':'{:.1%}','Brier':'{:.3f}'},na_rep='—'),
            use_container_width=True,hide_index=True)
    if stage in ('calibration','train'):
        st.warning('Ce jeu sert à entraîner ou calibrer le modèle : ses résultats ne sont pas un test indépendant.')
    contract=summary.get('contract') or {}
    horizon=int(contract.get('horizon_sessions',10));sl=float(contract.get('stop_loss_pct',.05))
    st.caption('AUC : qualité du classement des labels gagnants/perdants ; « — » si une seule classe ou aucune observation. '
        f'Exactitude : classe prédite avec un seuil de 0,5. Labels : résultat net H{horizon}, SL{100*sl:g} %, '
        f'sans TP/trailing, sortie open{horizon+1}. '
        'Ces mesures ne sont pas le taux de trades gagnants du portefeuille Winner. '
        'Les fenêtres quotidiennes se chevauchent ; la variante sans chevauchement utilise une phase fixe de 11 séances.')
    if summary.get('benchmark_reconstructed_from_SQL'):
        st.caption('Diagnostic reconstitué depuis les barres archivées et les poids d’origine ; '
            'le benchmark SPY a été relu en SQL et figé pour ce diagnostic. Son état exact au jour du training ancien n’était pas archivé.')
    st.download_button('Télécharger les métriques per-symbol (CSV)',frame.to_csv(index=False).encode('utf-8-sig'),
        file_name=f"{view['batch_id']}_per_symbol_metrics.csv",mime='text/csv',key=f"diag_path_metrics_csv_{view['batch_id']}")


def render_directional(view):
    summary=view.get('directional')
    if not summary:return
    st.subheader('🧩 Modèles per-symbol LONG / SHORT')
    st.success(f"{summary['models']:,} modèles annuels par titre présents et vérifiés, "
        f"pour un univers de {summary['universe_size']:,} titres.")
    left,right=st.columns(2)
    left.metric('Modèles LONG entraînés',f"{summary['long_models']:,}")
    right.metric('Modèles SHORT entraînés',f"{summary['short_models']:,}")
    st.caption(f"Chaque modèle est propre à un titre, une direction et une année d’utilisation ; "
        f"{summary['features']} variables. Le compteur de batch « 1 terminé » désigne le bundle complet, pas un seul titre.")
    st.dataframe(pd.DataFrame(summary['coverage']),use_container_width=True,hide_index=True)
    st.caption('Une année sans modèle signifie que les critères minimums de données ne sont pas satisfaits. '
        'Les absences ne sont pas remplacées par un score neutre. Les modèles SHORT sont archivés ; '
        'la sélection du bundle utilise uniquement LONG.')
    with st.expander('Détails des modèles par titre et périodes d’entraînement',expanded=False):
        details=pd.DataFrame(summary['details'])
        if not details.empty:
            years=sorted(details['Année d’utilisation'].unique().tolist(),reverse=True)
            year=st.selectbox('Année des modèles per-symbol',years,key=f"diag_path_year_{view['batch_id']}")
            side=st.selectbox('Branche per-symbol',['LONG','SHORT'],key=f"diag_path_side_{view['batch_id']}")
            chosen=details[(details['Année d’utilisation']==year)&(details['Direction']==side)]
            st.dataframe(chosen,use_container_width=True,hide_index=True)
            st.download_button('Télécharger le détail des modèles per-symbol (CSV)',
                details.to_csv(index=False).encode('utf-8-sig'),file_name=f"{view['batch_id']}_per_symbol.csv",
                mime='text/csv',key=f"diag_path_models_csv_{view['batch_id']}")
        else:st.info('Aucun modèle per-symbol entraîné dans le manifeste.')
    with st.expander('Modèles non entraînés : années, titres et motifs',expanded=False):
        omissions=pd.DataFrame(summary['omissions'])
        if not omissions.empty:
            counts=omissions.groupby(['Année d’utilisation','Direction','Motif']).size().reset_index(name='Nombre')
            st.dataframe(counts,use_container_width=True,hide_index=True)
            st.download_button('Télécharger les modèles non entraînés (CSV)',
                omissions.to_csv(index=False).encode('utf-8-sig'),file_name=f"{view['batch_id']}_per_symbol_absents.csv",
                mime='text/csv',key=f"diag_path_skipped_csv_{view['batch_id']}")
        else:st.info('Aucun modèle ignoré.')
    render_directional_metrics(view,summary)


def render_model(view,sql):
    horizon=(view.get('protocol') or {}).get('horizon',20)
    st.subheader(f'🔮 Oracle Extreme parcours H{horizon} — amplitude')
    st.info(f'Cible : véritable TOP20 % de l’amplitude absolue maximale entre J+1 et J+{horizon}, depuis le close ajusté J. '
        'Le modèle ne prédit ni LONG/SHORT, ni le rendement au seul vingtième jour, ni un gain exécutable.')
    for message in view.get('errors',[]):st.error('Artefacts parcours non qualifiés : '+message)
    for message in view.get('warnings',[]):st.warning(message)
    if not view.get('ready'):
        progress=view.get('progress') or {}
        if progress:
            st.caption(f"Training : {progress.get('status','—')} · phase {progress.get('phase','—')} · {progress.get('item','')}")
            current,total=progress.get('completed'),progress.get('total')
            if isinstance(current,(int,float)) and isinstance(total,(int,float)) and total>0:
                st.progress(min(1.,max(0.,current/total)))
            if progress.get('error'):st.error(str(progress['error']))
        render_periods(view,sql)
        return
    report=view['report'];overall=report['overall'];protocol=view['protocol']
    if protocol.get('training_config',{}).get('oracle_path_directional_enabled'):
        contract=protocol['directional_contract']
        st.info(f'Bundle parcours : {report.get("directional_models",0)} modèles annuels LONG/SHORT par titre. '
                f'Sélection enregistrée : TOP{contract["oracle_top_n"]} Oracle → TOP{contract["selected_n"]} LONG → risque → Winner. '
                'Les métriques ci-dessous concernent l’amplitude Oracle, pas la rentabilité des branches par titre.')
    columns=st.columns(4)
    columns[0].metric('AUC amplitude — OOF',_number(overall.get('auc')))
    columns[1].metric('Précision 10 premiers titres',_number(overall.get('precision_top_10_titles'),'.1%'))
    columns[2].metric('Précision TOP20 % prédit',_number(overall.get('precision_at_20pct'),'.1%'))
    columns[3].metric('Folds / features',f"{report['n_folds']} / {report['n_features']}")
    st.caption('Précision = proportion appartenant au véritable TOP20 % des amplitudes réalisées ; '
        'ce n’est ni un taux de trades gagnants ni une précision directionnelle. Métriques lues dans le rapport de training.')
    backend=report.get('training_backend') or protocol.get('training_backend') or protocol.get('backend','—')
    st.caption(f"Choix d’algorithme : {backend} · sélection : {report.get('selection',protocol.get('champion_selection','déclarée au training'))}.")
    st.markdown('**Les 10 / 20 / 50 premiers titres — pas des pourcentages d’univers**')
    table=pd.DataFrame(top_k_rows(report))
    st.dataframe(table.style.format({'Précision véritable TOP20 %':'{:.1%}',
        'Amplitude maximale moyenne (%)':'{:.2f}'},na_rep='—'),use_container_width=True,hide_index=True)
    st.caption('L’amplitude affichée est un maximum connu a posteriori, hausse ou baisse. Ce n’est pas un PnL ou un TP réalisable.')
    render_periods(view,sql)
    with st.expander('Folds test hors échantillon et algorithmes',expanded=False):
        folds=pd.DataFrame(view['fold_rows'])
        st.dataframe(folds.style.format({'AUC':'{:.3f}','Précision 10 titres':'{:.1%}',
            'Précision 20 titres':'{:.1%}','Précision 50 titres':'{:.1%}',
            'Amplitude 10 titres (%)':'{:.2f}'},na_rep='—'),use_container_width=True,hide_index=True)
        st.caption('Les labels d’entraînement et de validation doivent être disponibles avant les périodes suivantes. '
            'Les fichiers OOF de chaque fold et les poids ont été vérifiés ; aucun recalcul de labels n’est lancé par cette page.')
    comparisons=report.get('comparison_oof') or {}
    if len(comparisons)>1:
        with st.expander('Comparaison LightGBM / CatBoost hors échantillon',expanded=False):
            values=[{'Algorithme':name,'AUC':metrics.get('auc'),
                'Précision 10 titres':metrics.get('precision_top_10_titles'),
                'Amplitude 10 titres (%)':metrics.get('mean_path_amplitude_top_10_titles_pct')}
                for name,metrics in comparisons.items()]
            st.dataframe(pd.DataFrame(values).style.format({'AUC':'{:.3f}','Précision 10 titres':'{:.1%}',
                'Amplitude 10 titres (%)':'{:.2f}'},na_rep='—'),use_container_width=True,hide_index=True)
            st.caption('Comparaison diagnostique seulement : ces résultats de test ne rechoisissent pas le champion sélectionné sur validation.')
    with st.expander('Qualité et couverture des trajectoires',expanded=False):
        quality=report.get('quality') or {}
        st.json(quality)
        st.warning('Univers statique : biais de survivance possible. Prix ajustés actuels : révisions PIT non certifiées. '
            'Ces tests OOF n’évaluent pas automatiquement les nouvelles prédictions SQL.')
    with st.expander('Profil de features',expanded=False):
        st.dataframe(pd.DataFrame({'Feature':view['profile']['feature_columns']}),use_container_width=True,hide_index=True)
    render_directional(view)
    st.caption('Les labels future_return / oracle_extreme10 de la table de scores restent NULL pour ce modèle. '
        'Les anciens diagnostics D1/D10 et le constructeur de labels terminaux ne sont pas appliqués à sa cible parcours.')
