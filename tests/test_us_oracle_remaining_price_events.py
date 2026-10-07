import pandas as pd
import pytest

import argparse
from scripts.research.us_oracle_remaining_price_events import event_record, parse_events


def test_event_uses_actual_preceding_observation_not_calendar_day():
    frame = pd.DataFrame(dict(symbol=['X', 'X'],
        date=pd.to_datetime(['2023-12-01', '2023-12-05']),
        open=[1., 20.], high=[1., 20.], low=[1., 20.], close=[1., 20.],
        adj_close=[20., 20.], volume=[100, 5], instrument_id=[1, 1], is_filled=[0, 0]))
    row = event_record(frame, '2023-12-05')
    assert row['previous_date'] == pd.Timestamp('2023-12-01')
    assert row['daily_return_recomputed'] == 0.
    assert row['overnight_gap_recomputed'] == 0.
    assert row['instrument_changed'] is False
    frame['instrument_id'] = None
    assert event_record(frame, '2023-12-05')['instrument_changed'] is None


def test_missing_event_not_replaced_with_nearest_date():
    frame = pd.DataFrame(dict(symbol=['X'], date=pd.to_datetime(['2023-12-01']),
        open=[1.], high=[1.], low=[1.], close=[1.], adj_close=[1.],
        volume=[10], instrument_id=[1], is_filled=[0]))
    with pytest.raises(ValueError, match='event date'):
        event_record(frame, '2023-12-05')


def test_parse_explicit_events():
    assert parse_events('BASFY:2017-10-09,PECO:2021-07-15') == {
        'BASFY': '2017-10-09', 'PECO': '2021-07-15'}


@pytest.mark.parametrize('value', ['BASFY:2017-02-30', 'X:2017-01-01,X:2018-01-01',
                                  'BASFY', 'x:2017-01-01', 'X:NaT'])
def test_invalid_event_configuration_rejected(value):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_events(value)
