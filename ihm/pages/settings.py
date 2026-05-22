"""ihm/pages/settings.py — Paramètres / Santé système."""
from __future__ import annotations

import os
import sys
import hashlib

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
from ihm.services.notifications_preferences import (
    ALLOWED_STATUSES,
    DEFAULT_NOTIFY_ON,
    NOTIFICATIONS_PREFERENCES_PATH,
    NotificationPreferences,
    format_recipients,
    load_persisted_notification_preferences,
    parse_recipients,
    save_persisted_notification_preferences,
)
from ihm.services.notifications import load_smtp_config, read_smtp_test_failure_log, send_test_email
from ihm.services.capital_presets import get_capital_preset_by_key

ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY = "settings_alpha_scanner_dependency_thresholds_flash"
ALPHA_SCANNER_SELECTED_STYLE_KEY = "settings_alpha_scanner_selected_style"
ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY = "settings_alpha_scanner_selected_market_regime"
ALPHA_SCANNER_PENDING_THRESHOLDS_KEY = "settings_alpha_scanner_pending_thresholds"
ALPHA_SCANNER_PENDING_MARKET_REGIME_KEY = "settings_alpha_scanner_pending_market_regime"
BARS_PROVIDER_FLASH_KEY = "settings_bars_provider_flash"
BARS_PROVIDER_WIDGET_KEY = "settings_bars_provider_radio"
BARS_PROVIDER_PENDING_SYNC_KEY = "settings_bars_provider_pending_sync"

NOTIFICATIONS_RECIPIENTS_KEY = "settings_notifications_recipients_input"
NOTIFICATIONS_ENABLED_KEY = "settings_notifications_enabled_input"
NOTIFICATIONS_NOTIFY_ON_KEY = "settings_notifications_notify_on_input"
NOTIFICATIONS_FLASH_KEY = "settings_notifications_flash"
VAR_ENV_UPLOAD_SIGNATURE_KEY = "settings_var_env_upload_signature"
VAR_ENV_UPLOAD_RESULT_KEY = "settings_var_env_upload_result"
VAR_ENV_EXPORT_DATA_KEY = "settings_var_env_export_data"
VAR_ENV_EXPORT_FILENAME_KEY = "settings_var_env_export_filename"
MICRO_CAPITAL_PRESET_KEY = "capital_0_2000_eur"

VAR_ENV_UPLOAD_WIDGET_CSS = """
<style>
div[data-testid="stFileUploader"] {
    width: 100%;
}

div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] {
    min-height: 3rem;
    padding: 0.35rem 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(49, 51, 63, 0.2);
    border-radius: 0.5rem;
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(240,242,246,0.08));
    transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
    cursor: pointer;
}

div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"]:hover {
    border-color: rgba(255, 75, 75, 0.45);
    box-shadow: 0 0 0 0.08rem rgba(255, 75, 75, 0.12);
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(240,242,246,0.14));
}

div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] > div,
div[data-testid="stFileUploader"] small,
div[data-testid="stFileUploader"] button {
    display: none;
}

div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"]::after {
    content: "⬆️ Charger les variables d'environnement";
    display: block;
    text-align: center;
    font-size: 0.95rem;
    font-weight: 500;
    letter-spacing: 0.01em;
}
</style>
"""

BARS_PROVIDER_LABELS: dict[str, str] = {
    "eodhd": " EODHD (recommandé — bulk EOD, volume consolidé)",
    "alpaca": " Alpaca / IEX (historique, biais volume IEX)",
}
_MARKET_REGIME_LABELS_STR = {str(key): value for key, value in MARKET_REGIME_LABELS.items()}
_PRESET_STYLE_LABELS_STR = {str(key): value for key, value in PRESET_STYLE_LABELS.items()}
BARS_PROVIDER_HELP: dict[str, str] = {
    "eodhd": (
        "Source primaire = EODHD `/eod-bulk-last-day/US`. Backfill historique disponible via "
        "l'étape auxiliaire B3 de la page Pipeline. Cross-check Stooq actif. Quotes RT et exécution restent sur Alpaca. "
        "Aucun fallback automatique vers Alpaca n'est effectué si EODHD échoue."
    ),
    "alpaca": (
        "Source primaire = Alpaca/IEX (comportement historique). EODHD inutilisé. "
        "Aucun cross-check Stooq. À réserver aux tests de non-régression. Si `bars_provider=eodhd`, "
        "le module Alpaca daily devient un no-op contrôlé."
    ),
}


