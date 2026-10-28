"""Configured consolidated US quotes; order routing remains independent."""
from datetime import datetime, timezone
import math


def configured_provider():
    from common.config_loader import load_config
    value = str((load_config().get('market_data') or {}).get('quotes_provider_live', 'alpaca')).strip().lower()
    if value not in ('alpaca', 'tradier'):
        raise ValueError('market_data.quotes_provider_live doit être alpaca ou tradier (aucun fallback IEX/Yahoo)')
    return value


def fetch_latest_quotes(symbols, session=None, account_id=None):
    provider = configured_provider()
    if provider == 'tradier':
        from service.tradier.quotes import fetch_latest_quotes as fetch
        return fetch(symbols, session=session, account_id=account_id)
    from service.alpaca.clientAlpaca import fetch_latest_quotes as fetch
    rows = fetch(symbols, session=session, account_id=account_id)
    return {symbol: {**row, 'provider': 'alpaca', 'feed': 'sip',
                     'source': 'alpaca_sip', 'is_realtime': True}
            for symbol, row in rows.items()}


def validate_live_quote(quote, *, max_age_seconds=300, now=None, require_sizes=False):
    """Reject missing, delayed, wrong-source, crossed, stale or future evidence."""
    if (not isinstance(quote, dict) or quote.get('is_realtime') is not True
            or (quote.get('provider'), quote.get('feed')) not in
            (('alpaca', 'sip'), ('tradier', 'consolidated'))):
        raise ValueError('Quote consolidée temps réel non qualifiée (Alpaca SIP ou Tradier production)')
    bid, ask = float(quote['bp']), float(quote['ap'])
    if not all(math.isfinite(v) and v > 0 for v in (bid, ask)) or ask <= bid:
        raise ValueError('Bid/ask consolidé invalide')
    if require_sizes:
        if not all(math.isfinite(float(quote[k])) and float(quote[k]) > 0 for k in ('bs', 'as')):
            raise ValueError('Tailles bid/ask invalides')
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ValueError('Horloge/seuil de fraîcheur invalide')
    keys = ('t', 'bid_time', 'ask_time') if quote['provider'] == 'tradier' else ('t',)
    stamps = []
    for key in keys:
        stamp = datetime.fromisoformat(str(quote[key]).replace('Z', '+00:00'))
        if stamp.tzinfo is None or not 0 <= (current-stamp).total_seconds() <= max_age_seconds:
            raise ValueError('Quote consolidée future, périmée ou sans fuseau')
        stamps.append(stamp)
    if quote['provider'] == 'tradier' and stamps[0] != min(stamps[1:]):
        raise ValueError('Horodatages bid/ask Tradier incohérents')
    return quote


def validate_campaign_quote(snapshot, *, now, max_age_seconds):
    """Keep historical bars SIP; qualify Tradier quote evidence separately."""
    if snapshot.get('feed') != 'sip' or snapshot.get('quote_error'):
        raise ValueError('Barres SIP / quote consolidée temps réel requises')
    provider = snapshot.get('quote_provider', 'alpaca')
    if provider not in ('alpaca', 'tradier'):
        raise ValueError('Fournisseur quote campagne inconnu')
    if provider == 'tradier' or snapshot.get('raw_quote') is not None:
        quote = validate_live_quote(snapshot['raw_quote'], now=now, max_age_seconds=max_age_seconds, require_sizes=True)
        stamp = datetime.fromisoformat(str(snapshot['quote_time']).replace('Z', '+00:00'))
        if (quote['provider'] != provider or float(snapshot['bid']) != quote['bp']
                or float(snapshot['ask']) != quote['ap']
                or stamp != datetime.fromisoformat(quote['t'].replace('Z', '+00:00'))):
            raise ValueError('Snapshot campagne différent de la quote source')
