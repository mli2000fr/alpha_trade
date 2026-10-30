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
    st.caption('Les labels future_return / oracle_extreme10 de la table de scores restent NULL pour ce modèle. '
        'Les anciens diagnostics D1/D10 et le constructeur de labels terminaux ne sont pas appliqués à sa cible parcours.')
