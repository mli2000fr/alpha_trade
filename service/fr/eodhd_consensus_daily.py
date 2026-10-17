"""FR-only EODHD consensus: dedicated SQL research tables + raw file receipts.

No Yahoo, US fallback, historical PIT claim, canonical features or serving.
Daily first normalized observation wins; subsequent raw responses stay archived.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import time
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import text

from common.public_data_http import verified_session
from database.repositories.eodhd_consensus import TABLE, persist_rows
from database.router import get_market_engine
from service.eodhd.consensus_snapshot import FIELDS, parse as parse_us
from service.eodhd.clientEodhd import (_do_request, _get_base_url, _get_token,
    _redact_sensitive_text, EodhdPermissionError, EodhdSymbolNotFound)
from service.eodhd.quota import get_default_tracker, EodhdQuotaExceeded, EodhdCircuitOpen
from service.fr.consensus_daily import reference_scope
from service.inpi.files import atomic

ROOT = Path(__file__).resolve().parents[2]
RAW_TABLE = 'eodhd_consensus_raw_payloads'
DDL = ROOT/'database/sql/fr/eodhd_consensus.sql'
VALUE_FIELDS = {'eps_avg','eps_low','eps_high','eps_current','eps_7d_ago','eps_30d_ago',
    'eps_60d_ago','eps_90d_ago','revenue_avg','revenue_low','revenue_high'}


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def engine_fr():
    return get_market_engine('FR_EQ',database_alias='fr_primary')


def check_schema(engine):
    if engine.url.database != 'alpha_trade_fr':
        raise ValueError('Consensus FR limité à alpha_trade_fr, aucun fallback US')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade_fr':
            raise ValueError('Base physique FR contradictoire')
        conn.execute(text(f'SELECT raw_payload_id,isin,market_code,available_at FROM {TABLE} LIMIT 0'))
        conn.execute(text(f'SELECT id,parse_status,available_at FROM {RAW_TABLE} LIMIT 0'))


def install():
    engine=engine_fr()
    try:
        if engine.url.database != 'alpha_trade_fr':
            raise ValueError('Installation réservée à alpha_trade_fr')
        with engine.begin() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade_fr':
                raise ValueError('Base physique FR contradictoire')
            for statement in DDL.read_text(encoding='utf-8').split(';'):
                if statement.strip():
                    conn.execute(text(statement))
        check_schema(engine)
        return dict(status='INSTALLED_FR_RESEARCH_ONLY',database='alpha_trade_fr',tables=[RAW_TABLE,TABLE])
    finally:
        engine.dispose()


def fetch(symbol,session):
    if not isinstance(symbol,str) or not symbol.endswith('.PA') or any(c in symbol for c in '/\\,'):
        raise ValueError('Symbole FR Paris explicite requis')
    return _do_request(endpoint='calendar/trends',url=_get_base_url()+'/calendar/trends',
        params={'api_token':_get_token(),'fmt':'json','symbols':symbol},session=session,
        tracker=get_default_tracker(),feature='fr_consensus_snapshot')


def parse(payload,symbol,reference,observed,run_id,reference_hash):
    if not symbol.endswith('.PA') or reference.get('provider_symbol') != symbol:
        raise ValueError('Identité fournisseur FR contradictoire')
    rows=parse_us(payload,[symbol],observed,run_id)[symbol]
    for row in rows:
        row.update(snapshot_date=observed.astimezone(ZoneInfo('Europe/Paris')).date(),
            market_code='FR_EQ',isin=reference['isin'],reference_sha256=reference_hash,
            parser_version='eodhd_fr_v1',qualification_status='RESEARCH_ONLY',available_at=None)
        # Currency absent in Trends: never infer EUR from the listing venue.
    return rows


def seal(engine,raw_id,now=None):
    # Both raw/normalized records are already durably committed before this stamp.
    stamp=(now or datetime.now(UTC)).astimezone(UTC).replace(tzinfo=None)
    with engine.begin() as conn:
        observed=conn.execute(text(f'SELECT observed_at FROM {RAW_TABLE} WHERE id=:id'),dict(id=raw_id)).scalar_one()
        if not isinstance(observed,datetime):
            observed=datetime.fromisoformat(str(observed))
        if stamp < observed:
            raise ValueError('Horloge reculée, disponibilité consensus non confirmée')
        conn.execute(text(f'UPDATE {RAW_TABLE} SET available_at=:stamp WHERE id=:id '
            "AND available_at IS NULL AND parse_status IN ('READY','EMPTY')"),dict(stamp=stamp,id=raw_id))
        conn.execute(text(f'UPDATE {TABLE} SET available_at=:stamp WHERE raw_payload_id=:id '
            'AND available_at IS NULL'),dict(stamp=stamp,id=raw_id))


def persist(engine,root,symbol,reference,reference_hash,payload,observed,run_id,day):
    payload_json=encoded(payload)
    raw_hash=hashlib.sha256(payload_json.encode()).hexdigest()
    objects=root/'raw'
    obj=objects/f'{raw_hash}.json'
    if not obj.exists():
        atomic(obj,payload)
    if digest(json.loads(obj.read_text(encoding='utf-8'))) != raw_hash:
        raise ValueError('Archive brute consensus EODHD corrompue')
    # atomic() uses a different JSON whitespace layout; bind actual file bytes too.
    receipt=root/'receipts'/f'{run_id}-{symbol}.json'
    atomic(receipt,dict(provider='eodhd',endpoint='/calendar/trends',symbol=symbol,
        observed_at=observed.isoformat(),raw_hash=raw_hash,object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest(),
        reference_identity=reference,reference_sha256=reference_hash,ml_eligible=False))
    stamp=observed.astimezone(UTC).replace(tzinfo=None)
    with engine.begin() as conn:
        inserted=conn.execute(text(f'INSERT INTO {RAW_TABLE} '
            '(provider,symbol,observation_day,run_id,observed_at,available_at,raw_hash,payload_json,parse_status) '
            "VALUES ('eodhd',:symbol,:day,:run,:observed,NULL,:hash,:payload,'RECEIVED')"),
            dict(symbol=symbol,day=day,run=run_id,observed=stamp,hash=raw_hash,payload=payload_json))
        raw_id=inserted.lastrowid
    try:
        rows=parse(payload,symbol,reference,observed,run_id,reference_hash)
        meaningful=any(row[k] is not None for row in rows for k in VALUE_FIELDS)
        status='READY' if meaningful else 'EMPTY'
        for row in rows:
            row['raw_payload_id']=raw_id
        with engine.begin() as conn:
            count=persist_rows(conn,rows)
            conn.execute(text(f'UPDATE {RAW_TABLE} SET parse_status=:status,normalized_rows=:count '
                'WHERE id=:id'),dict(status=status,count=count,id=raw_id))
    except Exception:
        # The complete successful provider response survives parser/SQL failure.
        # RECEIVED stays unsealed, safe to retry; no daily success marker.
        raise
    seal(engine,raw_id)
    return dict(status='COMPLETED' if meaningful else 'NO_COVERAGE',rows=len(rows),
        persisted=count,raw_payload_id=int(raw_id),raw_hash=raw_hash,receipt=str(receipt))


def completed(engine,symbol,day):
    with engine.connect() as conn:
        row=conn.execute(text(f'SELECT id,parse_status,available_at,normalized_rows FROM {RAW_TABLE} '
            "WHERE provider='eodhd' AND symbol=:symbol AND observation_day=:day "
            "AND parse_status IN ('READY','EMPTY') ORDER BY id LIMIT 1"),
            dict(symbol=symbol,day=day)).mappings().first()
    if row is None:
        return None
    if row['available_at'] is None:
        seal(engine,row['id'])
    return dict(status='COMPLETED' if row['parse_status']=='READY' else 'NO_COVERAGE',
        raw_payload_id=int(row['id']),skipped_existing=True)


def collect(cfg,result,*,root,identities,dry_run=False,max_symbols=None,engine=None,
            fetcher=None,sleep=time.sleep):
    if cfg.get('provider') != 'eodhd':
        raise ValueError('Consensus FR Yahoo bloqué, fournisseur eodhd requis')
    total,scope,excluded=reference_scope(identities)
    cap=int(cfg.get('max_symbols_per_run',400))
    budget=int(cfg.get('max_endpoint_calls_per_day',400))
    pace=float(cfg.get('request_interval_seconds',1.1))
    if not 1 <= cap <= 1000 or not 1 <= budget <= 2000 or not 0 <= pace <= 60:
        raise ValueError('Budgets consensus EODHD FR invalides')
    selected=cfg.get('selected_symbols')
    if selected is not None:
        if not selected or len(set(selected)) != len(selected) or not set(selected).issubset(scope):
            raise ValueError('Sélection consensus hors référentiel FR vérifié')
        scope={s:scope[s] for s in selected}
    if max_symbols is not None:
        if not 1 <= max_symbols <= cap:
            raise ValueError('Limite de smoke invalide')
        scope=dict(list(scope.items())[:max_symbols])
    if not scope or len(scope)>cap:
        raise ValueError('Univers FR consensus vide ou au-delà du plafond')
    reference_hash=hashlib.sha256(identities.read_bytes()).hexdigest()
    now=datetime.now(UTC)
    day=now.astimezone(ZoneInfo('Europe/Paris')).date().isoformat()
    storage=root/'eodhd'
    checkpoint=storage/'days'/f'{day}.json'
    result.update(provider='eodhd',requested_count=len(scope),requested_unit='eligible_reference_symbols',
        received_unit='symbols_with_consensus',persisted_unit='new_normalized_fiscal_rows',
        observation_day=day,sql_writes=not dry_run,database='alpha_trade_fr',historical_pit=False,
        total_reference=total,reference_exclusions=excluded,reference_excluded_count=len(excluded),
        universe_sha256=reference_hash,coverage={},errors=[],skipped_completed=0,empty_count=0,
        raw_payloads_persisted=0,identity_qualified=False,checkpoint_path=str(checkpoint))
    if dry_run:
        return
    owned=engine is None
    engine=engine or engine_fr()
    try:
        check_schema(engine)  # Before any API call, no automatic DDL.
        state=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else dict(
            day=day,market_code='FR_EQ',provider='eodhd',universe_sha256=reference_hash,
            endpoint_calls=0,symbols={})
        if (state.get('provider'),state.get('market_code'),state.get('universe_sha256'),state.get('day')) != ('eodhd','FR_EQ',reference_hash,day):
            raise ValueError('Checkpoint consensus FR/EODHD ou référentiel contradictoire')
        run_id='fr-consensus-'+now.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
        result['run_id']=run_id
        with verified_session() as session:
            for symbol,(reference,names) in scope.items():
                prior=completed(engine,symbol,day)
                if prior is None and state['symbols'].get(symbol,{}).get('reason')=='INVALID_PROVIDER_SYMBOL':
                    prior=state['symbols'][symbol]
                if prior:
                    state['symbols'][symbol]=prior
                    result['skipped_completed']+=1
                    continue
                if state['endpoint_calls'] >= budget:
                    result['pause_reason']='EODHD_LOCAL_DAILY_REQUEST_BUDGET'
                    break
                state['endpoint_calls']+=1
                atomic(checkpoint,state)  # Reserve budget before network; crashes cannot reset it.
                try:
                    payload=(fetcher or fetch)(symbol,session)
                    observed=datetime.now(UTC)
                    entry=persist(engine,storage,symbol,reference,reference_hash,payload,observed,run_id,day)
                    state['symbols'][symbol]=entry
                    result['raw_payloads_persisted']+=1
                    result['persisted_count']+=entry['persisted']
                    if entry['status']=='COMPLETED':
                        result['received_count']+=1
                    else:
                        result['empty_count']+=1
                except EodhdSymbolNotFound:
                    state['symbols'][symbol]=dict(status='NO_COVERAGE',reason='INVALID_PROVIDER_SYMBOL')
                    result['empty_count']+=1
                except Exception as exc:
                    message=_redact_sensitive_text(str(exc))[:500]
                    state['symbols'][symbol]=dict(status='FAILED',reason=message,error_type=type(exc).__name__)
                    result['failed_count']+=1
                    result['errors'].append(dict(symbol=symbol,error_type=type(exc).__name__,message=message))
                    if isinstance(exc,(EodhdPermissionError,EodhdQuotaExceeded,EodhdCircuitOpen)):
                        result['pause_reason']=type(exc).__name__
                        break
                finally:
                    atomic(checkpoint,state)
                print(json.dumps(dict(batch='fr_consensus_snapshot',provider='eodhd',symbol=symbol,
                    status=state['symbols'][symbol]['status'],endpoint_calls=state['endpoint_calls']),ensure_ascii=False),flush=True)
                sleep(pace)
        statuses=[state['symbols'].get(s,{}).get('status') for s in scope]
        with engine.connect() as conn:
            result['raw_payloads_persisted']=int(conn.execute(text(
                f'SELECT COUNT(*) FROM {RAW_TABLE} WHERE run_id=:run'),dict(run=run_id)).scalar_one())
        result.update(endpoint_calls_today=state['endpoint_calls'],archived_symbols_today=statuses.count('COMPLETED'),
            coverage_ratio=statuses.count('COMPLETED')/len(scope),
            pending_count=sum(s not in ('COMPLETED','NO_COVERAGE') for s in statuses),
            no_consensus_count=statuses.count('NO_COVERAGE'),symbol_status_counts={s:statuses.count(s) for s in set(statuses) if s},
            coverage_complete=all(s in ('COMPLETED','NO_COVERAGE') for s in statuses))
        state.update(reference_exclusions=excluded,last_result=result)
        atomic(checkpoint,state)
        if result['failed_count'] or result.get('pause_reason') or result['pending_count']:
            raise RuntimeError('Consensus EODHD FR incomplet : '+str(result['errors'][:3] or result.get('pause_reason')))
    finally:
        if owned:
            engine.dispose()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--install-schema',action='store_true')
    modes.add_argument('--smoke',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--symbols',default='OR.PA,SU.PA,BN.PA')
    args=parser.parse_args()
    if args.install_schema:
        report=install()
    else:
        if args.output is None or args.output.exists():
            parser.error('--output doit désigner un nouveau dossier FR')
        output=args.output.resolve()
        if not output.is_relative_to((ROOT/'artifacts/fr').resolve()):
            parser.error('Sortie de smoke hors artifacts/fr')
        from service.fr.operational_batch_15a import load_section
        cfg=load_section('fr_consensus_snapshot',ROOT/'batch_fr.yaml')
        cfg['selected_symbols']=[s.strip() for s in args.symbols.split(',')]
        if not 1 <= len(cfg['selected_symbols']) <= 5:
            parser.error('Smoke limité à cinq titres explicites')
        report=dict(requested_count=0,received_count=0,persisted_count=0,failed_count=0,warning_count=0,
            status='RUNNING',limited_smoke=True,canonical_writes=False,serving_enabled=False)
        try:
            collect(cfg,report,root=output,identities=ROOT/cfg['identities_file'])
            report['status']='SUCCESS'
        except Exception as exc:
            report.update(status='FAILED',error_message=_redact_sensitive_text(str(exc))[:500])
        atomic(output/'report.json',report)
    print(json.dumps(report,ensure_ascii=False,default=str))
    if report.get('status')=='FAILED':
        raise SystemExit(1)
