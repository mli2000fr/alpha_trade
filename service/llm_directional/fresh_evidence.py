"""V7: bounded fresh factual context; no downloads, SQL writes or blanket qualifications.

Legacy builders/prompts remain immutable. Derived qualifications live only in
the archived per-analysis packet, never update source tables or legal blocks.
"""
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
import hashlib
import json
import math
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from sqlalchemy import inspect,text

from .local_evidence import enrich_contexts as legacy_contexts,_utc
from .prompts import FRESH_VERSION
from .repository import dumps,digest

NY=ZoneInfo('America/New_York')
FUND_FIELDS=('revenue','eps','net_margin','operating_margin','gross_margin','revenue_growth_yoy',
             'eps_growth_yoy','debt_to_equity','current_ratio','shares_outstanding')


def day(value):
    return value if type(value) is date else date.fromisoformat(str(value)[:10])


def numeric(value):
    if value is None:
        return None
    if isinstance(value,bool):
        raise ValueError('Boolean instead of numeric value')
    value=float(value)
    if not math.isfinite(value):
        raise ValueError('Non-finite value')
    return value


def stamp(value):
    return _utc(value).isoformat()


def fresh(value,cutoff,*,hours=None,days=None):
    if value is None:
        return False
    received=_utc(value)
    return cutoff-timedelta(hours=hours or 0,days=days or 0)<=received<cutoff


def facts(kind,identity,value,received,*,eligible=False,**metadata):
    result=dict(source_id=f'{kind}:{identity}',kind=kind,text=dumps(value),
        available_at_utc=stamp(received),eligible_for_direction=eligible,
        context_qualification='QUALIFIED_FACTUAL_CONTEXT',**metadata)
    return result


def existing_sources(ctx,cfg,cutoff):
    retained=[];excluded=[]
    for original in ctx['local_evidence']:
        source=dict(original)
        reason=None
        if source['kind']=='consensus':
            if not fresh(source['available_at_utc'],cutoff,hours=cfg.evidence_consensus_max_age_hours):
                reason='STALE_CONSENSUS_RECEIPT'
            data=json.loads(source['text']);values=data['values']
            period=day(data['fiscal_period_end']);today=cutoff.astimezone(NY).date()
            if not today-timedelta(days=120)<=period<=today+timedelta(days=400):
                reason='IRRELEVANT_FISCAL_PERIOD'
            for prefix in ('eps','revenue'):
                lo=numeric(values.get(prefix+'_low'));avg=numeric(values.get(prefix+'_avg'));hi=numeric(values.get(prefix+'_high'))
                if (lo is not None and hi is not None and lo>hi
                        or avg is not None and lo is not None and avg<lo
                        or avg is not None and hi is not None and avg>hi):
                    reason='INCONSISTENT_CONSENSUS_RANGE'
            history=[]
            for old in source.get('prior_actual_snapshots',[]):
                checked,discarded=existing_sources({'local_evidence':[old]},cfg,cutoff)
                history.extend(dict(s,role='HISTORICAL_COMPARISON',eligible_for_direction=False) for s in checked)
                excluded.extend(discarded)
            source['prior_actual_snapshots']=history
            source['context_qualification']=('UPSTREAM_QUALIFIED' if source['eligible_for_direction']
                                             else 'FRESH_CONTEXT_ONLY_UNQUALIFIED_UNITS_OR_PERIOD')
        else:
            if (not fresh(source['available_at_utc'],cutoff,hours=cfg.evidence_news_max_receipt_age_hours)
                    or not fresh(source['publication_utc'],cutoff,days=cfg.evidence_news_max_age_days)):
                reason='STALE_NEWS_PUBLICATION_OR_RECEIPT'
            source['context_qualification']='UPSTREAM_IDENTITY_QUALIFIED' if source['identity_qualified'] else 'FRESH_CONTEXT_ONLY_IDENTITY_UNVERIFIED'
        if reason:
            excluded.append(dict(source_id=source['source_id'],reason=reason))
        else:
            source['freshness_qualified']=True
            retained.append(source)
    return retained,excluded


