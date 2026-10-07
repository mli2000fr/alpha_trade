import pandas as pd
import pytest

from scripts.research.us_extreme50_capture import (
    POLICIES, cluster_events, forbid_writes, freeze_selection, metrics, qualify_endpoints,
)


def inputs():
    day = pd.Timestamp('2025-01-02')
    symbols = [f'S{i:03}' for i in range(100)]
    scores = pd.DataFrame({'date': day, 'symbol': symbols, 'proba_extreme': range(100)})
    atr = pd.DataFrame({'date': day, 'symbol': symbols, 'atr20_pct': [i+1 for i in range(100)]})
    return scores, atr


def test_percent_pools_and_count_pools_are_distinct_and_deterministic():
    scores, atr = inputs()
    first = freeze_selection(scores, atr)
    assert first.ORACLE_TOP20.sum() == 21  # Inclusive percentile boundary.
    assert first.ORACLE_TOP20_COUNT.sum() == 20
    assert first.ORACLE_TOP10.sum() == 10
    assert first.INTERSECTION_ORACLE_TOP50.sum() == 21
    second = freeze_selection(scores.sample(frac=1, random_state=1), atr.sample(frac=1, random_state=2))
    pd.testing.assert_frame_equal(first, second)
    scores.proba_extreme = 1
    tied = freeze_selection(scores, atr)
    assert tied.loc[tied.ORACLE_TOP10, 'symbol'].tolist() == scores.symbol.tolist()[:10]


def test_missing_atr_not_zero_and_cannot_affect_oracle_population():
    scores, atr = inputs()
    result = freeze_selection(scores, atr.iloc[:50])
    assert len(result) == 100 and result.atr20_pct.isna().sum() == 50
    assert result.ORACLE_TOP20.sum() == 21
    assert result.INTERSECTION.sum() == 0
    with pytest.raises(ValueError, match='Duplicate'):
        freeze_selection(pd.concat([scores, scores]), atr)


def test_price_checks_detect_mismatch_zero_volume_and_impossible_return():
    labels = pd.DataFrame({'date': pd.to_datetime(['2025-01-02']*3), 'symbol': ['A','B','C'],
        'oracle_exit_date': pd.to_datetime(['2025-02-03']*3),
        'future_return': [.5, .5, -1.2], 'future_return_raw': [.5,.5,-1.2]})
    bars = pd.DataFrame({'date':pd.to_datetime(['2025-01-02']*3+['2025-02-03']*3),
        'symbol':['A','B','C']*2, 'close':[10,10,10,15,16,1],
        'adj_close':[10,10,10,15,16,1], 'volume':[100,0,100,100,100,100],
        'is_filled':False, 'instrument_id':[1,2,3]*2})
    checked = qualify_endpoints(labels, bars).set_index('symbol')
    assert checked.loc['A','local_endpoint_ok']
    assert checked.loc['B','endpoint_mismatch'] and checked.loc['B','zero_endpoint_volume']
    assert checked.loc['C','impossible_long_return']
    assert not checked.loc['B','local_endpoint_ok']


def test_missing_endpoint_never_passes_local_checks():
    labels = pd.DataFrame({'date': [pd.Timestamp('2025-01-02')], 'symbol':['A'],
        'oracle_exit_date':[pd.Timestamp('2025-02-03')], 'future_return':[.5], 'future_return_raw':[.5]})
    bars = pd.DataFrame({'date':[pd.Timestamp('2025-01-02')], 'symbol':['A'],
        'close':[10], 'adj_close':[10], 'volume':[100], 'is_filled':[False], 'instrument_id':[1]})
    result = qualify_endpoints(labels, bars)
    assert result.missing_adjusted_endpoint.all()
    assert not result.local_endpoint_ok.any()


def test_metrics_unknowns_and_signed_tails_are_separate():
    scores, atr = inputs()
    data = freeze_selection(scores, atr)
    data['future_return'] = .1
    data.loc[data.symbol.eq('S099'),'future_return'] = -.6
    data.loc[data.symbol.eq('S098'),'future_return'] = 1.2
    data['target_quality_valid'] = 1
    data.loc[data.symbol.eq('S097'),'target_quality_valid'] = 0
    data['oracle_available_date'] = pd.Timestamp('2025-03-01')
    data['local_endpoint_ok'] = True
    results = metrics(data, as_of='2026-10-06')
    row = next(r for r in results if r['policy']=='ORACLE_TOP10' and r['scope']=='LABEL_VALID'
               and r['threshold_pct']==50 and r['side']=='ABS')
    assert row['selected'] == 10 and row['evaluated'] == 9 and row['unknown'] == 1
    assert row['target_hits'] == 2 and row['capture_pct'] == 100
    downside100 = [r for r in results if r['threshold_pct']==100 and r['side']=='DOWN']
    assert all(r['target_hits']==0 and r['capture_pct'] is None for r in downside100)
    data['oracle_available_date'] = pd.NaT
    assert all(r['evaluated']==0 for r in metrics(data, as_of='2026-10-06'))


def test_cluster_overlapping_windows_not_independent_trades():
    tails = pd.DataFrame({'symbol':['A']*3, 'side':['UP']*3,
        'date':pd.to_datetime(['2025-01-02','2025-01-03','2025-02-04']),
        'oracle_exit_date':pd.to_datetime(['2025-02-03','2025-02-04','2025-03-04']),
        'future_return':[.5,.6,.7], **{p:[False,True,False] for p in POLICIES}})
    result = cluster_events(tails)
    assert len(result)==2 and result[0]['windows']==2
    assert result[0]['ORACLE_TOP20'] and not result[1]['ORACLE_TOP20']


@pytest.mark.parametrize('sql',['UPDATE a SET b=0','INSERT INTO a VALUES(1)','DELETE FROM a','CREATE TABLE a(b INT)'])
def test_sql_write_guard(sql):
    with pytest.raises(RuntimeError, match='Read-only'):
        forbid_writes(None,None,sql,None,None,False)
    forbid_writes(None,None,' SELECT * FROM a',None,None,False)
