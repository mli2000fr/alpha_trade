"""Current ISIN/LEI/SIREN evidence, strict exclusions and resumable public lookup."""
import argparse
from collections import Counter
from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
import urllib.request
import uuid

from service.inpi.files import atomic
from service.inpi.accounts_pilot import ROOT, normal_name
from service.inpi.client import NoRedirect

BASE='https://api.gleif.org/api/v1/'
DEFAULT_ROOT=ROOT/'artifacts/fr/operations/fr_fundamentals_sync/mapping'


def valid_siren(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{9}',value): return False
    digits=[int(x) for x in value]
    return sum((2*d//10+2*d%10) if n%2 else d for n,d in enumerate(digits))%10==0


def registry_siren(value):
    if not isinstance(value,str) or not re.fullmatch(r'(?:\d{9}|\d{3}\s\d{3}\s\d{3})',value): return None
    return re.sub(r'\s','',value)


def evaluate(payload, isin):
    rows=payload.get('data',[])
    total=payload.get('meta',{}).get('pagination',{}).get('total')
    if total!=len(rows): return None,'INCOMPLETE_OR_MALFORMED_GLEIF_RESULTS'
    if not rows: return None,'NO_GLEIF_ISIN_MATCH'
    if len(rows)!=1: return None,'AMBIGUOUS_MULTIPLE_LEI'
    attrs=rows[0].get('attributes',{}); entity=attrs.get('entity',{}); registration=attrs.get('registration',{})
    if not re.fullmatch(r'[A-Z0-9]{20}',attrs.get('lei','')): return None,'INVALID_LEI'
    if entity.get('jurisdiction')!='FR': return None,'NON_FR_LEGAL_ENTITY'
    if entity.get('category')!='GENERAL': return None,'NON_GENERAL_ENTITY_OR_BRANCH'
    if entity.get('status')!='ACTIVE': return None,'INACTIVE_LEGAL_ENTITY'
    if registration.get('status')!='ISSUED': return None,'LEI_NOT_CURRENTLY_ISSUED'
    registry=entity.get('registeredAt',{}).get('id')
    if registry not in ('RA000189','RA000192'): return None,'UNQUALIFIED_FR_REGISTRY'
    siren=registry_siren(entity.get('registeredAs'))
    if not valid_siren(siren): return None,'INVALID_SIREN_CHECKSUM'
    if (registration.get('corroborationLevel')!='FULLY_CORROBORATED' or
        registration.get('validatedAt',{}).get('id') not in ('RA000189','RA000192') or registry_siren(registration.get('validatedAs'))!=siren):
        return None,'REGISTRY_VALIDATION_NOT_CORROBORATED'
    name=entity.get('legalName',{}).get('name')
    if not isinstance(name,str) or not name.strip(): return None,'MISSING_LEGAL_NAME'
    aliases=[name]+[n['name'] for n in entity.get('otherNames',[]) if n.get('name')]
    return {'isin':isin,'lei':attrs['lei'],'siren':siren,'issuer':name,'name_aliases':aliases,
            'registry':registry,'lei_updated_at':registration.get('lastUpdateDate'),
            'mapping_state':'VERIFIED_CURRENT_GLEIF_NOT_HISTORICAL_PIT'},None


class Gleif:
    def __init__(self,budget=1200,pace=.25):
        self.calls=0; self.budget=budget; self.pace=pace
        self.opener=urllib.request.build_opener(NoRedirect())

    def get(self,path):
        if self.calls>=self.budget: raise RuntimeError('MAPPING_CALL_BUDGET')
        if not re.fullmatch(r'lei-records(?:/[A-Z0-9]{20}/isins)?\?[^\s]+',path):
            raise ValueError('Endpoint GLEIF refusé')
        self.calls+=1; time.sleep(self.pace)
        request=urllib.request.Request(BASE+path,headers={'Accept':'application/json','User-Agent':'AlphaTrade-FR-mapping/1.0'})
        with self.opener.open(request,timeout=30) as response:
            raw=response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024: raise ValueError('Réponse GLEIF hors budget')
            return json.loads(raw),hashlib.sha256(raw).hexdigest()


def lookup(client,isin):
    source= 'lei-records?'+urlencode({'filter[isin]':isin,'page[size]':10})
    data,digest=client.get(source)
    candidate,reason=evaluate(data,isin)
    if reason: return {'isin':isin,'status':'EXCLUDED','reason':reason,'source_url':BASE+source,'sha256':digest}
    # Reverse relationship validates the exact ISIN, not just the server filter.
    hashes=[]; found=False
    for page in range(1,6):
        relation,h=client.get('lei-records/'+candidate['lei']+'/isins?'+urlencode({'page[size]':100,'page[number]':page}))
        hashes.append(h)
        rows=relation.get('data',[]); meta=relation.get('meta',{}).get('pagination',{})
        found=found or any(r.get('attributes',{}).get('isin')==isin and
            r.get('attributes',{}).get('lei')==candidate['lei'] for r in rows)
        if meta.get('currentPage')!=page or not isinstance(meta.get('lastPage'),int):
            return {'isin':isin,'status':'EXCLUDED','reason':'REVERSE_RELATION_MALFORMED'}
        if found: break
        if page>=meta['lastPage']: break
    if not found: return {'isin':isin,'status':'EXCLUDED','reason':'ISIN_NOT_FOUND_IN_REVERSE_RELATION'}
    return {**candidate,'status':'VERIFIED','source_url':BASE+source,'sha256':digest,
            'relation_sha256':hashes,'observed_at':datetime.now(UTC).isoformat(),
            'historical_pit_qualified':False}


def build(*,root=DEFAULT_ROOT,budget=1200,client=None,refresh=False,retry_reasons=()):
    reference=ROOT/'artifacts/fr/sprint6c_reference/identities.jsonl.gz'
    manual=json.loads((ROOT/'config/inpi_pilot_fr.json').read_text(encoding='utf-8'))
    with gzip.open(reference,'rt',encoding='utf-8') as stream: universe=[json.loads(s) for s in stream if s.strip()]
    ref_hash=hashlib.sha256(reference.read_bytes()).hexdigest()
    root.mkdir(parents=True,exist_ok=True)
    state_path=root/'mapping_report.json'
    old=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    if old and refresh:
        atomic(root/'history'/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json',old)
        old={}
    if old and old.get('reference_sha256')!=ref_hash: raise ValueError('Référentiel changé : nouvelle qualification requise')
    rows={r['isin']:r for r in old.get('rows',[]) if r.get('status') in ('VERIFIED','EXCLUDED')}
    if retry_reasons:
        atomic(root/'history'/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json',old)
        rows={key:r for key,r in rows.items() if r.get('reason') not in retry_reasons}
    seed={r['isin']:r for r in manual['issuers']}
    client=client or Gleif(budget)
    report={'reference_sha256':ref_hash,'identity_reference':str(reference.relative_to(ROOT)),
            'scope':'ALL_LOCAL_S6C_IDENTITIES_CURRENT_MAPPING','historical_pit_qualified':False}
    def save():
        report.update(rows=list(rows.values()),counts=dict(Counter(r['status'] for r in rows.values())),
                      reason_counts=dict(Counter(r.get('reason','VERIFIED') for r in rows.values())),
                      total_universe=len(universe),pending=len(universe)-len(rows),provider_calls=client.calls,
                      status='COMPLETE' if len(rows)==len(universe) else 'IN_PROGRESS')
        atomic(state_path,report)
        eligible=[{**r,'legal_source':r.get('legal_source') or r.get('source_url')} for r in rows.values() if r['status']=='VERIFIED']
        atomic(root/'verified_manifest.json',{'schema_version':2,'identity_reference':report['identity_reference'],
            'reference_sha256':ref_hash,'mapping_report':str(state_path),'canonical_go':False,'issuers':eligible})
    for identity in universe:
        isin=identity['isin']
        if isin in rows: continue
        base={'isin':isin,'symbol':identity['provider_symbol']}
        if identity.get('identity_state')!='VERIFIED_RESEARCH':
            result={**base,'status':'EXCLUDED','reason':'LOCAL_IDENTITY_NOT_VERIFIED'}
        else:
            try:
                result={**lookup(client,isin),**base}
                if isin in seed:
                    proven=seed[isin]
                    if result['status']=='VERIFIED' and result['siren']!=proven['siren']:
                        result.update(status='EXCLUDED',reason='CONFLICT_WITH_PRIMARY_LEGAL_SOURCE')
                    elif result.get('reason')=='NO_GLEIF_ISIN_MATCH':
                        result={**proven,**base,'status':'VERIFIED','mapping_state':'PRIMARY_LEGAL_SOURCE_REVIEWED',
                                'observed_at':datetime.now(UTC).isoformat(),'historical_pit_qualified':False}
                    elif result['status']=='VERIFIED':
                        result['name_aliases']=sorted(set(result['name_aliases']+proven['name_aliases']))
                        result['legal_source']=proven['legal_source']
            except Exception as exc:
                # Transient failures remain pending; never converted to verified or excluded.
                report['last_error_type']=type(exc).__name__; save()
                if client.calls>=client.budget: break
                print(json.dumps({**base,'status':'RETRY_PENDING','error_type':type(exc).__name__}),flush=True)
                continue
        result.setdefault('observed_at',datetime.now(UTC).isoformat())
        rows[isin]=result; save()
        print(json.dumps({**base,'status':result['status'],'reason':result.get('reason')}),flush=True)
    save(); return report


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--max-requests',type=int,default=1200)
    parser.add_argument('--refresh',action='store_true',help='Archiver la précédente recherche et requalifier les correspondances actuelles')
    parser.add_argument('--retry-reason',action='append',default=[],help='Réexaminer ce motif après qualification d’une nouvelle règle')
    args=parser.parse_args()
    if not 1<=args.max_requests<=1200: raise ValueError('Budget mapping 1..1200')
    result=build(budget=args.max_requests,refresh=args.refresh,retry_reasons=args.retry_reason)
    print(json.dumps({k:result[k] for k in ('status','counts','pending','provider_calls')}),flush=True)
    if result['pending']: raise SystemExit(2)


if __name__=='__main__': main()
