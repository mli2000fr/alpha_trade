"""Small non-canonical INPI coverage probe; no PDF, login payload or SQL writes."""
from datetime import UTC,datetime
import hashlib
import json
from pathlib import Path
import uuid

from service.inpi.client import InpiClient,InpiError

ROOT=Path(__file__).resolve().parents[2]


def summary(payload,siren):
    if payload.get('deleted') is True or payload.get('confidentiality')!='Public':
        raise InpiError('Bilan retiré ou non public : traitement refusé')
    if str(payload.get('siren'))!=siren: raise InpiError('Identité bilan incohérente')
    identity=payload.get('bilanSaisi',{}).get('bilan',{}).get('identite',{})
    if identity.get('siren') and str(identity['siren'])!=siren: raise InpiError('Identité interne bilan incohérente')
    detail=payload.get('bilanSaisi',{}).get('bilan',{}).get('detail',{})
    pages=detail.get('pages',[])
    cells=[cell for page in pages for cell in page.get('liasses',[])]
    numeric=sum(1 for cell in cells for key in ('m1','m2','m3','m4') if str(cell.get(key,'')).strip())
    allowed=('id','siren','denomination','dateDepot','dateCloture','typeBilan','confidentiality','deleted','createdAt','updatedAt')
    return {**{k:payload.get(k) for k in allowed},
        'identity':{k:identity.get(k) for k in ('dateClotureExercice','codeTypeBilan','codeDevise','codeSaisie','codeConfidentialite','infoTraitement')},
        'page_count':len(pages),'cell_count':len(cells),'nonempty_value_count':numeric,
        'cerfa_codes':[c.get('code') for c in cells[:10]],
        'source_payload_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}


def run(client,*,siren='438479941'):
    if siren!='438479941': raise InpiError('Smoke limité à l’identité vérifiée AB SCIENCE')
    result={'status':'FAILED','siren':siren,'issuer':'AB SCIENCE','symbol':'AB.PA','isin':'FR0010557264',
        'identity_source':'https://www.ab-science.com/wp-content/uploads/2024/11/RFS_AB_Science_S12024_18_11_2024_EN.pdf',
        'scope':'ONE_ISSUER_NOT_UNIVERSE_COVERAGE','observed_at':datetime.now(UTC).isoformat(),
        'sql_writes':False,'canonical_go':False,'credentials_persisted':False,'documents':[]}
    try:
        client.login()
        result['authentication_ok']=True
        for kind in ('bilans','bilans-saisis'):
            rows,cursor=client.accounts(siren,kind=kind)
            result[kind]={'received':len(rows),'more_pages':bool(cursor)}
            if kind=='bilans-saisis':
                for row in rows:
                    if row.get('deleted') is True or row.get('confidentiality')!='Public': continue
                    payload=client.account(row['id'])
                    result['documents'].append(summary(payload,siren))
        result['status']='ACCESS_VERIFIED' if result['documents'] else 'NO_PUBLIC_STRUCTURED_DOCUMENT'
        result['available_at']=datetime.now(UTC).isoformat()
    except InpiError as exc: result['error_message']=str(exc)
    finally:
        result['provider_calls']=client.calls
        client.close()
    return result


def main():
    result=run(InpiClient())
    folder=ROOT/'artifacts/fr/operations/validation_15f'/ (datetime.now(UTC).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'report':str(folder/'report.json'),
        'public_documents':len(result['documents']),'provider_calls':result['provider_calls'],
        'error_message':result.get('error_message')},ensure_ascii=False),flush=True)
    if result['status']=='FAILED': raise SystemExit(1)


if __name__=='__main__': main()
