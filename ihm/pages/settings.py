"""ihm/pages/settings.py — Paramètres / Santé système."""
from __future__ import annotations

import os
import sys

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_connection_form
from ihm.components.status_badges import env_badge
from ihm.services.alpha_scanner_threshold_presets import (
    DEFAULT_MARKET_REGIME,
    DEFAULT_PRESET_STYLE,
    MARKET_REGIME_LABELS,
    PRESET_STYLE_LABELS,
    get_alpha_scanner_threshold_preset,
)
from ihm.services.db import db_available, get_db_status, reset_db_caches
from ihm.services.queries import (
    ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
    get_alpha_scanner_dependency_diagnostic,
    get_alpha_scanner_dependency_thresholds,
)
from ihm.services.screener_preferences import (
    load_persisted_alpha_scanner_dependency_preset_metadata,
    reset_persisted_alpha_scanner_dependency_thresholds,
    save_persisted_alpha_scanner_dependency_thresholds,
)

ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY = "settings_alpha_scanner_dependency_thresholds_flash"
ALPHA_SCANNER_SELECTED_STYLE_KEY = "settings_alpha_scanner_selected_style"
ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY = "settings_alpha_scanner_selected_market_regime"


def _threshold_widget_key(step_key: str, metric_key: str) -> str:
    return f"settings_alpha_scanner_threshold_{step_key}_{metric_key}"


def _prime_alpha_scanner_dependency_threshold_state() -> dict[str, dict[str, float]]:
    thresholds = get_alpha_scanner_dependency_thresholds()
    metadata = load_persisted_alpha_scanner_dependency_preset_metadata()
    if ALPHA_SCANNER_SELECTED_STYLE_KEY not in st.session_state:
        st.session_state[ALPHA_SCANNER_SELECTED_STYLE_KEY] = metadata.get("selected_style") or DEFAULT_PRESET_STYLE
    if ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY not in st.session_state:
        st.session_state[ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY] = metadata.get("selected_market_regime") or DEFAULT_MARKET_REGIME
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            widget_key = _threshold_widget_key(step_key, metric_key)
            if widget_key not in st.session_state:
                st.session_state[widget_key] = float(metric_value)
    return thresholds


def _collect_alpha_scanner_dependency_threshold_inputs() -> dict[str, dict[str, float]]:
    payload: dict[str, dict[str, float]] = {}
    for step_key, metrics in ALPHA_SCANNER_DEPENDENCY_THRESHOLDS.items():
        payload[step_key] = {}
        for metric_key, default_value in metrics.items():
            widget_key = _threshold_widget_key(step_key, metric_key)
            payload[step_key][metric_key] = float(st.session_state.get(widget_key, default_value))
    return payload


def _set_alpha_scanner_dependency_threshold_state(thresholds: dict[str, dict[str, float]]) -> None:
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            st.session_state[_threshold_widget_key(step_key, metric_key)] = float(metric_value)


def _apply_alpha_scanner_threshold_preset(style: str, market_regime: str) -> None:
    normalized = get_alpha_scanner_threshold_preset(
        style=style,  # type: ignore[arg-type]
        market_regime=market_regime,  # type: ignore[arg-type]
    )
    _set_alpha_scanner_dependency_threshold_state(normalized)
    save_persisted_alpha_scanner_dependency_thresholds(
        normalized,
        defaults=ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
        selected_style=style,
        selected_market_regime=market_regime,
        selection_mode="preset",
    )
    get_alpha_scanner_dependency_diagnostic.clear()
    reset_db_caches()
    st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = (
        f"Preset `{PRESET_STYLE_LABELS.get(style, style)}` appliqué pour `{MARKET_REGIME_LABELS.get(market_regime, market_regime)}`."
    )
    st.rerun()


