import pandas as pd
import pytest

from scripts.research.us_oracle_repair_qualification import validate_parity


def frames():
    daily = pd.DataFrame(dict(symbol=['X'], date=pd.to_datetime(['2020-01-01']),
        open=[10.], high=[12.], low=[9.], close=[11.], adj_close=[11.],
        volume=[100], vwap=[32. / 3.], instrument_id=[1]))
    bars = daily.rename(columns=dict(open='open_price', high='high_price',
        low='low_price', close='close_price', vwap='vwa_price')).copy()
    bars['timestamp'] = bars.date + pd.Timedelta(hours=9, minutes=30)
    bars['timeframe'] = '1D'
    return daily, bars.drop(columns=['date', 'adj_close'])


def test_matching_tables_accepted():
    validate_parity(*frames())


def test_volume_mismatch_rejected():
    daily, bars = frames()
    with pytest.raises(ValueError, match='volume'):
        validate_parity(daily, bars.assign(volume=101))


def test_missing_bar_rejected():
    daily, bars = frames()
    with pytest.raises(ValueError, match='key sets'):
        validate_parity(daily, bars.iloc[:0])


def test_dividend_adjusted_close_not_silently_mixed():
    daily, bars = frames()
    with pytest.raises(ValueError, match='adjusted-close'):
        validate_parity(daily.assign(adj_close=10.), bars)


def test_identity_mismatch_rejected():
    daily, bars = frames()
    with pytest.raises(ValueError, match='identity'):
        validate_parity(daily, bars.assign(instrument_id=2))
