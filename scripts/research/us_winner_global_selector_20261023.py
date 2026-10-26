"""Global TOP100 profile selector: causal archives, purged labels, local CPU fit.

Unit counterfactuals are not a portfolio backtest. No broker/provider/SQL writes.
"""
from __future__ import annotations
import argparse
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import json
import logging
import time

import numpy as np
import pandas as pd
from sqlalchemy import text,bindparam

from scripts.research import us_winner_grid_scores_2017_2026_20261023 as scores_source
from scripts.research import us_winner_bottom_rank_filter_20261022 as common
from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import scalar_exit
from backtesting.winner_campaign_replay import atomic_json
from service.market.intraday_backfill import run_lock

ROOT=Path('artifacts/research/us_winner_global_selector/20261023-v1')
DOC=Path('doc/ml/winner_selecteur_global_top100_protocole_20261023.md')
BACKFILL=Path('artifacts/intraday_backfill/intraday-5dfcdc71cfaf4819ed1b/progress.json')
PROFILES=[
    dict(name='REFERENCE',sl=.07,tr=.15,tp=None,h=20),
    dict(name='COURT',sl=.03,tr=.03,tp=.07,h=10),
    dict(name='COURT_TP15',sl=.03,tr=.03,tp=.15,h=10),
    dict(name='EQUILIBRE',sl=.05,tr=.10,tp=.10,h=10),
    dict(name='PATIENT',sl=.07,tr=.20,tp=None,h=20),
    dict(name='H15',sl=.05,tr=.15,tp=.15,h=15)]
FEATURES=['oracle_rank_pct','ret5','ret10','ret20','ret60','ret120','vol5','vol20','vol60',
          'vol_ratio','atr20_pct','range5_pct','gap5_std','volume5_20','volume_J_20','log_adv20',
          'distance_sma20','drawdown20','spy_ret5','spy_ret20','spy_ret60','spy_vol20',
          'spy_sma50_distance','spy_sma200_distance','relative_ret20','relative_ret60']
PARAMS=['profile_sl','profile_tr','profile_tp','profile_h']+['profile_'+p['name'] for p in PROFILES]
LOG=logging.getLogger(__name__)


def cal_sessions():
    return [s for s in common.get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(
        date(2015,1,1),date(2027,1,31)) if s.is_open]


def split_name(day):
    y=pd.Timestamp(day).year
    return 'train' if y<=2024 else 'validation' if y==2025 else 'test'


def maturity_ok(day,maturity):
    cutoff={'train':'2024-12-31','validation':'2025-12-31','test':'2026-09-30'}[split_name(day)]
    return pd.Timestamp(maturity)<=pd.Timestamp(cutoff)


def sample_plan(top,sessions):
    days=[pd.Timestamp(s.session_date) for s in sessions];idx={d:i for i,d in enumerate(days)}
    rows=[]
    for symbol,g in top.sort_values(['symbol','date']).groupby('symbol',sort=True):
        blocked_until=-1
        for r in g.itertuples():
            d=pd.Timestamp(r.date);i=idx[d];m=days[i+41]
            split=split_name(d);reason=''
            if split!='train' and r.rank>10:
                reason='EVALUATION_PRIMARY_TOP10_ONLY'
            elif not maturity_ok(d,m):reason='LABEL_NOT_MATURE_AT_SPLIT_CUTOFF'
            elif i<=blocked_until:reason='OVERLAPPING_SYMBOL_COMMON_WINDOW'
            else:blocked_until=i+41
            rows.append(dict(date=d,symbol=symbol,rank=r.rank,split=split,maturity_date=m,
                             anchor=not reason,plan_reason=reason))
    return pd.DataFrame(rows)


