import numpy as np
import pandas as pd
import pytest

from scripts.research.us_q051_ceiling_overlays_20261128 import apply_anti_sl
from scripts.research.us_q051_entry_ceiling_20261127 import expand_windows


def test_veto_is_on_original_signal_no_refill_and_before_wait_expansion():
    days=pd.to_datetime(['2024-01-02','2024-01-03','2024-01-04','2024-01-05'])
    panel=pd.DataFrame(dict(entry_year=2024,origin_signal_date=days[:2],trade_date=days[:2],
        symbol=['A','A'],origin_id=['old','new'],rank=[1,1]))
    scores=pd.DataFrame(dict(entry_year=2024,origin_signal_date=days[:2],symbol=['A','A'],
        SL10_risk=[.3,.8],SL10_threshold=.5,SL10_available='2023-12-20'))
    checked=apply_anti_sl(panel,scores)
    assert checked.anti_sl_excluded.tolist()==[False,True]
    kept=checked[~checked.anti_sl_excluded][panel.columns]
    expanded,superseded=expand_windows(kept,days)
    assert expanded.origin_id.tolist()==['old','old'] and superseded.empty
    assert expanded.entry_day.tolist()==list(days[1:3])
    # Future outcomes never enter the score gate.
    scores['eventual_return']=1000
    pd.testing.assert_frame_equal(checked,apply_anti_sl(panel,scores))


def test_veto_requires_strictly_past_model_and_duplicate_scores_fail():
    day=pd.Timestamp('2024-01-02')
    panel=pd.DataFrame(dict(entry_year=[2024,2024],origin_signal_date=day,symbol=['A','B']))
    scores=pd.DataFrame(dict(entry_year=[2024,2024],origin_signal_date=day,symbol=['A','B'],
        SL10_risk=[.5,np.nan],SL10_threshold=[.5,np.nan],SL10_available=['2023-12-20',None]))
    checked=apply_anti_sl(panel,scores)
    assert checked.anti_sl_excluded.tolist()==[False,False]
    scores.loc[0,'SL10_available']='2024-01-02'
    with pytest.raises(ValueError,match='strictly before'):apply_anti_sl(panel,scores)
    with pytest.raises(ValueError,match='Duplicate'):apply_anti_sl(panel,pd.concat([scores,scores]))


@pytest.mark.parametrize('scheduled',[False,True])
def test_portfolio_budget_covers_scheduled_and_daily_observed_prices(scheduled):
    from scripts.research.us_q051_ceiling_overlays_20261128 import observed_open_policy
    dates=pd.bdate_range('2024-01-02',periods=70)
    close=pd.DataFrame({'A':100.*np.cumprod(np.resize([1.1,.9],len(dates)))},index=dates)
    policy=observed_open_policy(close,target=.20)
    now=(dates[-1]+pd.offsets.BDay()).tz_localize('America/New_York')+pd.Timedelta(hours=10)
    source='OBSERVED_5M_OPEN' if scheduled else 'CANONICAL_DAILY_OPEN'
    snapshot={'opening_at':now,'price_source':source,('entry_open' if scheduled else 'daily_open'):100.}
    seen=[]
    def native(state,version,proposed,snapshot,now,*,context):
        seen.append(snapshot.copy());return {'max_quantity':min(10,proposed)}
    result=policy.wrap(native)({'symbol':'A'},1,10,snapshot,now,
        context={'equity':1000.,'positions':[],'pending_entries':[]})
    assert result['max_quantity']<10
    assert policy.receipts[0]['price_source']==source
    assert policy.receipts[0]['observed_price']==100.
    assert all(s['daily_open']==100. for s in seen)