def _render_alpha_scanner_dependency_threshold_settings() -> None:
    current_thresholds = _prime_alpha_scanner_dependency_threshold_state()
    preset_metadata = load_persisted_alpha_scanner_dependency_preset_metadata()
    flash_message = st.session_state.pop(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY, None)
    if isinstance(flash_message, str) and flash_message.strip():
        st.success(flash_message)

    st.subheader("🩺 Seuils diagnostic Alpha Scanner")
    st.caption(
        "Valeurs recommandées par défaut pour un style swing cash strict : quotes fraîches et bien couvertes, horizon earnings suffisant, couverture earnings minimale mais non triviale."
    )
    st.info(
        "Le bon réglage est en pratique le croisement de **2 axes** : le style opératoire (`swing cash pro`, `agressif`, `tolérant`) ET le régime de marché (`normal`, `faible`, `très sélectif`)."
    )

    selected_market_regime = st.radio(
        "Régime de marché pour les presets",
        options=list(MARKET_REGIME_LABELS.keys()),
        index=list(MARKET_REGIME_LABELS.keys()).index(
            str(st.session_state.get(ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY, DEFAULT_MARKET_REGIME))
            if st.session_state.get(ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY, DEFAULT_MARKET_REGIME) in MARKET_REGIME_LABELS
            else DEFAULT_MARKET_REGIME
        ),
        format_func=lambda value: MARKET_REGIME_LABELS[value],
        key=ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY,
        horizontal=True,
    )

    selected_style = str(st.session_state.get(ALPHA_SCANNER_SELECTED_STYLE_KEY, DEFAULT_PRESET_STYLE) or DEFAULT_PRESET_STYLE)
    selection_mode = str(preset_metadata.get("selection_mode") or "custom")
    st.caption(
        f"Preset mémorisé : `{PRESET_STYLE_LABELS.get(selected_style, selected_style)}` × `{MARKET_REGIME_LABELS.get(selected_market_regime, selected_market_regime)}` | mode=`{selection_mode}`"
    )

    preset_col1, preset_col2, preset_col3 = st.columns(3)
    preset_buttons = (
        (preset_col1, "swing_cash_pro", "🛡️ Appliquer preset Swing Cash Pro"),
        (preset_col2, "aggressive", "⚡ Appliquer preset Agressif"),
        (preset_col3, "tolerant", "🟨 Appliquer preset Tolérant"),
    )
    for column, style_key, label in preset_buttons:
        with column:
            st.caption(PRESET_STYLE_LABELS[style_key])
            if st.button(label, key=f"apply_alpha_scanner_preset_{style_key}", use_container_width=True):
                st.session_state[ALPHA_SCANNER_SELECTED_STYLE_KEY] = style_key
                _apply_alpha_scanner_threshold_preset(style_key, selected_market_regime)

    quotes_col1, quotes_col2 = st.columns(2)
    with quotes_col1:
        st.markdown("**Sync Latest Quotes — recommandé swing cash pro**")
        st.number_input(
            "Quotes — couverture orange (%)",
            min_value=0.0,
            value=float(current_thresholds["sync_latest_quotes"]["coverage_warn_pct"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_latest_quotes", "coverage_warn_pct"),
        )
        st.number_input(
            "Quotes — couverture rouge (%)",
            min_value=0.0,
            value=float(current_thresholds["sync_latest_quotes"]["coverage_error_pct"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_latest_quotes", "coverage_error_pct"),
        )
        st.caption("Proposition par défaut : orange < 85%, rouge < 60%.")
    with quotes_col2:
        st.markdown("**Fraîcheur quotes**")
        st.number_input(
            "Quotes — âge orange (jours)",
            min_value=0.0,
            value=float(current_thresholds["sync_latest_quotes"]["max_age_warn_days"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_latest_quotes", "max_age_warn_days"),
        )
        st.number_input(
            "Quotes — âge rouge (jours)",
            min_value=0.0,
            value=float(current_thresholds["sync_latest_quotes"]["max_age_error_days"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_latest_quotes", "max_age_error_days"),
        )
        st.caption("Proposition par défaut : orange > 1 jour, rouge > 3 jours.")

    earnings_col1, earnings_col2 = st.columns(2)
    with earnings_col1:
        st.markdown("**Sync Earnings Calendar — recommandé swing cash pro**")
        st.number_input(
            "Earnings — couverture orange (%)",
            min_value=0.0,
            value=float(current_thresholds["sync_earnings_calendar"]["coverage_warn_pct"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_earnings_calendar", "coverage_warn_pct"),
        )
        st.number_input(
            "Earnings — couverture rouge (%)",
            min_value=0.0,
            value=float(current_thresholds["sync_earnings_calendar"]["coverage_error_pct"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_earnings_calendar", "coverage_error_pct"),
        )
        st.caption("Proposition par défaut : orange < 15%, rouge < 5%.")
    with earnings_col2:
        st.markdown("**Horizon earnings**")
        st.number_input(
            "Earnings — horizon orange (jours)",
            min_value=0.0,
            value=float(current_thresholds["sync_earnings_calendar"]["min_horizon_warn_days"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_earnings_calendar", "min_horizon_warn_days"),
        )
        st.number_input(
            "Earnings — horizon rouge (jours)",
            min_value=0.0,
            value=float(current_thresholds["sync_earnings_calendar"]["min_horizon_error_days"]),
            step=1.0,
            format="%.1f",
            key=_threshold_widget_key("sync_earnings_calendar", "min_horizon_error_days"),
        )
        st.caption("Proposition par défaut : orange si l'horizon futur est < 14 jours, rouge si < 7 jours.")

    action_col1, action_col2 = st.columns([2, 1])
    with action_col1:
        if st.button("💾 Enregistrer les seuils Alpha Scanner", key="settings_save_alpha_scanner_thresholds", use_container_width=True):
            normalized = save_persisted_alpha_scanner_dependency_thresholds(
                _collect_alpha_scanner_dependency_threshold_inputs(),
                defaults=ALPHA_SCANNER_DEPENDENCY_THRESHOLDS,
                selected_style=str(st.session_state.get(ALPHA_SCANNER_SELECTED_STYLE_KEY, DEFAULT_PRESET_STYLE)),
                selected_market_regime=str(st.session_state.get(ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY, DEFAULT_MARKET_REGIME)),
                selection_mode="custom",
            )
            _set_alpha_scanner_dependency_threshold_state(normalized)
            get_alpha_scanner_dependency_diagnostic.clear()
            reset_db_caches()
            st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils Alpha Scanner enregistrés."
            st.rerun()
    with action_col2:
        if st.button("↩️ Reset défauts", key="settings_reset_alpha_scanner_thresholds", use_container_width=True):
            reset_persisted_alpha_scanner_dependency_thresholds()
            _set_alpha_scanner_dependency_threshold_state(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS)
            st.session_state[ALPHA_SCANNER_SELECTED_STYLE_KEY] = DEFAULT_PRESET_STYLE
            st.session_state[ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY] = DEFAULT_MARKET_REGIME
            get_alpha_scanner_dependency_diagnostic.clear()
            reset_db_caches()
            st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils Alpha Scanner réinitialisés aux valeurs recommandées."
            st.rerun()


def _check_import(name: str) -> str:
    try:
        __import__(name)
        return f"🟢 `{name}` — OK"
    except ImportError:
        return f"🔴 `{name}` — **MANQUANT**"


def render() -> None:
    st.header("⚙️ Paramètres / Santé")

    # --- Variables d'environnement ---
    st.subheader("🔑 Variables d'environnement")
    for var in ("LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY"):
        st.markdown(env_badge(var, os.getenv(var)))

    # --- DB ---
    st.subheader("🗄️ Connexion DB")
    render_db_connection_form("settings_db_connection_form", show_host_fields=True)

    status = get_db_status()
    if db_available():
        st.success("🟢 Connexion MySQL OK")
    else:
        st.error("🔴 Connexion MySQL échouée. Vérifiez LOGIN_DB, PASSWORD_DB et que MySQL est démarré.")
    st.caption(
        f"Source active : `{status.get('source')}` — cible : `{status.get('host')}/{status.get('name')}`"
    )
    if status.get("last_query_error"):
        st.warning(str(status.get("last_query_error")))

    _render_alpha_scanner_dependency_threshold_settings()

    # --- Système ---
    st.subheader("🖥️ Système")
    st.text(f"Python : {sys.version}")
    st.text(f"Répertoire : {os.getcwd()}")

    # --- Dépendances ---
    st.subheader("📦 Dépendances critiques")
    for pkg in ("streamlit", "sqlalchemy", "pandas", "pymysql", "numpy", "torch", "transformers"):
        st.markdown(_check_import(pkg))

    # --- Rappel ---
    st.subheader("🚀 Commande de lancement")
    st.code("python -m streamlit run ihm/app.py", language="powershell")


run_page_if_standalone(__name__, render)


