"""READ ONLY Q051 activation proof: model, batch plan, accounts and daily inputs.

HTTP is limited to GET; SQL to SELECT/SHOW/SET/DESCRIBE. Does not start a
watcher, predict, train, create a plan, submit an order or alter shared SQL.
"""
import argparse
from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
from unittest.mock import patch

import requests
from sqlalchemy import event, text

from common.config_loader import load_batch_config
from common.q051_paper import reference, settings
from database.connection import get_sqlalchemy_engine
from service.forward_pit.us_pipeline import execute_pipeline
from service.q051_paper.pipeline import contract, make_broker
from service.q051_paper.risk import capture, complete_context
from service.q051_paper.coverage import capture as capture_coverage, latest_completed


def run(output, selection_run_id=None):
    policy = settings()
    day = latest_completed(datetime.now(UTC))
    root, protocol = contract(policy['model_batch_id'], policy['artifacts_dir'], day)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,many):
        if statement.lstrip().split()[0].upper() not in ('SELECT','SHOW','SET','DESCRIBE'):
            raise ValueError('Q051 readiness: SQL read only')
    event.listen(engine,'before_cursor_execute',readonly)
    original = requests.Session.request
    methods = []
    output.mkdir(parents=True,exist_ok=False)
    def get_only(self,method,url,*args,**kwargs):
        if method.upper() != 'GET':
            raise ValueError('Q051 readiness: HTTP GET only')
        methods.append(method)
        return original(self,method,url,*args,**kwargs)
    from common.market_calendar import get_market_calendar
    session = next(s for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(day,day) if s.is_open)
    checks = []
    coverage_summary = None
    with patch.object(requests.Session,'request',get_only):
        plan = execute_pipeline(engine,load_batch_config()['us_pipeline'],'q051-readiness',True,
                                now=session.close_at_utc+timedelta(minutes=30)).details
        for account in [plan['account_id'],*plan['other_paper_accounts']]:
            repo, broker, cfg = make_broker(engine,account)
            try:
                if account == plan['account_id']:
                    coverage, assets = capture_coverage(broker._client, protocol['universe'], account=account, day=day)
                    for name, value in [('coverage.json',coverage),('alpaca_assets.json',assets)]:
                        with (output/name).open('x',encoding='utf-8') as stream:
                            json.dump(value,stream,indent=2,ensure_ascii=False)
                    coverage_summary = dict(scope=coverage['scope'], denominator=len(coverage['eligible']),
                        excluded=len(coverage['excluded']), model_universe=len(protocol['universe']))
                context = capture(repo,broker,account,day,datetime.now(UTC))
                complete = complete_context(context,engine,protocol['universe'])
                qualified = complete['returns'].notna().all()
                missing_held = [p['symbol'] for p in context['positions'] if not qualified.get(p['symbol'],False)]
                check = dict(account_id=account,broker_mode='paper',status='READY' if not missing_held else 'MISSING_HELD_COVARIANCE',
                    equity=context['equity'],buying_power=context['available_buying_power'],
                    positions=len(context['positions']),pending_entries=len(context['pending_entries']),
                    regime_allows_new_entries=context['regime_allowed'],qualified_covariance_symbols=int(qualified.sum()),
                    missing_held_covariance=missing_held)
                if selection_run_id:
                    from service.q051_paper.pipeline import qualified
                    from service.q051_paper.risk import quantity
                    import math
                    import pandas as pd
                    folder, selection = qualified(selection_run_id,batch=policy['model_batch_id'],day=day,
                                                  artifacts_dir=policy['artifacts_dir'])
                    selected = pd.read_parquet(folder/'selection.parquet')
                    decisions = []
                    for row in selected[selected.selected].sort_values('rank').to_dict('records'):
                        symbol=row['symbol'];price=complete['reference_closes'].get(symbol)
                        asset=broker._client.get_asset(symbol)
                        if asset.get('status')!='active' or asset.get('tradable') is not True:
                            decision=dict(quantity=0,reason='BROKER_ASSET_NOT_TRADABLE')
                        elif price is None or not math.isfinite(float(price)) or price<=0:
                            decision=dict(quantity=0,reason='MISSING_PRIOR_CLOSE')
                        else:
                            from execution_engine.winner_live_risk import concentration_allowed
                            from common.q051_paper import risk_config
                            with engine.connect() as connection:
                                fills=connection.execute(text('SELECT f.symbol,r.request_id,r.side,r.intent_role,f.filled_qty,'
                                    'f.avg_fill_price,f.fill_timestamp FROM execution_broker_fills f '
                                    'JOIN execution_order_requests r ON r.request_id=f.request_id '
                                    'JOIN execution_runs e ON e.exec_run_id=r.exec_run_id '
                                    "WHERE f.account_id=:account AND e.broker_mode='paper' AND f.symbol=:symbol "
                                    'AND f.fill_timestamp<=:now ORDER BY f.fill_timestamp,f.fill_id'),
                                    dict(account=account,symbol=symbol,now=datetime.now(UTC))).mappings().all()
                            complete['concentration_allowed']=concentration_allowed(fills,risk_config(context['equity']),symbol,day,'ENTRY')
                            decision=quantity(symbol=symbol,price=float(price),proposed=math.floor(context['equity']/price),context=complete)
                            if decision['quantity']:
                                notional=decision['quantity']*price
                                complete['pending_entries'].append(dict(symbol=symbol,side='buy',notional=notional))
                                complete['available_buying_power']-=notional*1.0025
                        decisions.append(dict(symbol=symbol,quantity=decision['quantity'],reason=decision['reason']))
                    check['selection_run_id']=selection_run_id
                    check['selection_coverage']=selection['coverage']
                    check['read_only_sizing_preview']=decisions
                checks.append(check)
            except Exception as exc:
                checks.append(dict(account_id=account,status='FAILED',error_type=type(exc).__name__,error=str(exc)[:300]))
        with engine.connect() as c:
            required = {}
            for name in ['risk_decisions','portfolio_targets','execution_order_requests']:
                rows=c.execute(text('SHOW COLUMNS FROM '+name)).mappings()
                required[name]=[r['Field'] for r in rows if r['Null']=='NO' and r['Default'] is None and 'auto_increment' not in r['Extra']]
    report=dict(status='PASS' if all(c['status']=='READY' for c in checks) else 'NOT_READY',
        checked_at_utc=datetime.now(UTC).isoformat(),read_only=True,enabled=policy['enabled'],
        profile_sha256=reference()['sha256'],model_batch_id=policy['model_batch_id'],
        model_horizon=protocol['horizon'],model_universe=len(protocol['universe']),signal_day=str(day),
        coverage=coverage_summary,
        strategy_profile=plan['strategy_profile'],accounts=checks,required_schema_columns=required,
        stages=[s for s in plan['steps'] if s['number'] in ('10','11','12')],
        other_accounts=plan['additional_account_workflows'],HTTP_methods=sorted(set(methods)),
        SQL_writes=0,orders=0,watchers_started=0,predictions_generated=0)
    (output/'readiness.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    engine.dispose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('stages','other_accounts')}
        | {'report_path':str((output/'readiness.json').resolve())},ensure_ascii=False,default=str),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('artifacts/operations/q051_paper_activation')/datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))
    parser.add_argument('--selection-run-id', help='Prévisualiser le sizing réel en lecture seule, sans publier de cibles')
    logging.basicConfig(level=logging.WARNING)
    args=parser.parse_args()
    result=run(args.output_dir,args.selection_run_id)
    raise SystemExit(0 if result['status']=='PASS' else 1)
