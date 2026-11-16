import pandas as pd
from scripts.research.us_q051_sl_pause_20261116 import StopLedger,choose,Selection


def test_progress_writes_inside_isolated_case_only(tmp_path):
    from backtesting.isolation import ReadOnlyReplay
    from scripts.research.us_q051_sl_pause_20261116 import case_progress,read
    folder=tmp_path/'campaign'/'cases'/'CONTROL'
    folder.mkdir(parents=True)
    with ReadOnlyReplay(folder).install():
        case_progress(folder,'CONTROL',1,1443,'2021-01-04',0)
    assert read(folder/'progress.json')['completed']==1
    assert not (tmp_path/'campaign'/'progress.json').exists()


def calendar():
    return list(pd.bdate_range('2021-01-01',periods=350).date)


def stamp(days,i,time='20:00'):
    return pd.Timestamp(f'{days[i]} {time}',tz='America/New_York')


def test_thirty_sessions_inclusive_and_hundred_complete_pause_sessions():
    days=calendar();s=StopLedger(days)
    s.observe('X','STOP',stamp(days,1),'a');s.observe('X','STOP_GAP',stamp(days,30),'b')
    assert s.blocked(stamp(days,30))=={'X'}
    assert s.receipts[0]['resume_session']==str(days[131])
    assert s.blocked(stamp(days,130,'09:30'))=={'X'}
    assert s.blocked(stamp(days,131,'09:30'))==set()


def test_outside_thirty_and_non_sl_exit_reset_streak():
    days=calendar();s=StopLedger(days)
    for i,reason in [(1,'STOP'),(31,'STOP'),(32,'HORIZON_OPEN'),(33,'STOP')]:
        s.observe('X',reason,stamp(days,i),str(i))
    assert s.blocked(stamp(days,33))==set()
    s.observe('X','STOP',stamp(days,34),'34')
    assert s.blocked(stamp(days,34))=={'X'}


def test_no_future_observation_and_same_open_gap_veto():
    days=calendar();s=StopLedger(days)
    s.observe('X','STOP',stamp(days,1),'a')
    s.observe('X','STOP_GAP',stamp(days,5,'09:30'),'b')
    assert s.blocked(stamp(days,5,'09:29:59'))==set()
    assert s.blocked(stamp(days,5,'09:30'))=={'X'}


def test_excludes_before_oracle_fraction_and_promotes_next_rank():
    f=pd.DataFrame(dict(date=pd.Timestamp('2021-02-01'),symbol=[f'S{i:02}' for i in range(20)],
        proba_extreme=[1-i/25 for i in range(20)],long_probability=.8,short_probability=float('nan'),
        long_auc=.7,long_auc_available_date='2020-12-30',long_auc_source='calibration',
        long_auc_model_sha256='x',long_model_sha256='x'))
    s,top=choose(f,{'S00'},universe_size=20,long_top_n=1)
    assert top==2 and s.symbol.tolist()==['S01']
    s,top=choose(f,{'S00','S01','S02','S03','S04','S05','S06','S07','S08','S09'},universe_size=20,long_top_n=1)
    assert top==1 and s.symbol.tolist()==['S10']


def test_threshold_no_refill_after_long_top_rank():
    f=pd.DataFrame(dict(date=pd.Timestamp('2021-02-01'),symbol=['A','B'],proba_extreme=[.9,.8],
        long_probability=[.9,.8],short_probability=float('nan'),long_auc=[.4,.7],
        long_auc_available_date='2020-12-30',long_auc_source='calibration',
        long_auc_model_sha256='x',long_model_sha256='x'))
    selected,_=choose(f,set(),universe_size=20,long_top_n=1)
    assert selected.empty


def test_selection_preserves_long_priority_in_native_daily_copy():
    days=calendar();ledger=StopLedger(days)
    f=pd.DataFrame(dict(trade_date=pd.Timestamp('2021-02-01'),symbol=['A','B'],proba_extreme=[.9,.8],
        long_probability=[.7,.9],short_probability=float('nan'),long_auc=.7,
        long_auc_available_date='2020-12-30',long_auc_source='calibration',
        long_auc_model_sha256='x',long_model_sha256='x',rank=1))
    selector=Selection(ledger,{'A','B'}|{f'Z{i}' for i in range(18)})
    assert selector(days[20],f,stamp(days,21,'09:29:59'))['selected']==['B','A']
    assert f.set_index('symbol')['rank'].to_dict()=={'A':2,'B':1}
