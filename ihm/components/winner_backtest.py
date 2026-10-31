"""Focused Winner backtest form; no broker, prediction or provider call."""
from datetime import date, timedelta
from pathlib import Path
import json
import subprocess
import uuid

import streamlit as st

from common.winner_pyramiding import load_winner_pyramiding_config
from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command


def render_winner_backtest():
    from modelFactory.oracle_path.predict import load_contract, first_causal_date
    from common.market_calendar import get_market_calendar
    from risk_management.config import load_risk_config
    from execution_engine.config import load_leverage_config_from_yaml
    from service.options_directional.config import load_options_filter_config
    from backtesting.winner_settings import production_risk_defaults
    from ihm.components.winner_backtest_settings import (render_policy_settings,render_risk_settings,
                                                         reset_execution_settings)

    policy = load_winner_pyramiding_config()
    st.info('Profil par défaut : réglages de production et exécution prudente sur les bougies SIP 5m. '
            'Les ajustements dans ce formulaire restent propres au backtest.')
    st.button('Reprendre les réglages de production',on_click=reset_execution_settings,key='bt_winner_reset_settings')
    try:
        policy,policy_changes=render_policy_settings(policy)
    except ValueError as exc:
        st.error(f'Réglages Winner invalides : {exc}')
        st.stop()
    options_config=load_options_filter_config()
    filter_options=st.checkbox('Appliquer le filtre CALL/PUT + OI du pipeline',
        value=options_config.enabled,key='bt_winner_options_filter')
    if not filter_options:
        if options_config.enabled:
            st.warning('Témoin Oracle brut : ce replay n’applique pas la sélection options du pipeline.')
        else:
            st.caption('Filtre options désactivé conformément à la configuration de production.')
    st.caption('TOP Oracle → filtre options si activé → risque → Winner. Même calcul et '
               'mêmes seuils que le pipeline, avec les données connues au cutoff historique. Aucun appel GPT.')
    with st.expander('Réglages Winner et limites du replay', expanded=True):
        st.table([{'Paramètre':name,'Valeur':value} for name,value in [
            ('SL initial',f'{100*policy.stop_loss_pct:g} %'),
            ('TP',f'{100*policy.take_profit_pct:g} %' if policy.take_profit_pct else 'Désactivé'),
            ('Trailing',f'{100*policy.trailing_stop_pct:g} %' if policy.trailing_stop_pct else 'Désactivé'),
            ('Détention maximale',f'{policy.horizon_sessions} séances' if policy.horizon_sessions else 'Sans échéance'),
            ('Position initiale','Complète' if policy.initial_position_fraction==1 else 'Demi-position'),
            ('Renforcement','Activé' if policy.reinforcement_enabled else 'Désactivé'),
            ('Confirmation',f'{policy.confirmation_bars} clôtures de cinq minutes'),
            ('Attente maximale',f'{policy.entry_valid_sessions} séances')]])
        st.caption(f'Délai SIP : {policy.market_data_delay_seconds//60} min '
                   f'{policy.market_data_delay_seconds%60:02d} s ; marge limite retardée : '
                   f'{100*policy.delayed_entry_limit_buffer_pct:g} %. Un cours retardé ne devient pas une quote actuelle.')
        st.caption('Entrée incluse dans la détention ; vente à l’ouverture suivante après '
                   'l’horizon. Les cours OHLC ne reproduisent pas le carnet, le spread et les '
                   'exécutions réelles. Les secteurs sont les métadonnées actuelles.')
        st.caption('En exploitation, le watcher doit être actif sur le compte concerné. En mode '
                   'SIP retardé, les bougies ne sont utilisables qu’après le délai et l’ordre reste '
                   'limité au plafond accepté par le risque. Un cours qui dépasse ce plafond peut ne pas être acheté.')
    root = Path('artifacts/models')
    choices = {}
    for path in sorted(root.glob('*/oracle_path/report.json'), reverse=True):
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
            if report.get('status') == 'completed' and report.get('serving_ready') is True:
                choices[path.parent.parent.name] = f'{path.parent.parent.name} — parcours H{report.get("horizon",20)}'
        except (OSError, ValueError):
            continue
    if not choices:
        st.error('Aucun modèle Oracle parcours terminé disponible.')
        st.stop()
    batch = st.selectbox('Modèle Oracle parcours', list(choices),
                         format_func=choices.get, key='bt_winner_batch')
    try:
        _, contract, _, folds = load_contract(root, batch)
        causal = first_causal_date(folds).date()
        cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        first = next(s.session_date for s in cal.sessions(causal+timedelta(days=1),
                     causal+timedelta(days=14)) if s.is_open)
    except (OSError, ValueError) as exc:
        st.error(f'Contrat Oracle non exploitable : {exc}')
        st.stop()
    st.caption(f'Oracle H{contract["horizon"]} ; premier signal causal : {causal} ; '
               f'première entrée possible : {first}. Les prédictions doivent déjà être enregistrées.')
    start = st.date_input('Date de début Winner', value=max(first, date(2025,1,1)),
                          min_value=first, key=f'bt_winner_start_{batch}')
    end = st.date_input('Date de fin Winner', value=max(start,date.today()-timedelta(days=1)),
                        min_value=first, key=f'bt_winner_end_{batch}')
    source = st.text_input('Univers Winner',
        value='universe-file:config/univers_batch/univers_filtred_tradable.txt', key='bt_winner_universe')
    top = st.number_input('Nombre de premiers titres Oracle', min_value=1, max_value=1000,
                          value=options_config.oracle_top_n, key='bt_winner_top')
    equity = st.number_input('Capital initial ($)', min_value=1., value=4000., key='bt_winner_equity')
    risk = production_risk_defaults(load_risk_config(equity=float(equity),
        cli_overrides={'account_equity':float(equity)}))
    try:
        risk,risk_changes=render_risk_settings(risk)
    except ValueError as exc:
        st.error(f'Réglages de risque invalides : {exc}')
        st.stop()
    coverage = st.number_input('Couverture minimale des prédictions dans l’univers (%)',
        min_value=1., max_value=100., value=100.*options_config.min_oracle_coverage_ratio,
        key='bt_winner_coverage')
    positions = st.number_input('Positions simultanées maximales', min_value=1,
                                value=risk.effective_max_positions, key='bt_winner_positions',
                                help='Winner est LONG uniquement : le plafond LONG est aligné sur ce nombre.')
    account = st.selectbox('Type de compte simulé', ['cash','margin'], key='bt_winner_account')
    leverage_cfg = load_leverage_config_from_yaml()
    allowed = [1.]
    if account == 'margin' and leverage_cfg.enabled and leverage_cfg.max_leverage >= 2:
        allowed.append(2.)
    leverage = st.selectbox('Exposition brute maximale', allowed,
                            format_func=lambda x:f'{x:g}×', key=f'bt_winner_leverage_{account}')
    custom_costs = st.checkbox('Fixer les frais et le glissement par opération', key='bt_winner_custom_costs')
    costs = st.number_input('Coût total par achat ou vente (points de base)',
                            min_value=.01, max_value=1000., value=8., key='bt_winner_costs') if custom_costs else None
    if costs is None:
        st.caption('Frais canoniques du moteur appliqués. La réserve de sizing Winner reste distincte.')
    interest = st.number_input('Taux annuel de financement (%)', min_value=0., max_value=100.,
                               value=6.5, key='bt_winner_interest')
    factors = st.checkbox('Appliquer le contrôle factoriel de production',
                          value=risk.enable_factor_model, key='bt_winner_factors')
    if factors:
        st.caption('Exige des snapshots factoriels réellement disponibles à chaque décision. '
                   'Sans archive qualifiée, entrée bloquée et bilan incomplet.')
    else:
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
        winner_risk_overrides=risk_changes,winner_policy_overrides=policy_changes,
        winner_factor_model=factors, winner_research_assumptions=assumptions,
        oracle_batch_id=batch, max_positions=int(positions), account_type=account,
        margin_interest_rate=interest/100.,
        output_dir=f'artifacts/winner_replays/ihm-{uuid.uuid4().hex}')
    if assumptions:
        st.code(subprocess.list2cmdline(build_backtesting_command('run',options)),language='text')
    return options