def top100(root):
    file=root/'top100.parquet'
    if (root/'scores.json').exists():
        m=common.read(root/'scores.json');common.verify(m['inputs']);common.verify({str(file):m['sha256']});return pd.read_parquet(file)
    expected=[s.session_date for s in cal_sessions() if scores_source.START<=s.session_date<=scores_source.END]
    universe=set(scores_source.load_universe_file_symbols('universe-file:'+scores_source.UNIVERSE.as_posix()))
    parts=[];models={};inputs={str(scores_source.UNIVERSE):common.digest(scores_source.UNIVERSE)}
    for batch in sorted(set(scores_source.BATCHES.values())):
        folder,_,_,folds=scores_source.load_contract('artifacts/models',batch)
        path=folder/'oof_predictions.parquet'
        names=[path,folder/'protocol.json',folder/'feature_profile.json',folder/'report.json']
        for fold in folds.values():names.extend([Path(fold['model_file']),Path(fold['model_file']).with_name('done.json')])
        inputs.update({str(n):common.digest(n) for n in names})
        f=pd.read_parquet(path,columns=['date','symbol','proba_path_extreme','fold_start']).rename(columns={'proba_path_extreme':'score'})
        f['date']=pd.to_datetime(f.date)
        years=[y for y,b in scores_source.BATCHES.items() if b==batch]
        f=f[f.date.dt.year.isin(years)&f.date.between(pd.Timestamp(scores_source.START),pd.Timestamp(scores_source.END))&f.symbol.isin(universe)]
        ph=common.digest(folder/'feature_profile.json')
        q=scores_source.qualify(f,folds,source='OOF',profile_hash=ph);q['batch_id']=batch;parts.append(q);models[batch]=(folds,ph)
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as c,c.begin():
            c.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if c.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US only')
            for year in range(2017,2027):
                batch=scores_source.BATCHES[year]
                present={pd.Timestamp(d).date() for f in parts for d in f.loc[f.date.dt.year.eq(year),'date'].unique()}
                missing=[d for d in expected if d.year==year and d not in present]
                if not missing:continue
                query=text('SELECT p.prediction_date AS date,p.symbol,p.proba_extreme AS score,p.fold_start,'
                    'l.fold_start AS lineage_fold_start,l.model_available_date,l.model_sha256,l.feature_profile_sha256,'
                    'l.target_name,l.target_horizon FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l '
                    'ON p.prediction_date=l.prediction_date AND p.symbol=l.symbol AND p.batch_id=l.batch_id '
                    'WHERE p.batch_id=:batch AND p.prediction_date IN :days').bindparams(bindparam('days',expanding=True))
                f=pd.read_sql(query,c,params=dict(batch=batch,days=missing));f=f[f.symbol.isin(universe)]
                if not f.empty:
                    folds,ph=models[batch];q=scores_source.qualify(f,folds,source='SQL',profile_hash=ph);q['batch_id']=batch;parts.append(q)
    finally:engine.dispose()
    f=pd.concat(parts,ignore_index=True)
    if f.duplicated(['date','symbol']).any():raise ValueError('Duplicate scores')
    counts=f.groupby('date').size()
    if any(counts.get(pd.Timestamp(d),0)<100 for d in expected):raise ValueError('Incomplete TOP100 score dates')
    f=f.sort_values(['date','score','symbol'],ascending=[True,False,True]);f['rank']=f.groupby('date').cumcount()+1
    f=f[f['rank'].le(100)].copy();f.to_parquet(file,index=False)
    common.save_new(root/'scores.json',dict(rows=len(f),dates=f.date.nunique(),symbols=f.symbol.nunique(),
        sha256=common.digest(file),inputs=inputs,labels_read=False,SQL_writes=False,provider_calls=0))
    return f


