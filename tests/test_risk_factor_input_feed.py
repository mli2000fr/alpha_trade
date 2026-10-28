from datetime import UTC, date, datetime, timedelta
import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, select

from database.risk_factor_inputs import install_schema, snapshots
from risk_management.factor_inputs import calculate_inputs, select_caps, load_inputs, universe_hash

DAY = date(2026,10,27)
CUTOFF = datetime(2026,10,28,10,tzinfo=UTC)


def data():
    sessions = pd.bdate_range(end=str(DAY),periods=272).date.tolist()
    rows=[]
    for symbol in ('SPY','TEST','FALLING'):
        k=np.arange(272)
        close=(100+.1*k+np.sin(k)*.2 if symbol=='SPY' else
               (30+.08*k+np.sin(k)*.4 if symbol=='TEST' else 80-.08*k+np.cos(k)*.2))
        for day,price in zip(sessions,close):
            rows.append(dict(symbol=symbol,date=day,open=price,high=price+1,low=price-1,
                close=price,volume=10000,data_source='alpaca_sip',is_filled=False))
    caps=[dict(id=i+1,symbol=s,market_cap=(i+1)*1e9,source='FINNHUB',currency='USD',
        observation_date=DAY,available_date=date(2026,10,28),computed_at=CUTOFF.replace(tzinfo=None)-timedelta(hours=1))
        for i,s in enumerate(('TEST','FALLING'))]
    return pd.DataFrame(rows),caps,sessions


def test_unfiltered_symbols_get_real_features_including_a_falling_stock():
    bars,caps,sessions=data()
    result=calculate_inputs(bars,caps,['TEST','FALLING'],DAY,CUTOFF,sessions,config={})
    assert len(result)==2 and all(r['quality']=='QUALIFIED' for r in result)
    by_symbol={r['symbol']:r for r in result}
    assert by_symbol['FALLING']['trend_score'] < by_symbol['TEST']['trend_score']
    assert np.isfinite(by_symbol['TEST']['beta_126']) and by_symbol['FALLING']['market_cap']==2e9


@pytest.mark.parametrize('kind', ['missing','filled','bad_price','no_cap'])
def test_missing_data_produces_incomplete_evidence_never_neutral_factors(kind):
    bars,caps,sessions=data()
    test=bars.symbol.eq('TEST')
    if kind=='missing':bars=bars.drop(bars.loc[test].index[0])
    elif kind=='filled':bars.loc[bars.loc[test].index[0],'is_filled']=True
    elif kind=='bad_price':bars.loc[bars.loc[test].index[0],'close']=0.
    else:caps=[r for r in caps if r['symbol']!='TEST']
    result=calculate_inputs(bars,caps,['TEST'],DAY,CUTOFF,sessions,config={})[0]
    assert result['quality']=='INCOMPLETE' and json.loads(result['details_json'])['reasons']
    if kind=='no_cap':assert result['market_cap'] is None
    else:assert result['beta_126'] is None


def test_caps_must_be_known_at_actual_cutoff_and_have_qualified_currency_source():
    _,caps,_=data()
    assert select_caps(caps,DAY,CUTOFF)['TEST']['market_cap']==1e9
    assert select_caps(caps,DAY,CUTOFF-timedelta(days=1))=={}
    for patch in (dict(currency='EUR'),dict(source='YAHOO'),dict(computed_at=CUTOFF+timedelta(seconds=1))):
        assert 'TEST' not in select_caps([caps[0]|patch],DAY,CUTOFF)


def test_publication_is_invisible_before_its_real_observation_time():
    engine=create_engine('sqlite://');install_schema(engine)
    row=dict(run_id='one',symbol='TEST',asof_date=DAY,observed_at=CUTOFF.replace(tzinfo=None),
        universe_sha256=universe_hash(['TEST']),input_sha256='a'*64,beta_126=1.,trend_score=.5,
        market_cap=1e9,quality='QUALIFIED',details_json='{}')
    with engine.begin() as c:c.execute(snapshots.insert(),row)
    assert load_inputs(engine,['TEST'],DAY,CUTOFF-timedelta(seconds=1)).empty
    assert load_inputs(engine,['TEST'],DAY,CUTOFF).beta_126.iloc[0]==1.


def test_bad_duplicate_bars_cannot_be_published_as_qualified():
    bars,caps,sessions=data()
    bars=pd.concat([bars,bars.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError,match='duplicate'):
        calculate_inputs(bars,caps,['TEST'],DAY,CUTOFF,sessions,config={})
