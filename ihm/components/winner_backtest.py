"""Focused Winner backtest form; recovery may call historical data providers."""
from datetime import date, timedelta
from pathlib import Path
import json
from math import ceil
import subprocess
import uuid

import streamlit as st

from common.winner_pyramiding import load_winner_pyramiding_config
from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command

MODEL_ROOT=Path('artifacts/models')


def render_oracle_pool_size(universe_size,default,*,key,label):
    mode=st.radio('Mode du TOP Oracle',['Nombre de titres','Pourcentage de l’univers'],
        horizontal=True,key=key+'_mode')
    if mode=='Pourcentage de l’univers':
        pct=float(st.number_input('TOP Oracle (%)',min_value=.1,max_value=100.,value=10.,step=.5,
            key=key+'_pct',help='Pourcentage de l’univers figé du modèle sélectionné. '
                'Arrondi au nombre entier supérieur, avec au minimum un candidat.'))
        count=min(universe_size,max(1,ceil(universe_size*pct/100)))
        st.caption(f'{pct:g} % des {universe_size:,} titres du modèle = {count:,} candidats Oracle '
            '(arrondi supérieur). Ce nombre reste fixe pendant le backtest, même si des scores sont manquants.')
        return count
    if st.session_state.get(key,default)>universe_size:
        st.session_state[key]=universe_size
    return int(st.number_input(label,min_value=1,max_value=universe_size,
        value=min(int(default),universe_size),key=key))


def render_universe_selection(contract,batch):
    """Always use the selected batch's frozen symbols, including Oracle-only mode."""
    from backtesting.winner_universe import MODEL_UNIVERSE_SOURCE,universe_from_model
    try:
        symbols=universe_from_model(contract)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.text_input('Univers Winner',value=f'Univers du modèle sélectionné — {len(symbols)} titres',
        key=f'bt_winner_universe_auto_{batch}',disabled=True,
        help='Choix automatique depuis les symboles enregistrés dans le batch. '
             'Changer de modèle change son univers ; Top N règle uniquement le classement.')
    st.caption(f'Univers figé du batch {batch} : {len(symbols)} titres, avant classement Oracle et per-symbol.')
    return MODEL_UNIVERSE_SOURCE


