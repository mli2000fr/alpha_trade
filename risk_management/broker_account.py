"""Current broker capital for PAPER/LIVE risk; never CLI or cached equity."""
from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo

from risk_management.models import AccountRiskSnapshot
from risk_management.operational_data import OperationalDataSnapshot, OperationalDataUnavailable


def capture_current_account(account_id, mode, *, client=None, clock=None):
    if mode not in ('paper','live'):
        raise ValueError('Capture compte réservée à PAPER/LIVE')
    owned_session=None
    if client is None:
        from common.public_data_http import verified_session
        from service.alpaca.accounts import AccountRegistry
        from service.alpaca.trading_client import AlpacaTradingClient
        configured=AccountRegistry.get().resolve(account_id)
        if configured.mode!=mode:
            raise OperationalDataUnavailable('Mode du compte incompatible avec le risque demandé')
        owned_session=verified_session()
        client=AlpacaTradingClient(broker_mode=mode,account_id=account_id,session=owned_session)
    now=clock or (lambda:datetime.now(timezone.utc))
    try:
        account=client.get_account()
        observed=now()
        if observed.tzinfo is None:
            raise ValueError('Horodatage de capture sans fuseau')
        if not isinstance(account,dict) or account.get('trading_blocked') or account.get('account_blocked'):
            raise ValueError('Compte broker invalide ou bloqué')
        positions=client.get_positions()
        orders=client.list_orders(status='open',limit=500)
        if not isinstance(positions,list) or not isinstance(orders,list) or len(orders)>=500:
            raise ValueError('Positions/ordres invalides ou potentiellement tronqués')
        snapshot=OperationalDataSnapshot.from_raw(account_id=account_id,account=account,
            positions=positions,orders=orders,source=f'broker:{mode}:risk',as_of=observed)
        for field in ('equity','cash','buying_power'):
            if not math.isfinite(getattr(snapshot.account,field)):
                raise ValueError('Valeur de compte non finie')
        age=(now()-observed).total_seconds()
        if age<0 or age>300:
            raise ValueError('Capture compte périmée ou horloge incohérente')
        return snapshot,account
    except Exception as exc:
        raise OperationalDataUnavailable(
            f'Risque {mode.upper()} : snapshot réel du compte {account_id} indisponible/invalide ; '
            'aucun fallback sur --account-equity, aucune nouvelle cible') from exc
    finally:
        if owned_session is not None:
            owned_session.close()


def risk_snapshot(snapshot,raw,previous=None):
    """Use historical evidence only for peak drawdown, never current capital."""
    account=snapshot.account
    if previous is not None and previous.account_id!=account.account_id:
        raise OperationalDataUnavailable('Historique du compte différent du compte broker sélectionné')
    equity=float(account.equity)
    last=float(raw.get('last_equity',equity))
    peak=getattr(previous,'high_watermark',None) if previous else None
    peak=equity if peak is None else float(peak)
    if (not all(math.isfinite(v) for v in (equity,last,peak)) or equity<=0 or last<=0 or peak<=0):
        raise OperationalDataUnavailable('Equity/équité précédente/plus-haut broker invalide')
    return AccountRiskSnapshot(account_id=account.account_id,
        trade_date=account.as_of.astimezone(ZoneInfo('America/New_York')).date(),
        cash=account.cash,equity=equity,buying_power=account.buying_power,
        high_watermark=max(equity,peak),daily_total_pnl=equity-last,
        source=account.source,captured_at=account.as_of)
