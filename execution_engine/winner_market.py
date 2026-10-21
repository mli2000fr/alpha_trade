"""Read-only SIP evidence for campaign signals. No order or SQL mutation."""
from datetime import UTC, datetime, timedelta
import math
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import aware


class NativeWinnerMarket:
    def __init__(self, engine, account_id):
        self.engine, self.account_id = engine, account_id
        self.prior_highs = {}

    def __call__(self, state, now):
        from service.alpaca.intraday_bars import fetch_intraday
        from service.alpaca.clientAlpaca import fetch_latest_quotes
        now = aware(now)
        cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        day = now.astimezone(ZoneInfo('America/New_York')).date()
        sessions = [s for s in cal.sessions(day-timedelta(days=14), day) if s.is_open]
        previous = [s for s in sessions if s.close_at_utc < now]
        if not previous:
            raise ValueError('Official prior completed US session missing')
        previous_day = previous[-1].session_date
        # An after-close scan may tighten an existing stop, but cannot qualify
        # a new entry: the shared confirmation contract requires an open RTH.
        lookback = timedelta(minutes=5*(state['policy']['confirmation_bars']+2))
        earliest = (min((aware(l.get('last_bar_end') or l['filled_at'])-lookback for l in state['lots']),
            default=now.replace(hour=0, minute=0, second=0, microsecond=0))
            if state['policy']['trailing_stop_pct'] else now-lookback)
        rows = fetch_intraday(state['symbol'], start_epoch=earliest.timestamp(),
            end_epoch=now.timestamp(), interval='5m', feed='sip', account_id=self.account_id)
        bounds = {s.session_date: s for s in cal.sessions(
            earliest.astimezone(ZoneInfo('America/New_York')).date(), day) if s.is_open}
        bars, seen = [], set()
        for row in rows:
            stamp = datetime.fromtimestamp(float(row['timestamp']), UTC)
            session = bounds.get(stamp.astimezone(ZoneInfo('America/New_York')).date())
            if session is None or not session.open_at_utc <= stamp < session.close_at_utc:
                continue  # Extended-hours values cannot ratchet a regular-session trailing.
            if stamp in seen or (stamp-session.open_at_utc).total_seconds() % 300:
                raise ValueError('Duplicate or off-grid SIP campaign bar')
            seen.add(stamp)
            op, hi, lo, cl, vol = [float(row[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
            if (not all(math.isfinite(v) and v > 0 for v in (op, hi, lo, cl, vol))
                    or not lo <= min(op, cl) <= max(op, cl) <= hi):
                raise ValueError('Invalid real SIP campaign OHLCV')
            if stamp+timedelta(minutes=5) <= now:
                bars.append(dict(timestamp=stamp, open=op, high=hi, low=lo, close=cl,
                    volume=vol, session_tag='regular'))
        # Same RAW basis as today's five-minute bars. Fully split-adjusted
        # historical daily highs cannot be mixed with raw execution prices.
        key = state['symbol'], previous_day
        if key not in self.prior_highs:
            prior_session = previous[-1]
            raw_prior = fetch_intraday(state['symbol'], start_epoch=prior_session.open_at_utc.timestamp(),
                end_epoch=prior_session.close_at_utc.timestamp(), interval='5m', feed='sip', account_id=self.account_id)
            expected = set(range(int(prior_session.open_at_utc.timestamp()), int(prior_session.close_at_utc.timestamp()), 300))
            selected = [r for r in raw_prior if int(r['timestamp']) in expected]
            if len(selected) != len(expected) or {int(r['timestamp']) for r in selected} != expected:
                raise ValueError('Complete prior raw SIP regular session required')
            for row in selected:
                op, hi, lo, cl = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
                if not all(math.isfinite(v) and v > 0 for v in (op, hi, lo, cl)) or not lo <= min(op, cl) <= max(op, cl) <= hi:
                    raise ValueError('Unqualified prior raw SIP OHLC')
            self.prior_highs[key] = max(float(r['high']) for r in selected)
        snapshot = dict(bars=bars, prior_session_high=self.prior_highs[key],
            prior_session=previous_day, ask=None, bid=None, feed='sip')
        try:
            quote = fetch_latest_quotes([state['symbol']], account_id=self.account_id)[state['symbol']]
            if not all(math.isfinite(float(quote[k])) and float(quote[k]) > 0 for k in ('as', 'bs')):
                raise ValueError('SIP bid/ask size missing or zero')
            snapshot.update(ask=float(quote['ap']), bid=float(quote['bp']),
                quote_time=aware(quote['t']), raw_quote=quote)
        except Exception as exc:
            # Historical bars can still tighten an existing stop. No real-time
            # quote means no new entry or add; there is no IEX fallback.
            snapshot['quote_error'] = str(exc)[:300]
        return snapshot


from execution_engine.winner_live_risk import NativeWinnerRisk  # Public factory used by watcher.
