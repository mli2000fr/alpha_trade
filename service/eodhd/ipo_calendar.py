"""IPO calendar observations; historical events are not historical PIT snapshots."""
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
import logging
import time
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from common.public_data_http import verified_session
from service.eodhd.consensus_snapshot import number, load_symbols
from service.eodhd.clientEodhd import _do_request, _get_base_url, _get_token, _redact_sensitive_text
from service.eodhd.quota import get_default_tracker
from service.eodhd.symbols import to_eodhd

BATCH = 'eodhd_ipo_calendar_sync'
TABLE = 'stock_ipo_eodhd_history'
LOG = logging.getLogger(__name__)


def windows(start, end):
    """Stable calendar-month windows for safe incremental backfill."""
    while start <= end:
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        stop = min(end, next_month - timedelta(days=1))
        yield start, stop
        start = stop + timedelta(days=1)


def optional_date(value):
    return date.fromisoformat(value) if value else None


def normalize(payload, symbols, observed, run_id):
    from service.forward_pit.batch import _hash, _json
    if observed.tzinfo is None:
        raise ValueError('Observation must be timezone-aware')
    if not isinstance(payload, dict) or not isinstance(payload.get('ipos'), list):
        raise ValueError('Unexpected IPO calendar schema')
    allowed = {to_eodhd(symbol): symbol for symbol in symbols}
    rows = []
    for item in payload['ipos']:
        if not isinstance(item, dict) or not item.get('code'):
            raise ValueError('IPO row without provider identity')
        if item['code'] not in allowed:
            continue
        values = {}
        for field in ('price_from', 'price_to', 'offer_price', 'shares'):
            value = number(item.get(field))
            if value is not None and value < 0:
                raise ValueError('Negative IPO price/shares')
            values['offered_shares' if field == 'shares' else field] = value or None
        stamp = observed.astimezone(UTC).replace(tzinfo=None)
        rows.append(dict(symbol=allowed[item['code']], provider_code=item['code'],
            company_name=item.get('name'), exchange_name=item.get('exchange'),
            currency=item.get('currency') or None, start_date=optional_date(item.get('start_date')),
            filing_date=optional_date(item.get('filing_date')), amended_date=optional_date(item.get('amended_date')),
            deal_type=item.get('deal_type'), **values,
            snapshot_date=observed.astimezone(ZoneInfo('America/New_York')).date(),
            observed_at=stamp, available_at=stamp, run_id=run_id,
            historical_pit_qualified=False, raw_hash=_hash(item), raw_payload_json=_json(item)))
    return rows


def insert_rows(conn, rows):
    count = 0
    for row in rows:
        columns = list(row)
        try:
            with conn.begin_nested():
                conn.execute(text(f'INSERT INTO {TABLE} ({",".join(columns)}) VALUES '
                    f'({",".join(":"+key for key in columns)})'), row)
        except IntegrityError as exc:
            if (not exc.orig.args or exc.orig.args[0] != 1062) and 'UNIQUE constraint failed' not in str(exc.orig):
                raise
        else:
            count += 1
    return count


def collect(engine, cfg, run_id, dry_run):
    from service.forward_pit.batch import Outcome, BatchRunError, _hash, _raw
    if engine.url.database != 'alpha_trade':
        raise ValueError('IPO collection requires alpha_trade (US)')
    symbols = load_symbols(engine, cfg)
    if not symbols:
        raise ValueError('Empty IPO universe')
    today = datetime.now(ZoneInfo('America/New_York')).date()
    start = date.fromisoformat(cfg['start_date']) if cfg.get('start_date') else today-timedelta(days=int(cfg.get('lookback_days',7)))
    end = date.fromisoformat(cfg['end_date']) if cfg.get('end_date') else today+timedelta(days=int(cfg.get('forward_days',21)))
    if end < start:
        raise ValueError('end_date precedes start_date')
    planned = list(windows(start,end))
    outcome = Outcome(requested=len(planned), details={'universe_count':len(symbols),
        'universe_hash':_hash(symbols), 'start_date':start, 'end_date':end,
        'provider_rows':0, 'selected_rows':0, 'skipped_windows':0,
        'units':'requested/received/failed=monthly windows; persisted=IPO observations',
        'historical_pit':False, 'errors':[]})
    try:
        if not dry_run:
            with engine.connect() as conn:
                conn.execute(text(f'SELECT id FROM {TABLE} LIMIT 0'))
                conn.execute(text('SELECT run_id FROM eodhd_ipo_collection_windows LIMIT 0'))
        with verified_session() as session:
            for first,last in planned:
                params=dict(first=first,last=last,universe=outcome.details['universe_hash'])
                if cfg.get('backfill') and not dry_run:
                    with engine.connect() as conn:
                        done=conn.execute(text('SELECT 1 FROM eodhd_ipo_collection_windows WHERE '
                            'window_start=:first AND window_end=:last AND universe_hash=:universe'),params).first()
                    if done:
                        outcome.details['skipped_windows']+=1
                        continue
                payload=_do_request(endpoint='calendar/ipos',url=_get_base_url()+'/calendar/ipos',
                    params={'api_token':_get_token(),'fmt':'json','from':first.isoformat(),'to':last.isoformat()},
                    session=session,tracker=get_default_tracker(),feature=BATCH)
                observed=datetime.now(UTC)
                if not dry_run:
                    # Archive even rejected schemas, before normalization.
                    with engine.begin() as conn:
                        _raw(conn,run_id,BATCH,'eodhd','/calendar/ipos',f'{first}:{last}',payload,observed=observed.replace(tzinfo=None))
                rows=normalize(payload,symbols,observed,run_id)
                if not dry_run:
                    with engine.begin() as conn:
                        added=insert_rows(conn,rows)
                        conn.execute(text('INSERT INTO eodhd_ipo_collection_windows '
                            '(window_start,window_end,universe_hash,completed_at,run_id) '
                            'VALUES (:first,:last,:universe,:stamp,:run) '
                            'ON DUPLICATE KEY UPDATE completed_at=VALUES(completed_at),run_id=VALUES(run_id)'),
                            params|dict(stamp=observed.replace(tzinfo=None),run=run_id))
                    outcome.persisted+=added
                outcome.received+=1
                outcome.empty+=int(not rows)
                outcome.details['provider_rows']+=len(payload['ipos'])
                outcome.details['selected_rows']+=len(rows)
                LOG.info('IPO window %s..%s completed=%d/%d provider=%d selected=%d persisted=%d',
                    first,last,outcome.received+outcome.details['skipped_windows'],len(planned),len(payload['ipos']),len(rows),outcome.persisted)
                time.sleep(float(cfg.get('sleep_seconds',1.1)))
    except Exception as exc:
        outcome.failed=1
        message=_redact_sensitive_text(str(exc))[:2000]
        outcome.details['errors'].append(message)
        raise BatchRunError(message,outcome) from None
    return outcome


def main():
    import argparse
    from service.forward_pit.batch import execute, _json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-date',required=True)
    parser.add_argument('--end-date',default=date.today().isoformat())
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    status,outcome=execute(BATCH,ipo_backfill_dates=(args.start_date,args.end_date))
    print('::alpha_trade_run_summary::'+_json({'batch':BATCH,'status':status,**outcome.__dict__}),flush=True)


if __name__=='__main__':
    main()
