"""Independent correct clock bounds for all closed native Winner trades."""
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scripts.research.us_winner_bottom_rank_filter_20261022 import read,digest,verify,save_new


def near(a,b):
    if not math.isclose(float(a),float(b),abs_tol=1e-8,rel_tol=1e-10):raise AssertionError(f'{a} != {b}')


def audit(root):
    root=Path(root);p=read(root/'protocol.json');verify(p['sources'])
    report=read(root/'report.json');verify({str(root/k):v for k,v in report['files'].items()})
    parent=Path(p['parent']);snap=read(parent/'snapshot.json')
    d=pd.read_parquet(root/'trade-diagnostics.parquet');raw={}
    wanted=set(d.symbol)
    for item in snap['receipts']:
        if item['symbol'] in wanted:raw[item['symbol']]=pd.read_parquet(parent/item['file'])
    bounds=[]
    for r in d.itertuples():
        f=raw[r.symbol];entry=float(r.entry_price);exit_time=r.exit_date
        mask=f.bar_timestamp.ge(r.entry_date)
        before=f[mask&(f.bar_end_timestamp.lt(exit_time) if r.exit_reason=='STOP' else f.bar_end_timestamp.le(exit_time))]
        exitbar=f[f.bar_end_timestamp.eq(exit_time)] if r.exit_reason=='STOP' else f.iloc[:0]
        hi=max([entry,r.exit_price,*before.high]);lo=min([entry,r.exit_price,*before.low])
        upper_hi=max([hi,*exitbar.high]);upper_lo=min([lo,*exitbar.low])
        for a,b in zip([100*(hi/entry-1),100*(upper_hi/entry-1),100*(1-lo/entry),100*(1-upper_lo/entry)],
                [r.mfe_lower_pct,r.mfe_upper_pct,r.mae_lower_pct,r.mae_upper_pct]):near(a,b)
        first=f[mask].head(2)
        observed=len(first)==2 and bool((first.bar_end_timestamp.lt(exit_time) if r.exit_reason=='STOP' else first.bar_end_timestamp.le(exit_time)).all())
        if observed!=r.immediate_observed:raise AssertionError('Immediate availability')
        rebound=False
        if r.future_complete and 'STOP' in r.exit_reason:
            start=exit_time if r.exit_reason=='STOP' else exit_time+pd.Timedelta(minutes=5)
            after=f[f.bar_timestamp.ge(start)&f.bar_timestamp.lt(r.theoretical_due_open)]
            hit=after[after.close.ge(entry*1.07-1e-10)]
            rebound=not hit.empty
            if rebound!=r.post_stop_close_1R:raise AssertionError('Poststop close')
            if rebound:
                stamp=hit.bar_end_timestamp.iloc[0]
                if stamp!=r.post_stop_1R_time:raise AssertionError('Poststop timestamp')
                near((stamp-exit_time).total_seconds()/86400,r.post_stop_1R_calendar_days)
                low=min(r.exit_price,float(after.loc[after.bar_end_timestamp.le(stamp),'low'].min()))
                near(100*max(0,1-low/entry),r.post_stop_mae_until_1R_pct)
                bound_low=min([low,*exitbar.low])
                bounds.append(dict(year=r.year,campaign_id=r.campaign_id,symbol=r.symbol,pnl=r.pnl,
                    mae_after_stop_until_rebound_lower_pct=100*max(0,1-low/entry),
                    mae_after_stop_until_rebound_upper_pct=100*max(0,1-bound_low/entry),
                    rebound_calendar_days=r.post_stop_1R_calendar_days))
        certain=100*(hi/entry-1)>=7-1e-10;ambiguous=100*(hi/entry-1)<7-1e-10<=100*(upper_hi/entry-1)
        if certain!=r.gain_1R_certain or ambiguous!=r.exit_bar_1R_ambiguous:raise AssertionError('R bound')
        if r.pnl>=0:cat='WIN_OR_FLAT'
        elif certain:cat='GAIN_RESTITUTED_1R'
        elif r.immediate_failed_breakout is True or r.immediate_failed_breakout==True:cat='IMMEDIATE_FAILED_BREAKOUT'
        elif rebound:cat='POST_STOP_REBOUND_1R'
        elif ambiguous:cat='AMBIGUOUS_EXIT_BAR_1R'
        elif r.future_complete:cat='RESIDUAL_COMPLETE_WINDOW'
        else:cat='UNKNOWN_CENSORED_WINDOW'
        if cat!=r.diagnostic:raise AssertionError('Category')
    pd.DataFrame(bounds).to_csv(root/'poststop-adverse-bounds.csv',index=False)
    save_new(root/'final-audit.json',dict(status='PASS_CORRECT_NATIVE_BAR_END_EXCURSIONS_AND_POSTSTOP_CLOCK',
        trades=len(d),prefix_checks=read(root/'prefix-checks.json')['count'],
        report_sha256=digest(root/'report.json'),auditor_sha256=digest(__file__),
        bounds_sha256=digest(root/'poststop-adverse-bounds.csv'),independent_human_review=False))


if __name__=='__main__':
    audit('artifacts/research/us_winner_loss_diagnostics/20261023-v2')