def price_features(frame,days):
    g=frame.copy();g['date']=pd.to_datetime(g.date);g=g.set_index('date').reindex(days)
    if g.index.duplicated().any():raise ValueError('Duplicate daily')
    fields=['open','high','low','close','volume'];n=g[fields].astype(float)
    ok=(np.isfinite(n).all(axis=1)&n.gt(0).all(axis=1)&g.is_filled.eq(0)&g.data_adjustment.eq('split')
        &~g.data_source.str.contains('iex',case=False,na=True)&n.high.ge(n[['open','close']].max(axis=1))
        &n.low.le(n[['open','close']].min(axis=1)))
    n=n.where(ok);p=n.close;r=p.pct_change(fill_method=None)
    tr=pd.concat([n.high-n.low,(n.high-p.shift()).abs(),(n.low-p.shift()).abs()],axis=1).max(axis=1).where(p.shift().notna())
    f=pd.DataFrame(index=days)
    for h in [5,10,20,60,120]:f['ret'+str(h)]=p/p.shift(h)-1
    for h in [5,20,60]:f['vol'+str(h)]=r.rolling(h).std()
    f['vol_ratio']=f.vol20/f.vol60;f['atr20_pct']=tr.rolling(20).mean()/p
    f['range5_pct']=((n.high-n.low)/p).rolling(5).mean();f['gap5_std']=(n.open/p.shift()-1).rolling(5).std()
    f['volume5_20']=n.volume.rolling(5).mean()/n.volume.rolling(20).mean();f['volume_J_20']=n.volume/n.volume.rolling(20).mean()
    f['log_adv20']=np.log1p((n.volume*p).rolling(20).mean());f['distance_sma20']=p/p.rolling(20).mean()-1
    f['drawdown20']=p/p.rolling(20).max()-1
    f['sma50_distance']=p/p.rolling(50).mean()-1;f['sma200_distance']=p/p.rolling(200).mean()-1
    return f


def features_at(stock,spy,day,rank):
    a,b=stock.loc[day],spy.loc[day]
    row={k:float(a[k]) for k in FEATURES if k in stock and not k.startswith('spy_')}
    for k in ['ret5','ret20','ret60','vol20','sma50_distance','sma200_distance']:row['spy_'+k]=float(b[k])
    row.update(oracle_rank_pct=rank/100,relative_ret20=float(a.ret20-b.ret20),relative_ret60=float(a.ret60-b.ret60))
    if not all(k in row and np.isfinite(row[k]) for k in FEATURES):return None
    return row


def first_entry(groups,days,i):
    for j in range(i+1,i+21):
        prior=groups[days[j-1]];g=groups[days[j]]
        c=g.close.to_numpy(float);level=float(prior.high.max())
        hits=np.flatnonzero((c[:-3]<=level)&(c[1:-2]>level)&(c[2:-1]>level))
        if len(hits):return j,int(hits[0])+3
    return None


def rounded_levels(values):
    unique,inv=np.unique(values,return_inverse=True)
    # Python's round, exactly as the scalar/native cent contract, not np.round.
    return np.asarray([round(float(x),2) for x in unique])[inv]


def vector_exit(path,entry,due,profile):
    o,h,l,c=(path[k].to_numpy(float) for k in ['open','high','low','close'])
    initial=round(entry*(1-profile['sl']),2);target=round(entry*(1+profile['tp']),2) if profile['tp'] else np.inf
    peak=np.maximum.accumulate(np.r_[entry,h[:-1]])
    stop=np.maximum(initial,rounded_levels(peak*(1-profile['tr'])));stop[0]=initial;stop=np.maximum.accumulate(stop)
    eod=(path.bar_end_timestamp==path.session_close).to_numpy()
    old=np.r_[initial,stop[:-1]];old[1:]=np.where(eod[:-1],stop[1:],old[1:])
    due_hit=path.bar_timestamp.eq(due).to_numpy()
    gap=o<=old;tp_gap=o>=target;tight=(stop>old)&(o<=stop);touch=l<=stop;tp=h>=target
    post=np.maximum(stop,rounded_levels(np.maximum.accumulate(np.r_[entry,h])[1:]*(1-profile['tr'])))
    eod_tight=eod&(post>stop)&(c<=post)
    hit=due_hit|gap|tp_gap|tight|touch|tp|eod_tight
    where=np.flatnonzero(hit)
    if not len(where):raise ValueError('No exit before common maturity')
    j=int(where[0]);stamp=path.bar_timestamp.iloc[j]
    if due_hit[j]:return stamp,float(o[j]),'HORIZON_OPEN'
    if gap[j]:return stamp,float(o[j]),'STOP_GAP'
    if tp_gap[j]:return stamp,float(target),'TP_GAP_CAPPED'
    if tight[j]:return stamp,float(o[j]),'TIGHTENED_STOP_GAP'
    stamp=path.bar_end_timestamp.iloc[j]
    if touch[j]:return stamp,float(stop[j]),'STOP'
    if tp[j]:return stamp,float(target),'TP'
    return stamp,float(c[j]),'TIGHTENED_STOP_GAP'