def _build_micro_capital_preset_warning_message() -> str | None:
    preset = get_capital_preset_by_key(MICRO_CAPITAL_PRESET_KEY)
    if preset is None:
        return None
    return (
        f"⚠️ Le preset `{preset.label}` assume une concentration maximale : "
        "3 lignes, tickets élevés relativement à l'equity et univers selector volontairement relâché. "
        "À utiliser avec une discipline stricte sur la taille et les frais."
    )


def _render_capital_preset_warning_banner() -> None:
    message = _build_micro_capital_preset_warning_message()
    if message:
        st.warning(message)


def _flash_message(kind: str, message: str) -> None:
    if kind == "error":
        st.error(message)
    elif kind == "success":
        st.success(message)
    elif kind == "warning":
        st.warning(message)
    else:
        st.info(message)


def _market_regime_label(value: str) -> str:
    return _MARKET_REGIME_LABELS_STR.get(value, value)


def _preset_style_label(value: str) -> str:
    return _PRESET_STYLE_LABELS_STR.get(value, value)


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


def _render_bars_provider_settings():
    flash = st.session_state.pop(BARS_PROVIDER_FLASH_KEY, None)
    if isinstance(flash, tuple) and len(flash) == 2:
        kind, message = flash
        _flash_message(str(kind), str(message))

    current = get_bars_provider()
    st.subheader(" Source primaire des barres OHLCV")
    st.caption(
        "Définit `market_data.bars_provider` dans `config.yaml`. Toutes les étapes pipeline IHM "
        "(`Import Bars`, `corporate_actions_sync`, backfill historique) routent automatiquement "
        "vers le provider choisi. La metadata, les quotes temps réel et l'exécution restent sur Alpaca. "
        "Le basculement est explicite : aucun fallback automatique inter-provider n'est supporté."
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
        st.info(
            "Mode opératoire recommandé : **EODHD primaire** pour les barres daily ; **Alpaca/IEX** seulement en rétrocompatibilité. "
            "Quand EODHD est actif, `import_alpaca_bar` doit être compris comme un no-op contrôlé."
        )
        st.caption(
            f"Valeur persistée actuelle : `{current}` — défaut recommandé : `{DEFAULT_BARS_PROVIDER}`"
            f" — fichier : `{MARKET_DATA_CONFIG_PATH.name}`"
        )

        action_col1, action_col2 = st.columns([2, 1])
        with action_col1:
            disabled = (selected == current)
            if st.button(
                " Enregistrer le provider",
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


def _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds):
    for step_key, metrics in thresholds.items():
        for metric_key, metric_value in metrics.items():
            st.session_state[_threshold_widget_key(step_key, metric_key)] = float(metric_value)


def _prime_alpha_scanner_dependency_threshold_state():
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


def _collect_alpha_scanner_dependency_threshold_inputs():
    payload = {}
    for step_key, metrics in ALPHA_SCANNER_DEPENDENCY_THRESHOLDS.items():
        payload[step_key] = {}
        for metric_key, default_value in metrics.items():
            widget_key = _threshold_widget_key(step_key, metric_key)
            payload[step_key][metric_key] = float(st.session_state.get(widget_key, default_value))
    return payload


def _set_alpha_scanner_dependency_threshold_state(thresholds):
    _apply_alpha_scanner_dependency_threshold_state_to_session(thresholds)


def _apply_alpha_scanner_threshold_preset(style: str, market_regime: str):
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
        f"Preset `{_preset_style_label(style)}` appliqué pour `{_market_regime_label(market_regime)}`."
    )
    st.rerun()