def render_model_selection():
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.directional import enabled,load_manifest
    from ihm.services.queries import get_ml_training_batch_comments
    comments=get_ml_training_batch_comments()
    choices={}
    for path in sorted(MODEL_ROOT.glob('*/oracle_path/report.json'),reverse=True):
        try:
            report=json.loads(path.read_text(encoding='utf-8'))
            if report.get('status')=='completed' and report.get('serving_ready') is True:
                badge=' + per-symbol LONG/SHORT' if report.get('directional_models') else ' — Oracle seul'
                batch_id=path.parent.parent.name
                comment=comments.get(batch_id)
                prefix=f'{comment} — ' if comment else ''
                choices[batch_id]=f'{prefix}{batch_id} — parcours H{report.get("horizon",20)}{badge}'
        except (OSError,ValueError):
            continue
    if not choices:
        st.error('Aucun modèle Oracle parcours terminé disponible.')
        st.stop()
    batch=st.selectbox('Modèle Oracle parcours',list(choices),format_func=choices.get,key='bt_winner_batch')
    try:
        _,contract,_,folds=load_contract(MODEL_ROOT,batch)
        bundle=enabled(contract)
        manifest=load_manifest(MODEL_ROOT/batch/'oracle_path')[0] if bundle else None
    except (OSError,ValueError) as exc:
        st.error(f'Contrat Oracle non exploitable : {exc}')
        st.stop()
    count=contract.get('directional_contract',{}).get('selected_n',5)
    pool=contract.get('directional_contract',{}).get('oracle_top_n',20)
    active=st.checkbox('per-symbol',
        value=bundle,disabled=not bundle,key=f'bt_winner_per_symbol_long_{batch}',
        help='Classe les candidats Oracle avec les probabilités LONG/SHORT des modèles par titre du même batch. '
             'Les nombres et directions choisis ici restent propres à ce backtest.')
    active=bool(bundle and active)
    selection=dict(oracle_top_n=pool,allow_long=True,allow_short=False,long_top_n=10,short_top_n=count,
        min_long_probability=None,min_long_auc=None)
    if active:
        pool=render_oracle_pool_size(len(contract['universe']),pool,
            key=f'bt_per_symbol_pool_{batch}',label='Top N Oracle')
        left,right=st.columns(2)
        for column,side,label in [(left,'long','LONG'),(right,'short','SHORT')]:
            with column:
                selection['allow_'+side]=st.checkbox(label,value=side=='long',key=f'bt_per_symbol_allow_{side}_{batch}')
                key=f'bt_per_symbol_top_{side}_{batch}'
                default=10 if side=='long' else count
                migration=f'{key}_default10'
                if side=='long' and not st.session_state.get(migration):
                    if st.session_state.get(key)==min(count,pool):st.session_state[key]=min(10,pool)
                    st.session_state[migration]=True
                if st.session_state.get(key,1)>pool:st.session_state[key]=pool
                selection[side+'_top_n']=int(st.number_input('Top '+('X Long' if side=='long' else 'Y Short'),
                    min_value=1,max_value=pool,value=min(default,pool),disabled=not selection['allow_'+side],key=key))
        selection['oracle_top_n']=pool
        threshold=float(st.number_input('Score LONG minimum — strictement supérieur',min_value=0.,max_value=1.,
            value=.60,step=.01,format='%.2f',disabled=not selection['allow_long'],
            key=f'bt_per_symbol_min_long_probability_{batch}',
            help='Exemple : 0,60 conserve les scores > 0,60 ; un score exactement égal à 0,60 est exclu. '
                 'Filtre appliqué aux TOP X LONG, sans remplacement depuis les rangs suivants.'))
        selection['min_long_probability']=threshold if selection['allow_long'] else None
        auc_key=f'bt_per_symbol_auc_enabled_{batch}'
        if not st.session_state.get(auc_key+'_default_on'):
            st.session_state[auc_key]=True
            st.session_state[auc_key+'_default_on']=True
        use_auc=st.checkbox('Filtrer les titres selon leur AUC LONG',value=True,
            disabled=not selection['allow_long'],key=auc_key)
        auc=float(st.number_input('AUC LONG minimum du titre (≥)',min_value=0.,max_value=1.,value=.60,
            step=.01,format='%.2f',disabled=not (selection['allow_long'] and use_auc),
            key=f'bt_per_symbol_min_long_auc_{batch}',
            help='AUC de calibration du modèle annuel du titre, connue avant l’année testée. '
                 'Distincte du score LONG de l’entrée. AUC absente ou future : titre exclu, sans remplacement. '
                 'La calibration sert à ajuster le score : son AUC n’est pas un test indépendant.'))
        selection['min_long_auc']=auc if selection['allow_long'] and use_auc else None
        if selection['min_long_auc'] is not None:
            st.caption(f'Filtre supplémentaire : AUC LONG de calibration ≥ {auc:.2f}, disponible avant la décision. '
                'Les AUC du test de la même année ne sont pas utilisées pour choisir ses entrées.')
        if not selection['allow_long'] and not selection['allow_short']:
            st.error('Cocher LONG ou SHORT pour appliquer per-symbol.')
            st.stop()
        chosen=[]
        if selection['allow_long']:chosen.append(f"TOP{selection['long_top_n']} LONG de score > {threshold:.2f}")
        if selection['allow_short']:chosen.append(f"TOP{selection['short_top_n']} SHORT")
        st.success(f'TOP{pool} Oracle sur les {len(contract["universe"])} titres du batch → '+ ' + '.join(chosen)+' per-symbol.')
        st.caption('En cas de présence du même titre dans les deux sélections, garder la probabilité la plus forte ; '
                   'égalité : abstention. Aucun remplacement après ce contrôle ou un refus du risque. '
                   'Prévoir les prédictions de la séance précédant la première entrée simulée.')
        if selection['allow_long']:
            st.caption('Les TOP X LONG sont fixés avant le seuil. Si aucun ne dépasse le seuil, aucun achat issu '
                       'de cette sélection. Les positions déjà détenues restent suivies ; ce seuil ne déclenche pas leur vente.')
        if selection['allow_short']:
            st.warning('Le classement SHORT est paramétrable, mais le replay Winner actuel ne simule que les achats LONG. '
                       'Le lancement SHORT reste indisponible tant que son exécution n’est pas raccordée.')
    elif not bundle:
        st.caption('Ce modèle contient uniquement l’Oracle d’amplitude. Choisir un batch « + per-symbol LONG/SHORT » pour activer per-symbol.')
    return batch,contract,folds,manifest,active,selection


