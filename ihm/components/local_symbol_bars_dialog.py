"""US review dialogs: local daily OHLCV with period buttons, no provider fallback."""
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from ihm.components.symbol_consensus_panel import render_symbol_consensus_panel


_DIALOG_REQUEST_KEY = '_pipeline_local_bars_dialog_request'


def request_local_symbol_bars_dialog(symbol, end_date, company_name=None):
    """Leave the polling fragment before registering the interactive dialog."""
    st.session_state[_DIALOG_REQUEST_KEY] = (symbol, end_date, company_name)
    st.rerun(scope='app')


def render_pending_local_symbol_bars_dialog():
    """Call once from page scope, never inside the pipeline polling fragment.

    Otherwise a polling rerun prunes the nested dialog fragment and its period
    controls still look clickable but no longer have a registered handler.
    """
    request = st.session_state.pop(_DIALOG_REQUEST_KEY, None)
    if request is not None:
        show_local_symbol_bars_dialog(*request)


def annual_window(end_date):
    return period_window(end_date,12)


def period_window(end_date, months=12):
    if type(months) is not int or months not in (1,6,12):
        raise ValueError('Période autorisée : 1, 6 ou 12 mois')
    end = end_date if type(end_date) is date else date.fromisoformat(str(end_date))
    return (pd.Timestamp(end) - pd.DateOffset(months=months)).date(), end


def prepare_local_bars(frame, start, end):
    frame = frame.copy()
    frame['date'] = pd.to_datetime(frame['date'], errors='coerce')
    ohlc = ['open', 'high', 'low', 'close']
    for field in [*ohlc, 'volume', 'is_filled']:
        frame[field] = pd.to_numeric(frame[field], errors='coerce')
    valid_dates = frame['date'].between(pd.Timestamp(start), pd.Timestamp(end))
    valid_prices = pd.Series(np.isfinite(frame[ohlc].to_numpy(dtype=float)).all(axis=1), index=frame.index)
    valid_prices &= frame[ohlc].gt(0).all(axis=1)
    valid_prices &= frame['high'].ge(frame[ohlc].max(axis=1)) & frame['low'].le(frame[ohlc].min(axis=1))
    observed = frame['is_filled'].eq(0)
    stats = dict(received=len(frame), filled_or_unknown=int((~observed).sum()),
                 invalid_prices=int((~valid_prices).sum()))
    frame = frame.loc[valid_dates & valid_prices & observed].sort_values('date').reset_index(drop=True)
    invalid_volume = ~np.isfinite(frame['volume']) | frame['volume'].lt(0)
    frame.loc[invalid_volume, 'volume'] = np.nan
    stats.update(excluded=stats['received']-len(frame), missing_volume=int(invalid_volume.sum()))
    return frame, stats


def load_local_symbol_bars(engine, symbol, end_date, months=12):
    if engine.dialect.name == 'mysql' and engine.url.database != 'alpha_trade':
        raise ValueError('Graphique réservé à alpha_trade US')
    symbol = str(symbol or '').strip().upper()
    if not symbol or len(symbol) > 32 or any(c.isspace() or ord(c)<32 for c in symbol):
        raise ValueError('Symbole invalide')
    start, end = period_window(end_date,months)
    with engine.connect() as conn:
        records = conn.execute(text('''SELECT `date`,`open`,high,low,`close`,volume,is_filled,data_source
            FROM stock_bars_daily WHERE symbol=:symbol AND `date` BETWEEN :start AND :end
            ORDER BY `date`'''), dict(symbol=symbol,start=start,end=end)).mappings().all()
    frame = pd.DataFrame(records, columns=['date','open','high','low','close','volume','is_filled','data_source'])
    bars, stats = prepare_local_bars(frame,start,end)
    return dict(bars=bars, stats=stats, start=start, end=end)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_local_symbol_bars(symbol, end_date, months=12):
    return load_local_symbol_bars(get_sqlalchemy_engine(), symbol, end_date,months)


