"""Classify the entire frozen daily-bars file; never alter runtime universes or SQL.

Inputs are read-only reference exports in the audit directory. ADR/ADS are excluded.
The audit retains every source symbol and the evidence behind its decision.
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'artifacts/operations/ordinary_shares_inventory/20261103-v1'
SOURCE = ROOT / 'config/univers_batch/stock_bars_daily.txt'
OUTPUT = ROOT / 'config/univers_batch/action_ordinaire.txt'


def matches(pattern, value):
    return bool(re.search(pattern, value, re.I))


def same_issuer(name, reference_name):
    stop = {'the','inc','incorporated','corp','corporation','company','co','group','holdings','holding','ltd','limited','plc','sa','nv','stock','common','ordinary','shares','class','a','b','c','new','trust'}
    left = set(re.findall(r'[a-z0-9]+', name.lower())) - stop
    right = set(re.findall(r'[a-z0-9]+', reference_name.lower())) - stop
    shared = left & right
    return any(len(token) >= 4 for token in shared) or len(shared) >= 2


def classify(symbol, metadata, nasdaq, business, finnhub, eodhd=None):
    name = (nasdaq or metadata).get('company_name') or ''
    old_name = metadata.get('company_name') or ''
    names = name + ' | ' + old_name
    kind = (finnhub or {}).get('type', '')
    # Explicit instrument description outranks coarse Equity labels.
    if (nasdaq or {}).get('test_issue'):
        return 'EXCLUDE_TEST', 'Nasdaq test issue'
    if matches(r'\bETFs?\b|\bETNs?\b|exchange[ -]traded|\bETRACS\b|\bMicroSectors\b', names):
        return 'EXCLUDE_ETP', 'Explicit ETF/ETN description'
    if (nasdaq or {}).get('etf_flag'):
        return 'EXCLUDE_ETP', 'Nasdaq ETF flag'
    ordinary_named = kind == 'Common Stock' and matches(r'\bcommon stock\b|\bordinary shares?\b', name)
    preferred_instrument = matches(r'\b(?:preferred|preference)\s+(?:stock|shares?|securities)\b|\bprefs?\b', names)
    preferred_hint = matches(r'\b(preferred|preference|prefs?|depositary preferred)\b', names)
    if (preferred_hint and (not ordinary_named or preferred_instrument)) or matches(r'\.PR[A-Z]+$', symbol):
        return 'EXCLUDE_PREFERRED', 'Preferred share description or series symbol'
    if matches(r'\bwarrants?\b', names) or matches(r'\.(WS|WT)(\.[A-Z])?$', symbol):
        return 'EXCLUDE_WARRANT', 'Warrant instrument (not underlying common shares)'
    if matches(r'\brights?\b', names):
        return 'EXCLUDE_RIGHT', 'Subscription/acquisition right'
    if matches(r'\b(notes?|bonds?|debentures)\b.*\b(due|20\d\d|21\d\d)\b|\b(?:subordinated|senior|perpetual) notes\b|\bSTRATS\b|\bCorTS\b|\bCapital Securities\b|\bBacked Tr Cert|\bPPlus\b', names):
        return 'EXCLUDE_DEBT', 'Debt, capital security or structured certificate'
    if matches(r'\bunits?\b|\blimited partner(?:ship)? interests?\b|\blimited liability company interests?\b', names):
        return 'EXCLUDE_UNIT', 'Unit/partnership/LLC interest, not a direct ordinary share'
    if matches(r'\b(depositary|depository)\b|\bADRs?\b|\bADSs?\b|\bGDRs?\b', names):
        return 'EXCLUDE_DR', 'Depositary receipt/share; user explicitly excluded ADR/ADS'
    if matches(r'\bfunds?\b|\bmunicipal\b|\bMFS\b.*\bincome trust\b', names):
        return 'EXCLUDE_FUND', 'Investment fund/portfolio description'
    if kind in {'ADR', 'GDR', 'NVDR', 'Receipt', 'SDR', 'CDI', 'Canadian DR', 'Dutch Cert'}:
        return 'EXCLUDE_DR', f'Finnhub type {kind}'
    if kind in {'ETP', 'Closed-End Fund', 'Open-End Fund'}:
        return 'EXCLUDE_FUND', f'Finnhub type {kind}'
    if kind in {'Equity WRT', 'Right', 'Unit', 'MLP', 'Ltd Part', 'Royalty Trst', 'Preference', 'Stapled Security'}:
        return 'EXCLUDE_OTHER', f'Finnhub type {kind}'
    if matches(r'\b(common|ordinary)\s+(?:(?:subordinate|voting|non[ -]voting)\s+)*(?:stock|shares?)\b|\bcapital stock\b|\bsubordinate voting shares\b|\blimited voting shares\b', name):
        return 'INCLUDE_ORDINARY', 'Explicit ordinary/common/capital/voting share description'
    if kind in {'Common Stock', 'REIT', 'NY Reg Shrs', 'Foreign Sh.', 'Tracking Stk', 'Savings Share'}:
        return 'INCLUDE_ORDINARY', f'Finnhub type {kind}; no excluded instrument description'
    if (business or {}).get('security_type') == 'ETF':
        return 'EXCLUDE_ETP', 'Business Quant ETF type'
    if (business or {}).get('security_type') == 'Fund':
        return 'EXCLUDE_FUND', 'Business Quant fund type'
    # EODHD's Common Stock category also contains ADR and some funds: use only
    # identity-matched records after the more precise evidence above and manual review.
    if eodhd and same_issuer(name, eodhd.get('Name') or ''):
        eod_type = eodhd.get('Type')
        if matches(r'\bADRs?\b|\bADSs?\b|depositary|depository', eodhd.get('Name') or ''):
            return 'EXCLUDE_DR', 'Identity-matched EODHD description explicitly identifies ADR/ADS'
        if eod_type == 'Common Stock':
            if matches(r'\btrust\b', name) and metadata.get('sector') != 'Real Estate':
                return 'REVIEW', 'EODHD Common Stock also includes trusts; no direct corporate ordinary share confirmation'
            return 'INCLUDE_ORDINARY', 'Identity-matched EODHD Common Stock reference; more specific exclusions checked'
        if eod_type in {'ETF','ETC','FUND','Mutual Fund','Preferred Stock','Warrant','Unit','UNIT','Notes','BOND','INDEX'}:
            return 'EXCLUDE_OTHER', f'Identity-matched EODHD type {eod_type}'
    return 'REVIEW', 'No sufficiently specific classification'


def main(write=False):
    symbols = sorted({x.strip().upper() for x in SOURCE.read_text(encoding='utf-8-sig').split(',') if x.strip()})
    metadata = {x['symbol']: x for x in json.loads((AUDIT/'metadata.json').read_text(encoding='utf-8'))}
    masters = json.loads((AUDIT/'security-master.json').read_text(encoding='utf-8'))
    historical = json.loads((AUDIT/'historical-reference-completion.json').read_text(encoding='utf-8'))
    nasdaq = {x['symbol']: x for x in masters if x['provider'] == 'nasdaq_symbol_directory'}
    business = {x['symbol']: x for x in masters if x['provider'] == 'business_quant'}
    for row in historical:
        target = nasdaq if row['provider'] == 'nasdaq_symbol_directory' else business
        target.setdefault(row['symbol'], row)
    finnhub = {x['symbol']: x for x in json.loads((AUDIT/'finnhub-us-symbols.json').read_text(encoding='utf-8'))}
    eodhd = {x['Code']:x for x in json.loads((AUDIT/'eodhd-us-delisted-symbols.json').read_text(encoding='utf-8'))}
    eodhd.update({x['Code']:x for x in json.loads((AUDIT/'eodhd-us-symbols.json').read_text(encoding='utf-8'))})
    manual = json.loads((AUDIT/'review-decisions.json').read_text(encoding='utf-8')) if (AUDIT/'review-decisions.json').exists() else {}
    rows = []
    for symbol in symbols:
        status, reason = classify(symbol, metadata[symbol], nasdaq.get(symbol), business.get(symbol), finnhub.get(symbol), eodhd.get(symbol))
        if symbol in manual:
            status, reason = manual[symbol]['status'], manual[symbol]['reason']
        if status == 'REVIEW':
            status = 'EXCLUDE_UNKNOWN'
            reason = 'Type indéterminé : exclu conformément à la demande utilisateur'
        rows.append(dict(symbol=symbol, status=status, reason=reason, name=nasdaq.get(symbol, metadata[symbol])['company_name'],
            metadata_name=metadata[symbol]['company_name'], metadata_status=metadata[symbol]['status'],
            finnhub_type=finnhub.get(symbol, {}).get('type'), finnhub_name=finnhub.get(symbol, {}).get('description'),
            nasdaq_snapshot=nasdaq.get(symbol, {}).get('snapshot_date'), nasdaq_etf=nasdaq.get(symbol, {}).get('etf_flag'),
            business_type=business.get(symbol, {}).get('security_type'), eodhd_type=eodhd.get(symbol, {}).get('Type'),
            eodhd_name=eodhd.get(symbol, {}).get('Name'), manual_evidence=manual.get(symbol, {}).get('sources')))
    (AUDIT/'classification.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    pending = [x for x in rows if x['status'] == 'EXCLUDE_UNKNOWN']
    (AUDIT/'pending-review.json').write_text(json.dumps(pending, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    counts = dict(collections.Counter(x['status'] for x in rows))
    print(json.dumps(dict(total=len(rows), counts=counts, pending=[{'symbol':x['symbol'],'name':x['name'],'bq':x['business_type']} for x in pending]), ensure_ascii=False))
    if write:
        retained = [x['symbol'] for x in rows if x['status'] == 'INCLUDE_ORDINARY']
        assert len(rows) == len(symbols) and len(retained) == len(set(retained))
        OUTPUT.write_text(','.join(retained)+'\n', encoding='utf-8')
        report = dict(source=str(SOURCE), output=str(OUTPUT), input_symbols=len(symbols), retained=len(retained), counts=counts,
            source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            direct_ordinary_shares_only=True, include_adr_ads=False, active_tradable_liquidity_cap_filters=False,
            policy='Common/ordinary shares including corporate REIT equity and SPAC common shares; exclude funds, ETP, preferred, DR, debt, rights, warrants and units',
            unknown_types_policy='exclude', provider_calls={'Finnhub /stock/symbol?exchange=US':1,'EODHD /exchange-symbol-list/US':2},
            input_hashes={name:hashlib.sha256((AUDIT/name).read_bytes()).hexdigest() for name in ('metadata.json','security-master.json','historical-reference-completion.json','finnhub-us-symbols.json','eodhd-us-symbols.json','eodhd-us-delisted-symbols.json','review-decisions.json')})
        (AUDIT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    import sys
    main(write='--write' in sys.argv)
