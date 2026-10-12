"""Bounded AVB missing-history diagnostic; SELECT and historical-data GET only.

Never substitutes prices, publishes an identity, writes SQL or sends an order.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import ssl

import pandas as pd
import requests
from sqlalchemy import event, text

from database.connection import get_sqlalchemy_engine
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_barrier_comparison import readonly_statement
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin
from service.alpaca.clientAlpaca import _build_headers


def run(output, fetch=False):
    output.mkdir(parents=True, exist_ok=True)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    event.listen(engine, 'before_cursor_execute', readonly_statement)
    event.listen(engine, 'begin', readonly_begin)
    with engine.connect() as conn:
        metadata = pd.read_sql(text('SELECT symbol,id_alpaca,company_name,exchange,status FROM stock_metadata WHERE symbol=:symbol'),
                               conn, params={'symbol': 'AVB'})
        history = pd.read_sql(text('SELECT symbol,`date`,`open`,high,low,`close`,adj_close,volume,instrument_id,data_source,data_adjustment '
            'FROM stock_bars_daily WHERE symbol=:symbol AND `date` BETWEEN :start AND :end ORDER BY `date`'),
            conn, params=dict(symbol='AVB', start='2026-08-01', end='2026-10-06'), parse_dates=['date'])
    engine.dispose()
    atomic_json(output/'metadata.json', metadata.to_dict('records'))
    history.to_parquet(output/'sql-history.parquet', index=False)
    observed = datetime.now(timezone.utc).isoformat()
    result = dict(observed_at=observed, sql_history_rows=len(history), sql_writes=False, orders=False,
                  last_sql_bar=str(history.date.max()), sql_history_sha256=digest(output/'sql-history.parquet'))
    if fetch:
        trust = output/'windows-trust.pem'
        trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
        headers = _build_headers('default')
        with requests.Session() as session:
            session.verify = str(trust.resolve())
            asset = session.get('https://paper-api.alpaca.markets/v2/assets/AVB', headers=headers, timeout=30)
            result['asset_http'] = asset.status_code
            if asset.ok:
                payload = asset.json()
                public = {k: payload.get(k) for k in ('id', 'symbol', 'name', 'exchange', 'status', 'class')}
                atomic_json(output/'alpaca-asset.json', public)
                result['asset'] = public
            params = dict(timeframe='1Day', feed='sip', adjustment='split', limit=1000,
                start='2026-08-12T00:00:00-04:00', end='2026-10-07T00:00:00-04:00')
            response = session.get('https://data.alpaca.markets/v2/stocks/AVB/bars', params=params, headers=headers, timeout=30)
            result['bars_http'] = response.status_code
            if response.ok:
                payload = response.json()
                atomic_json(output/'alpaca-bars.json', payload)
                result['provider_rows'] = len(payload.get('bars') or [])
                result['raw_sha256'] = digest(output/'alpaca-bars.json')
                result['pagination_remaining'] = bool(payload.get('next_page_token'))
                overlaps = []
                for bar in payload.get('bars') or []:
                    day = pd.Timestamp(bar['t']).tz_convert('America/New_York').normalize().tz_localize(None)
                    source = history.loc[history.date.eq(day)]
                    if len(source) == 1:
                        ratios = {c: float(bar[k]/source[c].iloc[0]) for c, k in [('open', 'o'), ('high', 'h'), ('low', 'l'), ('close', 'c')]}
                        overlaps.append(dict(date=str(day.date()), ratios=ratios))
                result['overlap_ohlc_ratios_provider_over_sql'] = overlaps
                result['status'] = 'EVIDENCE_ONLY_NOT_PRICE_OR_IDENTITY_QUALIFICATION'
            else:
                result['status'] = 'BLOCKED_PROVIDER_HTTP'
    atomic_json(output/'report.json', result)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    run(args.output, args.fetch)