def campaign_labels(groups,days,sessions,anchor,audit=False):
    i=days.index(pd.Timestamp(anchor.date));entry=first_entry(groups,days,i)
    if entry is None:return [dict(profile=p['name'],entered=False,net_return=0.,exit_reason='NO_ENTRY') for p in PROFILES],0
    j,k=entry;frames=[groups[d] for d in days[j:j+21]];path=pd.concat(frames,ignore_index=True).iloc[k:].reset_index(drop=True)
    price=float(path.open.iloc[0]);stamp=path.bar_timestamp.iloc[0];rows=[];checks=0
    for p in PROFILES:
        due=pd.Timestamp(sessions[days[j+p['h']]].open_at_utc)
        got=vector_exit(path,price,due,p)
        if audit:
            scalar=scalar_exit(path,stamp,price,due,sl=p['sl'],tp=p['tp'],trail=p['tr'])
            if scalar is None or got[0]!=scalar[0] or got[2]!=scalar[2] or abs(got[1]-scalar[1])>1e-8:
                raise AssertionError(f'Vector/scalar mismatch: {p["name"]} {got} vs {scalar}')
            checks+=1
        net=(got[1]-price)/price-.0008*(1+got[1]/price)
        rows.append(dict(profile=p['name'],entered=True,entry_time=stamp,entry_price=price,
            exit_time=got[0],exit_price=got[1],exit_reason=got[2],net_return=net))
    return rows,checks


def prepare(root):
    root.mkdir(parents=True,exist_ok=True)
    if (root/'protocol.json').exists():
        p=common.read(root/'protocol.json');common.verify(p['sources']);return p
    paths=[Path(__file__),Path(scores_source.__file__),Path(common.__file__),DOC,
        Path('tests/test_us_winner_global_selector_20261023.py'),
        Path('scripts/research/us_winner_sl3_tp7_tr3_open11_audit_20261023.py'),Path('common/market_calendar.py')]
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),profiles=PROFILES,features=FEATURES,
        sources={str(x):common.digest(x) for x in paths},train='2017-06-02 through 2024-12-31',
        validation='2025; primary TOP10',test='2026 through 2026-09-30; primary TOP10',training_population='TOP100',
        label_maturity='J+41 official sessions for ALL profiles, regardless of early exits/no entry',
        anchor_rule='Earliest per-symbol, block through J+41 across calendar years, before coverage/outcomes',
        selection='One GLOBAL LightGBM regressor conditioned on candidate profile; predict return advantage vs REFERENCE',
        hyperparameters=dict(objective='regression',max_depth=3,num_leaves=7,n_estimators=150,learning_rate=.03,
            min_child_samples=150,reg_alpha=.1,reg_lambda=10.,random_state=731,n_jobs=1,verbosity=-1),
        minimum_campaigns=dict(train=500,validation=50,test=30),
        decision='REFERENCE fallback; choose other only if predicted unit advantage >16bps, frozen before fit',
        primary_outcome='Mean NET unit return; not annual portfolio PnL, no synthesized capital or leverage gain',
        guards='B4/sizing/margin/sector/correlation NOT bypassed; economic replay required separately',
        macro='SPY price regime/volatility proxies only. No unqualified revised macro vintage predictors.',
        sector='Current classification only in diagnostics, NOT ML predictors; historical membership PIT unqualified.',
        safety=dict(fee_per_leg=.0008,confirmation_bars=2,initial_position_fraction=.5,reinforcement_enabled=False,
            entry_valid_sessions=20,hard_stop_never_widened=True),SQL_writes=False,provider_calls=0,orders=False,
        production_changed=False,full_live_parity=False,
        limitations=['Static current survivor universe and revised historical prices.',
            'Common future SIP window/known-CA exclusions create coverage selection bias.',
            'Spaced within-symbol windows do NOT make common market dates independent.',
            'Labels are paired unit counterfactuals, not portfolio quantity/capital/reapproval outcomes.',
            '2025/2026 previously examined; temporal split is not an untouched holdout.',
            'First version chooses SL/TP/trailing/horizon only; sizing/confirmation/reinforcement remain fixed.'])
    common.save_new(root/'protocol.json',p);return p


