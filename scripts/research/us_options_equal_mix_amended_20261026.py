"""Pre-outcome amendment: prospective 30Min options, source-separated prices."""
from datetime import date
from pathlib import Path
import argparse
import re
import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam
from scripts.research import us_options_equal_mix_20261026 as b

ROOT=Path('artifacts/research/us_options_equal_mix/20261026-v2')
AMENDMENT=Path('doc/ml/options_volume_oi_amendement_20261026.md')


def snapshot(output):
    output.mkdir(parents=True,exist_ok=False)
    cutoff=pd.Timestamp.now(tz='UTC');cal=b.calendar(cutoff)
    last=cal.loc[cal.closed.lt(cutoff),'day'].max()
    symbols=sorted(set(s.upper() for s in re.split(r'[,;\s]+',b.UNIVERSE.read_text(encoding='utf-8-sig')) if s))
    sources={str(p):b.digest(p) for p in [Path(__file__),Path(b.__file__),b.TEST,b.DOC,b.UNIVERSE,AMENDMENT,
        Path('service/forward_pit/options_delayed.py'),
        Path('scripts/research/fr_p0_p1_directional_audit_20261026.py')]}
    protocol=dict(cutoff=cutoff,last_closed_session=last,sources=sources,symbols=symbols,
        universe_count=len(symbols),weights=dict(volume=.5,open_interest=.5),primary_horizon=20,
        secondary_horizons=[5,10],stop_loss_pct=.10,training=False,weight_search=False,
        source_separation=['eodhd_eod primary','alpaca_sip secondary'],volume_timeframe='30Min',
        SQL='alpha_trade READ ONLY REPEATABLE READ rollback',provider_calls=0,LLM_calls=0,
        production_changes=False,independent_holdout=False,amended_before_any_outcome=True)
    b.write(output/'protocol.json',protocol);cal.to_parquet(output/'calendar.parquet',index=False)
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':raise ValueError('Wrong database')
    params=dict(symbols=symbols,start='2026-09-10',end=str((last+pd.Timedelta(days=1)).date()),
        cutoff=cutoff.tz_localize(None).to_pydatetime())
    queries={
        'snapshots':'''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,
            option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,provider,feed
            FROM stock_option_snapshots WHERE provider='alpaca' AND feed='indicative'
            AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
            AND available_at<=:cutoff AND observed_at<=:cutoff''',
        'volumes':'''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
            bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,provenance_status,timeframe
            FROM stock_option_bars_delayed WHERE provider='alpaca' AND timeframe='30Min'
            AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
            AND bar_timestamp>=:start AND bar_timestamp<:end AND available_at<=:cutoff AND observed_at<=:cutoff''',
        'prices':'''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,data_adjustment,
            instrument_id,ingested_at,last_updated FROM stock_bars_daily WHERE symbol IN :symbols
            AND date>=:start AND date<:end AND data_adjustment='split'
            AND data_source IN ('eodhd_eod','alpaca_sip')'''}
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
            conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':raise ValueError('Wrong schema')
            for name,sql in queries.items():
                print('Reading '+name,flush=True)
                frame=pd.DataFrame([dict(r) for r in conn.execute(text(sql).bindparams(
                    bindparam('symbols',expanding=True)),params).mappings()])
                frame.to_parquet(output/(name+'.parquet'),index=False)
                print(name+' rows='+str(len(frame)),flush=True)
            conn.rollback()
    finally:engine.dispose()
    files=['protocol.json','calendar.parquet','snapshots.parquet','volumes.parquet','prices.parquet']
    b.write(output/'snapshot-seal.json',dict(files={n:b.digest(output/n) for n in files}))