def calendar(conn,ctx,cfg,cutoff,names):
    if 'stock_earnings_calendar' not in names:
        return dict(status='TABLE_MISSING',sources=[])
    today=cutoff.astimezone(NY).date()
    rows=conn.execute(text('''SELECT earnings_date,eps_estimate,revenue_estimate,fiscal_period,last_updated
        FROM stock_earnings_calendar WHERE symbol=:symbol AND earnings_date>=:day
        AND earnings_date<=:end AND last_updated<:cutoff ORDER BY earnings_date LIMIT 3'''),
        dict(symbol=ctx['symbol'],day=today,end=today+timedelta(days=45),cutoff=cutoff.replace(tzinfo=None))).mappings().all()
    sources=[];stale=0
    for row in rows:
        if not fresh(row['last_updated'],cutoff,hours=cfg.evidence_calendar_max_age_hours):
            stale+=1;continue
        value=dict(symbol=ctx['symbol'],next_earnings_date=str(row['earnings_date']),
            calendar_days_from_analysis=(day(row['earnings_date'])-today).days,
            announcement_time=None,date_status='PROVIDER_ESTIMATED_NOT_CONFIRMED',
            eps_estimate=numeric(row['eps_estimate']),revenue_estimate=numeric(row['revenue_estimate']),
            currency_and_revenue_units='UNVERIFIED',fiscal_period=row['fiscal_period'])
        sources.append(facts('earnings_calendar',digest(value)[:20],value,row['last_updated'],
            freshness_qualified=True,identity_qualified=False,
            caveat='Mutable calendar frozen at analysis; upcoming date is NOT bullish/bearish proof. No actual future results supplied.'))
    return dict(status='AVAILABLE' if sources else 'NO_FRESH_UPCOMING_CALENDAR',excluded_stale=stale,sources=sources)


def sec_url(url,cik,accession):
    try:
        parts=urlsplit(url or '')
        expected=f'/Archives/edgar/data/{int(cik)}/'
        compact=accession.replace('-','')
        return (parts.scheme=='https' and parts.hostname in ('sec.gov','www.sec.gov')
            and parts.username is None and parts.password is None and parts.port in (None,443)
            and parts.path.startswith(expected) and compact in parts.path.replace('-',''))
    except (ValueError,TypeError):
        return False


def body_document(body):
    """SEC full submissions contain headers/binary exhibits, not just primary HTML.

    Select an embedded EX-99 release first when present, otherwise the primary
    filing's TEXT. Keep the full archived submission hash as provenance.
    """
    candidates=[]
    for block in re.findall(r'<DOCUMENT\b[^>]*>(.*?)</DOCUMENT\s*>',body,re.I|re.S):
        kind=re.search(r'<TYPE>\s*([^\r\n<]+)',block,re.I)
        content=re.search(r'<TEXT\b[^>]*>(.*?)</TEXT\s*>',block,re.I|re.S)
        if not kind or not content:
            continue
        form=kind.group(1).strip().upper()
        if form.startswith('EX-99') or form in ('8-K','8-K/A','6-K','6-K/A','10-Q','10-Q/A','10-K','10-K/A'):
            candidates.append((0 if form.startswith('EX-99') else 1,content.group(1),form))
    if candidates:
        _,selected,form=min(candidates,key=lambda item:item[0])
        return selected,form
    # Plain HTML remains unchanged; remove a standalone submission header if any.
    return re.split(r'</SEC-HEADER\s*>',body,flags=re.I)[-1],None


def clean_excerpt(body,limit,*,prefer_lead=False):
    # No execution, no URL access. Text extraction only; preserve numeric tokens.
    soup=BeautifulSoup(body,'html.parser')
    for tag in soup.find_all(['script','style','noscript','template','ix:hidden']):
        tag.decompose()
    value=re.sub(r'\s+',' ',soup.get_text(' ',strip=True)).strip()
    match=re.search(r'\b(results of operations|financial results|guidance|outlook|equity offering|'
                    r'public offering|private placement|credit agreement|material agreement)\b',value,re.I)
    # A release's lead contains the issuer, announcement and key figures. Do not
    # jump to a late generic 'outlook' mention/safe-harbor section instead.
    start=max(0,match.start()-200) if match and not prefer_lead else 0
    return value[start:start+limit],start>0 or len(value)>limit


