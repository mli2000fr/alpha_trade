"""Isolated UI reproduction: generated local bars, no DB/network/trading actions.

Run with Streamlit to exercise nested dialog reruns under the pipeline's timer.
"""
from datetime import date

import pandas as pd
import streamlit as st

from ihm.components import local_symbol_bars_dialog as chart
from ihm.components import symbol_consensus_panel as consensus
from ihm.components.prediction_review_table import render_prediction_review_table


def fixture_bars(symbol, end_date, months=12):
    start, end = chart.period_window(end_date, months)
    days = pd.bdate_range(start, end)
    bars = pd.DataFrame(dict(date=days, open=10., high=12., low=9., close=11.,
                             volume=1000, data_source='test_fixture'))
    return dict(bars=bars, start=start, end=end, stats=dict(excluded=0, missing_volume=0))


chart._cached_local_symbol_bars = fixture_bars
# Explicitly synthetic consensus: this page must never read a real database.
consensus._days = lambda *a: ['2026-10-16','2026-10-15']
def fixture_consensus(symbol,end_date,snapshot):
    return [dict(symbol=symbol,provider='eodhd',snapshot_date=snapshot,
        fiscal_period_end='2026-12-31',horizon_raw='0q',currency=None,
        eps_avg=1.2,eps_low=.8,eps_high=1.4,eps_analyst_count=12,
        eps_current=1.2,eps_7d_ago=1.1,eps_30d_ago=1.,eps_60d_ago=.9,
        revisions_up_7d=3,revisions_down_7d=None,revisions_up_30d=8,revisions_down_30d=2,
        qualification_status='RESEARCH_ONLY',units_qualified=False,
        fiscal_identity_qualified=False,historical_pit_qualified=False,
        available_at=snapshot+' 23:00:00',observed_at=snapshot+' 23:00:00',
        run_id='fixture-not-a-real-run')]
consensus._snapshot = fixture_consensus
consensus._history = lambda *a: [dict(snapshot_date=a[2],eps_current=1.2,eps_avg=1.2)]
st.title('Graphique — test isolé sans base')


@st.fragment(run_every='2s')
def panel():
    render_prediction_review_table(pd.DataFrame([
        {'Rang Oracle': 1, 'Symbole': 'TEST', 'Nom de l’entreprise': 'Fixture locale'}]),
        key='dialog_period_fixture', trade_date=str(date(2026, 10, 16)))


panel()
chart.render_pending_local_symbol_bars_dialog()
