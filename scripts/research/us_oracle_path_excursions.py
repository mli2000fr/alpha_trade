"""Read-only H20 path-vs-terminal amplitude audit; no training, no PnL."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_oracle_amplitude_rerank import HISTORY, EXTERNAL, checked, pool, read
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

LOG=logging.getLogger(__name__)


def candidates():
    parts=[]
    protocol=read(HISTORY/'protocol.json')
    for start in protocol['expected_fold_starts']:
        directory=HISTORY/'corrected'/start
        checked(directory/'predictions.parquet',read(directory/'done.json')['predictions.parquet'])
        parts.append(pd.read_parquet(directory/'predictions.parquet'))
    history=pd.concat(parts,ignore_index=True)
    from scripts.research.us_oracle_numeric_top10 import load_pair
    external=load_pair(EXTERNAL,'external_frozen')[0]['corrected']
    output=[]
    for source,frame in [('historical_oof',history),('external_frozen',external)]:
        frame=frame[frame.date.ge(pd.Timestamp('2020-01-01'))]
        selected=pool(frame)
        checked((HISTORY if source=='historical_oof' else EXTERNAL)/'labels.parquet',
            read((HISTORY if source=='historical_oof' else EXTERNAL)/'labels.json')['sha256'])
        labels=pd.read_parquet((HISTORY if source=='historical_oof' else EXTERNAL)/'labels.parquet',
            columns=['date','symbol','target_quality_valid','oracle_available_date'])
        selected=selected.merge(labels,on=['date','symbol'],how='left',validate='one_to_one')
        selected['source']=source
        selected=selected.sort_values(['date','score','symbol'],ascending=[True,False,True])
        selected['oracle_pool_rank']=selected.groupby('date').cumcount()+1
        atr=selected.sort_values(['date','atr20_pct','symbol'],ascending=[True,False,True])
        atr_rank=atr.assign(atr_pool_rank=atr.groupby('date').cumcount()+1)[['date','symbol','atr_pool_rank']]
        output.append(selected.merge(atr_rank,on=['date','symbol'],validate='one_to_one'))
    return pd.concat(output,ignore_index=True)


def evaluate_symbol(selected,bars,sessions,registry):
    """Exactly J+1..J+20 NYSE sessions, never shift around missing bars."""
    from modelFactory.oracle.security_continuity import path_crosses_known_discontinuity
    bars=bars.copy()
    bars['date']=pd.to_datetime(bars.date)
    if bars.duplicated('date').any():
        raise ValueError('Duplicate symbol bar keys')
    values=bars.set_index('date').reindex(sessions)
    raw=values[['open','high','low','close','adj_close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    adjusted=raw.adj_close.where(raw.adj_close.notna(),raw.close)
    factor=adjusted/raw.close
    closes=adjusted.to_numpy(dtype=float)
    highs=(raw.high*factor).to_numpy(dtype=float)
    lows=(raw.low*factor).to_numpy(dtype=float)
    valid=(np.isfinite(raw[['open','high','low','close']]).all(axis=1)
           & raw[['open','high','low','close']].gt(0).all(axis=1)
           & raw.high.ge(raw[['open','close','low']].max(axis=1))
           & raw.low.le(raw[['open','close','high']].min(axis=1))
           & np.isfinite(factor) & factor.gt(0)
           & raw.is_filled.eq(0) & raw.volume.gt(0)).to_numpy()
    sources=values.data_source.fillna('UNKNOWN').astype(str).to_numpy()
    identities=values.instrument_id.to_numpy()
    adjustments=values.data_adjustment.fillna('UNKNOWN').astype(str).to_numpy()
    output=[]
    for row in selected.to_dict('records'):
        day=pd.Timestamp(row['date'])
        pos=sessions.get_indexer([day])[0]
        flags=[]
        if pos<0 or pos+20>=len(sessions):
            output.append({**row,'path_qualified':False,'path_flags':'OUTSIDE_CALENDAR'})
            continue
        sl=slice(pos,pos+21)
        exit_day=sessions[pos+20]
        if not valid[sl].all(): flags.append('MISSING_FILLED_ZERO_VOLUME_OR_INVALID_OHLC')
        if len(set(sources[sl]))!=1 or sources[pos]=='UNKNOWN': flags.append('SOURCE_CHANGE_OR_UNKNOWN')
        ids=pd.Series(identities[sl])
        if ids.isna().any() or ids.nunique()!=1: flags.append('IDENTITY_CHANGE_OR_UNKNOWN')
        if len(set(adjustments[sl]))!=1 or adjustments[pos]=='UNKNOWN': flags.append('ADJUSTMENT_CHANGE_OR_UNKNOWN')
        if path_crosses_known_discontinuity(row['symbol'],day,exit_day,registry): flags.append('KNOWN_IDENTITY_BREAK')
        baseline=closes[pos]
        price_path=closes[sl]
        ratios=price_path[1:]/price_path[:-1]
        if np.any((ratios>=20)|(ratios<=.05)): flags.append('UNEXPLAINED_20X_PRICE_BREAK')
        if row['target_quality_valid']!=1 or not np.isfinite(row['future_return']): flags.append('UNQUALIFIED_ARCHIVED_LABEL')
        if pd.isna(row['oracle_available_date']) or pd.Timestamp(row['oracle_available_date'])<=exit_day:
            flags.append('LABEL_CALENDAR_MISMATCH')
        terminal=closes[pos+20]/baseline-1 if np.isfinite(baseline) and baseline>0 else np.nan
        if not np.isclose(terminal,row['future_return'],rtol=1e-7,atol=1e-8,equal_nan=False):
            flags.append('ARCHIVED_RETURN_VS_CURRENT_BARS_MISMATCH')
        detail=dict(path_qualified=not flags,path_flags='|'.join(flags),exit_date=exit_day,
            terminal_return=terminal if np.isfinite(terminal) else None,
            large_close_jump_review=bool(np.any(np.abs(ratios-1)>=.5)),
            large_intraday_range_review=bool(np.any(highs[sl]/lows[sl]>=1.5)))
        for name in ['up_excursion','down_excursion','path_amplitude','close_path_amplitude','terminal_abs','roundtrip_loss']:
            detail[name]=None
        for suffix in ['20','50']:
            for prefix in ['path_ge','close_path_ge','terminal_ge','hidden_ge','close_hidden_ge','both_sides_ge']:
                detail[prefix+suffix]=None
        if not flags:
            future=slice(pos+1,pos+21)
            up=highs[future]/baseline-1
            down=lows[future]/baseline-1
            close_path=closes[future]/baseline-1
            amplitude=float(max(0.,up.max(),-down.min()))
            close_amplitude=float(np.abs(close_path).max())
            detail.update(up_excursion=float(max(0.,up.max())),down_excursion=float(max(0.,-down.min())),
                path_amplitude=amplitude,close_path_amplitude=close_amplitude,
                terminal_abs=abs(terminal),roundtrip_loss=amplitude-abs(terminal))
            for threshold,name in [(.2,'20'),(.5,'50')]:
                touch_up=up>=threshold-1e-12
                touch_down=down<=-threshold+1e-12
                hits=np.flatnonzero(touch_up|touch_down)
                detail.update({f'path_ge{name}':amplitude>=threshold-1e-12,
                    f'close_path_ge{name}':close_amplitude>=threshold-1e-12,
                    f'terminal_ge{name}':abs(terminal)>=threshold-1e-12,
                    f'hidden_ge{name}':amplitude>=threshold-1e-12 and abs(terminal)<threshold-1e-12,
                    f'close_hidden_ge{name}':close_amplitude>=threshold-1e-12 and abs(terminal)<threshold-1e-12,
                    f'first_touch_{name}_session':int(hits[0]+1) if len(hits) else None,
                    f'first_touch_{name}_ambiguous':bool(touch_up[hits[0]] and touch_down[hits[0]]) if len(hits) else False,
                    f'both_sides_ge{name}':bool(touch_up.any() and touch_down.any())})
        output.append({**row,**detail})
    return pd.DataFrame(output)


def summarize(frame):
    parts=[]
    for policy,mask in [('POOL',np.ones(len(frame),dtype=bool)),('ORACLE_TOP10',frame.oracle_pool_rank.le(10)),
                        ('ATR_TOP10',frame.atr_pool_rank.le(10))]:
        chosen=frame.loc[mask].copy()
        chosen['year']=pd.to_datetime(chosen.date).dt.year
        for (source,year),group in chosen.groupby(['source','year']):
            valid=group[group.path_qualified]
            result=dict(source=source,year=int(year),policy=policy,selected=len(group),qualified=len(valid),
                coverage=len(valid)/len(group),signal_sessions=group.date.nunique())
            if len(valid):
                for name in ['terminal_abs','path_amplitude','close_path_amplitude','roundtrip_loss']:
                    result['mean_'+name]=float(valid[name].mean())
                for suffix in ['20','50']:
                    for prefix in ['path_ge','close_path_ge','terminal_ge','hidden_ge','close_hidden_ge','both_sides_ge']:
                        # Mixed Python/numpy bool objects can reduce with logical OR
                        # under pandas/numpy. Convert explicitly before arithmetic.
                        result[prefix+suffix]=float(valid[prefix+suffix].astype(float).mean())
                    hidden=valid[valid['path_ge'+suffix]]
                    result['hidden_share_of_reached_'+suffix]=float(hidden['hidden_ge'+suffix].astype(float).mean()) if len(hidden) else None
            parts.append(result)
    return parts


def run(args):
    from sqlalchemy import bindparam,event,text
    from database.connection import get_sqlalchemy_engine
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import DEFAULT_REGISTRY_PATH,load_security_discontinuities
    output=args.output
    output.mkdir(parents=True,exist_ok=True)
    atomic_json(output/'progress.json',dict(status='RUNNING',phase='freeze_candidates'))
    selected=candidates()
    sessions=nyse_sessions(selected.date.min().date(),(selected.date.max()+pd.Timedelta(days=90)).date())
    end=sessions[sessions.get_indexer([selected.date.max()])[0]+20]
    registry=load_security_discontinuities()
    protocol=dict(code_sha256=digest(__file__),helpers_sha256=digest('scripts/research/us_oracle_amplitude_rerank.py'),
        candidate_fingerprint=hashlib.sha256(pd.util.hash_pandas_object(selected,index=False).values.tobytes()).hexdigest(),
        source_protocol_hashes=[digest(p/'protocol.json') for p in (HISTORY,EXTERNAL)],
        registry_sha256=digest(DEFAULT_REGISTRY_PATH),horizon=20,thresholds=[.2,.5],threshold_numerical_tolerance=1e-12,
        signal_start=str(selected.date.min()),signal_end=str(selected.date.max()),price_end=str(end),
        symbols=sorted(selected.symbol.unique()),pool='Frozen Oracle TOP20% intersect ATR TOP20%',
        anchor='adjusted signal-day close',path='J+1..J+20 NYSE sessions, no missing-bar shift or fill',
        intraday_basis='high/low multiplied by adj_close/close per bar; same adjusted close basis as archived label',
        hidden='path reaches threshold while abs(terminal return) remains below threshold',
        main_metrics=['path_ge20','hidden_ge20','close_hidden_ge20','mean_roundtrip_loss'],
        sensitivity='Exclude any path with an adjusted daily high/low ratio >=1.5; exploratory price-review sensitivity, not proof of error',
        price_cache_source=str(args.bars_cache) if args.bars_cache else None,
        price_cache_protocol_sha256=digest(args.bars_cache/'protocol.json') if args.bars_cache else None,
        qualification='complete positive OHLC/volume, unfilled, stable source/adjustment/identity, no known break, endpoint matches archive',
        sql='SELECT only in read-only transactions',training=False,sql_writes=False,serving_modified=False,
        limitations=['Retrospective excursions are not executable profits or directional predictions',
            'Intraday touch ordering unknown with daily OHLC; same-day both-side first touches flagged',
            '2026 already examined; current historical universe and adjusted prices not certified PIT',
            'Second half 2024 missing; archived scores and labels only',
            'High/low conversion shares close adjustment factor; not independent corporate-action certification',
            '50% daily jumps require review, not automatically an error',
            'Missing paths excluded with explicit coverage; survivorship and repeated overlapping windows remain'])
    if (output/'protocol.json').exists() and read(output/'protocol.json')!=protocol:
        raise ValueError('Resume protocol mismatch')
    atomic_json(output/'protocol.json',protocol)
    selected.to_parquet(output/'candidates.parquet',index=False)
    engine=None
    if args.bars_cache:
        prior=read(args.bars_cache/'protocol.json')
        for key in ['candidate_fingerprint','registry_sha256','horizon','thresholds','signal_start','signal_end','price_end','symbols']:
            if prior[key]!=protocol[key]: raise ValueError('Price cache scope mismatch: '+key)
    else:
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        if engine.url.database!='alpha_trade': raise ValueError('US database required')
        event.listen(engine,'begin',lambda conn:conn.exec_driver_sql('SET TRANSACTION READ ONLY'))
    symbols=sorted(selected.symbol.unique())
    groups={symbol:group for symbol,group in selected.groupby('symbol')}
    query=text('''SELECT symbol,`date`,CAST(`open` AS DOUBLE) AS `open`,CAST(high AS DOUBLE) AS high,
        CAST(low AS DOUBLE) AS low,CAST(`close` AS DOUBLE) AS `close`,CAST(adj_close AS DOUBLE) AS adj_close,
        volume,is_filled,instrument_id,data_source,data_adjustment
        FROM stock_bars_daily WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end
        ORDER BY symbol,`date`''').bindparams(bindparam('symbols',expanding=True))
    total=int(np.ceil(len(symbols)/25))
    all_paths=[]
    for chunk in range(total):
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='read_and_audit_paths',completed=chunk,total=total))
        names=symbols[chunk*25:(chunk+1)*25]
        directory=output/f'chunk-{chunk:03}'
        directory.mkdir(exist_ok=True)
        marker=directory/'done.json'
        if marker.exists():
            for name,sha in read(marker).items(): checked(directory/name,sha)
            paths=pd.read_parquet(directory/'paths.parquet')
        else:
            if args.bars_cache:
                cache=args.bars_cache/directory.name
                checked(cache/'bars.parquet',read(cache/'done.json')['bars.parquet'])
                bars=pd.read_parquet(cache/'bars.parquet')
                if not set(bars.symbol).issubset(names): raise ValueError('Cache chunk symbols mismatch')
            else:
                with engine.connect() as conn:
                    bars=pd.read_sql(query,conn,params=dict(symbols=names,start=selected.date.min().date(),end=end.date()))
            bars.to_parquet(directory/'bars.parquet',index=False)
            by_symbol={symbol:part for symbol,part in bars.groupby('symbol')}
            evaluated=[]
            for symbol in names:
                symbol_bars=by_symbol.get(symbol,bars.iloc[:0])
                evaluated.append(evaluate_symbol(groups[symbol],symbol_bars,sessions,registry))
            paths=pd.concat(evaluated,ignore_index=True)
            paths.to_parquet(directory/'paths.parquet',index=False)
            atomic_json(marker,{name:digest(directory/name) for name in ['bars.parquet','paths.parquet']})
        all_paths.append(paths)
        LOG.info('Chunk %d/%d symbols=%d paths=%d qualified=%d',chunk+1,total,len(names),len(paths),paths.path_qualified.sum())
    if engine is not None: engine.dispose()
    frame=pd.concat(all_paths,ignore_index=True)
    frame.to_parquet(output/'paths.parquet',index=False)
    annual=summarize(frame)
    pd.DataFrame(annual).to_parquet(output/'annual.parquet',index=False)
    sensitivity_frame=frame.copy()
    sensitivity_frame['path_qualified'] &= ~frame.large_intraday_range_review
    sensitivity=summarize(sensitivity_frame)
    pd.DataFrame(sensitivity).to_parquet(output/'annual_range_sensitivity.parquet',index=False)
    reserved=frame[~frame.path_qualified]
    reasons=reserved.path_flags.str.split('|').explode().value_counts().to_dict()
    qualified=frame[frame.path_qualified]
    examples=qualified[qualified.hidden_ge20.eq(True)].sort_values('roundtrip_loss',ascending=False).head(50)
    examples.to_parquet(output/'hidden_examples.parquet',index=False)
    flags=qualified[qualified.large_close_jump_review.eq(True)]
    flags.to_parquet(output/'large_jump_review.parquet',index=False)
    intraday=qualified[qualified.large_intraday_range_review.eq(True)]
    intraday.to_parquet(output/'intraday_range_review.parquet',index=False)
    atomic_json(output/'report.json',dict(status='COMPLETED_READ_ONLY_PATH_AUDIT',
        candidates=len(frame),qualified=len(qualified),reserved=len(reserved),reserved_reasons=reasons,
        large_close_jump_review=len(flags),large_intraday_range_review=len(intraday),annual=annual,
        sensitivity_excluding_intraday_range_ge50pct=sensitivity,
        price_cache_source=str(args.bars_cache) if args.bars_cache else None,sql_writes=False,training=False,
        limitations=protocol['limitations']))
    atomic_json(output/'progress.json',dict(status='COMPLETED',completed=total,total=total))
    LOG.info('Path audit complete %s qualified=%d/%d',output,len(qualified),len(frame))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bars-cache',type=Path,help='Verified immutable prior price snapshot; no SQL reads')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try: run(args)
    except Exception as exc:
        if args.output.exists(): atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__=='__main__': main()