def sec(conn,ctx,cfg,cutoff,names):
    needed={'sec_filing_raw','security_master_snapshots','pit_collection_runs'}
    if not needed<=names:
        return dict(status='TABLES_MISSING',sources=[])
    if cfg.evidence_sec_max_documents==0:
        return dict(status='DISABLED',sources=[])
    params=dict(symbol=ctx['symbol'],cutoff=cutoff.replace(tzinfo=None),
        since=(cutoff-timedelta(days=7)).replace(tzinfo=None))
    # Latest completed master snapshot; never trust a bare ticker/filer mapping.
    master=conn.execute(text('''SELECT s.cik,s.snapshot_date,s.available_at,r.finished_at
        FROM security_master_snapshots s JOIN pit_collection_runs r ON r.run_id=s.run_id
        WHERE s.symbol=:symbol AND s.available_at<:cutoff AND r.finished_at<:cutoff
        AND r.status IN ('COMPLETED','COMPLETED_WITH_WARNINGS') AND s.available_at>=:since
        ORDER BY s.snapshot_date DESC,s.available_at DESC LIMIT 10'''),params).mappings().all()
    ciks={str(r['cik']).zfill(10) for r in master if r['snapshot_date']==master[0]['snapshot_date'] and r['cik']} if master else set()
    if len(ciks)!=1:
        return dict(status='NO_FRESH_UNAMBIGUOUS_CIK',sources=[])
    cik=next(iter(ciks))
    params.update(cik=cik,publication_since=cutoff.astimezone(NY).date()-timedelta(days=cfg.evidence_sec_max_age_days),
        today=cutoff.astimezone(NY).date(),cap=cfg.evidence_sec_max_documents*3)
    rows=conn.execute(text('''SELECT f.accession_number,f.cik,f.symbol,f.form_type,f.filing_date,
        f.acceptance_datetime,f.filing_url,f.content_sha256,f.available_at,f.observed_at,
        CASE WHEN OCTET_LENGTH(f.content_text)<=2000000 THEN f.content_text ELSE NULL END AS content_text,
        r.finished_at AS collection_finished_at
        FROM sec_filing_raw f JOIN pit_collection_runs r ON r.run_id=f.run_id
        WHERE f.symbol=:symbol AND f.cik=:cik AND f.filing_date BETWEEN :publication_since AND :today
        AND f.form_type IN ('8-K','8-K/A','6-K','6-K/A','10-Q','10-Q/A','10-K','10-K/A')
        AND f.available_at<:cutoff AND f.observed_at<:cutoff AND r.finished_at<:cutoff
        AND r.status IN ('COMPLETED','COMPLETED_WITH_WARNINGS')
        ORDER BY f.filing_date DESC,f.accession_number DESC LIMIT :cap'''),params).mappings().all()
    sources=[];excluded=[]
    for raw in rows:
        row=dict(raw)
        bodies=[]
        if 'sec_filing_documents' in names:
            docs=conn.execute(text('''SELECT d.*,r.finished_at AS doc_finished_at FROM sec_filing_documents d
                JOIN pit_collection_runs r ON r.run_id=d.run_id WHERE d.accession_number=:accession
                AND d.document_type LIKE 'EX-99%' AND d.available_at<:cutoff AND d.observed_at<:cutoff
                AND r.finished_at<:cutoff AND r.status IN ('COMPLETED','COMPLETED_WITH_WARNINGS')
                AND OCTET_LENGTH(d.content_blob)<=2000000 ORDER BY d.document_sequence LIMIT 2'''),
                dict(accession=row['accession_number'],cutoff=params['cutoff'])).mappings().all()
            for d in docs:
                body=bytes(d['content_blob']) if d['content_blob'] is not None else b''
                bodies.append((body,d['content_sha256'],d['document_url'],str(d['id']),
                    max(_utc(d['available_at']),_utc(d['doc_finished_at'])),d['document_type']))
        body=(row['content_text'] or '').encode('utf-8')
        if body and len(body)<=2000000:
            bodies.append((body,row['content_sha256'],row['filing_url'],'primary',
                max(_utc(row['available_at']),_utc(row['collection_finished_at'])),row['form_type']))
        for body,expected_hash,url,identifier,received,document_type in bodies:
            if not body or hashlib.sha256(body).hexdigest()!=expected_hash or not sec_url(url,cik,row['accession_number']):
                excluded.append(dict(accession=row['accession_number'],reason='HASH_OR_SEC_URL_MISMATCH'));continue
            if not fresh(received,cutoff,days=cfg.evidence_sec_max_age_days):
                excluded.append(dict(accession=row['accession_number'],reason='STALE_SEC_RECEIPT'));continue
            document,embedded_type=body_document(body.decode('utf-8',errors='replace'))
            excerpt,truncated=clean_excerpt(document,cfg.evidence_sec_excerpt_chars,
                prefer_lead=(embedded_type or document_type).startswith('EX-99'))
            if len(excerpt)<100:
                excluded.append(dict(accession=row['accession_number'],reason='NO_SUBSTANTIVE_TEXT'));continue
            source=dict(source_id=f"sec:{row['accession_number']}:{identifier}:{expected_hash}",kind='sec',
                text=excerpt,available_at_utc=stamp(received),publication_date=str(row['filing_date']),
                publication_precision='FILING_DATE_ONLY',acceptance_datetime_raw=str(row['acceptance_datetime']),
                source_text_hash=expected_hash,accession=row['accession_number'],cik=cik,url=url,
                symbol=ctx['symbol'],form=row['form_type'],document_type=document_type,
                excerpt_document_type=embedded_type or document_type,
                excerpt_container='ARCHIVED_FULL_SUBMISSION' if embedded_type else 'ARCHIVED_DOCUMENT',
                text_truncated=truncated,identity_qualified=True,integrity_qualified=True,
                freshness_qualified=True,eligible_for_direction=True,
                context_qualification='CIK_HASH_COMPLETED_RUN_VERIFIED_PRIMARY_SOURCE',
                caveat='Factual primary evidence, not a directional guarantee. Date-only filing is not a fabricated publication time. '
                    'Available time conservatively includes collection completion; no historical PIT reconstruction.')
            sources.append(source)
            if len(sources)>=cfg.evidence_sec_max_documents:
                break
        if len(sources)>=cfg.evidence_sec_max_documents:
            break
    return dict(status='AVAILABLE' if sources else 'NO_FRESH_QUALIFIED_SEC',sources=sources,
        exclusions=excluded[:10],bounded_sample=True,cik=cik)


