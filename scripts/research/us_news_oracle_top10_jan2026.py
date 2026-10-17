"""Frozen January 2026 Oracle TOP10 / cached GPT evidence, no paid calls.

Prepare: bounded SELECT-only cache validation. Run: local daily-path description,
TP20 versus SL10, not a funded portfolio or proof of historical deployability.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine,text,bindparam

from service.llm_directional.news_cache import sha,request_identity
from service.llm_directional.stored_news import parse
from modelFactory.oracle.security_continuity import DEFAULT_REGISTRY_PATH,load_security_discontinuities,path_crosses_known_discontinuity
from scripts.research import us_news_event_qualification as evidence

SOURCE=Path('artifacts/research/us_news_gpt_top20_history/20261015-v1')
MONTH='2026-01'
BATCH='model-factory-20261014113232-bc35a7'
FOLD='2025-12-10'
TOP=10
GROUPS=('BULLISH','BEARISH','ABSTAIN','UNKNOWN_NO_QUALIFIED_TEXT','UNKNOWN_INVALID_RESPONSE')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def check_files(root,files):
    for name,digest in files.items():
        path=root/name
        if path.resolve().is_relative_to(root.resolve()) is False or evidence.sha(path)!=digest:
            raise ValueError('Changed or out-of-scope source: '+name)


def select_top(frame,days,model):
    frame=frame.copy()
    frame['date']=pd.to_datetime(frame.date).dt.normalize()
    if frame.duplicated(['date','symbol']).any() or set(frame.date.dt.strftime('%Y-%m-%d'))!=set(days):
        raise ValueError('Duplicate or missing sessions')
    if not frame.groupby('date').size().eq(20).all():raise ValueError('Frozen TOP20 required')
    if not np.isfinite(frame.score).all() or not frame.score.between(0,1).all():raise ValueError('Invalid scores')
    if frame[['future_return','oracle_extreme10']].notna().any().any():raise ValueError('Future labels in selection')
    if not frame.fold_start.astype(str).str.startswith(FOLD).all() or not frame.lineage_fold.astype(str).str.startswith(FOLD).all():
        raise ValueError('Wrong annual fold')
    if not frame.model_sha256.eq(model['model_sha256']).all() or not frame.feature_profile_sha256.eq(model['profile_sha256']).all():
        raise ValueError('Wrong model lineage')
    if not frame.target_name.eq('oracle_path_extreme20').all() or not frame.target_horizon.eq(20).all():
        raise ValueError('Wrong target')
    if not pd.to_datetime(frame.model_available_date).lt('2026-01-01').all():raise ValueError('Future annual model')
    ordered=frame.sort_values(['date','score','symbol'],ascending=[True,False,True])
    if not ordered.oracle_rank.eq(ordered.groupby('date').cumcount()+1).all():raise ValueError('Rank order changed')
    return ordered[ordered.oracle_rank.le(TOP)].copy()


def prepare(output):
    if output.exists():raise FileExistsError('Fresh immutable output required')
    protocol=read(SOURCE/'protocol.json');source_report=read(SOURCE/'report.json')
    if source_report['status']!='COMPLETED' or source_report['unresolved']!=0:raise ValueError('Complete campaign required')
    folder=SOURCE/'months'/MONTH
    prepared=read(folder/'prepared.json');completed=read(folder/'completed.json')
    check_files(folder,prepared['files']);check_files(folder,completed['files'])
    model=protocol['annual_models']['2026']
    if model['batch_id']!=BATCH or model['fold']!=FOLD or model['available_date']>='2026-01-01':
        raise ValueError('Wrong causal model')
    model_root=Path('artifacts/models')/BATCH/'oracle_path'
    weight=model_root/'folds'/FOLD/'catboost_model.cbm'
    if evidence.sha(weight)!=model['model_sha256'] or evidence.sha(model_root/'feature_profile.json')!=model['profile_sha256']:
        raise ValueError('Model artifact mismatch')
    done=read(model_root/'folds'/FOLD/'done.json')
    if any(pd.Timestamp(done['metrics'][key])>=pd.Timestamp('2026-01-01') for key in ('train_available_max','val_available_max')):
        raise ValueError('Training/validation labels reach test year')
    days=[d for d in protocol['sessions'] if d.startswith(MONTH)]
    top=select_top(pd.read_parquet(folder/'candidates.parquet'),days,model)
    packets=read(folder/'packets.json')
    packet_map={(r['decision_date'],r['symbol']):r for r in packets}
    local=[read(folder/name) for name in completed['files']]
    local_map={(r['decision_date'],r['symbol']):r for r in local}
    from database.connection import get_sqlalchemy_engine
    engine=create_engine(get_sqlalchemy_engine().url,pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    cache={};snapshots={}
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':raise ValueError('US database required')
            for suffix in ('prepared','completed'):
                ident=sha('us-news-top20-history-20261015-v1:'+MONTH+':'+suffix)
                row=conn.execute(text('SELECT snapshot_json,snapshot_sha256,imported_at FROM llm_news_analysis_research_runs WHERE import_id=:id'),{'id':ident}).mappings().one()
                value=json.loads(row['snapshot_json'])
                if sha(value)!=row['snapshot_sha256']:raise ValueError('SQL snapshot changed')
                snapshots[suffix]=dict(import_id=ident,snapshot_sha256=row['snapshot_sha256'],imported_at=row['imported_at'],value=value)
            frozen=snapshots['prepared']['value'];sealed=snapshots['completed']['value']
            if frozen['protocol']!=protocol or sealed['protocol_sha256']!=sha(protocol):raise ValueError('SQL/local protocol mismatch')
            if frozen['packets']!=packets:raise ValueError('SQL/local supplied text mismatch')
            values={(r['decision_date'],r['symbol']):r for r in sealed['assessments']}
            if len(values)!=400:raise ValueError('Incomplete month assessments')
            keys={values[(str(pd.Timestamp(r.date).date()),r.symbol)].get('cache_key') for r in top.itertuples()}-{None}
            q=text('SELECT * FROM llm_news_analysis_cache WHERE cache_key IN :keys').bindparams(bindparam('keys',expanding=True))
            cache={r['cache_key']:dict(r) for r in conn.execute(q,{'keys':sorted(keys)}).mappings()}
            if set(cache)!=keys:raise ValueError('Missing cached answers')
            conn.rollback()
    finally:engine.dispose()
    panel=[];news_counts=[]
    for r in top.itertuples():
        day=str(pd.Timestamp(r.date).date());key=day,r.symbol
        packet=packet_map[key];value=values[key];compact=local_map[key]
        for field in compact:
            if compact[field]!=value[field]:raise ValueError('Changed compact/SQL assessment')
        if packet['oracle_rank']!=r.oracle_rank or packet['batch_id']!=BATCH:raise ValueError('Changed packet rank')
        cutoff=pd.Timestamp(packet['cutoff_utc'])
        if packet['cutoff_utc']!=protocol['closes'][day]:raise ValueError('Wrong cutoff')
        for a in packet['articles']:
            pub=pd.Timestamp(a['publication_utc'])
            if pub.tzinfo is None or not cutoff-pd.Timedelta(hours=24)<=pub<cutoff:raise ValueError('Article outside frozen window')
        if value['decision']=='UNKNOWN_NO_QUALIFIED_TEXT':
            if packet['articles'] or value['cache_key'] is not None:raise ValueError('Unknown/no-text inconsistent')
        else:
            saved=cache[value['cache_key']]
            request=json.loads(saved['request_json']);response=json.loads(saved['response_json'])
            if request_identity(request,'SYMBOL_DATE_BUNDLE')[0]!=value['cache_key'] or sha(response)!=saved['response_sha256']:
                raise ValueError('Cache request/response hash mismatch')
            context=json.loads(request['input'])
            if any(context[k]!=packet[k] for k in ('symbol','issuer_reference','articles','decision_date','cutoff_utc')):
                raise ValueError('Cached analysis refers to different supplied evidence')
            if value['technical_status']=='VALID':
                if saved['status']!='VALID' or sha(response)!=value['raw_response_sha256']:raise ValueError('Invalid cache promoted')
                assessment=parse(response,request)
                if any(assessment[k]!=value[k] for k in assessment):raise ValueError('Reparsed response differs')
            elif value['decision']!='UNKNOWN_INVALID_RESPONSE':raise ValueError('Unsupported unresolved assessment')
        panel.append(dict(date=day,symbol=r.symbol,oracle_rank=int(r.oracle_rank),oracle_score=float(r.score),
            decision=value['decision'],confidence=value.get('confidence'),technical_status=value.get('technical_status'),
            articles=len(packet['articles']),cache_key=value.get('cache_key'),news_cutoff_utc=packet['cutoff_utc']))
    market=read('artifacts/research/us_oracle_path_protection_selector/20261014-v1/protocol.json')
    prices=Path(market['prices'])
    expected=next(v for k,v in market['sources'].items() if Path(k)==prices)
    if evidence.sha(prices)!=expected:raise ValueError('Qualified price tape changed')
    output.mkdir(parents=True)
    pd.DataFrame(panel).to_parquet(output/'cohort.parquet',index=False)
    evidence.save(output/'sql_cache_snapshot.json',dict(snapshots=snapshots,cache_rows=cache,used_read_only=True))
    p=dict(experiment='JAN2026_ORACLE_PATH_TOP10_CACHED_NEWS',created_at_utc=datetime.now(timezone.utc),
        month=MONTH,sessions=days,top=TOP,model={k:model[k] for k in ('batch_id','fold','model_sha256','profile_sha256','available_date','backend')},
        groups=['ALL_TOP10',*GROUPS],selection='Original rank<=10; no replacements after news/quality outcomes',
        news='Existing qualified 24h strictly before official close J; original cached bundle responses, no new GPT',
        entry='Next official session J+1 open',horizon_sessions=20,tp=.20,sl=.10,trailing=False,
        price_quality='Full twenty-session split-adjusted OHLCV, no synthetic rows, positive volume, stable instrument_id; known discontinuities reserved',
        same_bar='AMBIGUOUS, retain conservative SL-first lower bound and TP-first upper bound; never assume chronological high/low',
        gaps='Opening beyond barrier takes precedence over daily high/low; no intraday fill assumption',
        primary='LONG TP20 before SL10 and full-path/terminal descriptions by all five original decision categories',
        secondary='SHORT mirror of same independent paths, no short availability or profit claim',
        aggregation='candidate-days, not independent positions; per-date, per-symbol and leave-one-symbol-out sensitivity',
        no_portfolio_pnl=True,no_sizing_costs_or_leverage=True,no_confidence_threshold_search=True,
        historical_news_pit_certified=False,llm_future_memory_excluded=False,current_identity_non_pit=True,
        training=False,api_calls=0,new_llm_cost_usd=0,sql_writes=False,broker_orders=False,
        prices=str(prices),price_sha256=expected,registry_sha256=evidence.sha(DEFAULT_REGISTRY_PATH),
        source_files={str(p):evidence.sha(p) for p in (SOURCE/'protocol.json',SOURCE/'report.json',
            folder/'prepared.json',folder/'completed.json',folder/'candidates.parquet',folder/'packets.json',
            weight,model_root/'feature_profile.json',model_root/'folds'/FOLD/'done.json',Path(__file__))},
        files={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()})
    evidence.save(output/'protocol.json',p)
    return dict(status='PREPARED_NO_PRICE_OUTCOMES_LOADED',pairs=len(panel),
        decisions=dict(Counter(r['decision'] for r in panel)),with_news=sum(r['articles']>0 for r in panel),cache_rows=len(cache))


def path_result(frame,side):
    values=frame[['open','high','low','close','volume']].to_numpy(float)
    o,h,l,c,v=values.T
    if len(frame)!=20:return dict(qualified=False,reason='MISSING_PATH_SESSIONS')
    if (not np.isfinite(values).all() or (values<=0).any() or not (h>=np.maximum(o,c)).all()
            or not (l<=np.minimum(o,c)).all() or not (h>=l).all()):
        return dict(qualified=False,reason='INVALID_OHLCV')
    if not frame.is_filled.eq(0).all() or not frame.data_adjustment.eq('split').all():
        return dict(qualified=False,reason='SYNTHETIC_OR_UNQUALIFIED_ADJUSTMENT')
    if frame.instrument_id.isna().any() or frame.instrument_id.nunique()!=1:
        return dict(qualified=False,reason='UNSTABLE_INSTRUMENT')
    entry=o[0];tp=entry*(1.2 if side=='LONG' else .8);sl=entry*(.9 if side=='LONG' else 1.1)
    outcome='TIMEOUT';hit_day=None
    for i in range(20):
        if (o[i]<=sl if side=='LONG' else o[i]>=sl):outcome='SL_GAP'
        elif (o[i]>=tp if side=='LONG' else o[i]<=tp):outcome='TP_GAP'
        else:
            take=(h[i]>=tp if side=='LONG' else l[i]<=tp)
            stop=(l[i]<=sl if side=='LONG' else h[i]>=sl)
            outcome='AMBIGUOUS' if take and stop else 'SL' if stop else 'TP' if take else 'TIMEOUT'
        if outcome!='TIMEOUT':hit_day=str(frame.index[i].date());break
    sign=1 if side=='LONG' else -1
    return dict(qualified=True,reason=None,outcome=outcome,hit_date=hit_day,
        entry_date=str(frame.index[0].date()),terminal_date=str(frame.index[-1].date()),entry_price=float(entry),
        terminal_signed_return_pct=float(sign*(c[-1]/entry-1)*100),
        max_favourable_pct=float((h.max()/entry-1)*100 if side=='LONG' else (1-l.min()/entry)*100),
        max_adverse_pct=float((l.min()/entry-1)*100 if side=='LONG' else (1-h.max()/entry)*100))


def metrics(frame):
    good=frame[frame.qualified]
    n=len(good);counts=Counter(good.outcome)
    tp=sum(counts[k] for k in ('TP','TP_GAP'));sl=sum(counts[k] for k in ('SL','SL_GAP'));amb=counts['AMBIGUOUS']
    return dict(selected=len(frame),qualified=n,rejected=len(frame)-n,symbols=int(good.symbol.nunique()),dates=int(good.date.nunique()),
        reasons=dict(Counter(frame.loc[~frame.qualified,'reason'])),outcomes=dict(counts),
        tp20_before_sl10_lower_pct=100*tp/n if n else None,tp20_before_sl10_upper_pct=100*(tp+amb)/n if n else None,
        sl_first_conservative_pct=100*(sl+amb)/n if n else None,timeout_pct=100*counts['TIMEOUT']/n if n else None,
        terminal_positive_pct=100*good.terminal_signed_return_pct.gt(0).mean() if n else None,
        terminal_mean_pct=float(good.terminal_signed_return_pct.mean()) if n else None,
        terminal_median_pct=float(good.terminal_signed_return_pct.median()) if n else None,
        mean_max_favourable_pct=float(good.max_favourable_pct.mean()) if n else None,
        median_max_favourable_pct=float(good.max_favourable_pct.median()) if n else None,
        mean_max_adverse_pct=float(good.max_adverse_pct.mean()) if n else None,
        most_repeated_symbol_count=int(good.symbol.value_counts().max()) if n else 0)


def run(output):
    p=read(output/'protocol.json');check_files(Path('.'),p['source_files']);check_files(output,p['files'])
    if (output/'report.json').exists():raise FileExistsError('Immutable result already present')
    if evidence.sha(Path(p['prices']))!=p['price_sha256'] or evidence.sha(DEFAULT_REGISTRY_PATH)!=p['registry_sha256']:
        raise ValueError('Price/identity registry changed')
    cohort=pd.read_parquet(output/'cohort.parquet');cohort.date=pd.to_datetime(cohort.date)
    from common.market_calendar import get_market_calendar
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    days=pd.DatetimeIndex([s.session_date for s in calendar.sessions('2026-01-01','2026-03-31') if s.is_open])
    prices=pd.read_parquet(p['prices'],filters=[('symbol','in',sorted(cohort.symbol.unique())),('date','>=',pd.Timestamp('2026-01-01')),('date','<=',pd.Timestamp('2026-03-31'))])
    prices.date=pd.to_datetime(prices.date)
    if prices.duplicated(['date','symbol']).any():raise ValueError('Duplicate price keys')
    registry=load_security_discontinuities()
    grouped={s:f.set_index('date') for s,f in prices.groupby('symbol')}
    rows=[]
    for r in cohort.to_dict('records'):
        pos=days.get_loc(r['date']);target=days[pos+1:pos+21]
        if len(target)!=20:raise ValueError('Calendar tail missing')
        frame=grouped.get(r['symbol'],pd.DataFrame()).reindex(target)
        discontinuity=path_crosses_known_discontinuity(r['symbol'],target[0],target[-1],registry)
        for side in ('LONG','SHORT'):
            checked=(dict(qualified=False,reason='KNOWN_IDENTITY_DISCONTINUITY') if discontinuity else path_result(frame,side))
            rows.append(dict(r,side=side,**checked))
    result=pd.DataFrame(rows)
    result.to_parquet(output/'outcomes.parquet',index=False)
    prices.to_parquet(output/'prices_snapshot.parquet',index=False)
    groups={}
    for side in ('LONG','SHORT'):
        panel=result[result.side.eq(side)]
        groups[side]={'ALL_TOP10':metrics(panel),**{name:metrics(panel[panel.decision.eq(name)]) for name in GROUPS}}
    sensitivity=[]
    panel=result[result.side.eq('LONG')&result.qualified]
    for symbol in sorted(panel.symbol.unique()):
        rest=panel[~panel.symbol.eq(symbol)]
        baseline=metrics(rest);bull=metrics(rest[rest.decision.eq('BULLISH')])
        if baseline['qualified'] and bull['qualified']:
            sensitivity.append(dict(removed_symbol=symbol,bullish_n=bull['qualified'],
                delta_tp_lower_pp=bull['tp20_before_sl10_lower_pct']-baseline['tp20_before_sl10_lower_pct'],
                delta_terminal_mean_pp=bull['terminal_mean_pct']-baseline['terminal_mean_pct']))
    evidence.save(output/'leave_one_symbol_out.json',sensitivity)
    daily=[]
    for day,part in panel.groupby('date'):
        daily.append(dict(date=str(day.date()),baseline=metrics(part),bullish=metrics(part[part.decision.eq('BULLISH')]),bearish=metrics(part[part.decision.eq('BEARISH')])))
    evidence.save(output/'daily_comparison.json',daily)
    report=dict(status='COMPLETED_EXPLORATORY_NON_PIT',created_at_utc=datetime.now(timezone.utc),
        selected_pairs=len(cohort),decisions=dict(Counter(cohort.decision)),groups=groups,
        ambiguous_daily_bar_order_retained=True,repeated_paths_not_independent=True,portfolio_pnl_computed=False,
        causal_or_profitability_advantage_proven=False,api_calls=0,new_llm_cost_usd=0,sql_writes=False,training=False,
        protocol_sha256=evidence.sha(output/'protocol.json'),
        files={name:evidence.sha(output/name) for name in ('outcomes.parquet','prices_snapshot.parquet','daily_comparison.json','leave_one_symbol_out.json')})
    evidence.save(output/'report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','run'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    r=prepare(args.output) if args.phase=='prepare' else run(args.output)
    print(json.dumps(evidence.archive.json_value(r),ensure_ascii=False))
