"""Local source-passage screening, no LLM, network, SQL, prices or outcomes."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse
import hashlib
import re

from bs4 import BeautifulSoup
import pandas as pd

from scripts.research.us_economic_links_feasibility import read,FORMS
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_economic_links_feasibility/20261102-v4')
RELATION=re.compile(r'\b(customer[s]?|suppliers?|suppl(?:y|ies|ied)|purchas(?:e|es|ed|ing)|'
                    r'sell|sells|selling|sold|distribut(?:or|ors|ion)|foundr(?:y|ies)|manufactur(?:e|er|ers|ing))\b',re.I)
ALIASES={'MSFT':['Microsoft'],'AMZN':['Amazon','Amazon Web Services'],
    'AAPL':['Apple Inc.','Apple Inc'],'GOOGL':['Alphabet Inc.','Google'],
    'META':['Meta Platforms'],'NVDA':['NVIDIA'],'TSM':['Taiwan Semiconductor','TSMC'],
    'INTC':['Intel'],'AMAT':['Applied Materials'],'LRCX':['Lam Research'],
    'AMD':['Advanced Micro Devices'],'AVGO':['Broadcom'],'QCOM':['Qualcomm'],
    'TSLA':['Tesla'],'WDC':['Western Digital'],'STX':['Seagate'],
    'MCK':['McKesson'],'CAH':['Cardinal Health'],'SMTC':['Semtech']}
AMBIGUOUS={'bandwidth','packaging','reliance','interface','mine safety','prudential',
           'core','unity','target','on','standard','global','partners','enterprise'}


def aliases(companies):
    """Names are a candidate lookup only, never a historical identity certificate."""
    result=defaultdict(set)
    symbols={r['symbol'] for r in companies}
    for row in companies:
        name=(row.get('company_name') or '').strip()
        if not name:
            continue
        core=re.split(r'\b(?:Inc\.?|Incorporated|Corporation|Corp\.?|Limited|Ltd\.?|PLC|plc|Class [AB]|Common Stock)\b',name,maxsplit=1)[0]
        core=re.sub(r'[,\s]+$','',core).strip()
        for alias in [name,core]:
            if len(alias)>=5 and len(alias.split())<=7 and alias.casefold() not in AMBIGUOUS:
                result[alias].add(row['symbol'])
    for symbol,names in ALIASES.items():
        if symbol in symbols:
            for alias in names:
                result[alias].add(symbol)
    return {alias:next(iter(targets)) for alias,targets in result.items() if len(targets)==1}


def source_parts(body,form):
    selected=[]
    for index,block in enumerate(re.findall(r'<DOCUMENT\b[^>]*>(.*?)</DOCUMENT\s*>',body,re.I|re.S)):
        typ=re.search(r'<TYPE>\s*([^\r\n<]+)',block,re.I)
        text=re.search(r'<TEXT\b[^>]*>(.*?)</TEXT\s*>',block,re.I|re.S)
        if not typ or not text:
            continue
        typ=typ.group(1).strip().upper()
        if typ in FORMS or typ.startswith(('EX-99','EX-10')) and not typ.startswith('EX-101'):
            selected.append((index,typ,text.group(1)))
    if not selected:
        selected=[(0,form,re.split(r'</SEC-HEADER\s*>',body,flags=re.I)[-1])]
    output=[]
    for index,typ,raw in selected:
        if re.search(r'<PDF\b|begin 644',raw,re.I):
            continue
        soup=BeautifulSoup(raw,'html.parser')
        fields=defaultdict(set)
        for node in soup.find_all(re.compile(r'(?:^|:)nonnumeric$',re.I)):
            name=str(node.get('name','')).split(':')[-1]
            if name in ['EntityCentralIndexKey','TradingSymbol','EntityRegistrantName']:
                fields[name].add(node.get_text(' ',strip=True))
        for node in soup(['script','style','ix:hidden','ix:header','noscript']):
            node.decompose()
        visible=re.sub(r'\s+',' ',soup.get_text(' ',strip=True)).strip()
        if len(visible)>=100:
            output.append(dict(part=index,document_type=typ,text=visible,
                               fields={k:sorted(v) for k,v in fields.items()}))
    return output


def screen(text,mapping,owner):
    lowered=text.casefold()
    found=[]
    for alias,symbol in mapping.items():
        if symbol==owner or alias.casefold() not in lowered:
            continue
        for match in re.finditer(r'(?<![\w])'+re.escape(alias)+r'(?![\w])',text,re.I):
            if len(alias.split())==1 and not match.group(0)[0].isupper():
                continue
            start=max(0,match.start()-330);end=min(len(text),match.end()+330)
            quote=text[start:end]
            # Nearby words nominate a passage for review. They never prove a link.
            terms=[m.group(0) for m in RELATION.finditer(quote)]
            found.append(dict(counterparty_symbol=symbol,matched_alias=alias,
                start=start,end=end,quote=quote,relation_words=terms,
                screen_kind='RELATION_WORD_NEAR_NAME' if terms else 'NAME_ONLY_CONTROL'))
    # Distinct occurrences/aliases are retained as provenance, not independent evidence.
    unique={ (p['counterparty_symbol'],p['start'],p['end']):p for p in found }
    return list(unique.values())


def run(root,version='initial'):
    protocol=read(root/'protocol.json')
    destination=root if version=='initial' else root/version
    if (destination/'screen-report.json').exists():
        raise ValueError('Do not overwrite a reviewed screen')
    destination.mkdir(exist_ok=True)
    mapping=aliases(read(root/'company-names.json'))
    current=pd.read_parquet(root/'current-top20.parquet')
    rank=current.set_index('symbol').oracle_rank.to_dict()
    selected=read(root/'document-inventory.json')
    output=destination/'visible';output.mkdir(exist_ok=False)
    passages=[];docs=[]
    for item in selected:
        if not item.get('hash_matches') or not item.get('archive_path'):
            continue
        file=root/item['archive_path']
        if digest(file)!=item['actual_sha256']:
            raise ValueError('Archived filing changed')
        parts=source_parts(file.read_text(encoding='utf-8'),item['form_type'])
        for part in parts:
            key=item['accession_number']+'-'+str(part['part'])
            path=output/(key+'.txt')
            if not path.exists():
                with path.open('x',encoding='utf-8') as stream:
                    stream.write(part['text'])
            ciks={str(v).strip().zfill(10) for v in part['fields'].get('EntityCentralIndexKey',[])}
            doc=dict(document_key=key,owner_symbol=item['requested_symbol'],stored_symbol=item['symbol'],
                owner_cik=item['cik'],form_type=item['form_type'],part_type=part['document_type'],
                accession=item['accession_number'],filing_date=item['filing_date'],
                acceptance_datetime_raw=item['acceptance_datetime'],url=item['filing_url'],
                observed_at=item['observed_at'],available_at=item['available_at'],
                collection_finished_at=item['collection_finished_at'],run_status=item['run_status'],
                raw_sha256=item['actual_sha256'],visible_file=str(path.relative_to(root)),
                visible_sha256=digest(path),visible_chars=len(part['text']),
                primary_cik_match=item['cik'] in ciks,
                primary_symbol_match=item['requested_symbol'] in part['fields'].get('TradingSymbol',[]),
                primary_fields=part['fields'],document_complete_claim=False)
            docs.append(doc)
            for candidate in screen(part['text'],mapping,item['requested_symbol']):
                passages.append(dict(doc,**candidate))
    atomic_json(destination/'visible-documents.json',docs)
    atomic_json(destination/'all-passages.json',passages)
    grouped=defaultdict(list)
    for passage in passages:
        if passage['screen_kind']=='RELATION_WORD_NEAR_NAME':
            grouped[(passage['owner_symbol'],passage['counterparty_symbol'])].append(passage)
    # Round-robin over original Oracle ranks, max2 pairs/owner and <=20 total.
    perowner=defaultdict(list)
    for (owner,counterparty),parts in sorted(grouped.items()):
        priority=lambda p:(0 if p['part_type'] in ['10-K','10-Q','20-F','40-F'] else 1,
                           0 if any(w.lower().startswith(('customer','suppli')) for w in p['relation_words']) else 1,
                           p['accession'],p['start'])
        parts=sorted(parts,key=priority)
        perowner[owner].append(dict(owner_symbol=owner,counterparty_symbol=counterparty,
            oracle_rank=int(rank[owner]),screened_passage_count=len(parts),passages=parts[:2],
            review_status='NOT_REVIEWED'))
    chosen=[]
    for round_ in range(2):
        for owner in sorted(perowner,key=lambda s:rank[s]):
            if round_<len(perowner[owner]) and len(chosen)<20:
                chosen.append(perowner[owner][round_])
    controls=[];seen=set()
    for passage in sorted(passages,key=lambda p:(rank[p['owner_symbol']],p['counterparty_symbol'],p['accession'],p['start'])):
        pair=(passage['owner_symbol'],passage['counterparty_symbol'])
        if passage['screen_kind']=='NAME_ONLY_CONTROL' and pair not in seen and len(controls)<10:
            controls.append(passage);seen.add(pair)
    atomic_json(destination/'review-pairs.json',chosen)
    atomic_json(destination/'review-controls.json',controls)
    result=dict(status='SCREENED_NOT_VERIFIED_RELATIONSHIPS',original_top20=20,
        owners_with_copied_body=len({p['requested_symbol'] for p in selected if p.get('archive_path')}),
        visible_parts=len(docs),visible_characters=sum(d['visible_chars'] for d in docs),
        primary_identity_fields_matched_parts=sum(d['primary_cik_match'] and d['primary_symbol_match'] for d in docs),
        all_passages=len(passages),candidate_pairs=len(grouped),candidate_owners=len(perowner),
        preselected_review_pairs=len(chosen),control_passages=len(controls),
        relations_verified=0,automatic_relation_admission=False,http_calls=0,llm_calls=0,
        outcome_reads=False,sql_writes=False,scan_source_sha256=digest(__file__),
        files={n:digest(destination/n) for n in ['visible-documents.json','all-passages.json','review-pairs.json','review-controls.json']})
    atomic_json(destination/'screen-report.json',result)
    atomic_json(root/'progress.json',result)
    return result


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT)
    p.add_argument('--screen-output',choices=['initial','screen-v2'],default='initial')
    a=p.parse_args();print(json.dumps(run(a.output,a.screen_output)))
