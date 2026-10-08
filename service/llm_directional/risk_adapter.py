"""LONG is explicit LLM policy; subjective confidence never becomes P(LONG)."""
import json
from .runner import qualified_selection


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
    result = []
    for rank, item in enumerate(selected, 1):
        if item['symbol'] not in universe:
            continue  # live tradability remains authoritative, never replaced by the LLM
        assessment = json.loads(item['assessment_json'])
        result.append(MLRankedCandidate(symbol=item['symbol'], trade_date=trade_date,
            side='long', p_long=0., p_short=0., p_flat=0., p_side=0., side_rank=rank,
            model_run_id=run['batch_id'], universe_run_id=universe_run_id,
            account=account_id, lineage={'llm_filter_run_id': run_id,
                'confidence_uncalibrated': assessment['confidence'],
                'oracle_score': item['oracle_score'], 'selection_source': 'oracle_web_llm_long'}))
    return result


def build_entries(builder, candidates, prices, sector_map, trade_date, return_matrix):
    from risk_management.models import SelectionScore
    for candidate in candidates:
        price = prices.get(candidate.symbol)
        if (price is None or price.price_asof_date != trade_date or price.atr_asof_date != trade_date
                or price.adv_usd is None or price.adv_usd <= 0):
            raise ValueError(f'Prix/ATR/ADV J non qualifié: {candidate.symbol}')
    selections = [SelectionScore(symbol=c.symbol, sector=sector_map.get(c.symbol, 'Unknown'),
        score_used=c.lineage['confidence_uncalibrated'], score_source='llm_confidence_uncalibrated',
        snapshot_date=trade_date, selection_rank=c.side_rank, side='buy',
        selector_signal_mode='oracle_web_llm_long', universe_run_id=c.universe_run_id,
        selection_explanation=f'LLM audited run {c.lineage["llm_filter_run_id"]}; not a calibrated probability')
        for c in candidates]
    return builder.build(selections, prices, return_matrix=return_matrix, trade_date=trade_date,
                         selection_policy='oracle_web_llm_long')