def _render_alpha_scanner_dependency_threshold_settings():
    current_thresholds = _prime_alpha_scanner_dependency_threshold_state()
    preset_metadata = load_persisted_alpha_scanner_dependency_preset_metadata()
    flash_message = st.session_state.pop(ALPHA_SCANNER_DEPENDENCY_THRESHOLDS_FLASH_KEY, None)
    if isinstance(flash_message, str) and flash_message.strip():
        st.success(flash_message)

    st.subheader(" Seuils diagnostic Alpha Scanner")
    st.caption(
        "Ordre opératoire couvert ici : étape 4 `Sync Latest Quotes` → étape 5 `Sync Earnings Calendar` → étape 6 `Alpha Scanner`."
    )
    st.info(
        "Le bon réglage est en pratique le croisement de **2 axes** : le style opératoire (`swing cash pro`, `agressif`, `tolérant`) ET le régime de marché (`normal`, `faible`, `très sélectif`)."
    )
    st.caption(
        "⚠️ Ce bloc concerne **uniquement les presets de seuils du diagnostic Alpha Scanner** "
        "(fraîcheur / couverture quotes + earnings). Ce n'est **pas** le même mécanisme que le "
        "mode régime market-aware d'exécution (`normal` / `capital_preservation` / `close_only` / `cash_only`)."
    )

    selected_market_regime_value = st.session_state.get(
        ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY,
        DEFAULT_MARKET_REGIME,
    )
    selected_market_regime_default = (
        str(selected_market_regime_value)
        if str(selected_market_regime_value) in MARKET_REGIME_LABELS
        else DEFAULT_MARKET_REGIME
    )
    selected_market_regime = st.radio(
        "Contexte marché pour les presets Alpha Scanner",
        options=list(MARKET_REGIME_LABELS.keys()),
        index=list(_MARKET_REGIME_LABELS_STR.keys()).index(selected_market_regime_default),
        format_func=_market_regime_label,
        key=ALPHA_SCANNER_SELECTED_MARKET_REGIME_KEY,
        horizontal=True,
    )

    selected_style = str(st.session_state.get(ALPHA_SCANNER_SELECTED_STYLE_KEY, DEFAULT_PRESET_STYLE) or DEFAULT_PRESET_STYLE)
    selection_mode = str(preset_metadata.get("selection_mode") or "custom")
    with st.container(border=True):
        st.markdown("**Étape 6 — Gouvernance opérateur du diagnostic partagé**")
        st.caption(
            f"Preset mémorisé : `{_preset_style_label(selected_style)}` × `{_market_regime_label(selected_market_regime)}` | mode=`{selection_mode}`"
        )
        preset_col1, preset_col2, preset_col3 = st.columns(3)
        preset_buttons = (
            (preset_col1, "swing_cash_pro", "️ Appliquer preset Swing Cash Pro"),
            (preset_col2, "aggressive", "⚡ Appliquer preset Agressif"),
            (preset_col3, "tolerant", " Appliquer preset Tolérant"),
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
            if st.button(" Enregistrer les seuils Alpha Scanner", key="settings_save_alpha_scanner_thresholds", use_container_width=True):
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


def _get_notifications_failure_log_download_payload():
    payload = read_smtp_test_failure_log()
    if not payload.strip():
        return None
    return ("smtp_test_email_failure.log", payload)


def _build_smtp_not_configured_warning_message(smtp_cfg) -> str | None:
    if getattr(smtp_cfg, "is_configured", False):
        return None
    return (
        "SMTP non configuré → aucune notification email ne sera envoyée, même si des destinataires sont enregistrés dans l'IHM. "
        "Renseignez les variables `ALPHA_TRADE_SMTP_*` ou la section `notifications.smtp` de `config.yaml`."
    )


def _build_var_env_upload_signature(file_name: str, file_bytes: bytes) -> str:
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{file_name}:{len(file_bytes)}:{digest}"


def _prepare_var_env_export():
    from ihm.services.varEnv import get_var_env_streamlit

    # Génère le CSV en mémoire (BytesIO)
    csv_bytesio = get_var_env_streamlit()
    csv_bytesio.seek(0)
    csv_data = csv_bytesio.read()
    return {"file_name": "var_env.csv", "data": csv_data}


def _render_environment_variable_settings():
    st.subheader(" Variables d'environnement")
    for var in ("LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "FINNHUB_API_KEY"):
        st.markdown(env_badge(var, os.getenv(var)))

    try:
        from ihm.services.varEnv import get_conf_var_env, set_var_env
    except Exception:
        st.error("Module `ihm.services.varEnv` introuvable. Vérifiez le nom du fichier et le path.")
        return

    st.markdown(VAR_ENV_UPLOAD_WIDGET_CSS, unsafe_allow_html=True)

    col_env1, col_env2 = st.columns(2)
    with col_env1:
        with st.container(border=True):
            st.caption("Télécharge le CSV des variables d'environnement autorisées.")
            if st.button(
                "Préparer le téléchargement",
                key="prepare_recuperer_var_env",
                use_container_width=True,
                help="Génère le fichier CSV filtré par `conf/var_env.json`.",
            ):
                try:
                    export_payload = _prepare_var_env_export()
                except Exception as exc:
                    st.session_state.pop(VAR_ENV_EXPORT_DATA_KEY, None)
                    st.session_state.pop(VAR_ENV_EXPORT_FILENAME_KEY, None)
                    st.error(f"Échec génération du CSV : {exc}")
                else:
                    st.session_state[VAR_ENV_EXPORT_DATA_KEY] = export_payload["data"]
                    st.session_state[VAR_ENV_EXPORT_FILENAME_KEY] = export_payload["file_name"]

            export_data = st.session_state.get(VAR_ENV_EXPORT_DATA_KEY)
            export_file_name = st.session_state.get(VAR_ENV_EXPORT_FILENAME_KEY, "var_env.csv")
            if export_data is not None:
                st.download_button(
                    label="Télécharger les variables d'environnement",
                    data=export_data,
                    file_name=export_file_name,
                    mime="text/csv",
                    key="download_recuperer_var_env",
                    use_container_width=True,
                    help="Télécharge le dernier CSV préparé.",
                )
            else:
                st.caption(
                    "Cliquez d'abord sur **Préparer le téléchargement** pour générer le CSV."
                )

    with col_env2:
        with st.container(border=True):
            st.caption("Importe un CSV `Variable,Valeur` puis applique les clés autorisées.")
            uploaded = st.file_uploader(
                "Charger les variables d'environnement",
                type="csv",
                key="upload_var_env",
                accept_multiple_files=False,
                label_visibility="collapsed",
                help="Sélectionnez un CSV au format `Variable,Valeur`.",
            )

            current_result = None
            if uploaded is not None:
                try:
                    file_bytes = uploaded.getvalue()
                except Exception as exc:
                    st.error(f"Échec lecture du fichier uploadé : {exc}")
                    file_bytes = b""

                if not file_bytes:
                    st.warning("Le fichier sélectionné est vide.")
                else:
                    signature = _build_var_env_upload_signature(uploaded.name or "var_env.csv", file_bytes)
                    if st.session_state.get(VAR_ENV_UPLOAD_SIGNATURE_KEY) != signature:
                        try:
                            current_result = set_var_env(file_bytes, apply=True)
                        except Exception as exc:
                            current_result = {"error": str(exc)}
                        st.session_state[VAR_ENV_UPLOAD_SIGNATURE_KEY] = signature
                        st.session_state[VAR_ENV_UPLOAD_RESULT_KEY] = current_result

            upload_result = current_result or st.session_state.get(VAR_ENV_UPLOAD_RESULT_KEY)
            if isinstance(upload_result, dict):
                error_message = upload_result.get("error")
                if error_message:
                    st.error(f"Échec traitement du fichier CSV : {error_message}")
                else:
                    applied = upload_result.get("applied", {})
                    if applied:
                        st.info(
                            "Import réussi."
                        )
                    elif uploaded is not None:
                        st.info("Aucune variable autorisée n'a été appliquée depuis le fichier importé.")


def _render_notifications_settings():
    """Sprint S27 — Notifications email fin de workflow pipeline."""
    flash = st.session_state.pop(NOTIFICATIONS_FLASH_KEY, None)
    failure_log_payload = _get_notifications_failure_log_download_payload()
    if isinstance(flash, tuple) and len(flash) == 2:
        kind, message = flash
        _flash_message(str(kind), str(message))
        if kind == "error" and failure_log_payload is not None:
            st.download_button(
                "⬇️ Télécharger les logs IHM de l'échec SMTP",
                data=failure_log_payload[1],
                file_name=failure_log_payload[0],
                mime="text/plain",
                key="settings_notifications_download_failure_log_flash",
                use_container_width=False,
            )

    prefs = load_persisted_notification_preferences()
    smtp_cfg = load_smtp_config()

    st.subheader(" Notifications email — fin de workflow pipeline")
    st.caption(
        "À chaque fin de run pipeline (succès, échec, timeout, arrêt), un email est "
        "envoyé aux destinataires configurés. En cas d'échec, l'email contient le nom "
        "de l'étape fautive, un extrait des logs et joint le `combined.log` complet."
    )
    smtp_warning = _build_smtp_not_configured_warning_message(smtp_cfg)
    if smtp_warning:
        st.warning(smtp_warning)

    if NOTIFICATIONS_RECIPIENTS_KEY not in st.session_state:
        st.session_state[NOTIFICATIONS_RECIPIENTS_KEY] = format_recipients(prefs.recipients)
    if NOTIFICATIONS_ENABLED_KEY not in st.session_state:
        st.session_state[NOTIFICATIONS_ENABLED_KEY] = bool(prefs.enabled)
    if NOTIFICATIONS_NOTIFY_ON_KEY not in st.session_state:
        st.session_state[NOTIFICATIONS_NOTIFY_ON_KEY] = list(prefs.notify_on)

    with st.container(border=True):
        st.checkbox(
            "Activer les notifications email",
            key=NOTIFICATIONS_ENABLED_KEY,
            help="Décochez pour suspendre les envois sans perdre la configuration.",
        )
        st.text_input(
            "Destinataires",
            key=NOTIFICATIONS_RECIPIENTS_KEY,
            help="Plusieurs adresses peuvent être saisies, séparées par un point-virgule (;).",
            placeholder="exemple@gmail.com;autre@domaine.fr",
        )
        st.multiselect(
            "Statuts déclencheurs",
            options=sorted(ALLOWED_STATUSES),
            key=NOTIFICATIONS_NOTIFY_ON_KEY,
            default=None,
            help=(
                "Statuts pour lesquels une notification est envoyée. Par défaut : "
                f"{', '.join(DEFAULT_NOTIFY_ON)}."
            ),
        )

        smtp_state = " SMTP configuré" if smtp_cfg.is_configured else " SMTP non configuré"
        st.caption(
            f"{smtp_state} — host=`{smtp_cfg.host or '—'}` port=`{smtp_cfg.port}` "
            f"from=`{smtp_cfg.sender or '—'}` TLS=`{smtp_cfg.use_tls}` SSL=`{smtp_cfg.use_ssl}`. "
            "Variables d'env prioritaires : `ALPHA_TRADE_SMTP_HOST/_PORT/_USER/_PASSWORD/_FROM/_USE_TLS/_USE_SSL/_CA_FILE`."
        )
        st.caption(f"Préférences persistées dans `{NOTIFICATIONS_PREFERENCES_PATH}`.")

        save_col, test_col = st.columns([2, 1])
        with save_col:
            if st.button(
                " Enregistrer les préférences",
                key="settings_notifications_save",
                use_container_width=True,
            ):
                raw_recipients = str(st.session_state.get(NOTIFICATIONS_RECIPIENTS_KEY, ""))
                parsed = parse_recipients(raw_recipients)
                if not parsed:
                    st.session_state[NOTIFICATIONS_FLASH_KEY] = (
                        "error",
                        "Aucune adresse email valide saisie. Format attendu : `nom@domaine.tld` "
                        "(plusieurs adresses séparées par `;`).",
                    )
                else:
                    notify_on_raw = st.session_state.get(NOTIFICATIONS_NOTIFY_ON_KEY) or list(DEFAULT_NOTIFY_ON)
                    new_prefs = NotificationPreferences(
                        recipients=parsed,
                        enabled=bool(st.session_state.get(NOTIFICATIONS_ENABLED_KEY, True)),
                        notify_on=list(notify_on_raw),
                    )
                    saved = save_persisted_notification_preferences(new_prefs)
                    st.session_state[NOTIFICATIONS_RECIPIENTS_KEY] = format_recipients(saved.recipients)
                    st.session_state[NOTIFICATIONS_NOTIFY_ON_KEY] = list(saved.notify_on)
                    st.session_state[NOTIFICATIONS_FLASH_KEY] = (
                        "success",
                        f"Préférences enregistrées ({len(saved.recipients)} destinataire(s)).",
                    )
                st.rerun()
        with test_col:
            if st.button(
                "✉️ Envoyer un email de test",
                key="settings_notifications_test",
                use_container_width=True,
                disabled=not smtp_cfg.is_configured,
                help=None if smtp_cfg.is_configured else "Configurez d'abord les variables SMTP.",
            ):
                raw_recipients = str(st.session_state.get(NOTIFICATIONS_RECIPIENTS_KEY, ""))
                parsed = parse_recipients(raw_recipients) or list(prefs.recipients)
                test_prefs = NotificationPreferences(
                    recipients=parsed,
                    enabled=True,
                    notify_on=list(st.session_state.get(NOTIFICATIONS_NOTIFY_ON_KEY) or DEFAULT_NOTIFY_ON),
                )
                ok, message = send_test_email(test_prefs, smtp_config=smtp_cfg)
                st.session_state[NOTIFICATIONS_FLASH_KEY] = (
                    "success" if ok else "error",
                    message,
                )
                st.rerun()

        if failure_log_payload is not None:
            st.caption("Dernier échec SMTP disponible au téléchargement pour diagnostic.")
            st.download_button(
                "⬇️ Télécharger le journal du dernier échec SMTP",
                data=failure_log_payload[1],
                file_name=failure_log_payload[0],
                mime="text/plain",
                key="settings_notifications_download_failure_log",
                use_container_width=True,
            )


def _check_import(name: str) -> str:
    try:
        __import__(name)
        return f" `{name}` — OK"
    except ImportError:
        return f" `{name}` — **MANQUANT**"


def render():
    st.header("⚙️ Paramètres / Santé")
    st.caption(
        "Page recentrée sur les prérequis opérateur puis sur les paramètres réellement utilisés par le flux `quotes → earnings → alpha scanner`."
    )
    _render_capital_preset_warning_banner()

    prereq_col1, prereq_col2 = st.columns(2)
    with prereq_col1:
        with st.container(border=True):
            _render_environment_variable_settings()
    with prereq_col2:
        with st.container(border=True):
            st.subheader("️ Connexion DB")
            render_db_connection_form("settings_db_connection_form", show_host_fields=True)
            status = get_db_status()
            if db_available():
                st.success(" Connexion MySQL OK")
            else:
                st.error(" Connexion MySQL échouée. Vérifiez LOGIN_DB, PASSWORD_DB et que MySQL est démarré.")
            st.caption(
                f"Source active : `{status.get('source')}` — cible : `{status.get('host')}/{status.get('name')}`"
            )
            if status.get("last_query_error"):
                st.warning(str(status.get("last_query_error")))

    st.subheader(" Paramétrage pipeline")
    _render_bars_provider_settings()
    _render_alpha_scanner_dependency_threshold_settings()
    _render_notifications_settings()

    # ---- Sprint S26 (gap P3) — Maintenance & sécurité ops ------------
    st.subheader(" Maintenance & sécurité ops")
    st.caption(
        "Lancement direct des scripts ops `prune_artifacts` et "
        "`verify_vault_rotation`. Chaque run est tracé dans "
        "`artifacts/ihm_pipeline_runs/` (préfixe `ops:`)."
    )
    ops_tabs = st.tabs([" Nettoyage artefacts", "️ Rotation des secrets"])
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

    with st.expander("️ Diagnostic environnement Python", expanded=False):
        st.text(f"Python : {sys.version}")
        st.text(f"Répertoire : {os.getcwd()}")

        st.markdown("** Dépendances critiques**")
        for pkg in ("streamlit", "sqlalchemy", "pandas", "pymysql", "numpy", "torch", "transformers"):
            st.markdown(_check_import(pkg))

        st.markdown("** Commande de lancement**")
        st.code("python -m streamlit run ihm/app.py", language="powershell")


run_page_if_standalone(__name__, render)

