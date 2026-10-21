"""Pre-outcome identity supplements; never changes frozen event admissions.

PBT is a non-inline-XBRL cover, EMPD may require a prefiling quarterly cover
because the last annual precedes a name/ticker change. Preserve the original
UNKNOWN report and publish a separate qualified identity artifact.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re

from scripts.research.us_activist_13d_confirmation import prepare,Client
from scripts.research.us_activist_13d_confirmation_replay import freeze,primary_name
from scripts.research.us_activist_13d_extension import parse_quarter
from scripts.research.us_activist_13d_pilot import READ,Stopped,normalized,visible
from scripts.research.us_activist_13d_review import identity
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def plain_pbt_cover(body,receipt,annual):
    text=normalized(visible(body.decode('utf-8',errors='replace')))[:8000]
    clause='Units of Beneficial Interest PBT New York Stock Exchange'
    if clause not in text or 'PERMIAN BASIN ROYALTY TRUST' not in text:
        return None
    if receipt['url']!=f'https://www.sec.gov/Archives/edgar/data/319654/{annual["accession"].replace("-","")}/pbt_10-k_2024-12-31.htm':
        return None
    return dict(cik='0000319654',symbol='PBT',class_name='Units of Beneficial Interest',exchange='New York Stock Exchange',
                exact_cover_clause=clause,annual_filed=annual['filed'],method='ORIGINAL_NON_INLINE_ANNUAL_COVER')


def capture(root):
    reviewout,review=freeze(root);target=reviewout/'identity-qualified-v1.json'
    if target.exists():
        raise ValueError('Immutable qualified identity artifact')
    original=READ(reviewout/'identity-capture.json');verify_hashes(root,original['files'])
    supplements=[];stop=None
    pbt=next(r for r in review['rows'] if r.get('symbol')=='PBT' and r['admitted'])
    old=next(r for r in original['rows'] if r['accession']==pbt['accession'])
    if not old['identity'] and old.get('receipt',{}).get('status')=='OK':
        proof=plain_pbt_cover((root/old['receipt']['file']).read_bytes(),old['receipt'],pbt['annual_metadata'])
        supplements.append(dict(accession=pbt['accession'],symbol='PBT',identity=proof,receipt=old['receipt'],
                               reason='Cover contains explicit historical ticker/class/exchange; inline-XBRL-only reader was too narrow'))
    empd=next(r for r in review['rows'] if r.get('symbol')=='EMPD' and r['admitted'])
    candidates=[]
    for idx in READ(root/'selection.json')['indexes']:
        if idx['status']!='OK':
            continue
        receipt=idx['receipt'];path=root/receipt['file']
        if digest(path)!=receipt['sha256']:
            raise ValueError('Historical quarterly index changed')
        candidates.extend(r for r in parse_quarter(path.read_bytes(),idx['year'],idx['quarter'])
                          if r['cik']==empd['cik'] and r['form']=='10-Q' and r['filed']<empd['filed'])
    client=Client(root,prepare(root)['limits'])
    try:
        item=dict(accession=empd['accession'],symbol='EMPD',identity=None,
                  reason='Last annual cover predates rename; a strictly earlier quarterly cover may establish new ticker')
        if candidates:
            latest=sorted(candidates,key=lambda x:(x['filed'],x['accession']))[-1]
            if sum(r['filed']==latest['filed'] for r in candidates)!=1:
                raise ValueError('Ambiguous last prefiling10Q')
            item['quarterly_metadata']=latest
            base=f'https://www.sec.gov/Archives/edgar/data/{int(empd["cik"])}/{latest["accession"].replace("-","")}/'
            body,receipt=client.get(base+latest['accession']+'-index.html');item['index_receipt']=receipt
            if body:
                name=primary_name(body,'10-Q');body,receipt=client.get(base+name);item['receipt']=receipt
                if body:
                    item['identity']=identity(body,empd['cik'],empd['symbol'])
        supplements.append(item)
    except (Stopped,ValueError) as exc:
        stop=str(exc)
    finally:
        client.session.close()
    byid={r['accession']:r for r in supplements};rows=[]
    for item in original['rows']:
        row=dict(item)
        added=byid.get(item['accession'])
        if added and added['identity']:
            row.update(identity=added['identity'],status='PREFILING_SUPPLEMENT_CONFIRMED',supplement=added)
        rows.append(row)
    result=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),rows=rows,supplements=supplements,stop=stop,
                event_admissions_unchanged=True,qualified_before_price_outcomes=True,
                sources={str(Path(__file__)):digest(Path(__file__)),str(Path('tests/test_us_activist_13d_confirmation_identity.py')):digest(Path('tests/test_us_activist_13d_confirmation_identity.py')),
                         str(reviewout/'protocol.json'):digest(reviewout/'protocol.json'),str(reviewout/'identity-capture.json'):digest(reviewout/'identity-capture.json')},
                files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')},requests=client.calls,streamed_bytes=client.bytes)
    atomic_json(target,result)
    print('Qualified identities',sum(bool(x['identity']) for x in rows),'/',len(rows),'stop',stop,flush=True)


def qualified_identities(root):
    payload=READ(root/'review-frozen-v1/identity-qualified-v1.json')
    verify_hashes(Path('.'),payload['sources']);verify_hashes(root,payload['files'])
    return payload


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    capture(p.parse_args().output)
