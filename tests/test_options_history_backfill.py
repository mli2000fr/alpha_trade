from datetime import date, datetime

import pytest

from service.alpaca.options_history_backfill import failure_limit_reached, monthly_ranges, normalized_row, select_pairs


def contract(side, strike=100, expiry='2024-02-09'):
    return {'symbol':f'ABC{side}{strike}', 'underlying_symbol':'ABC', 'type':side,
        'strike_price':str(strike),'expiration_date':expiry}


def test_month_ranges_start_on_requested_day():
    assert list(monthly_ranges(date(2024,1,20),date(2024,2,3)))==[
        (date(2024,1,20),date(2024,1,31)),(date(2024,2,1),date(2024,2,3))]


def test_same_strike_pairs_and_dedup_targets():
    items=[contract('call',100),contract('put',100),contract('call',101)]
    result=select_pairs(items,101,date(2024,1,22),targets=(15,20),tolerance=5)
    assert {x['symbol'] for x in result}=={'ABCcall100','ABCput100'}
    assert len(result)==2


def test_missing_put_and_expired_contract_not_selected():
    assert select_pairs([contract('call')],100,date(2024,1,22))==[]
    assert select_pairs([contract('call',expiry='2024-01-22'),contract('put',expiry='2024-01-22')],
        100,date(2024,1,22))==[]


def test_preserve_actual_download_date_and_historical_bar_time():
    observed=datetime(2026,10,10,22)
    item={'t':'2024-01-22T05:00:00Z','o':1,'h':2,'l':.5,'c':1.5,'v':12,'n':4,'vw':1.1}
    row=normalized_row(contract('call'),item,observed=observed,run_id='test')
    assert row['ts']==datetime(2024,1,22,5)
    assert row['observed']==observed
    assert row['timeframe']=='1Day'
    assert row['provenance']=='UNVERIFIED_OPRA'
    assert row['hash']==normalized_row(contract('call'),item,observed=datetime(2026,10,11),run_id='other')['hash']


def test_invalid_bar_is_rejected():
    item={'t':'2024-01-22T05:00:00Z','o':1,'h':.5,'l':.5,'c':1,'v':12}
    with pytest.raises(ValueError,match='Inconsistent'):
        normalized_row(contract('call'),item,observed=datetime.now(),run_id='test')


def test_failure_threshold_counts_total_not_consecutive():
    statuses={str(i):{'status':'FAILED' if i%2==0 else 'COMPLETED'} for i in range(1998)}
    assert not failure_limit_reached(statuses,1000)
    statuses['last']={'status':'FAILED'}
    assert failure_limit_reached(statuses,1000)
    with pytest.raises(ValueError):
        failure_limit_reached(statuses,0)
