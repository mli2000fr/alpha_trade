import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from common import daily_bar_sources as sources
from modelFactory import data_loader


def cfg(value='eodhd'):
    return {'market_data': {'daily_bars_preferred_source': value}}


def bars():
    return pd.DataFrame([
        dict(symbol='SPY', date=pd.Timestamp('2026-10-12'), close=10., volume=100, data_source='alpaca_sip'),
        dict(symbol='SPY', date=pd.Timestamp('2026-10-12'), close=20., volume=200, data_source='eodhd_eod'),
        dict(symbol='SPY', date=pd.Timestamp('2026-10-13'), close=30., volume=300, data_source='alpaca_sip'),
        dict(symbol='ABC', date=pd.Timestamp('2026-10-12'), close=40., volume=400, data_source='eodhd_eod'),
    ])


@pytest.mark.parametrize('preference,close,volume', [('eodhd', 20., 200), ('alpaca_sip', 10., 100)])
def test_pair_preference_whole_row_and_absent_source_fallback(preference, close, volume):
    raw = bars(); before = raw.copy(deep=True)
    out = sources.select_daily_bars(raw, config=cfg(preference))
    assert len(out) == 3
    assert out.iloc[0].close == close and out.iloc[0].volume == volume
    assert out.iloc[1].close == 30. and out.iloc[2].close == 40.
    pd.testing.assert_frame_equal(raw, before)


def test_order_does_not_change_selected_rows_and_missing_days_not_invented():
    a = sources.select_daily_bars(bars(), config=cfg()).sort_values(['symbol','date']).reset_index(drop=True)
    b = sources.select_daily_bars(bars().iloc[::-1], config=cfg()).sort_values(['symbol','date']).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)
    assert a.date.max() == pd.Timestamp('2026-10-13')


@pytest.mark.parametrize('value', ['iex', 'alpaca', None, True, 3])
def test_invalid_preference_fails(value):
    with pytest.raises(ValueError, match='daily_bars_preferred_source'):
        sources.preferred_daily_source(cfg(value))


def test_default_and_unambiguous_legacy_frames():
    assert sources.preferred_daily_source({}) == 'eodhd_eod'
    frame = bars().iloc[2:].drop(columns='data_source')
    pd.testing.assert_frame_equal(sources.select_daily_bars(frame, config={}), frame)


@pytest.mark.parametrize('kind', ['same_source', 'unknown_source', 'no_provenance'])
def test_no_arbitrary_deduplication(kind):
    frame = bars().iloc[:2].copy()
    if kind == 'same_source':
        frame['data_source'] = 'eodhd_eod'
    elif kind == 'unknown_source':
        frame.loc[0,'data_source'] = 'alpaca_iex'
    else:
        frame = frame.drop(columns='data_source')
    with pytest.raises(ValueError, match='duplicate'):
        sources.select_daily_bars(frame, config={})


@pytest.mark.parametrize('preference', ['eodhd', 'alpaca_sip'])
def test_sql_pair_rule_matches_dataframe_and_limit_is_after_selection(preference):
    engine = create_engine('sqlite://')
    frame = bars(); frame.date = frame.date.dt.strftime('%Y-%m-%d')
    frame.to_sql('stock_bars_daily', engine, index=False)
    clause, params = sources.daily_source_filter(config=cfg(preference))
    with engine.connect() as conn:
        got = pd.read_sql(text('SELECT * FROM stock_bars_daily WHERE 1=1 '+clause+' ORDER BY symbol,date'), conn, params=params)
    expected = sources.select_daily_bars(frame, config=cfg(preference)).sort_values(['symbol','date']).reset_index(drop=True)
    pd.testing.assert_frame_equal(got, expected)


@pytest.mark.parametrize('preference', ['eodhd', 'alpaca_sip'])
def test_model_single_benchmark_and_panel_use_same_preference(monkeypatch, preference):
    engine = create_engine('sqlite://')
    frame = bars()
    for field in ['open','high','low','adj_close','vwap']:
        frame[field] = frame.close
    frame['daily_return'] = 0.; frame['is_filled'] = 0
    frame.to_sql('stock_bars_daily', engine, index=False)
    monkeypatch.setattr(sources, 'load_config', lambda: cfg(preference))
    panel = data_loader.load_universe_bars(engine, ['SPY','ABC'])
    benchmark = data_loader.load_benchmark_bars(engine, 'SPY')
    assert len(panel) == 3 and len(benchmark) == 2
    assert benchmark.bar_data_source.iloc[0] == sources.SOURCES[preference]
    pd.testing.assert_series_equal(benchmark.close, panel.loc[panel.symbol.eq('SPY'),'close'].reset_index(drop=True))


def test_sql_identifiers_are_not_interpolated_unchecked():
    with pytest.raises(ValueError):
        sources.daily_source_filter(alias='x;DROP')
