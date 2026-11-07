"""Prepare / analyze / replay a frozen 2025 local-LLM veto after per-symbol.

Preparation is read-only against MySQL. Inference contacts loopback LM Studio
only, sequentially. Replays use the existing frozen tape, never a provider.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import argparse
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sqlite3
import time

import numpy as np
import pandas as pd
from sqlalchemy import text

from common.ia_prompts import load_prompt
from service.local_ai.lm_studio import Client, Connection, load_connection
from service.local_ai.research_veto import Cache, SCHEMA, encoded, key_for, validate_response
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


REFERENCE = Path('artifacts/ihm_backtesting_runs/run/20261107_095041_0b38b8de/artifacts')
TAPE = Path('artifacts/research/us_winner_ui_grid/20261107-v3')
PROMPT = 'local.oracle_directional.v1.research_veto'
LOG = logging.getLogger(__name__)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def news_query_windows(days):
    """Merge only candidate lookbacks, then partition at calendar-month boundaries."""
    merged = []
    for day in sorted(set(days)):
        start, end = pd.Timestamp(day)-pd.Timedelta(days=7), pd.Timestamp(day)+pd.Timedelta(days=1)
        if merged and start<=merged[-1][1]:
            merged[-1] = (merged[-1][0],max(end,merged[-1][1]))
        else:
            merged.append((start,end))
    result = []
    for start,end in merged:
        while start<end:
            stop = min(end,start.to_period('M').to_timestamp()+pd.offsets.MonthBegin(1))
            result.append((start,stop)); start = stop
    return result


def price_summary(bars, symbol, day):
    part = bars[bars.symbol.eq(symbol) & pd.to_datetime(bars.date).le(pd.Timestamp(day))].sort_values('date').tail(60)
    if part.empty:
        return dict(status='MISSING', sessions=0)
    if part.duplicated('date').any():
        raise ValueError('Bougies de contexte dupliquées')
    clean = part[['open', 'high', 'low', 'close', 'volume']].astype(float)
    if (not np.isfinite(clean.to_numpy()).all() or clean[['open', 'low', 'close']].le(0).any().any()
            or clean.high.lt(clean[['open', 'low', 'close']].max(axis=1)).any()
            or clean.low.gt(clean[['open', 'close']].min(axis=1)).any()
            or clean.volume.lt(0).any() or part.is_filled.fillna(1).ne(0).any()):
        return dict(status='INVALID', sessions=len(part))
    close = clean.close
    returns = {str(n): float(close.iloc[-1]/close.iloc[-n-1]-1) if len(close)>n else None
               for n in (1, 5, 20, 59)}
    return dict(status='ASOF_COMPLETE' if pd.Timestamp(part.date.iloc[-1]) == pd.Timestamp(day) else 'STALE',
        sessions=len(part), first_date=str(pd.Timestamp(part.date.iloc[0]).date()),
        last_date=str(pd.Timestamp(part.date.iloc[-1]).date()), last_close=float(close.iloc[-1]),
        returns_fraction=returns, mean_volume_20=float(clean.volume.tail(20).mean()),
        volume_last_over_mean20=float(clean.volume.iloc[-1]/clean.volume.tail(20).mean())
            if clean.volume.tail(20).mean()>0 else None,
        source_counts=part.data_source.value_counts().to_dict(),
        adjustment_counts=part.data_adjustment.value_counts().to_dict(),
        current_archived_vintage_not_certified_pit=True)


def news_context(frame, symbol, cutoff):
    from scripts.research.us_news_materiality_feasibility import raw_publication_reason
    part = frame[frame.symbol.eq(symbol)].copy() if not frame.empty else frame
    if part.empty:
        return [], dict(recent=0, qualified=0, supplied=0, omitted=0, invalid_publication=0)
    stamps = pd.to_datetime(part.published_at_utc, utc=True)
    part = part[stamps.ge(cutoff-pd.Timedelta(days=7)) & stamps.lt(cutoff)].copy()
    recent = len(part)
    result = []; seen = set(); invalid = 0
    for row in part.sort_values(['published_at_utc', 'article_id'], ascending=[False, True]).to_dict('records'):
        stamp = pd.Timestamp(row['published_at_utc'])
        if raw_publication_reason(row['provider_publication'], stamp):
            invalid += 1
            continue
        body = str(row.get('body') or '').strip()
        if len(body)<200:
            continue
        content_hash = row.get('content_sha256') or hashlib.sha256(body.encode()).hexdigest()
        if content_hash in seen:
            continue
        seen.add(content_hash)
        title = str(row.get('headline') or '')[:500]
        snippet = body[:3000]
        result.append(dict(source_id=f"news:{row['article_id']}:{content_hash}",
            text=title+'\n'+snippet, url=row.get('url'), published_at_utc=stamp.isoformat(),
            provider=row['ingestion_source'], primary_ticker_association=row.get('is_primary_ticker') == 1,
            observed_created_at=str(row.get('created_at')), observed_updated_at=str(row.get('updated_at')),
            body_excerpt_truncated=int(row.get('content_chars') or len(body))>len(snippet),
            historical_version_available_at_cutoff_not_certified=True))
    return result[:6], dict(recent=recent, qualified=len(result), supplied=min(6,len(result)),
        omitted=max(0,len(result)-6), invalid_publication=invalid)


def prepare(root):
    from backtesting.isolation import ReadOnlyReplay
    from common.market_calendar import get_market_calendar
    from database.connection import get_sqlalchemy_engine
    from scripts.research.us_news_materiality_feasibility import META_FIELDS
    from scripts.research.us_winner_ui_grid_20261107 import verify_inputs

    root.mkdir(parents=True, exist_ok=False)
    verify_inputs(TAPE)
    signals = pd.read_csv(REFERENCE/'signals.csv')
    if len(signals)!=204 or signals.symbol.nunique()!=24 or signals.duplicated(['trade_date','symbol']).any():
        raise ValueError('La référence a changé ; revoir le protocole avant préparation')
    bars = pd.read_parquet(TAPE/'inputs/daily.parquet')
    symbols = sorted(signals.symbol.unique())
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = cal.sessions('2024-12-31', '2025-12-30')
    closes = {str(s.session_date): pd.Timestamp(s.close_at_utc) for s in sessions if s.is_open}
    config = replace(load_connection(), timeout_seconds=300, max_output_tokens=8192)
    if config.model != 'qwen3.5-9b':
        raise ValueError('Modèle différent du pilote demandé')
    prompt = load_prompt(PROMPT, runtime='local')
    (root/'prompt.txt').write_text(prompt, encoding='utf-8')
    news_rows = []; metadata = {}
    with ReadOnlyReplay(root).install():
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
        with engine.connect() as conn, conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            for i, symbol in enumerate(symbols):
                atomic_json(root/'progress.json', dict(status='PREPARING_READ_ONLY', completed=i,
                    total=len(symbols), symbol=symbol, local_calls=0, cloud_calls=0))
                # The isolation guard deliberately forbids SQL comment hints.
                sql = META_FIELDS.replace('/*+ MAX_EXECUTION_TIME(15000) */', '').replace(
                    'n.headline,', 'n.headline,LEFT(n.content,12000) body,')+'''
                    FROM news_ticker_map m FORCE INDEX(idx_news_ticker_map_symbol)
                    STRAIGHT_JOIN news_raw n ON n.article_id=m.article_id
                    WHERE m.symbol=:symbol AND n.published_at_utc>=:start AND n.published_at_utc<:end
                    AND n.ingestion_source IN ('eodhd','alpaca') LIMIT 20001'''
                part = []
                windows = news_query_windows(signals.loc[signals.symbol.eq(symbol),'trade_date'])
                for start,end in windows:
                    chunk = [dict(r) for r in conn.execute(text(sql), dict(symbol=symbol,
                        start=start.to_pydatetime(), end=end.to_pydatetime())).mappings()]
                    if len(chunk)>=20001:
                        raise ValueError(f'Corpus tronqué pour {symbol}/{start}/{end}; partitionner avant de continuer')
                    part.extend(chunk)
                news_rows.extend(part)
                meta = conn.execute(text('SELECT company_name FROM stock_metadata WHERE symbol=:symbol'),
                                    dict(symbol=symbol)).scalar_one_or_none()
                metadata[symbol] = meta
                LOG.info('Contexte %s %d/%d : %d associations news', symbol, i+1, len(symbols), len(part))
    news = pd.DataFrame(news_rows)
    if not news.empty:
        if news.duplicated(['article_id','symbol']).any():
            raise ValueError('Associations news dupliquées')
        news['published_at_utc'] = pd.to_datetime(news.published_at_utc, utc=True)
    news.to_parquet(root/'news-snapshot.parquet', index=False)
    signals.to_parquet(root/'signals.parquet', index=False)
    packets = []; coverage = []
    for row in signals.sort_values(['trade_date','rank']).itertuples(index=False):
        day = str(row.trade_date)[:10]; cutoff = closes[day]
        articles, counts = news_context(news, row.symbol, cutoff)
        context = dict(symbol=row.symbol, signal_date=day, cutoff_utc=cutoff.isoformat(),
            company_name_current_non_pit=metadata[row.symbol],
            news=articles, news_coverage=counts,
            price_context=price_summary(bars,row.symbol,day),
            benchmark_context=price_summary(bars,'SPY',day),
            unavailable=['historical_consensus','historical_options','qualified_SEC_receipts','historical_sentiment_versions'],
            retrospective_news_versions=True, future_prices_included=False)
        messages = [dict(role='system',content=prompt), dict(role='user',content=encoded(context))]
        request = dict(model=config.model, messages=messages, temperature=config.temperature,
                       max_tokens=config.max_output_tokens, stream=False,
                       response_format=dict(type='json_schema',json_schema=dict(
                           name='issuer_news_veto',strict=True,schema=SCHEMA)))
        revision = 'qwen3.5-9b-local-20261107-research-v2-structured'
        packet = dict(key=key_for(request, revision), symbol=row.symbol, signal_date=day,
                      model=config.model, context=context, request=request)
        packets.append(packet)
        coverage.append(dict(signal_date=day,symbol=row.symbol,price_status=context['price_context']['status'],
                             request_characters=len(encoded(request)),**counts))
    atomic_json(root/'requests.json',packets)
    pd.DataFrame(coverage).to_csv(root/'coverage.csv',index=False)
    sources = {str(p): digest(p) for p in (REFERENCE/'protocol.json',REFERENCE/'signals.csv',
        REFERENCE/'report.json',TAPE/'protocol.json',TAPE/'inputs/manifest.json',
        Path(__file__),Path('service/local_ai/research_veto.py'),Path('service/local_ai/lm_studio.py'))}
    files = {name:digest(root/name) for name in ('prompt.txt','requests.json','signals.parquet','news-snapshot.parquet','coverage.csv')}
    protocol = dict(experiment='LOCAL_QWEN_NEWS_VETO_AFTER_PER_SYMBOL_2025_V1', status='PREPARED',
        prepared_at_utc=datetime.now(timezone.utc).isoformat(), reference=str(REFERENCE), tape=str(TAPE),
        prompt_id=PROMPT, prompt_runtime='local', connection=asdict(config), declared_model_revision=revision,
        structured_output='LM Studio response_format json_schema; no unsupported reasoning control',
        candidates=len(packets), distinct_symbols=len(symbols), with_news=sum(bool(p['context']['news']) for p in packets),
        without_news=sum(not p['context']['news'] for p in packets),
        news_associations_extracted=len(news), corpus_query_truncated=False,
        extraction_scope='Union of candidate seven-day lookbacks, partitioned at month boundaries; SQL exclusive end',
        dossier_limits=dict(news_days=7,max_articles=6,body_characters=3000,price_sessions=60),
        baseline=read(REFERENCE/'protocol.json'),
        veto='UNFAVORABLE + SUFFICIENT + exact bearish quote + model issuer attribution + primary ticker association',
        no_news_or_indeterminate='KEEP_BASELINE', invalid_response='KEEP_BASELINE_AND_MARK_ANALYSIS_INCOMPLETE',
        refill=False, strategy_changed=False, training=False, sql_shared_writes=False,
        cloud_calls=0, local_calls=0, broker_calls=0, strict_pit=False, independent_holdout=False,
        limitations=['Mutable news versions retrieved today, not an historical availability certificate',
            'LLM training-memory look-ahead cannot be excluded',
            'Primary ticker mapping and LLM issuer attribution require content review',
            'Current issuer metadata; survivorship and common OHLC replay limitations',
            'Comparing only these two frozen arms does not validate an economic edge'],
        files=files, sources=sources)
    atomic_json(root/'protocol.json',protocol)
    atomic_json(root/'progress.json',{k:protocol[k] for k in ('status','candidates','distinct_symbols','with_news','without_news','local_calls','cloud_calls')})
    return protocol


def verified(root):
    plan = read(root/'protocol.json')
    for name,sha in plan['files'].items():
        if digest(root/name)!=sha:
            raise ValueError('Dossier figé modifié : '+name)
    for name,sha in plan['sources'].items():
        if digest(Path(name))!=sha:
            raise ValueError('Source figée modifiée : '+name)
    for p in read(root/'requests.json'):
        if p['key']!=key_for(p['request'],plan['declared_model_revision']):
            raise ValueError('Identité de requête incompatible')
    return plan


def refreeze(source, root, *, max_output_tokens=8192, preserve_valid=False, timeout_seconds=None):
    """Change only output budget/transport using sealed inputs, without new SQL."""
    previous = read(source/'protocol.json')
    for name,sha in previous['files'].items():
        if digest(source/name)!=sha:
            raise ValueError('Archive source modifiée : '+name)
    for name,sha in previous['sources'].items():
        if Path(name).suffix!='.py' and digest(Path(name))!=sha:
            raise ValueError('Entrée de référence modifiée : '+name)
    connection = Connection(**{**previous['connection'],'max_output_tokens':max_output_tokens,
        'timeout_seconds':previous['connection'].get('timeout_seconds',300) if timeout_seconds is None else timeout_seconds})
    root.mkdir(parents=True,exist_ok=False)
    for name in ('prompt.txt','news-snapshot.parquet','signals.parquet'):
        shutil.copyfile(source/name,root/name)
    packets = read(source/'requests.json')
    revision = 'qwen3.5-9b-local-20261107-research-v2-structured'
    cached = {}
    if preserve_valid:
        db = sqlite3.connect((source/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        try:
            for key,req,raw,val in db.execute('SELECT a.request_key,a.request_json,a.response_json,a.validation_json '
                    'FROM attempts a JOIN (SELECT request_key,MAX(id) id FROM attempts GROUP BY request_key) b ON a.id=b.id'):
                cached[key] = dict(request=json.loads(req),response=json.loads(raw) if raw else None,validation=json.loads(val))
            target = sqlite3.connect(root/'analyses.sqlite3')
            try:
                db.backup(target)
            finally:
                target.close()
        finally:
            db.close()
    reused = []; changed = []
    for p in packets:
        prior = cached.get(p['key'])
        if prior and prior['validation']['valid']:
            if prior['request']!=p['request'] or key_for(p['request'],previous['declared_model_revision'])!=p['key']:
                raise ValueError('Cache valide incompatible avec la requête figée')
            if prior['response'] is not None:
                if prior['response']['request']!=p['request']:
                    raise ValueError('Requête réelle du cache incompatible')
                validate_response(prior['response'],p)
            elif p['context']['news'] or prior['validation']['veto']:
                raise ValueError('Réponse absente injustifiée dans le cache')
            reused.append(dict(symbol=p['symbol'],signal_date=p['signal_date'],request_key=p['key']))
            continue
        old_key = p['key']
        p['request']['max_tokens'] = max_output_tokens
        p['request']['response_format'] = dict(type='json_schema',json_schema=dict(
            name='issuer_news_veto',strict=True,schema=SCHEMA))
        p['key'] = key_for(p['request'],revision)
        changed.append(dict(symbol=p['symbol'],signal_date=p['signal_date'],old_request_key=old_key,
                            new_request_key=p['key'],previous_error=bool(prior and not prior['validation']['valid'])))
    atomic_json(root/'requests.json',packets)
    coverage = pd.read_csv(source/'coverage.csv')
    sizes = {(p['signal_date'],p['symbol']):len(encoded(p['request'])) for p in packets}
    coverage['request_characters'] = [sizes[(r.signal_date,r.symbol)] for r in coverage.itertuples()]
    coverage.to_csv(root/'coverage.csv',index=False)
    plan = dict(previous, prepared_at_utc=datetime.now(timezone.utc).isoformat(),
        data_snapshot_prepared_at_utc=previous['prepared_at_utc'],
        revised_from_protocol=dict(path=str(source/'protocol.json'),sha256=digest(source/'protocol.json')),
        connection=asdict(connection),declared_model_revision=revision,
        structured_output=f'LM Studio response_format json_schema; new requests output budget {max_output_tokens}; sealed inputs reused without SQL extraction',
        cached_valid_requests_preserved=len(reused),new_or_retried_requests=len(changed),
        local_calls=0,files={n:digest(root/n) for n in previous['files']},
        sources={n:digest(Path(n)) for n in previous['sources']})
    atomic_json(root/'protocol.json',plan)
    atomic_json(root/'budget-amendment.json',dict(previous_protocol_sha256=digest(source/'protocol.json'),
        new_max_output_tokens=max_output_tokens,timeout_seconds=connection.timeout_seconds,
        reused_requests=reused,changed_requests=changed,old_attempts_preserved=preserve_valid,
        only_output_budget_and_request_timeout_changed=True,financial_selection_and_prompt_unchanged=True))
    atomic_json(root/'progress.json',dict(status='PREPARED',candidates=len(packets),local_calls=0,cloud_calls=0))
    return {k:plan[k] for k in ('status','candidates','with_news','without_news','connection')}


def analyze(root,limit=5,retry_errors=False):
    plan = verified(root)
    cache = Cache(root/'analyses.sqlite3')
    client = None; calls = 0; started = time.monotonic()
    try:
        for packet in read(root/'requests.json'):
            prior = cache.latest(packet['key'])
            if prior and (prior['validation']['valid'] or not retry_errors):
                continue
            if not packet['context']['news']:
                cache.put(packet['key'],packet['request'],None,dict(valid=True,veto=False,reason='NO_QUALIFIED_NEWS_KEEP_BASELINE'))
                continue
            if calls>=limit:
                continue
            requested_config = replace(Connection(**plan['connection']),max_output_tokens=packet['request']['max_tokens'])
            if client is None or client.config!=requested_config:
                if client:
                    client.close()
                client = Client(requested_config)
                if client.config.model not in client.models():
                    raise ValueError('Modèle local figé non disponible')
            response = None
            atomic_json(root/'progress.json',dict(status='ANALYZING_LOCAL',local_calls_this_invocation=calls,
                current_symbol=packet['symbol'],current_signal_date=packet['signal_date'],
                request_started_at_utc=datetime.now(timezone.utc).isoformat(),
                max_output_tokens=requested_config.max_output_tokens))
            LOG.info('LLM local début %s %s plafond_sortie=%d',packet['symbol'],packet['signal_date'],requested_config.max_output_tokens)
            try:
                calls += 1
                response = client.chat(packet['request']['messages'],response_format=packet['request'].get('response_format'))
                if response['request']!=packet['request']:
                    raise ValueError('Requête réelle différente du dossier figé')
                validation = validate_response(response,packet)
            except Exception as exc:
                response = getattr(exc,'result',response)
                validation = dict(valid=False,veto=False,error_type=type(exc).__name__,error=str(exc))
            cache.put(packet['key'],packet['request'],response,validation)
            atomic_json(root/'progress.json',dict(status='ANALYZING_LOCAL',local_calls_this_invocation=calls,
                last_symbol=packet['symbol'],last_signal_date=packet['signal_date'],last_valid=validation['valid']))
            if response is None or response.get('finish_reason')=='length':
                # Unavailable server or exhausted output: stop before a cascade.
                break
        decisions = []
        for packet in read(root/'requests.json'):
            value = cache.latest(packet['key'])
            validation = value['validation'] if value else dict(valid=False,veto=False,reason='PENDING')
            decisions.append(dict(symbol=packet['symbol'],signal_date=packet['signal_date'],
                                  request_key=packet['key'],**validation))
        atomic_json(root/'decisions.json',decisions)
        result = dict(status='ANALYSIS_COMPLETE_RESEARCH_ONLY' if all(v['valid'] for v in decisions) else 'ANALYSIS_INCOMPLETE',
            evaluated=sum(v['valid'] for v in decisions),total=len(decisions),vetoes=sum(v['veto'] for v in decisions),
            local_calls_this_invocation=calls,cloud_calls=0,elapsed_seconds=time.monotonic()-started)
        atomic_json(root/'analysis-report.json',result)
        atomic_json(root/'progress.json',result)
        return result
    finally:
        cache.close()
        if client:
            client.close()


def replay(root):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid

    verified(root)
    packets = read(root/'requests.json'); decisions = []
    cache = Cache(root/'analyses.sqlite3')
    try:
        for packet in packets:
            value = cache.latest(packet['key'])
            if not value or not value['validation']['valid']:
                raise ValueError('Analyses incomplètes ou invalides : aucun replay comparatif publié')
            validation = validate_response(value['response'],packet) if value['response'] else value['validation']
            decisions.append(dict(symbol=packet['symbol'],date=packet['signal_date'],veto=validation['veto']))
    finally:
        cache.close()
    grid.verify_inputs(TAPE)
    folder = root/'replay'; folder.mkdir(exist_ok=False)
    grid.initialize_worker(TAPE)  # HTTP disabled from here; no inference during replay.
    base = pd.read_parquet(root/'signals.parquet')
    excluded = {(v['date'],v['symbol']) for v in decisions if v['veto']}
    reports = []
    for name in ('A_REFERENCE','B_LOCAL_VETO'):
        out = folder/name; out.mkdir()
        selected = base.copy()
        if name=='B_LOCAL_VETO':
            selected = selected.loc[[(str(r.trade_date)[:10],r.symbol) not in excluded for r in selected.itertuples()]]
        selected.to_csv(out/'signals.csv',index=False)
        with ReadOnlyReplay(out).install():
            def progress(done,total,day):
                atomic_json(out/'progress.json',dict(status='RUNNING',completed=done,total=total,last_date=day))
            cfg = grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
            result = BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
                high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
                signals_df=selected,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
                winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
            report = metrics(result,4000.)
            if name=='A_REFERENCE':
                original = read(REFERENCE/'report.json')
                for key in ('final_equity','return_pct','max_drawdown_pct','average_gross_capital','costs','margin_interest','closed_lot_trades'):
                    if not np.isclose(report[key],original[key],rtol=1e-10,atol=1e-6):
                        raise ValueError('Référence financière différente : '+key)
            report.update(arm=name,selected_signals=len(selected),excluded_signals=len(base)-len(selected),
                          strict_pit=False,cloud_calls=0,broker_calls=0)
            atomic_json(out/'report.json',report)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.closed_trades_df.to_csv(out/'trades.csv',index=False)
            result.trade_events_df.to_csv(out/'events.csv',index=False)
            reports.append(report)
    pd.DataFrame(reports).to_csv(folder/'comparison.csv',index=False)
    atomic_json(folder/'report.json',dict(status='COMPLETED_EXPLORATORY',arms=reports,strict_pit=False))
    return dict(status='COMPLETED_EXPLORATORY',output=str(folder))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','refreeze','analyze','replay'])
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--from-prepared',type=Path)
    parser.add_argument('--max-output-tokens',type=int,default=8192)
    parser.add_argument('--timeout-seconds',type=int)
    parser.add_argument('--preserve-valid',action='store_true')
    parser.add_argument('--limit',type=int,default=5,help='Maximum local inference attempts this invocation')
    parser.add_argument('--retry-errors',action='store_true')
    args = parser.parse_args()
    if args.limit<1:
        parser.error('limit must be positive')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.phase=='refreeze':
        if args.from_prepared is None:
            parser.error('--from-prepared required for refreeze')
        result = refreeze(args.from_prepared,args.output_dir,max_output_tokens=args.max_output_tokens,
                          preserve_valid=args.preserve_valid,timeout_seconds=args.timeout_seconds)
    elif args.phase=='prepare':
        result = prepare(args.output_dir)
    else:
        with exclusive_run(args.output_dir):
            result = analyze(args.output_dir,args.limit,args.retry_errors) if args.phase=='analyze' else replay(args.output_dir)
    print(encoded({k:v for k,v in result.items() if k not in ('baseline','sources','files','connection','limitations')}))


if __name__=='__main__':
    main()
