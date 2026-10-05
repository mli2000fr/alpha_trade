"""Resumable all-public structured account collection; always quarantined."""
from datetime import UTC, datetime, timedelta
import gzip
import hashlib
import json
import time

from service.inpi.files import atomic
from service.inpi.accounts_pilot import ROOT
from service.inpi.client import InpiClient, InpiError
from service.inpi.secure_collection import ArchiveClient, DocumentExcluded
from service.inpi.universe_mapping import valid_siren


class QuotaPause(RuntimeError): pass


def validate(manifest):
    reference=ROOT/manifest['identity_reference']
    if reference.resolve()!=(ROOT/'artifacts/fr/sprint6c_reference/identities.jsonl.gz').resolve():
        raise ValueError('Référentiel FR inattendu')
    if hashlib.sha256(reference.read_bytes()).hexdigest()!=manifest['reference_sha256']:
        raise ValueError('Référentiel modifié : mapping à refaire')
    with gzip.open(reference,'rt',encoding='utf-8') as stream:
        identities={(r['provider_symbol'],r['isin']) for r in (json.loads(s) for s in stream if s.strip())
                    if r.get('identity_state')=='VERIFIED_RESEARCH'}
    issuers=manifest['issuers']; seen=set()
    evidence_path=ROOT/'artifacts/fr/operations/fr_fundamentals_sync/mapping/mapping_report.json'
    if manifest.get('mapping_report')!=str(evidence_path): raise ValueError('Preuve mapping hors périmètre')
    evidence=json.loads(evidence_path.read_text(encoding='utf-8'))
    proven={(r['symbol'],r['isin']):r for r in evidence['rows'] if r['status']=='VERIFIED'}
    if len(issuers)>len(identities): raise ValueError('Manifeste hors univers')
    for issuer in issuers:
        key=(issuer['symbol'],issuer['isin'])
        if key not in identities or key in seen or not valid_siren(issuer['siren']):
            raise ValueError('Correspondance invalide/dupliquée')
        if issuer.get('status')!='VERIFIED' or not issuer.get('name_aliases'):
            raise ValueError('Correspondance non vérifiée')
        proof=proven.get(key,{})
        if any(issuer.get(field)!=proof.get(field) for field in ('siren','lei','name_aliases','mapping_state')):
            raise ValueError('Manifeste divergent de la preuve mapping')
        observed=datetime.fromisoformat(issuer['observed_at'])
        age=datetime.now(UTC)-observed
        if not timedelta(0)<=age<=timedelta(days=30):
            raise ValueError('Mapping périmé ou futur : relancer universe_mapping --refresh')
        seen.add(key)


