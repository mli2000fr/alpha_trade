"""Bounded read-only investigation of remaining Oracle price discontinuities."""
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
import ssl

import pandas as pd
import requests
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_feature_outliers import diagnose_segment
from service.eodhd.adapters import eodhd_to_split_only, to_stock_bars_daily_row
from service.eodhd.clientEodhd import fetch_eod, fetch_splits
from service.eodhd.quota import EodhdQuotaTracker


EVENTS = {'DEC': '2023-12-05', 'TALO': '2016-06-13', 'INDV': '2022-11-28'}


def parse_events(value):
    events = {}
    for item in value.split(','):
        symbol, separator, day = item.strip().partition(':')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}', symbol):
            raise argparse.ArgumentTypeError('Expected SYMBOL:YYYY-MM-DD')
        if symbol in events or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            raise argparse.ArgumentTypeError('Duplicate symbol or invalid date')
        try:
            pd.Timestamp(day)
        except ValueError as exc:
            raise argparse.ArgumentTypeError('Invalid event date') from exc
        events[symbol] = day
    return events


def event_record(frame, event):
    computed = diagnose_segment(frame)
    row = computed.loc[computed.date.eq(pd.Timestamp(event))]
    if len(row) != 1:
        raise ValueError('Missing or ambiguous event date')
    row = row.iloc[0]
    result = {key: row[key] for key in ('date', 'previous_date', 'close', 'previous_close',
        'adj_close', 'previous_adj_close', 'volume', 'previous_volume',
        'daily_return_recomputed', 'overnight_gap_recomputed', 'instrument_changed')}
    if pd.isna(row.instrument_id) or pd.isna(row.previous_instrument_id):
        result['instrument_changed'] = None
    return {key: value.item() if hasattr(value, 'item') else value
            for key, value in result.items()}


def run(output, events=None):
    events = EVENTS if events is None else events
    output.mkdir(parents=True, exist_ok=False)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    session = requests.Session()
    trust = output / 'windows-trust.pem'
    trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in
        ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
    session.verify = str(trust.resolve())
    tracker = EodhdQuotaTracker(cache_dir=output / 'provider-quota')
    results = []
    try:
        for symbol, event in events.items():
            start = str((pd.Timestamp(event) - pd.Timedelta(days=20)).date())
            end = str((pd.Timestamp(event) + pd.Timedelta(days=20)).date())
            with engine.connect() as conn:
                conn.exec_driver_sql('SET TRANSACTION READ ONLY')
                local = pd.read_sql(text('SELECT symbol,`date`,`open`,high,low,`close`,adj_close,'
                    'volume,vwap,is_filled,instrument_id,data_source,data_adjustment FROM stock_bars_daily '
                    'WHERE symbol=:symbol AND `date` BETWEEN :start AND :end ORDER BY `date`'),
                    conn, params=dict(symbol=symbol, start=start, end=end), parse_dates=['date'])
            local.to_parquet(output / f'{symbol}-local.parquet', index=False)
            result = dict(symbol=symbol, event=event, local=event_record(local, event))
            try:
                raw = fetch_eod(symbol, start=start, end=end, session=session, tracker=tracker,
                                feature='oracle_outlier_audit')
                splits = fetch_splits(symbol, session=session, tracker=tracker,
                                      feature='oracle_outlier_audit')
                atomic_json(output / f'{symbol}-raw.json', raw)
                atomic_json(output / f'{symbol}-splits.json', splits)
                fresh = pd.DataFrame([to_stock_bars_daily_row(b, symbol)
                    for b in eodhd_to_split_only(raw, splits)])
                fresh['date'] = pd.to_datetime(fresh.date)
                # Unknown historical identity: do not invent a stable ID for vendor rows.
                fresh['instrument_id'] = None
                fresh.to_parquet(output / f'{symbol}-canonical.parquet', index=False)
                result.update(status='RECEIVED', fresh=event_record(fresh, event),
                    splits=splits, raw_sha256=digest(output / f'{symbol}-raw.json'),
                    splits_sha256=digest(output / f'{symbol}-splits.json'))
            except Exception as exc:
                result.update(status='FAILED_PROVIDER_RECHECK', error_type=type(exc).__name__)
            results.append(result)
            atomic_json(output / 'progress.json', dict(completed=len(results), total=len(events)))
    finally:
        session.close()
        engine.dispose()
    atomic_json(output / 'report.json', dict(
        status='COMPLETED' if all(r['status'] == 'RECEIVED' for r in results) else 'PARTIAL',
        observed_at=datetime.now(timezone.utc).isoformat(), events=events, results=results, sql_writes=False,
        training=False, models_modified=False,
        caveats=['Same-provider current reread, not independent daily price certification',
                 'Historical aliases/ADRs/bankruptcy identity not certified',
                 'Windowed diagnostic only, no model feature recomputation or production repair']))
    print([(r['symbol'], r['status']) for r in results])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--events', type=parse_events,
                        help='Comma-separated SYMBOL:YYYY-MM-DD; one event per symbol')
    run(**vars(parser.parse_args()))
