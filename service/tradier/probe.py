"""One read-only quote request; no SQL, no orders, no provider activation."""
import argparse
from datetime import datetime, timezone
import json

from service.market.live_quotes import validate_live_quote
from service.tradier.quotes import fetch_latest_quotes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', default='AAPL,MSFT')
    args = parser.parse_args()
    symbols = list(dict.fromkeys(s.strip().upper() for s in args.symbols.split(',') if s.strip()))
    if not 1 <= len(symbols) <= 20:
        parser.error('Choisir entre 1 et 20 symboles')
    try:
        quotes = fetch_latest_quotes(symbols)
    except Exception as exc:
        # Only known credential message or status/type, never bearer token/headers/body.
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        print(json.dumps(dict(status='UNAVAILABLE', provider='tradier', error_type=type(exc).__name__,
                             http_status=status, hint='Vérifier TRADIER_API_TOKEN (production), droits et connectivité')))
        return 1
    results = []
    for symbol in symbols:
        quote = quotes.get(symbol)
        row = dict(symbol=symbol, available=quote is not None, fresh=False)
        if quote:
            try:
                validate_live_quote(quote, require_sizes=True)
                row['fresh'] = True
            except (ValueError, TypeError, KeyError, OverflowError):
                pass
            row.update(bid=quote['bp'], ask=quote['ap'], quote_time=quote['t'],
                       spread_bps=10000*(quote['ap']-quote['bp'])/((quote['ap']+quote['bp'])/2))
        results.append(row)
    print(json.dumps(dict(status='READ_COMPLETED', provider='tradier', feed='consolidated',
                          checked_at_utc=datetime.now(timezone.utc).isoformat(), quotes=results)))
    return 0 if all(r['fresh'] for r in results) else 2


if __name__ == '__main__':
    raise SystemExit(main())
