"""Read-only qualification of existing unsubmitted PAPER Winner campaigns.

No broker POST/DELETE, SQL DML, guard-state save, campaign save or order bridge.
The native risk collector is used with its current input publication; missing
publication is an error under the SQL read-only guard, never a silent refresh.
"""
import argparse
from datetime import UTC, datetime
import json
import re
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

from common.verified_http import verified_session
from common.winner_pyramiding import load_winner_pyramiding_config
from database.connection import get_sqlalchemy_engine
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.winner_campaign_store import WinnerCampaignStore
from execution_engine.winner_live_risk import NativeWinnerRisk
from execution_engine.winner_market import NativeWinnerMarket
from service.alpaca.trading_client import AlpacaTradingClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--risk-run-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    engine = get_sqlalchemy_engine()
    def readonly(conn, cursor, statement, parameters, context, many):
        first = statement.lstrip().split()[0].upper()
        if (first not in ('SELECT', 'SHOW', 'DESCRIBE', 'SET', 'WITH')
                or (first == 'WITH' and re.search(r'\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP)\b',statement,re.I))):
            raise RuntimeError('Read-only preview forbids SQL mutation')
    event.listen(engine, 'before_cursor_execute', readonly)
    config = ExecutionConfig(broker_mode='paper', account_id='default',
        winner_pyramiding=load_winner_pyramiding_config())
    session = verified_session()
    original_request = session.request
    def only_get(method, *a, **kw):
        if method.upper() != 'GET':
            raise RuntimeError('Read-only preview forbids broker mutation')
        return original_request(method, *a, **kw)
    session.request = only_get
    broker = BrokerAdapter(AlpacaTradingClient(broker_mode='paper', account_id='default', session=session),config)
    store = WinnerCampaignStore(engine)
    rows = [r for r in store.rows('default','paper') if r['state']['risk_run_id']==args.risk_run_id]
    if not rows or any(r['state']['status']!='PENDING' or r['state']['lots']
            or r['state'].get('operations') or r['state'].get('parents') for r in rows):
        raise ValueError('Preview requires untouched pending plans for the exact risk run')
    positions = broker.get_all_positions()
    orders = broker.list_recent_orders(status='open',limit=500)
    if positions or orders:
        raise ValueError('Account activity changed; inspect before this isolated preview')
    repo = ExecutionRepository(engine)
    risk = NativeWinnerRisk(repo,broker,config)
    market = NativeWinnerMarket(engine,'default',config)
    report = dict(observed_at=datetime.now(UTC).isoformat(),risk_run_id=args.risk_run_id,
        broker_positions=len(positions),broker_open_orders=len(orders),read_only=True,decisions=[])
    # These are the two side effects of capture; they are suppressed explicitly.
    # The SQL guard above independently enforces no other write can occur.
    with patch('service.market.save_regime_state'), patch.object(WinnerCampaignStore,'save_guard'):
        for row in rows:
            state = row['state']
            now = datetime.now(UTC)
            snapshot = market(state,now)
            decision = risk(state,row['version'],state['initial_quantity'],snapshot,now,'ENTRY')
            report['decisions'].append(dict(symbol=state['symbol'],campaign_id=state['campaign_id'],decision=decision))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,default=str,allow_nan=False)
    print(json.dumps(report,default=str))


if __name__=='__main__':
    main()
