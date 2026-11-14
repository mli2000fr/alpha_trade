import numpy as np
import pandas as pd

from backtesting.range_support_entry import aggregate_m15,freeze_range,RangeSupportSettings
from scripts.research.us_a2_bulk_frequency import m15_groups,freeze_many,as_candles


def test_bulk_m15_matches_scalar_with_holes_and_two_symbols():
    from tests.test_range_support_entry import tape
    f=tape();f['symbol']='A';b=f.copy();b['symbol']='B';b=b.drop(index=4)
    all_bars=pd.concat([f,b],ignore_index=True)
    opening=pd.Timestamp('2026-10-19T13:30Z');closing=pd.Timestamp('2026-10-19T20:00Z')
    groups=m15_groups(all_bars,opening,closing)
    for s,g in all_bars.groupby('symbol'):
        scalar=aggregate_m15(g,opening.date(),known_at=closing)
        np.testing.assert_array_equal(groups[s][0],pd.DatetimeIndex(scalar.timestamp).asi8)
        np.testing.assert_allclose(groups[s][1],scalar[['open','high','low','close','volume']].to_numpy())
    assert len(as_candles(groups['B'],opening,closing))==1


def test_bulk_freezing_matches_original_wilder_and_rule_order():
    rng=np.random.default_rng(1234);windows=[]
    for _ in range(200):
        close=100+np.cumsum(rng.normal(.1,.4,46));op=np.r_[close[0],close[:-1]]
        hi=np.maximum(op,close)+rng.uniform(.1,.5,46);lo=np.minimum(op,close)-rng.uniform(.1,.5,46)
        windows.append(np.column_stack([op,hi,lo,close,np.full(46,100.)]))
    # Explicitly include a qualifying range, so matching rejection counts is
    # not the only parity evidence.
    v=np.tile([100.,101.,99.,100.,100.],(46,1))
    for i in range(14,26):v[i,:4]=[100+(i-14)*.5,100+(i-13)*.5+.2,100+(i-14)*.5-.2,100+(i-13)*.5]
    for i in range(26,46):
        p=106.+(.6 if i%2 else 0.);v[i,:4]=[p+.1,p+.4,p,p+.2]
    windows.append(v)
    end=pd.Timestamp('2026-10-16T20:00Z');zones,reasons=freeze_many(np.stack(windows),end)
    for values,zone,reason in zip(windows,zones,reasons):
        f=pd.DataFrame(values,columns=['open','high','low','close','volume'])
        f['end']=pd.date_range(end=end,periods=46,freq='15min')
        old,status=freeze_range(f)
        assert reason==status
        if old is not None:
            for key in ['low','high','atr','tolerance','impulse_atr']:
                np.testing.assert_allclose(zone[key],old[key],rtol=0,atol=1e-12)
            assert zone['low_touches']==old['low_touches'] and zone['high_touches']==old['high_touches']
    assert reasons[-1]=='RANGE_READY'
