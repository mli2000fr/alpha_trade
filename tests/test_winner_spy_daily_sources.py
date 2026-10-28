"""SPY regime inputs share the configured daily-source and as-of contract."""
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from common.daily_bar_sources import load_daily_close_series


def database(extra=()):
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE stock_bars_daily(symbol TEXT,date DATE,close REAL,data_source TEXT)'))
        rows = [('2026-10-15', 600., 'eodhd_eod'), ('2026-10-15', 601., 'alpaca_sip'),
            ('2026-10-16', 602., 'eodhd_eod'), ('2026-10-16', 603., 'alpaca_sip'),
            ('2026-10-19', 604., 'alpaca_sip'), ('2026-10-20', 999., 'alpaca_sip'), *extra]
        for day, close, source in rows:
            conn.execute(text('INSERT INTO stock_bars_daily VALUES (:symbol,:day,:close,:source)'),
                dict(symbol='SPY', day=day, close=close, source=source))
    return engine


@pytest.mark.parametrize('preference,expected', [('eodhd', [600., 602., 604.]),
                                               ('alpaca_sip', [601., 603., 604.])])
def test_known_pairs_follow_config_and_recent_single_source_is_retained(preference, expected):
    result = load_daily_close_series(database(), 'SPY', date(2026, 10, 19),
        config={'market_data': {'daily_bars_preferred_source': preference}})
    assert result.index.is_unique and result.tolist() == expected
    assert result.index.max() == pd.Timestamp('2026-10-19')  # Future 999 never enters regime.


@pytest.mark.parametrize('extra', [ [('2026-10-16', 100., 'eodhd_eod')],
    [('2026-10-19', 100., 'iex')], [('2026-10-19', -1., 'alpaca_sip')]])
def test_bad_sources_prices_or_duplicate_rows_still_block(extra):
    with pytest.raises(ValueError):
        load_daily_close_series(database(extra), 'SPY', date(2026, 10, 19), config={})


def test_missing_required_session_fails_instead_of_rolling_old_close_forward():
    with pytest.raises(ValueError, match='missing as-of'):
        load_daily_close_series(database(), 'SPY', date(2026, 10, 21), config={})


