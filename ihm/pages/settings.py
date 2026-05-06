"""ihm/pages/settings.py — Paramètres / Santé système."""
from __future__ import annotations

import os
import sys

import streamlit as st

from ihm.pages import run_page_if_standalone
from ihm.components.db_controls import render_db_connection_form
from ihm.components.ops_command_panel import render_ops_command_panel
from ihm.components.status_badges import env_badge
from ihm.services.alpha_scanner_threshold_presets import (
    DEFAULT_MARKET_REGIME,
    DEFAULT_PRESET_STYLE,
    MARKET_REGIME_LABELS,
    PRESET_STYLE_LABELS,
    get_alpha_scanner_threshold_preset,
)
from ihm.services.db import db_available, get_db_status, reset_db_caches
from ihm.services.market_data_provider import (
    CONFIG_PATH as MARKET_DATA_CONFIG_PATH,
    DEFAULT_BARS_PROVIDER,
    get_bars_provider,
    set_bars_provider,
)
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
ALPHA_SCANNER_PENDING_THRESHOLDS_KEY = "settings_alpha_scanner_pending_thresholds"
ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY = "settings_alpha_scanner_pending_market_regime"
BARS_PROVIDER_FLASH_KEY = "settings_bars_provider_flash"
BARS_PROVIDER_WIDGET_KEY = "settings_bars_provider_radio"
BARS_PROVIDER_PENDING_SYNC_KEY = "settings_bars_provider_pending_sync"

BARS_PROVIDER_LABELS: dict[str, str] = {
    "eodhd": "🟢 EODHD (recommandé — bulk EOD, volume consolidé)",
    "alpaca": "🟡 Alpaca / IEX (historique, biais volume IEX)",
}
BARS_PROVIDER_HELP: dict[str, str] = {
    "eodhd": (
        "Source primaire = EODHD `/eod-bulk-last-day/US`. Backfill historique disponible via "
        "l'étape auxiliaire B3 de la page Pipeline. Cross-check Stooq actif. Quotes RT et exécution restent sur Alpaca."
    ),
    "alpaca": (
        "Source primaire = Alpaca/IEX (comportement historique). EODHD inutilisé. "
        "Aucun cross-check Stooq. À réserver aux tests de non-régression."
    ),
}


def _prime_bars_provider_widget_state(current: str) -> str:
    options = list(BARS_PROVIDER_LABELS.keys())
    initial = current if current in options else DEFAULT_BARS_PROVIDER
    pending = st.session_state.pop(BARS_PROVIDER_PENDING_SYNC_KEY, None)
    if isinstance(pending, str) and pending in options:
        st.session_state[BARS_PROVIDER_WIDGET_KEY] = pending
        return pending

    selected = st.session_state.get(BARS_PROVIDER_WIDGET_KEY)
    if selected not in options:
        st.session_state[BARS_PROVIDER_WIDGET_KEY] = initial
        return initial

    return str(selected)


