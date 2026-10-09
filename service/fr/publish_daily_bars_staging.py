"""Publish archived daily EODHD versions to FR research staging only.

No network or broker. Transactions commit one payload at a time. Existing
versions/timestamps are never replaced, and raw observations are not PIT releases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.router import get_market_engine
from service.fr.eodhd_daily_15b import atomic, symbols_from_identities
from service.fr.load_eodhd_staging import classify_bar

ROOT = Path(__file__).resolve().parents[2]
DATASET = 'eod_daily'
CLASSIFIER = 'fr_daily_staging_v1'


def timestamp(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Timezone required for daily source observation')
    if stamp > datetime.now(UTC):
        raise ValueError('Future source observation')
    return stamp.astimezone(UTC).replace(tzinfo=None)


def prepare(root, symbols, start, end):
    """Validate entire archived payload before any SQL. Invalid payloads quarantined."""
    sessions = set(get_market_calendar('FR_EQ').session_dates(start, end))
    if not sessions or not 0 <= (end-start).days <= 31:
        raise ValueError('Bounded nonempty FR session window required')
    first = {}; errors = []; empty = 0
    for symbol in sorted(symbols):
        key = hashlib.sha256(symbol.encode()).hexdigest()
        for observation in sorted((root/'observations'/key).glob('*.json')):
            try:
                meta = json.loads(observation.read_text(encoding='utf-8'))
                if meta['symbol'] != symbol:
                    raise ValueError('Observation identity mismatch')
                window = [date.fromisoformat(x) for x in meta['window']]
                if len(window) != 2 or window[0] > window[1]:
                    raise ValueError('Malformed observation window')
                if window[1] < start or window[0] > end:
                    continue
                digest = meta['raw_sha256']
                if not re.fullmatch('[0-9a-f]{64}', digest):
                    raise ValueError('Invalid raw hash')
                observed, available = timestamp(meta['observed_at']), timestamp(meta['available_at'])
                if available < observed:
                    raise ValueError('Invalid source availability')
                candidate = {'symbol':symbol, 'digest':digest, 'window':meta['window'],
                             'observed':observed, 'available':available}
                old = first.get(digest)
                if old and (old['symbol'] != symbol or old['window'] != meta['window']):
                    raise ValueError('Raw identity/window conflict')
                if old is None or (available, observed) < (old['available'],old['observed']):
                    first[digest] = candidate
            except (ValueError, TypeError, KeyError, OSError) as exc:
                errors.append({'symbol':symbol, 'observation':observation.name, 'error_type':type(exc).__name__})
    payloads = []
    for digest, meta in sorted(first.items(), key=lambda pair:(pair[1]['available'],pair[0])):
        try:
            raw = root/'raw'/f'{digest}.json'
            content = raw.read_bytes()
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError('Raw hash mismatch')
            payload = json.loads(content)
            if payload['symbol'] != meta['symbol'] or payload['window'] != meta['window']:
                raise ValueError('Raw/observation identity mismatch')
            if not isinstance(payload['rows'],list):
                raise ValueError('Raw rows not a list')
            window_start, window_end = map(date.fromisoformat,meta['window'])
            source_sessions = set(get_market_calendar('FR_EQ').session_dates(window_start,window_end))
            rows = []; seen = set()
            for row in payload['rows']:
                day, quality, fields = classify_bar(row, source_sessions)
                if day in seen or not window_start <= day <= window_end:
                    raise ValueError('Duplicate/out-of-window source date')
                seen.add(day)
                if quality not in ('VALID','ZERO_VOLUME'):
                    raise ValueError('Unqualified source OHLCV')
                if day in sessions:
                    rows.append({'day':day,'quality':quality,**fields})
            if not rows:
                empty += 1; continue
            payloads.append({**meta, 'path':str(raw.resolve()), 'rows':rows,
                             'request_key':':'.join([meta['symbol'],*meta['window']])})
        except (ValueError, TypeError, KeyError, OSError) as exc:
            errors.append({'symbol':meta['symbol'],'raw_sha256':digest,'error_type':type(exc).__name__})
    return payloads, errors, empty


def assert_fr(conn):
    if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade_fr':
        raise ValueError('Publisher refuses any database other than alpha_trade_fr')


def publish_payload(conn, payload, *, run_id, published_at):
    """Caller owns transaction. Progress and all staged rows commit atomically."""
    assert_fr(conn)
    conn.execute(text('''INSERT INTO fr_raw_payloads
        (run_id,provider,dataset,request_key,content_sha256,payload_uri,observed_at,available_at)
        VALUES (:run,'EODHD',:dataset,:key,:hash,:path,:observed,:available)
        ON DUPLICATE KEY UPDATE raw_payload_id=raw_payload_id'''),
        {'run':run_id,'dataset':DATASET,'key':payload['request_key'],'hash':payload['digest'],
         'path':payload['path'],'observed':payload['observed'],'available':payload['available']})
    raw_id = conn.execute(text('''SELECT raw_payload_id FROM fr_raw_payloads
        WHERE provider='EODHD' AND dataset=:dataset AND request_key=:key AND content_sha256=:hash'''),
        {'dataset':DATASET,'key':payload['request_key'],'hash':payload['digest']}).scalar_one()
    checkpoint = conn.execute(text('''SELECT classifier_version,row_count FROM fr_staging_progress
        WHERE provider='EODHD' AND provider_symbol=:symbol AND raw_payload_id=:raw
        AND dataset=:dataset AND status='COMPLETED' FOR UPDATE'''),
        {'symbol':payload['symbol'],'raw':raw_id,'dataset':DATASET}).mappings().first()
    # Date windows may grow later: do not use a checkpoint to skip unimported rows.
    already = set(conn.execute(text('''SELECT session_date FROM fr_provider_bars_staging
        WHERE provider='EODHD' AND provider_symbol=:symbol AND raw_payload_id=:raw'''),
        {'symbol':payload['symbol'],'raw':raw_id}).scalars())
    if checkpoint and checkpoint['classifier_version'] != CLASSIFIER:
        raise ValueError('Existing daily classifier mismatch; explicit requalification required')
    new_rows = [r for r in payload['rows'] if r['day'] not in already]
    if new_rows:
        conn.execute(text('''INSERT INTO fr_provider_bars_staging
            (provider,provider_symbol,session_date,raw_payload_id,open_price,high_price,low_price,
             close_price,provider_adjusted_close,provider_volume_split_adjusted,quality_code,observed_at,available_at)
            VALUES ('EODHD',:symbol,:day,:raw,:open,:high,:low,:close,:adjusted,:volume,:quality,:observed,:available)
            ON DUPLICATE KEY UPDATE raw_payload_id=raw_payload_id'''),
            [{**r,'symbol':payload['symbol'],'raw':raw_id,'observed':payload['observed'],
              'available':max(published_at,payload['available'])} for r in new_rows])
    total = conn.execute(text('''SELECT COUNT(*) AS total,
        SUM(quality_code='VALID') AS valid FROM fr_provider_bars_staging
        WHERE provider='EODHD' AND provider_symbol=:symbol AND raw_payload_id=:raw'''),
        {'symbol':payload['symbol'],'raw':raw_id}).mappings().one()
    conn.execute(text('''INSERT INTO fr_staging_progress
        (provider,provider_symbol,raw_payload_id,dataset,classifier_version,row_count,valid_count,status,completed_at)
        VALUES ('EODHD',:symbol,:raw,:dataset,:classifier,:rows,:valid,'COMPLETED',:now)
        ON DUPLICATE KEY UPDATE completed_at=IF(row_count<>VALUES(row_count),VALUES(completed_at),completed_at),
        row_count=VALUES(row_count),valid_count=VALUES(valid_count),status='COMPLETED' '''),
        {'symbol':payload['symbol'],'raw':raw_id,'dataset':DATASET,'classifier':CLASSIFIER,
         'rows':total['total'],'valid':total['valid'] or 0,'now':published_at})
    return len(new_rows)


def run(*, start, end, write=False, root=None, identities=None, output=None, selected_symbols=None):
    root = (root or ROOT/'artifacts/fr/operations/eodhd_daily').resolve()
    identities = (identities or ROOT/'artifacts/fr/sprint6c_reference/identities.jsonl.gz').resolve()
    if not all(p.is_relative_to((ROOT/'artifacts/fr').resolve()) for p in (root,identities)):
        raise ValueError('Daily publication source outside FR artifacts')
    if output is not None:
        output = output.resolve()
        if not output.is_relative_to((ROOT/'artifacts/fr').resolve()) or output.exists():
            raise ValueError('New FR report path required')
    root.mkdir(parents=True,exist_ok=True)
    lock=root/'.publish.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(fd,'w') as stream: stream.write(str(os.getpid()))
    engine=None; run_id='fr-daily-staging-'+uuid.uuid4().hex
    result={'market_code':'FR_EQ','database':'alpha_trade_fr','sql_writes':write,
            'canonical_writes':False,'serving_enabled':False,'run_id':run_id,
            'status':'RUNNING',
            'window':[str(start),str(end)],'new_staging_rows':0,'unchanged_staging_rows':0,
            'committed_payloads':0,'failed_payloads':0}
    try:
        symbols=symbols_from_identities(identities)
        if selected_symbols is not None:
            if (not selected_symbols or len(selected_symbols)!=len(set(selected_symbols))
                    or not set(selected_symbols).issubset(symbols)):
                raise ValueError('Publication subset outside verified daily FR universe')
            symbols=sorted(selected_symbols)
        result['selected_symbol_count']=len(symbols)
        payloads,errors,empty=prepare(root,symbols,start,end)
        result.update(candidate_payloads=len(payloads),candidate_rows=sum(len(p['rows']) for p in payloads),
                      source_errors=errors,empty_or_outside_payloads=empty)
        from service.fr.collection_coverage_remediation import audit_files
        coverage=audit_files(symbols,get_market_calendar('FR_EQ').session_dates(start,end),daily_root=root)
        result['source_file_coverage']={k:coverage[k] for k in (
            'expected_symbol_sessions','present_symbol_sessions','coverage_pct',
            'current_response_confirmed_symbol_sessions','current_response_confirmed_coverage_pct',
            'missing','retained_rows_not_reconfirmed','malformed_or_unverifiable')}
        result['coverage_is_not_canonical_release']=True
        if not write:
            result['status']='PREVIEW'; return result
        if not payloads:
            raise ValueError('No validated daily payload to publish')
        engine=get_market_engine('FR_EQ',database_alias='fr_primary')
        now=datetime.now(UTC).replace(tzinfo=None)
        config_hash=hashlib.sha256(json.dumps({'classifier':CLASSIFIER,'window':result['window'],'symbols':symbols,
                     'universe_sha256':hashlib.sha256(identities.read_bytes()).hexdigest()},sort_keys=True).encode()).hexdigest()
        with engine.begin() as conn:
            assert_fr(conn)
            conn.execute(text('''INSERT INTO fr_ingestion_runs
                (run_id,provider,dataset,status,requested,received,effective_config_hash,started_at)
                VALUES (:run,'EODHD',:dataset,'RUNNING',:count,:count,:hash,:now)'''),
                {'run':run_id,'dataset':DATASET,'count':len(payloads),'hash':config_hash,'now':now})
        for index,payload in enumerate(payloads,1):
            try:
                with engine.begin() as conn:
                    added=publish_payload(conn,payload,run_id=run_id,published_at=datetime.now(UTC).replace(tzinfo=None))
                result['new_staging_rows']+=added
                result['unchanged_staging_rows']+=len(payload['rows'])-added
                result['committed_payloads']+=1
            except Exception as exc:
                result['failed_payloads']+=1
                result.setdefault('sql_errors',[]).append({'symbol':payload['symbol'],'error_type':type(exc).__name__})
            if output:
                atomic(output.with_name(output.stem+'.progress.json'),result)
            if index%50==0:
                print(f"FR staging {index}/{len(payloads)} nouveaux={result['new_staging_rows']} échecs={result['failed_payloads']}",flush=True)
        result['status']='FAILED' if errors or result['failed_payloads'] else 'COMPLETED'
        with engine.begin() as conn:
            assert_fr(conn)
            conn.execute(text('''UPDATE fr_ingestion_runs SET status=:status,persisted=:rows,failed=:failed,
                warnings=:warnings,details_json=:details,finished_at=:now WHERE run_id=:run'''),
                {'status':result['status'],'rows':result['new_staging_rows'],'failed':result['failed_payloads']+len(errors),
                 'warnings':len(errors)+len(coverage['missing'])+len(coverage['retained_rows_not_reconfirmed'])+len(coverage['malformed_or_unverifiable']),
                 'details':json.dumps(result,default=str),'now':datetime.now(UTC).replace(tzinfo=None),'run':run_id})
        return result
    except Exception as exc:
        result.update(status='FAILED',error_type=type(exc).__name__)
        # Infrastructure failures remain failures, including when the final
        # status write fails. No successful report is manufactured.
        if engine:
            try:
                with engine.begin() as conn:
                    assert_fr(conn)
                    conn.execute(text('''UPDATE fr_ingestion_runs SET status='FAILED',failed=:failed,
                        persisted=:rows,details_json=:details,finished_at=:now WHERE run_id=:run'''),
                        {'failed':max(1,result['failed_payloads']),'rows':result['new_staging_rows'],
                         'details':json.dumps(result,default=str),'now':datetime.now(UTC).replace(tzinfo=None),'run':run_id})
            except Exception:
                result['final_run_status_not_confirmed']=True
        raise RuntimeError('FR staging publication failed: '+type(exc).__name__) from None
    finally:
        if engine: engine.dispose()
        lock.unlink(missing_ok=True)
        if output: atomic(output,result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=date.fromisoformat,required=True)
    parser.add_argument('--end',type=date.fromisoformat,required=True)
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(**vars(args)); print(json.dumps(result,ensure_ascii=True))
    if result['status']=='FAILED': raise SystemExit(1)


if __name__=='__main__': main()