def make_labels(scored,prices,cal,cutoff,source):
    if not prices.data_source.eq(source).all():raise ValueError('Mixed source path')
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate price')
    prices=prices.copy();prices['date']=pd.to_datetime(prices.date)
    cols=['open','high','low','close','volume']
    for col in cols:prices[col]=pd.to_numeric(prices[col],errors='coerce')
    prices['valid']=(np.isfinite(prices[cols].to_numpy(float)).all(axis=1)&prices[cols].gt(0).all(axis=1)
        &prices.is_filled.eq(0)&prices.instrument_id.notna()&prices.data_adjustment.eq('split')
        &prices.high.ge(prices[['open','close']].max(axis=1))&prices.low.le(prices[['open','close']].min(axis=1)))
    groups={s:g.set_index('date') for s,g in prices.groupby('symbol')};days=list(cal.day);rows=[]
    for r in scored.to_dict('records'):
        i=days.index(pd.Timestamp(r['entry_day']))
        for h in [5,10,20]:
            record={**r,'horizon':h};window=cal.iloc[i:i+h]
            if len(window)<h or not window.closed.lt(cutoff).all():
                rows.append({**record,'status':'NOT_MATURE'});continue
            path=groups.get(r['symbol'])
            if path is None:rows.append({**record,'status':'MISSING_PRICES'});continue
            path=path.reindex(window.day)
            if not path.valid.eq(True).all() or path.instrument_id.nunique()!=1:
                rows.append({**record,'status':'INVALID_OR_INCOMPLETE_PRICE_IDENTITY'});continue
            bars=[dict(date=str(d.date()),open=p.open,high=p.high,low=p.low,close=p.close) for d,p in path.iterrows()]
            long,short=b.protected_excursion(bars,'LONG'),b.protected_excursion(bars,'SHORT')
            direction,first=b.compare_paths(long,short)
            record.update(status='LABEL' if direction!='AMBIGUOUS_OR_TIE' else 'AMBIGUOUS_PATH',
                dominant_direction=direction,first_peak=first)
            record.update({'long_'+k:v for k,v in long.items()});record.update({'short_'+k:v for k,v in short.items()})
            rows.append(record)
    return pd.DataFrame(rows,columns=None if rows else b.KEY+b.SCORES+['horizon','status','dominant_direction'])


def analyze(output):
    if (output/'report.json').exists():raise FileExistsError('Immutable report')
    seal=b.read(output/'snapshot-seal.json');protocol=b.read(output/'protocol.json')
    for n,sha in seal['files'].items():
        if Path(n).name!=n or b.digest(output/n)!=sha:raise ValueError('Snapshot changed')
    for p,sha in protocol['sources'].items():
        if b.digest(p)!=sha:raise ValueError('Source changed '+p)
    cal=pd.read_parquet(output/'calendar.parquet');cutoff=pd.Timestamp(protocol['cutoff'])
    inputs={n:pd.read_parquet(output/(n+'.parquet')) for n in ['snapshots','volumes','prices']}
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',sources={},
        source_rows={n:len(f) for n,f in inputs.items()},primary_price_source='eodhd_eod',
        no_economic_backtest=True,independent_holdout=False,no_training=True)
    for source in ['eodhd_eod','alpaca_sip']:
        print('Analyze '+source,flush=True)
        root=output/source;root.mkdir(exist_ok=False)
        prices=inputs['prices'][inputs['prices'].data_source.eq(source)].copy()
        features,audit=b.build_features(inputs['snapshots'],inputs['volumes'],prices,cal)
        features.to_parquet(root/'features.parquet',index=False)
        scored=b.score_candidates(features);scored.to_parquet(root/'asof-scores.parquet',index=False)
        labels=make_labels(scored,prices,cal,cutoff,source)
        labels.to_parquet(root/'protected-paths.parquet',index=False)
        horizons={}
        for h in [5,10,20]:
            f=labels[labels.horizon.eq(h)]
            selected=b.spaced_dates(scored.entry_day,h,cal)
            first=scored.sort_values(b.KEY).drop_duplicates('symbol')[b.KEY]
            days=sorted(scored.entry_day.unique());mid=len(days)//2
            daily=b.metrics(f)['daily']
            horizons[str(h)]=dict(all=b.metrics(f),nonoverlap_entry_dates=selected,
                nonoverlap=b.metrics(f[f.entry_day.isin(selected)]),
                first_per_symbol=b.metrics(f.merge(first,on=b.KEY,validate='one_to_one')),
                original_observation_window=b.metrics(f[f.entry_day.le('2026-10-12')]),
                extension_observation_window=b.metrics(f[f.entry_day.gt('2026-10-12')]),
                first_half=b.metrics(f[f.entry_day.isin(days[:mid])]),second_half=b.metrics(f[f.entry_day.isin(days[mid:])]),
                leave_one_date_out=[dict(excluded=r['day'],delta_vs_volume=float(np.mean([
                    x['delta_vs_volume'] for x in daily if x['day']!=r['day']]))) for r in daily] if len(daily)>1 else [])
        report['sources'][source]=dict(feature_audit=audit,scores=len(scored),symbols=int(scored.symbol.nunique()),
            first_price=str(prices.date.min()),last_price=str(prices.date.max()),horizons=horizons)
        b.write(root/'report.json',report['sources'][source])
        print(source+' scores='+str(len(scored)),flush=True)
    b.write(output/'report.json',report)
    b.write(output/'seal.json',dict(files={str(p.relative_to(output)):b.digest(p) for p in output.rglob('*')
        if p.is_file() and p.name!='seal.json'},sources=protocol['sources']))
    print('COMPLETED_EXPLORATORY_NO_PROMOTION',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=['snapshot','analyze'])
    parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args();(snapshot if args.phase=='snapshot' else analyze)(args.output)