def render_winner_backtest():
    from modelFactory.oracle_path.predict import first_causal_date
    from common.market_calendar import get_market_calendar
    from risk_management.config import load_risk_config
    from execution_engine.config import load_leverage_config_from_yaml
    from service.options_directional.config import load_options_filter_config
    from backtesting.winner_settings import production_risk_defaults
    from ihm.components.winner_backtest_settings import (render_policy_settings,render_risk_settings,
                                                         reset_execution_settings,initialize_reference_profile)

    policy = load_winner_pyramiding_config()
    profile=initialize_reference_profile()
    reference_defaults=profile=='reference'
    st.info(('Profil par défaut : réglages du test de référence pour la confirmation, le poids des positions, '
             'le contrôleur DD et les facteurs. ' if reference_defaults else 'Profil : réglages de production. ')+
            'Les ajustements dans ce formulaire restent propres au backtest.')
    st.caption('Simulation isolée : base en lecture seule, rapports et caches dans son dossier. '
               'Les nouveaux runs peuvent fonctionner en parallèle du pipeline. Les anciens runs gardent leur verrou initial.')
    st.button('Reprendre les réglages de production',on_click=reset_execution_settings,key='bt_winner_reset_settings')
    st.button('Reprendre les réglages du test de référence',on_click=reset_execution_settings,
              args=('reference',),key='bt_winner_reset_reference')
    batch,contract,folds,manifest,directional_bundle,per_symbol_selection=render_model_selection()
    options_config=load_options_filter_config()
    if directional_bundle:
        st.session_state['bt_winner_options_filter']=False
    filter_options=st.checkbox('Appliquer le filtre CALL/PUT + OI du pipeline',
        value=False,disabled=directional_bundle,key='bt_winner_options_filter')
    if directional_bundle:
        filter_options=False
    elif not filter_options:
        if options_config.enabled:
            st.warning('Témoin Oracle brut : ce replay n’applique pas la sélection options du pipeline.')
        else:
            st.caption('Filtre options désactivé conformément à la configuration de production.')
    st.caption(('TOP Oracle → classement per-symbol choisi → risque → Winner. '
                'Les nombres et directions sont ceux de ce formulaire. ' if directional_bundle else
                'TOP Oracle → filtre options si activé → risque → Winner. ')+
               'Scores qualifiés au cutoff historique. Aucun appel GPT.')
    with st.expander('Réglages Winner et limites du replay', expanded=True):
        daily_entry=st.checkbox('Entrée journalière à l’ouverture J+1',value=True,key='bt_winner_daily_entry',
            help='Achat au cours journalier d’ouverture de la prochaine séance, sous réserve du capital et du risque. '
                 'Protections en 5m lorsque la séance est complète, sinon sur les OHLC journaliers.')
        if daily_entry:
            st.caption('Signal J → un seul essai d’achat à l’ouverture de la prochaine séance officielle. '
                       'Cours journalier d’ouverture, capital partagé et dimensionnement du risque. '
                       'Aucune exclusion liée aux lacunes intraday futures. Si la séance 5m manque ou présente '
                       'une base de prix incompatible, les protections utilisent les OHLC daily : SL prioritaire '
                       'si la chronologie est inconnue. Le trailing daily est ajusté à la clôture pour la séance suivante. '
                       'Aucun renforcement 5m n’est inventé sur ces séances ; elles sont détaillées dans le rapport.')
        try:
            policy,policy_changes=render_policy_settings(policy,reference_defaults=reference_defaults,
                daily_entry_enabled=daily_entry)
        except ValueError as exc:
            st.error(f'Réglages Winner invalides : {exc}')
            st.stop()
        st.caption(f'Délai SIP : {policy.market_data_delay_seconds//60} min '
                   f'{policy.market_data_delay_seconds%60:02d} s ; marge limite retardée : '
                   f'{100*policy.delayed_entry_limit_buffer_pct:g} %. Un cours retardé ne devient pas une quote actuelle.')
        from backtesting.winner_clock import observation_offset
        if observation_offset(policy) and not daily_entry:
            st.caption('Le signal retardé est évalué à son heure de disponibilité. Faute de prix à cet instant '
                       'dans les bougies 5m, le replay tente un seul achat à l’ouverture 5m suivante, '
                       'avec capital réservé et plafond de prix conservé. Si cette ouverture manque ou dépasse '
                       'la limite, cet ordre simulé est annulé. Cette approximation ne reproduit pas un IOC réel. '
                       'Un ajustement de stop prend aussi effet à l’ouverture suivante ; l’ancien stop reste actif jusque-là.')
        st.caption('Entrée incluse dans la détention ; vente à l’ouverture suivante après '
                   'l’horizon. Les cours OHLC ne reproduisent pas le carnet, le spread et les '
                   'exécutions réelles. Les secteurs sont les métadonnées actuelles.')
        st.caption('Ce mode d’entrée journalier est propre au backtest. En exploitation, le watcher '
                   'doit être actif sur le compte concerné. En mode '
                   'SIP retardé, les bougies ne sont utilisables qu’après le délai et l’ordre reste '
                   'limité au plafond accepté par le risque. Un cours qui dépasse ce plafond peut ne pas être acheté.')
    try:
        causal = first_causal_date(folds).date()
        if directional_bundle:
            for side in ['long','short']:
                if not per_symbol_selection['allow_'+side]:continue
                years=[r['year'] for r in manifest['models'] if r['side']==side]
                if not years:raise ValueError('Aucun modèle '+side.upper()+' annuel disponible')
                causal=max(causal,date(min(years),1,1))
        cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        first = next(s.session_date for s in cal.sessions(causal+timedelta(days=1),
                     causal+timedelta(days=14)) if s.is_open)
    except (OSError, ValueError) as exc:
        st.error(f'Contrat Oracle non exploitable : {exc}')
        st.stop()
    st.caption(f'Oracle H{contract["horizon"]} ; premier signal causal : {causal} ; '
               f'première entrée possible : {first}. Les prédictions doivent déjà être enregistrées.')
    preferred_year=int(contract.get('training_config',{}).get('data',{}).get('training_end_date','2024-12-31')[:4])+1
    default_start=min(date.today(),max(first,date(preferred_year,1,1)))
    default_end=max(default_start,min(date(preferred_year,12,31),date.today()-timedelta(days=1)))
    start = st.date_input('Date de début Winner', value=default_start,
                          min_value=first, key=f'bt_winner_start_v2_{batch}')
    end = st.date_input('Date de fin Winner', value=max(start,default_end),
                        min_value=first, key=f'bt_winner_end_v2_{batch}')
    if directional_bundle:
        days=[s.session_date for s in cal.sessions(start,end) if s.is_open]
        if days:
            st.caption(f'Prédictions nécessaires : signal du {cal.previous_session(days[0])} au '
                       f'{cal.previous_session(days[-1])}, pour les achats simulés du {days[0]} au {days[-1]}.')
    source=render_universe_selection(contract,batch)
    ignore_missing=st.checkbox('Ignorer automatiquement les titres aux données intraday manquantes',
        value=True,key='bt_winner_ignore_missing_intraday',disabled=daily_entry,
        help='Tente Alpaca SIP, puis Yahoo, puis EODHD. Si les bougies restent manquantes, bloque uniquement les dates d’entrée dont la détention pourrait traverser ces lacunes ; aucun remplacement Oracle.')
    if daily_entry:
        ignore_missing=False
        st.caption('Mode journalier : le filtre des lacunes futures et le rattrapage fournisseur sont désactivés. '
                   'Repli sur les protections daily, sans exclure les achats J+1 pour ce motif.')
    if ignore_missing:
        st.warning('Rattrapage des bougies manquantes : Alpaca SIP → Yahoo → EODHD. '
                   'Les entrées incompatibles avec les lacunes restantes sont écartées par date, sans exclure le titre sur toute la période. '
                   'Ce contrôle utilise la disponibilité future des données et peut biaiser le résultat. '
                   'Les appels utilisent tes comptes et quotas existants. Les titres et dates exclus seront consignés dans le rapport et le log final.')
    if directional_bundle:
        top=per_symbol_selection['oracle_top_n']
    else:
        top=render_oracle_pool_size(len(contract['universe']),options_config.oracle_top_n,
            key=f'bt_winner_top_{batch}_{directional_bundle}',label='Nombre de premiers titres Oracle')
    equity = st.number_input('Capital initial ($)', min_value=1., value=4000., key='bt_winner_equity')
    risk = production_risk_defaults(load_risk_config(equity=float(equity),
        cli_overrides={'account_equity':float(equity)}))
    try:
        risk,risk_changes,controller_enabled=render_risk_settings(risk,reference_defaults=reference_defaults)
    except ValueError as exc:
        st.error(f'Réglages de risque invalides : {exc}')
        st.stop()
    from modelFactory.oracle_path.predict import prediction_coverage_ratio
    coverage = st.number_input('Couverture minimale des prédictions dans l’univers (%)',
        min_value=1., max_value=100., value=100.*(prediction_coverage_ratio() if directional_bundle else options_config.min_oracle_coverage_ratio),
        key=f'bt_winner_coverage_{batch}_{directional_bundle}')
    positions = st.number_input('Positions simultanées maximales', min_value=1,
                                value=risk.effective_max_positions, key='bt_winner_positions',
                                help='Winner est LONG uniquement : le plafond LONG est aligné sur ce nombre.')
    if not st.session_state.get('bt_winner_margin_defaults_20261105'):
        for key in ('bt_winner_account','bt_winner_leverage_margin'):
            st.session_state.pop(key,None)
        st.session_state['bt_winner_margin_defaults_20261105']=True
    account = st.selectbox('Type de compte simulé', ['margin','cash'], key='bt_winner_account')
    leverage_cfg = load_leverage_config_from_yaml()
    allowed = [1.]
    if account == 'margin' and leverage_cfg.enabled and leverage_cfg.max_leverage >= 2:
        allowed.append(2.)
    leverage = st.selectbox('Exposition brute maximale', allowed,
                            index=len(allowed)-1,format_func=lambda x:f'{x:g}×', key=f'bt_winner_leverage_{account}')
    st.caption(f'Plafond combiné risque / compte simulé : {min(leverage,risk.max_gross_exposure):g}× '
               'le capital courant, sous réserve des conditions de levier. '
               'Pour autoriser 2×, choisir margin, exposition 2× et plafond du risque 2,00×. '
               'Ce plafond autorise une capacité ; il ne force pas les achats.')
    custom_costs = st.checkbox('Fixer les frais et le glissement par opération', key='bt_winner_custom_costs')
    costs = st.number_input('Coût total par achat ou vente (points de base)',
                            min_value=.01, max_value=1000., value=8., key='bt_winner_costs') if custom_costs else None
    if costs is None:
        st.caption('Frais canoniques du moteur appliqués. La réserve de sizing Winner reste distincte.')
    interest = st.number_input('Taux annuel de financement (%)', min_value=0., max_value=100.,
                               value=6.5, key='bt_winner_interest')
    factors = st.checkbox('Appliquer le contrôle factoriel de production',
                          value=False if reference_defaults else risk.enable_factor_model, key='bt_winner_factors')
    cap_check=st.checkbox('Contrôler la capitalisation historique — facteur taille',value=False,
        disabled=not factors,key='bt_winner_factor_cap',
        help='Décocher retire le facteur taille dans ce backtest. Le bêta, le momentum et les autres protections restent contrôlés.')
    if factors and not cap_check:
        st.warning('Replay sans facteur taille : aucune capitalisation requise ni substituée. '
                   'Le risque est calculé sur les facteurs marché et momentum ; ce résultat diffère du modèle factoriel complet.')
    if factors and cap_check:
        st.caption('Utilise les snapshots historiques qualifiés ; sinon, reconstruit automatiquement les facteurs '
                   'depuis les bougies passées et les capitalisations datées connues à l’époque. '
                   'Les reconstructions sont identifiées dans le rapport. Si les sources nécessaires manquent, '
                   'l’entrée reste bloquée et le bilan incomplet.')
    elif not factors:
        if risk.enable_factor_model:
            st.warning('Contrôle factoriel désactivé uniquement dans ce replay : différence explicite avec la production.')
        else:
            st.caption('Contrôle factoriel désactivé conformément à la configuration de production.')
    assumptions = st.checkbox('Utiliser le replay prudent disponible, proche du fonctionnement en production',
                               value=True,key='bt_winner_prudent_replay')
    st.caption('En cas de SL et TP touchés dans la même bougie, priorité à la sortie défavorable ; '
               'aucun achat rétroactif. Les secteurs actuels restent une approximation historique '
               'et ne deviennent pas des secteurs connus à l’époque. Le rapport reste exploratoire.')
    if end < start:
        st.error('La date de fin doit suivre la date de début.')
        st.stop()
    options = BacktestRunOptions(start=start.isoformat(), end=end.isoformat(), equity=float(equity),
        ml_mode='off', winner_enabled=True, winner_top_n=int(top), winner_symbol_source=source,
        winner_max_leverage=leverage, winner_cost_per_leg_bps=costs,
        winner_min_oracle_coverage=coverage/100.,
        winner_options_filter_enabled=filter_options,
        winner_per_symbol_long_enabled=directional_bundle,
        winner_per_symbol_allow_long=per_symbol_selection['allow_long'],
        winner_per_symbol_allow_short=per_symbol_selection['allow_short'],
        winner_per_symbol_top_long=per_symbol_selection['long_top_n'],
        winner_per_symbol_top_short=per_symbol_selection['short_top_n'],
        winner_per_symbol_min_long_probability=per_symbol_selection['min_long_probability'],
        winner_per_symbol_min_long_auc=per_symbol_selection['min_long_auc'],
        winner_ignore_missing_intraday=ignore_missing,
        winner_risk_overrides=risk_changes,winner_policy_overrides=policy_changes,
        winner_drawdown_controller_enabled=controller_enabled,
        winner_daily_entry_enabled=daily_entry,
        winner_factor_model=factors,winner_factor_market_cap_check=cap_check, winner_research_assumptions=assumptions,
        oracle_batch_id=batch, max_positions=int(positions), account_type=account,
        margin_interest_rate=interest/100.,
        output_dir=f'artifacts/winner_replays/ihm-{uuid.uuid4().hex}')
    if assumptions:
        st.code(subprocess.list2cmdline(build_backtesting_command('run',options)),language='text')
    return options
