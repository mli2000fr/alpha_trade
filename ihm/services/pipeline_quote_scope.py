"""Safe step-4 defaults: closed-session SIP, no implicit real-time request."""
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from common.config_loader import load_config
from common.market_calendar import get_market_calendar
from common.universe_files import normalize_universe_file_source, is_universe_file_source

DEFAULT_SOURCE = 'universe-file:config/univers_batch/univers_filtred_tradable.txt'


def quote_defaults(config=None):
    config = load_config() if config is None else config
    market = (config or {}).get('market_data') or {}
    policy = market.get('pipeline_quotes') or {}
    if not isinstance(policy, dict):
        raise ValueError('market_data.pipeline_quotes doit être un dictionnaire')
    mode = str(policy.get('mode', 'historical')).strip().lower()
    if mode not in ('historical', 'latest'):
        raise ValueError('market_data.pipeline_quotes.mode : historical ou latest attendu')
    lookback = policy.get('lookback_days', 7)
    if type(lookback) is not int or not 0 <= lookback <= 365:
        raise ValueError('market_data.pipeline_quotes.lookback_days : entier entre 0 et 365 attendu')
    source = str(policy.get('symbol_source', DEFAULT_SOURCE)).strip()
    if not source:
        raise ValueError('market_data.pipeline_quotes.symbol_source vide')
    known = {'active-tradable','stock-scores','stock-scores-history','stock-scores-all',
             'stock-bars-daily','tradable-universe'}
    if not is_universe_file_source(source) and source.lower().replace('_','-') not in known:
        raise ValueError('market_data.pipeline_quotes.symbol_source invalide ; aucun élargissement implicite')
    if str(market.get('quotes_historical_feed', 'sip')).strip().lower() != 'sip':
        raise ValueError('Quotes : SIP obligatoire, aucun fallback IEX')
    return dict(mode=mode, lookback_days=lookback, symbol_source=normalize_universe_file_source(source))


def _day(value):
    if value is None or str(value).strip() == '':
        return None
    return date.fromisoformat(str(value).strip())


def resolve_quote_scope(options, *, config=None, now=None, calendar=None):
    """Return pinned options; never rewrite trade_date or an explicit history window."""
    policy = quote_defaults(config)
    start = _day(options.data_integrity_quotes_from_date)
    end = _day(options.data_integrity_quotes_to_date)
    explicit = start is not None or end is not None
    mode = options.data_integrity_quotes_mode or ('historical' if explicit else policy['mode'])
    if mode not in ('historical', 'latest'):
        raise ValueError('Mode de collecte quotes inconnu')
    source = options.data_integrity_quotes_symbol_source or policy['symbol_source']
    values = dict(data_integrity_quotes_mode=mode, data_integrity_quotes_symbol_source=source)
    if mode == 'latest':
        if explicit:
            raise ValueError('Mode temps réel incompatible avec une fenêtre historique explicite')
        return replace(options, **values)
    if explicit:
        start, end = start or end, end or start
        if start > end:
            raise ValueError('Quotes : début postérieur à la fin')
    else:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError('Horodatage timezone-aware requis')
        today = now.astimezone(ZoneInfo('America/New_York')).date()
        limit = min(_day(options.trade_date) or today, today)
        calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        eligible = [day for day in calendar.session_dates(limit-timedelta(days=32), limit)
                    if calendar.session_bounds(day)[1]+timedelta(minutes=20) <= now]
        if not eligible:
            raise ValueError('Aucune séance US clôturée et disponible pour les quotes SIP')
        end = max(eligible)
        start = end-timedelta(days=policy['lookback_days'])
    return replace(options, **values, data_integrity_quotes_from_date=start.isoformat(),
                   data_integrity_quotes_to_date=end.isoformat())
