from copy import deepcopy
from datetime import UTC,datetime
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from scripts.research.us_q051_retrospective_daily_repair_20261115 import qualify


@pytest.fixture
def prices():
    dates=pd.bdate_range('2026-10-08','2026-11-13')
    quotes=dict(open=[3.4]*len(dates),high=[3.5]*len(dates),low=[3.3]*len(dates),
                close=[3.45]*len(dates),volume=[1000]*len(dates))
    result=dict(meta=dict(symbol='TKOMY',currency='USD',instrumentType='EQUITY',exchangeTimezoneName='America/New_York'),
        timestamp=[int(d.replace(hour=9,minute=30,tzinfo=ZoneInfo('America/New_York')).timestamp()) for d in dates.to_pydatetime()],
        indicators=dict(quote=[quotes]),events={})
    payload=dict(http_status=200,symbol='TKOMY',received_at=datetime.now(UTC).isoformat(),response=dict(chart=dict(result=[result])))
    canonical=pd.DataFrame(quotes).assign(symbol='TKOMY',date=dates).iloc[:7]
    return payload,canonical


def test_only_missing_sessions_added_and_canonical_prices_never_overwritten(prices):
    payload,canonical=prices
    frame,receipt=qualify(payload,canonical)
    assert len(frame)==20 and frame.date.min()==pd.Timestamp('2026-10-19')
    assert not set(frame.date)&set(canonical.date)
    assert frame.data_source.eq('yahoo_daily_research').all()
    assert receipt['original_rows_overwritten']==0 and receipt['anchor_sessions']==7


@pytest.mark.parametrize('bad',['currency','splits','different_prices','missing_session','duplicate_date','invalid_ohlc'])
def test_repair_refuses_identity_price_basis_or_coverage_mismatches(prices,bad):
    payload,canonical=prices;payload=deepcopy(payload)
    result=payload['response']['chart']['result'][0]
    if bad=='currency':result['meta']['currency']='JPY'
    if bad=='splits':result['events']['splits']={'x':dict(numerator=2,denominator=1)}
    if bad=='different_prices':result['indicators']['quote'][0]['close'][0]=3.49
    if bad=='missing_session':result['timestamp'][-1]=int(datetime(2026,11,14,15,tzinfo=UTC).timestamp())
    if bad=='duplicate_date':result['timestamp'][-1]=result['timestamp'][-2]
    if bad=='invalid_ohlc':result['indicators']['quote'][0]['low'][0]=5.
    with pytest.raises(ValueError):qualify(payload,canonical)
