"""Read-only audit of CALL/PUT filtering against matched Oracle candidates."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from dataclasses import replace
import re

import pandas as pd
import numpy as np
from sqlalchemy import text

from scripts.research.us_consensus_observed_revision_pilot import connect_readonly
from scripts.research.us_collected_directional_refresh_20261105 import query
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_options_winrate/20261109-v1')
MODELS={'H10':'model-factory-20261107222627-db80b0','H20':'model-factory-20261108130333-7a5385'}
HORIZONS=(5,10,15,20)
RANKS=(10,20,50)


def inventory(root):
    root.mkdir(parents=True,exist_ok=False)
    cutoff=datetime.now(timezone.utc)
    engine,conn=connect_readonly()
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        params=dict(start='2026-09-01',cutoff=cutoff.replace(tzinfo=None))
        result={'cutoff_utc':cutoff.isoformat(),'start':params['start'],'SQL_writes':0,'provider_calls':0,'orders':0}
        for table,extra in [('stock_option_snapshots',''),('stock_option_bars_delayed',",timeframe")]:
            result[table]=query(conn,f'''SELECT provider,feed{extra},DATE(available_at) day,COUNT(*) n,
                COUNT(DISTINCT underlying_symbol) symbols,MIN(observed_at) first_observed,MAX(observed_at) last_observed
                FROM {table} WHERE available_at>=:start AND available_at<=:cutoff
                GROUP BY provider,feed{extra},DATE(available_at) ORDER BY day''',**params)
        result['oracle']=query(conn,'''SELECT p.batch_id,l.target_horizon,COUNT(*) n,
            COUNT(DISTINCT p.prediction_date) dates,MIN(p.prediction_date) first_signal,
            MAX(p.prediction_date) last_signal,MIN(p.created_at) first_created,MAX(p.created_at) last_created
            FROM oracle_extreme_predictions p JOIN oracle_path_prediction_lineage l
              ON l.batch_id=p.batch_id AND l.symbol=p.symbol AND l.prediction_date=p.prediction_date
            WHERE p.prediction_date>=:start AND p.created_at<=:cutoff
            GROUP BY p.batch_id,l.target_horizon''',**params)
        result['runs']=query(conn,'''SELECT batch_name,status,COUNT(*) n,MAX(started_at) last_started,
            MAX(finished_at) last_finished FROM pit_collection_runs WHERE started_at>=:start
            AND batch_name IN ('oracle_options_indicative_snapshot','options_delayed_bars_sync')
            GROUP BY batch_name,status''',start=params['start'])
        conn.rollback()
    finally:conn.close();engine.dispose()
    atomic_json(root/'inventory.json',result)
    atomic_json(root/'progress.json',dict(status='INVENTORY_READY'))
    print(json.dumps({k:result[k] for k in ['cutoff_utc','oracle','runs']},default=str,ensure_ascii=False))


def snapshot(root):
    from common.config_loader import load_config
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract
    from service.options_directional.config import load_options_filter_config
    from service.options_directional.runner import validate_oracle_lineage
    if (root/'snapshot-seal.json').exists():raise FileExistsError('Immutable snapshot')
    cfg=load_config();options=load_options_filter_config();cutoff=pd.Timestamp.now(tz='UTC')
    universe_file=Path('config/univers_batch/univers_filtred_tradable.txt')
    universe=sorted(set(s.upper() for s in re.split(r'[,;\s]+',universe_file.read_text(encoding='utf-8-sig')) if s))
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    calendar=pd.DataFrame([dict(day=pd.Timestamp(s.session_date),opened=pd.Timestamp(s.open_at_utc),closed=pd.Timestamp(s.close_at_utc))
        for s in cal.sessions(pd.Timestamp('2026-09-01').date(),pd.Timestamp('2026-12-31').date()) if s.is_open])
    calendar.to_parquet(root/'calendar.parquet',index=False);days=list(calendar.day)
    models={};sources={str(Path(__file__)):digest(Path(__file__)),str(universe_file):digest(universe_file)}
    for label,batch in MODELS.items():
        folder,contract,_,folds=load_contract('artifacts/models',batch)
        if pd.Timestamp(contract['training_config']['data']['training_end_date'])>=pd.Timestamp('2026-01-01'):
            raise ValueError('Model trained on evaluated year')
        models[batch]=dict(profile_hash=digest(folder/'feature_profile.json'),folds=folds,horizon=contract['horizon'],label=label)
        for name in ['protocol.json','feature_profile.json','report.json']:sources[str(folder/name)]=digest(folder/name)
        for fold in folds.values():sources[str(fold['model_file'])]=digest(fold['model_file'])
    for name in ['service/options_directional/features.py','service/options_directional/history.py','service/options_directional/runner.py',
        'common/daily_bar_sources.py','common/options_directional_contract.py','config/data_quality/security_discontinuities.json',
        'scripts/research/us_options_top20_refresh_20261030.py','scripts/research/fr_p0_p1_directional_audit_20261026.py']:
        sources[name]=digest(Path(name))
    protocol=dict(cutoff_utc=str(cutoff),start='2026-09-01',models=models,universe=universe,options=options.snapshot(),ranks=RANKS,
        horizons=HORIZONS,price_config={'market_data':{'daily_bars_preferred_source':cfg.get('market_data',{}).get('daily_bars_preferred_source','eodhd')}},
        trade=dict(entry='J+1 official open',stop_loss=.05,take_profit=None,trailing=None,exit='open of H+1-th holding session',
            fees_per_leg=.0008,commission_slippage_combined=True,financing=False,dividends=False,independent_entries=True),
        decision='five minutes before next official open',physical_oracle_required_for_prospective_claim=True,
        provider_calls=0,SQL_writes=0,orders=0,new_inference=False,training=False,threshold_search=False,sources=sources)
    atomic_json(root/'protocol.json',protocol)
    engine,conn=connect_readonly()
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        params=dict(start=protocol['start'],end=str(cutoff.date()),cutoff=cutoff.tz_localize(None).to_pydatetime(),batches=list(MODELS.values()))
        raw=pd.DataFrame(query(conn,'''SELECT p.prediction_date signal_day,p.symbol,p.proba_extreme,p.fold_start,p.batch_id,
            p.created_at prediction_created_at,l.created_at lineage_created_at,l.fold_start lineage_fold_start,
            l.model_available_date,l.target_name,l.target_horizon,l.model_sha256,l.feature_profile_sha256
            FROM oracle_extreme_predictions p JOIN oracle_path_prediction_lineage l
              ON l.batch_id=p.batch_id AND l.symbol=p.symbol AND l.prediction_date=p.prediction_date
            WHERE p.batch_id IN :batches AND p.prediction_date BETWEEN :start AND :end AND p.created_at<=:cutoff''',**params))
        raw['signal_day']=pd.to_datetime(raw.signal_day);raw.to_parquet(root/'oracle-raw.parquet',index=False)
        rows=[];coverage=[]
        for (batch,day),group in raw[raw.symbol.isin(universe)].groupby(['batch_id','signal_day']):
            if group.symbol.duplicated().any():raise ValueError('Duplicate Oracle keys')
            covered=len(group)/len(universe)
            coverage.append(dict(batch_id=batch,signal_day=str(day.date()),count=len(group),universe=len(universe),ratio=covered,
                qualifies=covered>=options.min_oracle_coverage_ratio))
            if covered<options.min_oracle_coverage_ratio:continue
            model=models[batch]
            validate_oracle_lineage(group.to_dict('records'),day.date(),model['profile_hash'],model['folds'],horizon=model['horizon'])
            entry=days[days.index(day)+1];decision=calendar.set_index('day').loc[entry,'opened']-pd.Timedelta(minutes=5)
            if decision>=cutoff:continue
            group=group.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(50).copy()
            group['oracle_rank']=np.arange(1,len(group)+1);group['entry_day']=entry;group['decision_at']=decision
            # Rank is physical only if the ENTIRE ranking was available before selecting TOP-N.
            full=raw[raw.batch_id.eq(batch)&raw.signal_day.eq(day)&raw.symbol.isin(universe)]
            group['physical_oracle']=bool((pd.to_datetime(full.prediction_created_at,utc=True).lt(decision)
                &pd.to_datetime(full.lineage_created_at,utc=True).lt(decision)).all())
            group['model_label']=model['label'];rows.append(group)
        if not rows:raise ValueError('No qualified Oracle dates')
        top=pd.concat(rows,ignore_index=True);top.to_parquet(root/'oracle-top50.parquet',index=False)
        pd.DataFrame(coverage).to_csv(root/'oracle-coverage.csv',index=False)
        params=dict(start=protocol['start'],end=protocol['cutoff_utc'][:10],cutoff=params['cutoff'],symbols=sorted(top.symbol.unique()))
        queries={
            'snapshots':'''SELECT id,provider,feed,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                observed_at,available_at,provider_timestamp,open_interest,payload_hash FROM stock_option_snapshots
                WHERE provider='alpaca' AND feed='indicative' AND underlying_symbol IN :symbols
                AND available_at>=:start AND available_at<=:cutoff AND observed_at<=:cutoff''',
            'volumes':'''SELECT id,provider,feed,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                bar_timestamp,observed_at,available_at,volume,payload_hash,provenance_status,timeframe FROM stock_option_bars_delayed
                WHERE provider='alpaca' AND timeframe='30Min' AND underlying_symbol IN :symbols
                AND available_at>=:start AND available_at<=:cutoff AND observed_at<=:cutoff
                AND bar_timestamp>=:start AND bar_timestamp<=:cutoff''',
            'prices':'''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,data_adjustment,instrument_id,
                ingested_at,last_updated FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN :start AND :end
                AND data_source IN ('eodhd_eod','alpaca_sip')'''}
        for name,sql in queries.items():
            selected_params={k:v for k,v in params.items() if ':'+k in sql}
            count=query(conn,'SELECT COUNT(*) n FROM ('+sql+') bounded_export',**selected_params)[0]['n']
            if count>600000:raise ValueError(f'Export needs partition, no truncation: {name}={count}')
            frame=pd.DataFrame(query(conn,sql,**selected_params))
            if len(frame)!=count:raise ValueError('Export count mismatch')
            frame.to_parquet(root/(name+'.parquet'),index=False);print(name,len(frame),flush=True)
        conn.rollback()
    finally:conn.close();engine.dispose()
    atomic_json(root/'snapshot-seal.json',dict(files={p.name:digest(p) for p in root.iterdir() if p.is_file() and p.name not in ('progress.json',)},sources=sources))
    atomic_json(root/'progress.json',dict(status='SNAPSHOT_READY',oracle_candidates=len(top),oracle_dates=int(top.signal_day.nunique())))


def trade_label(path,window,exit_day,*,stop=.05,fee=.0008):
    """Independent LONG; no target, so stop-day high/low ordering is immaterial."""
    frame=path.reindex(list(window)+[exit_day])
    numeric=frame[['open','high','low','close']].apply(pd.to_numeric,errors='coerce')
    quality=(np.isfinite(numeric.to_numpy(float)).all(axis=1)&numeric.gt(0).all(axis=1)&frame.is_filled.eq(0)
        &frame.instrument_id.notna()&frame.data_adjustment.eq('split')
        &numeric.high.ge(numeric[['open','close']].max(axis=1))&numeric.low.le(numeric[['open','close']].min(axis=1)))
    if not quality.all() or frame.instrument_id.nunique()!=1:return dict(trade_status='INVALID_OR_MISSING_PRICE_IDENTITY')
    entry=float(numeric.iloc[0].open);stop_price=entry*(1-stop);exit_price=float(numeric.iloc[-1].open);reason='HORIZON_OPEN';exit_date=exit_day
    for day,r in numeric.iloc[:-1].iterrows():
        if r.open<=stop_price:exit_price=float(r.open);reason='STOP_GAP';exit_date=day;break
        if r.low<=stop_price:exit_price=stop_price;reason='STOP';exit_date=day;break
    no_stop=float(numeric.iloc[-1].open)*(1-fee)/(entry*(1+fee))-1
    net=exit_price*(1-fee)/(entry*(1+fee))-1
    return dict(trade_status='VALID',entry_price=entry,exit_price=exit_price,exit_date=str(pd.Timestamp(exit_date).date()),exit_reason=reason,
        net_return_pct=100*net,winning=net>0,nostop_net_return_pct=100*no_stop,nostop_winning=no_stop>0)


def describe(frame,*,without_stop=False):
    valid=frame[frame.trade_status.eq('VALID')]
    col='nostop_winning' if without_stop else 'winning';ret='nostop_net_return_pct' if without_stop else 'net_return_pct'
    return dict(candidates=len(frame),n=len(valid),wins=int(valid[col].sum()) if len(valid) else 0,
        win_rate_pct=100*float(valid[col].mean()) if len(valid) else None,
        symbols=int(valid.symbol.nunique()),dates=int(valid.signal_day.nunique()),
        mean_return_pct=float(valid[ret].mean()) if len(valid) else None,
        status_counts=frame.trade_status.value_counts().to_dict())


def analyze(root):
    from common.daily_bar_sources import select_daily_bars
    from service.options_directional.config import OptionsFilterConfig
    from service.options_directional.features import build_features,select_top
    from scripts.research.us_options_top20_refresh_20261030 import labels_for_path,auc_metrics
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    seal=json.loads((root/'snapshot-seal.json').read_text(encoding='utf-8'))
    for name,sha in seal['files'].items():
        if digest(root/name)!=sha:raise ValueError('Snapshot changed '+name)
    for name,sha in seal['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Source changed '+name)
    p=json.loads((root/'protocol.json').read_text(encoding='utf-8'));cutoff=pd.Timestamp(p['cutoff_utc'])
    output=root/'analysis';output.mkdir(exist_ok=False)
    calendar=pd.read_parquet(root/'calendar.parquet');days=list(calendar.day)
    top=pd.read_parquet(root/'oracle-top50.parquet');prices=select_daily_bars(pd.read_parquet(root/'prices.parquet'),config=p['price_config'])
    prices['date']=pd.to_datetime(prices.date);groups={s:g.set_index('date') for s,g in prices.groupby('symbol')}
    snaps=pd.read_parquet(root/'snapshots.parquet');volume=pd.read_parquet(root/'volumes.parquet')
    for frame in (snaps,volume):frame['receipt_day']=pd.to_datetime(frame.available_at,utc=True).dt.tz_convert('America/New_York').dt.date
    decisions=[];parity=0
    for (model,day),g in top.groupby(['model_label','signal_day']):
        decision=g.decision_at.iloc[0];spot=prices[prices.date.eq(day)&prices.is_filled.eq(0)]
        spots={r.symbol:float(r.close) for r in spot.itertuples() if pd.notna(r.close) and r.close>0}
        features=build_features(snaps[snaps.receipt_day.eq(day.date())].copy(),volume[volume.receipt_day.eq(day.date())].copy(),spots,day.date(),decision)
        for rank in RANKS:
            cfg=replace(OptionsFilterConfig(**p['options']),oracle_top_n=rank)
            chosen=select_top(g.to_dict('records'),features,cfg);meta=g.set_index('symbol').to_dict('index')
            for r in chosen:decisions.append({**meta[r['symbol']],**r,'top_n':rank})
    observed=pd.DataFrame(decisions)
    for name in ['volume_score','oi_score','combined_score']:
        if name not in observed:observed[name]=np.nan
    observed.to_parquet(output/'decisions.parquet',index=False);observed.to_csv(output/'decisions.csv',index=False)
    registry=load_security_discontinuities();labels=[]
    # Outcomes constructed only after fixed decisions are exported.
    for r in top.to_dict('records'):
        offset=days.index(r['entry_day']);path=groups.get(r['symbol'])
        for h in HORIZONS:
            window=calendar.iloc[offset:offset+h];exit_day=days[offset+h]
            if len(window)!=h or not window.closed.lt(cutoff).all() or calendar.iloc[offset+h].opened>=cutoff:
                label=dict(trade_status='NOT_MATURE',status='NOT_MATURE')
            elif path is None:label=dict(trade_status='MISSING_PRICES',status='MISSING_PRICES')
            elif any(e.crosses(window.day.iloc[0],exit_day) for e in registry.get(r['symbol'],())):
                label=dict(trade_status='KNOWN_IDENTITY_BREAK',status='KNOWN_IDENTITY_BREAK')
            else:
                label={**trade_label(path,list(window.day),exit_day),**labels_for_path(path,window)}
            labels.append(dict(model_label=r['model_label'],signal_day=r['signal_day'],symbol=r['symbol'],horizon=h,**label))
    panel=observed.merge(pd.DataFrame(labels),on=['model_label','signal_day','symbol'],validate='many_to_many')
    panel.to_parquet(output/'outcomes.parquet',index=False);panel.to_csv(output/'outcomes.csv',index=False)
    reports=[];table=[]
    for (model,rank,h),frame in panel.groupby(['model_label','top_n','horizon']):
        selected=frame[frame.selected];active=selected.signal_day.unique()
        matched=frame[frame.signal_day.isin(active)];covered=matched[matched.combined_score.notna()]
        summary=dict(model=model,top_n=int(rank),horizon=int(h),all_oracle=describe(frame),
            matched_all_oracle=describe(matched),matched_covered=describe(covered),filtered=describe(selected),
            nostop=dict(matched_covered=describe(covered,without_stop=True),filtered=describe(selected,without_stop=True)),
            prospective=dict(all_oracle=describe(frame[frame.physical_oracle]),filtered=describe(selected[selected.physical_oracle])))
        summary['peak_direction']={}
        for name,part in [('matched_all_oracle',matched),('matched_covered',covered),('filtered',selected)]:
            valid=part[part.status.eq('LABEL')]
            summary['peak_direction'][name]=dict(n=len(valid),long_n=int(valid.dominant_direction.eq('LONG').sum()),
                long_share_pct=100*float(valid.dominant_direction.eq('LONG').mean()) if len(valid) else None,
                ambiguous=int(part.status.eq('AMBIGUOUS_PATH').sum()))
        summary['peak_direction']['auc']=auc_metrics(covered)
        # Count only full horizons; deduplicate companies without looking at returns.
        first=frame.sort_values(['signal_day','symbol']).drop_duplicates('symbol')
        summary['first_per_symbol']=dict(all=describe(first),filtered=describe(first[first.selected]))
        daypos={day:i for i,day in enumerate(days)};spaced=[]
        for day in sorted(active):
            if not spaced or daypos[day]-daypos[spaced[-1]]>=int(h)+1:spaced.append(day)
        summary['nonoverlap_dates']=dict(dates=[str(pd.Timestamp(d).date()) for d in spaced],
            covered=describe(covered[covered.signal_day.isin(spaced)]),filtered=describe(selected[selected.signal_day.isin(spaced)]))
        reports.append(summary)
        row=dict(model=model,top_n=int(rank),horizon=int(h))
        for key in ['matched_all_oracle','matched_covered','filtered']:
            for value in ['n','wins','win_rate_pct','symbols','dates','mean_return_pct']:row[key+'_'+value]=summary[key][value]
        a=summary['matched_covered']['win_rate_pct'];b=summary['filtered']['win_rate_pct']
        row['lift_pp']=None if a is None or b is None else b-a;table.append(row)
    pd.DataFrame(table).to_csv(output/'summary.csv',index=False)
    coverage=observed.groupby(['model_label','top_n']).apply(lambda f:pd.Series(dict(candidates=len(f),dates=f.signal_day.nunique(),
        covered=int(f.combined_score.notna().sum()),selected=int(f.selected.sum()),physical_dates=int(f.loc[f.physical_oracle,'signal_day'].nunique()))),include_groups=False)
    coverage.to_csv(output/'coverage.csv')
    report=dict(status='COMPLETED_EXPLORATORY',cutoff_utc=p['cutoff_utc'],results=reports,coverage=coverage.reset_index().to_dict('records'),
        limitations=['Current-year model weights trained through 2025; scores reconstructed November 8, not available at historic entry time',
            'Price-only independent LONG trades, overlapping entries; no shared capital, Winner confirmation, execution quotes, margin or dividends',
            'Current canonical split-adjusted daily bars and present-day tradable universe; not certified full historical PIT',
            'Unsigned option volumes and indicative snapshots, not certified OPRA/NBBO',
            'Selection ranks fixed before outcomes; missing data never filled and no replacement',
            'Few independent dates/companies, repeated tests; no production promotion'],
        provider_calls=0,SQL_writes=0,orders=0,new_inference=False,training=False)
    atomic_json(output/'report.json',report);atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY',report=str(output/'report.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=ROOT)
    p.add_argument('--phase',choices=['inventory','snapshot','analyze'],default='inventory');args=p.parse_args()
    {'inventory':inventory,'snapshot':snapshot,'analyze':analyze}[args.phase](args.output_dir)
