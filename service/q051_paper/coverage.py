"""Current PAPER serving coverage; never a historical universe or ranking filter."""
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from zoneinfo import ZoneInfo

from common.q051_paper import reference, require_paper


SOURCE = dict(endpoint='https://paper-api.alpaca.markets/v2/assets',
              params=dict(status='active', asset_class='us_equity'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def timestamp(value):
    result = datetime.fromisoformat(str(value))
    if result.tzinfo is None:
        raise ValueError('Q051 couverture : horodatage UTC explicite requis')
    return result.astimezone(UTC)


def latest_completed(now):
    from common.market_calendar import get_market_calendar
    local = now.astimezone(ZoneInfo('America/New_York')).date()
    sessions = [s for s in get_market_calendar('US_EQ', allow_us_weekday_fallback=False).sessions(
        local-timedelta(days=14), local) if s.is_open and s.close_at_utc < now]
    if not sessions:
        raise ValueError('Q051 couverture : aucune séance terminée qualifiée')
    return sessions[-1].session_date


def receipt(raw, universe, *, account, day, observed_at):
    require_paper(account)
    if not isinstance(raw, list) or not raw:
        raise ValueError('Q051 couverture : liste Alpaca absente')
    assets = {}
    for row in raw:
        name = row.get('symbol') if isinstance(row, dict) else None
        if (not isinstance(name, str) or not name or name != name.strip().upper() or name in assets
                or row.get('status') != 'active' or row.get('class') != 'us_equity'
                or type(row.get('tradable')) is not bool):
            raise ValueError('Q051 couverture : réponse Alpaca invalide ou dupliquée')
        assets[name] = dict(asset_id=row.get('id'), status=row['status'], tradable=row['tradable'])
    names = sorted(set(universe))
    records = {name:assets.get(name, dict(asset_id=None, status='not_in_active_assets', tradable=False))
               for name in names}
    eligible = [name for name in names if records[name]['status'] == 'active' and records[name]['tradable']]
    value = dict(schema_version=1, scope='q051_paper_alpaca_active_tradable', broker_mode='paper',
        account_id=account, profile_sha256=reference()['sha256'], signal_day=str(day),
        observed_at=observed_at.isoformat(), source=SOURCE, source_payload_sha256=fingerprint(raw),
        source_asset_count=len(raw), model_universe=names, model_universe_sha256=fingerprint(names),
        model_assets=records, eligible=eligible, excluded=sorted(set(names)-set(eligible)))
    validate(value, names, [day], now=observed_at)
    return value


def validate(value, universe, days, *, now=None):
    """Fresh, single latest completed session only; reject LIVE/historical reuse."""
    now = now or datetime.now(UTC)
    names = sorted(set(universe))
    try:
        require_paper(value['account_id'], value['broker_mode'])
        observed = timestamp(value['observed_at'])
        day = date.fromisoformat(value['signal_day'])
        records = value['model_assets']
        valid_rows = all(isinstance(row, dict) and type(row.get('tradable')) is bool
            and row.get('status') in ('active', 'not_in_active_assets')
            and (row['status'] == 'active' or row['tradable'] is False) for row in records.values())
        eligible = sorted(name for name, row in records.items()
                          if row.get('status') == 'active' and row.get('tradable') is True)
        if (value['schema_version'] != 1 or value['scope'] != 'q051_paper_alpaca_active_tradable'
                or value['profile_sha256'] != reference()['sha256'] or value['source'] != SOURCE
                or value['model_universe'] != names or value['model_universe_sha256'] != fingerprint(names)
                or set(records) != set(names) or not valid_rows
                or value['eligible'] != eligible or value['excluded'] != sorted(set(names)-set(eligible))
                or len(eligible) < 20 or len(value['source_payload_sha256']) != 64
                or value['source_asset_count'] < sum(r['status'] == 'active' for r in records.values())
                or not 0 <= (now-observed).total_seconds() <= 600
                or [str(d)[:10] for d in days] != [str(day)]
                or day != latest_completed(now) or day != latest_completed(observed)):
            raise ValueError('Q051 couverture : reçu incompatible, périmé ou hors dernière séance')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Q051 couverture : reçu incomplet') from exc
    return eligible


def capture(client, universe, *, account, day):
    require_paper(account)
    if client.broker_mode != 'paper' or client.account_id != account:
        raise ValueError('Q051 couverture : client PAPER du compte exact requis')
    raw = client._request('GET', '/v2/assets', params=SOURCE['params'])
    return receipt(raw, universe, account=account, day=day, observed_at=datetime.now(UTC)), raw
