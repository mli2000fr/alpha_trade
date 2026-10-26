"""Bounded causal-context audit of archived SL5/SL1 portfolios, not a replay.

Six predeclared flags; choose at most one using 2020-2022 matured outcomes,
freeze it, then examine 2023/2024. No automatic exposure changes or model fit.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT=Path('artifacts/research/us_winner_anticipation_audit/20261025-v1')
INPUT=Path('artifacts/research/us_winner_monthly_selector/20261024-v1')
DOC=Path('doc/ml/winner_anticipation_protocole_20261025.md')
TEST=Path('tests/test_us_winner_anticipation_audit_20261025.py')
CASES={
    'SL5':Path('artifacts/research/us_winner_min70_4000/20261025-v1/cases/FIXED_REFERENCE_MIN70'),
    'SL1':Path('artifacts/research/us_winner_sl1_min70/20261025-v1/cases/FIXED_SL1_H20_MIN70'),
}
FLAGS=['SPY_BELOW_SMA50','SPY_VOL20_HIGH','ORACLE_BREADTH20_WEAK',
       'STOCK_RELATIVE20_NEGATIVE','STOCK_ATR20_HIGH','STRATEGY_PF20_WEAK']
TRAIN_END=pd.Timestamp('2022-12-31',tz='UTC')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,payload):Path(path).write_text(json.dumps(payload,indent=2,default=str,allow_nan=False),encoding='utf-8')


def price_features(pivots,cohort):
    """Backward-only windows; no future outcomes or selected/coverage gates."""
    close=pivots['close'];prev=close.shift(1)
    ret20=close/close.shift(20)-1
    ret1=close.pct_change(fill_method=None)
    vol=ret1.SPY.rolling(20,min_periods=20).std()
    med=vol.rolling(126,min_periods=126).median()
    spyma=close.SPY.rolling(50,min_periods=50).mean()
    tr=np.maximum.reduce([(pivots['high']-pivots['low']).to_numpy(),
        (pivots['high']-prev).abs().to_numpy(),(pivots['low']-prev).abs().to_numpy()])
    atr=pd.DataFrame(tr,index=close.index,columns=close.columns).rolling(20,min_periods=20).mean()/close
    market=pd.DataFrame(index=close.index)
    market['SPY_BELOW_SMA50']=(close.SPY<spyma).where(close.SPY.notna()&spyma.notna())
    market['SPY_VOL20_HIGH']=(vol>med).where(vol.notna()&med.notna())
    breadth={};counts={}
    for day,g in cohort.groupby('date'):
        day=pd.Timestamp(day)
        if day not in ret20.index:continue
        if len(g)!=20 or g.symbol.duplicated().any():raise ValueError('TOP20 membership changed')
        values=ret20.loc[day,g.symbol.tolist()].dropna()
        counts[day]=len(values)
        breadth[day]=float(values.gt(0).mean()) if len(values)>=16 else np.nan
    market['oracle_breadth20']=pd.Series(breadth)
    market['oracle_breadth_count']=pd.Series(counts)
    market['ORACLE_BREADTH20_WEAK']=(market.oracle_breadth20<.5).where(market.oracle_breadth20.notna())
    return market,ret20.sub(ret20.SPY,axis=0),atr


def closed_health(trades,cutoff,count=20):
    """Labels can be used as past observations ONLY after the actual exit."""
    known=trades[pd.to_datetime(trades.exit_date,utc=True).le(cutoff)].sort_values('exit_date',kind='stable').tail(count)
    if len(known)<count:return None,None
    gains=float(known.pnl.clip(lower=0).sum());losses=float(-known.pnl.clip(upper=0).sum())
    return bool(gains<losses),pd.Timestamp(known.exit_date.max())


def label_rows(trades,schedule,market,relative,atr):
    days=sorted(d for d in schedule if d<=pd.Timestamp('2024-12-31').date())
    indices={d:i for i,d in enumerate(days)};rows=[];reserved={}
    for t in trades.itertuples():
        stamp=pd.Timestamp(t.entry_date);day=stamp.tz_convert('America/New_York').date();i=indices[day]
        # Common maturity, regardless of an early losing exit. Do not keep recent
        # stop-outs while dropping recent winners still open at archive end.
        if i==0 or i+20>=len(days):
            reserved['COMMON_OPEN21_UNAVAILABLE']=reserved.get('COMMON_OPEN21_UNAVAILABLE',0)+1;continue
        prior=days[i-1];source=pd.Timestamp(prior);cutoff=pd.Timestamp(schedule[prior].close_at_utc)
        if cutoff>=stamp:raise ValueError('Context not known before entry')
        health,last=closed_health(trades,cutoff)
        if last is not None and last>cutoff:raise ValueError('Future realized PnL in health')
        record=dict(symbol=t.symbol,campaign_id=t.campaign_id,entry_at=stamp,entry_year=day.year,
            entry_month=str(pd.Timestamp(day).to_period('M')),source_date=source,known_before=cutoff,
            common_maturity_at=pd.Timestamp(schedule[days[i+20]].open_at_utc),exit_at=pd.Timestamp(t.exit_date),
            net_return_pct=float(t.return_pct*100),net_pnl_usd=float(t.pnl),entry_notional=float(t.quantity*t.entry_price),
            past_health_last_exit=last,STRATEGY_PF20_WEAK=health)
        for name in FLAGS[:3]:
            value=market.at[source,name] if source in market.index else np.nan
            record[name]=bool(value) if pd.notna(value) else None
        r=relative.at[source,t.symbol];a=atr.at[source,t.symbol]
        record['STOCK_RELATIVE20_NEGATIVE']=bool(r<0) if np.isfinite(r) else None
        record['STOCK_ATR20_HIGH']=bool(a>=.05) if np.isfinite(a) else None
        rows.append(record)
    return pd.DataFrame(rows),reserved


def aggregate(frame,flag):
    qualified=frame[frame[flag].notna()]
    groups={}
    for adverse,label in [(False,'unflagged'),(True,'flagged')]:
        g=qualified[qualified[flag].eq(adverse)]
        gains=float(g.net_pnl_usd.clip(lower=0).sum());losses=float(-g.net_pnl_usd.clip(upper=0).sum())
        groups[label]=dict(trades=len(g),entry_dates=int(g.entry_at.dt.date.nunique()),symbols=int(g.symbol.nunique()),
            mean_net_return_pct=float(g.net_return_pct.mean()) if len(g) else None,
            win_pct=float(g.net_pnl_usd.gt(0).mean()*100) if len(g) else None,
            net_closed_pnl_usd=float(g.net_pnl_usd.sum()),gross_loss_mass_usd=losses,
            gross_gain_mass_usd=gains,profit_factor=gains/losses if losses else None,
            entry_notional_sum_usd=float(g.entry_notional.sum()))
    bad,good=groups['flagged'],groups['unflagged']
    gap=bad['mean_net_return_pct']-good['mean_net_return_pct'] if bad['trades'] and good['trades'] else None
    total_loss=bad['gross_loss_mass_usd']+good['gross_loss_mass_usd']
    total_gain=bad['gross_gain_mass_usd']+good['gross_gain_mass_usd']
    return dict(flag=flag,total_trades=len(frame),qualified=len(qualified),missing=len(frame)-len(qualified),
        flagged_trade_pct=100*bad['trades']/len(qualified) if len(qualified) else None,
        delta_mean_return_pct=gap,flagged_loss_share_pct=100*bad['gross_loss_mass_usd']/total_loss if total_loss else None,
        flagged_gain_share_pct=100*bad['gross_gain_mass_usd']/total_gain if total_gain else None,**groups)


def choose_on_development(frame):
    train=frame[frame.entry_year.between(2020,2022)&frame.common_maturity_at.le(TRAIN_END)&frame.exit_at.le(TRAIN_END)]
    scores=[]
    for flag in FLAGS:
        total=aggregate(train,flag)
        annual=[aggregate(g,flag) for _,g in train.groupby('entry_year')]
        qualified=[r for r in annual if min(r['flagged']['trades'],r['unflagged']['trades'])>=15
            and min(r['flagged']['entry_dates'],r['unflagged']['entry_dates'])>=10]
        supported=(len(qualified)>=2 and min(total['flagged']['trades'],total['unflagged']['trades'])>=60
            and min(total['flagged']['entry_dates'],total['unflagged']['entry_dates'])>=20)
        score=float(np.mean([r['delta_mean_return_pct'] for r in qualified])) if qualified else None
        eligible=supported and sum(r['delta_mean_return_pct']<0 for r in qualified)>=2 and score<0
        scores.append(dict(flag=flag,eligible=bool(eligible),equal_year_gap_pct=score,
            development=total,annual=qualified))
    eligible=[r for r in scores if r['eligible']]
    best=min(eligible,key=lambda r:r['equal_year_gap_pct'])['flag'] if eligible else None
    return best,scores,len(train)


def month_bootstrap(frame,flag,draws=3000):
    f=frame[frame[flag].notna()].copy()
    if f.empty:return None
    f['bad_count']=f[flag].eq(True).astype(int);f['good_count']=f[flag].eq(False).astype(int)
    f['bad_sum']=f.net_return_pct*f.bad_count;f['good_sum']=f.net_return_pct*f.good_count
    groups=f.groupby('entry_month')[['bad_sum','bad_count','good_sum','good_count']].sum().to_numpy(float)
    if len(groups)<6:return None
    rng=np.random.default_rng(4271);samples=groups[rng.integers(0,len(groups),size=(draws,len(groups)))].sum(axis=1)
    valid=(samples[:,1]>0)&(samples[:,3]>0)
    gaps=samples[valid,0]/samples[valid,1]-samples[valid,2]/samples[valid,3]
    if not len(gaps):return None
    return dict(months=len(groups),valid_draws=len(gaps),lower95_pct=float(np.quantile(gaps,.025)),
        upper95_pct=float(np.quantile(gaps,.975)),method='ENTRY_MONTH_CLUSTER; no cross-month independence guarantee')


def prepare():
    sources={str(p):digest(p) for p in [Path(__file__),DOC,TEST,INPUT/'inputs/manifest.json',
        Path('scripts/research/us_winner_monthly_inputs_20261024.py')]}
    for folder in CASES.values():
        report=read(folder/'report.json');sources[str(folder/'report.json')]=digest(folder/'report.json')
        for name,h in report['files'].items():
            p=folder/name
            if digest(p)!=h:raise ValueError('Archived case mutated: '+str(p))
            sources[str(p)]=h
    ROOT.mkdir(parents=True,exist_ok=False)
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,flags=FLAGS,
        thresholds=dict(spy_sma=50,volatility_sessions=20,vol_median_sessions=126,oracle_breadth_min_count=16,
            oracle_breadth_threshold=.5,relative_return_sessions=20,stock_atr_sessions=20,stock_atr_threshold=.05,
            realized_health_closed_trades=20,realized_health_profit_factor=1),
        development='SL5 entries2020-2022 with commonopen21 AND actual exit known by2022-12-31',
        selection='At most ONE flag, lowest equal-year bad-minus-good mean net unit return on development; '
            '>=60 trades and20entrydates each state; >=15trades/10dates each state in at least2years; bad delta in>=2years',
        evaluation='All6descriptive; selected flag frozen for2023/2024 SL5 and SL1 sensitivity; no retuning',
        gates='2023 and2024 selected flag gap negative, >=20trades/10dates per state peryear, '
            'month-cluster bootstrap upper95<0 each year; SL1 sensitivity both years also negative',
        temporal='Latest complete prior official session close only; health actual exits<=that close; '
            'current TOP20 breadth uses ALL20 ranks, not future selected coverage; missing remains unknown',
        outcome='Actual accepted-entry net trade return, commonopen21 matured; not counterfactual portfolio or saved PnL',
        anticipation='Pre-entry context associations, not a proven forecast of a later market turning point',
        no_SQL=True,no_network=True,no_new_backtest=True,no_training=True,no_orders=True,no_production_changes=True,
        limitations=['Years and indicators already examined; no untouched holdout.',
            'Revised histories, survivor universe, OOF/ranking and future coverage bias inherited.',
            'Accepted trades conditioned on native B4/admission; unit returns not exposure-matched causal effects.',
            'SL1 same market dates, not independent confirmation; repeated/overlapping positions.',
            'Macro vintage unqualified: no VIX, rates or consensus invented as historically available.',
            'Native B4 already reduces risk; no additional protection promoted by this audit.'])
    save(ROOT/'protocol.json',protocol)
    return protocol


def main():
    protocol=prepare()
    from scripts.research import us_winner_monthly_inputs_20261024 as inputs
    tape=inputs.Tape(INPUT)
    # Use the official calendar, not weekday counting or gaps in a single symbol.
    schedule={s.session_date:s for s in inputs.grid.calendar().sessions(
        tape.pivots['close'].index.min().date(),inputs.END) if s.is_open}
    dates=pd.to_datetime(sorted(schedule))
    pivots={k:v.reindex(dates) for k,v in tape.pivots.items()}
    market,relative,atr=price_features(pivots,tape.cohort)
    market.to_parquet(ROOT/'market-features.parquet')
    all_rows={};reservations={}
    for label,folder in CASES.items():
        trades=pd.read_parquet(folder/'trades.parquet').sort_values('entry_date',kind='stable')
        frame,reserved=label_rows(trades,schedule,market,relative,atr)
        all_rows[label]=frame;reservations[label]=reserved
    selected,development,count=choose_on_development(all_rows['SL5'])
    # Seal selection before touching validation aggregates.
    save(ROOT/'frozen-development-choice.json',dict(selected_flag=selected,training_trades=count,
        development=development,no_validation_consumed=True))
    rows=[];primary=[]
    for label,frame in all_rows.items():
        for year,g in frame.groupby('entry_year'):
            if year not in [2020,2021,2022,2023,2024]:continue
            for flag in FLAGS:
                item=dict(run=label,entry_year=int(year),**aggregate(g,flag))
                item['bootstrap']=month_bootstrap(g,flag) if flag==selected and year in [2023,2024] else None
                rows.append(item)
                if flag==selected and year in [2023,2024]:primary.append(item)
        frame.to_parquet(ROOT/(label.lower()+'-entry-contexts.parquet'),index=False)
    def qualified(r):
        return (min(r['flagged']['trades'],r['unflagged']['trades'])>=20
            and min(r['flagged']['entry_dates'],r['unflagged']['entry_dates'])>=10)
    native=[r for r in primary if r['run']=='SL5'];sensitivity=[r for r in primary if r['run']=='SL1']
    passed=(selected is not None and len(native)==2 and all(qualified(r) and r['delta_mean_return_pct']<0
        and r['bootstrap'] is not None and r['bootstrap']['upper95_pct']<0 for r in native)
        and len(sensitivity)==2 and all(qualified(r) and r['delta_mean_return_pct']<0 for r in sensitivity))
    verdict='DESCRIPTIVE_CANDIDATE_ONLY_REQUIRES_SEPARATE_REPLAY' if passed else 'NO_ROBUST_EARLY_WARNING_VALIDATED'
    for name,h in protocol['sources'].items():
        if digest(name)!=h:raise ValueError('Sealed audit source changed: '+name)
    report=dict(status='COMPLETED_READ_ONLY_AUDIT',selected_flag=selected,verdict=verdict,
        primary=primary,all_flags=rows,reservations=reservations,development=development,
        production_unchanged=True,counterfactual_portfolio_performance_not_computed=True,
        limitations=protocol['limitations'],sources=protocol['sources'])
    save(ROOT/'report.json',report)
    print(json.dumps(dict(selected_flag=selected,verdict=verdict,primary=primary),indent=2,default=str))


if __name__=='__main__':main()