def snapshot_symbol(root,symbol,anchors,schedule,conn):
    folder=root/'symbols'/symbol;folder.mkdir(parents=True,exist_ok=True)
    marker=folder/'snapshot.json'
    if marker.exists():
        m=common.read(marker);common.verify({str(folder/n):h for n,h in m['files'].items()});return folder
    first=anchors.date.min();last=anchors.maturity_date.max()
    queries={
        'bars.parquet':("SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,payload_hash "
            "FROM stock_bars_intraday FORCE INDEX(PRIMARY) WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end "
            "AND provider='alpaca' AND data_source='alpaca_sip' AND interval_code='5m' AND market_code='US_EQ' "
            "AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 ORDER BY bar_timestamp",
            dict(symbol=symbol,start=str(first.date()),end=str((last+pd.Timedelta(days=1)).date()))),
        'daily.parquet':("SELECT date,open,high,low,close,volume,data_adjustment,is_filled,data_source FROM stock_bars_daily "
            "FORCE INDEX(PRIMARY) WHERE symbol=:symbol AND date BETWEEN :start AND :end ORDER BY date",
            dict(symbol=symbol,start=str((first-pd.Timedelta(days=650)).date()),end=str(last.date()))),
        'actions.parquet':('SELECT ca_type,ex_date FROM corporate_actions_events WHERE symbol=:symbol AND ex_date BETWEEN :start AND :end',
            dict(symbol=symbol,start=str(first.date()),end=str(last.date())))}
    files={}
    for name,(sql,params) in queries.items():
        f=pd.read_sql(text(sql),conn,params=params)
        if name=='bars.parquet':
            for k in ['bar_timestamp','bar_end_timestamp']:f[k]=pd.to_datetime(f[k],utc=True)
            f['trade_date']=pd.to_datetime(f.trade_date)
        f.to_parquet(folder/name,index=False);files[name]=common.digest(folder/name)
    common.save_new(marker,dict(files=files,SQL_reads_only=True,symbol=symbol,first=str(first),last=str(last),
        observed_at_utc=datetime.now(timezone.utc).isoformat()))
    return folder


