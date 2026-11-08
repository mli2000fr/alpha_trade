"""Independent per-stock reliability, three OOS years; research files only.

No Oracle conditioning, shared model, provider API, SQL writes or broker orders.
Options/consensus reliability is withheld when even its optimistic independent
sample upper bound cannot satisfy the frozen minimum. Missing sources are never
replaced by neutral scores to populate a requested TOP1500.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import argparse
import hashlib
import json
import logging
import math
from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from lightgbm import LGBMClassifier

from common.daily_bar_sources import select_daily_bars
from common.market_calendar import get_market_calendar
from common.trading_costs import TradingCostModel
from common.symbol_artifact_paths import symbol_directory
from database.connection import get_sqlalchemy_engine
from modelFactory.features import compute_features
from modelFactory.oracle.security_continuity import load_security_discontinuities
from scripts.research.us_winner_per_symbol_long_20261103 import INPUTS, FEATURES, DELTAS, long_labels

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/research/us_predictable_symbols/20261103-v1'
SOURCE=ROOT/'config/univers_batch/action_ordinaire.txt'
ASOF=pd.Timestamp('2026-11-02')
TARGETS=('winner_h10','parcours_h20')
YEARS=(2023,2024,2025,2026)
RANK_YEARS=(2023,2024,2025)
FIT=dict(n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,min_child_samples=60,
    reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=1,random_state=20261103)
LOG=logging.getLogger(__name__)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
    tmp.replace(path)


def path_labels(bars,calendar,breaks=()):
    """J+1 open, max high/min low over twenty holding sessions, no SL.

    Same-session high/low order is unknown from daily OHLC. Earliest session
    containing each peak is retained; no invented within-session sequence.
    """
    p,valid=label_arrays(bars,calendar,21,breaks)
    n=max(0,len(calendar)-20)
    if not n:return pd.DataFrame(columns=['date','label','label_available_date'])
    high=np.lib.stride_tricks.sliding_window_view(p[:,1],21)[:,1:]
    low=np.lib.stride_tricks.sliding_window_view(p[:,2],21)[:,1:]
    up_at=np.argmax(high,axis=1)+1;down_at=np.argmin(low,axis=1)+1
    entry=p[1:n+1,0]
    up=np.maximum(0.,np.max(high,axis=1)/entry-1)
    down=np.minimum(0.,np.min(low,axis=1)/entry-1)
    tied=np.isclose(up,-down,rtol=0,atol=1e-10)
    labels=np.where(tied,np.nan,(up>-down).astype(float))
    return pd.DataFrame(dict(date=calendar[:n],label=labels,label_available_date=calendar[20:],
        max_up_pct=100*up,max_down_pct=100*down,up_peak_session=up_at,down_peak_session=down_at,
        first_peak=np.where(up_at==down_at,'SAME_SESSION_ORDER_UNKNOWN',np.where(up_at<down_at,'UP','DOWN'))))[valid].copy()


def label_arrays(bars,calendar,width,breaks=()):
    a=bars.set_index('date').reindex(calendar)
    factor=pd.to_numeric(a.adj_close,errors='coerce').fillna(a.close)/a.close
    p=a[['open','high','low','close']].multiply(factor,axis=0).to_numpy(float)
    good=(np.isfinite(p).all(axis=1)&(p>0).all(axis=1)&(p[:,1]>=np.maximum(p[:,0],p[:,3]))
          &(p[:,2]<=np.minimum(p[:,0],p[:,3]))&a.is_filled.eq(0).to_numpy()&a.volume.gt(0).to_numpy())
    if len(calendar)<width:return p,np.zeros(0,dtype=bool)
    valid=np.lib.stride_tricks.sliding_window_view(good,width).all(axis=1)
    for column in ('instrument_id','data_source'):
        codes=pd.factorize(a[column],sort=False)[0]
        windows=np.lib.stride_tricks.sliding_window_view(codes,width)
        valid&=(windows>=0).all(axis=1)&(windows==windows[:,[0]]).all(axis=1)
    if breaks:
        for i in np.flatnonzero(valid):
            if any(event.crosses(calendar[i],calendar[i+width-1]) for event in breaks):valid[i]=False
    return p,valid


def winner_labels(bars,calendar,fee,breaks=()):
    p,valid=label_arrays(bars,calendar,12,breaks)
    n=max(0,len(calendar)-11)
    if not n:return pd.DataFrame(columns=['date','label','label_available_date'])
    opens=np.lib.stride_tricks.sliding_window_view(p[:,0],12)
    lows=np.lib.stride_tricks.sliding_window_view(p[:,2],12)
    entry=opens[:,1];floor=entry*.95
    hits=lows[:,1:11]<=floor[:,None]
    any_hit=hits.any(axis=1);first=hits.argmax(axis=1)+1
    first_open=opens[np.arange(n),first]
    stop_price=np.where(first_open<=floor,first_open,floor)
    exit_price=np.where(any_hit,stop_price,opens[:,11])
    net=exit_price*(1-fee)/(entry*(1+fee))-1
    return pd.DataFrame(dict(date=calendar[:n],label=(net>0).astype(float),
        label_net_return=net,label_available_date=calendar[11:],
        label_exit=np.where(any_hit,np.where(first_open<=floor,'SL_GAP','SL'),'TIME_OPEN')))[valid].copy()


def split(panel,year):
    boundary=pd.Timestamp(f'{year}-01-01');cal_start=pd.Timestamp(f'{year-1}-01-01')
    fit=panel[panel.date.lt(cal_start)&panel.label_available_date.lt(cal_start)&panel.label.notna()]
    cal=panel[panel.date.ge(cal_start)&panel.date.lt(boundary)&panel.label_available_date.lt(boundary)&panel.label.notna()]
    test=panel[panel.date.ge(boundary)&panel.date.lt(pd.Timestamp(f'{year+1}-01-01'))
               &panel.label_available_date.le(ASOF)&panel.label.notna()]
    return fit,cal,test


def metrics(frame):
    y=frame.label.to_numpy(int);p=frame.probability.to_numpy(float)
    auc=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None
    selected=frame[frame.probability.ge(frame.long_threshold)]
    return dict(rows=len(frame),positive=int(y.sum()),auc=auc,
        brier=float(brier_score_loss(y,p)) if len(y) else None,
        baseline_brier=float(np.mean((y-frame.baseline_probability.to_numpy(float))**2)) if len(y) else None,
        long_selected=len(selected),long_winners=int(selected.label.sum()),
        long_precision=float(selected.label.mean()) if len(selected) else None,
        base_rate=float(np.mean(y)) if len(y) else None)


def wilson(k,n,z=1.96):
    if n==0:return 0.,1.
    p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return center-radius,center+radius


def reliability(frame,target):
    h=10 if target=='winner_h10' else 20
    a=frame[frame.year.isin(RANK_YEARS)].copy()
    sparse=a[a.session_index.mod(h).eq(0)]
    annual=[dict(year=year,**metrics(a[a.year.eq(year)]),
                 sparse=metrics(sparse[sparse.year.eq(year)])) for year in RANK_YEARS]
    allstats=metrics(sparse)
    selected=sparse[sparse.probability.ge(sparse.long_threshold)]
    lower,_=wilson(int(selected.label.sum()),len(selected))
    _,base_upper=wilson(int(sparse.label.sum()),len(sparse))
    annual_auc=[x['sparse']['auc'] for x in annual]
    qualified=(all(x['rows']>=150 for x in annual) and len(sparse)>=(45 if h==10 else 24)
        and all(x is not None for x in annual_auc) and sparse.label.nunique()==2 and len(selected)>=8)
    lift=None if not len(selected) else float(selected.label.mean()-sparse.label.mean())
    score=lower-base_upper
    return dict(qualified_history=bool(qualified),annual=annual,sparse=allstats,
        long_precision_lift=lift,long_lift_conservative_bound=score,
        worst_annual_auc=min(x for x in annual_auc if x is not None) if any(x is not None for x in annual_auc) else None,
        reliability_confirmed=bool(qualified and score>0 and all(x['sparse']['auc']>.5 for x in annual)),
        n_independent=len(sparse),rank_uses_2026=False,
        check_2026=metrics(frame[frame.year.eq(2026)]))


def make_panel(raw,bench,calendar,breaks):
    raw=raw.copy();raw['date']=pd.to_datetime(raw.date)
    raw=select_daily_bars(raw).sort_values('date')
    if raw.date.duplicated().any():raise ValueError('Duplicate qualified daily dates')
    # Missing sessions are not forward-filled into returns or entry labels.
    valid=raw.set_index('date').reindex(calendar)
    valid['symbol']=str(raw.symbol.iloc[0])
    valid=valid.rename_axis('date').reset_index()
    numeric=['open','high','low','close','volume','adj_close','vwap']
    for c in numeric:valid[c]=pd.to_numeric(valid[c],errors='coerce')
    bar_ok=(valid[['open','high','low','close']].notna().all(axis=1)
        &valid.is_filled.eq(0)&valid.volume.gt(0)&valid.instrument_id.notna())
    valid.loc[~bar_ok,['open','high','low','close','adj_close','vwap','volume']]=np.nan
    features=compute_features(valid,benchmark_df=bench,feature_set='expert',include_factors=False)
    history_ok=pd.Series(bar_ok.to_numpy(),index=calendar).rolling(60,min_periods=60).sum().eq(60)
    features=features[features.date.map(history_ok).fillna(False)].copy()
    features=features.set_index('date').reindex(calendar)
    for c in DELTAS:
        features[c+'_delta5']=(features[c]-features[c].shift(5)).where(features[c].notna().rolling(6).sum().eq(6))
    features=features.rename_axis('date').reset_index()[['date',*INPUTS]]
    panels={}
    for target in TARGETS:
        labels=(winner_labels(raw,calendar,
            fee=TradingCostModel().per_leg_cost_pct,breaks=breaks) if target=='winner_h10'
            else path_labels(raw,calendar,breaks=breaks))
        frame=features.merge(labels,on='date',how='left',validate='one_to_one')
        frame['session_index']=np.arange(len(frame))
        frame=frame[frame[INPUTS].notna().mean(axis=1).ge(.8)]
        panels[target]=frame
    return raw,panels


def stock(symbol,raw,bench,calendar,breaks):
    folder=symbol_directory(OUT/'symbols',symbol);folder.mkdir(parents=True,exist_ok=True)
    receipt=folder/'result.json'
    if receipt.exists():return json.loads(receipt.read_text(encoding='utf-8'))
    result=dict(symbol=symbol,targets={},status='PROCESSED',models=0)
    if raw.empty:
        result.update(status='NO_DAILY_BARS');save(receipt,result);return result
    raw.to_parquet(folder/'source-bars.parquet',index=False)
    result['bars_sha256']=digest(folder/'source-bars.parquet')
    _,panels=make_panel(raw,bench,calendar,breaks)
    for target,panel in panels.items():
        scored=[];fits=[]
        panel.to_parquet(folder/(target+'-panel.parquet'),index=False)
        for year in YEARS:
            fit,cal,test=split(panel,year)
            evidence=dict(year=year,fit_rows=len(fit),calibration_rows=len(cal),test_rows=len(test),status='INSUFFICIENT_HISTORY')
            enough=(len(fit)>=756 and len(cal)>=126 and not test.empty
                and fit.label.value_counts().reindex([0.,1.],fill_value=0).min()>=40
                and cal.label.value_counts().reindex([0.,1.],fill_value=0).min()>=15)
            if enough:
                lo,hi=fit[INPUTS].quantile(.01),fit[INPUTS].quantile(.99)
                x=fit[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                z=cal[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                model=make_pipeline(SimpleImputer(strategy='median').set_output(transform='pandas'),LGBMClassifier(**FIT))
                model.fit(x,fit.label.astype(int))
                cp=np.clip(model.predict_proba(z)[:,1],1e-6,1-1e-6)
                if np.std(cp)<=1e-6:
                    evidence['status']='CONSTANT_MODEL';fits.append(evidence);continue
                calibrator=LogisticRegression(C=1.,random_state=20261103)
                calibrator.fit(np.log(cp/(1-cp)).reshape(-1,1),cal.label.astype(int))
                calp=calibrator.predict_proba(np.log(cp/(1-cp)).reshape(-1,1))[:,1]
                threshold=float(np.quantile(calp,.7))  # Fixed prior-year quantile, never test-tuned.
                obs=test[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                prob=np.clip(model.predict_proba(obs)[:,1],1e-6,1-1e-6)
                score=test[['date','label','label_available_date','session_index']].copy()
                for c in ['max_up_pct','max_down_pct','up_peak_session','down_peak_session','first_peak','label_net_return','label_exit']:
                    if c in test:score[c]=test[c]
                score['probability']=calibrator.predict_proba(np.log(prob/(1-prob)).reshape(-1,1))[:,1]
                score['long_threshold']=threshold;score['baseline_probability']=float(cal.label.mean());score['year']=year
                scored.append(score)
                modelpath=folder/f'{target}-{year}.joblib'
                joblib.dump(dict(model=model,calibrator=calibrator,lo=lo,hi=hi,features=INPUTS,
                    long_threshold=threshold,target=target,year=year),modelpath,compress=3)
                evidence.update(status='FITTED',fit_label_available_max=str(fit.label_available_date.max()),
                    calibration_label_available_max=str(cal.label_available_date.max()),model_sha256=digest(modelpath))
                assert fit.label_available_date.max()<pd.Timestamp(f'{year-1}-01-01')
                assert cal.label_available_date.max()<pd.Timestamp(f'{year}-01-01')
                result['models']+=1
            fits.append(evidence)
        if scored:
            scores=pd.concat(scored,ignore_index=True)
            scores.to_parquet(folder/(target+'-predictions.parquet'),index=False)
            result['targets'][target]=dict(fits=fits,**reliability(scores,target))
        else:result['targets'][target]=dict(fits=fits,qualified_history=False,reliability_confirmed=False)
    save(receipt,result)
    return result


def load_bars(engine,symbols):
    sql='''SELECT symbol,date,CAST(open AS DOUBLE) open,CAST(high AS DOUBLE) high,
        CAST(low AS DOUBLE) low,CAST(close AS DOUBLE) close,CAST(volume AS DOUBLE) volume,
        CAST(adj_close AS DOUBLE) adj_close,CAST(vwap AS DOUBLE) vwap,
        is_filled,data_source,instrument_id FROM stock_bars_daily FORCE INDEX (PRIMARY)
        WHERE symbol IN :symbols AND date>='2016-01-01' AND date<=:end
        AND data_source IN ('eodhd_eod','alpaca_sip') ORDER BY symbol,date'''
    with engine.connect() as conn:
        conn.execute(text('START TRANSACTION READ ONLY'))
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=60000'))
        frame=pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,
                          params={'symbols':symbols,'end':ASOF.date()})
        conn.rollback()
    return frame


def availability_gate(symbols,calendar):
    """A necessary upper-bound check, not a claim rows are source-qualified."""
    oi=pd.read_parquet(OUT/'options_snapshots-coverage.parquet').set_index('symbol')
    vol=pd.read_parquet(OUT/'options_volume-coverage.parquet').set_index('symbol')
    cons=pd.read_parquet(OUT/'consensus-coverage.parquet').set_index('symbol')
    rows=[]
    for target in TARGETS:
        h=10 if target=='winner_h10' else 20
        for symbol in symbols:
            starts={}
            if symbol in oi.index and symbol in vol.index:
                starts['options']=max(pd.Timestamp(oi.loc[symbol,'first_available']),pd.Timestamp(vol.loc[symbol,'first_available']))
            if symbol in cons.index:starts['consensus']=pd.Timestamp(cons.loc[symbol,'first_available'])
            for family in ('options','consensus'):
                stamp=starts.get(family)
                # Include the receipt day and every subsequent session: optimistic
                # even for after-close receipts or missing/rejected paired rows.
                n=0 if stamp is None else int((calendar>=stamp.normalize()).sum())
                matured=max(0,n-h)
                independent=math.ceil(matured/h)
                rows.append(dict(symbol=symbol,target=target,source=family,
                    first_receipt=None if stamp is None else str(stamp),
                    optimistic_matured_sessions=matured,optimistic_independent_upper_bound=independent,
                    minimum_independent_required=20,
                    status='SOURCE_ABSENT' if stamp is None else 'INSUFFICIENT_HISTORY' if independent<20 else 'NEEDS_FULL_SOURCE_QUALIFICATION'))
    frame=pd.DataFrame(rows);frame.to_parquet(OUT/'source-reliability-gates.parquet',index=False)
    if frame.status.eq('NEEDS_FULL_SOURCE_QUALIFICATION').any():
        raise ValueError('Source history now sufficient: implement/review full dated feature qualification before ranking, never silently skip it')
    return frame


def finalize(symbols,gates):
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((OUT/'symbols').glob('*/result.json'))]
    records={r['symbol']:r for r in rows}
    if set(records)!=set(symbols):raise ValueError('Every requested symbol must have an audit receipt')
    report={'status':'COMPLETED_WITH_UNQUALIFIED_SOURCES','symbols_requested':len(symbols),
        'processed':len(records),'models_fitted':sum(r.get('models',0) for r in rows),
        'errors':sum(r['status']=='ERROR' for r in rows),'cases':{},'sql_writes':False,'provider_calls':0,
        'ranking_years':RANK_YEARS,'check_year_not_used_for_rank':2026,
        'warning':'Intersections empty because options/consensus histories cannot establish per-symbol reliability; not evidence no predictable stocks exist.'}
    if report['errors']:report['status']='PARTIAL_FAILED_WITH_UNQUALIFIED_SOURCES'
    for target in TARGETS:
        ranking=[]
        for symbol in symbols:
            r=records.get(symbol,{});t=r.get('targets',{}).get(target,{})
            ranking.append(dict(symbol=symbol,status=r.get('status','NOT_PROCESSED'),
                qualified_history=t.get('qualified_history',False),reliability_confirmed=t.get('reliability_confirmed',False),
                long_lift_conservative_bound=t.get('long_lift_conservative_bound'),
                worst_annual_auc=t.get('worst_annual_auc'),auc_nonoverlap=t.get('sparse',{}).get('auc'),
                independent_observations=t.get('n_independent',0),precision_lift=t.get('long_precision_lift'),
                check_2026_auc=t.get('check_2026',{}).get('auc')))
        allrows=pd.DataFrame(ranking)
        allrows.to_csv(OUT/(target+'-per-symbol-audit.csv'),index=False)
        ranked=allrows[allrows.qualified_history].sort_values(
            ['long_lift_conservative_bound','worst_annual_auc','auc_nonoverlap','symbol'],ascending=[False,False,False,True]).copy()
        ranked['rank']=np.arange(1,len(ranked)+1)
        ranked.to_csv(OUT/(target+'-per-symbol-ranking.csv'),index=False)
        shortlist=ranked.head(1500).symbol.tolist()
        (OUT/(target+'-model-top1500.txt')).write_text(','.join(shortlist)+'\n',encoding='utf-8')
        # Necessary-history gates excluded everyone before numeric performance
        # fitting; do not manufacture an ordering from today's bullishness.
        for family in ('options','consensus'):
            (OUT/(target+'-'+family+'-top1500.txt')).write_text('',encoding='utf-8')
        eligible=ranked[ranked.reliability_confirmed].symbol.tolist()
        (OUT/(target+'-model-confirmed.txt')).write_text(','.join(eligible)+'\n',encoding='utf-8')
        final=ROOT/'config/univers_batch'/('symbol_trade_'+target+'.txt')
        if final.exists():raise FileExistsError('Do not overwrite an existing trading universe')
        final.write_text('',encoding='utf-8')
        report['cases'][target]=dict(model_history_qualified=len(ranked),model_top1500=len(shortlist),
            model_exploratory_confirmed=len(eligible),options_top1500=0,consensus_top1500=0,
            intersection=0,output=str(final),not_production_certified=True,
            source_gate_counts=gates[gates.target.eq(target)].groupby(['source','status']).size().to_dict())
        # JSON cannot serialize tuple dictionary keys.
        report['cases'][target]['source_gate_counts']={f'{a}/{b}':int(n) for (a,b),n in report['cases'][target]['source_gate_counts'].items()}
        save(final.with_suffix('.audit.json'),dict(status='UNQUALIFIED_EMPTY_DO_NOT_USE_FOR_TRADING',target=target,
            symbols=0,reason='Options/consensus reliability history insufficient',report=str(OUT/'report.json')))
    save(OUT/'report.json',report)
    return report


def run(workers=3):
    symbols=sorted(set(SOURCE.read_text(encoding='utf-8-sig').strip().split(',')))
    if len(symbols)!=5253:raise ValueError('Ordinary-share source changed; freeze a fresh campaign')
    calendar=pd.DatetimeIndex(get_market_calendar('US_EQ',allow_us_weekday_fallback=False).session_dates(date(2016,1,1),ASOF.date()))
    gates=availability_gate(symbols,calendar)
    files=[SOURCE,ROOT/'config.yaml',Path(__file__),ROOT/'modelFactory/features.py',
        ROOT/'config/data_quality/security_discontinuities.json']
    protocol=dict(status='FROZEN_BEFORE_FIT',created_at_utc=datetime.now(timezone.utc).isoformat(),symbols=symbols,
        targets={'winner_h10':'Daily proxy LONG next open, SL5, no TP/trailing, exit open11, net fees positive; not full Winner5m execution',
            'parcours_h20':'Max upward high excursion > absolute downward low excursion from next open over20 sessions; ties unknown; daily same-session peak order unknown'},
        ranking_years=RANK_YEARS,check_year=2026,asof=str(ASOF.date()),features=INPUTS,model=FIT,
        annual_refit=True,fit_min_rows=756,calibration='Previous calendar year; at least126 rows; own-stock Platt',
        training_start='2016-01-01',class_min_fit=40,class_min_calibration=15,
        long_threshold='70th percentile of own-stock prior-year calibrated probabilities; fixed quantile',
        ranking='Conservative Wilson LONG precision lift bound then worst annual nonoverlap AUC then pooled nonoverlap AUC; TOP1500 exploratory, not proof of reliability',
        independent_phase='Global calendar session index mod target horizon ==0, fixed before outcomes',
        source_min_independent=20,unknown_source_policy='Exclude, never fill1500 with missing data',
        intersection_policy='Strict common membership in all three matching-target lists',
        fees_per_leg=TradingCostModel().per_leg_cost_pct,
        limitations=['Current survivorship universe','Reconstructed historical prices, no archived as-known vintage claim',
            'Many per-symbol comparisons; no multiple-testing-adjusted certification','2024-26 periods previously explored',
            'Maximum path direction is not executable realized PnL','No native Winner5m portfolio replay'],
        source_hashes={str(p.relative_to(ROOT)):digest(p) for p in files},sql_writes=False,provider_calls=0,llm_calls=0,broker_orders=0)
    frozen=OUT/'protocol.json'
    if frozen.exists():
        old=json.loads(frozen.read_text(encoding='utf-8'))
        if old['source_hashes']!=protocol['source_hashes']:raise ValueError('Frozen source changed')
    else:save(frozen,protocol)
    engine=get_sqlalchemy_engine(db_name='alpha_trade');bench=load_bars(engine,['SPY'])
    bench['date']=pd.to_datetime(bench.date);bench=select_daily_bars(bench).sort_values('date')
    registry=load_security_discontinuities();start=time.monotonic();done=0;fitted=0
    chunks=[symbols[i:i+50] for i in range(0,len(symbols),50)]
    def chunk(group):
        remaining=[s for s in group if not (symbol_directory(OUT/'symbols',s)/'result.json').exists()]
        data=load_bars(engine,remaining) if remaining else pd.DataFrame()
        results=[]
        for symbol in group:
            try:
                a=pd.DataFrame() if data.empty else data[data.symbol.eq(symbol)].copy()
                if not a.empty:a['date']=pd.to_datetime(a.date)
                results.append(stock(symbol,a,bench,calendar,registry.get(symbol,())))
            except Exception as exc:
                LOG.exception('Symbol %s failed',symbol)
                r=dict(symbol=symbol,status='ERROR',error_type=type(exc).__name__,targets={},models=0)
                save(symbol_directory(OUT/'symbols',symbol)/'result.json',r);results.append(r)
        return results
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs=[pool.submit(chunk,group) for group in chunks]
        for future in as_completed(jobs):
            records=future.result();done+=len(records);fitted+=sum(r.get('models',0) for r in records)
            elapsed=time.monotonic()-start
            save(OUT/'progress.json',dict(status='AUDITING_PER_SYMBOL',completed=done,total=len(symbols),
                models_fitted=fitted,elapsed_seconds=elapsed,remaining_seconds_estimate=elapsed/max(done,1)*(len(symbols)-done)))
            LOG.info('Symbols %s/%s models=%s elapsed=%.1fs',done,len(symbols),fitted,elapsed)
    result=finalize(symbols,gates)
    save(OUT/'progress.json',dict(status=result['status'],completed=done,total=len(symbols),models_fitted=fitted,
        elapsed_seconds=time.monotonic()-start,errors=result['errors']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:run(args.workers)
    except Exception:
        LOG.exception('Campaign failed')
        save(OUT/'failure.json',dict(status='FAILED',at_utc=datetime.now(timezone.utc).isoformat()))
        raise
