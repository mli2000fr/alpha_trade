import numpy as np
import pandas as pd
import pytest
from scripts.research.us_sip_daily_universe_audit import provider_frame,price_valid,metrics,download


def test_new_york_day_not_utc_previous_day():
    frame=provider_frame({'ABC':[dict(t='2026-01-02T05:00:00Z',o=100,h=102,l=99,c=101,v=200,vw=100.5)]})
    assert frame.date.iloc[0]==pd.Timestamp('2026-01-02')
    assert price_valid(frame).all()


def test_provider_duplicates_rejected():
    bar=dict(t='2026-01-02T05:00:00Z',o=100,h=102,l=99,c=101,v=200,vw=100.5)
    with pytest.raises(ValueError,match='Duplicate'):provider_frame({'ABC':[bar,bar]})


def test_invalid_prices_excluded():
    frame=pd.DataFrame(dict(open=[100,100,0],high=[102,98,1],low=[99,99,0],close=[101,101,1]))
    assert price_valid(frame).tolist()==[True,False,False]


def test_metrics_volume_zero_and_price_percent():
    frame=pd.DataFrame({f+'_'+s:[100.] for f in ('open','high','low','close','volume','vwap') for s in ('local','sip')})
    frame['close_sip']=101.;frame['volume_local']=0
    result=metrics(frame)
    assert np.isclose(result['close_absolute_bps']['median'],100.)
    assert result['sip_to_local_volume_ratio']['n']==0


def test_empty_provider_history():
    frame=provider_frame({'ABC':[]})
    assert frame.empty and 'date' in frame


def test_invalid_symbol_bisection_but_auth_failure_stops(monkeypatch):
    import requests
    import scripts.research.us_sip_daily_universe_audit as module
    def fake(session,symbols,start,end):
        if 'BAD' in symbols:
            response=requests.Response();response.status_code=422
            raise requests.HTTPError(response=response)
        return {s:[] for s in symbols},1
    monkeypatch.setattr(module,'fetch',fake)
    result=download(None,['GOOD','BAD'],'2026-01-01','2026-09-30')
    assert 'GOOD' in result['bars'] and result['errors'][0]['symbol']=='BAD'
    def forbidden(*args):
        response=requests.Response();response.status_code=403
        raise requests.HTTPError(response=response)
    monkeypatch.setattr(module,'fetch',forbidden)
    with pytest.raises(requests.HTTPError):download(None,['GOOD','BAD'],'2026-01-01','2026-09-30')