def dataset(root):
    p=prepare(root);top=top100(root);sessions=cal_sessions();days=[pd.Timestamp(s.session_date) for s in sessions]
    schedule={pd.Timestamp(s.session_date):s for s in sessions}
    plan=sample_plan(top,sessions)
    file=root/'sample-plan.parquet'
    if file.exists():pd.testing.assert_frame_equal(pd.read_parquet(file),plan,check_exact=True)
    else:plan.to_parquet(file,index=False)
    while True:
        b=common.read(BACKFILL)
        if b['status']=='COMPLETED' and b['failed_tasks']==0:break
        if b['status']!='RUNNING':raise RuntimeError('2018 provider catchup incomplete; no automatic retry')
        atomic_json(root/'progress.json',dict(status='WAITING_2018_CATCHUP',completed=b['completed_tasks'],total=b['total_tasks']))
        time.sleep(5)
    anchors=plan[plan.anchor];symbols=sorted(anchors.symbol.unique());snapshots=[]
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as c:
            c.execute(text('SET SESSION MAX_EXECUTION_TIME=60000'))
            c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if c.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':raise ValueError('US only')
            spy_file=root/'spy-daily.parquet'
            if not spy_file.exists():
                f=pd.read_sql(text("SELECT date,open,high,low,close,volume,data_adjustment,is_filled,data_source "
                    "FROM stock_bars_daily FORCE INDEX(PRIMARY) WHERE symbol='SPY' AND date BETWEEN '2015-01-01' AND '2026-09-30' ORDER BY date"),c)
                f.to_parquet(spy_file,index=False)
            spy=price_features(pd.read_parquet(spy_file),days)
            root.joinpath('parts').mkdir(exist_ok=True)
            for number,symbol in enumerate(symbols):
                part=root/'parts'/f'{symbol}.parquet';receipt=part.with_suffix('.json')
                if receipt.exists():
                    r=common.read(receipt);common.verify({str(part):r['sha256']});snapshots.append(r);continue
                a=anchors[anchors.symbol.eq(symbol)].copy()
                atomic_json(root/'progress.json',dict(status='DATASET_READ_ONLY',symbol=symbol,completed_symbols=number,total_symbols=len(symbols),
                    completed_anchors=sum(x['qualified_anchors'] for x in snapshots),reserved_anchors=sum(x['reserved_anchors'] for x in snapshots)))
                # Release the prior read snapshot; never hold one MVCC snapshot for hours.
                c.commit()
                c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
                folder=snapshot_symbol(root,symbol,a,schedule,c)
                c.commit()
                raw=pd.read_parquet(folder/'bars.parquet');raw['session_close']=raw.trade_date.map({d:s.close_at_utc for d,s in schedule.items()})
                groups={}
                for day,g in raw.groupby('trade_date',sort=True):
                    s=schedule.get(pd.Timestamp(day))
                    if s and common.qualify_session(g,s):groups[pd.Timestamp(day)]=g.reset_index(drop=True)
                features=price_features(pd.read_parquet(folder/'daily.parquet'),days)
                actions=pd.read_parquet(folder/'actions.parquet');action_days=set(pd.to_datetime(actions.ex_date))
                data=[];reserved=[];checks=0
                for n,r in enumerate(a.itertuples()):
                    i=days.index(r.date);window=days[i:i+42]
                    x=features_at(features,spy,r.date,r.rank)
                    reason=('FEATURES_J_UNQUALIFIED' if x is None else
                        'COMMON_SIP_WINDOW_MISSING' if any(d not in groups for d in window) else
                        'CORPORATE_ACTION_RESERVED' if action_days.intersection(window) else '')
                    if reason:reserved.append(dict(date=str(r.date.date()),reason=reason));continue
                    labels,count=campaign_labels(groups,days,schedule,r,audit=(n==0 or n%20==0));checks+=count
                    for label in labels:data.append(dict(date=r.date,symbol=symbol,rank=r.rank,split=r.split,
                        maturity_date=r.maturity_date,**x,**label))
                pd.DataFrame(data).to_parquet(part,index=False)
                record=dict(symbol=symbol,sha256=common.digest(part),file=str(part.relative_to(root)),
                    qualified_anchors=len(data)//len(PROFILES),reserved_anchors=len(reserved),scalar_exit_checks=checks,reserved=reserved,
                    snapshot_sha256=common.digest(folder/'snapshot.json'))
                common.save_new(receipt,record);snapshots.append(record)
    finally:engine.dispose()
    common.verify(p['sources'])
    manifest=root/'dataset.json'
    if not manifest.exists():common.save_new(manifest,dict(parts=snapshots,plan_sha256=common.digest(file),spy_sha256=common.digest(spy_file),
        input_scores_sha256=common.digest(root/'scores.json'),qualified_anchors=sum(x['qualified_anchors'] for x in snapshots),
        reserved_anchors=sum(x['reserved_anchors'] for x in snapshots),scalar_exit_checks=sum(x['scalar_exit_checks'] for x in snapshots),
        SQL_writes=False,provider_calls=0))


def design(frame):
    result=frame[FEATURES].copy()
    params={p['name']:p for p in PROFILES}
    for k,key in [('profile_sl','sl'),('profile_tr','tr'),('profile_tp','tp'),('profile_h','h')]:
        result[k]=frame.profile.map(lambda n:params[n][key] or 0.).astype(float)
    for p in PROFILES:result['profile_'+p['name']]=frame.profile.eq(p['name']).astype(float)
    return result[FEATURES+PARAMS]


def decisions(model,frame):
    f=frame.copy();f['predicted_advantage']=model.predict(design(f))
    f.loc[f.profile.eq('REFERENCE'),'predicted_advantage']=.0016
    f['profile_order']=f.profile.map({p['name']:i for i,p in enumerate(PROFILES)})
    return f.sort_values(['date','symbol','predicted_advantage','profile_order'],ascending=[True,True,False,True]).drop_duplicates(['date','symbol'])


