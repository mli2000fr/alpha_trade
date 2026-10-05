"""Bounded ten-issuer research pilot. No SQL, full source JSON or credentials saved."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
import uuid

from service.inpi.accounts_smoke import summary
from service.inpi.client import InpiClient, InpiError

ROOT=Path(__file__).resolve().parents[2]


def normal_name(value):
    value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+',' ',value).strip()


def number(value):
    """Accept documented signed numeric cells only; blank is unknown, never zero."""
    if value is None or str(value).strip()=='': return None
    text=str(value).strip()
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',text): raise InpiError('Cellule numérique non reconnue')
    try:
        amount=Decimal(text)
        if not amount.is_finite(): raise InpiError('Cellule non finie')
        return amount
    except InvalidOperation: raise InpiError('Cellule numérique invalide') from None


def accounting_checks(payload,siren):
    result=summary(payload,siren)
    bilan=payload['bilanSaisi']['bilan']; identity=bilan['identite']
    result['identity'].update({k:identity.get(k) for k in ('dureeExerciceN','dureeExerciceNMoins1','dateClotureExerciceNMoins1')})
    kind=identity.get('codeTypeBilan')
    if kind not in ('C','K'):
        result['normalization_status']='UNSUPPORTED_LAYOUT'; return result
    index={}; duplicates=[]
    for page in bilan.get('detail',{}).get('pages',[]):
        for cell in page.get('liasses',[]):
            code=cell.get('code')
            if code in index: duplicates.append(code)
            index[code]=cell
    def value(code,column): return number(index.get(code,{}).get(column))
    specs={'assets_net':('CO','m3'),'liabilities_total':('EE','m1'),
           'equity':('DL','m1'),'cash':('CF','m3'),'revenue':('FJ','m3'),
           'income':('DI','m1') if kind=='C' else ('P2','m1')}
    amounts={name:value(*spec) for name,spec in specs.items()}
    result['amounts_source_units']={name:str(v) if v is not None else None for name,v in amounts.items()}
    result['field_lineage']={name:{'code':c,'column':col} for name,(c,col) in specs.items()}
    assets=amounts['assets_net']; liabilities=amounts['liabilities_total']
    result['balance_identity']='UNKNOWN' if assets is None or liabilities is None else ('PASS' if assets==liabilities else 'FAIL')
    result['duplicate_codes']=sorted(set(duplicates))
    result['scale_status']='SOURCE_UNITS_NOT_YET_INDEPENDENTLY_RECONCILED'
    result['external_reconciliation']='PENDING_ISSUER_REPORT_COMPARISON'
    issues=[]
    if duplicates: issues.append('DUPLICATE_CODES')
    if identity.get('codeSaisie')!='00': issues.append('SOURCE_ENTRY_CODE_NOT_00')
    if identity.get('codeConfidentialite')!='0': issues.append('INTERNAL_CONFIDENTIALITY_NOT_PUBLIC')
    if identity.get('codeDevise')!='EUR': issues.append('CURRENCY_NOT_EUR')
    if result['balance_identity']!='PASS': issues.append('BALANCE_NOT_VERIFIED')
    if str(identity.get('dureeExerciceN'))!='12': issues.append('DURATION_NOT_12_MONTHS')
    if any(v is None for v in amounts.values()): issues.append('MISSING_CORE_FIELDS')
    if payload.get('typeBilan')!=kind: issues.append('TYPE_MISMATCH')
    if payload.get('dateCloture')!=identity.get('dateClotureExercice'): issues.append('CLOSING_DATE_MISMATCH')
    result['issues']=issues
    result['normalization_status']='TECHNICAL_CHECKS_PASS_REVIEW_PENDING' if not issues else 'REVIEW_REQUIRED'
    return result


def collect_pages(client,siren,kind,max_pages=4):
    rows={}; cursor=None; seen=set()
    for page in range(max_pages):
        values,next_cursor=client.accounts(siren,kind=kind,page_size=10,search_after=cursor)
        for item in values:
            if not item.get('id'): raise InpiError('Métadonnée sans identifiant')
            if item['id'] in rows and rows[item['id']]!=item: raise InpiError('Version changeante dans pagination')
            rows[item['id']]=item
        if not values and next_cursor:
            raise InpiError('Page vide avec curseur : couverture indéterminée')
        if not values or not next_cursor: return list(rows.values()),{'pages':page+1,'complete':True}
        if next_cursor in seen: raise InpiError('Curseur répété ; pagination interrompue')
        seen.add(next_cursor); cursor=next_cursor
        time.sleep(.25)
    return list(rows.values()),{'pages':max_pages,'complete':False,'reason':'BOUNDED_PILOT_MAX_PAGES'}


def validate_manifest(manifest):
    issuers=manifest['issuers']
    if not 1<=len(issuers)<=10: raise InpiError('Pilote limité à dix émetteurs')
    reference=ROOT/manifest['identity_reference']
    with gzip.open(reference,'rt',encoding='utf-8') as handle: rows=[json.loads(line) for line in handle]
    seen=set()
    for issuer in issuers:
        key=(issuer['symbol'],issuer['isin'])
        matches=[r for r in rows if (r.get('provider_symbol'),r.get('isin'))==key and r.get('identity_state')=='VERIFIED_RESEARCH']
        if len(matches)!=1 or key in seen: raise InpiError('Identité locale absente/ambiguë/dupliquée : '+issuer['symbol'])
        if not re.fullmatch(r'\d{9}',issuer['siren']): raise InpiError('SIREN invalide')
        if not issuer.get('legal_source','').startswith('https://'): raise InpiError('Preuve légale requise')
        seen.add(key)
    return hashlib.sha256(reference.read_bytes()).hexdigest()


def run(client,manifest,folder):
    folder.mkdir(parents=True,exist_ok=False)
    report={'status':'RUNNING','observed_at':datetime.now(UTC).isoformat(),
            'scope':'TEN_ISSUER_BOUNDED_PILOT_NOT_UNIVERSE_COVERAGE',
            'sql_writes':False,'canonical_go':False,'issuers':[]}
    def save():
        path=folder/'report.json'; temporary=folder/'report.tmp'
        temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
    try:
        report['identity_reference_sha256']=validate_manifest(manifest)
        client.login()
        for issuer in manifest['issuers']:
            entry={**issuer,'status':'FAILED','mapping_status':'LOCAL_ISIN_AND_PRIMARY_LEGAL_SOURCE_REVIEWED',
                   'accounts':[],'documents':{},'errors':[],'canonical_go':False}
            try:
                listings={}
                for kind in ('bilans','bilans-saisis'):
                    rows,coverage=collect_pages(client,issuer['siren'],kind)
                    listings[kind]=rows
                    entry['documents'][kind]={**coverage,'count':len(rows),
                        'types':dict(Counter(r.get('typeBilan','UNKNOWN') for r in rows)),
                        'public':sum(r.get('confidentiality')=='Public' and not r.get('deleted') for r in rows)}
                public=[r for r in listings['bilans-saisis'] if r.get('confidentiality')=='Public' and not r.get('deleted')]
                selected=[]
                for kind in ('C','K'):
                    selected.extend(sorted([r for r in public if r.get('typeBilan')==kind],
                                           key=lambda r:(r.get('dateCloture') or '',r.get('updatedAt') or ''),reverse=True)[:2])
                names={normal_name(x) for x in issuer['name_aliases']}
                for row in selected:
                    try:
                        payload=client.account(row['id'])
                        if normal_name(payload.get('denomination')) not in names:
                            raise InpiError('Dénomination INPI non rapprochée : revue nécessaire')
                        account=accounting_checks(payload,issuer['siren'])
                        account['available_at']=datetime.now(UTC).isoformat()
                        entry['accounts'].append(account)
                    except InpiError as exc: entry['errors'].append({'id':row['id'],'message':str(exc)})
                    time.sleep(.25)
                entry['status']='ACCOUNTS_CHECKED_REVIEW_PENDING' if entry['accounts'] else 'NO_SELECTED_PUBLIC_STRUCTURED_ACCOUNT'
                if entry['errors']: entry['status']='PARTIAL_OR_REVIEW_REQUIRED'
            except InpiError as exc: entry['errors'].append({'message':str(exc)})
            report['issuers'].append(entry); report['provider_calls']=client.calls; save()
            print(json.dumps({'issuer':issuer['symbol'],'status':entry['status'],'accounts':len(entry['accounts'])}),flush=True)
        report['status']=('PILOT_PARTIAL_REVIEW_PENDING' if any(
            entry['errors'] or not entry['accounts'] for entry in report['issuers'])
            else 'PILOT_COMPLETE_REVIEW_PENDING')
    except InpiError as exc:
        report['status']='FAILED'; report['error_message']=str(exc)
    except Exception as exc:
        # No arbitrary exception text: provider payloads may contain sensitive data.
        report['status']='FAILED'; report['error_message']='Erreur interne : '+type(exc).__name__
    finally:
        client.close(); report['provider_calls']=client.calls
        report['finished_at']=datetime.now(UTC).isoformat(); save()
    return report


def main():
    manifest=json.loads((ROOT/'config/inpi_pilot_fr.json').read_text(encoding='utf-8'))
    folder=ROOT/'artifacts/fr/operations/inpi_pilot'/ (datetime.now(UTC).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    result=run(InpiClient(),manifest,folder)
    print(json.dumps({'status':result['status'],'report':str(folder/'report.json'),'provider_calls':result['provider_calls']}),flush=True)
    if result['status'] in ('FAILED','PILOT_PARTIAL_REVIEW_PENDING'): raise SystemExit(1)


if __name__=='__main__': main()
