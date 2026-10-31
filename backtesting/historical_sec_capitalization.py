"""Local SEC-as-reported shares times a contemporaneous RAW regular-session close.

No provider calls, SQL writes, aggregate fundamentals reuse, adjusted-price
multiplication or backdated observation timestamps. CompanyFacts is a current
local extract of historical filings, not an archived vintage of the SEC feed.
"""
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from collections import Counter
from zoneinfo import ZoneInfo
import hashlib
import json
import logging
import math
import re

from sqlalchemy import bindparam, text

from common.instrument_policy import excluded_collective_instrument_reason
from common.market_cap import compute_sec_market_cap
from common.winner_pyramiding import regular_bounds
from modelFactory.oracle.security_continuity import load_security_discontinuities

LOG=logging.getLogger(__name__)
TAGS=(('dei','EntityCommonStockSharesOutstanding'),('us-gaap','CommonStockSharesOutstanding'))
FORMS={'10-K','10-Q','10-K/A','10-Q/A'}


def share_facts(payload,cik):
    if str(payload.get('cik','')).zfill(10)!=str(cik).zfill(10):
        raise ValueError('SEC_CIK_MISMATCH')
    output=[]
    for priority,(namespace,tag) in enumerate(TAGS):
        for raw in payload.get('facts',{}).get(namespace,{}).get(tag,{}).get('units',{}).get('shares',[]):
            try:
                end=date.fromisoformat(raw['end']);filed=date.fromisoformat(raw['filed'])
                value=float(raw['val']);accession=str(raw['accn'])
                if (not math.isfinite(value) or value<=0 or end>filed or raw.get('form') not in FORMS
                        or raw.get('start',raw['end'])!=raw['end']
                        or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession)):
                    continue
                # A filing date without time is usable only AFTER that whole
                # New York calendar day; never invent an intraday acceptance time.
                available=datetime.combine(filed+timedelta(days=1),time(),ZoneInfo('America/New_York')).astimezone(UTC)
                output.append(dict(end=end,filed=filed,available_at=available,value=value,
                    accession=accession,tag=namespace+':'+tag,tag_priority=priority,form=raw['form']))
            except (KeyError,TypeError,ValueError,OverflowError):continue
    return output


def select_shares(facts,day,cutoff,*,max_age_days=365,split_dates=(),identity_events=()):
    if any(day<e.first_successor_date.date() for e in identity_events):
        raise ValueError('CURRENT_ISSUER_BEFORE_KNOWN_IDENTITY_BREAK')
    first=max((e.first_successor_date.date() for e in identity_events),default=date.min)
    eligible=[r for r in facts if r['available_at']<=cutoff and first<=r['end']<=day
        and 0<=(day-r['end']).days<=max_age_days]
    if not eligible:raise ValueError('NO_PUBLIC_SHARE_FACT_BEFORE_CUTOFF')
    # Latest measurement, then publication/revision. Do not let a comparative
    # old period in a more recent annual report replace fresher shares.
    best=max((r['end'],r['available_at'],-r['tag_priority']) for r in eligible)
    choices=[r for r in eligible if (r['end'],r['available_at'],-r['tag_priority'])==best]
    if len({r['value'] for r in choices})!=1:
        raise ValueError('AMBIGUOUS_AS_REPORTED_SHARE_VALUES')
    chosen=min(choices,key=lambda r:r['accession'])
    if any(chosen['end']<=d<=day for d in split_dates):
        raise ValueError('KNOWN_SPLIT_SINCE_SHARE_MEASUREMENT')
    return chosen


