"""Show the archived reference, independently of the current form's edits."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT=Path(__file__).resolve().parents[2]
STUDY=PROJECT/'artifacts/research/us_winner_q051_risk_budget/20261109-v1'
BASE=PROJECT/'artifacts/research/us_winner_continuous_q051_q088/20261108-v2'
VARIANTS=PROJECT/'artifacts/research/us_q051_selection_variants/20261115-v1'
CLASSIC=PROJECT/'artifacts/research/us_q051_classic_top10/20261115-v1'
FEATURE_GROUPS=PROJECT/'artifacts/research/us_q051_feature_groups/20261116-lot1'
ANTI_SL=PROJECT/'artifacts/research/us_q051_b_early_sl/20261116-v1'
CURVE_LABELS=('Q051 témoin — TOP5','Volatilité 20 % + régime — TOP5',
              'Volatilité 20 % + régime — TOP10','Q051 témoin — TOP10',
              'Témoin B — 24 variables, mêmes Oracle','B seul — 29 variables, TOP10',
              'B + anti-SL témoin — TOP10','SPY')


def comparison_data():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    specifications=[
        (CURVE_LABELS[0],BASE/'cases/Q051_050/result',None),
        (CURVE_LABELS[1],STUDY/'REGIME_VOL20/result',None),
        (CURVE_LABELS[2],VARIANTS/'cases/TOP10_SCORE050/result',VARIANTS/'validation-independent.json'),
        (CURVE_LABELS[3],CLASSIC/'cases/TOP10/result',CLASSIC/'validation-independent.json'),
        (CURVE_LABELS[4],FEATURE_GROUPS/'variants/T0/cases/T0_SIMPLE/result',FEATURE_GROUPS/'validation.json'),
        (CURVE_LABELS[5],FEATURE_GROUPS/'variants/B/cases/B_SIMPLE/result',FEATURE_GROUPS/'validation.json'),
        (CURVE_LABELS[6],ANTI_SL/'cases/SL10/result',ANTI_SL/'selection-validation.json'),
    ]
    rows=[];curves=[]
    for label,folder,validation in specifications:
        if validation is not None and read(validation).get('status') not in ('PASS','ARITHMETIC_CHECKS_PASS_RESEARCH_ONLY'):
            raise ValueError(f'Archive non validée : {label}')
        if folder.is_relative_to(FEATURE_GROUPS):
            case=folder.parent.name
            audit=read(FEATURE_GROUPS/'price-window-validation.json')
            checks=[c for c in audit['checks'] if c['case']==case]
            if len(checks)!=1 or checks[0]['status']!='OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY':
                raise ValueError(f'Qualification des prix archivée absente : {label}')
        if folder.is_relative_to(ANTI_SL):
            audit=read(ANTI_SL/'post-run-review.json')
            checks=[c for c in audit['checks'] if c['case']=='SL10']
            if (audit.get('status') not in ('ARITHMETIC_CONTROL_AND_SCOPE_CHECKED_RESEARCH_ONLY',
                    'ARITHMETIC_CONTROL_PASS_WITH_PRICE_OR_EVENT_RESERVES') or len(checks)!=1
                    or read(ANTI_SL/'oracle-oof-causality.json').get('status')!='PASS'
                    or read(ANTI_SL/'selection-validation.json').get('no_refill') is not True):
                raise ValueError(f'Contrôles de l’archive anti-SL absents ou invalides : {label}')
        r=read(folder/'report.json')
        equity=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).iloc[:,0].astype(float)
        if equity.index.has_duplicates or not equity.index.is_monotonic_increasing:
            raise ValueError(f'Dates de courbe invalides : {label}')
        if abs(equity.iloc[-1]-r['final_equity'])>1e-6:
            raise ValueError(f'Capital final incompatible avec la courbe : {label}')
        r['daily_max_drawdown_pct']=100.*(equity/equity.cummax().clip(lower=4000.)-1).min()
        equity.loc[pd.Timestamp('2021-01-01')]=4000.
        curves.append(equity.sort_index().rename(label))
        rows.append({'Courbe':label,'Capital final ($)':round(r['final_equity'],2),
            'Rendement (%)':round(r['return_pct'],2),
            'DD sur clôtures (%)':round(r['daily_max_drawdown_pct'],2),
            'DD intraday (%)':round(r['max_drawdown_pct'],2) if 'max_drawdown_pct' in r else None,
            'Trades clôturés':r.get('closed_lot_trades'),
            'Trades gagnants (%)':round(r['win_pct'],2) if 'win_pct' in r else None})
    spy=read(STUDY/'spy-benchmark.json')
    spy_curve=pd.read_csv(STUDY/'charts/q051-temoin-volatilite20-regime-vs-spy-2021-2026.csv',
        index_col=0,parse_dates=True)['SPY_hors_dividendes_frais_USD'].astype(float)
    if abs(spy_curve.iloc[-1]-spy['final_equity'])>1e-6:raise ValueError('Capital final SPY incompatible avec la courbe')
    curves.append(spy_curve.rename('SPY'))
    rows.append({'Courbe':'SPY','Capital final ($)':round(spy['final_equity'],2),
        'Rendement (%)':round(spy['return_pct'],2),'DD sur clôtures (%)':round(spy['daily_max_drawdown_pct'],2),
        'DD intraday (%)':None,'Trades clôturés':None,'Trades gagnants (%)':None})
    chart=pd.concat(curves,axis=1)
    if chart.isna().any().any():raise ValueError('Périodes différentes entre les courbes')
    return pd.DataFrame(rows),chart,read(BASE/'protocol.json')['annual_models']


def reference_comparison():
    table,_,models=comparison_data()
    return table,models


def comparison_figure(curves):
    # Fully local rendering, including on PCs without interactive chart extras.
    from matplotlib.figure import Figure
    figure=Figure(figsize=(12,6),layout='constrained')
    ax=figure.subplots()
    colors=['#2455cc','#008f72','#ee8b22','#8c44ac','#b17b28','#ce3458','#009eb1','#737373']
    for label,color in zip(CURVE_LABELS,colors):
        ax.plot(curves.index,curves[label],label=label,color=color,linewidth=1.4)
    ax.set_title('Q051, B seul, B + anti-SL et SPY — capital valorisé')
    ax.set_ylabel('Capital ($), départ 4 000');ax.grid(alpha=.2)
    ax.legend(loc='upper left',fontsize=9)
    return figure


@st.dialog('Q051, B et B + anti-SL — comparaison avec SPY',width='large')
def show_reference_comparison():
    try:
        table,curves,models=comparison_data()
    except (OSError,ValueError,KeyError) as exc:
        st.warning(f'Comparaison archivée indisponible sur ce PC : {exc}')
        return
    st.caption('Référence du 01/01/2021 au 01/10/2026 · 4 000 $ initiaux · capital continu, sans remise à zéro annuelle.')
    st.pyplot(comparison_figure(curves),width='stretch')
    st.dataframe(table,hide_index=True,width='stretch')
    st.caption('Comparer le DD sur clôtures pour les courbes. Le DD intraday SPY n’est pas disponible. '
        'Stratégies : frais et financement inclus. SPY : cours seuls, sans dividendes ni frais. '
        'Couverture 5m incomplète avec protections daily de secours ; résultats exploratoires.')
    with st.expander('Réglages et lecture des courbes'):
        st.write('Q051 témoin : TOP10 % Oracle → TOP5 ou TOP10 LONG per-symbol selon le profil, '
            'score > 0,50 et AUC de calibration ≥ 0,50. '
            'Entrée directe à l’ouverture J+1, position complète, SL5 %, sans TP, trailing ni renforcement, sortie open11. '
            'Risque 1,25 % par entrée, poids maximal 20 %, 20 positions, minimum 50 $, plafond de risque 1× ; '
            'compte margin de capacité 2×. Frais 8 points de base par opération et financement annuel 6,5 %. '
            'B4/DD15, facteurs, corrélation et limites sectorielles désactivés.')
        st.write('Volatilité 20 % + régime : même base. Covariance des 60 dernières séances connues pour réduire '
            'les nouveaux achats lorsque la volatilité annualisée prévue du portefeuille dépasse 20 %. '
            'Achats autorisés si SPY à J > 98 % de sa moyenne 200 séances. Les titres détenus ne sont pas liquidés par ces règles. '
            'La cible de volatilité ne garantit pas un drawdown maximal de 20 %.')
        st.write('TOP5 et TOP10 sont des nombres maximaux avant les rejets de seuil et de risque, sans remplacement. '
            'Le témoin TOP5 vaut +206,51 % ; le témoin TOP10 vaut +280,94 %. '
            'Avec vol20 + régime, TOP5 vaut +125,98 % et TOP10 +150,90 %. '
            'Les résultats présentés sont ceux des archives annuelles, pas une prévision pour le formulaire courant.')
        st.write('B seul utilise les mêmes réglages Q051 TOP10, avec cinq variables de volatilité supplémentaires '
            'dans les modèles par titre, soit 29. Ce ne sont ni le budget de volatilité du portefeuille ni un filtre de régime. '
            'B seul vaut +297,35 %, DD −40,99 %, 37,63 % gagnants ; sans pause100. '
            'Son témoin apparié à 24 variables vaut +129,06 %, DD −39,12 %. Ces deux courbes utilisent les mêmes '
            'Oracle annuels entre elles, différents des archives Q051 précédentes : comparer B directement à son témoin apparié. '
            'Le profil charge les réglages du portefeuille ; les variables sont figées à l’entraînement du batch choisi.')
        st.write('B + anti-SL témoin reprend B seul et les mêmes modèles Oracle/B : après le TOP10 LONG, '
            'un modèle commun à 44 variables écarte les risques de SL première séance supérieurs au percentile 90 '
            'de calibration, sans remplacer les titres exclus. Les dix séances sont une fenêtre passée de variables. '
            'Résultat archivé : 16 140,82 $, +303,52 %, DD intraday −34,98 %, 38,13 % gagnants, 1 356 trades. '
            'Le nouveau profil exige une tête anti-SL native ; il ne recharge pas automatiquement les poids de recherche.')
        anti_review=json.loads((ANTI_SL/'post-run-review.json').read_text(encoding='utf-8'))
        case=next(c for c in anti_review['checks'] if c['case']=='SL10')
        st.caption(f'Archive anti-SL : contrôle arithmétique avec réserves, '
            f'{case["event_label_mismatches"]} écart(s) de label première séance sur {case["known_event_labels"]} trades qualifiés ; '
            f'{len(anti_review.get("price_reserves",[]))} réserve(s) de prix. Historique non certifié PIT, sans parité live complète.')
        st.write('SPY : achat conservé sur toute la période, sans levier, dividendes ni frais. '
            'Les courbes montrent des capitaux valorisés, y compris les positions encore ouvertes.')
        st.caption('Ces résultats utilisent les modèles annuels suivants. Choisir ce profil ne remplace pas le modèle ni '
            'les dates du formulaire et ne lance pas automatiquement un replay multi-modèles.')
        st.dataframe(pd.DataFrame([{'Année':year,'Modèle':v['batch_id']} for year,v in models.items()]),
            hide_index=True,width='stretch')
        b_models=json.loads((FEATURE_GROUPS/'variants/B/models.json').read_text(encoding='utf-8'))
        st.caption('Oracle annuels du témoin apparié et de B ; modèles LONG B archivés séparément dans cette recherche.')
        st.dataframe(pd.DataFrame([{'Année':year,'Oracle B / témoin':v['batch_id'],
            'Variables par titre B':29} for year,v in b_models.items()]),hide_index=True,width='stretch')
