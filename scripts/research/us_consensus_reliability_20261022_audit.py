"""Offline scalar review of received-consensus features/short returns, no SQL."""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_consensus_reliability_20261022 as study


def audit(root):
    p=study.check(root)
    report=study.read(root/'report.json')
    for name,expected in report['files'].items():
        assert study.digest(root/name)==expected,name
    source={int(r['id']):r for r in pd.read_parquet(root/'consensus.parquet').to_dict('records')}
    runs={r['run_id']:r for r in pd.read_parquet(root/'runs.parquet').to_dict('records')}
    features=pd.read_parquet(root/'features.parquet')
    assert not features.duplicated(['symbol','entry_date']).any()
    assert len(features)==report['decision_pairs']
    assert features.entry_date.nunique()==report['decision_dates']
    for row in features.itertuples():
        a,b=source[row.old_id],source[row.new_id]
        assert a['symbol']==b['symbol']==row.symbol
        assert a['horizon_raw']==b['horizon_raw']=='0q'
        assert str(a['fiscal_period_end'])[:10]==str(b['fiscal_period_end'])[:10]==str(row.fiscal_anchor)[:10]
        stamps=[]
        for record,bound in [(a,row.prior_open),(b,row.entry_open)]:
            parent=runs[record['run_id']]
            assert parent['status']=='COMPLETED'
            available=max([study.utc(record[k]) for k in ('observed_at','available_at','ingestion_at')]+
                          [study.utc(parent['finished_at'])])
            assert available<bound
            assert available>=bound-pd.Timedelta(days=4)
            stamps.append(available)
        assert stamps==[row.old_available,row.new_available]
        assert row.entry_open<study.utc(p['cutoff_utc'])
        for metric in ('revenue','eps'):
            old,new=a.get(metric+'_avg'),b.get(metric+'_avg')
            good=pd.notna(old) and pd.notna(new) and np.isfinite([old,new]).all()
            if metric=='revenue':good=good and min(old,new)>0
            delta=float(new-old) if good else np.nan
            actual=getattr(row,metric+'_delta')
            assert (pd.isna(delta) and pd.isna(actual)) or abs(delta-actual)<1e-8
            assert getattr(row,metric+'_sign')==(int(np.sign(delta)) if good else 0)
    prices=pd.read_parquet(root/'prices.parquet')
    prices['date']=pd.to_datetime(prices.date)
    lookup={(r.symbol,r.date):r for r in prices.itertuples()}
    cal=study.schedule()
    checked=0
    unknowns={}
    for horizon in (1,3,5):
        scored=pd.read_parquet(root/f'diagnostic-H{horizon}.parquet')
        assert len(scored)==len(features)
        assert (scored.exit_idx==scored.entry_idx+horizon-1).all()
        expected=pd.to_datetime(scored.exit_idx.map(cal.closing.to_dict()),utc=True)
        assert (scored.maturity==expected).all()
        assert np.array_equal(scored.mature,expected.lt(study.utc(p['cutoff_utc'])))
        assert scored.loc[~scored.mature,'return_pct'].isna().all()
        selected=scored[scored.return_pct.notna()]
        for row in selected.itertuples():
            days=cal.day.iloc[row.entry_idx:row.exit_idx+1]
            assert len(days)==horizon
            for symbol in (row.symbol,'SPY'):
                bars=[lookup[symbol,day] for day in days]
                assert all(b.open>0 and b.close>0 and b.volume>0 and b.is_filled==0 for b in bars)
                value=(float(bars[-1].close)/float(bars[0].open)-1)*100
                expected_return=row.return_pct if symbol==row.symbol else row.spy_return_pct
                assert abs(value-expected_return)<1e-9
                checked+=1
        primary=scored[scored.revenue_technical_ok & scored.revenue_count_group.eq('UNCHANGED_COUNT') &
                       scored.revenue_sign.ne(0) & scored.return_pct.notna()]
        summary=report['horizons'][str(horizon)]['groups']['REVENUE_UNCHANGED_COUNT_PRIMARY']['all']
        assert len(primary)==summary['n']
        assert primary.entry_date.nunique()==summary['dates']
        if len(primary):
            signed=primary.revenue_sign*primary.return_pct
            assert abs(signed.mean()-summary['signed_mean_pct'])<1e-9
            assert abs((signed>0).mean()*100-summary['correct_sign_pct'])<1e-9
            assert abs(signed.mean()-.16-summary['after_16bps_mean_pct'])<1e-9
        unknowns[str(horizon)]=scored.price_status.value_counts().to_dict()
    assert not report['horizons']['10']['outcomes_reported']
    assert not (root/'diagnostic-H10.parquet').exists()
    assert not report['minimum_independent_confirmation_met']
    assert not report['live_qualified'] and not report['pnl'] and not report['sql_writes']
    result=dict(status='PASS_CAUSAL_RECEIPTS_SIGNS_MATURITY_AND_SCALAR_PRICES',
        feature_pairs_checked=len(features),scalar_prices_checked=checked,price_reserves=unknowns,
        independent_human_review=False,full_supplier_truth_or_economic_qualification=False,
        report_sha256=study.digest(root/'report.json'),auditor_sha256=study.digest(Path(__file__)))
    study.save(root/'final-audit.json',result)
    print(result,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=study.ROOT)
    audit(parser.parse_args().output_dir)
