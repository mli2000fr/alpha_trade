"""Fixed, no-fit options audit on Oracle TOP10% and Q051 retained TOP5 LONG."""
from pathlib import Path
from types import SimpleNamespace
import json
from unittest.mock import patch
import numpy as np
import pandas as pd
import requests
from sklearn.metrics import roc_auc_score
from scripts.research.us_options_q051_top_fraction_audit_20261115 import ROOT,BATCH,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.options_asof_rows_20261115 import build_features_asof


def outcome(path,window,exit_day,cutoff):
    g=path.reindex(window.day);numeric=g[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    valid=(np.isfinite(numeric.to_numpy(float)).all(axis=1)&numeric[['open','high','low','close']].gt(0).all(axis=1)
        &numeric.volume.ge(0)&g.is_filled.eq(0)&g.instrument_id.notna()&g.data_adjustment.eq('split')
        &numeric.high.ge(numeric[['open','close']].max(axis=1))&numeric.low.le(numeric[['open','close']].min(axis=1)))
    if not window.closed.lt(cutoff).all():return dict(path_status='NOT_MATURE',trade_status='NOT_MATURE')
    if not valid.all() or g.instrument_id.nunique()!=1:return dict(path_status='INVALID_OR_MISSING_PRICE_IDENTITY',trade_status='INVALID_OR_MISSING_PRICE_IDENTITY')
    entry=float(numeric.iloc[0].open);up=max(0.,float(numeric.high.max()/entry-1));down=max(0.,float(1-numeric.low.min()/entry))
    direction='LONG' if up>down+1e-12 else 'SHORT' if down>up+1e-12 else 'TIE'
    result=dict(path_status='LABEL' if direction!='TIE' else 'TIE',dominant_direction=direction,
        max_up_pct=100*up,max_down_pct=100*down,terminal_return_pct=100*(numeric.iloc[-1].close/entry-1),entry_price=entry)
    if exit_day.opened>=cutoff:return result|dict(trade_status='NOT_MATURE')
    stop=round(entry*.95,2);price=None;reason=None
    for _,bar in numeric.iterrows():
        if bar.open<=stop:price=float(bar.open);reason='STOP_GAP';break
        if bar.low<=stop:price=stop;reason='STOP';break
    if price is None:
        if exit_day.day not in path.index:return result|dict(trade_status='MISSING_EXIT_OPEN')
        r=path.loc[exit_day.day]
        if pd.isna(r.open) or r.open<=0 or r.is_filled or pd.isna(r.instrument_id) or r.instrument_id!=g.instrument_id.iloc[0]:
            return result|dict(trade_status='INVALID_EXIT_OPEN')
        price=float(r.open);reason='HORIZON_OPEN'
    net=100*(price-entry-.0008*entry-.0008*price)/entry
    return result|dict(trade_status='VALID',exit_reason=reason,net_return_pct=net,winning=net>0)


def describe(frame):
    path=frame[frame.path_status.eq('LABEL')];trades=frame[frame.trade_status.eq('VALID')]
    return dict(candidates=len(frame),symbols=int(frame.symbol.nunique()),dates=int(frame.signal_day.nunique()),
        direction_n=len(path),direction_dates=int(path.signal_day.nunique()),direction_symbols=int(path.symbol.nunique()),
        long_n=int(path.dominant_direction.eq('LONG').sum()),long_share_pct=100*float(path.dominant_direction.eq('LONG').mean()) if len(path) else None,
        trade_n=len(trades),trade_dates=int(trades.signal_day.nunique()),trade_symbols=int(trades.symbol.nunique()),
        wins=int(trades.winning.sum()) if len(trades) else 0,win_rate_pct=100*float(trades.winning.mean()) if len(trades) else None,
        mean_net_return_pct=float(trades.net_return_pct.mean()) if len(trades) else None)


def aucs(frame):
    f=frame[frame.path_status.eq('LABEL')&frame.combined_score.notna()];result={}
    for score in ['volume_score','oi_score','combined_score']:
        daily=[float(roc_auc_score(g.dominant_direction.eq('LONG'),g[score])) for _,g in f.groupby('signal_day') if g.dominant_direction.nunique()==2]
        result[score]=dict(pooled_auc=float(roc_auc_score(f.dominant_direction.eq('LONG'),f[score])) if f.dominant_direction.nunique()==2 else None,
            mean_daily_auc=float(np.mean(daily)) if daily else None,informative_dates=len(daily),n=len(f))
    return result


def run(root=ROOT):
    from common.daily_bar_sources import select_daily_bars
    from service.options_directional.features import build_features,select_top
    from service.options_directional.runner import validate_oracle_lineage
    from modelFactory.oracle_path.directional import load_manifest
    from modelFactory.oracle.security_continuity import load_security_discontinuities,path_crosses_known_discontinuity
    from backtesting.per_symbol_selection import attach_calibration_auc,select_per_symbol,PerSymbolSelection
    from backtesting.isolation import ReadOnlyReplay
    root=Path(root);out=root/'analysis-v2';out.mkdir(exist_ok=False)
    protocol=read(root/'protocol.json');seal=read(root/'snapshot-seal.json');cutoff=pd.Timestamp(protocol['cutoff_utc'])
    for name,sha in seal['files'].items():
        if digest(root/name)!=sha:raise ValueError('Changed snapshot: '+name)
    for name,sha in seal['models'].items():
        if digest(Path(name))!=sha:raise ValueError('Changed model contract')
    atomic_json(out/'protocol.json',dict(snapshot_sha256=digest(root/'snapshot-seal.json'),
        score='native 50/50 relative volume/OI in common Oracle TOP179, min4 covered, upper half and score>.5',
        stages=['ORACLE_TOP10PCT','PER_SYMBOL_TOP5_RETAINED'],time_modes=['STRICT_NATIVE','ASOF_72H'],
        asof='unchanged observed/available clocks, volume bar session J; receipts <= decision and no older than72h',
        SL5_trade='independent daily LONGs, native rounded stop, fees8bps/leg, open6/open11; not shared-capital Winner replay',
        no_fit=True,no_threshold_search=True,no_production_change=True,
        sources={str(p):digest(p) for p in [Path(__file__),Path('scripts/research/options_asof_rows_20261115.py'),
            Path('service/options_directional/features.py'),Path('common/options_directional_contract.py')]}))
    model=Path(protocol['model_root']);manifest,mhash=load_manifest(model)
    raw=pd.read_parquet(root/'oracle-raw.parquet');raw['date']=pd.to_datetime(raw.date)
    models={(r['symbol'],r['year'],r['side']):r for r in manifest['models']}
    if not raw.manifest_sha256.eq(mhash).all():raise ValueError('Directional manifest mismatch')
    for side in ['long','short']:
        for r in raw[raw[side+'_probability'].notna()].itertuples():
            m=models.get((r.symbol,r.date.year,side));p=getattr(r,side+'_probability')
            if m is None or getattr(r,side+'_model_sha256')!=m['sha256'] or pd.Timestamp(m['available'])>=r.date or not 0<=p<=1:
                raise ValueError('Noncausal/mismatched directional model')
    calendar=pd.read_parquet(root/'calendar.parquet');days=list(calendar.day);universe=protocol['symbols'];n_universe=len(universe)
    coverage=[];qualified=[]
    for day,g in raw[raw.symbol.isin(universe)].groupby('date'):
        ok=len(g)>=int(np.ceil(n_universe*protocol['oracle_coverage_ratio']))
        if g.symbol.duplicated().any():raise ValueError('Duplicate Oracle key')
        coverage.append(dict(signal_day=day,scores=len(g),universe=n_universe,ratio=len(g)/n_universe,qualified=ok))
        if not ok:continue
        validate_oracle_lineage(g.to_dict('records'),day.date(),protocol['feature_profile_sha256'],protocol['folds'],horizon=10)
        entry=calendar.iloc[days.index(day)+1];decision=min(entry.opened-pd.Timedelta(minutes=5),cutoff)
        g=g.copy();g['signal_day']=day;g['entry_day']=entry.day;g['decision_at']=decision
        g['physical_ranking']=bool((pd.to_datetime(g.prediction_created_at,utc=True).le(decision)&pd.to_datetime(g.lineage_created_at,utc=True).le(decision)).all())
        g['physical_directional']=bool(pd.to_datetime(g.directional_created_at,utc=True).le(decision).all())
        qualified.append(g)
    pd.DataFrame(coverage).to_csv(out/'oracle-coverage.csv',index=False)
    if not qualified:raise ValueError('No qualified Oracle dates')
    ranked=select_per_symbol(attach_calibration_auc(pd.concat(qualified,ignore_index=True),model),
        PerSymbolSelection(oracle_top_n=179,long_top_n=5,allow_short=False,min_long_probability=.5,min_long_auc=.5))
    pool=ranked[ranked.oracle_rank.le(179)].rename(columns={'selected':'per_symbol_selected'}).copy()
    pool.to_parquet(out/'oracle-pool-before-options.parquet',index=False)
    prices=select_daily_bars(pd.read_parquet(root/'prices.parquet'),config=protocol['daily_price_config'])
    for column in ['open','high','low','close','volume']:
        prices[column]=pd.to_numeric(prices[column],errors='coerce').astype(float)
    prices['date']=pd.to_datetime(prices.date);price_groups={s:g.set_index('date').sort_index() for s,g in prices.groupby('symbol')}
    frames={}
    for name in ['snapshots','volumes']:
        parts=[pd.read_parquet(p) for p in sorted((root/'raw'/name).glob('*.parquet'))]
        parts=[p for p in parts if len(p)];f=pd.concat(parts,ignore_index=True)
        for c in ['observed_at','available_at','provider_timestamp','bar_timestamp']:
            if c in f:f[c]=pd.to_datetime(f[c],utc=True,errors='coerce')
        f['receipt']=f[['observed_at','available_at']].max(axis=1);frames[name]=f
    if not len(frames['snapshots']) or not len(frames['volumes']):raise ValueError('No archived option inputs')
    latest=pd.Timestamp(protocol['last_price_date']);features=[];daily_coverage=[];decisions=[]
    cfg=SimpleNamespace(oracle_top_n=179,min_covered=4,min_combined_score=.5)
    def no_http(*args,**kwargs):raise ValueError('HTTP forbidden in offline options audit')
    with ReadOnlyReplay(out).install(),patch.object(requests.Session,'request',no_http):
        for i,row in calendar[calendar.day.le(latest)].iterrows():
            day=row.day;entry=calendar.iloc[days.index(day)+1];decision=min(entry.opened-pd.Timedelta(minutes=5),cutoff)
            spots=prices[prices.date.eq(day)&prices.is_filled.eq(0)&prices.close.gt(0)].set_index('symbol').close.to_dict()
            subsets={k:f[f.receipt.between(decision-pd.Timedelta(hours=96),decision)] for k,f in frames.items()}
            for mode,builder in [('STRICT_NATIVE',build_features),('ASOF_72H',build_features_asof)]:
                values=builder(subsets['snapshots'],subsets['volumes'],spots,day.date(),decision)
                daily_coverage.append(dict(mode=mode,signal_day=day,decision_at=decision,universe=n_universe,
                    spot_covered=len(spots),qualified_combined=len(values),coverage_pct=100*len(values)/n_universe))
                features.extend(dict(mode=mode,signal_day=day,symbol=s,**v) for s,v in values.items())
                g=pool[pool.signal_day.eq(day)]
                if g.empty:continue
                rows=select_top(g.to_dict('records'),values,cfg)
                for r in rows:
                    r['options_selected']=r.pop('selected');r['options_reason']=r.pop('reason')
                    decisions.append(dict(mode=mode,signal_day=day,**r))
            atomic_json(out/'progress.json',dict(status='QUALIFYING_OPTIONS_AND_FREEZING_SELECTIONS',completed=i+1,total=int(calendar.day.le(latest).sum()),last_day=str(day.date())))
        pd.DataFrame(features).to_parquet(out/'features.parquet',index=False)
        pd.DataFrame(daily_coverage).to_csv(out/'universe-daily-coverage.csv',index=False)
        d=pd.DataFrame(decisions)
        for c in ['volume_score','oi_score','combined_score']:
            if c not in d:d[c]=np.nan
        d=d.merge(pool[['signal_day','symbol','per_symbol_selected','long_rank','long_probability','long_auc',
                       'physical_ranking','physical_directional','entry_day','decision_at']],on=['signal_day','symbol'],validate='many_to_one')
        d.to_parquet(out/'decisions-before-outcomes.parquet',index=False)
        # Outcomes are read only after candidates and options selection are fixed.
        records=[];breaks=load_security_discontinuities()
        for r in pool[['signal_day','symbol','entry_day']].drop_duplicates().itertuples():
            offset=days.index(r.entry_day);path=price_groups.get(r.symbol)
            for h in [5,10]:
                window=calendar.iloc[offset:offset+h];exit_day=calendar.iloc[offset+h]
                if path is None:label=dict(path_status='MISSING_PRICES',trade_status='MISSING_PRICES')
                elif path_crosses_known_discontinuity(r.symbol,r.entry_day,exit_day.day,breaks):label=dict(path_status='IDENTITY_BREAK',trade_status='IDENTITY_BREAK')
                else:label=outcome(path,window,exit_day,cutoff)
                records.append(dict(signal_day=r.signal_day,symbol=r.symbol,horizon=h,**label))
        panel=d.merge(pd.DataFrame(records),on=['signal_day','symbol'],validate='many_to_many')
        panel.to_parquet(out/'outcomes.parquet',index=False);summaries=[];table=[]
        for (mode,h),allrows in panel.groupby(['mode','horizon']):
            for stage,f in [('ORACLE_TOP10PCT',allrows),('PER_SYMBOL_TOP5_RETAINED',allrows[allrows.per_symbol_selected])]:
                covered=f[f.combined_score.notna()];selected=f[f.options_selected]
                active=selected.signal_day.unique();matched=covered[covered.signal_day.isin(active)]
                positions={day:i for i,day in enumerate(days)};spaced=[]
                for day in sorted(covered.signal_day.unique()):
                    if not spaced or positions[day]-positions[spaced[-1]]>=h:spaced.append(day)
                first=covered.sort_values(['signal_day','symbol']).drop_duplicates('symbol')
                summary=dict(mode=mode,stage=stage,horizon=int(h),all_stage=describe(f),covered=describe(covered),
                    matched_covered=describe(matched),selected=describe(selected),auc=aucs(covered),
                    non_overlap_dates=dict(dates=[str(pd.Timestamp(t).date()) for t in spaced],
                        covered=describe(covered[covered.signal_day.isin(spaced)]),selected=describe(selected[selected.signal_day.isin(spaced)])),
                    first_per_symbol=dict(covered=describe(first),selected=describe(first[first.options_selected])),
                    prospective_selected=describe(selected[selected.physical_ranking&selected.physical_directional]))
                summaries.append(summary)
                flat=dict(mode=mode,stage=stage,horizon=int(h))
                for k in ['all_stage','covered','matched_covered','selected']:
                    for c in ['candidates','direction_n','long_share_pct','trade_n','win_rate_pct','symbols','dates','mean_net_return_pct']:
                        flat[k+'_'+c]=summary[k][c]
                flat.update(combined_auc=summary['auc']['combined_score']['pooled_auc'],
                    combined_mean_daily_auc=summary['auc']['combined_score']['mean_daily_auc'],
                    volume_auc=summary['auc']['volume_score']['pooled_auc'],oi_auc=summary['auc']['oi_score']['pooled_auc'])
                table.append(flat)
        pd.DataFrame(table).to_csv(out/'summary.csv',index=False)
        coverage=pd.DataFrame(daily_coverage);coverage_summary=[]
        feature_frame=pd.DataFrame(features)
        for mode,g in coverage.groupby('mode'):
            fg=feature_frame[feature_frame['mode'].eq(mode)] if len(feature_frame) else feature_frame
            coverage_summary.append(dict(mode=mode,universe=n_universe,signal_days=len(g),
                first=str(g.signal_day.min().date()),last=str(g.signal_day.max().date()),
                ever_qualified_symbols=int(fg.symbol.nunique()) if len(fg) else 0,
                ever_qualified_pct=100*fg.symbol.nunique()/n_universe if len(fg) else 0,
                mean_daily_qualified=float(g.qualified_combined.mean()),mean_daily_coverage_pct=float(g.coverage_pct.mean()),
                latest=g.iloc[-1].to_dict()))
        final=dict(status='COMPLETED_EXPLORATORY',coverage=coverage_summary,results=summaries,
            model=BATCH,qualified_model_dates=int(pool.signal_day.nunique()),oracle_pool_rows=len(pool),
            per_symbol_signals=int(pool.per_symbol_selected.sum()),
            production_issue='Native row reader equates receipt NY day to bar/session day; next-midnight collections rejected despite availability before next open',
            limitations=['ASOF_72H is a research-only time qualification, not a deployed filter; original clocks unchanged.',
                'Retrospectively saved Oracle/per-symbol scores; causal annual weights, not certified prospective trading results.',
                'Few dates with highly overlapping H5/H10 windows and repeated symbols; pooled row counts overstate independence.',
                'Unsigned CALL/PUT activity and indicative OI are relative signals, not calibrated direction probabilities.',
                'Current tradable universe and revised historical prices, no full historical PIT certification.',
                'Independent SL5 daily labels, no shared portfolio capital, Winner confirmation, margin or dividends.'],
            SQL_writes=0,provider_calls=0,orders=0,training=False,new_inference=False,production_changes=False)
        atomic_json(out/'report.json',final)
        atomic_json(out/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    return final


if __name__=='__main__':
    r=run();print(json.dumps(dict(status=r['status'],coverage=r['coverage'],dates=r['qualified_model_dates'],per_symbol_signals=r['per_symbol_signals']),default=str,ensure_ascii=False),flush=True)
