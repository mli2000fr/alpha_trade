"""FIRDS daily reference observations for the verified FR subset, files only.

Never repairs inherited history gaps or promotes tradability/SQL instruments.
All delta fragments are checked before a new checkpoint can be published.
"""
from __future__ import annotations

import copy
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

from service.fr.eodhd_daily_15b import atomic
from service.fr.esma_firds_download import INDEX_URL, ARCHIVE_HOST, _get_json, _tls_context, _download, _check
from service.fr.esma_firds_history import archive_records, apply_event, _observed_interval, _trading_episodes
from service.fr.operational_collectors_15c import reference

PART = re.compile(r'DLTINS_(\d{8})_(\d+)of(\d+)\.zip\Z')


def validate_index(rows, start, end):
    """Require complete numbered fragments for every indexed day; never infer no publication."""
    by_day = {}
    names = set()
    for row in rows:
        match = PART.fullmatch(row['file'])
        link = urlparse(row['url'])
        if not match or link.scheme != 'https' or link.hostname != ARCHIVE_HOST or not link.path.endswith('/'+row['file']):
            raise ValueError('Fichier/lien ESMA non autorisé')
        day = date.fromisoformat(f'{match[1][:4]}-{match[1][4:6]}-{match[1][6:]}')
        if not start <= day <= end or str(day) != row['date'] or row['file'] in names:
            raise ValueError('Date ou doublon dans index ESMA')
        names.add(row['file'])
        number, total = int(match[2]), int(match[3])
        if not 1 <= number <= total <= 100: raise ValueError('Numérotation ESMA invalide')
        by_day.setdefault(day, []).append((number,total))
    for day, parts in by_day.items():
        totals = {p[1] for p in parts}
        if len(totals)!=1 or sorted(p[0] for p in parts)!=list(range(1,next(iter(totals))+1)):
            raise ValueError('Fragments ESMA incomplets : '+str(day))
    missing=[]
    day=start
    while day<=end:
        if day not in by_day: missing.append(str(day))
        day+=timedelta(days=1)
    return missing


def delta_index(start, end, context):
    rows=[]; offset=0
    while True:
        params=urlencode({'q':'file_type:DLTINS',
            'fq':f'publication_date:[{start}T00:00:00Z TO {end}T23:59:59Z]',
            'wt':'json','start':offset,'rows':1000,'sort':'id asc'})
        response=_get_json(INDEX_URL+'?'+params,context)['response']
        if int(response['numFound'])>1000: raise ValueError('Index quotidien au-delà du budget')
        for item in response['docs']:
            name=item.get('file_name','')
            match=PART.fullmatch(name)
            if not match: continue
            day=f'{match[1][:4]}-{match[1][4:6]}-{match[1][6:]}'
            rows.append({'file':name,'date':day,'type':'DLTINS','url':item.get('download_link',''),
                         'md5':item.get('checksum') or None})
        offset+=len(response['docs'])
        if not response['docs'] or offset>=int(response['numFound']): break
    validate_index(rows,start,end)
    return sorted(rows,key=lambda r:(r['date'],r['file']))


def initial_checkpoint(base, identities, base_hash):
    verified={r['isin'] for r in reference(identities) if r.get('identity_state')=='VERIFIED_RESEARCH'}
    indexed={r['isin']:r for r in base['symbols']}
    if not verified or verified-set(indexed) or not base.get('complete'):
        raise ValueError('Checkpoint initial/identités FR incomplets')
    return {'schema_version':1,'market_code':'FR_EQ', 'end':base['end'],
            'base_sha256':base_hash,'base_end':base['end'],
            'historical_continuity_confirmed':bool(base.get('publication_continuity_confirmed')),
            'historical_missing_days':base.get('missing_delta_days',[]),
            'target_mics':base['target_mics'],
            'symbols':copy.deepcopy([indexed[isin] for isin in sorted(verified)]),
            'files':[], 'anomalies':[], 'canonical_go':False,'tradable_enabled':False,
            'serving_enabled':False, 'scope':'VERIFIED_SUBSET_NOT_FULL_FRENCH_MARKET'}


def advance(prior, paths, *, end, observed_at):
    next_state=copy.deepcopy(prior)
    history={(s['isin'],v['mic']):v['versions'] for s in next_state['symbols'] for v in s['market_reference']}
    isins={s['isin'] for s in next_state['symbols']}
    previous={r['file']:r for r in next_state['files']}
    new_versions=0
    for row, path, proof in paths:
        if row['file'] in previous:
            if previous[row['file']]['sha256']!=proof['sha256']:
                raise ValueError('Correction archive déjà rejouée : revue requise')
            continue
        if row['date']<=prior['end']: continue
        for record in archive_records(path,isins,set(prior['target_mics'])):
            record={**record,'observed_at':observed_at,'available_at':observed_at,
                    'publication_archive_date':row['date']}
            apply_event(history,record,date.fromisoformat(row['date']),row['file'],next_state['anomalies'])
            new_versions+=1
        next_state['files'].append({**row,**proof})
    # Same-day modifications remain visible; their ordering isn't asserted intraday.
    for symbol in next_state['symbols']:
        symbol['market_reference']=[{'mic':mic,'versions':versions,
            'observed_asof_intervals':[window for v in versions if (window:=_observed_interval(v))],
            'trading_episodes':_trading_episodes(versions)}
            for (isin,mic),versions in sorted(history.items()) if isin==symbol['isin']]
    next_state.update(end=str(end),delta_publication_continuity_confirmed=True)
    if str(end)!=prior['end'] or len(next_state['files'])!=len(prior['files']):
        next_state['last_observed_at']=observed_at
    return next_state,new_versions


