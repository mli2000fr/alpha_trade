"""Bounded official MiFIR equity currency POC, file-only and never a release."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from service.fr.issuer_pilot_16g import PILOT
from service.fr.mifir_options_poc import TRADES_PAGE, fetch, instant, number
from service.fr.prediction_contract_16a import ROOT, scoped_path

URL = TRADES_PAGE + '/download/EQUITIES/PREVIOUS_TRADING_DAY/PAR'
REQUIRED = {'TradingDateTime', 'PublicationDateTime', 'MifidInstrumentID',
            'MifidPrice', 'MifidQuantity', 'MifidPriceNotation', 'MifidCurrency',
            'Venue', 'VenueOfPublication', 'TradeUniqueIdentifier',
            'MmtModificationIndicator', 'MmtPublicationMode', 'MissingPrice'}


def select_rows(raw):
    selected, count = [], 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or not entries[0].filename.lower().endswith('.csv'):
            raise ValueError('Single CSV expected')
        if entries[0].file_size > 256_000_000:
            raise ValueError('Uncompressed size limit exceeded')
        with archive.open(entries[0]) as stream:
            text = io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')
            preamble = []
            for line in text:
                if line.startswith('TradingDateTime,'):
                    fields = next(csv.reader([line]))
                    break
                preamble.append(line.rstrip())
                if len(preamble) > 30:
                    raise ValueError('CSV header absent')
            else:
                raise ValueError('CSV header absent')
            if not REQUIRED.issubset(fields):
                raise ValueError('Equity schema changed')
            for row in csv.DictReader(text, fieldnames=fields):
                count += 1
                if count > 3_000_000 or None in row or any(v is None for v in row.values()):
                    raise ValueError('Malformed or oversized CSV')
                if row['MifidInstrumentID'] in PILOT.values():
                    selected.append(row)
                    if len(selected) > 200_000:
                        raise ValueError('Pilot row limit exceeded')
    return selected, count, '\n'.join(preamble)


def analyze(rows, observed_at):
    observed = instant(observed_at)
    groups, rejected, accepted = defaultdict(list), Counter(), defaultdict(list)
    for row in rows:
        if row['MifidInstrumentID'] not in PILOT.values():
            raise ValueError('Outside frozen pilot')
        if row['Venue'] != 'XPAR' or not row['TradeUniqueIdentifier']:
            rejected['WRONG_VENUE_OR_MISSING_ID'] += 1
            continue
        groups[(row['Venue'], row['VenueOfPublication'], row['TradeUniqueIdentifier'])].append(row)
    duplicates = 0
    for group in groups.values():
        unique = {json.dumps(r, sort_keys=True): r for r in group}
        duplicates += len(group) - len(unique)
        group = list(unique.values())
        if len(group) != 1 or {r['MmtModificationIndicator'] for r in group} != {'-'}:
            rejected['AMENDED_CANCELLED_OR_CONFLICTING_ID'] += len(group)
            continue
        row = group[0]
        try:
            traded, published = instant(row['TradingDateTime']), instant(row['PublicationDateTime'])
            if published < traded or published + timedelta(minutes=15) > observed:
                raise ValueError('PUBLICATION_TIME_NOT_QUALIFIED')
            # The cash schema differs from derivatives: do not invent a
            # NumberOfTransactions or MmtPostTradeDeferral field if absent.
            if (row['MmtPublicationMode'] != '-'
                    or row.get('MmtPostTradeDeferral', '-') != '-'
                    or row.get('NumberOfTransactions', '1') not in ('', '1')
                    or row['MissingPrice'] not in ('', '-')):
                raise ValueError('DEFERRED_AGGREGATED_OR_MISSING_PRICE')
            if (number(row['MifidPrice']) <= 0 or number(row['MifidQuantity']) <= 0
                    or row['MifidPriceNotation'] != 'MONE'
                    or not re.fullmatch('[A-Z]{3}', row['MifidCurrency'])):
                raise ValueError('UNQUALIFIED_PRICE_OR_CURRENCY')
            accepted[row['MifidInstrumentID']].append(row)
        except ValueError as exc:
            rejected[str(exc)] += 1
    matrix = []
    for symbol, isin in PILOT.items():
        items = accepted[isin]
        dates = sorted({r['TradingDateTime'][:10] for r in items})
        currencies = dict(Counter(r['MifidCurrency'] for r in items))
        matrix.append({'symbol': symbol, 'isin': isin, 'mic': 'XPAR',
                       'accepted_rows': len(items), 'observed_trade_dates': dates,
                       'currencies': currencies,
                       'point_observation_status': ('NO_MATCHED_TRADES' if not items else
                           'CURRENCY_CONFLICT' if len(currencies) != 1 else 'DATED_TRADE_CURRENCY_OBSERVED'),
                       'samples': items[:3], 'available_at': observed_at,
                       'trading_currency_interval_qualified': False,
                       'actions_coverage_qualified': False, 'servable': False})
    return {'matrix': matrix, 'exclusion_counts': dict(rejected),
            'exact_duplicates_removed': duplicates,
            'counts_are_publication_rows_not_certified_trade_count': True,
            'accepted_rows': sum(len(items) for items in accepted.values())}


def run(output_dir, archive_report=None):
    output = scoped_path(str(output_dir), ROOT)
    output.mkdir(parents=True, exist_ok=False)
    report = {'market_code': 'FR_EQ', 'status': 'RUNNING', 'source_url': URL,
              'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False,
              'historical_interval_qualified': False, 'corporate_actions_qualified': False,
              'distribution_allowed_by_this_poc': False}
    try:
        if archive_report:
            source_path = scoped_path(str(archive_report), ROOT)
            prior = json.loads(source_path.read_text(encoding='utf-8'))
            if prior['source_url'] != URL or prior['market_code'] != 'FR_EQ':
                raise ValueError('Wrong offline source')
            page = (source_path.parent / 'source_page.html').read_bytes()
            raw = (source_path.parent / 'trades.zip').read_bytes()
            page_receipt, receipt = prior['source_page_receipt'], prior['download_receipt']
            for data, proof in ((page, page_receipt), (raw, receipt)):
                if hashlib.sha256(data).hexdigest() != proof['sha256']:
                    raise ValueError('Archived source hash mismatch')
            if page_receipt['url'] != TRADES_PAGE or receipt['url'] != URL:
                raise ValueError('Archived receipt URL mismatch')
            report['offline_source_report'] = str(source_path)
            report['offline_source_sha256'] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        else:
            page, page_receipt = fetch(TRADES_PAGE, 300_000)
        (output / 'source_page.html').write_bytes(page)
        text = page.decode('utf-8')
        for required in ('value="EQUITIES"', 'value="PREVIOUS_TRADING_DAY"', 'value="PAR"',
                         'TERMS AND CONDITIONS FOR DELAYED TRADE DATA'):
            if required not in text:
                raise ValueError('Official form/terms changed; review before download')
        report['source_page_receipt'] = page_receipt
        if not archive_report:
            raw, receipt = fetch(URL, 64_000_000)
            (output / 'trades.zip').write_bytes(raw)
        else:
            report['trades_zip_path'] = str(source_path.parent / 'trades.zip')
        report['download_receipt'] = receipt
        rows, count, copyright_notice = select_rows(raw)
        report.update(analyze(rows, receipt['received_at']))
        report.update(status='POINT_CURRENCY_EVIDENCE_NOT_RELEASED',
                      input_rows=count, pilot_input_rows=len(rows), copyright_notice=copyright_notice)
    except Exception as exc:
        report.update(status='FAILED_NOT_RELEASED', error=str(exc)[:500])
    report['completed_at'] = datetime.now(UTC).isoformat()
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--archive-report')
    args = parser.parse_args()
    result = run(args.output_dir, args.archive_report)
    print(json.dumps({k: result.get(k) for k in ('status', 'input_rows', 'pilot_input_rows', 'accepted_rows', 'error')}))
    if result['status'] == 'FAILED_NOT_RELEASED':
        raise SystemExit(1)
