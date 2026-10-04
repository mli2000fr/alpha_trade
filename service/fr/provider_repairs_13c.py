"""Bounded provider refresh, versioned raw evidence; no SQL or archive overwrite."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from service.eodhd.accounts import EodhdAccountRegistry
from service.fr.eodhd_backfill import _fetch
from service.fr.exploitable_scope_12e import sha
from service.fr.yahoo_price_reference_pilot import normalize_chart
from service.fr.execution_evidence_12c import collect_source


def public_sources(output):
    output.mkdir(parents=True,exist_ok=False)
    urls={
        'opmobility_votes':'https://www.opmobility.com/wp-content/uploads/2025/05/opmobility-ag2025-compte-rendu-fr.pdf',
        'ses_paid':'https://www.ses.com/press-release/ses-q1-2025-results',
        'stif_terms':'https://investir.stif.fr/wp-content/uploads/2025/05/STIF-OJ-et-txt-resolutions-STIF-AGM.docx.pdf',
    }
    rows=[]
    for name,url in urls.items():
        try:
            rows.append({'name':name,'status':'ARCHIVED_NOT_AUTOMATICALLY_QUALIFIED',
                **collect_source(url,output/(name+('.pdf' if url.endswith('.pdf') else '.html')))})
        except Exception as exc:
            rows.append({'name':name,'status':'UNAVAILABLE','url':url,'error':str(exc)})
    (output/'report.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print([(r['name'],r['status']) for r in rows])


def price_overlay(refresh):
    report=json.loads((refresh/'yahoo-report.json').read_text(encoding='utf-8'))
    overlay={'schema_version':1,'state':'EXPLORATORY_ONLY_NOT_QUALIFIED','prices':[],'dividends':[]}
    for row in report['results']:
        if row['overlap_rows']!=2 or row['price_difference_count'] or row['yahoo_metadata']['currency']!='EUR':
            raise ValueError('Neighboring source convention mismatch')
        matches=list((refresh/'yahoo').glob(f"{__import__('hashlib').sha256(row['symbol'].encode()).hexdigest()[:16]}_*.json"))
        if len(matches)!=1 or sha(matches[0])!=row['cache_sha256']:
            raise ValueError('Source cache ambiguity/hash mismatch')
        prices,_=normalize_chart(json.loads(matches[0].read_text(encoding='utf-8'))['payload'])
        bar=prices['2024-07-30']
        overlay['prices'].append({'symbol':row['symbol'],'date':'2024-07-30',
            'bar':{k:bar[k] for k in ('open','high','low','close','volume')},
            'source_path':str(matches[0]),'source_sha256':sha(matches[0]),
            'evidence':'YAHOO_SECONDARY_PROVIDER_NEIGHBOR_PRICES_MATCH_NOT_OFFICIAL'})
    path=refresh/'overlay.json'
    path.write_text(json.dumps(overlay,indent=2),encoding='utf-8')
    return path


def supplement_payments(output,source=Path('config/research_fr/public_payment_review_13c.json')):
    output.mkdir(parents=True,exist_ok=False)
    review=json.loads(source.read_text(encoding='utf-8'))
    base=Path('artifacts/fr/research/provider_exploratory_13b/repair-20261004-v1/overlay.json')
    overlay=json.loads(base.read_text(encoding='utf-8'))
    for row in review['reviews']:
        references=[{'path':str(source),'sha256':sha(source)}]
        if row.get('archive'):
            references.append({'path':row['archive'],'sha256':sha(Path(row['archive']))})
        overlay['dividends'].append({**row,'source_path':str(source),'source_sha256':sha(source),
                                    'references':references})
    (output/'overlay.json').write_text(json.dumps(overlay,indent=2),encoding='utf-8')


def collect(output):
    output.mkdir(parents=True,exist_ok=False)
    token=EodhdAccountRegistry.get().get_token()
    qualification=pd.read_parquet('artifacts/fr/research/economic_qualification_12a/qualification-20261004-v2/holding_path_qualification.parquet')
    symbols=sorted(set(qualification[qualification.dividend_field_reasons.map(len).gt(0)].symbol))
    targets=[('eod',s,'2024-07-29','2024-07-31') for s in ('ERA.PA','GLE.PA','MEDCL.PA','VCT.PA')]
    targets += [('div',s,'2024-07-01','2025-08-31') for s in symbols]
    report={'status':'COLLECTING','observed_at':datetime.now(UTC).isoformat(),'canonical_writes':False,'sources':[]}
    for kind,symbol,start,end in targets:
        item={'kind':kind,'symbol':symbol,'start':start,'end':end}
        try:
            rows=_fetch(f'{kind}/{symbol}',token,{'from':start,'to':end},pace=.5)
            path=output/f'{kind}-{symbol}.json'
            path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
            item.update(status='COLLECTED',rows=len(rows),path=str(path),sha256=sha(path))
        except Exception as exc:
            item.update(status='FAILED',error=str(exc))
        report['sources'].append(item)
        (output/'progress.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(kind,symbol,item['status'],item.get('rows'),flush=True)
    report['status']='PROVIDER_REFRESH_COMPLETE_NOT_QUALIFIED'
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--build-price-overlay',action='store_true')
    parser.add_argument('--public-sources',action='store_true')
    parser.add_argument('--supplement-payments',action='store_true')
    parser.add_argument('--review',type=Path,default=Path('config/research_fr/public_payment_review_13c.json'))
    args=parser.parse_args()
    if args.supplement_payments:
        supplement_payments(args.output,args.review)
    elif args.public_sources:
        public_sources(args.output)
    elif args.build_price_overlay:
        print(price_overlay(args.output))
    else:
        collect(args.output)