def collect(cfg,result,*,root,manifest_path,dry_run=False,max_symbols=None,client=None):
    if cfg.get('collection_mode')!='quarantine_only' or cfg.get('canonical_writes_enabled') is not False or cfg.get('serving_enabled') is not False:
        raise ValueError('Collecte INPI exclusivement en quarantaine')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')); validate(manifest)
    budget=cfg.get('max_requests_per_run',500); daily=cfg.get('max_requests_per_day',2000)
    cap=cfg.get('max_issuers_per_run',25); refresh=cfg.get('refresh_days',7)
    byte_budget=cfg.get('max_archive_bytes_per_run',134217728)
    pace=cfg.get('request_interval_seconds',.25)
    if any(type(v) is not int for v in (budget,daily,cap,refresh,byte_budget)) or not (
        10<=budget<=1000 and budget<=daily<=5000 and 1<=cap<=330 and 1<=refresh<=90 and
        1<=byte_budget<=134217728 and .2<=pace<=60): raise ValueError('Budgets INPI invalides')
    if max_symbols is not None: cap=min(cap,max_symbols)
    if cap<1: raise ValueError('Limite émetteurs invalide')
    result.update(collection_mode='quarantine_only',ml_usable=False,historical_pit_qualified=False,
                  scope='VERIFIED_SUBSET_OF_ALL_LOCAL_FR_IDENTITIES',eligible_issuers=len(manifest['issuers']),
                  mapping_report=manifest.get('mapping_report'),quarantined_count=0)
    if dry_run: result['requested_count']=min(cap,len(manifest['issuers'])); return
    state_path=root/'collection_state.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'issuers':{}}
    state.setdefault('issuers',{})
    now=datetime.now(UTC)
    selected=[]
    ordered=sorted(manifest['issuers'],key=lambda i:bool(state['issuers'].get(i['isin']+'-'+i['siren'],{}).get('completed_at')))
    # Never-completed/checkpointed issuers first: weekly refresh must not starve the tail of the universe.
    for issuer in ordered:
        key=issuer['isin']+'-'+issuer['siren']; previous=state['issuers'].get(key,{})
        if previous.get('completed_at') and now-datetime.fromisoformat(previous['completed_at'])<timedelta(days=refresh): continue
        if previous.get('completed_at'): previous={}
        state['issuers'][key]=previous
        selected.append((key,issuer,previous))
        if len(selected)>=cap: break
    result['requested_count']=len(selected)
    client=client or InpiClient(username_env=cfg.get('username_env','INPI_USERNAME'),password_env=cfg.get('password_env','INPI_PASSWORD'))
    ledger_path=root/'request_quota.json'
    def guard():
        if client.calls>=budget: raise QuotaPause('RUN_CALL_BUDGET')
        day=datetime.now(UTC).date().isoformat()
        ledger=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {}
        count=ledger.get('reserved_calls',0) if ledger.get('day_utc')==day else 0
        if count>=daily: raise QuotaPause('UTC_DAILY_CALL_BUDGET')
        # Reserve before sending: crashes/errors still consume a request allowance.
        atomic(ledger_path,{'day_utc':day,'reserved_calls':count+1,'daily_limit':daily})
        time.sleep(pace)
    client.request_guard=guard
    archive=ArchiveClient(client,manifest,root,max_requests=budget+1,max_bytes=byte_budget)
    folder=root/'observations'/now.strftime('%Y%m%dT%H%M%S%fZ'); folder.mkdir(parents=True,exist_ok=False)
    def save():
        state.update(updated_at=datetime.now(UTC).isoformat(),canonical_go=False,ml_usable=False)
        atomic(folder/'quarantine_manifest.json',{'documents':archive.observations,
               'qualification_state':'QUARANTINED_UNQUALIFIED','canonical_go':False,'ml_usable':False})
        atomic(state_path,state)
        result.update(received_count=len(archive.observations),persisted_count=len(archive.observations),
            quarantined_count=len(archive.observations),new_objects_count=archive.new_documents,
            provider_calls=client.calls,quarantine_manifest=str(folder/'quarantine_manifest.json'),
            collection_state=str(state_path),counter_units='requested=issuers; received/persisted=public structured account observations')
    try:
        if selected: archive.login()
        for key,issuer,checkpoint in selected:
            checkpoint.setdefault('rows',{}); checkpoint.setdefault('done_ids',[])
            checkpoint.setdefault('skipped_documents',[]); checkpoint.setdefault('seen_cursors',[])
            checkpoint['last_error']=None
            try:
                while not checkpoint.get('list_complete'):
                    rows,cursor=archive.accounts(issuer['siren'],kind='bilans-saisis',page_size=10,
                                                search_after=checkpoint.get('cursor'))
                    if not rows and cursor: raise InpiError('Page vide avec curseur')
                    for row in rows:
                        if not row.get('id'): raise InpiError('Référence sans ID')
                        checkpoint['rows'][row['id']]=row
                    if cursor:
                        if cursor in checkpoint['seen_cursors']: raise InpiError('Curseur INPI répété')
                        checkpoint['seen_cursors'].append(cursor)
                    checkpoint.update(cursor=cursor,list_complete=not bool(cursor)); save()
                for identifier,row in checkpoint['rows'].items():
                    if identifier in checkpoint['done_ids']: continue
                    if row.get('deleted') or row.get('confidentiality')!='Public':
                        checkpoint['skipped_documents'].append({'id':identifier,'reason':'WITHDRAWN_OR_NON_PUBLIC'})
                    else:
                        # Store before checkpoint; a crash can replay an observation, never duplicate an object.
                        try: archive.account(identifier)
                        except DocumentExcluded as exc:
                            checkpoint['skipped_documents'].append({'id':identifier,'reason':str(exc)})
                            result['warning_count']=result.get('warning_count',0)+1
                    checkpoint['done_ids'].append(identifier); save()
                checkpoint['completed_at']=datetime.now(UTC).isoformat(); save()
                print(json.dumps({'symbol':issuer['symbol'],'status':'COLLECTED_QUARANTINE',
                                  'references':len(checkpoint['rows'])}),flush=True)
            except QuotaPause: raise
            except InpiError as exc:
                checkpoint['last_error']=str(exc); result['failed_count']+=1; save()
                if 'HTTP 429' in str(exc): raise QuotaPause('PROVIDER_RATE_LIMIT') from None
        result['completed_this_run']=sum(bool(c.get('completed_at')) for _,_,c in selected)
    except QuotaPause as exc:
        result['pause_reason']=str(exc)
    finally:
        archive.close(); save()
    result['pending_issuers']=sum(not state['issuers'].get(i['isin']+'-'+i['siren'],{}).get('completed_at') for i in manifest['issuers'])
    result['coverage_complete']=result['pending_issuers']==0
    if result['failed_count']: raise InpiError('Échecs INPI ; reprise conservée dans collection_state.json')