def fit(root):
    import lightgbm as lgb
    p=prepare(root);m=common.read(root/'dataset.json');frames=[]
    for item in m['parts']:
        common.verify({str(root/item['file']):item['sha256']})
        f=pd.read_parquet(root/item['file'])
        if not f.empty:frames.append(f)
    f=pd.concat(frames,ignore_index=True)
    if f.duplicated(['date','symbol','profile']).any():raise ValueError('Duplicate training examples')
    groups=f.groupby(['date','symbol']).profile.nunique()
    if not groups.eq(len(PROFILES)).all():raise ValueError('Unpaired labels')
    if not all(maturity_ok(d,a) for d,a in f[['date','maturity_date']].itertuples(index=False,name=None)):
        raise ValueError('Future/unmature label contamination')
    counts=f.groupby('split').size().div(len(PROFILES)).astype(int).to_dict()
    if any(counts.get(k,0)<v for k,v in p['minimum_campaigns'].items()):
        atomic_json(root/'progress.json',dict(status='BLOCKED_INSUFFICIENT_EFFECTIVE_CAMPAIGNS',counts=counts,minimum=p['minimum_campaigns']))
        return
    reference=f[f.profile.eq('REFERENCE')][['date','symbol','net_return']].rename(columns={'net_return':'reference_return'})
    f=f.merge(reference,on=['date','symbol'],validate='many_to_one');f['target_advantage']=f.net_return-f.reference_return
    train=f[f.split.eq('train')];val=f[f.split.eq('validation')]
    # A single frozen fit; 2025 picks the fixed comparator, NOT training weights.
    weights=1./train.groupby('date').date.transform('size');weights=weights/weights.mean()
    model=lgb.LGBMRegressor(**p['hyperparameters'])
    atomic_json(root/'progress.json',dict(status='TRAINING_GLOBAL_LIGHTGBM',counts=counts))
    model.fit(design(train),train.target_advantage,sample_weight=weights)
    output=root/'model';output.mkdir(exist_ok=True)
    if (output/'fit.json').exists():raise FileExistsError('Frozen fit already exists')
    model.booster_.save_model(str(output/'selector.txt'))
    constants=val.groupby('profile').net_return.mean()
    best=sorted(constants.index,key=lambda n:(-constants[n],next(i for i,p in enumerate(PROFILES) if p['name']==n)))[0]
    # Freeze fit and comparator BEFORE evaluating 2026 outcomes.
    common.save_new(output/'fit.json',dict(status='TRAINED_RESEARCH_ONLY',train_campaigns=counts['train'],
        features=FEATURES+PARAMS,model_sha256=common.digest(output/'selector.txt'),best_fixed_validation=best,
        validation_means=constants.to_dict(),test_used_for_fit=False,early_stopping_on_test=False,
        stock_specific_models=False,sector_predictors_used=False,unqualified_macro_predictors_used=False))
    summaries=[];chosen=[]
    for split in ['validation','test']:
        sub=f[f.split.eq(split)];d=decisions(model,sub);chosen.append(d)
        for name,g in [('LEARNED',d),*[(p['name'],sub[sub.profile.eq(p['name'])]) for p in PROFILES]]:
            summaries.append(dict(split=split,policy=name,opportunities=len(g),entered=int(g.entered.sum()),
                mean_net_return_pct=100*float(g.net_return.mean()),median_net_return_pct=100*float(g.net_return.median()),
                positive_pct=100*float(g.net_return.gt(0).mean()),negative_pct=100*float(g.net_return.lt(0).mean()),
                selected_profiles=g.profile.value_counts().to_dict()))
    pd.concat(chosen).to_parquet(root/'validation-test-decisions.parquet',index=False)
    pd.DataFrame([{k:v for k,v in s.items() if k!='selected_profiles'} for s in summaries]).to_csv(root/'unit-comparison.csv',index=False)
    test=next(s for s in summaries if s['split']=='test' and s['policy']=='LEARNED')
    fixed=next(s for s in summaries if s['split']=='test' and s['policy']==best)
    gain=test['mean_net_return_pct']-fixed['mean_net_return_pct']
    chosen_test=chosen[-1][['date','symbol','net_return']]
    fixed_test=f[f.split.eq('test')&f.profile.eq(best)][['date','symbol','net_return']]
    delta=chosen_test.merge(fixed_test,on=['date','symbol'],suffixes=('_learned','_fixed'),validate='one_to_one')
    delta['delta']=100*(delta.net_return_learned-delta.net_return_fixed)
    monthly=delta.groupby(delta.date.dt.to_period('M')).delta.agg(['sum','count'])
    rng=np.random.default_rng(731);boot=[]
    for _ in range(2000):
        sample=monthly.iloc[rng.integers(0,len(monthly),len(monthly))]
        boot.append(float(sample['sum'].sum()/sample['count'].sum()))
    ci=np.quantile(boot,[.025,.975]).tolist()
    verdict=('EXPLORATORY_UNIT_GAIN_REQUIRES_PORTFOLIO_TEST'
        if gain>.25 and len(test['selected_profiles'])>=2 and len(monthly)>=6 and ci[0]>0
        else 'NO_GO_STABLE_PERSONALIZATION_NOT_DEMONSTRATED')
    common.verify(p['sources'])
    common.save_new(root/'report.json',dict(status=verdict,counts=counts,comparison=summaries,test_gain_vs_validation_fixed_pp=gain,
        best_fixed_validation=best,annual_portfolio_return=None,model_global=True,SQL_writes=False,
        provider_calls=0,orders=False,production_changed=False,independent_holdout=False,
        macro_sector_limitations=dict(primary_market_context='SPY observed price proxies',
            macro_vintage_unqualified_excluded=True,sector_non_PIT_excluded=True),
        monthly_cluster_bootstrap_95_pp=ci,confirmation_months=len(monthly),bootstrap_seed=731,bootstrap_draws=2000,
        files={n:common.digest(root/n) for n in ['model/selector.txt','model/fit.json','unit-comparison.csv','validation-test-decisions.parquet']}))
    atomic_json(root/'progress.json',dict(status=verdict,counts=counts,training_completed=True,test_gain_pp=gain,
        annual_portfolio_backtest_started=False))


