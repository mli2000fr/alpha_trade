"""FR daily vendor/public observations. Files only; no canonical SQL promotion."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse
import uuid
from zoneinfo import ZoneInfo

from service.fr.eodhd_daily_15b import atomic, symbols_from_identities
from service.fr.eodhd_backfill import _fetch
from service.fr.event_data_qualification_11b import CATALOG, fetch, parse_positions, public_day

DILA = 'https://www.info-financiere.gouv.fr/api/explore/v2.0/catalog/datasets/flux-amf-new-prod/exports/json'


def reference(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def window(cfg, today=None):
    end = today or datetime.now(ZoneInfo('Europe/Paris')).date()
    lookback = int(cfg.get('lookback_days', 7))
    if not 1 <= lookback <= 31:
        raise ValueError('Fenêtre FR invalide : 1..31 jours')
    return end-timedelta(days=lookback), end


def archive(root, payload):
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = root/'raw'/f'{digest}.json'
    if not path.exists():
        atomic(path, payload)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('Archive FR corrompue')
    return digest


def observe(root, payload):
    stamp = datetime.now(UTC)
    atomic(root/'observations'/f'{stamp:%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json',
           {'observed_at':stamp.isoformat(), 'available_at':stamp.isoformat(), **payload})


def validate_actions(rows, kind, start, end):
    prepared=[]
    seen=set()
    for row in rows:
        day=date.fromisoformat(str(row.get('date','')))
        if not start <= day <= end:
            raise ValueError('Action fournisseur hors fenêtre')
        if kind == 'splits':
            parts=str(row.get('split','')).split('/')
            if len(parts) != 2:
                raise ValueError('Ratio split absent/invalide')
            numbers=[Decimal(p) for p in parts]
        else:
            numbers=[Decimal(str(row.get('value')))]
        if any(not n.is_finite() or n <= 0 for n in numbers):
            raise ValueError('Valeur action invalide')
        key=json.dumps(row,sort_keys=True)
        if key in seen:
            raise ValueError('Action fournisseur dupliquée')
        seen.add(key)
        prepared.append(row)
    return prepared


def corporate(cfg, result, *, root, identities, dry_run=False, today=None, resume=False, max_symbols=None):
    start,end=window(cfg,today)
    symbols=symbols_from_identities(identities)
    if max_symbols is not None:
        if max_symbols < 1: raise ValueError('max_symbols doit être positif')
        symbols=symbols[:max_symbols]
    pace=float(cfg.get('request_interval_seconds',0.5))
    if not 0.1 <= pace <= 60 or len(symbols) > int(cfg.get('max_symbol_requests',400)):
        raise ValueError('Budget/cadence FR invalide')
    result.update(requested_count=2*len(symbols),window=[str(start),str(end)],sql_writes=False,
                  counter_unit='payloads titre/type',unchanged_count=0,changed_count=0,resumed_count=0,errors=[])
    if dry_run: return
    token=os.environ.get('EODHD_API_TOKEN')
    if not token: raise ValueError('EODHD_API_TOKEN absent')
    state_path=root/'windows'/f'{start}_{end}.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'payloads':{}}
    for symbol in symbols:
        for kind in ('div','splits'):
            key=hashlib.sha256(f'{symbol}:{kind}'.encode()).hexdigest()
            latest=root/'latest'/f'{key}.json'
            prior=state['payloads'].get(key,{})
            if resume and prior.get('status') == 'COMPLETED' and latest.exists():
                raw=root/'raw'/f"{prior['sha256']}.json"
                if (raw.exists() and hashlib.sha256(raw.read_bytes()).hexdigest()==prior['sha256']
                    and hashlib.sha256(latest.read_bytes()).hexdigest()==prior.get('latest_sha256')):
                    result['resumed_count']+=1
                    continue
            try:
                rows=_fetch(f'{kind}/{quote(symbol,safe=".")}',token,{'from':str(start),'to':str(end)},pace=pace)
                result['received_count']+=1
                digest=archive(root,{'symbol':symbol,'kind':kind,'window':[str(start),str(end)],'rows':rows})
                observe(root,{'symbol':symbol,'kind':kind,'raw_sha256':digest,'window':[str(start),str(end)]})
                rows=validate_actions(rows,kind,start,end)
                old=json.loads(latest.read_text(encoding='utf-8')) if latest.exists() else {'events':{}}
                current={d:v for d,v in old['events'].items() if not str(start)<=d<=str(end)}
                for row in rows:
                    current.setdefault(row['date'],[]).append(row)
                for events in current.values(): events.sort(key=lambda r:json.dumps(r,sort_keys=True))
                changed=current!=old['events']
                if changed or not latest.exists():
                    atomic(latest,{'market_code':'FR_EQ','symbol':symbol,'kind':kind,'events':current,
                        'raw_sha256':digest,'available_at':datetime.now(UTC).isoformat(),
                        'evidence_state':'VENDOR_OBSERVATION_NOT_VALIDATED_CORPORATE_ACTION'})
                    result['persisted_count']+=1
                    result['changed_count']+=int(bool(old.get('events')) and changed)
                else: result['unchanged_count']+=1
                state['payloads'][key]={'status':'COMPLETED','sha256':digest,
                    'latest_sha256':hashlib.sha256(latest.read_bytes()).hexdigest()}
            except Exception as exc:
                result['failed_count']+=1
                result['errors'].append({'symbol':symbol,'kind':kind,'error':str(exc)[:240]})
                state['payloads'][key]={'status':'FAILED'}
            atomic(state_path,state)
        print(f'FR actions {symbol}: reçus={result["received_count"]} persistés={result["persisted_count"]} échecs={result["failed_count"]}',flush=True)
    if result['failed_count']: raise RuntimeError('Collecte actions FR partiellement en échec ; reprise disponible')


def public_collection(name,cfg,result,*,root,identities,dry_run=False,today=None):
    start,end=window(cfg,today)
    isins={r['isin'] for r in reference(identities) if r.get('identity_state')=='VERIFIED_RESEARCH'}
    result.update(requested_count=1,window=[str(start),str(end)],sql_writes=False,
                  counter_units='demandés/reçus=exports; persistés=enregistrements uniques modifiés')
    if dry_run: return
    if name=='fr_amf_short_sync':
        catalog=json.loads(fetch(CATALOG))
        resources=[r for r in catalog['resources'] if r.get('format','').lower()=='csv']
        if len(resources)!=1: raise ValueError('Ressource CSV AMF absente/ambiguë')
        url=resources[0]['url']
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in ('www.data.gouv.fr','static.data.gouv.fr','data.gouv.fr','object-api.infra.data.gouv.fr'):
            raise ValueError('Hôte CSV AMF non qualifié')
        raw=fetch(url)
        digest=archive(root,{'catalog':catalog,'csv_utf8':raw.decode('utf-8-sig')})
        rows,rejected=parse_positions(raw)
        rows=[{k:v for k,v in r.items() if k!='source_line'} for r in rows if r['isin'] in isins]
        result.update(source_url=url,license=catalog.get('license'),source_rejected_count=len(rejected))
        # Known historical malformed rows are quarantined, not erased or advertised as current failures.
        atomic(root/'quarantine'/f'{digest}.json',{'rejected':rejected})
        scope='FULL_CURRENT_RECONSTRUCTED_EXPORT_NOT_HISTORICAL_VINTAGE'
    else:
        where=f"uin_dat_amf >= '{start}' AND uin_dat_amf < '{end+timedelta(days=1)}'"
        payload=json.loads(fetch(DILA+'?'+urlencode({'where':where})))
        if not isinstance(payload,list): raise ValueError('Export DILA non liste')
        digest=archive(root,{'query_window':[str(start),str(end)],'records':payload})
        rows=[]; rejected=[]; sentinel_count=0
        for r in payload:
            if r.get('identificationsociete_iso_cd_isi') not in isins: continue
            sentinel_count += int(any(str(r.get(k, '')).startswith(('8887-', '8888-'))
                for k in ('uin_dat_amf','uin_dat_mar','informationdeposee_inf_dat_emt')))
            if not r.get('uin_idt_uin') or not public_day(r) or public_day(r)>str(end):
                rejected.append(r); continue
            rows.append(r)
        result['warning_count']+=int(bool(rejected))
        result['rejected_count']=len(rejected)
        result['date_sentinel_count']=sentinel_count
        result['date_notice']='Known DILA date sentinels excluded; valid transmission is not proven web availability'
        atomic(root/'quarantine'/f'{digest}.json',{'rejected':rejected})
        scope='METADATA_ONLY_NO_DOCUMENT_OR_GUIDANCE_EXTRACTION'
    result['received_count']=1
    observe(root,{'raw_sha256':digest,'window':[str(start),str(end)],'scope':scope})
    latest=root/'latest.json'
    prior=json.loads(latest.read_text(encoding='utf-8')) if latest.exists() else {'records':{}}
    # AMF full export replaces the view; DILA window merges versions by full-content hash.
    current={} if name=='fr_amf_short_sync' else dict(prior['records'])
    for row in rows:
        key=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        current[key]=prior['records'].get(key) or {'row':row,'raw_sha256':digest,'available_at':datetime.now(UTC).isoformat()}
    result['persisted_count']=sum(k not in prior['records'] for k in current)
    result['removed_count']=len(set(prior['records'])-set(current))
    result['unique_records']=len(current)
    atomic(latest,{'market_code':'FR_EQ','records':current,'scope':scope,'raw_sha256':digest})


def quality(cfg,result,*,operations,dry_run=False,today=None):
    now=datetime.now(UTC)
    checks=[]
    names=[n for n in cfg['collection_dependencies'] if n!='fr_pit_quality_daily']
    allowed={'fr_daily_bars_sync','fr_corporate_actions_sync','fr_amf_short_sync','fr_dila_disclosures_sync'}
    if not names or any(n not in allowed for n in names):
        raise ValueError('Dépendance de supervision FR non autorisée')
    for name in names:
        paths=sorted((operations/'runs'/name).glob('*.json'),reverse=True)
        row=json.loads(paths[0].read_text(encoding='utf-8')) if paths else None
        stamp=datetime.fromisoformat(row['finished_at']) if row else None
        age=(now-stamp).total_seconds()/3600 if stamp else None
        ok=bool(row and row['status']=='SUCCESS' and not row.get('limited_smoke') and age is not None and 0<=age<=float(cfg['max_run_age_hours']))
        checks.append({'batch':name,'last_status':row.get('status') if row else None,'age_hours':age,'ok':ok})
    result.update(requested_count=len(checks),received_count=len(checks),checks=checks,
                  failed_count=sum(not c['ok'] for c in checks),scope='LOCAL_COLLECTOR_RUNS_NOT_SQL_PIT_CERTIFICATION')
    if not dry_run:
        atomic(operations/'quality'/f'{now:%Y%m%dT%H%M%S%fZ}.json',{'checks':checks,'observed_at':now.isoformat()})
        result['persisted_count']=len(checks)
    if result['failed_count']: raise RuntimeError(f'{result["failed_count"]} collecte(s) FR absente(s), ancienne(s) ou en échec')
