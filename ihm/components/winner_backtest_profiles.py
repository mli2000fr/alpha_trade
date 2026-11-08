"""UI-only replay profiles, expressed in widget units (percent, dollars, days).

Source: us_winner_risk_tradeoff/20261107-v1/cases/Q088_SIZE125_B4DD15/configuration.json.
Q051: same risk settings, selection thresholds from continuous Q051_050 (20261108-v2).
No production configuration or model contract is modified.
"""
import streamlit as st

Q088_MARKER = 'bt_winner_q088_size125_b4dd15_defaults_20261107'
Q088_WIDGETS = {
    'bt_winner_daily_entry': True,
    'bt_wp_sl': 5., 'bt_wp_tp_enabled': False, 'bt_wp_trailing_enabled': False,
    'bt_wp_horizon_enabled': True, 'bt_wp_horizon': 10,
    'bt_wp_fraction': 1., 'bt_wp_add': False, 'bt_wp_add_trigger': 5.,
    'bt_wp_confirmation': 0, 'bt_wp_validity': 1, 'bt_wp_delay': 0,
    'bt_wp_delayed_buffer': 1., 'bt_wp_reserve': 25.,
    'bt_wr_gross': 2., 'bt_wr_budget': 1.25, 'bt_wr_minimum': 50.,
    'bt_wr_weight': 20., 'bt_wr_sector_weight_enabled': False,
    'bt_wr_sector_weight': 50., 'bt_wr_sector_count_enabled': False,
    'bt_wr_sector_count': 0, 'bt_wr_controller_enabled': True,
    'bt_wr_dd': 15., 'bt_wr_dayloss': 3., 'bt_wr_close': True,
    'bt_wr_close_pct': 50., 'bt_wr_vol': False, 'bt_wr_vol_days': 60,
    'bt_wr_correlation': False, 'bt_wr_corr_max': .9,
    'bt_wr_corr_days': 40, 'bt_wr_corr_overlap': 25, 'bt_wr_beta': 5.,
    'bt_wr_concentration_max_trades_per_symbol': 10,
    'bt_wr_concentration_window_calendar_days': 90,
    'bt_wr_concentration_max_consecutive_losses': 3,
    'bt_wr_concentration_blacklist_duration_days': 90,
    'bt_winner_positions': 20, 'bt_winner_factors': False,
    'bt_winner_factor_cap': False, 'bt_winner_options_filter': False,
    'bt_winner_equity': 4000., 'bt_winner_account': 'margin',
    'bt_winner_leverage_margin': 2., 'bt_winner_custom_costs': True,
    'bt_winner_costs': 8., 'bt_winner_interest': 6.5,
    'bt_winner_prudent_replay': True,
    'bt_winner_margin_defaults_20261105': True,
}
Q051_WIDGETS = {
    **Q088_WIDGETS,
    'bt_wr_gross': 1., 'bt_wr_controller_enabled': False, 'bt_wr_close': False,
}

PROFILE_LABELS = {
    'q088': 'Q088 — risque réduit + B4/DD15 (défaut)',
    'q051': 'Q051 — seuils 0,50, plafond de risque 1×',
    'production': 'Réglages de production — config.yaml',
    'reference': 'Ancien test de référence',
}
PROFILE_DESCRIPTIONS = {
    'q088': (
        'TOP20 % Oracle → TOP10 LONG per-symbol, score > 0,60 et AUC ≥ 0,60. '
        'Risque par entrée 1,25 %, poids maximal 20 %, plafond de risque 2×. '
        'B4/DD15 actif : liquidation de 50 %, perte quotidienne limitée à 3 %. '
        'Position complète, entrée à l’ouverture J+1 sans confirmation, SL5 %, '
        'sans TP ni trailing, sortie open11. Facteurs, corrélation et limites sectorielles désactivés. '
        'Résultat exploratoire 2025 : +35,13 %, DD −17,20 % ; DD15 est un seuil d’action, pas un plafond garanti.'),
    'q051': (
        'TOP10 % Oracle → TOP5 LONG per-symbol, score > 0,50 et AUC ≥ 0,50. '
        'Risque par entrée 1,25 %, poids maximal 20 %, plafond de risque 1× sur les nouvelles entrées. '
        'B4/DD15 et liquidation globale désactivés. Position complète, entrée à l’ouverture J+1 '
        'sans confirmation, SL5 %, sans TP ni trailing, sortie open11. '
        'Facteurs, corrélation et limites sectorielles désactivés. '
        'Le compte margin conserve une capacité 2×, bornée par le plafond de risque 1× pour les achats. '
        'Replay continu H10 du 01/01/2021 au 01/10/2026, modèles annuels, capital initial 4 000 $ : '
        '12 260,32 $ finaux, +206,51 %, DD −36,89 %, taux gagnant 35,01 %. '
        'Frais et financement inclus. Couverture intraday incomplète ; résultat rétrospectif exploratoire, '
        'sans garantie de reproduction sur une autre période ou un autre modèle.'),
    'production': (
        'Recharge les protections Winner et les limites de risque de config.yaml et du preset de capital. '
        'La confirmation, le délai SIP et les contrôles reprennent ces valeurs de production. '
        'L’entrée journalière est désactivée. Les comptes réels et la configuration de production '
        'ne sont pas modifiés ; ces réglages restent propres à la simulation.'),
    'reference': (
        'Ancien profil témoin : entrée journalière J+1 sans confirmation ni délai SIP, '
        'poids maximal par titre 20 %, plafond de risque 2×, contrôleur DD/B4 et facteurs désactivés. '
        'Les autres protections et limites sont reprises de config.yaml. '
        'La sélection Oracle/per-symbol reprend les valeurs du formulaire et du contrat du modèle ; '
        'ce profil ne correspond pas aux variantes Q051/Q088.'),
}


