"""READ ONLY diagnosis of test1's exact pending Winner plans and factor shares.

No risk approval is consumed, no plan/guard saved, no broker mutation allowed.
Values are a fresh diagnostic, not a reconstructed historical broker snapshot.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
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
from execution_engine.winner_risk import reapprove_campaign
from risk_management.factor_model import decompose_portfolio_risk, portfolio_beta_exposure
from service.alpaca.trading_client import AlpacaTradingClient
import risk_management.live_factor_context as factors


def main():
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,many):
        first=statement.lstrip().split()[0].upper()
        if first not in ('SELECT','SHOW','DESCRIBE','SET','WITH') or (
            first=='WITH' and re.search(r'\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP)\b',statement,re.I)):
            raise RuntimeError('Diagnostic forbids SQL mutations')
    event.listen(engine,'before_cursor_execute',readonly)
    config=ExecutionConfig(account_id='test1',broker_mode='paper',winner_pyramiding=load_winner_pyramiding_config())
    report=dict(account_id='test1',risk_run_id='3524c36a4ee84930',signal_date='2026-10-28',
        diagnostic_started_at=datetime.now(timezone.utc).isoformat(),read_only=True,
        historical_snapshot=False,rows=[])
    original=factors.factor_violations
    captured=[]
    def explain(context,weights,cfg,*,candidate,other_sides=None):
        total=sum(abs(v) for v in weights.values())
        normalized={s:abs(v)/total for s,v in weights.items() if v}
        decomposition=decompose_portfolio_risk(normalized,context['exposures'],context['covariance'])
        captured.append(dict(symbol=candidate,weights_relative_to_equity=weights,
            factor_contributions_pct=decomposition.factor_contribution_pct,
            systematic_risk_pct=decomposition.systematic_pct,
            specific_risk_pct=100.-decomposition.systematic_pct,
            total_annual_volatility=decomposition.total_volatility,
            significant_factors=sum(v>10. for v in decomposition.factor_contribution_pct.values()),
            required_factors=cfg.effective_min_factor_diversification,
            beta_exposure=portfolio_beta_exposure(weights,context['exposures'],basis=cfg.beta_exposure_basis),
            beta_limit=cfg.max_portfolio_beta,concentration_limit_pct=cfg.max_factor_concentration_pct*100,
            factor_exposures={s:{k:getattr(context['exposures'][s],k) for k in
                ('market_beta','size_exposure','momentum_exposure')} for s in weights},
            specific_variances={s:context['covariance'].specific_variances[s] for s in weights},
            factor_snapshot_hash=context['snapshot_hash']))
        return original(context,weights,cfg,candidate=candidate,other_sides=other_sides)
    with verified_session() as session:
        request=session.request
        def only_get(method,*args,**kwargs):
            if method.upper()!='GET':raise RuntimeError('Diagnostic forbids broker mutation')
            return request(method,*args,**kwargs)
        session.request=only_get
        broker=BrokerAdapter(AlpacaTradingClient(broker_mode='paper',account_id='test1',session=session),config)
        store=WinnerCampaignStore(engine)
        records=[r for r in store.rows('test1','paper') if r['state']['risk_run_id']==report['risk_run_id']]
        if len(records)!=6 or any(r['state']['status']!='PENDING' or r['state']['lots']
                or r['state']['operations'] for r in records):
            raise ValueError('Exact plans changed; no historical reconstruction invented')
        native=NativeWinnerRisk(ExecutionRepository(engine),broker,config)
        market=NativeWinnerMarket(engine,'test1',config)
        with patch('service.market.save_regime_state'),patch.object(WinnerCampaignStore,'save_guard'),\
                patch.object(factors,'factor_violations',explain):
            for record in sorted(records,key=lambda r:r['state']['target'].get('selection_rank') or 999):
                state=record['state']
                now=datetime.now(timezone.utc)
                snapshot=market(state,now)
                context=native.capture(state,snapshot,now,'ENTRY')
                before=len(captured)
                approval=reapprove_campaign(state,record['version'],state['initial_quantity'],snapshot,
                    datetime.now(timezone.utc),'ENTRY',context=context)
                if len(captured)!=before+1:raise ValueError('No factor stage reached; other guard blocks diagnostic')
                row=captured[-1]
                row.update(observed_at=context['captured_at'],equity=context['equity'],
                    held_positions=context['positions'],pending_entries=context['pending_entries'],
                    planned_quantity=state['initial_quantity'],reference_price=state['target']['entry_price'],
                    decision=approval['reason'],factor_rejections=approval['factor_rejections'])
                report['rows'].append(row)
                print(json.dumps({k:row[k] for k in ('symbol','factor_contributions_pct','specific_risk_pct',
                    'significant_factors','required_factors','decision')},default=str),flush=True)
    output=Path('artifacts/operations/test1_factor_zero')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir(parents=True,exist_ok=False)
    with (output/'report.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,default=str,allow_nan=False)
    print(json.dumps(dict(report_path=str((output/'report.json').resolve()),
        equity=report['rows'][0]['equity'],holdings=report['rows'][0]['held_positions'])),flush=True)
    engine.dispose()


if __name__=='__main__':main()
