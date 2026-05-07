"""Popin réutilisable affichant l'historique des bars OHLCV d'un symbole.

Utilise ``@st.dialog`` (Streamlit ≥ 1.32). La source de bars est :
1. EODHD (provider configuré par défaut côté IHM, cf.
   :mod:`ihm.services.market_data_provider`) si un token est dispo ;
2. Stooq comme fallback gratuit si EODHD échoue (token manquant, quota,
   payload inattendu, etc.).

API publique :

* :func:`load_symbol_bars` — chargement caché par ``st.cache_data`` ;
* :func:`show_symbol_bars_dialog` — déclenche la popin (via décorateur
  ``@st.dialog``).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

LOGGER = logging.getLogger(__name__)

# Mapping label → nombre de jours d'historique à charger.
_PERIOD_OPTIONS: dict[str, int] = {
    "1 mois": 31,
    "3 mois": 92,
    "6 mois": 183,
    "1 an": 365,
    "2 ans": 365 * 2,
    "5 ans": 365 * 5,
}
_DEFAULT_PERIOD_LABEL = "1 an"


def _normalize_eodhd_payload(payload: list[dict[str, Any]]) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()
    df = pd.DataFrame(payload)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    rename_map = {"adjusted_close": "adjusted_close", "Adjusted_close": "adjusted_close"}
    df = df.rename(columns=rename_map)
    keep = [c for c in ("date", "open", "high", "low", "close", "adjusted_close", "volume") if c in df.columns]
    df = df[keep].dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def _normalize_stooq_payload(payload: list[dict[str, Any]]) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()
    df = pd.DataFrame(payload)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def _fetch_bars_eodhd(symbol: str, *, start: date, end: date) -> pd.DataFrame:
    try:
        from service.eodhd.clientEodhd import fetch_eod  # import local pour éviter coût d'import
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("EODHD indisponible (import) pour %s : %s", symbol, exc)
        return pd.DataFrame()
    try:
        payload = fetch_eod(symbol, start=start.isoformat(), end=end.isoformat())
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("EODHD fetch_eod échec pour %s : %s", symbol, exc)
        return pd.DataFrame()
    return _normalize_eodhd_payload(payload if isinstance(payload, list) else [])


def _fetch_bars_stooq(symbol: str, *, start: date, end: date) -> pd.DataFrame:
    try:
        from service.stooq.clientStooq import fetch_daily_bars
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Stooq indisponible (import) pour %s : %s", symbol, exc)
        return pd.DataFrame()
    try:
        payload = fetch_daily_bars(symbol, start=start, end=end)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Stooq fetch_daily_bars échec pour %s : %s", symbol, exc)
        return pd.DataFrame()
    return _normalize_stooq_payload(payload if isinstance(payload, list) else [])


@st.cache_data(ttl=900, show_spinner=False)
def load_symbol_bars(symbol: str, lookback_days: int = 365) -> pd.DataFrame:
    """Charge les bars OHLCV daily d'un symbole sur ``lookback_days`` jours.

    Essaie EODHD puis Stooq (fallback gratuit). Retourne un DataFrame vide en
    cas d'échec total. Cache 15 min.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return pd.DataFrame()
    end = date.today()
    start = end - timedelta(days=int(lookback_days))
    bars = _fetch_bars_eodhd(sym, start=start, end=end)
    if bars.empty:
        bars = _fetch_bars_stooq(sym, start=start, end=end)
    return bars


def _render_dialog_body(symbol: str, default_lookback_days: int) -> None:
    sym = (symbol or "").strip().upper() or "—"
    st.markdown(f"### 📈 {sym} — historique des bars")

    default_label = _DEFAULT_PERIOD_LABEL
    # Choisit le label le plus proche du lookback demandé
    nearest_label = min(
        _PERIOD_OPTIONS.items(),
        key=lambda item: abs(item[1] - int(default_lookback_days)),
    )[0]
    if nearest_label in _PERIOD_OPTIONS:
        default_label = nearest_label

    period_label = st.selectbox(
        "Période",
        options=list(_PERIOD_OPTIONS.keys()),
        index=list(_PERIOD_OPTIONS.keys()).index(default_label),
        key=f"_symbol_bars_period_{sym}",
    )
    lookback_days = _PERIOD_OPTIONS[period_label]

    with st.spinner(f"Chargement des bars `{sym}`…"):
        bars = load_symbol_bars(sym, lookback_days=lookback_days)

    if bars.empty:
        st.warning(
            f"Aucune barre disponible pour `{sym}` (EODHD et Stooq ont échoué). "
            "Vérifie le token EODHD ou la connectivité réseau."
        )
        return

    last = bars.iloc[-1]
    first = bars.iloc[0]
    last_close = float(last.get("close") or 0.0)
    first_close = float(first.get("close") or 0.0)
    delta_pct = ((last_close / first_close) - 1.0) * 100.0 if first_close else 0.0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dernier close", f"{last_close:,.2f}")
    col2.metric("Variation période", f"{delta_pct:+.2f}%")
    col3.metric("Bars", len(bars))
    col4.metric("Dernière date", str(pd.to_datetime(last["date"]).date()))

    chart_df = bars.set_index("date")[["close"]]
    st.line_chart(chart_df, use_container_width=True, height=280)
    if "volume" in bars.columns:
        st.bar_chart(bars.set_index("date")[["volume"]], use_container_width=True, height=160)

    with st.expander("Bars (60 dernières lignes)", expanded=False):
        st.dataframe(bars.tail(60).iloc[::-1], use_container_width=True, hide_index=True, height=320)

    if st.button("Fermer", key=f"_symbol_bars_close_{sym}", use_container_width=True):
        st.session_state.pop(f"_symbol_bars_open_{sym}", None)
        st.rerun()


# ``@st.dialog`` est requis par Streamlit pour que la popin soit appelée
# directement comme une fonction. On garde la fonction interne séparée pour
# pouvoir la tester sans le décorateur.
@st.dialog("Historique des bars", width="large")
def show_symbol_bars_dialog(symbol: str, lookback_days: int = 365) -> None:
    """Ouvre la popin Streamlit affichant l'historique des bars d'un symbole."""
    _render_dialog_body(symbol, lookback_days)


__all__ = [
    "load_symbol_bars",
    "show_symbol_bars_dialog",
]