def collect(cfg,result,*,root,identities,base_path,dry_run=False,today=None):
    day=today or datetime.now(ZoneInfo('Europe/Paris')).date()
    # Day J can still be partial in the catalogue, even after the exchange closes.
    end=day-timedelta(days=1)
    max_days=int(cfg.get('max_catchup_days',31))
    overlap=int(cfg.get('lookback_days',7))
    if not 1<=max_days<=31 or not 1<=overlap<=31: raise ValueError('Fenêtre ESMA 1..31 jours requise')
    base_bytes=base_path.read_bytes()
    base_hash=hashlib.sha256(base_bytes).hexdigest()
    base=json.loads(base_bytes)
    checkpoint_path=root/'checkpoint.json'
    prior=json.loads(checkpoint_path.read_text(encoding='utf-8')) if checkpoint_path.exists() else initial_checkpoint(base,identities,base_hash)
    if prior.get('market_code')!='FR_EQ' or prior.get('base_sha256')!=base_hash:
        raise ValueError('Checkpoint FR/base historique modifiés : audit requis')
    if set(r['isin'] for r in prior['symbols'])!={r['isin'] for r in reference(identities) if r.get('identity_state')=='VERIFIED_RESEARCH'}:
        raise ValueError('Univers modifié : requalification requise')
    last=date.fromisoformat(prior['end'])
    if end<last: raise ValueError('Régression de date du checkpoint interdite')
    if (end-last).days>max_days: raise ValueError('Rattrapage au-delà du budget ; rejeu manuel nécessaire')
    start=max(date.fromisoformat(prior['base_end'])+timedelta(days=1), min(last+timedelta(days=1),end-timedelta(days=overlap)))
    result.update(window=[str(start),str(end)],sql_writes=False,canonical_go=False,
        counter_unit='archives demandées/reçues ; nouvelles versions persistées',
        reference_symbols=len(prior['symbols']),historical_continuity_confirmed=prior['historical_continuity_confirmed'])
    if dry_run: return
    if start>end:
        result.update(received_count=0,persisted_count=0,unchanged=True)
        return
    context=_tls_context()
    items=delta_index(start,end,context)
    missing=validate_index(items,start,end)
    result['requested_count']=len(items)
    limit=int(cfg.get('max_archive_requests',128))
    if not 1<=limit<=256 or len(items)>limit: raise ValueError('Budget archives ESMA dépassé')
    stamp=datetime.now(UTC).isoformat()
    atomic(root/'observations'/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json',
        {'observed_at':stamp,'start':str(start),'end':str(end),'files':items,'missing_days':missing})
    if missing:
        result.update(failed_count=len(missing),missing_publication_days=missing)
        raise ValueError('Publications ESMA absentes/inconnues ; checkpoint non avancé : '+','.join(missing))
    paths=[]
    for item in items:
        print('ESMA archive '+item['file'],flush=True)
        proof=_download(item,root/'archives',context)
        path=root/'archives'/item['date'][:4]/item['file']
        proof={**proof,**_check(path,item['md5'])}
        paths.append((item,path,proof))
        result['received_count']+=1
    state, new_versions=advance(prior,paths,end=end,observed_at=stamp)
    result.update(persisted_count=new_versions,checkpoint_end=str(end),
                  new_anomalies=len(state['anomalies'])-len(prior['anomalies']))
    if result['new_anomalies']:
        result['warning_count']+=result['new_anomalies']
    # Version report first; checkpoint replacement last. Crash -> harmless re-read.
    content=json.dumps(state,ensure_ascii=False,sort_keys=True).encode()
    digest=hashlib.sha256(content).hexdigest()
    atomic(root/'versions'/f'{digest}.json',state)
    atomic(checkpoint_path,state)
    result['checkpoint_path']=str(checkpoint_path)


def main():
    import argparse
    from service.fr.operational_batch_15a import ROOT, OPS, load_section, _handle
    parser=argparse.ArgumentParser(description='Qualification manuelle ESMA FR ; ne change pas enabled ni les tâches Windows')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    cfg=load_section('fr_security_master_sync',ROOT/'batch_fr.yaml')
    result={'batch':'fr_security_master_sync','requested_count':0,'received_count':0,
        'persisted_count':0,'failed_count':0,'warning_count':0,'status':'RUNNING',
        'started_at':datetime.now(UTC).isoformat(),'qualification_only':True}
    try:
        _handle('fr_security_master_sync',cfg,result,dry_run=args.dry_run,today=None)
        result['status']='DRY_RUN' if args.dry_run else 'SUCCESS'
    except Exception as exc:
        result.update(status='FAILED',failed_count=max(1,result['failed_count']),error_message=str(exc))
    result['finished_at']=datetime.now(UTC).isoformat()
    if not args.dry_run:
        path=OPS/'validation_15e'/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json'
        atomic(path,result)
        result['report_path']=str(path)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if result['status']=='FAILED': raise SystemExit(1)


if __name__=='__main__': main()
