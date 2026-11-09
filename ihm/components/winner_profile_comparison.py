"""Show the archived reference, independently of the current form's edits."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT=Path(__file__).resolve().parents[2]
STUDY=PROJECT/'artifacts/research/us_winner_q051_risk_budget/20261109-v1'
BASE=PROJECT/'artifacts/research/us_winner_continuous_q051_q088/20261108-v2'
CHART=STUDY/'charts/q051-temoin-volatilite20-regime-vs-spy-2021-2026.png'


def reference_comparison():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    base=read(BASE/'cases/Q051_050/result/report.json')
    curve=pd.read_csv(BASE/'cases/Q051_050/result/equity-daily.csv',index_col=0)
    equity=curve.iloc[:,0].astype(float)
    base['daily_max_drawdown_pct']=100.*(equity/equity.cummax().clip(lower=4000.)-1).min()
    protected=read(STUDY/'REGIME_VOL20/result/report.json')
    spy=read(STUDY/'spy-benchmark.json')
    rows=[]
    for label,r in [('Q051 témoin',base),('Volatilité 20 % + régime',protected),('SPY',spy)]:
        rows.append({'Courbe':label,'Capital final ($)':round(r['final_equity'],2),
            'Rendement (%)':round(r['return_pct'],2),
            'DD sur clôtures (%)':round(r['daily_max_drawdown_pct'],2),
            'DD intraday (%)':round(r['max_drawdown_pct'],2) if 'max_drawdown_pct' in r else None,
            'Trades clôturés':r.get('closed_lot_trades'),
            'Trades gagnants (%)':round(r['win_pct'],2) if 'win_pct' in r else None})
    return pd.DataFrame(rows),read(BASE/'protocol.json')['annual_models']


@st.dialog('Q051, volatilité 20 % + régime et SPY',width='large')
def show_reference_comparison():
    try:
        table,models=reference_comparison()
        if not CHART.is_file():raise FileNotFoundError(CHART)
    except (OSError,ValueError,KeyError) as exc:
        st.warning(f'Comparaison archivée indisponible sur ce PC : {exc}')
        return
    st.caption('Référence du 01/01/2021 au 01/10/2026 · 4 000 $ initiaux · capital continu, sans remise à zéro annuelle.')
    st.image(str(CHART),width='stretch')
    st.dataframe(table,hide_index=True,width='stretch')
    st.caption('Comparer le DD sur clôtures pour les trois courbes. Le DD intraday SPY n’est pas disponible. '
        'Stratégies : frais et financement inclus. SPY : cours seuls, sans dividendes ni frais. '
        'Couverture 5m incomplète avec protections daily de secours ; résultats exploratoires.')
    with st.expander('Réglages et lecture des trois courbes'):
        st.write('Q051 témoin : TOP10 % Oracle → TOP5 LONG per-symbol, score > 0,50 et AUC de calibration ≥ 0,50. '
            'Entrée directe à l’ouverture J+1, position complète, SL5 %, sans TP, trailing ni renforcement, sortie open11. '
            'Risque 1,25 % par entrée, poids maximal 20 %, 20 positions, minimum 50 $, plafond de risque 1× ; '
            'compte margin de capacité 2×. Frais 8 points de base par opération et financement annuel 6,5 %. '
            'B4/DD15, facteurs, corrélation et limites sectorielles désactivés.')
        st.write('Volatilité 20 % + régime : même base. Covariance des 60 dernières séances connues pour réduire '
            'les nouveaux achats lorsque la volatilité annualisée prévue du portefeuille dépasse 20 %. '
            'Achats autorisés si SPY à J > 98 % de sa moyenne 200 séances. Les titres détenus ne sont pas liquidés par ces règles. '
            'La cible de volatilité ne garantit pas un drawdown maximal de 20 %.')
        st.write('SPY : achat conservé sur toute la période, sans levier, dividendes ni frais. '
            'Les courbes montrent des capitaux valorisés, y compris les positions encore ouvertes.')
        st.caption('Ces résultats utilisent les modèles annuels suivants. Choisir ce profil ne remplace pas le modèle ni '
            'les dates du formulaire et ne lance pas automatiquement un replay multi-modèles.')
        st.dataframe(pd.DataFrame([{'Année':year,'Modèle':v['batch_id']} for year,v in models.items()]),
            hide_index=True,width='stretch')
