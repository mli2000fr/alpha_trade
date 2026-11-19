"""Bounded timing audit: new causal rules, no implied portfolio performance.

Two fixed alternatives to the delayed mature-winrate observer. Outcome windows
only evaluate alerts; they never enter state construction. No source replay edits.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_b_protection_timing/20261118-v1')
SOURCE=Path('artifacts/research/us_q051_b_early_sl/20261116-v1/cases/SL10/result/equity-daily.csv')
OBSERVER=Path('artifacts/research/us_q051_internal_liquidation/20261118-v1/inputs/SL10_SHADOW-states.parquet')


def observable(equity):
    a=pd.DataFrame({'shadow_equity':equity})
    a['return1']=equity.pct_change(fill_method=None)
    a['return5']=equity/equity.shift(5)-1
    a['ema10']=equity.ewm(span=10,adjust=False,min_periods=10).mean()
    a['dd20']=equity/equity.rolling(20,min_periods=20).max()-1
    a['prior_sigma60']=a.return1.rolling(60,min_periods=60).std().shift(1)
    return a


def states(frame,mode):
    if mode not in ('DD20_EMA10','CUSUM'):raise ValueError('Unknown timing rule')
    active=False;on_at=None;down=up=0.;bad=good=0;rows=[]
    for offset,(day,row) in enumerate(frame.iterrows()):
        transition='';qualified=False
        if mode=='DD20_EMA10':
            qualified=pd.notna(row.dd20) and pd.notna(row.return5) and pd.notna(row.ema10)
            if not active:
                bad=bad+1 if qualified and row.dd20<=-.08 and row.return5<0 else 0
                if bad>=2:active=True;transition='ON';on_at=offset;good=bad=0
            else:
                good=good+1 if qualified and row.return5>0 and row.shadow_equity>row.ema10 else 0
                if offset-on_at>=3 and good>=2:active=False;transition='OFF';good=bad=0
        else:
            qualified=pd.notna(row.prior_sigma60) and row.prior_sigma60>1e-6 and pd.notna(row.return1)
            if qualified:
                z=float(row.return1/row.prior_sigma60)
                if not active:
                    down=max(0.,down-z-.25)
                    if down>=4.:active=True;transition='ON';on_at=offset;up=down=0.
                else:
                    up=max(0.,up+z-.25)
                    if offset-on_at>=3 and up>=3. and row.return5>0:
                        active=False;transition='OFF';up=down=0.
            else:down=up=0.
        rows.append(dict(date=day,active=active,transition=transition,qualified=qualified,
            down_score=down,up_score=up,bad_count=bad,good_count=good))
    return pd.DataFrame(rows).set_index('date')


def future_targets(equity):
    out=pd.DataFrame(index=equity.index)
    future=pd.concat([equity.shift(-k)/equity-1 for k in range(1,11)],axis=1)
    known=future.notna().all(axis=1)
    out['mature10']=known;out['forward_min10']=future.min(axis=1).where(known)
    out['forward_return10']=(equity.shift(-10)/equity-1).where(known)
    out['risk10']=out.forward_min10.lt(-.05).where(known)
    out['recovery10']=(out.forward_return10.gt(0)&out.forward_min10.gt(-.05)).where(known)
    return out


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    if (ROOT/'protocol.json').exists():raise ValueError('Audit already sealed, use a fresh directory')
    atomic_json(ROOT/'protocol.json',dict(source_sha256={str(p):digest(p) for p in [SOURCE,OBSERVER,Path(__file__)]},
        study='Timing only, no portfolio replay or performance claim',
        DD20_EMA10='ON shadowDD20<=-8% and return5<0,2closes; OFF return5>0 and NAV>EMA10,2closes,minimum3protected sessions',
        CUSUM='Prior60sigma normalization; loss accumulator max(0,score-z-.25)>=4; recovery score max(0,score+z-.25)>=3 and return5>0; min3sessions; reset at transitions',
        evaluation='Next10shadow closes drawdown below-5% vs current close; recovery positive10return without below-5%. Diagnostic only, no opening fills/fees replayed.',
        year_blocks=['2021-2023','2024','2025-2026'],threshold_tuning=False,
        separate_future_labels=True,independent_holdout=False,SQL_reads=0,SQL_writes=0,provider_calls=0,broker_orders=0,production_changes=False))
    equity=pd.read_csv(SOURCE,index_col=0,parse_dates=True).equity
    seed=pd.Series([4000.],index=pd.to_datetime(['2020-12-31']))
    equity=pd.concat([seed,equity]);features=observable(equity)
    targets=future_targets(equity);features.to_parquet(ROOT/'observables.parquet');targets.to_parquet(ROOT/'future-targets.parquet')
    old=pd.read_parquet(OBSERVER).reindex(equity.index)
    policies={'OLD_SHADOW':old[['active','transition','qualified']].copy()}
    for mode in ['DD20_EMA10','CUSUM']:
        s=states(features,mode)
        for cut in ['2022-12-30','2024-11-29','2025-05-30']:
            pd.testing.assert_frame_equal(s.loc[:cut],states(features.loc[:cut],mode))
        policies[mode]=s
    metrics=[];events=[]
    for name,s in policies.items():
        s=s.loc['2021-01-01':'2026-09-30'];s.to_parquet(ROOT/(name+'-states.parquet'))
        data=s.join(targets)
        for label,start,end in [('2021-2023','2021-01-01','2023-12-31'),('2024','2024-01-01','2024-12-31'),('2025-2026','2025-01-01','2026-09-30')]:
            g=data.loc[start:end];known=g[g.mature10];risk=known.risk10.eq(True);good=known.recovery10.eq(True)
            on=known[known.transition.eq('ON')];off=known[known.transition.eq('OFF')]
            metrics.append(dict(rule=name,period=label,sessions=len(g),protected_pct=100*g.active.mean(),
                on=int(g.transition.eq('ON').sum()),off=int(g.transition.eq('OFF').sum()),
                risky_windows=int(risk.sum()),risky_window_protected_pct=float(100*known.loc[risk,'active'].mean()),
                rebound_windows=int(good.sum()),rebound_window_blocked_pct=float(100*known.loc[good,'active'].mean()),
                mature_on=len(on),on_followed_drop_pct=float(100*on.risk10.eq(True).mean()) if len(on) else None,
                mature_off=len(off),off_followed_recovery_pct=float(100*off.recovery10.eq(True).mean()) if len(off) else None))
        for day,row in data[data.transition.fillna('').ne('')].iterrows():
            events.append(dict(rule=name,date=str(day.date()),transition=row.transition,forward_min10=row.forward_min10,
                forward_return10=row.forward_return10,mature10=bool(row.mature10),shadow_equity=float(equity.loc[day]),
                observed_return5=features.loc[day,'return5'],observed_dd20=features.loc[day,'dd20']))
    pd.DataFrame(metrics).to_csv(ROOT/'timing-metrics.csv',index=False);pd.DataFrame(events).to_csv(ROOT/'timing-events.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(12,8),sharex=True,gridspec_kw={'height_ratios':[2,1,1,1]},facecolor='#f7f9fc')
    w=equity.loc['2024-11-01':'2025-12-31'];axes[0].plot(w.index,w,color='#1d4ed8');axes[0].set_ylabel('Témoin virtuel ($)')
    for ax,(name,s) in zip(axes[1:],policies.items()):
        g=s.reindex(w.index);ax.fill_between(g.index,0,g.active.astype(float),step='post',color='#d97706',alpha=.5)
        ax.set_ylabel(name,fontsize=9);ax.set_yticks([0,1],['OFF','ON'])
    for ax in axes:ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Diagnostic des conditions ON/OFF — pas un backtest de performance',fontweight='bold')
    fig.text(.09,.02,'États calculés à la clôture, application possible seulement à l’ouverture suivante.\n'
        'Deux règles fixes exploratoires ; aucun seuil choisi après résultat ; historique déjà exploré.',fontsize=9)
    fig.subplots_adjust(left=.13,right=.97,top=.93,bottom=.12,hspace=.12);fig.savefig(ROOT/'timing-comparison.png',dpi=150);plt.close(fig)
    atomic_json(ROOT/'status.json',dict(status='COMPLETED_EXPLORATORY_TIMING_AUDIT',prefix_checks=6,
        rules=3,performance_replayed=False,thresholds_optimized=False,independent_holdout=False,production_changes=False))
    print(pd.DataFrame(metrics).to_string(index=False))


if __name__=='__main__':main()
