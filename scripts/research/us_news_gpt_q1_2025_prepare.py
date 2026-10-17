"""Prepare TOP10/news/budget for Q1 2025, with NO paid API entry point.

Read-only SQL, fixed annual CatBoost inference, research outputs only. No fit,
price outcomes, Web, broker, production change or GPT call is performed here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_gpt_september_pilot as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE=pilot.SOURCE
ARCHIVE=Path('artifacts/research/oracle_path_confirmation/20261013-v1')
DATASET=Path('artifacts/research/us_oracle_path_protection_dataset/20261014-v1')
START,END,TOP='2025-01-01','2025-03-31',10
LOG=logging.getLogger(__name__)


def fixed_top(scores, count):
    if type(count) is not int or count<1:
        raise ValueError('Positive integer count required')
    if scores.duplicated(['date','symbol']).any() or not np.isfinite(scores.score).all():
        raise ValueError('Duplicate/nonfinite scores')
    if not scores.score.between(0,1).all():
        raise ValueError('Invalid score range')
    if scores.groupby('date').size().lt(count).any():
        raise ValueError('Insufficient daily universe')
    selected=scores.sort_values(['date','score','symbol'],ascending=[True,False,True]).copy()
    selected['oracle_rank']=selected.groupby('date').cumcount()+1
    return selected[selected.oracle_rank.le(count)].copy()


def compare_original_top5(candidates, original):
    left=candidates[candidates.oracle_rank.le(5)].sort_values(['date','oracle_rank'])
    right=original.sort_values(['date','oracle_rank'])
    keys=['date','symbol','oracle_rank']
    pd.testing.assert_frame_equal(left[keys].reset_index(drop=True),right[keys].reset_index(drop=True),check_exact=True)
    error=float(np.max(np.abs(left.score.to_numpy()-right.score.to_numpy())))
    if not math.isfinite(error) or error>1e-7:
        raise ValueError('Reproduced annual score differs from original')
    return dict(rows_compared=len(left),daily_top5_exact=True,score_max_absolute_error=error)


def j_history_admission(group, features, quality, dataset):
    # Oracle rank is a candidate field, not a raw price-derived feature. Preserve
    # the same merge and finite-input check as the archived annual preparation.
    admission=group[['date','symbol','oracle_rank']].merge(features[dataset.STOCK+dataset.MARKET],
        left_on='date',right_index=True,how='left',validate='one_to_one')
    valid=admission.date.map(quality).fillna(False).to_numpy() & np.isfinite(
        admission[dataset.FEATURES]).all(axis=1).to_numpy()
    return [dict(date=row.date,symbol=row.symbol,selected=bool(ok),
        entry_quality_reason='' if ok else 'J_HISTORY_OR_SELECTOR_INPUT_UNQUALIFIED_ALL_ARMS')
        for row,ok in zip(admission.itertuples(index=False),valid)]


def panel_rows(candidates, news, closes):
    from scripts.research.us_news_materiality_feasibility import guarded_reasons, raw_publication_reason
    empty=news.iloc[:0]
    groups={symbol:part for symbol,part in news.groupby('symbol')}
    panel=[]
    for row in candidates.sort_values(['date','oracle_rank']).itertuples(index=False):
        cutoff=closes[pd.Timestamp(row.date)]
        part=groups.get(row.symbol,empty)
        part=part[part.published_at_utc.lt(cutoff) & part.published_at_utc.ge(cutoff-pd.Timedelta(hours=24))]
        records=part.to_dict('records')
        reasons=Counter(reason for item in records for reason in guarded_reasons(item,cutoff))
        accepted=[item['article_id'] for item in records
            if not raw_publication_reason(item['provider_publication'],item['published_at_utc'])]
        panel.append(dict(decision_date=str(row.date.date()),symbol=row.symbol,oracle_rank=int(row.oracle_rank),
            cutoff_utc=cutoff.isoformat(),article_ids=sorted(part.article_id),
            accepted_article_ids=sorted(accepted),conservative_guarded_pairs=sum(
                not guarded_reasons(item,cutoff) for item in records),
            guard_reasons=dict(sorted(reasons.items())),selected_j_history=bool(row.selected)))
    return panel


def packet_for(item, metadata, bodies, identity):
    articles=[]
    for article in item['accepted_article_ids']:
        row=metadata.loc[article]
        raw=bodies[article]
        body=pilot.clean(raw['body'])
        length=int(row['content_chars']) if pd.notna(row['content_chars']) else 0
        articles.append(dict(article_id=article,headline=pilot.clean(raw['headline'])[:500],
            summary=pilot.clean(raw['summary'])[:700],body=body[:2400],
            publication_utc=row['published_at_utc'].isoformat(),
            body_truncated=bool(length>12000 or len(body)>2400),body_sha256=raw['body_sha256']))
    value={k:item[k] for k in ['decision_date','symbol','oracle_rank','cutoff_utc']}
    value.update(issuer_reference=identity or {},articles=articles)
    return value


def preflight(root):
    marker=root/'protocol.json'
    if marker.exists():
        saved=pilot.read(marker);verify_hashes(Path('.'),saved['sources']);return saved
    from common.config_loader import load_config
    from common.market_calendar import get_market_calendar
    from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes
    prior=pilot.read(SOURCE/'protocol.json')
    report=pilot.read(SOURCE/'report.json')
    verify_hashes(SOURCE,{'candidates.parquet':report['files']['candidates.parquet']})
    model=prior['annual_models']['2025']
    if any(pd.Timestamp(model[k])>=pd.Timestamp(START) for k in ['train_available_max','val_available_max']):
        raise ValueError('Annual fold is not strictly prior to 2025')
    model_root=Path('artifacts/models')/model['batch_id']/'oracle_path'
    model_file=model_root/'folds'/model['fold']/'catboost_model.cbm'
    if digest(model_file)!=model['model_sha256']:
        raise ValueError('Annual model hash mismatch')
    model_protocol=pilot.read(model_root/'protocol.json')
    if model_protocol.get('training_backend')!='catboost':
        raise ValueError('Expected explicitly selected annual CatBoost')
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    sessions=[s for s in calendar.sessions(START,END) if s.is_open]
    if len(sessions)!=60:
        raise ValueError('Unexpected official Q1 session calendar')
    config=load_config('config.yaml')['llm_directional_filter']
    if config['model']!='gpt-6-luna':
        raise ValueError('Reconfirm pricing before preparing another GPT model')
    chunks=sorted((ARCHIVE/'chunks').iterdir())
    sources=code_hashes()
    for path in [Path(__file__),Path('tests/test_us_news_gpt_q1_2025_prepare.py'),
        Path(pilot.__file__),SOURCE/'protocol.json',SOURCE/'report.json',SOURCE/'candidates.parquet',
        SOURCE/'annual-features.parquet',DATASET/'protocol.json',model_root/'protocol.json',
        model_file,model_file.parent/'done.json',ARCHIVE/'scores.parquet',
        Path('scripts/research/us_news_materiality_feasibility.py'),
        Path('scripts/research/us_oracle_path_protection_dataset.py')]:
        sources[str(path)]=digest(path)
    for folder in chunks:
        done=pilot.read(folder/'done.json')
        verify_hashes(folder,{'features.parquet':done['files']['features.parquet']})
        sources[str(folder/'done.json')]=digest(folder/'done.json')
        sources[str(folder/'features.parquet')]=done['files']['features.parquet']
    value=dict(experiment='GPT_NEWS_TOP10_Q1_2025_PREPARATION_ONLY',
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),start=START,end=END,top=TOP,
        sessions=[str(s.session_date) for s in sessions],candidate_days_expected=600,
        closes={str(s.session_date):s.close_at_utc.isoformat() for s in sessions},
        annual_model=model,model_file=str(model_file),universe=list(model_protocol['universe']),
        inference_only=True,oracle_training=False,original_top5_must_reproduce=True,
        cross_sectional_ranks='all observable rows pooled across chunks per date, before TOP10',
        news_window_hours=24,cutoff='STRICTLY_BEFORE_NYSE_CLOSE_J',
        primary_rule='SAME_AS_SEPTEMBER_VETO_BEARISH_MATERIAL_FACT_MATCHED_QUOTES_CONFIDENCE_GE_0_75',
        tp=.20,sl=.05,trailing=False,horizon=20,entry='next session open',
        no_top11_replacement=True,no_news_policy='UNKNOWN, retained by veto arm',
        gpt_model=config['model'],paid_analysis_authorized=False,api_calls=0,web_calls=0,
        preparation_has_no_paid_api_entry_point=True,
        pricing_reference={'url':'https://developers.openai.com/api/docs/models/gpt-6-luna',
            'checked_on':'2026-10-14','input_usd_per_million':.10,'output_usd_per_million':.50,
            'processing':'standard, short context','cached_discount_ignored':True},
        max_output_tokens_per_future_request=pilot.MAX_OUTPUT_TOKENS,
        future_request_max_bytes=240000,request_overhead_token_margin=2000,
        historical_news_non_pit=True,llm_historical_memory_contamination_not_excluded=True,
        current_issuer_metadata_non_pit=True,static_universe_survivorship_reserved=True,
        financial_outcomes_not_read=True,future_price_quality_not_used_for_selection=True,
        sql_read_only=True,sql_writes=False,production_changed=False,broker_calls=False,
        sources=sources,prices_history_path=prior['prices'],
        price_hash=next(v for k,v in prior['sources'].items() if Path(k)==Path(prior['prices'])),
        feature_chunk_count=len(chunks))
    atomic_json(marker,value)
    return value


def score_candidates(root,p):
    marker=root/'scores-ready.json'
    if marker.exists():
        saved=pilot.read(marker);verify_hashes(root,saved['files']);return saved
    from catboost import CatBoostClassifier
    from modelFactory.oracle_path.train import restore_ranks
    profile=pilot.read(DATASET/'protocol.json')['features_profile']
    pieces=[]
    folders=sorted((ARCHIVE/'chunks').iterdir())
    for i,folder in enumerate(folders):
        frame=pd.read_parquet(folder/'features.parquet',filters=[('date','>=',pd.Timestamp(START)),
            ('date','<=',pd.Timestamp(END))])
        if not frame.empty:
            frame=frame.drop(columns=[c for c in frame if c.endswith('_xs_rank')])
            pieces.append(frame)
        if i%8==0 or i==len(folders)-1:
            atomic_json(root/'progress.json',dict(status='READING_FEATURES',completed=i+1,total=len(folders),
                rows=sum(len(part) for part in pieces),api_calls=0))
            LOG.info('Features %d/%d; %d rows',i+1,len(folders),sum(len(part) for part in pieces))
    matrix=pd.concat(pieces,ignore_index=True)
    if matrix.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate pooled observable feature membership')
    matrix=restore_ranks(matrix,profile['generator_options'])
    observable=pd.read_parquet(ARCHIVE/'scores.parquet',columns=['date','symbol'],
        filters=[('date','>=',pd.Timestamp(START)),('date','<=',pd.Timestamp(END))])
    matrix=matrix.merge(observable,on=['date','symbol'],how='inner',validate='one_to_one')
    if not set(matrix.symbol).issubset(p['universe']):
        raise ValueError('Observable cache contains symbols outside frozen model universe')
    model=CatBoostClassifier().load_model(p['model_file'])
    columns=profile['feature_columns']
    if model.feature_names_!=columns:
        raise ValueError('Annual model/cache feature order mismatch')
    atomic_json(root/'progress.json',dict(status='SCORING_FIXED_MODEL',rows=len(matrix),api_calls=0))
    scores=matrix[['date','symbol']].copy()
    scores['score']=model.predict_proba(matrix[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32),thread_count=2)[:,1]
    scores['proba_extreme']=scores.groupby('date').score.rank(method='average',pct=True)
    selected=fixed_top(scores,TOP)
    original=pd.read_parquet(SOURCE/'candidates.parquet')
    original=original[original.date.between(START,END)].copy()
    match=compare_original_top5(selected,original)
    if len(selected)!=600 or set(selected.date)!=set(pd.to_datetime(p['sessions'])):
        raise ValueError('Incomplete fixed quarter TOP10')
    selected['year']=2025;selected['backend']='catboost';selected['fold_start']=p['annual_model']['fold']
    # Archive only J feature summaries for the eventual native admission gate.
    from scripts.research import us_oracle_path_protection_dataset as dataset
    from modelFactory.oracle.security_continuity import load_security_discontinuities,split_frame_on_discontinuities
    from modelFactory.oracle.build_labels import nyse_sessions
    if digest(p['prices_history_path'])!=p['price_hash']:
        raise ValueError('Historical price archive changed')
    # No price after March31 is read during preparation.
    history=pd.read_parquet(p['prices_history_path'],filters=[('date','<=',pd.Timestamp(END))])
    history=history[history.symbol.isin(set(selected.symbol)|{'SPY'})].copy()
    history['date']=pd.to_datetime(history.date)
    days=nyse_sessions('2023-01-01',END)
    spy=history[history.symbol.eq('SPY')].set_index('date')
    benchmark=spy.adj_close.where(spy.adj_close.notna(),spy.close).reindex(days)
    registry=load_security_discontinuities()
    admissions=[]
    for symbol,group in selected.groupby('symbol'):
        calculated=[];qualities=[]
        for part in split_frame_on_discontinuities(history[history.symbol.eq(symbol)],symbol,registry):
            calculated.append(dataset.decision_features(part,benchmark))
            segment=part.set_index('date').reindex(days[(days>=part.date.min())&(days<=part.date.max())])
            qualities.append(dataset.j_history_quality(segment,benchmark,days))
        if not calculated:
            admissions.extend(dict(date=row.date,symbol=symbol,selected=False,
                entry_quality_reason='MISSING_J_HISTORY') for row in group.itertuples(index=False));continue
        features=pd.concat(calculated);quality=pd.concat(qualities)
        admissions.extend(j_history_admission(group,features,quality,dataset))
    selected=selected.merge(pd.DataFrame(admissions),on=['date','symbol'],validate='one_to_one')
    actual=selected[selected.oracle_rank.le(5)][['date','symbol','selected']].merge(
        original[['date','symbol','selected']],on=['date','symbol'],suffixes=('_new','_old'),validate='one_to_one')
    if not actual.selected_new.eq(actual.selected_old).all():
        raise ValueError('Backward-only admission differs from original TOP5')
    scores.to_parquet(root/'observable-scores.parquet',index=False)
    selected.to_parquet(root/'candidates.parquet',index=False)
    saved=dict(status='TOP10_FIXED_MODEL_REPRODUCED',rows_scored=len(scores),candidate_days=len(selected),
        sessions=int(selected.date.nunique()),distinct_symbols=int(selected.symbol.nunique()),
        candidates_j_history_qualified=int(selected.selected.sum()),original_top5_admission_exact=True,
        original_top5_comparison=match,price_history_latest_read=END,financial_outcomes_read=False,
        files={n:digest(root/n) for n in ['observable-scores.parquet','candidates.parquet']})
    atomic_json(marker,saved)
    return saved


def collect_news_metadata(root,p,candidates,conn):
    from sqlalchemy import text,bindparam
    from scripts.research.us_news_materiality_feasibility import META_FIELDS,STAMPS
    query=text(META_FIELDS+''' FROM news_raw n FORCE INDEX (idx_news_raw_source_published)
        STRAIGHT_JOIN news_ticker_map m ON m.article_id=n.article_id
        WHERE n.ingestion_source IN ('eodhd','alpaca')
        AND n.published_at_utc>=:start AND n.published_at_utc<:end
        AND m.symbol IN :symbols LIMIT 20001''').bindparams(bindparam('symbols',expanding=True))
    boundaries=list(pd.date_range('2025-01-01','2025-04-01',freq='7D',tz='UTC'))
    if boundaries[-1]!=pd.Timestamp('2025-04-01',tz='UTC'):
        boundaries.append(pd.Timestamp('2025-04-01',tz='UTC'))
    folder=root/'news-chunks';folder.mkdir(exist_ok=True)
    parts=[];probes=[]
    closes={pd.Timestamp(day):pd.Timestamp(value) for day,value in p['closes'].items()}
    for i,(start,end) in enumerate(zip(boundaries[:-1],boundaries[1:])):
        active=candidates[candidates.date.map(closes).lt(end+pd.Timedelta(hours=24)) &
            candidates.date.map(closes).gt(start)]
        symbols=sorted(active.symbol.unique())
        stem=folder/f'{i:02d}-{start.date()}'
        marker=stem.with_suffix('.json');path=stem.with_suffix('.parquet')
        if marker.exists():
            saved=pilot.read(marker);verify_hashes(folder,saved['files'])
            part=pd.read_parquet(path);probes.append(saved)
        else:
            values=dict(start=start.tz_localize(None).to_pydatetime(),end=end.tz_localize(None).to_pydatetime(),symbols=symbols)
            rows=[dict(row) for row in conn.execute(query,values).mappings()] if symbols else []
            if len(rows)>20000:
                raise ValueError('News chunk truncated; no interpretation as absence')
            columns=['article_id','symbol','ingestion_source','source','published_at_utc','created_at','updated_at',
                'map_created_at','map_updated_at','is_primary_ticker','headline','content_chars','content_sha256',
                'provider_publication','payload_json_type','url','dedupe_hash']
            part=pd.DataFrame(rows,columns=columns)
            for field in STAMPS:
                part[field]=pd.to_datetime(part[field],utc=True,errors='coerce')
            part.to_parquet(path,index=False)
            saved=dict(chunk=i,start=start.isoformat(),end=end.isoformat(),symbols=symbols,rows=len(rows),
                truncated=False,query_complete=True,files={path.name:digest(path)})
            atomic_json(marker,saved);probes.append(saved)
        parts.append(part)
        atomic_json(root/'progress.json',dict(status='READING_NEWS_METADATA',completed=i+1,total=len(boundaries)-1,
            associations=sum(len(part) for part in parts),api_calls=0))
        LOG.info('News metadata %d/%d; %d associations',i+1,len(boundaries)-1,sum(len(part) for part in parts))
    news=pd.concat(parts,ignore_index=True)
    if news.duplicated(['article_id','symbol']).any():
        raise ValueError('Overlapping SQL chunks or duplicate article/symbol key')
    atomic_json(root/'query-coverage.json',dict(probes=probes,all_queries_complete=True,no_truncation=True))
    return news,closes


def prepare_news(root,p):
    marker=root/'prepare.json'
    if marker.exists():
        saved=pilot.read(marker);verify_hashes(root,saved['files']);return saved
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import create_engine,text,bindparam
    candidates=pd.read_parquet(root/'candidates.parquet')
    base=get_sqlalchemy_engine()
    engine=create_engine(base.url,connect_args={'read_timeout':25,'write_timeout':10},echo=False);base.dispose()
    bodies={}
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US alpha_trade required')
            news,closes=collect_news_metadata(root,p,candidates,conn)
            if news.empty:
                raise ValueError('No historical text metadata; no GPT preparation possible')
            panel=panel_rows(candidates,news,closes)
            all_ids=sorted({article for item in panel for article in item['accepted_article_ids']})
            identities={row['symbol']:dict(row) for row in conn.execute(text(
                'SELECT symbol,company_name,exchange FROM stock_metadata WHERE symbol IN :symbols').bindparams(
                    bindparam('symbols',expanding=True)),dict(symbols=sorted(candidates.symbol.unique()))).mappings()}
            metadata=news.drop_duplicates('article_id').set_index('article_id')
            body_folder=root/'text-chunks';body_folder.mkdir(exist_ok=True)
            for number,start in enumerate(range(0,len(all_ids),100)):
                subset=all_ids[start:start+100]
                path=body_folder/f'{number:03d}.json';mark=body_folder/f'{number:03d}.done.json'
                if mark.exists():
                    saved=pilot.read(mark);verify_hashes(body_folder,saved['files'])
                    if saved['article_ids']!=subset:
                        raise ValueError('Changed immutable text chunk membership')
                    rows=pilot.read(path)
                else:
                    rows=[dict(row) for row in conn.execute(text('''SELECT article_id,headline,summary,
                        LEFT(content,12000) body,SHA2(content,256) body_sha256 FROM news_raw
                        WHERE article_id IN :ids''').bindparams(bindparam('ids',expanding=True)),dict(ids=subset)).mappings()]
                    if len(rows)!=len(subset):
                        raise ValueError('Historical body disappeared during snapshot')
                    atomic_json(path,rows)
                    atomic_json(mark,dict(article_ids=subset,files={path.name:digest(path)}))
                for row in rows:
                    expected=metadata.loc[row['article_id'],'content_sha256']
                    if row['body_sha256']!=expected:
                        raise ValueError('Body hash changed during snapshot')
                    bodies[row['article_id']]=row
                atomic_json(root/'progress.json',dict(status='SNAPSHOTTING_TEXTS',completed=len(bodies),total=len(all_ids),api_calls=0))
    finally:
        engine.dispose()
    # Metadata and full bodies never enter the paid request as SQL timestamps or
    # outcome labels; only publication-qualified excerpts are selected.
    packets=[packet_for(item,metadata,bodies,identities.get(item['symbol'])) for item in panel]
    plan=[]
    for i,packet in enumerate(packets):
        identity_ready=bool(packet['issuer_reference'].get('company_name'))
        request=pilot.build_request(packet,p['gpt_model']) if packet['articles'] and identity_ready else None
        size,bound=pilot.token_cost_bound(request) if request else (0,0.)
        plan.append(dict(packet=i,decision_date=packet['decision_date'],symbol=packet['symbol'],
            articles=len(packet['articles']),identity_ready=identity_ready,planned_call=request is not None,
            request_bytes=size,conservative_cost_bound_usd=bound,
            exceeds_short_context_byte_guard=size>p['future_request_max_bytes'],
            payload_sha256=__import__('hashlib').sha256(json.dumps(request,ensure_ascii=False,sort_keys=True).encode()).hexdigest() if request else None))
    atomic_json(root/'packets.json',packets)
    atomic_json(root/'availability.json',panel)
    atomic_json(root/'request-plan.json',plan)
    news.to_parquet(root/'news-metadata.parquet',index=False)
    cells=[]
    for month in ['2025-01','2025-02','2025-03']:
        sub=[(item,packet) for item,packet in zip(panel,packets) if item['decision_date'].startswith(month)]
        cells.append(dict(month=month,candidate_days=len(sub),
            with_news=sum(bool(packet['articles']) for _,packet in sub),
            article_mappings=sum(len(packet['articles']) for _,packet in sub),
            guarded_mappings=sum(item['conservative_guarded_pairs'] for item,_ in sub)))
    reference=pilot.read('artifacts/research/us_news_gpt_september/20261014-v1/analysis.json')
    reference_prep=pilot.read('artifacts/research/us_news_gpt_september/20261014-v1/prepare.json')
    bytes_total=sum(item['request_bytes'] for item in plan)
    calls=sum(item['planned_call'] for item in plan)
    proxy_input=bytes_total*reference['input_tokens']/reference_prep['input_bytes']
    proxy_output=calls*reference['output_tokens']/reference['actual_calls']
    empirical_proxy=(proxy_input*.10+proxy_output*.50)/1e6
    missing_identity=[item for item in plan if item['articles'] and not item['identity_ready']]
    oversized=[item for item in plan if item['exceeds_short_context_byte_guard']]
    bound=sum(item['conservative_cost_bound_usd'] for item in plan)
    files=['protocol.json','scores-ready.json','observable-scores.parquet','candidates.parquet',
        'packets.json','availability.json','request-plan.json','news-metadata.parquet','query-coverage.json']
    files += [str(path.relative_to(root)) for path in sorted((root/'text-chunks').iterdir())]
    report=dict(status='PREPARED_AWAITING_PAID_ANALYSIS_GO' if not missing_identity and not oversized else 'PREPARED_WITH_INPUT_BLOCKERS',
        period=[START,END],sessions=60,top=TOP,candidate_days=len(panel),distinct_symbols=int(candidates.symbol.nunique()),
        with_publication_qualified_news=sum(bool(packet['articles']) for packet in packets),
        without_publication_qualified_news=sum(not packet['articles'] for packet in packets),
        requested_article_mappings=sum(len(item['article_ids']) for item in panel),
        publication_qualified_article_mappings=sum(len(packet['articles']) for packet in packets),
        unique_articles=len(all_ids),truncated_article_mappings=sum(article['body_truncated'] for packet in packets for article in packet['articles']),
        conservative_guarded_mappings=sum(item['conservative_guarded_pairs'] for item in panel),
        monthly_coverage=cells,planned_gpt_calls=calls,api_calls_performed=0,api_credit_consumed_usd=0,
        conservative_standard_token_cost_bound_usd=bound,
        recommended_future_budget_cap_usd=max(.05,math.ceil(bound/.05)*.05),
        approximate_empirical_cost_proxy_usd=empirical_proxy,
        estimate_warning='Empirical proxy from September only; conservative byte bound controls future standard short-context requests; taxes/FX/concurrent jobs excluded',
        max_output_tokens_per_request=pilot.MAX_OUTPUT_TOKENS,request_bytes_total=bytes_total,
        blocked_missing_identity=missing_identity,blocked_oversized_requests=oversized,
        source_created_at_min=str(news.loc[news.article_id.isin(all_ids),'created_at'].min()),
        source_created_at_max=str(news.loc[news.article_id.isin(all_ids),'created_at'].max()),
        no_financial_outcomes_computed=True,no_training=True,no_sql_writes=True,no_broker_orders=True,
        no_production_changes=True,preparation_does_not_demonstrate_predictive_gain=True,
        files={name:digest(root/name) for name in files})
    atomic_json(marker,report)
    atomic_json(root/'report.json',report)
    atomic_json(root/'progress.json',dict(status=report['status'],planned_gpt_calls=calls,api_calls=0))
    return report


def run(root):
    p=preflight(root)
    scores=score_candidates(root,p)
    LOG.info('TOP10 ready: %d candidates, %d symbols; original TOP5 verified',scores['candidate_days'],scores['distinct_symbols'])
    result=prepare_news(root,p)
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,result['files'])
    return result


def main():
    from scripts.research.oracle_path_confirmation import exclusive_run
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive_run(args.output):
        try:
            result=run(args.output)
            print(json.dumps({key:value for key,value in result.items() if key!='files'},default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error=f'{type(exc).__name__}: {str(exc)[:600]}',api_calls=0))
            raise


if __name__=='__main__':
    main()