def fundamentals(conn,ctx,cfg,cutoff,names):
    if 'stock_fundamentals_daily' not in names:
        return dict(status='TABLE_MISSING',sources=[])
    today=cutoff.astimezone(NY).date()
    columns=','.join(FUND_FIELDS)
    rows=conn.execute(text(f'''SELECT id,trade_date,available_date,fetched_at,fiscal_period_end,
        form,accession_number,source,{columns} FROM stock_fundamentals_daily
        WHERE symbol=:symbol AND UPPER(source)='SEC_EDGAR' AND fetched_at<:cutoff
        AND fetched_at>=:fetched_since AND trade_date BETWEEN :filed_since AND :today
        AND available_date<=:today AND fiscal_period_end BETWEEN :period_since AND :today
        ORDER BY fiscal_period_end DESC,trade_date DESC,fetched_at DESC LIMIT 3'''),
        dict(symbol=ctx['symbol'],cutoff=cutoff.replace(tzinfo=None),today=today,
             fetched_since=(cutoff-timedelta(days=cfg.evidence_fundamental_max_fetch_age_days)).replace(tzinfo=None),
             filed_since=today-timedelta(days=cfg.evidence_fundamental_max_filing_age_days),
             period_since=today-timedelta(days=cfg.evidence_fundamental_max_period_age_days))).mappings().all()
    for row in rows:
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',str(row['accession_number'] or '')):
            continue
        # Date-only upstream availability is conservatively known after its full NY day.
        available_day_end=datetime.combine(day(row['available_date'])+timedelta(days=1),datetime.min.time(),NY)
        received=max(_utc(row['fetched_at']),available_day_end.astimezone(timezone.utc))
        if received>=cutoff:
            continue
        values={key:numeric(row[key]) for key in FUND_FIELDS}
        value=dict(symbol=ctx['symbol'],fiscal_period_end=str(row['fiscal_period_end']),
            filing_date=str(row['trade_date']),form=row['form'],accession=row['accession_number'],
            values=values,units='UPSTREAM_SEC_NORMALIZATION; ratio scale/TTM comparability not independently qualified')
        source=facts('fundamentals',f"{row['id']}:{digest(value)[:16]}",value,received,
            freshness_qualified=True,source='SEC_EDGAR',filing_date=str(row['trade_date']),
            fiscal_period_end=str(row['fiscal_period_end']),fetch_at_utc=stamp(row['fetched_at']),
            caveat='Latest available accounts, not news today. SEC normalized financial context only; no Yahoo fallback. '
                   'Not independently sufficient to authorize LONG/SHORT.')
        return dict(status='AVAILABLE',sources=[source])
    return dict(status='NO_FRESH_QUALIFIED_FUNDAMENTALS',sources=[])


