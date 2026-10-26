"""Independent scalar formulation of confirmation/exit calculations; same assistant."""
import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_consensus_confirmation_exit_20261022 as study
from scripts.research.us_consensus_confirmation_exit_split_20261022 import ROOT


def scalar(prices,sign,inverse_day=None):
    entry=float(prices.iloc[0].open)
    tp=entry*(1+sign*.1);sl=entry*(1-sign*.05)
    def lower(a,b):return a<b or math.isclose(a,b,rel_tol=1e-12,abs_tol=0)
    def upper(a,b):return a>b or math.isclose(a,b,rel_tol=1e-12,abs_tol=0)
    for j,r in enumerate(prices.itertuples()):
        opening=float(r.open)
        stop_open=lower(opening,sl) if sign==1 else upper(opening,sl)
        target_open=upper(opening,tp) if sign==1 else lower(opening,tp)
        stop_inside=lower(float(r.low),sl) if sign==1 else upper(float(r.high),sl)
        tp_inside=upper(float(r.high),tp) if sign==1 else lower(float(r.low),tp)
        if stop_open:price,reason=opening,'STOP_GAP'
        elif target_open:price,reason=tp,'TP_GAP_CAPPED'
        elif inverse_day is not None and j==inverse_day:price,reason=opening,'INVERSE_AT_OPEN'
        elif stop_inside:price,reason=sl,'STOP_TOUCH_BOTH' if tp_inside else 'STOP_TOUCH'
        elif tp_inside:price,reason=tp,'TP_TOUCH'
        else:continue
        return sign*(price/entry-1)*100,reason,j
    return sign*(float(prices.iloc[-1].close)/entry-1)*100,'HORIZON_CLOSE',len(prices)-1


def audit(root):
    p=study.check(root)
    report=study.parent.read(root/'report.json')
    for name,expected in report['files'].items():
        assert study.parent.digest(root/name)==expected,name
    f=pd.read_parquet(root/'features.parquet')
    records={(r.symbol,r.entry_idx):r for r in f.itertuples()}
    expected_three=[]
    def valid(r):
        return (r.revenue_technical_ok and r.revenue_count_group=='UNCHANGED_COUNT'
            and r.old_revenue_count==r.new_revenue_count and r.new_revenue_count>=3 and r.revenue_sign!=0)
    for r in f.itertuples():
        assert r.one_sign==(r.revenue_sign if valid(r) else 0)
        prev=[records.get((r.symbol,r.entry_idx-i)) for i in (2,1,0)]
        sign=0
        if all(x is not None for x in prev) and all(valid(x) for x in prev):
            if (len({x.revenue_sign for x in prev})==len({x.fiscal_anchor for x in prev})==
                len({x.new_revenue_count for x in prev})==1 and prev[0].new_id==prev[1].old_id
                and prev[1].new_id==prev[2].old_id):sign=r.revenue_sign
        expected_three.append(sign)
        assert r.three_sign==sign
    assert np.count_nonzero(expected_three)==report['frequency']['three_change_signals']
    raw=pd.read_parquet(root/'prices.parquet')
    raw['date']=pd.to_datetime(raw.date)
    by_symbol={s:g.set_index('date') for s,g in raw.groupby('symbol')}
    cal=study.parent.schedule()
    checks=0;inverse_features=[];controls=[]
    for horizon in (1,3,5):
        cases=pd.read_parquet(root/f'cases-H{horizon}.parquet')
        until={};independent=set()
        for r in f.sort_values(['entry_idx','symbol']).itertuples():
            if r.entry_idx>until.get(r.symbol,-1):
                independent.add((r.symbol,r.entry_idx));until[r.symbol]=r.entry_idx+horizon-1
        for row in cases.itertuples():
            entry=records[row.symbol,row.entry_idx]
            assert row.no_overlap==((row.symbol,row.entry_idx) in independent)
            last=row.entry_idx+horizon-1
            assert row.maturity==cal.iloc[last].closing
            expected_inverse=None
            if row.arm==study.ARMS[2]:
                for i in range(row.entry_idx+1,last+1):
                    later=records.get((row.symbol,i))
                    if (later is not None and valid(later) and later.revenue_sign==-row.sign
                        and later.fiscal_anchor==entry.fiscal_anchor and later.new_revenue_count==entry.new_revenue_count):
                        assert later.new_available<later.entry_open
                        expected_inverse=i;break
                assert (pd.isna(row.inverse_idx) and expected_inverse is None) or row.inverse_idx==expected_inverse
                if expected_inverse is not None:
                    inverse_features.append(dict(symbol=row.symbol,entry_date=row.entry_date,horizon=horizon,
                        inverse_date=cal.iloc[expected_inverse].day,status=row.status))
            if row.status=='IMMATURE':assert row.maturity>=study.parent.utc(p['price_cutoff_utc'])
            if row.status!='AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED':continue
            assert row.maturity<study.parent.utc(p['price_cutoff_utc'])
            bars=by_symbol[row.symbol].reindex(cal.day.iloc[row.entry_idx:last+1])
            assert len(bars)==horizon and bars[['open','high','low','close','volume']].notna().all().all()
            assert bars.data_source.eq('alpaca_sip').all() and bars.data_adjustment.eq('split').all()
            actual,why,offset=scalar(bars,row.sign,expected_inverse-row.entry_idx if expected_inverse is not None else None)
            assert abs(actual-row.gross_pct)<1e-9,(row.symbol,row.entry_date,horizon,actual,row.gross_pct)
            assert why==row.exit_reason and offset==row.exit_offset
            checks+=1
            if row.arm==study.ARMS[1]:
                long_result=scalar(bars,1)[0];short_result=scalar(bars,-1)[0]
                controls.append(dict(symbol=row.symbol,entry_date=row.entry_date,horizon=horizon,
                    selected_sign=row.sign,selected_return_pct=row.gross_pct,
                    always_long_same_protections_pct=long_result,always_short_same_protections_pct=short_result))
        fixed=cases[cases.arm.eq(study.ARMS[1])].set_index(['symbol','entry_idx'])
        dynamic=cases[cases.arm.eq(study.ARMS[2])].set_index(['symbol','entry_idx'])
        assert fixed.index.equals(dynamic.index) and fixed.status.equals(dynamic.status)
        if horizon==1:
            pd.testing.assert_series_equal(fixed.gross_pct,dynamic.gross_pct)
    pd.DataFrame(inverse_features).to_csv(root/'inverse-feature-coverage.csv',index=False)
    control_frame=pd.DataFrame(controls)
    control_frame.to_csv(root/'confirmed-matched-protection-controls.csv',index=False)
    result=dict(status='PASS_CONFIRMATION_CHAIN_CLOCK_STOP_PRIORITY_AND_MATCHED_ENTRIES',
        feature_rows=len(f),confirmed_signals=int(np.count_nonzero(expected_three)),
        scalar_cases_checked=checks,independent_human_review=False,
        inverse_features=inverse_features,
        matched_controls={str(h):dict(n=len(g),selected_mean_pct=float(g.selected_return_pct.mean()),
            always_long_mean_pct=float(g.always_long_same_protections_pct.mean()),
            always_short_mean_pct=float(g.always_short_same_protections_pct.mean())) for h,g in control_frame.groupby('horizon')},
        no_h10_returns=not (root/'cases-H10.parquet').exists(),
        report_sha256=study.parent.digest(root/'report.json'),auditor_sha256=study.parent.digest(Path(__file__)))
    study.parent.save(root/'final-audit.json',result)
    print(result,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    audit(parser.parse_args().output_dir)