def _render_bars_provider_settings() -> None:
    flash = st.session_state.pop(BARS_PROVIDER_FLASH_KEY, None)
    if isinstance(flash, tuple) and len(flash) == 2:
        kind, message = flash
        getattr(st, kind, st.info)(message)

    current = get_bars_provider()
    st.subheader("📡 Source primaire des barres OHLCV")
    st.caption(
        "Définit `market_data.bars_provider` dans `config.yaml`. Toutes les étapes pipeline IHM "
        "(`Import Bars`, `corporate_actions_sync`, backfill historique) routent automatiquement "
        "vers le provider choisi. La metadata, les quotes temps réel et l'exécution restent sur Alpaca."
    )

    options = list(BARS_PROVIDER_LABELS.keys())  # eodhd d'abord (défaut recommandé)
    _prime_bars_provider_widget_state(current)

    with st.container(border=True):
        selected = st.radio(
            "Provider actif",
            options=options,
            format_func=lambda value: BARS_PROVIDER_LABELS.get(value, value),
            key=BARS_PROVIDER_WIDGET_KEY,
            horizontal=False,
        )
        st.caption(BARS_PROVIDER_HELP.get(selected, ""))
        st.caption(
            f"Valeur persistée actuelle : `{current}` — défaut recommandé : `{DEFAULT_BARS_PROVIDER}`"
            f" — fichier : `{MARKET_DATA_CONFIG_PATH.name}`"
        )

        action_col1, action_col2 = st.columns([2, 1])
        with action_col1:
            disabled = (selected == current)
            if st.button(
                "💾 Enregistrer le provider",
                key="settings_save_bars_provider",
                use_container_width=True,
                disabled=disabled,
                help="Inactif tant que la sélection est identique à la valeur persistée." if disabled else None,
            ):
                try:
                    applied = set_bars_provider(selected)
                except (OSError, ValueError) as exc:
                    st.session_state[BARS_PROVIDER_FLASH_KEY] = (
                        "error",
                        f"Échec écriture `config.yaml` : {exc}",
                    )
                else:
                    st.session_state[BARS_PROVIDER_PENDING_SYNC_KEY] = applied
                    st.session_state[BARS_PROVIDER_FLASH_KEY] = (
                        "success",
                        f"Provider mis à jour : `{applied}`. Relance des pipelines IHM nécessaire pour prise en compte.",
                    )
                st.rerun()
        with action_col2:
            if st.button(
                "↩️ Reset défaut (EODHD)",
                key="settings_reset_bars_provider",
                use_container_width=True,
                disabled=(current == DEFAULT_BARS_PROVIDER),
            ):
                try:
                    set_bars_provider(DEFAULT_BARS_PROVIDER)
                except (OSError, ValueError) as exc:
                    st.session_state[BARS_PROVIDER_FLASH_KEY] = ("error", f"Échec reset : {exc}")
                else:
                    st.session_state[BARS_PROVIDER_PENDING_SYNC_KEY] = DEFAULT_BARS_PROVIDER
                    st.session_state[BARS_PROVIDER_FLASH_KEY] = (
                        "success",
                        f"Provider réinitialisé sur `{DEFAULT_BARS_PROVIDER}` (défaut recommandé).",
                    )
                st.rerun()


def _threshold_widget_key(step_key: str, metric_key: str) -> str:
    return f"settings_alpha_scanner_threshold_{step_key}_{metric_key}"


def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds: dict[str, dict[str, float]]) -> None:
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            st.session_state[_threshold_widget_key(step_key, metric_key)] = float(metric_value)


def _prime_alpha_scanner_dependency_threshold_state() -> dict[str, dict[str, float]]:
    thresholds = get_alpha_scanner_dependency_thresholds()
    metadata = load_persisted_alpha_scanner_dependency_preset_metadata()
    pending_market_regime = st.session_state.pop(ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY, None)
    if isinstance(pending_market_regime, str) and pending_market_regime in MARKET_REGIME_LABELS:
        st.session_state[ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY] = pending_market_regime
    if ALPHA_SCANNER_SELECTED_STYLE_KEY not in st.session_state:
        st.session_state[ALPHA_SCANNER_SELECTED_STYLE_KEY] = metadata.get("selected_style") or DEFAULT_PRESET_STYLE
    if ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY not in st.session_state:
        st.session_state[ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY] = metadata.get("selected_market_regime") or DEFAULT_MARKET_REGIME
    pending_thresholds = st.session_state.pop(ALPHA_SCANNER_PENDING_THRESHOLDS_KEY, None)
    if isinstance(pending_thresholds, dict) and pending_thresholds:
        _apply_alpha_scanner_dependency_threshold_state_to_session(pending_thresholds)
        thresholds = pending_thresholds
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
    _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds)