def smoke(root):
    parent=Path('artifacts/research/us_winner_native_grid_2017_2026/20261023-v1/inputs/2017')
    m=common.read(parent/'snapshot.json');schedule={pd.Timestamp(s.session_date):s for s in cal_sessions()}
    verified=0
    for receipt in m['receipts'][:8]:
        f=pd.read_parquet(parent/receipt['file']);f['session_close']=f.trade_date.map({d:s.close_at_utc for d,s in schedule.items()})
        if len(f)<100:continue
        for offset in [3,20,60]:
            path=f.iloc[offset:offset+3500].reset_index(drop=True)
            if len(path)<100:continue
            entry=float(path.open.iloc[0]);stamp=path.bar_timestamp.iloc[0]
            for p in PROFILES:
                due=path.bar_timestamp.iloc[min(len(path)-1,1500)]
                x=vector_exit(path,entry,due,p);y=scalar_exit(path,stamp,entry,due,sl=p['sl'],tp=p['tp'],trail=p['tr'])
                if y is None or x[0]!=y[0] or x[2]!=y[2] or abs(x[1]-y[1])>1e-8:raise AssertionError(f'Smoke scalar mismatch {x} {y}')
                verified+=1
    if verified<30:raise ValueError('Insufficient scalar smoke checks')
    atomic_json(root/'smoke.json',dict(status='PASS_VECTOR_SCALAR_REAL_SIP',checks=verified))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--phase',choices=['prepare','smoke','all','fit'],default='all');a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    with run_lock(a.output):
        try:
            prepare(a.output)
            if a.phase=='smoke':smoke(a.output)
            if a.phase=='all':
                if common.read(a.output/'smoke.json')['status']!='PASS_VECTOR_SCALAR_REAL_SIP':raise ValueError('Smoke required')
                dataset(a.output);fit(a.output)
            if a.phase=='fit':fit(a.output)
        except Exception as exc:
            atomic_json(a.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            raise


if __name__=='__main__':main()
