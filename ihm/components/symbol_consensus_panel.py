"""Documented EODHD values in the US symbol dialog. Local SQL reads only."""
from datetime import date

import pandas as pd
import streamlit as st

from database.connection import get_sqlalchemy_engine
from ihm.services.consensus_review import (
    GROUPS, change_rows, field_rows, load_period_history, load_snapshot, load_snapshot_days,
)


@st.cache_data(ttl=60,show_spinner=False)
def _days(symbol,end_date):
    return load_snapshot_days(get_sqlalchemy_engine(),symbol,end_date)


@st.cache_data(ttl=60,show_spinner=False)
def _snapshot(symbol,end_date,snapshot_day):
    return load_snapshot(get_sqlalchemy_engine(),symbol,end_date,snapshot_day)


@st.cache_data(ttl=60,show_spinner=False)
def _history(symbol,end_date,snapshot_day,fiscal_end,horizon):
    return load_period_history(get_sqlalchemy_engine(),symbol,end_date,snapshot_day,fiscal_end,horizon)


def _default_period(rows,end_date):
    day=date.fromisoformat(str(end_date))
    for horizon in ('0q','+1q','0y','+1y'):
        future=[(date.fromisoformat(str(r['fiscal_period_end'])),i) for i,r in enumerate(rows)
                if r['horizon_raw']==horizon and date.fromisoformat(str(r['fiscal_period_end']))>=day]
        if future:
            return min(future)[1]
    return 0


def render_symbol_consensus_panel(symbol,end_date):
    with st.expander('Consensus analystes EODHD — valeurs et explications',expanded=False):
        st.caption('Source locale : alpha_trade.stock_analyst_consensus_eodhd_history. '
            'Aucun appel EODHD/Yahoo/LLM, aucun ordre ni modification des données.')
        st.info('Une ligne = un titre, une date de collecte et une période fiscale/horizon. '
            'Le consensus décrit les attentes des analystes : ce n’est ni un objectif de cours, '
            'ni une prédiction LONG/SHORT de notre Oracle.')
        st.caption(f'Consultation documentaire bornée à la fin du {end_date} à New York '
            '(réception UTC strictement antérieure au lendemain à 00 h New York). '
            'Ce n’est pas le snapshot exact utilisé par le LLM, ni une preuve de disponibilité '
            'avant l’heure précise de sa décision. Au plus 90 dates de collecte sont proposées.')
        try:
            days=_days(symbol,end_date)
        except Exception:
            st.warning('Consensus local indisponible : table absente ou lecture impossible. '
                       'Le graphique reste indépendant ; aucun téléchargement de remplacement.')
            return
        if not days:
            st.info('Aucun consensus EODHD reçu pour ce titre avant cette borne. '
                    'Cela ne signifie ni zéro analyste, ni avis neutre.')
            return
        selected=st.selectbox('Date de collecte du consensus — New York',days,
            key=f'consensus_day_{symbol}_{end_date}')
        try:
            rows=_snapshot(symbol,end_date,selected)
        except Exception:
            st.warning('Impossible de lire cette photographie du consensus. Aucun secret de connexion n’est affiché.')
            return
        if not rows:
            st.info('Aucune période fiscale disponible pour cette collecte.')
            return
        index=st.selectbox('Période fiscale et horizon fournisseur',list(range(len(rows))),
            index=_default_period(rows,end_date),
            format_func=lambda i:f"{rows[i]['fiscal_period_end']} · {rows[i]['horizon_raw']}",
            key=f'consensus_period_{symbol}_{end_date}_{selected}')
        row=rows[index]
        st.warning('Les valeurs et leurs qualifications sont affichées telles qu’enregistrées. '
            'RESEARCH_ONLY ou qualification « Non » ne constitue pas une donnée validée pour ML/trading. '
            'Une ancienne date fiscale ne prouve pas un consensus connu à cette date. '
            'Valeur absente = inconnue, jamais zéro. Ne pas supposer une devise ou une échelle.')
        for group in GROUPS:
            st.markdown(f'**{group}**')
            # Static tables wrap long explanations instead of truncating them
            # inside a grid cell. Historical observations remain sortable below.
            st.table(pd.DataFrame(field_rows(row,group)).set_index('Indicateur'))
        st.markdown('**Écarts descriptifs des références EPS**')
        st.dataframe(pd.DataFrame(change_rows(row)),hide_index=True,width='stretch')
        st.caption('Ces références J−7/30/60/90 sont livrées dans la réponse sélectionnée, '
            'pas des collectes archivées ces jours-là. Les compteurs de révisions 7/30 jours '
            'se chevauchent : ne pas les additionner. Une amélioration ne garantit pas une hausse du cours.')
        st.markdown('**Nos observations réellement collectées — même période et même horizon**')
        try:
            history=_history(symbol,end_date,selected,row['fiscal_period_end'],row['horizon_raw'])
        except Exception:
            st.warning('Historique des observations indisponible ; les valeurs ci-dessus restent consultables.')
            return
        st.caption('Au plus 30 observations, sans jour inventé ni mélange de périodes fiscales. '
            'Une seule première observation par clé/jour est conservée. '
            'Les champs d’unités restent à qualifier avant de comparer leurs montants.')
        st.dataframe(pd.DataFrame(history).rename(columns={
            'snapshot_date':'Collecte (New York)','available_at':'Réception (UTC)',
            'eps_current':'EPS courant','eps_avg':'EPS moyen','revenue_avg':'Revenus moyens',
            'revisions_up_30d':'Révisions ↑ 30 j','revisions_down_30d':'Révisions ↓ 30 j'}),
            hide_index=True,width='stretch')
