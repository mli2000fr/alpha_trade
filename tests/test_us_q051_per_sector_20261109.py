import numpy as np
import pandas as pd

from scripts.research.us_q051_per_sector_20261109 import sector_name,train_sector,model_predictions,merge_benchmark
from modelFactory.oracle_path.directional import INPUTS


def test_current_sector_mapping_does_not_invent_unknown_membership():
    assert sector_name('Information Technology')=='Information Technology'
    assert sector_name('technology')=='Information Technology'
    assert sector_name('Biotechnology')=='Health Care'
    assert sector_name('Consumer Defensive')=='Consumer Staples'
    assert sector_name('Transportation')=='Industrials'
    assert sector_name(None) is None and sector_name('unknown') is None


def test_benchmark_reconstruction_only_extends_identical_archives():
    import pytest
    f=pd.DataFrame({c:[100.,101.,102.] for c in ['open','high','low','close','adj_close','volume']})
    f['date']=pd.bdate_range('2020-01-01',periods=3)
    pd.testing.assert_frame_equal(merge_benchmark(f.iloc[:2],f.iloc[1:]),f)
    changed=f.iloc[1:].copy();changed.loc[1,'close']=999.
    with pytest.raises(ValueError,match='disagree'):merge_benchmark(f.iloc[:2],changed)


def test_sector_training_is_purged_and_ignores_future_test_year_rows(tmp_path):
    import joblib
    rng=np.random.default_rng(12);days=pd.bdate_range('2015-01-01','2021-12-31')
    frames=[]
    for symbol in ['A','B','C','D']:
        x=pd.DataFrame(rng.normal(size=(len(days),len(INPUTS))),columns=INPUTS)
        x['symbol']=symbol;x['date']=days;x['available']=days+pd.Timedelta(days=16)
        x['long']=(x.return_5d+.3*rng.normal(size=len(x))>0).astype(float);frames.append(x)
    panel=pd.concat(frames,ignore_index=True)
    first=tmp_path/'first';first.mkdir();second=tmp_path/'second';second.mkdir()
    a,aucs=train_sector(panel,2021,'Information Technology',first)
    assert pd.Timestamp(a['fit_available_max'])<pd.Timestamp('2020-01-01')
    assert pd.Timestamp(a['available'])<pd.Timestamp('2021-01-01')
    assert len(aucs)==4 and all(r['source']=='calibration' and r['qualified'] for r in aucs)
    assert all(r['model_sha256']==a['sha256'] for r in aucs)
    panel.loc[panel.date.dt.year.eq(2021),INPUTS]=1000.
    panel.loc[panel.date.dt.year.eq(2021),'long']=1.
    b,other=train_sector(panel,2021,'Information Technology',second)
    assert a['fit_rows']==b['fit_rows'] and a['calibration_rows']==b['calibration_rows']
    assert a['calibration_metrics']==b['calibration_metrics']
    sample=panel[panel.date.dt.year.eq(2019)].head(20)
    np.testing.assert_array_equal(model_predictions(joblib.load(a['file']),sample),
                                  model_predictions(joblib.load(b['file']),sample))


def test_benchmark_slice_index_does_not_lose_test_year_features():
    from pathlib import Path
    from scripts.research.us_q051_per_sector_recovery_20261109 import safe_panels
    from modelFactory.oracle.build_labels import nyse_sessions
    root=Path('artifacts/models/model-factory-20261107222627-db80b0/oracle_path')
    start,end=pd.Timestamp('2020-03-21'),pd.Timestamp('2022-12-29')
    bars=pd.read_parquet(root/'chunks/0000/bars.parquet')
    bars=bars[bars.symbol.eq('AA')&bars.date.between(start,end)]
    benchmark=pd.read_parquet(root/'directional/benchmark.parquet')
    benchmark=benchmark[benchmark.date.between(start,end)]
    assert benchmark.index.min()>0
    calendar=nyse_sessions(start.date(),end.date())
    a=safe_panels(bars,benchmark,calendar)
    b=safe_panels(bars,benchmark.reset_index(drop=True),calendar)
    pd.testing.assert_frame_equal(a,b)
    assert a.date.max()==end and a.date.dt.year.eq(2022).sum()>200
    close=benchmark.adj_close.fillna(benchmark.close).reset_index(drop=True)
    expected=close.iloc[-1]/close.iloc[-6]-1
    np.testing.assert_allclose(a.iloc[-1].benchmark_return_5,expected,rtol=0,atol=1e-12)