def _apply_alpha_scanner_threshold_preset(style: str, market_regime: str) -> None:
    normalized = get_alpha_scanner_threshold_preset(
        style=style,  # type: ignore[arg-type]
        market_regime=market_regime,  # type: ignore[arg-type]
    )
    st.session_state[ALPHA_SCANNER_SELECTED_STYLE_KEY] = style
    st.session_state[ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY] = market_regime
    st.session_state[ALPHA_SCANNER_PENDING_THRESHOLDS_KEY] = normalized
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
        "Ordre opératoire couvert ici : étape 4 `Sync Latest Quotes` → étape 5 `Sync Earnings Calendar` → étape 6 `Alpha Scanner`."
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
    with st.container(border=True):
        st.markdown("**Étape 6 — Gouvernance opérateur du diagnostic partagé**")
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
                    _apply_alpha_scanner_threshold_preset(style_key, selected_market_regime)

    with st.container(border=True):
        st.markdown("**Étape 4 — Sync Latest Quotes**")
        st.caption("Quotes fraîches et bien couvertes pour garder un filtre de spread exploitable en swing cash.")
        quotes_col1, quotes_col2 = st.columns(2)
        with quotes_col1:
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

    with st.container(border=True):
        st.markdown("**Étape 5 — Sync Earnings Calendar**")
        st.caption("Horizon earnings futur suffisant pour que le blackout résultats reste fiable côté Alpha Scanner.")
        earnings_col1, earnings_col2 = st.columns(2)
        with earnings_col1:
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

    with st.container(border=True):
        st.markdown("**Validation opérateur**")
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
                st.session_state[ALPHA_SCANNER_PENDING_THRESHOLDS_KEY] = normalized
                get_alpha_scanner_dependency_diagnostic.clear()
                reset_db_caches()
                st.session_state[ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY] = "Seuils Alpha Scanner enregistrés."
                st.rerun()
        with action_col2:
            if st.button("↩️ Reset défauts", key="settings_reset_alpha_scanner_thresholds", use_container_width=True):
                reset_persisted_alpha_scanner_dependency_thresholds()
                st.session_state[ALPHA_SCANNER_PENDING_THRESHOLDS_KEY] = ALPHA_SCANNER_DEPENDENCY_THRESHOLDS
                st.session_state[ALPHA_SCANNER_SELECTED_STYLE_KEY] = DEFAULT_PRESET_STYLE
                st.session_state[ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY] = DEFAULT_MARKET_REGIME
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
    st.caption(
        "Page recentrée sur les prérequis opérateur puis sur les paramètres réellement utilisés par le flux `quotes → earnings → alpha scanner`."
    )

    prereq_col1, prereq_col2 = st.columns(2)
    with prereq_col1:
        with st.container(border=True):
            st.subheader("🔑 Variables d'environnement")
            for var in ("LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY"):
                st.markdown(env_badge(var, os.getenv(var)))
    with prereq_col2:
        with st.container(border=True):
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

    st.subheader("🧭 Paramétrage pipeline")
    _render_bars_provider_settings()
    _render_alpha_scanner_dependency_threshold_settings()

    # ---- Sprint S26 (gap P3) — Maintenance & sécurité ops ------------
    st.subheader("🧹 Maintenance & sécurité ops")
    st.caption(
        "Lancement direct des scripts ops `prune_artifacts` et "
        "`verify_vault_rotation`. Chaque run est tracé dans "
        "`artifacts/ihm_pipeline_runs/` (préfixe `ops:`)."
    )
    ops_tabs = st.tabs(["🧹 Nettoyage artefacts", "🗝️ Rotation des secrets"])
    with ops_tabs[0]:
        apply_changes = st.checkbox(
            "Appliquer les suppressions (sinon dry-run)",
            value=False,
            key="settings_prune_artifacts_apply",
        )
        render_ops_command_panel(
            "prune_artifacts",
            confirm_phrase="PRUNE" if apply_changes else None,
            command_kwargs={"apply_changes": apply_changes},
        )
    with ops_tabs[1]:
        render_ops_command_panel("verify_vault_rotation")

    with st.expander("🖥️ Diagnostic environnement Python", expanded=False):
        st.text(f"Python : {sys.version}")
        st.text(f"Répertoire : {os.getcwd()}")

        st.markdown("**📦 Dépendances critiques**")
        for pkg in ("streamlit", "sqlalchemy", "pandas", "pymysql", "numpy", "torch", "transformers"):
            st.markdown(_check_import(pkg))

        st.markdown("**🚀 Commande de lancement**")
        st.code("python -m streamlit run ihm/app.py", language="powershell")


run_page_if_standalone(__name__, render)


