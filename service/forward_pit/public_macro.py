"""Producer-direct BLS/H15 snapshots. No reconstructed historical PIT vintage."""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from sqlalchemy import text

from common.config_loader import load_batch_config
from common.public_data_http import verified_session

BLS_URL = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'
H15_URL = 'https://www.federalreserve.gov/releases/h15/'
BLS_SERIES = {
    'CUSR0000SA0': ('CPI_ALL_ITEMS_SA', 'index_1982_1984_100'),
    'CUSR0000SA0L1E': ('CPI_EX_FOOD_ENERGY_SA', 'index_1982_1984_100'),
    'LNS14000000': ('UNEMPLOYMENT_RATE_SA', 'percent'),
    'CES0000000001': ('NONFARM_EMPLOYMENT_SA', 'thousands_persons'),
}
H15_SERIES = {'3-month': 'TREASURY_CMT_NOMINAL_3M', '2-year': 'TREASURY_CMT_NOMINAL_2Y',
              '10-year': 'TREASURY_CMT_NOMINAL_10Y', '30-year': 'TREASURY_CMT_NOMINAL_30Y'}
TABLE = 'macro_public_observation_versions'


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)


def digest(value):
    return hashlib.sha256(encoded(value).encode('utf-8')).hexdigest()


def number(value):
    cleaned = str(value).strip(' \t\r\n\xa0\ufffd').replace(',', '')
    if cleaned.lower() in ('', 'n.a.', 'na', '-', '--'):
        return None
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', cleaned):
        raise ValueError('Unrecognized public numeric value')
    result = float(cleaned)
    if not math.isfinite(result):
        raise ValueError('Non-finite public numeric value')
    return result


def observation(provider, series, metric, start, end, frequency, raw, unit, metadata):
    return {'provider': provider, 'native_series_id': series, 'metric_key': metric,
            'period_start': start, 'period_end': end, 'frequency': frequency,
            'value_num': number(raw), 'value_raw': str(raw).strip(), 'unit': unit,
            'metadata_json': encoded(metadata)}


def parse_bls(payload, expected_series):
    if payload.get('status') != 'REQUEST_SUCCEEDED':
        raise ValueError('BLS request not successful (check quota/API status)')
    blocks = payload.get('Results', {})
    if isinstance(blocks, list):
        blocks = blocks[0] if len(blocks) == 1 else {}
    groups = blocks.get('series', [])
    rows, counts = [], {}
    for group in groups:
        native = group.get('seriesID')
        if native not in expected_series or native not in BLS_SERIES:
            raise ValueError('Unexpected BLS series')
        if native in counts:
            raise ValueError('Duplicate BLS series block')
        counts[native] = 0
        for item in group.get('data', []):
            period = item.get('period', '')
            if period == 'M13':  # Annual averages are not monthly observations.
                continue
            if not re.fullmatch(r'M(?:0[1-9]|1[0-2])', period):
                raise ValueError('Unsupported BLS period')
            year, month = int(item['year']), int(period[1:])
            metric, unit = BLS_SERIES[native]
            row = observation('bls', native, metric, date(year, month, 1),
                              date(year, month, calendar.monthrange(year, month)[1]),
                              'monthly', item['value'], unit,
                              {'seasonal_adjustment': 'seasonally_adjusted',
                               'footnotes': item.get('footnotes', []), 'parser_version': 1})
            rows.append(row)
            counts[native] += 1
    if any(not counts.get(native) for native in expected_series):
        raise ValueError('Missing or empty BLS requested series')
    _validate_unique(rows)
    return rows


def _validate_unique(rows):
    identities = {(r['native_series_id'], r['period_start']) for r in rows}
    if len(identities) != len(rows):
        raise ValueError('Duplicate public observation identity')


