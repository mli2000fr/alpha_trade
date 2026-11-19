"""Secondary fixed cross of activation/recovery families, no performance fit.

Declared after inspecting the initial timing audit: all years already explored.
No current economic replay is changed. This does not create an independent test.
"""
from pathlib import Path
import json
import pandas as pd

from scripts.research.us_b_protection_timing_20261118 import SOURCE,OBSERVER,observable,future_targets
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_b_protection_timing/20261118-v2-cross')


def states(frame,on_rule,off_rule):
    active=False;start=None;down=up=0.;bad=good=0;rows=[]
    for offset,(day,row) in enumerate(frame.iterrows()):
        transition='';sigma=row.prior_sigma60
        qualified_sigma=pd.notna(sigma) and sigma>1e-6 and pd.notna(row.return1)
        z=float(row.return1/sigma) if qualified_sigma else None
        if not active:
            bad=bad+1 if pd.notna(row.dd20) and row.dd20<=-.08 and row.return5<0 else 0
            down=max(0.,down-z-.25) if z is not None else 0.
            hit=bad>=2 if on_rule=='DD20' else down>=4.
            if hit:active=True;start=offset;transition='ON';down=up=0.;bad=good=0
        else:
            good=good+1 if pd.notna(row.ema10) and row.return5>0 and row.shadow_equity>row.ema10 else 0
            up=max(0.,up+z-.25) if z is not None else 0.
            recovered=good>=2 if off_rule=='EMA10' else up>=3. and row.return5>0
            if offset-start>=3 and recovered:active=False;transition='OFF';down=up=0.;bad=good=0
        rows.append(dict(date=day,active=active,transition=transition,negative_score=down,positive_score=up,
            bad_count=bad,good_count=good))
    return pd.DataFrame(rows).set_index('date')


def main():
    if (ROOT/'protocol.json').exists():raise ValueError('Use a fresh audit folder')
    ROOT.mkdir(parents=True,exist_ok=True)
    atomic_json(ROOT/'protocol.json',dict(source_sha256={str(p):digest(p) for p in [Path(__file__),SOURCE,OBSERVER]},
        declared_after='Initial timing audit v1 inspected, including2024/25; secondary exploratory analysis, no new holdout',
        on_rules=['DD20<=-8% and return5<0 for2closes','Negative standardizedCUSUM>=4, allowance .25sigma/day'],
        off_rules=['return5>0 and shadowNAV>EMA10 for2closes','Positive standardizedCUSUM>=3 and return5>0'],
        sigma='Prior60 close returns, excludes current return',minimum_ON_sessions=3,reset='Both accumulators and runs at every transition',
        giant_2024_optimization=False,threshold_search=False,performance_replay=False,production_changes=False))
    equity=pd.read_csv(SOURCE,index_col=0,parse_dates=True).equity
    equity=pd.concat([pd.Series([4000.],index=pd.to_datetime(['2020-12-31'])),equity])
    features=observable(equity);targets=future_targets(equity);metrics=[];events=[]
    for on in ['DD20','CUSUM']:
        for off in ['EMA10','CUSUM']:
            key=on+'_'+off;s=states(features,on,off)
            for cut in ['2022-12-30','2024-11-29','2025-05-30']:
                pd.testing.assert_frame_equal(s.loc[:cut],states(features.loc[:cut],on,off))
            s.to_parquet(ROOT/(key+'-states.parquet'))
            d=s.join(targets).loc['2021-01-01':'2026-09-30']
            for label,first,last in [('2021-2023','2021-01-01','2023-12-31'),('2024','2024-01-01','2024-12-31'),('2025-2026','2025-01-01','2026-09-30')]:
                g=d.loc[first:last];known=g[g.mature10];risk=known.risk10.eq(True);good=known.recovery10.eq(True)
                activated=known[known.transition.eq('ON')];deactivated=known[known.transition.eq('OFF')]
                metrics.append(dict(rule=key,period=label,protected_pct=100*g.active.mean(),on=int(g.transition.eq('ON').sum()),
                    off=int(g.transition.eq('OFF').sum()),risky_window_protected_pct=100*known.loc[risk,'active'].mean(),
                    rebound_window_blocked_pct=100*known.loc[good,'active'].mean(),
                    mature_ON=len(activated),ON_followed_drop_pct=100*activated.risk10.eq(True).mean() if len(activated) else None,
                    mature_OFF=len(deactivated),OFF_followed_recovery_pct=100*deactivated.recovery10.eq(True).mean() if len(deactivated) else None))
            for day,row in d[d.transition.ne('')].iterrows():
                events.append(dict(rule=key,date=str(day.date()),transition=row.transition,
                    future_min10=row.forward_min10,future_return10=row.forward_return10,mature10=bool(row.mature10)))
    pd.DataFrame(metrics).to_csv(ROOT/'timing-metrics.csv',index=False);pd.DataFrame(events).to_csv(ROOT/'timing-events.csv',index=False)
    atomic_json(ROOT/'status.json',dict(status='COMPLETED_SECONDARY_EXPLORATORY_TIMING_AUDIT',prefix_checks=12,
        new_holdout=False,new_performance_claim=False,production_changes=False))
    print(pd.DataFrame(metrics).to_string(index=False))


if __name__=='__main__':main()