def apply_research_defaults(profile):
    for key in list(st.session_state):
        if key.startswith(('bt_q088_selection_', 'bt_research_selection_')):
            del st.session_state[key]
    st.session_state.update({'q088': Q088_WIDGETS, 'q051': Q051_WIDGETS}[profile])
    st.session_state['bt_winner_settings_profile'] = profile
    st.session_state[Q088_MARKER] = True


def apply_q088_defaults():
    apply_research_defaults('q088')


def initialize_research_selection(batch, bundle):
    """Seed once per batch; subsequent reruns preserve the user's edits."""
    profile = st.session_state.get('bt_winner_settings_profile')
    if profile not in ('q088', 'q051'):
        return
    # Migrate the previous Q051 0.60 defaults once, then preserve manual edits.
    version = '_050_20261108' if profile == 'q051' else ''
    marker = f'bt_research_selection_{profile}_{batch}{version}'
    if st.session_state.get(marker):
        return
    pool_key = f'bt_per_symbol_pool_{batch}' if bundle else f'bt_winner_top_{batch}_False'
    st.session_state[pool_key+'_mode'] = 'Pourcentage de l’univers'
    st.session_state[pool_key+'_pct'] = 10. if profile == 'q051' else 20.
    if bundle:
        count = 5 if profile == 'q051' else 10
        threshold = .5 if profile == 'q051' else .6
        st.session_state.update({
            f'bt_winner_per_symbol_long_{batch}': True,
            f'bt_per_symbol_allow_long_{batch}': True,
            f'bt_per_symbol_allow_short_{batch}': False,
            f'bt_per_symbol_top_long_{batch}': count,
            f'bt_per_symbol_top_long_{batch}_default10': True,
            f'bt_per_symbol_min_long_probability_{batch}': threshold,
            f'bt_per_symbol_auc_enabled_{batch}': True,
            f'bt_per_symbol_auc_enabled_{batch}_default_on': True,
            f'bt_per_symbol_min_long_auc_{batch}': threshold,
        })
    st.session_state[marker] = True


def apply_selected_profile():
    from ihm.components.winner_backtest_settings import reset_execution_settings
    reset_execution_settings(st.session_state['bt_winner_profile_choice'])


def render_profile_selector(profile):
    if 'bt_winner_profile_choice' not in st.session_state:
        st.session_state['bt_winner_profile_choice'] = profile
    selected = st.selectbox('Profil de paramètres du backtest', list(PROFILE_LABELS),
        format_func=PROFILE_LABELS.get, key='bt_winner_profile_choice',
        on_change=apply_selected_profile,
        help='Le choix charge les réglages du profil avant le formulaire. Ils restent ensuite modifiables.')
    st.info(PROFILE_DESCRIPTIONS[selected])
    st.caption('Les ajustements restent propres au backtest. Le modèle sélectionné et les dates sont conservés. '
               'Les profils Q051/Q088 ont été étudiés avec un bundle Oracle H10 + per-symbol.')
    st.button('Réappliquer le profil choisi', on_click=apply_selected_profile,
        key='bt_winner_profile_reload')
    return selected
