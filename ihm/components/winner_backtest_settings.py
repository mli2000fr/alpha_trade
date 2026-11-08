"""Only display settings genuinely consumed by the intraday replay."""
from dataclasses import asdict
import streamlit as st

from backtesting.winner_settings import apply_risk_settings, apply_policy_settings


REFERENCE_DEFAULTS_MARKER='bt_winner_reference_defaults_20261105'
GROSS_DEFAULTS_MARKER='bt_winner_gross_default_2_20261105'


def initialize_reference_profile():
    """Migrate open sessions to the requested Q088 defaults once."""
    if not st.session_state.get(REFERENCE_DEFAULTS_MARKER):
        for key in ('bt_wp_confirmation','bt_wp_delay','bt_wr_weight','bt_wr_close',
                    'bt_winner_factors','bt_wr_controller_enabled'):
            st.session_state.pop(key,None)
        st.session_state['bt_winner_settings_profile']='reference'
        st.session_state[REFERENCE_DEFAULTS_MARKER]=True
    if not st.session_state.get(GROSS_DEFAULTS_MARKER):
        st.session_state['bt_wr_gross']=2.
        st.session_state[GROSS_DEFAULTS_MARKER]=True
    from ihm.components.winner_backtest_profiles import Q088_MARKER,apply_q088_defaults
    if not st.session_state.get(Q088_MARKER):
        apply_q088_defaults()
    return st.session_state.get('bt_winner_settings_profile','q088')


def reset_execution_settings(profile='production'):
    for key in list(st.session_state):
        if (key.startswith(('bt_wr_','bt_wp_','bt_per_symbol_','bt_q088_selection_','bt_research_selection_','bt_winner_top_','bt_winner_per_symbol_long_')) or key in ('bt_winner_positions','bt_winner_factors','bt_winner_factor_cap','bt_winner_excluded_symbols','bt_winner_ignore_missing_intraday',
                'bt_winner_custom_costs','bt_winner_costs','bt_winner_interest','bt_winner_options_filter',
                'bt_winner_coverage','bt_winner_top','bt_winner_daily_entry')):
            del st.session_state[key]
    st.session_state['bt_winner_settings_profile']=profile
    st.session_state['bt_winner_daily_entry']=profile!='production'
    st.session_state[REFERENCE_DEFAULTS_MARKER]=True
    from ihm.components.winner_backtest_profiles import Q088_MARKER,apply_research_defaults
    st.session_state[Q088_MARKER]=True
    if profile in ('q088','q051'):
        apply_research_defaults(profile)


def percent(label,value,key,*,disabled=False,maximum=100.):
    return float(st.number_input(label,min_value=.01,max_value=float(maximum),value=100.*float(value),
        format='%.2f',key=key,disabled=disabled))/100.