def market(conn,ctx,cfg,cutoff,names):
    if 'stock_bars_daily' not in names:
        raise ValueError('Barres daily absentes ; aucun appel LLM avec cours périmés')
    from common.market_calendar import get_market_calendar
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    trade=day(ctx['trade_date']);today=cutoff.astimezone(NY).date()
    closed=[s for s in calendar.sessions(today-timedelta(days=15),today)
            if s.is_open and s.close_at_utc is not None and s.close_at_utc<=cutoff]
    if not closed or max(s.session_date for s in closed)!=trade:
        raise ValueError('Séance de prix périmée/non close pour le contexte LLM')
    q='''SELECT symbol,`date`,open,high,low,close,volume,is_filled,data_source,data_adjustment,
        ingested_at,last_updated FROM stock_bars_daily WHERE symbol=:symbol AND `date`<=:day
        AND `date`>=:since AND ingested_at<:cutoff AND last_updated<:cutoff
        ORDER BY `date` DESC LIMIT 21'''
    params=dict(symbol=ctx['symbol'],day=trade,since=trade-timedelta(days=45),cutoff=cutoff.replace(tzinfo=None))
    raw=[dict(r) for r in conn.execute(text(q),params).mappings()]
    for row in raw:
        row['data_source']=str(row['data_source']).lower()
    if not raw or day(raw[0]['date'])!=trade:
        raise ValueError(f"Cours J manquant/périmé pour {ctx['symbol']} ; pas de repli J-1")
    allowed={'eodhd','eodhd_eod','alpaca_sip'}
    def valid(r):
        vals=[numeric(r[k]) for k in ('open','high','low','close')]
        return (r['is_filled']==0 and str(r['data_source']).lower() in allowed
            and all(v is not None and v>0 for v in vals)
            and vals[2]<=min(vals[0],vals[3])<=max(vals[0],vals[3])<=vals[1])
    if not valid(raw[0]):
        raise ValueError(f"OHLC/flux J non qualifié pour {ctx['symbol']}")
    # Only a contiguous, same-source/same-adjustment history may generate path summaries.
    rows=[];warnings=[]
    for row in raw:
        if (not valid(row) or row['data_source']!=raw[0]['data_source']
                or row['data_adjustment']!=raw[0]['data_adjustment']):
            warnings.append('INCONSISTENT_HISTORICAL_BAR_OR_PROVENANCE');break
        rows.append(row)
    expected=[s.session_date for s in calendar.sessions(trade-timedelta(days=45),trade) if s.is_open]
    while rows and [day(r['date']) for r in rows]!=list(reversed(expected[-len(rows):])):
        rows.pop();warnings.append('HISTORICAL_SESSION_GAP')
    if not rows:
        raise ValueError('Historique de séance incohérent')
    split_guard='NOT_AVAILABLE'
    if 'corporate_action_source_events' in names:
        events=conn.execute(text('''SELECT COUNT(*) FROM corporate_action_source_events
            WHERE symbol=:symbol AND LOWER(action_type) IN ('split','reverse_split','stock_split')
            AND effective_date>:since AND effective_date<=:day AND available_at<:cutoff'''),
            dict(params,since=day(rows[-1]['date']))).scalar_one()
        split_guard='KNOWN_SPLIT_IN_WINDOW' if events else 'NO_KNOWN_SPLIT_NOT_EXHAUSTIVE'
        if events:
            rows=rows[:1];warnings.append('PATH_SUPPRESSED_KNOWN_CORPORATE_ACTION')
    head=rows[0];close=numeric(head['close']);volume=numeric(head['volume'])
    returns={str(n):round((close/numeric(rows[n]['close'])-1)*100,4) if len(rows)>n else None for n in (1,5,10,20)}
    previous=numeric(rows[1]['close']) if len(rows)>1 else None
    volumes=[numeric(r['volume']) for r in rows[1:21]]
    volume_ratio=None
    if len(volumes)==20 and all(v is not None and v>0 for v in volumes) and volume is not None and volume>0:
        volume_ratio=round(volume/(sum(volumes)/20),4)
    value=dict(symbol=ctx['symbol'],trade_date=str(trade),source=head['data_source'],
        adjustment=head['data_adjustment'],close=close,open=numeric(head['open']),high=numeric(head['high']),low=numeric(head['low']),
        volume=volume if volume is not None and volume>=0 else None,
        volume_relative_to_prior_20_sessions=volume_ratio,returns_pct=returns,
        gap_pct=round((numeric(head['open'])/previous-1)*100,4) if previous else None,
        intraday_return_pct=round((close/numeric(head['open'])-1)*100,4),
        high_low_range_pct=round((numeric(head['high'])-numeric(head['low']))/close*100,4),
        history_sessions=len(rows),corporate_action_guard=split_guard,warnings=sorted(set(warnings)),
        caveat='Descriptive price/volume context, not a directional catalyst or calibrated signal.')
    receipt=max(_utc(head['ingested_at']),_utc(head['last_updated']))
    source=facts('price_volume',digest(value)[:24],value,receipt,freshness_qualified=True,
        price_trade_date=str(trade),source=head['data_source'],event_basis='LATEST_CLOSED_US_SESSION',
        observation_is_mutable=True,identity_qualified=False)
    closes=[dict(date=str(r['date']),close=numeric(r['close'])) for r in reversed(rows)]
    return dict(status='AVAILABLE',sources=[source],closes=closes,latest_trade_date=str(trade),warnings=sorted(set(warnings)))


