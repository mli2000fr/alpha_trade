"""Bounded financial-release + price-reaction readiness; no return outcomes.

Existing local SEC facts and READ ONLY SQL metadata only. No API/LLM, training,
production edits, orders, PnL or reconstructed analyst consensus. Fiscal facts
are keyed by accession/start/end/unit, never by filing fy/fp alone.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from sqlalchemy import bindparam, text

from scripts.research.us_consensus_observed_revision_pilot import connect_readonly, utc
from scripts.research.us_directional_information_readiness import query, UNIVERSE
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
SCORES = Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
PRICES = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
CURRENT = Path('artifacts/research/us_directional_information/20261019-v2/observed-revisions-v1/oracle-top10.parquet')
MAP = Path('artifacts/sec_cache/company_tickers.json')
TAGS = {'revenue': ['Revenues','SalesRevenueNet','RevenueFromContractWithCustomerExcludingAssessedTax'],
        'operating': ['OperatingIncomeLoss'], 'eps': ['EarningsPerShareDiluted']}


def date(value):
    try: return pd.Timestamp(value).normalize() if value is not None else None
    except (ValueError, TypeError): return None


def quarter_fact(e):
    start,end,filed = [date(e.get(k)) for k in ('start','end','filed')]
    if any(v is None or pd.isna(v) for v in (start,end,filed)): return False
    try: value=float(e['val'])
    except (ValueError,TypeError,KeyError): return False
    return (70 <= (end-start).days+1 <= 110 and filed>=end and np.isfinite(value)
        and e.get('form') in ('10-Q','10-K') and bool(e.get('accn')))


def same_quarter_prior(current, old):
    """Comparative facts from SAME filing; 52/53-week calendars allowed, not YTD."""
    return (current['accn']==old['accn'] and current['unit']==old['unit']
        and current['tag']==old['tag']
        and 350 <= (date(current['end'])-date(old['end'])).days <= 378
        and 350 <= (date(current['start'])-date(old['start'])).days <= 378
        and abs((date(current['end'])-date(current['start'])).days
            -(date(old['end'])-date(old['start'])).days)<=8)


def unique_value(rows):
    if not rows: return None,'MISSING'
    vals={float(r['val']) for r in rows}
    return (next(iter(vals)),'OK') if len(vals)==1 else (None,'CONFLICTING_FACT_VALUES')


def accounting_direction(revenue, prior_revenue, operating, prior_operating):
    vals=[revenue,prior_revenue,operating,prior_operating]
    if any(v is None or not np.isfinite(v) for v in vals): return 'ABSTAIN',None,None
    if min(revenue,prior_revenue)<=0: return 'ABSTAIN',None,None
    growth=revenue/prior_revenue-1
    margin_change=operating/revenue-prior_operating/prior_revenue
    side='LONG' if growth>0 and margin_change>0 else ('SHORT' if growth<0 and margin_change<0 else 'ABSTAIN')
    return side,growth,margin_change


def facts_events(payload, *, cutoff):
    """Direct 70-110d facts only, same-accession comparatives; no derived Q4/YTD.

    This is a reconstructible filing observation, NOT proof of the first earnings
    announcement, original payload reception, unaffected merger scope or identity.
    """
    groups={}; stats=Counter()
    for metric,tags in TAGS.items():
        for tag in tags:
            obj=payload.get('facts',{}).get('us-gaap',{}).get(tag,{})
            for unit,entries in obj.get('units',{}).items():
                for original in entries:
                    if not quarter_fact(original): continue
                    e=dict(original,tag=tag,unit=unit,metric=metric)
                    if date(e['filed'])>date(cutoff): continue
                    groups.setdefault(e['accn'],[]).append(e)
    result=[]
    for accn,rows in sorted(groups.items()):
        # fy/fp describes the filing; historical comparative dates may differ.
        end=max(date(r['end']) for r in rows)
        if end < pd.Timestamp('2023-01-01'): continue
        latest=[r for r in rows if date(r['end'])==end]
        filed=max(date(r['filed']) for r in latest)
        if not 0 <= (filed-end).days <= 180:
            stats['LATE_OR_COMPARATIVE_ONLY_FILING']+=1; continue
        rev=[r for r in latest if r['metric']=='revenue']
        reasons=[]; chosen={}; components={}
        for metric in ('revenue','operating','eps'):
            unit='USD/shares' if metric=='eps' else 'USD'
            candidates=[r for r in latest if r['metric']==metric and r['unit']==unit]
            if metric=='revenue':
                if len({(r['start'],r['end']) for r in candidates})>1:
                    reasons.append('REVENUE_QUARTER_INTERVAL_AMBIGUOUS')
                if len({float(r['val']) for r in candidates})>1:
                    reasons.append('REVENUE_TAG_CONFLICT')
            # Deterministic tag preference; conflicts remain exclusions.
            candidates.sort(key=lambda r:(TAGS[metric].index(r['tag']),r['start'],r['end']))
            current=candidates[0] if candidates else None
            if current is None:
                components[metric]=(None,None)
                if metric!='eps': reasons.append('MISSING_CURRENT_'+metric.upper())
                continue
            same=[r for r in candidates if r['tag']==current['tag'] and r['start']==current['start']]
            val,why=unique_value(same)
            prior=[r for r in rows if r['metric']==metric and same_quarter_prior(current,r)]
            prior_val,prior_why=unique_value(prior)
            if why!='OK' or prior_why!='OK':
                if metric!='eps': reasons.append(metric.upper()+'_'+why+'_'+prior_why)
            if metric!='revenue' and rev and (date(current['start'])!=date(rev[0]['start'])):
                if metric!='eps': reasons.append('METRIC_INTERVAL_MISMATCH')
            components[metric]=(val,prior_val)
            chosen[metric]=dict(tag=current['tag'],unit=unit,start=current['start'],end=current['end'],
                filed=current['filed'],accn=accn,prior_starts=sorted({r['start'] for r in prior}),
                prior_ends=sorted({r['end'] for r in prior}))
        side,growth,margin=accounting_direction(*components['revenue'],*components['operating'])
        if reasons: side='ABSTAIN'
        result.append(dict(accession_number=accn,filed=filed,fiscal_period_end=end,
            revenue=components['revenue'][0],prior_revenue=components['revenue'][1],
            operating=components['operating'][0],prior_operating=components['operating'][1],
            eps=components['eps'][0],prior_eps=components['eps'][1],revenue_growth=growth,
            operating_margin_change=margin,accounting_pattern=side,
            numeric_ready=not reasons and growth is not None,technical_reasons=sorted(set(reasons)),
            components=chosen,first_publication_proven=False,original_document_verified=False))
    # Original 10-Q/K observation per target quarter; subsequent repeats not new events.
    seen=set(); unique=[]
    for row in sorted(result,key=lambda r:(r['filed'],r['accession_number'])):
        key=str(row['fiscal_period_end'])
        if key in seen: stats['REPEATED_TARGET_PERIOD_RESERVED']+=1;continue
        seen.add(key);unique.append(row)
    return unique,dict(stats)


def reaction_session(filed, days):
    """First FULL session strictly after date-only filing, never invented hour."""
    i=days.searchsorted(date(filed),side='right')
    return days[i] if i<len(days) else None


def reaction(stock_previous,stock_close,spy_previous,spy_close):
    values=[stock_previous,stock_close,spy_previous,spy_close]
    if any(v is None or not np.isfinite(v) or v<=0 for v in values):return None,'UNKNOWN'
    relative=stock_close/stock_previous-spy_close/spy_previous
    return relative,('LONG' if relative>0 else 'SHORT' if relative<0 else 'ABSTAIN')


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh directory required')
    symbols=sorted(set(__import__('re').split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip())))
    inputs=[Path(__file__),Path('tests/test_us_earnings_reaction_readiness.py'),MAP,UNIVERSE,CURRENT,
        SCORES/'protocol.json',SCORES/'final-audit.json',PRICES,PRICES.parent/'quality-reserves.json',
        Path('service/sec/xbrl_mapper.py')]
    tops=[]
    for year in (2024,2025,2026):
        file=SCORES/f'{year}-H20-scores.parquet';inputs.append(file)
        # Explicit allowlist: do NOT read target/amplitude/future-quality columns.
        f=pd.read_parquet(file,columns=['date','symbol','rank','score'])
        if f.duplicated(['date','symbol']).any():raise ValueError('Duplicate scores')
        ranked=f.sort_values(['date','score','symbol'],ascending=[True,False,True]).copy()
        ranked['expected']=ranked.groupby('date').cumcount()+1
        if not ranked['rank'].eq(ranked.expected).all():raise ValueError('Rank mismatch')
        top=ranked[ranked['rank'].le(10)].drop(columns='expected')
        if not top.groupby('date').size().eq(10).all():raise ValueError('IncompleteTOP10')
        tops.append(top)
    top=pd.concat(tops,ignore_index=True)
    selected=sorted(set(top.symbol)|set(pd.read_parquet(CURRENT,columns=['symbol']).symbol))
    raw=READ(MAP);mapping={}
    for x in raw.values():mapping.setdefault(str(x['ticker']).upper(),set()).add(str(x['cik_str']).zfill(10))
    paths={};identities=[]
    for s in selected:
        ciks=sorted(mapping.get(s,set()));file=Path(f'artifacts/sec_cache/companyfacts/CIK{ciks[0]}.json') if len(ciks)==1 else None
        present=file is not None and file.exists()
        identities.append(dict(symbol=s,current_ciks=ciks,cache_path=str(file) if present else None,
            historical_ticker_identity_certified=False))
        if present:paths[s]=str(file);inputs.append(file)
    root.mkdir(parents=True)
    top.to_parquet(root/'top10.parquet',index=False)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(x):digest(x) for x in inputs},
        universe=symbols,symbols=selected,facts_paths=paths,identities=identities,
        oracle_reference='Archived research H20 CatBoost rolling annual models,2024-2026 through1Sep2026,not production annual model IDs; scores only, not outcomes. Current16Oct TOP10 a separate metadata context.',
        historical_primary_start='2024-01-01',historical_primary_end='2026-09-01',
        primary='Realized revenue YoY and operating-margin YoY SAME accession, direct comparable quarters; joint positive LONG, joint negative SHORT, disagreement/missing ABSTAIN. Not consensus surprise.',
        reaction='First full NYSE session strictly AFTER date-only SEC filed; close/previous-close stock return minus SPY. Only reaction <= decision; potential entry NEXT session open.',
        membership='First10 by archived H20 score at REACTION CLOSE before accounting/price filters, no replacements; each accession/target period at most1 event.',
        arms=['ACCOUNTING_ONLY','PRICE_REACTION_ONLY','AGREEMENT_BOTH'],
        future_test='If qualified later: same TP10/SL5 and10sessions for3 arms, no trailing, gap-aware loss-first same-bar, common8bps/leg and20bps stress; H20 secondary only. NO outcome or PnL here.',
        requirements='Original issuer+period+GAAP+currency+scope+first earnings announcement timestamps must be proven. 10-Q filing is not automatically a new earnings announcement; contemporaneous earlier 8-K/IR must be examined.',
        first_filing='Only direct70-110day facts; USD and USD/shares; no annual-as-Q4, YTD subtraction, fy/fp-only period keys, later amendments or cross-accession comparatives.',
        limits=dict(sql_rows=100000,document_sample=20,sample_bytes=8*1024*1024),
        document_selection='Newest10 original10-Q/K, then up to10 preceding8-K/6-K same issuer within45days, deterministic date/symbol/accession ties; total<=20. No price outcomes.',
        minimum_later_confirmation='At least100 independent events and50 distinct decision sessions across2024/25/26; not formal power analysis or guaranteed robustness. Repeated daily membership is not independent.',
        declared_reserves=['current survivor universe and current ticker-CIK mapping,not historical security master',
            'already examined market years,no untouched holdout','current companyfacts cache is not original received vintage',
            'SEC filed date differs from first earnings release; retrieved raw receipts only beginSep2026',
            '8-K/10-Q amendment/restatement/merger scope cannot be certified from numeric tag equality alone'],
        sql='READ ONLY / REPEATABLE READ / UTC session / ROLLBACK',api_calls=0,llm_calls=0,new_training=False,
        price_outcomes=False,sql_writes=False,production_changes=False,orders=False)
    atomic_json(root/'protocol.json',p)
    atomic_json(root/'selection-ready.json',dict(files={'top10.parquet':digest(root/'top10.parquet')},rows=len(top),symbols=int(top.symbol.nunique()),dates=int(top.date.nunique())))
    print('Protocol sealed; TOP10',len(top),'symbol/dates;',len(selected),'cache candidates',flush=True)
    return p


def snapshot(root):
    p=prepare(root)
    if (root/'snapshot-ready.json').exists():raise ValueError('Immutable SQL snapshot')
    engine,conn=connect_readonly()
    try:
        names=['stock_fundamentals_daily','sec_filing_raw','sec_filing_documents']
        schema=query(conn,"SELECT TABLE_NAME,COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE()")
        inventory={'schema':{name:[r['COLUMN_NAME'] for r in schema if r['TABLE_NAME']==name] for name in names}}
        inventory['fundamental_coverage']=query(conn,'''SELECT source,COUNT(*) n,COUNT(DISTINCT symbol) symbols,
            MIN(trade_date) first_event,MAX(trade_date) last_event,MIN(fetched_at) first_fetch,MAX(fetched_at) last_fetch,
            SUM(accession_number IS NOT NULL) accession_present,SUM(fiscal_period_end IS NOT NULL) fiscal_present
            FROM stock_fundamentals_daily WHERE symbol IN :symbols AND trade_date BETWEEN '2023-01-01' AND '2026-10-19'
            GROUP BY source''',p['universe'])
        inventory['filing_coverage']=query(conn,'''SELECT form_type,COUNT(*) n,COUNT(DISTINCT symbol) symbols,
            MIN(filing_date) first_filing,MAX(filing_date) last_filing,MIN(available_at) first_available,
            SUM(content_text IS NOT NULL) content_present FROM sec_filing_raw WHERE symbol IN :symbols
            GROUP BY form_type''',p['universe'])
        cutoff=utc(p['created_at_utc']).tz_localize(None).to_pydatetime()
        fund=query(conn,'''SELECT id,symbol,trade_date,available_date,fetched_at,fiscal_period_end,form,accession_number,
            source,eps,revenue,eps_growth_yoy,revenue_growth_yoy,net_margin,operating_margin
            FROM stock_fundamentals_daily WHERE source='SEC_EDGAR' AND symbol IN :symbols
            AND trade_date BETWEEN '2023-01-01' AND '2026-10-19' AND fetched_at<:cutoff
            ORDER BY symbol,trade_date,id''',p['symbols'],cutoff=cutoff)
        filings=query(conn,'''SELECT id,symbol,cik,accession_number,form_type,filing_date,acceptance_datetime,
            available_at,observed_at,content_sha256,CHAR_LENGTH(content_text) content_chars,run_id,amendment
            FROM sec_filing_raw WHERE symbol IN :symbols AND observed_at<:cutoff AND available_at<:cutoff
            ORDER BY symbol,filing_date,accession_number''',p['symbols'],cutoff=cutoff)
        if max(len(fund),len(filings))>p['limits']['sql_rows']:raise ValueError('Unpartitioned size bound; no truncation')
        # Sample before price outcomes; preceding event reports can reveal earlier announcements.
        sample=[r for r in filings if r['form_type'] in ('10-Q','10-K') and r['content_chars']
            and r['content_chars']<=p['limits']['sample_bytes']]
        sample=sorted(sample,key=lambda r:(-pd.Timestamp(r['filing_date']).value,r['symbol'],r['accession_number']))[:10]
        companions=[r for r in filings if r['form_type'] in ('8-K','6-K') and r['content_chars']
            and r['content_chars']<=p['limits']['sample_bytes'] and any(r['symbol']==q['symbol']
            and 0 <= (date(q['filing_date'])-date(r['filing_date'])).days <=45 for q in sample)]
        sample+=sorted(companions,key=lambda r:(-pd.Timestamp(r['filing_date']).value,r['symbol'],r['accession_number']))[:10]
        bodies=[]
        if sample:
            stmt=text('SELECT accession_number,content_text,content_sha256 FROM sec_filing_raw WHERE id IN :ids')
            bodies=[dict(r) for r in conn.execute(stmt.bindparams(bindparam('ids',expanding=True)),dict(ids=[r['id'] for r in sample])).mappings()]
        conn.rollback()
    finally:conn.close();engine.dispose()
    pd.DataFrame(fund).to_parquet(root/'fundamental-rows.parquet',index=False)
    pd.DataFrame(filings).to_parquet(root/'filing-metadata.parquet',index=False)
    atomic_json(root/'inventory.json',inventory)
    docroot=root/'documents';docroot.mkdir();docmeta=[]
    for r in bodies:
        body=r['content_text'].encode('utf-8');file=f"documents/{r['accession_number']}.txt"
        (root/file).write_bytes(body)
        docmeta.append(dict(accession_number=r['accession_number'],file=file,bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),declared_sha256=r['content_sha256']))
    atomic_json(root/'document-sample.json',dict(selection=p['document_selection'],documents=docmeta))
    files=['fundamental-rows.parquet','filing-metadata.parquet','inventory.json','document-sample.json']+[r['file'] for r in docmeta]
    atomic_json(root/'snapshot-ready.json',dict(finished_at_utc=datetime.now(timezone.utc).isoformat(),
        rows=len(fund),filings=len(filings),documents=len(bodies),files={n:digest(root/n) for n in files}))
    print('READ ONLY snapshot',len(fund),'fundamentals;',len(filings),'filings;',len(bodies),'documents',flush=True)


def build(root):
    p=prepare(root)
    if (root/'report.json').exists():raise ValueError('Immutable finished report')
    for n in ('selection-ready.json','snapshot-ready.json'):verify_hashes(root,READ(root/n)['files'])
    all_events=[];cache=[]
    for i,(s,file) in enumerate(p['facts_paths'].items(),1):
        payload=READ(file);events,stats=facts_events(payload,cutoff='2026-10-19')
        expected=Path(file).stem.removeprefix('CIK')
        if str(payload.get('cik')).zfill(10)!=expected:raise ValueError('Cache CIK mismatch')
        for r in events:r.update(symbol=s,cik=expected,cache_path=file)
        all_events+=events;cache.append(dict(symbol=s,events=len(events),stats=stats,entity_name=payload.get('entityName')))
        if i%20==0:print('Local facts',i,'/',len(p['facts_paths']),flush=True)
    if not all_events:raise ValueError('No local candidate facts; no false success')
    events=pd.DataFrame(all_events);events['technical_reasons']=events.technical_reasons.map(json.dumps)
    events['components']=events.components.map(json.dumps)
    days=mcal.get_calendar('NYSE').schedule(start_date='2023-01-01',end_date='2026-10-20').index
    events['reaction_date']=[reaction_session(x,days) for x in events.filed]
    events['potential_entry_date']=[reaction_session(x,days) if x is not None else None for x in events.reaction_date]
    top=pd.read_parquet(root/'top10.parquet')
    events=events.merge(top.rename(columns={'date':'reaction_date','rank':'oracle_rank','score':'oracle_score'}),on=['reaction_date','symbol'],how='left',validate='many_to_one')
    events['in_frozen_top10']=events.oracle_rank.notna()
    filings=pd.read_parquet(root/'filing-metadata.parquet')
    metadata={r['accession_number']:r for r in filings.to_dict('records')}
    events['original_metadata_present']=events.accession_number.isin(metadata)
    events['received_before_reaction']=False
    for idx,r in events.iterrows():
        src=metadata.get(r.accession_number)
        if src and pd.notna(r.reaction_date) and src['available_at'] is not None:
            close=mcal.get_calendar('NYSE').schedule(start_date=r.reaction_date,end_date=r.reaction_date).iloc[0].market_close
            stamps=[utc(src[k]) for k in ('available_at','observed_at','acceptance_datetime')]
            events.at[idx,'received_before_reaction']=all(x is not None and x<close for x in stamps)
    candidates=events[events.in_frozen_top10].copy()
    # Only load J and previous close for screened candidates, never future H10/H20 bars.
    required=set()
    for r in candidates.itertuples():
        j=days.get_loc(r.reaction_date)
        for s in (r.symbol,'SPY'):
            required.add((s,days[j]));required.add((s,days[j-1]))
    columns=['date','symbol','open','high','low','close','adj_close','volume','is_filled','instrument_id','data_source','data_adjustment']
    prices=pd.read_parquet(PRICES,columns=columns,filters=[('symbol','in',sorted({s for s,_ in required}))]) if required else pd.DataFrame(columns=columns)
    prices=prices[[k in required for k in zip(prices.symbol,prices.date)]]
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate feature prices')
    lookup={(r['symbol'],r['date']):r for r in prices.to_dict('records')}
    checks=[]
    for r in candidates.itertuples():
        j=days.get_loc(r.reaction_date); window=[];reasons=[]
        for s in (r.symbol,'SPY'):
            pair=[lookup.get((s,days[k])) for k in (j-1,j)]
            if any(x is None for x in pair):reasons.append('MISSING_REACTION_PRICE');continue
            for b in pair:
                if (any(b[k] is None or not np.isfinite(b[k]) or b[k]<=0 for k in ('open','high','low','close','adj_close','volume'))
                    or b['is_filled']!=0 or b['low']>min(b['open'],b['close']) or b['high']<max(b['open'],b['close'])):
                    reasons.append('BAD_REACTION_PRICE')
            for k in ('instrument_id','data_source','data_adjustment'):
                if any(pd.isna(b[k]) for b in pair) or pair[0][k]!=pair[1][k]:reasons.append('PRICE_IDENTITY_OR_BASIS_CHANGE')
            window += [b['adj_close'] for b in pair]
        value,side=reaction(*window) if len(window)==4 and not reasons else (None,'UNKNOWN')
        checks.append(dict(symbol=r.symbol,accession_number=r.accession_number,reaction_date=r.reaction_date,
            relative_reaction=value,price_pattern=side,reasons=sorted(set(reasons))))
    check=pd.DataFrame(checks,columns=['symbol','accession_number','reaction_date','relative_reaction','price_pattern','reasons'])
    candidates=candidates.merge(check,on=['symbol','accession_number','reaction_date'],how='left',validate='one_to_one')
    if len(candidates): candidates['agreement_pattern']=np.where(candidates.numeric_ready & candidates.accounting_pattern.eq(candidates.price_pattern),candidates.accounting_pattern,'ABSTAIN')
    else:candidates['agreement_pattern']=pd.Series(dtype=str)
    events.to_parquet(root/'filing-candidates.parquet',index=False)
    candidates.to_parquet(root/'top10-candidates.parquet',index=False)
    prices.to_parquet(root/'reaction-price-inputs.parquet',index=False)
    atomic_json(root/'cache-coverage.json',cache)
    numeric=events[events.numeric_ready];numeric_top=candidates[candidates.numeric_ready]
    years=[]
    for year in (2024,2025,2026):
        e=events[events.reaction_date.dt.year.eq(year) & events.reaction_date.le('2026-09-01')]
        t=candidates[candidates.reaction_date.dt.year.eq(year)]
        years.append(dict(year=year,quarter_observations=len(e),numeric_ready=int(e.numeric_ready.sum()),
            top10_events=len(t),top10_dates=int(t.reaction_date.nunique()),top10_numeric_ready=int(t.numeric_ready.sum()),
            accounting_patterns=t[t.numeric_ready].accounting_pattern.value_counts().to_dict(),
            reaction_patterns=t.price_pattern.value_counts().to_dict(),agreement_patterns=t.agreement_pattern.value_counts().to_dict(),
            original_metadata_present=int(t.original_metadata_present.sum()),received_before_reaction=int(t.received_before_reaction.sum())))
    reasons=Counter(x for xs in events.technical_reasons for x in json.loads(xs))
    result=dict(status='READINESS_COMPLETED_HISTORICAL_NOVELTY_AND_ORIGINAL_EVIDENCE_UNQUALIFIED',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),top10_dates=int(top.date.nunique()),top10_symbol_dates=len(top),
        top10_symbols=int(top.symbol.nunique()),cache_symbols=len(p['facts_paths']),quarter_observations=len(events),
        numeric_ready=len(numeric),top10_events=len(candidates),top10_numeric_ready=len(numeric_top),years=years,
        numeric_reasons=dict(reasons),first_announcement_qualified=0,fully_qualified_events=0,
        documents_sampled=READ(root/'snapshot-ready.json')['documents'],
        rejection='Do not call a 10-Q/10-K a new earnings announcement without earlier8-K/IR checks. Cached numeric records alone cannot prove novelty/accounting-scope or actual historical reception.',
        next_action='Review bounded existing original documents/announcements, match accession and quarter. Do not compute performance or fit until novelty/identity/availability gates and sample feasibility pass.',
        reading='Numeric/price agreement is feature feasibility, NOT accuracy, win-rate, future return or independent validation.',
        sources_verified=True,sql_writes=False,new_training=False,provider_calls=0,llm_calls=0,price_outcomes=False,orders=False,
        files={n:digest(root/n) for n in ['protocol.json','selection-ready.json','snapshot-ready.json',
            'filing-candidates.parquet','top10-candidates.parquet','reaction-price-inputs.parquet','cache-coverage.json']})
    verify_hashes(Path('.'),p['sources'])
    atomic_json(root/'report.json',result)
    print(json.dumps({k:result[k] for k in ('status','top10_events','top10_numeric_ready','years')},default=str),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['prepare','snapshot','build'],required=True);args=a.parse_args()
    {'prepare':prepare,'snapshot':snapshot,'build':build}[args.phase](args.output)
