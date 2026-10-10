"""Explicit LLM direction; subjective confidence never becomes a probability."""
import json
from .runner import qualified_selection


def validate_short_broker(broker, symbols, *, account=None):
    """Read-only, fail-closed ETB check at risk AND immediately before execution.

    HTB/locates and fractional shorts are deliberately unsupported. No API order.
    """
    from service.alpaca.accounts import AccountRegistry
    from .runner import assert_paper_account
    assert_paper_account('default')
    if AccountRegistry.get().resolve('default').long_only:
        raise ValueError('Compte default long_only : SHORT GPT interdit')
    account = account if account is not None else broker.get_account()
    if (account.get('shorting_enabled') is not True or account.get('trading_blocked')
            or account.get('account_blocked')):
        raise ValueError('Compte PAPER non autorisé à vendre à découvert')
    evidence = {}
    from .repository import utcnow
    for symbol in symbols:
        asset = broker.get_asset(symbol)
        if (asset.get('symbol') != symbol or asset.get('status') != 'active'
                or any(asset.get(k) is not True for k in
                       ('tradable', 'marginable', 'shortable', 'easy_to_borrow'))):
            raise ValueError(f'SHORT GPT bloqué : actif {symbol} non qualifié/ETB')
        evidence[symbol] = {'provider': 'alpaca_paper_asset', 'observed_at': str(utcnow()),
                            'shortable': True, 'easy_to_borrow': True}
    return evidence


def capture_paper_snapshot():
    from .runner import assert_paper_account
    from service.alpaca.trading_client import AlpacaTradingClient
    from risk_management.operational_data import OperationalDataSnapshot
    assert_paper_account()
    client = AlpacaTradingClient(broker_mode='paper', account_id='default')
    account = client.get_account()
    if account.get('trading_blocked') or account.get('account_blocked'):
        raise ValueError('Compte principal PAPER bloqué par le broker')
    positions, orders = client.get_positions(), client.list_orders(status='open', limit=500)
    if len(orders) >= 500:
        raise ValueError('Liste ordres potentiellement tronquée; risque bloqué')
    return OperationalDataSnapshot.from_raw(account_id='default', account=account,
        positions=positions, orders=orders, source='broker:paper:llm'), account


def load_candidates(engine, run_id, trade_date, account_id, universe_run_id, universe_symbols):
    from risk_management.selection_contract import MLRankedCandidate
    run, selected = qualified_selection(engine, run_id, trade_date, account_id)
    universe = set(universe_symbols)
    short_symbols = [i['symbol'] for i in selected if i['symbol'] in universe
                     and json.loads(i['assessment_json'])['decision'] == 'SHORT']
    borrow = {}
    if short_symbols:
        from service.alpaca.trading_client import AlpacaTradingClient
        borrow = validate_short_broker(AlpacaTradingClient(broker_mode='paper', account_id='default'),
                                      short_symbols)
    result = []
    for rank, item in enumerate(selected, 1):
        if item['symbol'] not in universe:
            continue  # live tradability remains authoritative, never replaced by the LLM
        assessment = json.loads(item['assessment_json'])
        result.append(MLRankedCandidate(symbol=item['symbol'], trade_date=trade_date,
            side=assessment['decision'].lower(), p_long=0., p_short=0., p_flat=0., p_side=0., side_rank=rank,
            model_run_id=run['batch_id'], universe_run_id=universe_run_id,
            account=account_id, lineage={'llm_filter_run_id': run_id,
                'confidence_uncalibrated': assessment['confidence'],
                'oracle_score': item['oracle_score'], 'selection_source': 'oracle_web_llm_directional',
                'borrow_evidence': borrow.get(item['symbol'])}))
    return result


def build_entries(builder, candidates, prices, sector_map, trade_date, return_matrix):
    from risk_management.models import SelectionScore
    if any(c.side not in ('long', 'short') for c in candidates):
        raise ValueError('Direction GPT inconnue')
    if any(c.side == 'short' for c in candidates) and not builder._cfg.short_selling_enabled:
        raise ValueError('SHORT désactivé par la configuration risque')
    from service.market.new_entry_data_guard import validate_entry_prices
    rejected = validate_entry_prices(prices, [c.symbol for c in candidates], trade_date)
    if rejected:
        raise ValueError(f'Prix/ATR/ADV J non qualifié: {rejected}')
    selections = [SelectionScore(symbol=c.symbol, sector=sector_map.get(c.symbol, 'Unknown'),
        score_used=c.lineage['confidence_uncalibrated'], score_source='llm_confidence_uncalibrated',
        snapshot_date=trade_date, selection_rank=c.side_rank, side='sell' if c.side == 'short' else 'buy',
        selector_signal_mode='oracle_web_llm_directional', universe_run_id=c.universe_run_id,
        selection_explanation=f'LLM audited run {c.lineage["llm_filter_run_id"]}; not a calibrated probability')
        for c in candidates]
    return builder.build(selections, prices, return_matrix=return_matrix, trade_date=trade_date,
                         selection_policy='oracle_web_llm_directional')