def enrich_contexts(engine,contexts,config,cutoff):
    cutoff=_utc(cutoff)
    # Restrict old readers to recent material, preserving their legacy contracts.
    bounded=replace(config,consensus_max_age_days=min(config.consensus_max_age_days,
        max(1,math.ceil(config.evidence_consensus_max_age_hours/24))),
        max_source_age_days=min(config.max_source_age_days,config.evidence_news_max_age_days))
    base=legacy_contexts(engine,contexts,bounded,cutoff)
    names=set(inspect(engine).get_table_names());result=[]
    with engine.connect() as conn:
        for ctx in base:
            ctx['analysis_protocol']=FRESH_VERSION
            sources,exclusions=existing_sources(ctx,config,cutoff)
            statuses=ctx['local_data_status']
            for kind in ('consensus','news'):
                count=sum(s['kind']==kind for s in sources)
                statuses[kind]=dict(status='AVAILABLE' if count else 'NO_FRESH_USABLE_EVIDENCE',
                    included=count,previous_status=statuses[kind],
                    eligible_for_direction=sum(s['kind']==kind and s.get('eligible_for_direction') is True for s in sources))
            for name,reader in (('earnings_calendar',calendar),('sec',sec),('price_volume',market),('fundamentals',fundamentals)):
                packet=reader(conn,ctx,config,cutoff,names)
                sources.extend(packet.pop('sources'))
                if name=='price_volume':
                    ctx['prices_through_decision_date']=packet.pop('closes')
                statuses[name]=packet
            ctx['local_evidence']=sources;ctx['local_evidence_sha256']=digest(sources)
            ctx['evidence_exclusions']=exclusions
            ctx['freshness_policy']=dict(consensus_max_age_hours=config.evidence_consensus_max_age_hours,
                news_publication_max_age_days=config.evidence_news_max_age_days,
                news_receipt_max_age_hours=config.evidence_news_max_receipt_age_hours,
                calendar_max_age_hours=config.evidence_calendar_max_age_hours,sec_max_age_days=config.evidence_sec_max_age_days,
                fundamentals_fetch_max_age_days=config.evidence_fundamental_max_fetch_age_days,
                fundamentals_filing_max_age_days=config.evidence_fundamental_max_filing_age_days,
                fundamentals_period_max_age_days=config.evidence_fundamental_max_period_age_days,
                max_context_age_minutes=config.evidence_context_max_age_minutes)
            result.append(ctx)
    return result


