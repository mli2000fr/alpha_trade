"""Offline semantic dossiers / causal Q1 cohort; no economic outcomes or training."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_public_information_followup import (
    TOP20,READY,OLD,primary_parts,exhibits,visible,quarter_dates,same_month_anchor,
)
from scripts.research.us_earnings_release_table_review import LABELS,numbers,scale_in
from scripts.research.us_earnings_release_recalage import accounting,price_reaction,PRICE

PARENT=Path('artifacts/research/us_public_information_followup/20261020-v1')
COMPACT=Path('artifacts/research/us_public_information_followup/compact-20261020-v1')
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def reporting_units(body):
    tags={'Revenues','SalesRevenueNet','RevenueFromContractWithCustomerExcludingAssessedTax',
          'RevenueFromContractWithCustomerIncludingAssessedTax','Revenue','RevenueFromContractsWithCustomers'}
    proofs=[];focus=[]
    for typ,part in primary_parts(body):
        soup=BeautifulSoup(part,'html.parser')
        units={u.get('id'):u.get_text(' ',strip=True) for u in soup.find_all(re.compile(r'(?:^|:)unit$'))}
        contexts={c.get('id'):c for c in soup.find_all(re.compile(r'(?:^|:)context$'))}
        header={}
        for fact in soup.find_all('ix:nonnumeric'):
            name=str(fact.get('name','')).split(':')[-1]
            if name in ('DocumentPeriodEndDate','DocumentFiscalPeriodFocus','DocumentFiscalYearFocus','CurrentFiscalYearEndDate','TradingSymbol','EntityRegistrantName'):
                header.setdefault(name,set()).add(fact.get_text(' ',strip=True))
        if header:focus.append(dict(form=typ,fields={k:sorted(v) for k,v in header.items()}))
        for fact in soup.find_all('ix:nonfraction'):
            name=str(fact.get('name',''))
            if name.split(':')[-1] not in tags:continue
            context=contexts.get(fact.get('contextref'))
            if context is None or context.find(re.compile(r'(?:explicitmember|typedmember)$')) is not None:continue
            measure=units.get(fact.get('unitref'),'');codes=re.findall(r'iso4217:([A-Z]{3})\b',measure)
            end=context.find(re.compile(r'(?:^|:)enddate$'))
            if len(codes)==1 and end is not None:
                proof=dict(currency=codes[0],tag=name,unit=measure,period_end=end.get_text(strip=True),context_id=context.get('id'))
                if proof not in proofs:proofs.append(proof)
    currencies=sorted({p['currency'] for p in proofs})
    return dict(currency=currencies[0] if len(currencies)==1 else None,proofs=proofs,fiscal_focus=focus)


def release_tables(body,year):
    found=[]
    for typ,html in exhibits(body):
        soup=BeautifulSoup(html,'html.parser')
        for node in soup(['script','style','ix:header','ix:hidden']):node.decompose()
        whole=' '.join(soup.stripped_strings)
        for index,table in enumerate(soup.find_all('table')):
            if table.find('table') is not None:continue
            content=' '.join(table.stripped_strings);where=whole.find(content)
            preceding=whole[max(0,where-700):where] if where>=0 else ''
            head=content[:1800];scale=scale_in(head) or scale_in(preceding)
            years=list(dict.fromkeys(int(x) for x in re.findall(r'\b20\d{2}\b',head)))
            if not scale or years[:2]!=[year,year-1] or not re.search(r'three\s+months|thirteen\s+weeks|quarter',head,re.I):continue
            if re.search(r'non[ -]GAAP|adjusted|reconciliation',head[:350],re.I):continue
            values={};quotes={}
            for row in table.find_all('tr'):
                cells=[' '.join(c.stripped_strings) for c in row.find_all(['td','th'],recursive=False)]
                good=[(i,x) for i,x in enumerate(cells) if x]
                if not good:continue
                i,label=good[0];metric=next((k for k,p in LABELS.items() if p.fullmatch(label.strip())),None)
                if metric is None:continue
                nums=numbers(' '.join(cells[i+1:]))
                if len(nums)>=2:values.setdefault(metric,set()).add(tuple(x*scale for x in nums[:2]));quotes[metric]=' '.join(cells)
            if set(values)=={'revenue','operating'} and all(len(v)==1 for v in values.values()):
                found.append(dict(exhibit=typ,table=index,scale=scale,header=head,preceding_context=preceding,
                    values=[*next(iter(values['revenue'])),*next(iter(values['operating']))],rows=quotes))
    unique={tuple(p['values']) for p in found}
    return dict(values=list(next(iter(unique))) if len(unique)==1 else None,proofs=found)


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh review output required')
    for parent in (PARENT,COMPACT):
        verify_hashes(Path('.'),READ(parent/'protocol.json')['sources'])
        verify_hashes(parent,READ(parent/'documents.json')['files'])
    root.mkdir(parents=True)
    files=[Path(__file__),Path('tests/test_us_public_information_review.py'),
        PARENT/'protocol.json',PARENT/'metadata.json',PARENT/'document-plan.json',PARENT/'documents.json',
        PARENT/'consensus-candidates.parquet',PARENT/'q1-top10.parquet',COMPACT/'protocol.json',COMPACT/'documents.json',
        TOP20/'qualified-cohort.parquet',PRICE,PRICE.parent/'quality-reserves.json']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(p):digest(p) for p in files},
        scope='Review all62 reserved revenue patterns; separate fresh2024Q1 population, no prior93case admission condition.',
        semantics='Reporting units from original issuer inline revenue facts. Period/date extracts must be manually reviewed; debt-conversion windows and fiscal calendar coherence alone are not target-quarter revenue proof.',
        compact='Wrappers around separate original HTML pieces are derivative parsing aids,not fabricated original SGML. Raw URLs/hashes remain attached.',
        chronology='Causal reconstructed public SEC acceptance proxy,not original AlphaTrade receipt nor first worldwide IR. Qualification NOW,never backdated.',
        reaction='Stock previous close to reaction close minus SPY; entry would follow at next open. No later prices read; no win-rate/PnL or model.',
        sql=False,api_calls=0,llm_calls=0,training=False,orders=False,production_changes=False)
    atomic_json(root/'protocol.json',p);return p


def load_bodies():
    full={r['accession']:r for r in READ(PARENT/'documents.json')['documents']}
    compact={r['accession']:r for r in READ(COMPACT/'documents.json')['documents']}
    cache={}
    def get(accession):
        if accession in cache:return cache[accession]
        record=full.get(accession,{}).get('receipt',{})
        if record.get('status')=='OK':
            result=((PARENT/record['file']).read_text(encoding='utf-8',errors='replace'),[dict(root=str(PARENT),receipt=record)],True)
        else:
            c=compact.get(accession,{});parts=[];refs=[]
            for piece in c.get('pieces',[]):
                receipt=piece['receipt']
                if receipt.get('status')=='OK':
                    html=(COMPACT/receipt['file']).read_text(encoding='utf-8',errors='replace')
                    parts.append('<DOCUMENT><TYPE>'+piece['document_type']+'\n<TEXT>'+html+'</TEXT></DOCUMENT>')
                    refs.append(dict(root=str(COMPACT),receipt=receipt,role=piece['role'],derivative_wrapper=True))
            result=('\n'.join(parts),refs,bool(parts) and c.get('attachments_complete',False))
        cache[accession]=result;return result
    return get


def build(root):
    prepare(root)
    if (root/'evidence.json').exists():raise ValueError('Immutable semantic evidence')
    get=load_bodies();plan=READ(PARENT/'document-plan.json');metadata={r['symbol']:r for r in READ(PARENT/'metadata.json')['issuers']}
    candidates=pd.read_parquet(PARENT/'consensus-candidates.parquet');consensus=[]
    for link in plan['consensus']:
        row=candidates[candidates.symbol.eq(link['symbol'])].iloc[0];currency=[];dates=[];hints=[];focus=[];references=[]
        for accession in link['accessions']:
            body,refs,complete=get(accession)
            references.append(dict(accession=accession,pieces=refs,complete=complete))
            if not body:continue
            result=reporting_units(body)
            currency += [dict(accession=accession,**proof) for proof in result['proofs']]
            focus += [dict(accession=accession,**proof) for proof in result['fiscal_focus']]
            for typ,part in primary_parts(body)+exhibits(body):
                text=visible(part)
                for found in quarter_dates(text,prospective=True):
                    if same_month_anchor(found['end'],row.fiscal_anchor):dates.append(dict(accession=accession,form=typ,**found))
                if typ.startswith('EX-99'):
                    found=list(re.finditer(r'(?:first|second|third|fourth|fiscal).{0,30}quarter.{0,40}(?:2026|2027)|(?:outlook|guidance).{0,35}(?:quarter|revenue)',text,re.I))
                    for match in found[:5]:hints.append(dict(accession=accession,form=typ,quote=text[max(0,match.start()-100):match.end()+450]))
        codes=sorted({p['currency'] for p in currency})
        consensus.append(dict(symbol=row.symbol,rank=int(row.oracle_rank),anchor=row.fiscal_anchor,
            relative=float(row.relative),pattern=row.numeric_pattern,currency=codes[0] if len(codes)==1 else None,
            currency_proofs=currency,fiscal_focus=focus,period_quotes=dates,guidance_hints=hints,
            metadata_complete=link['metadata_complete'],references=references,
            sec_fiscal_year_end=metadata[row.symbol].get('fiscal_year_end')))
        print('Semantic dossier',len(consensus),'/',len(candidates),row.symbol,flush=True)
    releases=[]
    for row in plan['events']:
        body,refs,complete=get(row['accession']);periods=[]
        for typ,part in exhibits(body):
            text=visible(part)
            if not re.search(r'financial results|quarter.{0,40}results|results.{0,40}quarter',text[:5000],re.I):continue
            periods.extend(dict(exhibit=typ,**r) for r in quarter_dates(text) if r['end']<=row['metadata']['filingDate'])
        end=max((r['end'] for r in periods),default=None)
        tables=release_tables(body,int(end[:4])) if end else dict(values=None,proofs=[])
        releases.append(dict(**row,complete_document=complete,source_refs=refs,period_end=end,
            period_quotes=[p for p in periods if p['end']==end],**tables))
    atomic_json(root/'evidence.json',dict(consensus=consensus,releases=releases,
        files={n:digest(root/n) for n in ['protocol.json']}))
    print('Offline dossiers and release evidence complete',flush=True)


def cohort(root):
    prepare(root)
    if (root/'event-report.json').exists():raise ValueError('Immutable Q1 cohort')
    evidence=READ(root/'evidence.json');releases=evidence['releases']
    first={}
    for r in sorted(releases,key=lambda r:(r['metadata'].get('acceptanceDateTime',''),r['accession'])):
        if r['period_end'] is not None:
            first.setdefault((r['symbol'],r['period_end']),r['accession'])
    selected=[r for r in releases if r['in_q1_top10']]
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2023-12-01',end_date='2024-04-08')
    keys=set()
    for r in selected:
        day=pd.Timestamp(r['reaction_date']);j=schedule.index.get_loc(day)
        if r['values'] and first.get((r['symbol'],r['period_end']))==r['accession']:
            keys.update((s,d) for s in (r['symbol'],'SPY') for d in (schedule.index[j-1],day))
    columns=['symbol','date','open','high','low','close','adj_close','volume','is_filled','instrument_id','data_source','data_adjustment']
    prices=pd.read_parquet(PRICE,columns=columns,filters=[('symbol','in',sorted({s for s,_ in keys})),
        ('date','in',sorted({d for _,d in keys}))]) if keys else pd.DataFrame(columns=columns)
    prices=prices[[key in keys for key in zip(prices.symbol,prices.date)]]
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate reaction price')
    lookup={(r['symbol'],r['date']):r for r in prices.to_dict('records')};rows=[]
    for r in selected:
        reasons=[];day=pd.Timestamp(r['reaction_date']);j=schedule.index.get_loc(day)
        if r['period_end'] is None:reasons.append('EXPLICIT_ACTUAL_QUARTER_NOT_RESOLVED')
        elif first[(r['symbol'],r['period_end'])]!=r['accession']:reasons.append('REPEATED_SEC_TARGET_PERIOD')
        if not r['metadata_complete'] or not r['complete_document']:reasons.append('INCOMPLETE_PUBLIC_DOCUMENT_POPULATION')
        side,growth,margin=accounting(r['values'])
        if r['values'] is None:reasons.append('QUARTERLY_SOURCE_TABLE_QUARTET_UNRESOLVED')
        relative=None;price_side='UNKNOWN'
        if not reasons:
            relative,price_side,reason=price_reaction([lookup.get((s,d)) for s in (r['symbol'],'SPY') for d in (schedule.index[j-1],day)])
            if reason:reasons.append(reason)
        agreement=side if not reasons and side in ('LONG','SHORT') and side==price_side else 'ABSTAIN'
        rows.append(dict(symbol=r['symbol'],accession=r['accession'],period_end=r['period_end'],
            acceptance=r['metadata']['acceptanceDateTime'],reaction_date=r['reaction_date'],
            potential_entry=str(schedule.index[j+1])[:10],source_values=r['values'],accounting_pattern=side,
            revenue_growth=growth,margin_change=margin,relative_reaction=relative,price_pattern=price_side,
            provisional_agreement=agreement,reasons=reasons,fully_qualified=False,live_admission=False,
            historical_identity_verified=False,first_worldwide_release_verified=False))
    frame=pd.DataFrame(rows);frame.to_parquet(root/'q1-event-cohort.parquet',index=False)
    prices.to_parquet(root/'reaction-price-inputs.parquet',index=False)
    metadata=READ(PARENT/'metadata.json')['issuers'];q1=READ(PARENT/'protocol.json')['q1_symbols']
    missing=[r['symbol'] for r in metadata if r['symbol'] in q1 and not r['complete']]
    report=dict(status='Q1_2024_CAUSAL_MEMBERSHIP_COHORT_EXPLORATORY_NO_EFFICACY_TEST',
        window='2024-01-01/2024-03-31',oracle_symbol_dates=610,oracle_sessions=61,oracle_symbols=32,
        metadata_missing_issuers=missing,filing_population=len(releases),in_top10_before_source_filters=len(selected),
        first_period_releases=sum(r['period_end'] is not None and first[(r['symbol'],r['period_end'])]==r['accession'] for r in releases),
        source_quartets=sum(r['values'] is not None for r in selected),
        provisional_agreements=frame.provisional_agreement.value_counts().to_dict(),
        reasons=dict(Counter(reason for row in rows for reason in row['reasons'])),
        admission_did_not_use_prior_93_cases=True,first_worldwide_release_verified=False,
        historical_security_master_qualified=False,fully_qualified=0,prices_after_entry_read=False,
        pnl=False,training=False,orders=False,sql=False,api_calls=0,
        files={n:digest(root/n) for n in ['protocol.json','evidence.json','q1-event-cohort.parquet','reaction-price-inputs.parquet']})
    atomic_json(root/'event-report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','build','cohort'],required=True);args=parser.parse_args()
    globals()[args.phase](args.output)
