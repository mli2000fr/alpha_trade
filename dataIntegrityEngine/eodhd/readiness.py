"""Session publication window and exact-date coverage for the US daily pipeline."""
from datetime import UTC, date, datetime, timedelta
import logging
import math
import time
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text

LOGGER = logging.getLogger('dataIntegrityEngine.import_eodhd_bar')


def publication_offset(config):
    value = float((config.get('eodhd') or {}).get('bulk_publish_offset_hours', 2))
    if not math.isfinite(value) or not 0 <= value <= 24:
        raise ValueError('eodhd.bulk_publish_offset_hours doit être entre 0 et 24')
    return timedelta(hours=value)


def calendar_us():
    from common.market_calendar import get_market_calendar
    return get_market_calendar('US_EQ', allow_us_weekday_fallback=False)


def publication_at(day, config, *, calendar=None):
    calendar = calendar or calendar_us()
    if day not in calendar.session_dates(day, day):
        raise ValueError(f'Date hors séance US : {day}')
    _, close = calendar.session_bounds(day)
    return close + publication_offset(config)


def latest_published_session(config, *, now=None, calendar=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('Horodatage timezone-aware requis')
    calendar = calendar or calendar_us()
    day = now.astimezone(ZoneInfo('America/New_York')).date()
    # Publication delay is an operational hypothesis, not a provider guarantee.
    for session in reversed(calendar.session_dates(day - timedelta(days=32), day)):
        if now >= publication_at(session, config, calendar=calendar):
            return session.isoformat()
    raise ValueError('Aucune séance US publiée dans la fenêtre de 32 jours')


def wait_for_publication(day, config, *, now_fn=None, sleep_fn=None, calendar=None):
    now_fn = now_fn or (lambda: datetime.now(UTC))
    sleep_fn = sleep_fn or time.sleep
    ready_at = publication_at(day, config, calendar=calendar)
    now = now_fn()
    if now.tzinfo is None:
        raise ValueError('Horodatage timezone-aware requis')
    if (ready_at - now).total_seconds() > 24 * 3600:
        raise ValueError('Date cible future : attente de publication limitée à 24 heures')
    while now < ready_at:
        seconds = (ready_at - now).total_seconds()
        LOGGER.info('[eodhd] attente publication séance=%s prête=%s Paris ; reste=%.0fs',
                    day, ready_at.astimezone(ZoneInfo('Europe/Paris')).isoformat(), seconds)
        sleep_fn(min(seconds, 60))
        now = now_fn()
    return ready_at


def target_coverage(engine, symbols, day, *, benchmark='SPY', minimum=.95):
    """Read committed canonical bars; older/future/filled/invalid bars never qualify."""
    if not math.isfinite(minimum) or not 0 < minimum <= 1:
        raise ValueError('Couverture minimale attendue dans ]0,1]')
    universe = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
    if not universe:
        raise ValueError('Univers de contrôle vide')
    benchmark = str(benchmark).strip().upper()
    if not benchmark:
        raise ValueError('Benchmark de contrôle vide')
    query = text('''SELECT symbol FROM stock_bars_daily
        WHERE `date`=:day AND symbol IN :symbols AND is_filled=0
          AND `open`>0 AND high>0 AND low>0 AND `close`>0 AND volume>0
          AND high>=low AND high>=`open` AND high>=`close` AND low<=`open` AND low<=`close`
    ''').bindparams(bindparam('symbols', expanding=True))
    with engine.connect() as conn:
        present = {str(s).strip().upper() for s in conn.execute(query,
            {'day': day, 'symbols': sorted(set(universe) | {benchmark})}).scalars()}
    missing = sorted(set(universe) - present)
    ratio = (len(universe) - len(missing)) / len(universe)
    result = dict(target_date=str(day), requested=len(universe),
                  covered=len(universe)-len(missing), missing_count=len(missing),
                  missing_symbols=missing, coverage_ratio=ratio, minimum=minimum,
                  benchmark=benchmark, benchmark_available=benchmark in present)
    result['status'] = 'PASSED' if ratio >= minimum and benchmark in present else 'FAILED'
    return result
