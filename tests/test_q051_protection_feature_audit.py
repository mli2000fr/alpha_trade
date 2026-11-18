import numpy as np
import pandas as pd
import pytest

from scripts.research.us_q051_protection_features_data_20261118 import aggregate,mature_series


def test_mature_feature_ignores_future_outcomes_and_unknowns_are_not_losses():
    days=pd.bdate_range('2021-01-01',periods=60)
    rows=pd.DataFrame({'available':np.repeat(days,10),'outcome':np.resize([0.,1.],600)})
    a=mature_series(rows,days,'outcome','available')
    changed=rows.copy();changed.loc[changed.available.gt(days[30]),'outcome']=1.
    pd.testing.assert_frame_equal(a.loc[:days[30]],mature_series(changed,days,'outcome','available').loc[:days[30]])
    missing=rows.copy();missing.loc[missing.available.le(days[20]),'outcome']=np.nan
    b=mature_series(missing,days,'outcome','available')
    assert pd.isna(b.loc[days[10],'rate5']) and b.loc[days[10],'coverage5']==0
    assert a.loc[days[10],'rate5']==.5


def test_aggregation_keeps_unknown_features_and_is_cross_sectional_per_day():
    a=pd.DataFrame({'date':np.repeat(pd.to_datetime(['2021-01-04','2021-01-05']),5),
        'feature':[1.,2.,3.,4.,5.,np.nan,np.nan,np.nan,20.,30.]})
    actual=aggregate(a,['feature'],'pool')
    assert actual.iloc[0]['pool__median__feature']==3.
    assert actual.iloc[0]['pool__iqr__feature']==2.
    assert pd.isna(actual.iloc[1]['pool__median__feature'])
    altered=a.copy();altered.loc[altered.date.gt(pd.Timestamp('2021-01-04')),'feature']=999.
    pd.testing.assert_series_equal(actual.iloc[0],aggregate(altered,['feature'],'pool').iloc[0])


def test_empirical_transform_uses_training_distribution_only():
    from scripts.research.us_q051_protection_feature_audit_20261118 import empirical
    train=np.arange(100,dtype=float);values=np.array([10.,50.,np.nan])
    a=empirical(train,values,1);b=empirical(train,np.r_[values,1e9],1)
    np.testing.assert_equal(a,b[:3]);assert np.isnan(a[-1])


def test_selected_feature_ids_do_not_use_future_auc(tmp_path,monkeypatch):
    from scripts.research import us_q051_protection_feature_audit_20261118 as audit
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    days=pd.bdate_range('2021-01-01',periods=100)
    features=pd.DataFrame({'market__a':np.arange(100),'market__b':np.sin(np.arange(100))},index=days)
    rows=[]
    for target in ['risk20','recovery20']:
        rows.extend([dict(feature='market__a',family='market',target=target,discovery_score=.65,auc_2022=.7,eligible=True,auc_2026=.1),
            dict(feature='market__b',family='market',target=target,discovery_score=.60,auc_2022=.6,eligible=True,auc_2026=.9)])
    table=pd.DataFrame(rows);mask=np.ones(100,dtype=bool)
    a=audit.select_features(table,features,mask).feature.tolist()
    table['auc_2026']=1-table.auc_2026
    b=audit.select_features(table,features,mask).feature.tolist()
    assert a==b==['market__a','market__a']


def test_hysteresis_state_is_causal_and_minimum_hold_is_respected():
    from scripts.research.us_q051_protection_feature_audit_20261118 import state_machine
    days=pd.bdate_range('2024-01-02',periods=10)
    scores=pd.DataFrame(dict(risk=.9,recovery=.9,risk_votes=3,recovery_votes=3),index=days)
    a=state_machine(scores,.8,.5,off_confirm=1)
    assert a.iloc[1].transition=='ON' and a.iloc[4].transition=='OFF'
    pd.testing.assert_frame_equal(a.iloc[:6],state_machine(scores.iloc[:6],.8,.5,off_confirm=1))


def test_relative_levels_ignore_future_and_preserve_warmup_unknowns():
    from scripts.research.us_q051_protection_adaptive_audit_20261118 import relative_levels
    dates=pd.bdate_range('2021-01-01',periods=200);f=pd.DataFrame({'x':np.arange(200,dtype=float)},index=dates)
    a=relative_levels(f)
    assert a.iloc[:63].isna().all().all()
    pd.testing.assert_frame_equal(a.iloc[:100],relative_levels(f.iloc[:100]))
    changed=f.copy();changed.iloc[100:]=1e9
    pd.testing.assert_frame_equal(a.iloc[:100],relative_levels(changed).iloc[:100])


def test_archival_coverage_cannot_be_an_economic_risk_signal():
    from scripts.research.us_q051_protection_qualified_audit_20261118 import diagnostic_only
    assert diagnostic_only('quality_PER_SL10__reference_coverage')
    assert diagnostic_only('internal_oracle179__net_long__coverage5__delta5')
    assert not diagnostic_only('internal_oracle179__net_long__rate5')
    assert not diagnostic_only('scores_B10__median__long_probability')


def test_macro_relative_levels_and_changes_do_not_read_future_rows():
    from scripts.research.us_q051_protection_macro_sensitivity_20261118 import macro_features
    dates=pd.bdate_range('2021-01-01',periods=180)
    a=pd.DataFrame({c:20.+np.arange(180)*.1 for c in ['vix','vix9d','vix3m','vxn','move','ten_y']})
    a['trade_date']=dates;rows=a.to_dict('records')
    f=macro_features(rows,dates)
    pd.testing.assert_frame_equal(f.iloc[:100],macro_features(rows[:100],dates[:100]))
    a.loc[100:,'vix']=1e8
    pd.testing.assert_frame_equal(f.iloc[:100],macro_features(a.to_dict('records'),dates).iloc[:100])
