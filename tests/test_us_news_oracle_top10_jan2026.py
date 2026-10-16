import numpy as np
import pandas as pd
import pytest

from scripts.research import us_news_oracle_top10_jan2026 as study


def path():
    return pd.DataFrame(dict(open=[100.]*20,high=[101.]*20,low=[99.]*20,close=[100.]*20,
        volume=[1000]*20,is_filled=[0]*20,data_adjustment=['split']*20,instrument_id=[1]*20),
        index=pd.bdate_range('2026-01-05',periods=20))


def test_tp_then_later_sl_and_reverse_are_not_terminal_direction():
    f=path();f.iloc[2,f.columns.get_loc('high')]=125;f.iloc[7,f.columns.get_loc('low')]=80
    assert study.path_result(f,'LONG')['outcome']=='TP'
    assert study.path_result(f,'LONG')['terminal_signed_return_pct']==0
    f=path();f.iloc[2,f.columns.get_loc('low')]=80;f.iloc[7,f.columns.get_loc('high')]=125
    assert study.path_result(f,'LONG')['outcome']=='SL'


def test_same_bar_order_ambiguous_but_open_gap_takes_precedence():
    f=path();f.iloc[2,f.columns.get_loc('high')]=125;f.iloc[2,f.columns.get_loc('low')]=80
    assert study.path_result(f,'LONG')['outcome']=='AMBIGUOUS'
    f.iloc[2,f.columns.get_loc('open')]=85
    assert study.path_result(f,'LONG')['outcome']=='SL_GAP'
    f.iloc[2,f.columns.get_loc('open')]=121
    assert study.path_result(f,'LONG')['outcome']=='TP_GAP'


def test_short_mirror_and_twenty_sessions_only():
    f=path();f.iloc[19,f.columns.get_loc('low')]=79
    assert study.path_result(f,'SHORT')['outcome']=='TP'
    assert study.path_result(f,'SHORT')['max_favourable_pct']==pytest.approx(21)
    assert study.path_result(path().iloc[:19],'LONG')['qualified'] is False
    assert study.path_result(path(),'LONG')['outcome']=='TIMEOUT'


@pytest.mark.parametrize('col,value',[
    ('is_filled',1),('volume',0),('instrument_id',2),('data_adjustment','raw'),('open',np.nan),('high',98)])
def test_path_quality_rejects_bad_row_without_imputation(col,value):
    f=path();f.loc[f.index[4],col]=value
    assert study.path_result(f,'LONG')['qualified'] is False


def test_metrics_keeps_ambiguity_and_unknown_separate():
    rows=[]
    for i,outcome in enumerate(('TP','SL','AMBIGUOUS','TIMEOUT')):
        rows.append(dict(symbol='A',date=pd.Timestamp('2026-01-02')+pd.Timedelta(days=i),
            qualified=True,reason=None,outcome=outcome,terminal_signed_return_pct=5.,
            max_favourable_pct=22.,max_adverse_pct=-12.))
    rows.append(dict(symbol='B',date=pd.Timestamp('2026-01-02'),qualified=False,reason='MISSING'))
    m=study.metrics(pd.DataFrame(rows))
    assert m['selected']==5 and m['qualified']==4 and m['rejected']==1
    assert m['tp20_before_sl10_lower_pct']==25
    assert m['tp20_before_sl10_upper_pct']==50
    assert m['sl_first_conservative_pct']==50
    assert m['timeout_pct']==25


def test_selection_is_original_score_order_not_future_returns():
    model={'model_sha256':'weights','profile_sha256':'features'}
    rows=[dict(date='2026-01-02',symbol=f'S{i:02}',score=1-i/30,oracle_rank=i+1,
        fold_start='2025-12-10',lineage_fold='2025-12-10',model_sha256='weights',
        feature_profile_sha256='features',target_name='oracle_path_extreme20',target_horizon=20,
        model_available_date='2025-12-09',future_return=None,oracle_extreme10=None) for i in range(20)]
    f=pd.DataFrame(rows)
    top=study.select_top(f.iloc[::-1],['2026-01-02'],model)
    assert top.symbol.tolist()==[f'S{i:02}' for i in range(10)]
    f.loc[0,'future_return']=.9
    with pytest.raises(ValueError,match='Future labels'):
        study.select_top(f,['2026-01-02'],model)
