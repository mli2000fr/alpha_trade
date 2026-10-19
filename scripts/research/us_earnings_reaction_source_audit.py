"""Offline scalar and document-structure audit; no new source or return outcomes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def sections(body):
    """Preserve SGML exhibit boundaries; don't merge issuer and exhibit text."""
    out=[]
    for part in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',body,re.I|re.S):
        typ=re.search(r'<TYPE>([^\r\n<]+)',part)
        if not typ: continue
        typ=typ.group(1).strip()
        if typ not in ('10-Q','10-K','8-K','6-K','EX-99','EX-99.1'): continue
        soup=BeautifulSoup(part,'html.parser')
        for node in soup(['script','style','ix:header','ix:hidden','xbrli:xbrl']):node.decompose()
        text=' '.join(soup.stripped_strings)
        out.append(dict(document_type=typ,text=text))
    return out


def excerpts(text):
    # These are routing snippets, never an automatic new-announcement approval.
    out=[]
    terms=[r'Item\s*2\.02',r'On September.{0,30}2026',r'issued a press release',r'announced.{0,100}results',r'quarterly period ended']
    for term in terms:
        matches=list(re.finditer(term,text,re.I))[:3]
        for m in matches:
            start=max(0,m.start()-100);end=min(len(text),m.end()+300)
            out.append(dict(pattern=term,start=start,end=end,quote=text[start:end]))
    return out


def audit(root):
    if (root/'source-audit.json').exists():raise ValueError('Immutable completed audit')
    p=READ(root/'protocol.json');r=READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,r['files'])
    events=pd.read_parquet(root/'filing-candidates.parquet')
    selected=pd.read_parquet(root/'top10-candidates.parquet')
    top=pd.read_parquet(root/'top10.parquet')
    assert len(top)==r['top10_symbol_dates'] and top.groupby('date').size().eq(10).all()
    expected=events.merge(top[['date','symbol']].rename(columns={'date':'reaction_date'}),on=['reaction_date','symbol'])
    assert set(zip(expected.symbol,expected.accession_number))==set(zip(selected.symbol,selected.accession_number))
    count=0
    for symbol,g in events[events.numeric_ready].groupby('symbol'):
        raw=READ(p['facts_paths'][symbol])
        for row in g.itertuples():
            comp=json.loads(row.components)
            values={}
            for metric in ('revenue','operating'):
                c=comp[metric];facts=raw['facts']['us-gaap'][c['tag']]['units'][c['unit']]
                current={float(e['val']) for e in facts if e.get('accn')==row.accession_number
                    and e.get('start')==c['start'] and e.get('end')==c['end']}
                previous={float(e['val']) for e in facts if e.get('accn')==row.accession_number
                    and e.get('start') in c['prior_starts'] and e.get('end') in c['prior_ends']}
                assert len(current)==len(previous)==1
                values[metric]=(next(iter(current)),next(iter(previous)))
            revenue,old_revenue=values['revenue'];operating,old_operating=values['operating']
            growth=(revenue-old_revenue)/old_revenue
            margin=operating/revenue-old_operating/old_revenue
            assert abs(growth-row.revenue_growth)<1e-12 and abs(margin-row.operating_margin_change)<1e-12
            side='LONG' if growth>0 and margin>0 else 'SHORT' if growth<0 and margin<0 else 'ABSTAIN'
            assert side==row.accounting_pattern
            count+=1
    days=mcal.get_calendar('NYSE').schedule(start_date='2023-01-01',end_date='2026-10-20').index
    prices=pd.read_parquet(root/'reaction-price-inputs.parquet')
    assert not prices.duplicated(['date','symbol']).any()
    keys=set(); lookup={(x.symbol,x.date):x.adj_close for x in prices.itertuples()}
    for row in selected.itertuples():
        d=row.reaction_date;j=days.get_loc(d)
        assert d>row.filed and row.potential_entry_date>d
        keys.update((s,day) for s in (row.symbol,'SPY') for day in (days[j-1],d))
        if row.price_pattern!='UNKNOWN':
            rel=lookup[(row.symbol,d)]/lookup[(row.symbol,days[j-1])]-lookup[('SPY',d)]/lookup[('SPY',days[j-1])]
            assert abs(rel-row.relative_reaction)<1e-12
            assert row.price_pattern==('LONG' if rel>0 else 'SHORT' if rel<0 else 'ABSTAIN')
        assert row.agreement_pattern==(row.accounting_pattern if row.numeric_ready
            and row.accounting_pattern==row.price_pattern else 'ABSTAIN')
    assert set(zip(prices.symbol,prices.date))<=keys
    docs=READ(root/'document-sample.json')['documents'];inspections=[];files={}
    for meta in docs:
        assert digest(root/meta['file'])==meta['sha256']==meta['declared_sha256']
        body=(root/meta['file']).read_text(encoding='utf-8');parts=sections(body)
        item=dict(accession_number=meta['accession_number'],original_sha256=meta['sha256'],parts=[])
        for n,part in enumerate(parts):
            file=f"documents/{meta['accession_number']}-{n}-visible.txt"
            (root/file).write_text(part['text'],encoding='utf-8');files[file]=digest(root/file)
            item['parts'].append(dict(document_type=part['document_type'],visible_path=file,
                visible_chars=len(part['text']),snippets=excerpts(part['text'])))
        inspections.append(item)
    atomic_json(root/'document-inspection.json',dict(scope='Structural/excerpt review only,not full human reading or issuer novelty qualification',documents=inspections))
    result=dict(status='PASS_FEATURE_ARITHMETIC_AND_SOURCE_STRUCTURE_ONLY',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        numeric_observations_checked=count,top10_reactions_checked=len(selected),source_documents_checked=len(docs),
        exact_exported_reaction_dates_only=True,first_announcement_qualified=0,
        current_reception_never_backdated=True,independent_human_review=False,
        report_sha256=digest(root/'report.json'),code_sha256=digest(Path(__file__)),
        files={**files,'document-inspection.json':digest(root/'document-inspection.json')},
        api_calls=0,sql=False,training=False,price_outcomes=False)
    atomic_json(root/'source-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},default=str))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);audit(p.parse_args().output)