def render_policy_settings(policy,*,reference_defaults=False,daily_entry_enabled=False):
    values={}
    with st.container():
        profile=st.session_state.get('bt_winner_settings_profile')
        st.caption((f'Profil {profile.upper()} : SL5 %, sans TP/trailing, H10, position complète, sans confirmation. '
                    if profile in ('q088','q051') else
                    'Défauts du test de référence : aucune confirmation et aucun délai SIP. '
                    'Les autres protections viennent de config.yaml. ' if reference_defaults else
                    'Valeurs par défaut : section winner_pyramiding de config.yaml. ')+
                   'Ces réglages sont modifiables pour ce backtest uniquement. '
                   'Le profil « Réglages de production » recharge les valeurs de configuration.')
        values['stop_loss_pct']=percent('SL initial (%)',policy.stop_loss_pct,'bt_wp_sl',maximum=99.99)
        tp=st.checkbox('Activer un TP en prix',value=policy.take_profit_pct is not None,key='bt_wp_tp_enabled')
        values['take_profit_pct']=percent('TP (%)',policy.take_profit_pct or .20,'bt_wp_tp',
            disabled=not tp,maximum=99.99) if tp else None
        trailing=st.checkbox('Activer le trailing',value=policy.trailing_stop_pct is not None,key='bt_wp_trailing_enabled')
        values['trailing_stop_pct']=percent('Trailing (%)',policy.trailing_stop_pct or .15,'bt_wp_trailing',
            maximum=99.99) if trailing else None
        horizon=st.checkbox('Sortir après une durée maximale',value=policy.horizon_sessions is not None,key='bt_wp_horizon_enabled')
        values['horizon_sessions']=int(st.number_input('Séances de détention, entrée incluse',min_value=1,max_value=252,
            value=policy.horizon_sessions or 20,key='bt_wp_horizon')) if horizon else None
        if values['horizon_sessions']:
            st.caption(f"Sortie à l’ouverture de la {values['horizon_sessions']+1}e séance depuis le fill réel.")
        fractions=[1.,.5]
        values['initial_position_fraction']=st.selectbox('Part de la position initiale',fractions,
            index=fractions.index(policy.initial_position_fraction),
            format_func=lambda v:'Position complète' if v==1 else 'Demi-position',key='bt_wp_fraction')
        values['reinforcement_enabled']=st.checkbox('Renforcer une position gagnante',value=policy.reinforcement_enabled,key='bt_wp_add')
        if values['reinforcement_enabled']:
            values['reinforcement_trigger_pct']=percent('Hausse requise avant renforcement (%)',
                policy.reinforcement_trigger_pct,'bt_wp_add_trigger',maximum=99.99)
            st.caption('Un seul ajout, dans le budget initial. Aucun ajout avec une position initiale déjà complète.')
        values['confirmation_bars']=int(st.number_input('Clôtures 5m de confirmation',min_value=0,max_value=12,
            value=0 if reference_defaults else policy.confirmation_bars,key='bt_wp_confirmation',disabled=daily_entry_enabled))
        values['entry_valid_sessions']=int(st.number_input('Séances maximales pour attendre l’entrée',min_value=1,max_value=60,
            value=policy.entry_valid_sessions,key='bt_wp_validity',disabled=daily_entry_enabled))
        if daily_entry_enabled:
            values['entry_valid_sessions']=1
            st.caption('Entrée initiale uniquement à l’ouverture J+1, sans confirmation 5m ni nouvelle tentative. '
                       'Le délai SIP et les confirmations restent applicables au suivi et au renforcement éventuel.')
        values['market_data_delay_seconds']=int(st.number_input('Retard SIP accepté (secondes)',min_value=0,max_value=3600,
            value=0 if reference_defaults else policy.market_data_delay_seconds,step=1,key='bt_wp_delay',
            help='0 = temps réel ; de 900 à 3600 = mode retardé. Les bougies restent sur leur grille 5m.'))
        values['delayed_entry_limit_buffer_pct']=float(st.number_input('Marge du prix limite retardé (%)',min_value=0.,
            max_value=5.,value=100.*policy.delayed_entry_limit_buffer_pct,key='bt_wp_delayed_buffer'))/100.
        values['cost_reserve_bps_per_leg']=float(st.number_input('Réserve de sizing par opération (points de base)',
            min_value=0.,max_value=500.,value=float(policy.cost_reserve_bps_per_leg),key='bt_wp_reserve'))
        st.caption('La réserve réduit la quantité achetable ; elle ne remplace pas les frais facturés dans le replay.')
    changes={k:v for k,v in values.items() if v!=getattr(policy,k)}
    return apply_policy_settings(policy,changes),changes