def parse_h15(body):
    soup = BeautifulSoup(body, 'html.parser')
    table = soup.find('table', id='h15table')
    if table is None or table.thead is None or table.tbody is None:
        raise ValueError('H15 official table missing')
    dates = {}
    for cell in table.thead.find_all('th'):
        if cell.get('id', '').startswith('col'):
            dates[cell['id']] = datetime.strptime(cell.get_text(' ', strip=True), '%Y %b %d').date()
    if not dates:
        raise ValueError('H15 date headers missing')
    rows, expected = [], set(H15_SERIES.values()) | {'FED_FUNDS_EFFECTIVE_DAILY'}
    for tr in table.tbody.find_all('tr'):
        stub = tr.find('th')
        if stub is None:
            continue
        for footnote in stub.find_all('a'):
            footnote.decompose()
        label = stub.get_text(' ', strip=True)
        ancestors = stub.get('headers', [])
        ancestor_labels = []
        for identifier in ancestors:
            parent = table.find('th', id=identifier)
            if parent is not None:
                ancestor_labels.append(parent.get_text(' ', strip=True))
        nominal = ('Treasury constant maturities' in ancestor_labels
                   and any(s.startswith('Nominal') for s in ancestor_labels)
                   and not any(s.startswith('Inflation indexed') for s in ancestor_labels))
        metric = ('FED_FUNDS_EFFECTIVE_DAILY' if label == 'Federal funds (effective)'
                  else H15_SERIES.get(label) if nominal else None)
        if metric is None:
            continue
        for cell in tr.find_all('td'):
            columns = [h for h in cell.get('headers', []) if h in dates]
            if len(columns) != 1:
                raise ValueError('H15 value/header mapping ambiguous')
            day = dates[columns[0]]
            rows.append(observation('federal_reserve_board', 'H15_' + metric, metric,
                                    day, day, 'daily', cell.get_text(strip=True), 'percent',
                                    {'rate_type': 'effective' if metric.startswith('FED_FUNDS')
                                     else 'nominal_constant_maturity', 'parser_version': 1}))
    if {r['metric_key'] for r in rows} != expected:
        raise ValueError('H15 requested instrument coverage incomplete')
    _validate_unique(rows)
    return rows


def version_parameters(row, observed, run_id, source_url):
    # Hash excludes retrieval time/run: repeat unchanged snapshots are deduplicated.
    return {**row, 'version_hash': digest(row), 'observed_at': observed,
            'available_at': observed, 'available_at_basis': 'FIRST_OBSERVED',
            'run_id': run_id, 'source_url': source_url}


def persist_versions(conn, rows, observed, run_id, source_url):
    inserted = 0
    for row in rows:
        params = version_parameters(row, observed, run_id, source_url)
        previous = conn.execute(text(f'''SELECT version_hash,observed_at FROM {TABLE}
            WHERE provider=:provider AND native_series_id=:native_series_id AND period_start=:period_start
            ORDER BY observed_at DESC,id DESC LIMIT 1'''), params).mappings().first()
        if previous and previous['version_hash'] == params['version_hash']:
            continue  # Keep earliest available_at for this unchanged current version.
        if previous and previous['observed_at'] > observed:
            raise ValueError('Refusing out-of-order public snapshot insertion')
        names = list(params)
        conn.execute(text(f"INSERT INTO {TABLE} ({','.join(names)}) VALUES ({','.join(':'+n for n in names)})"), params)
        inserted += 1
    return inserted