class HistoricalSecCapitalizations:
    def __init__(self,conn,universe,*,root=None,max_age_days=365):
        self.conn=conn;self.universe=tuple(sorted(set(universe)))
        self.root=Path(root or Path(__file__).resolve().parents[1]/'artifacts/sec_cache')
        self.max_age_days=max_age_days
        self.loaded=False;self.entities={};self.rejections={};self.splits={}
        self.registry=load_security_discontinuities()
        self.receipts=[];self.manifest={}

    def _load(self):
        if self.loaded:return
        required={'instruments','stock_metadata','corporate_actions_events','stock_bars_intraday'}
        if self.conn.dialect.name=='sqlite':
            names=set(self.conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
        else:
            names=set(self.conn.execute(text('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')).scalars())
        if not required.issubset(names):
            self.rejections={s:'LOCAL_SEC_RECONSTRUCTION_TABLES_UNAVAILABLE' for s in self.universe};self.loaded=True;return
        try:
            mapping_file=self.root/'company_tickers.json'
            data=mapping_file.read_bytes()
            mapping={str(r['ticker']).upper():str(r['cik_str']).zfill(10) for r in json.loads(data).values()}
        except (OSError,ValueError,KeyError,TypeError):
            self.rejections={s:'LOCAL_SEC_CIK_MAPPING_UNAVAILABLE' for s in self.universe};self.loaded=True;return
        self.manifest['mapping_sha256']=hashlib.sha256(data).hexdigest()
        query=text('SELECT local_symbol AS symbol,instrument_id,instrument_type,currency,mapping_status, '
            "display_name FROM instruments WHERE market_code='US_EQ' AND local_symbol IN :symbols"
            ).bindparams(bindparam('symbols',expanding=True))
        metadata_query=text('SELECT symbol,instrument_id,company_name FROM stock_metadata WHERE symbol IN :symbols'
            ).bindparams(bindparam('symbols',expanding=True))
        # The legacy tables can have different MySQL collations. Match the
        # exact symbol AND instrument ID in Python, never coerce the SQL schema.
        metadata={(r['symbol'],r['instrument_id']):r['company_name'] for r in
            self.conn.execute(metadata_query,dict(symbols=self.universe)).mappings()}
        grouped={}
        for row in self.conn.execute(query,dict(symbols=self.universe)).mappings():
            row=dict(row);row['company_name']=metadata.get((row['symbol'],row['instrument_id']))
            grouped.setdefault(row['symbol'],[]).append(row)
        for index,symbol in enumerate(self.universe):
            try:
                rows=grouped.get(symbol,[])
                if len(rows)!=1:raise ValueError('INSTRUMENT_IDENTITY_MISSING_OR_AMBIGUOUS')
                meta=rows[0];name=str(meta['company_name'] or meta['display_name'] or '')
                if meta['currency']!='USD' or meta['instrument_type']!='equity' or meta['mapping_status']!='mapped':
                    raise ValueError('NON_USD_OR_UNQUALIFIED_EQUITY')
                if ('.' in symbol or re.search(r'\b(?:ADR|ADS|DEPOSITARY|DEPOSITORY)\b',name,re.I)
                        or re.search(r'\bCLASS\s+[A-Z0-9]+\b',name,re.I)):
                    raise ValueError('ADR_OR_SHARE_CLASS_AMBIGUITY')
                if excluded_collective_instrument_reason(name):raise ValueError('NON_CORPORATE_EQUITY')
                cik=mapping.get(symbol)
                if not cik or not re.fullmatch(r'\d{10}',cik):raise ValueError('LOCAL_CIK_UNAVAILABLE')
                path=self.root/'companyfacts'/('CIK'+cik+'.json')
                blob=path.read_bytes();facts=share_facts(json.loads(blob),cik)
                if not facts:raise ValueError('NO_STANDARD_INSTANT_SHARE_FACTS')
                self.entities[symbol]=dict(facts=facts,cik=cik,instrument_id=meta['instrument_id'],
                    source_path=str(path),source_sha256=hashlib.sha256(blob).hexdigest())
            except (OSError,ValueError,KeyError,TypeError) as exc:
                self.rejections[symbol]=str(exc) if isinstance(exc,ValueError) else 'LOCAL_SEC_FACTS_UNAVAILABLE'
            if (index+1)%100==0:
                LOG.info('Qualification SEC locale : %d/%d émetteurs, %d sources utilisables',index+1,len(self.universe),len(self.entities))
        query=text("SELECT symbol,ex_date FROM corporate_actions_events WHERE symbol IN :symbols "
            "AND ca_type IN ('split','reverse_split') AND LOWER(provider) IN ('alpaca','eodhd')"
            ).bindparams(bindparam('symbols',expanding=True))
        for row in self.conn.execute(query,dict(symbols=self.universe)).mappings():
            self.splits.setdefault(row['symbol'],set()).add(date.fromisoformat(str(row['ex_date'])[:10]))
        self.manifest.update(symbols=len(self.universe),usable_local_entities=len(self.entities),
            rejected_entities=dict(Counter(self.rejections.values())),
            identity_scope='CURRENT_CIK_MAPPING_WITH_REVIEWED_IDENTITY_BREAKS_NOT_COMPLETE_HISTORICAL_MASTER',
            source_scope='LOCAL_COMPANYFACTS_AS_REPORTED_NOT_ARCHIVED_API_VINTAGES')
        self.loaded=True

    def reconstruct(self,day,cutoff,symbols):
        self._load()
        selected={};rejected={}
        for symbol in sorted(set(symbols)):
            try:
                if symbol not in self.entities:raise ValueError(self.rejections.get(symbol,'SEC_SOURCE_UNAVAILABLE'))
                selected[symbol]=select_shares(self.entities[symbol]['facts'],day,cutoff,
                    max_age_days=self.max_age_days,split_dates=self.splits.get(symbol,()),
                    identity_events=self.registry.get(symbol,()))
            except ValueError as exc:rejected[symbol]=str(exc)
        output=[]
        if selected:
            closing=regular_bounds(day)[1]
            query=text('SELECT symbol,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,payload_hash '
                'FROM stock_bars_intraday WHERE symbol IN :symbols AND trade_date=:day AND bar_timestamp=:stamp '
                "AND interval_code='5m' AND data_source='alpaca_sip' AND provider='alpaca' AND market_code='US_EQ' "
                "AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0"
                ).bindparams(bindparam('symbols',expanding=True))
            grouped={}
            for row in self.conn.execute(query,dict(symbols=sorted(selected),day=day,
                    stamp=(closing-timedelta(minutes=5)).replace(tzinfo=None))).mappings():
                grouped.setdefault(row['symbol'],[]).append(dict(row))
            for symbol,shares in selected.items():
                try:
                    rows=grouped.get(symbol,[])
                    if len(rows)!=1:raise ValueError('RAW_REGULAR_CLOSE_MISSING_OR_DUPLICATE')
                    bar=rows[0];numbers=[float(bar[k]) for k in ('open','high','low','close','volume')]
                    bar_end=bar['bar_end_timestamp']
                    if isinstance(bar_end,str):bar_end=datetime.fromisoformat(bar_end)
                    bar_end=bar_end.replace(tzinfo=UTC) if bar_end.tzinfo is None else bar_end.astimezone(UTC)
                    if (not all(math.isfinite(v) and v>0 for v in numbers) or not bar['payload_hash']
                            or not numbers[2]<=min(numbers[0],numbers[3])<=max(numbers[0],numbers[3])<=numbers[1]
                            or bar_end!=closing):
                        raise ValueError('RAW_REGULAR_CLOSE_UNQUALIFIED')
                    entity=self.entities[symbol];cap=compute_sec_market_cap(bar['close'],shares['value'])
                    if cap is None:raise ValueError('INVALID_RECONSTRUCTED_CAPITALIZATION')
                    available=max(shares['available_at'],closing+timedelta(minutes=15))
                    if available>cutoff:raise ValueError('SOURCE_NOT_AVAILABLE_BEFORE_CUTOFF')
                    proof=dict(cik=entity['cik'],instrument_id=entity['instrument_id'],
                        share_fact=shares,companyfacts_sha256=entity['source_sha256'],
                        companyfacts_path=entity['source_path'],raw_bar_payload_hash=bar['payload_hash'],
                        raw_close=float(bar['close']),price_date=day,
                        price_basis='LAST_REGULAR_RAW_5M_CLOSE_NOT_OFFICIAL_CLOSING_AUCTION')
                    digest=hashlib.sha256(json.dumps(proof,sort_keys=True,default=str).encode()).hexdigest()
                    output.append(dict(id='reconstructed-sec-'+digest,symbol=symbol,market_cap=cap,source='SEC_X_CLOSE',
                        currency='USD',observation_date=day,available_date=available.date(),
                        computed_at=datetime.now(UTC),input_available_at=available,
                        evidence_kind='RECONSTRUCTED_SEC_FACT',proof=proof,input_sha256=digest))
                except (KeyError,ValueError,TypeError,OverflowError) as exc:rejected[symbol]=str(exc)
        receipt=dict(day=str(day),requested=len(set(symbols)),reconstructed=len(output),
            rejection_counts=dict(Counter(rejected.values())),rejected_symbols=rejected,
            sources=self.manifest,computed_at=datetime.now(UTC).isoformat())
        self.receipts.append(receipt)
        LOG.info('Capitalisations SEC reconstruites %s : %d/%d, refus=%s',day,len(output),len(set(symbols)),receipt['rejection_counts'])
        return output
