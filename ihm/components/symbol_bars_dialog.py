"""Popin réutilisable affichant l'historique des bars OHLCV d'un symbole.

Utilise ``market_data.bars_provider`` : Alpaca SIP historique, ou EODHD
avec repli Stooq uniquement lorsque EODHD est explicitement configuré.
Le compte Alpaca choisi et le fournisseur font partie de la clé de cache.

API publique :

* :func:`load_symbol_bars` — chargement caché par ``st.cache_data`` ;
* :func:`show_symbol_bars_dialog` — déclenche la popin (via décorateur
  ``@st.dialog``).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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


def _fetch_bars_alpaca(symbol: str, *, start: date, end: date, account_id: str | None) -> pd.DataFrame:
    from common.verified_http import verified_session
    from service.alpaca.clientAlpaca import fetch_bars
    try:
        with verified_session() as session:
            # The shared client compares provider timestamps to this boundary;
            # keep it aware. A bare YYYY-MM-DD becomes naive in its post-filter.
            payload=fetch_bars(symbol,'1Day',start_date=start.isoformat()+'T00:00:00+00:00',account_id=account_id,
                               session=session,feed='sip')
        frame=pd.DataFrame(payload)
        if frame.empty:return frame
        frame=frame.rename(columns=dict(t='date',o='open',h='high',l='low',c='close',v='volume'))
        frame['date']=(pd.to_datetime(frame['date'],utc=True,errors='coerce')
                       .dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize())
        fields=['open','high','low','close','volume']
        for field in fields:
            frame[field]=pd.to_numeric(frame[field],errors='coerce').replace([float('inf'),-float('inf')],float('nan'))
        frame=frame.loc[frame.date.between(pd.Timestamp(start),pd.Timestamp(end)),['date',*fields]]
        frame=frame.dropna(subset=['date','open','high','low','close'])
        frame=frame.loc[frame[['open','high','low','close']].gt(0).all(axis=1)]
        frame=frame.loc[frame.high.ge(frame[['open','low','close']].max(axis=1)) &
                        frame.low.le(frame[['open','high','close']].min(axis=1))]
        frame=frame.sort_values('date').drop_duplicates('date',keep='last').reset_index(drop=True)
        frame.attrs['provider']='alpaca_sip'
        return frame
    except Exception as exc:
        LOGGER.warning('Alpaca SIP historique indisponible pour %s : %s',symbol,type(exc).__name__)
        return pd.DataFrame()


def load_symbol_bars(symbol: str, lookback_days: int = 365, *, account_id: str | None = None) -> pd.DataFrame:
    """Charge les bars OHLCV daily d'un symbole sur ``lookback_days`` jours.

    Respecte le fournisseur configuré ; SIP historique ne bascule pas vers IEX
    ou EODHD en cas de refus. Cache 15 min, isolé par compte et fournisseur.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return pd.DataFrame()
    from ihm.services.market_data_provider import get_bars_provider
    end=datetime.now(ZoneInfo('America/New_York')).date()
    return _cached_symbol_bars(sym,int(lookback_days),get_bars_provider(),account_id,end)


@st.cache_data(ttl=900,show_spinner=False)
def _cached_symbol_bars(sym,lookback_days,provider,account_id,end):
    start=end-timedelta(days=lookback_days)
    if provider=='alpaca':
        bars=_fetch_bars_alpaca(sym,start=start,end=end,account_id=account_id)
        bars.attrs['provider']='alpaca_sip'
        return bars
    bars = _fetch_bars_eodhd(sym, start=start, end=end)
    if bars.empty:
        bars = _fetch_bars_stooq(sym, start=start, end=end)
    return bars


def _render_dialog_body(symbol: str, default_lookback_days: int, *, account_id: str | None = None) -> None:
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
        bars = load_symbol_bars(sym, lookback_days=lookback_days,account_id=account_id)

    from ihm.services.market_data_provider import get_bars_provider
    provider=get_bars_provider()
    if provider=='alpaca':
        st.caption('Source : Alpaca SIP historique, requête arrêtée à maintenant moins vingt minutes. '
                   'Barres ajustées des splits ; la dernière bougie peut être en cours de formation.')

    if bars.empty:
        if provider=='alpaca':
            st.warning(f'Aucune barre Alpaca SIP historique disponible pour `{sym}`. '
                       'Vérifie les accès du compte sélectionné et la connexion réseau.')
        else:
            st.warning(f'Aucune barre disponible pour `{sym}` (EODHD et Stooq ont échoué). '
                       'Vérifie le token EODHD ou la connectivité réseau.')
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
def show_symbol_bars_dialog(symbol: str, lookback_days: int = 365, *, account_id: str | None = None) -> None:
    """Ouvre la popin Streamlit affichant l'historique des bars d'un symbole."""
    _render_dialog_body(symbol, lookback_days,account_id=account_id)


__all__ = [
    "load_symbol_bars",
    "show_symbol_bars_dialog",
]