def render_risk_settings(risk,*,reference_defaults=False):
    values={}
    with st.expander('Dimensionnement et limites du portefeuille',expanded=True):
        values['max_gross_exposure']=float(st.number_input('Plafond d’exposition brute du risque (× capital)',
            min_value=.01,max_value=2.,value=2. if reference_defaults else min(2.,float(risk.max_gross_exposure)),step=.1,
            format='%.2f',key='bt_wr_gross',
            help='Propre à ce backtest : 1 = 100 % du capital courant ; 2 = 200 %. '
                 'La limite effective reste bornée par le compte simulé et le levier autorisé.'))
        values['risk_per_trade_pct']=percent('Risque budgété par entrée (%)',risk.risk_per_trade_pct,'bt_wr_budget',maximum=99.99)
        minimum=float(st.number_input('Montant minimum par position ($)',min_value=.01,
            value=risk.effective_min_notional,key='bt_wr_minimum'))
        values['min_position_notional']=minimum
        if risk.enforce_min_notional is not None:
            values['enforce_min_notional']=minimum
        values['max_position_weight']=percent('Poids maximal par position (%)',.20 if reference_defaults else risk.max_position_weight,'bt_wr_weight')
        sector=st.checkbox('Limiter le poids par secteur',value=risk.sector_weight_limit_enabled,key='bt_wr_sector_weight_enabled')
        values['sector_weight_limit_enabled']=sector
        values['max_sector_weight']=percent('Poids maximal par secteur (%)',risk.max_sector_weight,'bt_wr_sector_weight',disabled=not sector)
        count=st.checkbox('Limiter le nombre de titres par secteur',value=risk.sector_ticker_limit_enabled,key='bt_wr_sector_count_enabled')
        values['sector_ticker_limit_enabled']=count
        cap=int(st.number_input('Titres maximum par secteur (0 = aucun plafond)',min_value=0,
            value=risk.max_tickers_per_sector or 0,key='bt_wr_sector_count',disabled=not count))
        values['max_tickers_per_sector']=(cap or None) if count else risk.max_tickers_per_sector
    with st.expander('Drawdown, pertes quotidiennes et volatilité'):
        controller=st.checkbox('Appliquer le contrôleur DD / perte quotidienne / B4',
            value=not reference_defaults,key='bt_wr_controller_enabled',
            help='Propre au backtest : désactive les blocages DD/perte quotidienne, la réduction B4 et leur liquidation. '
                 'Le SL, le TP, le trailing et les limites de dimensionnement restent applicables.')
        st.caption((f'Contrôleur de risque actif : {risk.policy.upper()}. Les seuils déclenchent une réaction ; '
                    'un gap peut les dépasser.' if controller else
                    'Contrôleur DD/perte quotidienne/B4 désactivé pour ce backtest. Le drawdown reste mesuré dans le rapport.'))
        values['max_portfolio_drawdown_pct']=percent('Seuil de drawdown (%)',risk.max_portfolio_drawdown_pct,'bt_wr_dd',maximum=99.99,disabled=not controller)
        values['max_daily_loss_pct']=percent('Seuil de perte quotidienne (%)',risk.max_daily_loss_pct,'bt_wr_dayloss',maximum=99.99,disabled=not controller)
        close=st.checkbox('Liquider des positions au déclenchement du coupe-circuit',
            value=False if reference_defaults else risk.force_close_on_breaker,key='bt_wr_close',disabled=not controller)
        values['force_close_on_breaker']=bool(controller and close)
        values['force_close_pct']=percent('Part des positions à liquider (%)',risk.force_close_pct,'bt_wr_close_pct',disabled=not(controller and close))
        vol=st.checkbox('Appliquer une cible de volatilité',value=risk.target_annual_vol is not None,key='bt_wr_vol')
        values['target_annual_vol']=percent('Volatilité annuelle cible (%)',risk.target_annual_vol or .13,'bt_wr_vol_pct') if vol else None
        if vol:
            values['vol_target_lookback_days']=int(st.number_input('Historique de volatilité (séances)',min_value=2,max_value=252,
                value=risk.vol_target_lookback_days,key='bt_wr_vol_days'))
    with st.expander('Corrélations, répétition des entrées et bêta'):
        corr=st.checkbox('Contrôler les corrélations entre titres',value=risk.correlation_check_enabled,key='bt_wr_correlation')
        values['correlation_check_enabled']=corr
        values['correlation_threshold']=float(st.number_input('Corrélation maximale',min_value=.01,max_value=1.,
            value=float(risk.correlation_threshold),key='bt_wr_corr_max',disabled=not corr))
        values['correlation_lookback_days']=int(st.number_input('Historique de corrélation (séances)',min_value=2,max_value=252,
            value=risk.correlation_lookback_days,key='bt_wr_corr_days',disabled=not corr))
        values['correlation_min_overlap']=int(st.number_input('Minimum de séances communes',min_value=2,max_value=252,
            value=risk.correlation_min_overlap,key='bt_wr_corr_overlap',disabled=not corr))
        for field,label in [('concentration_max_trades_per_symbol','Entrées maximales par titre'),
                ('concentration_window_calendar_days','Fenêtre des entrées (jours calendaires)'),
                ('concentration_max_consecutive_losses','Pertes consécutives avant exclusion'),
                ('concentration_blacklist_duration_days','Durée d’exclusion (jours calendaires)')]:
            values[field]=int(st.number_input(label,min_value=1,value=getattr(risk,field),key='bt_wr_'+field))
        values['max_portfolio_beta']=float(st.number_input('Plafond bêta du portefeuille',min_value=.01,
            value=float(risk.max_portfolio_beta),key='bt_wr_beta',help='Pris en compte lorsque le contrôle factoriel est activé.'))
    changes={k:v for k,v in values.items() if v!=getattr(risk,k)}
    edited=apply_risk_settings(risk,changes)
    with st.expander('Tous les paramètres de risque hérités de la production'):
        st.json(asdict(edited))
        st.caption('Les champs affichés en lecture seule ne sont pas des commandes supplémentaires du replay. '
                   'La qualification complète et les limites sont consignées dans le rapport.')
    return edited,changes,controller
