"""Bounded DOCN/FUN semantic review; immutable evidence, no production writes.

Read existing received-snapshot archives and source envelopes; archive five
known public documents once, with verified TLS. No challenge bypass, supplier
data API, LLM, price outcomes, training or orders.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy import bindparam, text

from scripts.research import us_consensus_observed_revision_pilot as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PARENT=Path('artifacts/research/us_directional_information/20261019-v2/observed-revisions-v1')
SYMBOLS=['DOCN','FUN']
PUBLIC={
    'docn_q2': 'https://investors.digitalocean.com/news/news-details/2026/DigitalOcean-Announces-Second-Quarter-2026-Financial-Results/default.aspx',
    'fun_q2': 'https://www.sec.gov/Archives/edgar/data/1999001/000199900126000094/sixflags-exh991xq22026.htm',
    'fun_notice': 'https://www.businesswire.com/news/home/20261007925585/en/Six-Flags-to-Announce-2026-Third-Quarter-Results-on-November-5-Earnings-Call-Starts-at-8-AM-EST',
    'provider_calendar': 'https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits',
    'provider_glossary': 'https://eodhd.com/financial-academy/financial-faq/fundamentals-glossary-common-stock',
}
CIKS={'DOCN':'0001582961','FUN':'0001999001'}
REQUIRED=['issuer_identity','exact_target_period','consensus_currency_scale','consensus_eps_basis','metric_comparability']


def qualify(components, receipt_ok, source_scope, reviewed_at, cutoff):
    """Context is not vendor-field evidence; qualifications cannot be backdated."""
    reasons=[k.upper()+'_UNQUALIFIED' for k in REQUIRED if components.get(k) is not True]
    if not receipt_ok: reasons.append('SOURCE_ENVELOPE_UNQUALIFIED')
    if source_scope!='calendar/trends:earningsEstimateAvg': reasons.append('EPS_EVIDENCE_WRONG_FIELD_OR_PRODUCT')
    historical=pilot.utc(reviewed_at)<pilot.utc(cutoff)
    if not historical: reasons.append('REVIEW_AFTER_FROZEN_ENTRY_CUTOFF')
    return dict(semantically_complete=all(components.get(k) is True for k in REQUIRED)
        and receipt_ok and source_scope=='calendar/trends:earningsEstimateAvg',
        admissible_at_frozen_entry=not reasons,reasons=reasons)


def prepare(root):
    if (root/'protocol.json').exists():
        p=pilot.READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh directory required')
    old=pilot.prepare(PARENT)
    for name in ['snapshot-ready.json','pair-ready.json','proof-ready.json','report.json']:
        verify_hashes(PARENT,pilot.READ(PARENT/name)['files'])
    files=[Path(__file__),Path('tests/test_us_consensus_two_issuer_qualification.py'),
        Path('scripts/research/us_consensus_docn_fun_findings_20261019.json'),
        PARENT/'protocol.json',PARENT/'snapshot-ready.json',PARENT/'consensus.parquet',PARENT/'runs.parquet',
        PARENT/'report.json',Path('common/public_data_http.py')]
    files += [Path(f'artifacts/sec_cache/companyfacts/CIK{CIKS[s]}.json') for s in SYMBOLS]
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        parent=str(PARENT),symbols=SYMBOLS,public_documents=PUBLIC,entry_cutoff_utc=old['entry_cutoff_utc'],
        scope='Qualify only DOCN and FUN received records11-18Oct2026; FMC untouched/reserved. No expansion or performance.',
        public_access='Five exact public URLs once each, max8MiB each, timeout30s, TLS verified. Archive status/refusal; no circumventing403/429, no browser session or cookies, no date backdating.',
        existing_sql='Only stored EODHD raw receipts and security-master metadata for2 symbols; READ ONLY UTC REPEATABLE READ then ROLLBACK.',
        semantic='epsActual non-GAAP documentation is not proof that calendar/trends earningsEstimateAvg uses that same definition. Issuer guidance is not analyst consensus.',
        chronology='Public pages retrieved and review completed NOW; original stated publication dates retained separately, no retroactive availability/qualification.',
        product_api_calls=0,llm_calls=0,sql_writes=False,production_changes=False,new_training=False,price_outcomes=False,orders=False)
    atomic_json(root/'protocol.json',p)
    rows=pd.read_parquet(PARENT/'consensus.parquet')
    selected=rows[rows.symbol.isin(SYMBOLS)].copy()
    selected.to_parquet(root/'selected-snapshots.parquet',index=False)
    atomic_json(root/'selection-ready.json',dict(rows=len(selected),files={'selected-snapshots.parquet':digest(root/'selected-snapshots.parquet')}))
    return p


def existing_proofs(root):
    p=prepare(root);verify_hashes(root,pilot.READ(root/'selection-ready.json')['files'])
    if (root/'proof-ready.json').exists():raise ValueError('Immutable proof snapshot')
    f=pd.read_parquet(root/'selected-snapshots.parquet')
    runids=sorted(f.run_id.unique())
    stamps=sorted(pd.to_datetime(f.observed_at,utc=True).dt.tz_localize(None).unique().tolist())
    # Datetime conversion must preserve microseconds and exact group receipts.
    stamps=[pd.Timestamp(x).to_pydatetime() for x in stamps]
    engine,conn=pilot.connect_readonly()
    try:
        stmt=text('''SELECT id,run_id,entity_key,observed_at,available_at,http_status,payload_hash,payload_json
            FROM pit_raw_payloads WHERE batch_name='eodhd_consensus_snapshot' AND provider='eodhd'
            AND endpoint='/calendar/trends' AND run_id IN :runs AND observed_at IN :stamps ORDER BY id''')
        stmt=stmt.bindparams(bindparam('runs',expanding=True),bindparam('stamps',expanding=True))
        raw=[dict(r) for r in conn.execute(stmt,dict(runs=runids,stamps=stamps)).mappings()]
        master=pilot.inventory.query(conn,'''SELECT s.provider,s.symbol,s.cik,s.company_name,s.snapshot_date,
            s.observed_at,s.available_at,s.run_id,r.status,r.finished_at
            FROM security_master_snapshots s LEFT JOIN pit_collection_runs r ON r.run_id=s.run_id
            WHERE s.symbol IN :symbols AND s.available_at<:cutoff AND s.snapshot_date>='2026-09-01'
            ORDER BY s.symbol,s.snapshot_date,s.available_at''',SYMBOLS,
            cutoff=pilot.utc(p['entry_cutoff_utc']).tz_localize(None).to_pydatetime())
        conn.rollback()
    finally:
        conn.close();engine.dispose()
    pd.DataFrame(raw).to_parquet(root/'raw-receipts.parquet',index=False)
    pd.DataFrame(master).to_parquet(root/'master-metadata.parquet',index=False)
    atomic_json(root/'proof-ready.json',dict(raw_receipts=len(raw),master_rows=len(master),
        files={n:digest(root/n) for n in ['raw-receipts.parquet','master-metadata.parquet']}))
    print(dict(raw_receipts=len(raw),master_rows=len(master)),flush=True)


def archive_public(root):
    from common.public_data_http import verified_session
    p=prepare(root)
    if (root/'public-ready.json').exists():raise ValueError('Immutable public document snapshot')
    out=root/'public';out.mkdir(exist_ok=False)
    result=[];files={}
    with verified_session() as client:
        for name,url in p['public_documents'].items():
            item=dict(source_id=name,url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                historical_reception_proven=False,attempts=1)
            headers={}
            if name=='fun_q2':
                ua=os.getenv('SEC_EDGAR_USER_AGENT')
                if not ua:
                    result.append(dict(item,status='NO_SEC_CONTACT_USER_AGENT_NO_REQUEST'));continue
                headers['User-Agent']=ua
            try:
                response=client.get(url,headers=headers,timeout=30,stream=True,allow_redirects=False)
                with response:
                    item['http_status']=response.status_code
                    item['content_type']=response.headers.get('Content-Type')
                    if response.status_code!=200:
                        result.append(dict(item,status='REFUSED_OR_UNAVAILABLE_NO_BYPASS'));continue
                    body=bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body)>8*1024*1024:raise ValueError('PUBLIC_SIZE_BOUND')
                    soup=BeautifulSoup(bytes(body),'html.parser')
                    for node in soup(['script','style','noscript','template']):node.decompose()
                    visible=' '.join(soup.stripped_strings)
                    if not visible or any(x in visible[:2000].lower() for x in ['verify you are human','just a moment...','access denied']):
                        result.append(dict(item,status='CHALLENGE_OR_EMPTY_NO_BYPASS'));continue
                    binary=f'public/{name}.html';plain=f'public/{name}.txt'
                    (root/binary).write_bytes(body);(root/plain).write_text(visible,encoding='utf-8')
                    files[binary]=digest(root/binary);files[plain]=digest(root/plain)
                    item.update(status='ARCHIVED_CURRENT_BYTES',bytes=len(body),html_path=binary,text_path=plain,
                        html_sha256=files[binary],text_sha256=files[plain])
                    result.append(item)
            except Exception as exc:
                # No URL/headers/exception text: user-agent may contain a private contact address.
                result.append(dict(item,status='TECHNICAL_FAILURE_NO_RETRY',error_type=type(exc).__name__))
            print(name,result[-1]['status'],flush=True)
    atomic_json(root/'public-ready.json',dict(sources=result,files=files))


def report(root):
    p=prepare(root)
    if (root/'report.json').exists():raise ValueError('Immutable completed review')
    for name in ['selection-ready.json','proof-ready.json','public-ready.json']:
        verify_hashes(root,pilot.READ(root/name)['files'])
    f=pd.read_parquet(root/'selected-snapshots.parquet');raw=pd.read_parquet(root/'raw-receipts.parquet')
    runs={r['run_id']:r for r in pd.read_parquet(PARENT/'runs.parquet').to_dict('records')}
    matching={};bad=[]
    for r in raw.to_dict('records'):
        obj=json.loads(r['payload_json'])
        if r['http_status']!=200 or pilot.payload_hash(obj)!=r['payload_hash'] or pilot.utc(r['available_at'])<pilot.utc(r['observed_at']):
            bad.append(int(r['id']));continue
        for group in obj.get('trends',[]):
            for item in group:
                matching[(r['run_id'],pilot.utc(r['observed_at']),pilot.payload_hash(item))]=int(r['id'])
    checked=[]
    for r in f.to_dict('records'):
        own=pilot.row_checks(r,runs)
        receipt=matching.get((r['run_id'],pilot.utc(r['observed_at']),r['raw_hash']))
        checked.append(dict(id=int(r['id']),symbol=r['symbol'],receipt_id=receipt,
            matched=receipt is not None,technical_reasons=own['technical_reasons']))
    atomic_json(root/'row-checks.json',dict(rows=checked,bad_envelopes=bad))
    findings=pilot.READ(Path('scripts/research/us_consensus_docn_fun_findings_20261019.json'))
    public=pilot.READ(root/'public-ready.json')
    master=pd.read_parquet(root/'master-metadata.parquet')
    now=datetime.now(timezone.utc).isoformat();results=[]
    for symbol in SYMBOLS:
        note=findings[symbol]
        good=all(r['matched'] and not r['technical_reasons'] for r in checked if r['symbol']==symbol)
        facts=pilot.READ(Path(f'artifacts/sec_cache/companyfacts/CIK{CIKS[symbol]}.json'))
        observed_master=master[master.symbol.eq(symbol)] if len(master) else master
        ciks=sorted({str(x).zfill(10) for x in observed_master.cik.dropna() if str(x).strip()}) if len(observed_master) else []
        gate=qualify(note['components'],good,note['eps_evidence_scope'],now,p['entry_cutoff_utc'])
        results.append(dict(symbol=symbol,**gate,components=note['components'],
            issuer_context=dict(expected_cik=CIKS[symbol],cached_entity_name=facts.get('entityName'),
                local_master_ciks=ciks,master_matches_expected=bool(ciks==[CIKS[symbol]])),
            received_snapshots=int(f[f.symbol.eq(symbol)].snapshot_date.nunique()),
            raw_rows_checked=sum(r['symbol']==symbol for r in checked),all_receipts_match=good,
            findings=note['findings'],missing=note['missing'],evidence_references=note['sources']))
    source_meta={r['source_id']:r for r in public['sources']}
    # Web-inspected claims are explicit review notes. Local fetch success is not assumed.
    result=dict(status='BOUNDED_REVIEW_COMPLETED_PARTIAL_CONTEXT_NO_DIRECTIONAL_QUALIFICATION',
        reviewed_at_utc=now,entry_cutoff_utc=p['entry_cutoff_utc'],rows_checked=len(checked),
        receipt_matches=sum(r['matched'] for r in checked),bad_envelopes=bad,results=results,
        public_sources=source_meta,public_capture_is_current_not_historical=True,
        total_qualified_symbols=sum(r['semantically_complete'] for r in results),
        admitted_at_original_entry=sum(r['admissible_at_frozen_entry'] for r in results),
        source_scope_note='Issuer financial statements establish issuer context, not analyst-consensus field basis. General non-GAAP actual EPS glossary is not field-specific consensus documentation.',
        action='Ask provider precise field/date/units/basis questions; no subscription change or email sent. Keep FMC reserved; no production qualifications or orders.',
        files={n:digest(root/n) for n in ['protocol.json','selection-ready.json','proof-ready.json','public-ready.json','row-checks.json']},
        sql_writes=False,paid_data_api_calls=0,llm_calls=0,price_outcomes=False)
    atomic_json(root/'report.json',result)
    print(dict(status=result['status'],rows=len(checked),matches=result['receipt_matches'],
        qualified=result['total_qualified_symbols'],results=results),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','proofs','public','report'],required=True);a=parser.parse_args()
    {'prepare':prepare,'proofs':existing_proofs,'public':archive_public,'report':report}[a.phase](a.output)