def fetch(provider, cfg, client):
    if provider == 'bls':
        series = cfg.get('bls_series', list(BLS_SERIES))
        if not isinstance(series, list) or not series or len(series) != len(set(series)) or set(series) - BLS_SERIES.keys():
            raise ValueError('BLS series must be a nonempty unique list of supported native IDs')
        years = int(cfg.get('bls_lookback_years', 2))
        if not 1 <= years <= 10:
            raise ValueError('BLS v1 supports at most ten years per request')
        year = datetime.now(UTC).year
        response = client.post(BLS_URL, json={'seriesid': series, 'startyear': str(year-years+1),
                                             'endyear': str(year)}, timeout=30, allow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        rows = parse_bls(payload, series)
        source = BLS_URL
    elif provider == 'federal_reserve_board':
        response = client.get(H15_URL, timeout=30, allow_redirects=False)
        response.raise_for_status()
        # Decode HTML bytes using its declared charset, rather than Requests' default.
        soup = BeautifulSoup(response.content, 'html.parser')
        encoding = soup.original_encoding or 'utf-8'
        payload = {'html': response.content.decode(encoding), 'encoding': encoding,
                   'body_sha256': hashlib.sha256(response.content).hexdigest()}
        rows = parse_h15(payload['html'])
        source = H15_URL
    else:
        raise ValueError('Unsupported public macro provider')
    observed = utcnow()  # Both payload reception and parsing finished.
    if any(row['period_start'] > observed.date() for row in rows):
        raise ValueError('Future public observation period')
    return source, payload, rows, observed


def collect(engine, cfg, run_id, dry_run, *, archive_dir=None, session=None):
    from service.forward_pit.batch import Outcome, BatchRunError, _raw
    if not dry_run and engine.url.database != 'alpha_trade':
        raise ValueError('Public macro persistence requires alpha_trade (US)')
    providers = cfg.get('providers', ['bls', 'federal_reserve_board'])
    if not isinstance(providers, list) or not providers or len(providers) != len(set(providers)):
        raise ValueError('Public macro providers must be a nonempty unique list')
    outcome = Outcome(requested=len(providers), details={'providers': {}, 'basis': 'FIRST_OBSERVED',
                                                       'historical_pit_reconstructed': False})
    with (session or verified_session()) as client:
        for provider in providers:
            try:
                source, payload, rows, observed = fetch(provider, cfg, client)
                outcome.received += 1
                details = {'observations': len(rows), 'series': len({r['native_series_id'] for r in rows}),
                           'observed_at': observed.isoformat(), 'null_values': sum(r['value_num'] is None for r in rows)}
                if archive_dir:
                    folder = Path(archive_dir) / run_id
                    folder.mkdir(parents=True, exist_ok=True)
                    with (folder / f'{provider}.json').open('x', encoding='utf-8') as handle:
                        handle.write(encoded({'source': source, 'observed_at': observed, 'payload': payload,
                                              'payload_hash': digest(payload)}))
                if not dry_run:
                    # Network completed BEFORE transaction/lock. Serializes revision comparisons.
                    with engine.connect() as conn:
                        lock = conn.execute(text("SELECT GET_LOCK('alpha_trade_public_macro',10)")).scalar()
                        conn.commit()
                        if lock != 1:
                            raise RuntimeError('Public macro lock unavailable')
                        try:
                            with conn.begin():
                                _raw(conn, run_id, 'public_macro_snapshot_sync', provider, source, provider,
                                     payload, observed=observed)
                                count = persist_versions(conn, rows, observed, run_id, source)
                        finally:
                            conn.execute(text("SELECT RELEASE_LOCK('alpha_trade_public_macro')"))
                            conn.commit()
                    outcome.persisted += count
                    details['new_versions'] = count
                    details['unchanged'] = len(rows) - count
                outcome.details['providers'][provider] = {'status': 'OK', **details}
            except Exception as exc:
                outcome.failed += 1
                outcome.details['providers'][provider] = {'status': 'FAILED', 'error_type': type(exc).__name__,
                                                         'error_message': str(exc)[:500]}
    if outcome.failed:
        raise BatchRunError('Public macro: one or more providers failed; see details', outcome)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.add_argument('--archive-dir', required=True)
    parser.add_argument('--batch-config')
    args = parser.parse_args()
    from service.forward_pit.batch import BatchRunError
    cfg = load_batch_config(args.batch_config).get('public_macro_snapshot_sync', {})
    run_id = 'public-macro-smoke-' + datetime.now(UTC).strftime('%Y%m%d%H%M%S') + '-' + uuid.uuid4().hex[:8]
    try:
        outcome = collect(None, cfg, run_id, True, archive_dir=args.archive_dir)
        report = {'status': 'DRY_RUN', **outcome.__dict__}
    except BatchRunError as exc:
        report = {'status': 'FAILED', **exc.outcome.__dict__}
    folder = Path(args.archive_dir) / run_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'report.json').write_text(encoded(report), encoding='utf-8')
    print(encoded({'report_path': str(folder / 'report.json'), **report}))
    if report['status'] == 'FAILED':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
