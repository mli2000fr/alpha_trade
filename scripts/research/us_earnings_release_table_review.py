"""Offline conservative original-release table matching, no direction promotion.

Later10-Q values are verification targets ONLY: unless present in a correctly
scaled release table, they must not be moved to the release date. No downloads.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
LABELS={'revenue':re.compile(r'^(?:total\s+)?(?:(?:net|operating)\s+)?(?:revenues?|sales)(?:\s*\(\d+\))?\s*:?$',re.I),
    'operating':re.compile(r'^(?:total\s+)?(?:(?:income|loss)(?:\s*\((?:income|loss)\))?\s+from\s+operations|operating\s+(?:income|loss)(?:\s*\((?:income|loss)\))?)\s*:?$',re.I)}


def exhibits(body):
    out=[]
    for block in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',body,re.I|re.S):
        m=re.search(r'<TYPE>([^\r\n<]+)',block)
        if m and re.fullmatch(r'EX-99(?:\.\d+)?',m.group(1).strip(),re.I):out.append((m.group(1).strip(),block))
    return out


def numbers(text):
    # Missing/dash is never silently promoted to zero; all values need literal numerals.
    if re.search(r'[—–]',text):return []
    values=[]
    for m in re.finditer(r'[-−]?\s*\(?\s*\d[\d,]*(?:\.\d+)?\s*\)?',text):
        token=m.group().strip();negative=token.startswith(('(','-','−'))
        token=re.sub(r'[^\d.]','',token)
        try:value=float(token)
        except ValueError:return []
        values.append(-value if negative else value)
    return values


def scale_in(text):
    found=set()
    if re.search(r'in\s+thousands',text,re.I):found.add(1000)
    if re.search(r'in\s+millions',text,re.I):found.add(1000000)
    return next(iter(found)) if len(found)==1 else None


def table_matches(html,current_year,expected):
    soup=BeautifulSoup(html,'html.parser')
    for node in soup(['script','style','ix:header','ix:hidden']):node.decompose()
    doc=' '.join(soup.stripped_strings);global_scale=scale_in(doc)
    matched=[];routes=Counter()
    for ti,table in enumerate(soup.find_all('table')):
        if table.find('table') is not None:continue  # No nested repeated rows/container proofs.
        content=' '.join(table.stripped_strings)
        pos=doc.find(content);context=doc[max(0,pos-700):pos] if pos>=0 else ''
        scale=scale_in(content[:1800]) or global_scale
        year_tokens=[int(x) for x in re.findall(r'\b20\d{2}\b',content[:1800])]
        year_order=[]
        for y in year_tokens:
            if y not in year_order:year_order.append(y)
        quarter=bool(re.search(r'three\s+months|thirteen\s+weeks|quarter',content[:1800],re.I))
        year_ok=year_order[:2]==[current_year,current_year-1]
        for ri,tr in enumerate(table.find_all('tr')):
            cells=[' '.join(c.stripped_strings).replace('\xa0',' ') for c in tr.find_all(['td','th'],recursive=False)]
            nonempty=[(i,x) for i,x in enumerate(cells) if x]
            if not nonempty:continue
            i,label=nonempty[0];label=re.sub(r'\s+',' ',label).strip()
            metric=next((k for k,pattern in LABELS.items() if pattern.fullmatch(label)),None)
            if metric is None:continue
            routes['recognized_metric_rows']+=1
            vals=numbers(' '.join(cells[i+1:]))
            exp=expected.get(metric)
            if scale is None or not year_ok or not quarter or exp is None or len(vals)<2:
                routes['missing_scale_quarter_year_or_values']+=1;continue
            if not all(np.isfinite(exp)):continue
            actual=[vals[0]*scale,vals[1]*scale]
            if all(abs(x-y)<=scale/2+1e-6 for x,y in zip(actual,exp)):
                matched.append(dict(metric=metric,table_index=ti,row_index=ri,label=label,scale=scale,
                    literal_values=vals[:2],reported_values=actual,later_filing_values=list(exp),
                    rounding_tolerance=scale/2,year_order=year_order[:2],
                    header=content[:1800],preceding_context=context,
                    statement_title_hint=bool(re.search(r'statements?.{0,80}(?:operations|income)',context+content[:500],re.I)),
                    original_row_text=' '.join(cells)))
            else:routes['values_differ_or_other_columns']+=1
    return matched,dict(routes)


def review(parent,output):
    if output.exists():raise ValueError('Fresh review directory required')
    protocol=READ(parent/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    base=READ(parent/'report.json');verify_hashes(parent,base['files'])
    docs=READ(parent/'documents.json');verify_hashes(parent,docs['files'])
    output.mkdir(parents=True)
    files=[Path(__file__),Path('tests/test_us_earnings_release_table_review.py'),parent/'protocol.json',parent/'report.json',parent/'documents.json',
        parent/'release-evidence.json',parent/'cases.parquet',parent/'reconstructed-cases.parquet']
    atomic_json(output/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(f):digest(f) for f in files},parent=str(parent),
        rule='Verify first two current/prior quarter columns, explicit scale, recognizable GAAP-like revenue/operating label, literal numbers and expected original-quarter values within half reporting-unit rounding. Matches are technical,not a global accounting-scope certificate.',
        forbidden='No direction promoted from a later10-Q unless original-release values validated; no market outcomes, new source, SQL, fit, model or order.',
        independent_human_review=False))
    cases=pd.read_parquet(parent/'cases.parquet');reconstructed=pd.read_parquet(parent/'reconstructed-cases.parquet')
    index={x['accession']:x for x in docs['documents']};evidence=READ(parent/'release-evidence.json')['records']
    grouped={}
    for e in evidence:grouped.setdefault(e['case_accession'],set()).add(e['release_accession'])
    cache={};results=[];proof=[];counts=Counter()
    for c in cases.to_dict('records'):
        original=c['accession_number'];r=reconstructed[reconstructed.case_accession.eq(original)].iloc[0]
        accn=r.release_accession if pd.notna(r.release_accession) else None
        reasons=[];metric_matches=[]
        if accn is None:reasons.append('NO_EXPLICIT_TARGET_QUARTER_RELEASE')
        elif not c['numeric_ready']:reasons.append('ORIGINAL_QUARTER_NUMBERS_UNQUALIFIED')
        else:
            # Only the EARLIEST identified release; a later correction must not be used at that time.
            expected=dict(revenue=(c['revenue'],c['prior_revenue']),operating=(c['operating'],c['prior_operating']))
            doc=index[accn]
            if accn not in cache:
                b=(parent/doc['receipt']['file']).read_text(encoding='utf-8',errors='replace');cache[accn]=exhibits(b)
            for part_type,html in cache[accn]:
                matches,routes=table_matches(html,pd.Timestamp(c['fiscal_period_end']).year,expected)
                counts.update(routes)
                for m in matches:
                    m.update(symbol=c['symbol'],case_accession=original,release_accession=accn,exhibit_type=part_type,
                        raw_document_sha256=doc['receipt']['sha256'])
                    metric_matches.append(m)
            metrics={x['metric'] for x in metric_matches}
            if 'revenue' not in metrics:reasons.append('RELEASE_REVENUE_CURRENT_PRIOR_NOT_MATCHED')
            if 'operating' not in metrics:reasons.append('RELEASE_OPERATING_CURRENT_PRIOR_NOT_MATCHED')
        proof+=metric_matches
        complete=not reasons and bool(metric_matches)
        results.append(dict(symbol=c['symbol'],case_accession=original,release_accession=accn,
            original_numeric_ready=bool(c['numeric_ready']),corrected_reaction=str(r.corrected_reaction) if pd.notna(r.corrected_reaction) else None,
            retained_in_corrected_top10=bool(r.retained_in_corrected_top10),release_four_values_matched=complete,
            first_worldwide_announcement_qualified=False,accounting_scope_manually_qualified=False,
            historical_local_receipt_proven=False,qualified_direction='ABSTAIN',reasons=reasons))
    atomic_json(output/'table-evidence.json',dict(proofs=proof,routing_counts=dict(counts)))
    atomic_json(output/'case-review.json',dict(rows=results))
    result=dict(status='ORIGINAL_RELEASE_TABLE_REVIEW_COMPLETED_NO_DIRECTION_PROMOTION',cases=len(results),
        earliest_release_four_values_matched=sum(x['release_four_values_matched'] for x in results),
        matched_and_still_top10=sum(x['release_four_values_matched'] and x['retained_in_corrected_top10'] for x in results),
        qualified_directions=0,reasons=dict(Counter(y for x in results for y in x['reasons'])),
        reserve='Literal source-table matching is not a certified merger/issuer scope or first-worldwide-release review. Unmatched or later-corrected values are never assumed available earlier.',
        sql=False,api_calls=0,llm_calls=0,training=False,price_outcomes=False,orders=False,
        files={n:digest(output/n) for n in ['protocol.json','table-evidence.json','case-review.json']})
    atomic_json(output/'report.json',result);print(json.dumps({k:v for k,v in result.items() if k!='files'},default=str))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();review(a.parent,a.output)