def validate_fresh_packet(context,config,now,*,before_call=False):
    if context.get('analysis_protocol')!=FRESH_VERSION:
        return
    cutoff=_utc(context['evidence_cutoff_utc']);now=_utc(now)
    if cutoff>now or before_call and now-cutoff>timedelta(minutes=config.evidence_context_max_age_minutes):
        raise ValueError('Contexte LLM expiré/futur ; relancer une nouvelle analyse, aucun refresh implicite')
    if digest(context.get('local_evidence'))!=context.get('local_evidence_sha256'):
        raise ValueError('Paquet de preuves altéré')
    for source in context['local_evidence']:
        kind=source['kind'];received=_utc(source['available_at_utc'])
        if received>=cutoff:
            raise ValueError('Preuve reçue après cutoff')
        if kind=='consensus':
            ok=fresh(received,cutoff,hours=config.evidence_consensus_max_age_hours)
            if any(not fresh(old['available_at_utc'],cutoff,hours=config.evidence_consensus_max_age_hours)
                   or old.get('role')!='HISTORICAL_COMPARISON' or old.get('eligible_for_direction') is not False
                   for old in source.get('prior_actual_snapshots',[])):
                raise ValueError('Historique de consensus périmé/non étiqueté')
        elif kind=='news':
            ok=(fresh(received,cutoff,hours=config.evidence_news_max_receipt_age_hours)
                and fresh(source['publication_utc'],cutoff,days=config.evidence_news_max_age_days))
        elif kind=='earnings_calendar':
            ok=fresh(received,cutoff,hours=config.evidence_calendar_max_age_hours)
        elif kind=='sec':
            ok=(fresh(received,cutoff,days=config.evidence_sec_max_age_days)
                and cutoff.astimezone(NY).date()-timedelta(days=config.evidence_sec_max_age_days)
                    <=day(source['publication_date'])<=cutoff.astimezone(NY).date())
        elif kind=='fundamentals':
            today=cutoff.astimezone(NY).date()
            ok=(fresh(source['fetch_at_utc'],cutoff,days=config.evidence_fundamental_max_fetch_age_days)
                and today-timedelta(days=config.evidence_fundamental_max_filing_age_days)<=day(source['filing_date'])<=today
                and today-timedelta(days=config.evidence_fundamental_max_period_age_days)<=day(source['fiscal_period_end'])<=today)
        elif kind=='price_volume':
            ok=source['price_trade_date']==context['trade_date'] and source.get('source') in ('eodhd','eodhd_eod','alpaca_sip')
        else:
            raise ValueError('Type de preuve inconnu')
        if not ok:
            raise ValueError('Preuve périmée dans le paquet LLM : '+kind)