def build_bars_figure(bars):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.04, row_heights=[.76,.24])
    figure.add_trace(go.Candlestick(x=bars['date'], open=bars['open'], high=bars['high'],
        low=bars['low'], close=bars['close'], name='OHLC',
        increasing_line_color='#178764', decreasing_line_color='#d44b54'),row=1,col=1)
    figure.add_trace(go.Bar(x=bars['date'], y=bars['volume'], name='Volume',
        marker_color=['#178764' if c>=o else '#d44b54' for c,o in zip(bars['close'],bars['open'])]),row=2,col=1)
    figure.update_layout(height=540, showlegend=False, dragmode='zoom',
        margin=dict(l=15,r=15,t=15,b=15), xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text='Prix ($)',row=1,col=1)
    figure.update_yaxes(title_text='Volume',row=2,col=1)
    figure.update_xaxes(rangebreaks=[dict(bounds=['sat','mon'])])
    return figure


def _render_local_bars_dialog_body(symbol, end_date, company_name=None):
    st.subheader(f'{symbol} — Barres journalières')
    if company_name:
        st.caption(company_name)
    _render_local_bars_section(symbol,end_date)
    # Consensus remains readable even when the symbol has no valid local bars.
    render_symbol_consensus_panel(symbol,end_date)
    if st.button('Fermer',key=f'local_bars_close_{symbol}_{end_date}',use_container_width=True):
        st.rerun()


def _render_local_bars_section(symbol,end_date):
    periods={'1 an':12,'6 mois':6,'1 mois':1}
    period=st.segmented_control('Période',options=list(periods),default='1 an',
        key=f'local_bars_period_{symbol}_{end_date}') or '1 an'
    try:
        with st.spinner('Lecture des barres déjà présentes en base…'):
            result = _cached_local_symbol_bars(symbol, end_date,periods[period])
    except Exception:
        st.warning('Historique local indisponible. Aucun téléchargement fournisseur n’a été tenté.')
        return
    bars, stats = result['bars'], result['stats']
    st.caption(f"Fenêtre : {result['start']:%d/%m/%Y} → {result['end']:%d/%m/%Y}, arrêtée à la séance de l’analyse. "
               'Source : alpha_trade.stock_bars_daily ; lecture seule, aucun appel fournisseur. '
               'La période demandée ne garantit pas une couverture complète en base.')
    if stats['excluded']:
        st.warning(f"{stats['excluded']} barre(s) exclue(s) du graphique : remplie(s), statut inconnu, date ou OHLC invalide(s). "
                   'Les trous ne sont pas comblés artificiellement.')
    if bars.empty:
        st.info('Aucune barre journalière réelle et valide disponible sur cette fenêtre pour ce titre.')
        return
    left, right = st.columns(2)
    left.metric('Dernière clôture affichée',f"{bars.iloc[-1]['close']:,.4f} $")
    right.metric('Barres affichées',len(bars))
    st.caption('Dernière barre : ' + bars.iloc[-1]['date'].strftime('%d/%m/%Y')
               + ' · Sources enregistrées : ' + ', '.join(sorted(bars['data_source'].fillna('inconnue').astype(str).unique())))
    if stats['missing_volume']:
        st.caption(f"Volume non renseigné ou invalide sur {stats['missing_volume']} barre(s), laissé vide (pas remplacé par zéro).")
    # Recreate the viewport for a period change, rather than preserving a zoom
    # from another window. The selected period is part of both query and key.
    figure = build_bars_figure(bars)
    figure.update_xaxes(range=[str(result['start']), str(result['end'])], autorange=False)
    st.plotly_chart(figure,width='stretch',key=f'local_bars_chart_{symbol}_{end_date}_{periods[period]}')
    with st.expander('Voir les barres OHLCV et leur source',expanded=False):
        st.dataframe(bars.iloc[::-1],hide_index=True,use_container_width=True,height=320)


@st.dialog('Historique des barres',width='large',on_dismiss='rerun')
def show_local_symbol_bars_dialog(symbol, end_date, company_name=None):
    _render_local_bars_dialog_body(symbol,end_date,company_name)


