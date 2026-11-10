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
from common.us_signal_date import resolve_us_signal_date
from database.connection import get_sqlalchemy_engine
from service.forward_pit.us_pipeline import execute_pipeline
from service.q051_paper.pipeline import contract, make_broker
from service.q051_paper.risk import capture, complete_context


def run(output):
    policy = settings()
    day = resolve_us_signal_date(None)
    root, protocol = contract(policy['model_batch_id'], policy['artifacts_dir'], day)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,many):
        if statement.lstrip().split()[0].upper() not in ('SELECT','SHOW','SET','DESCRIBE'):
            raise ValueError('Q051 readiness: SQL read only')
    event.listen(engine,'before_cursor_execute',readonly)
    original = requests.Session.request
    methods = []
    def get_only(self,method,url,*args,**kwargs):
        if method.upper() != 'GET':
            raise ValueError('Q051 readiness: HTTP GET only')
        methods.append(method)
        return original(self,method,url,*args,**kwargs)
    from common.market_calendar import get_market_calendar
    session = next(s for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(day,day) if s.is_open)
    checks = []
    with patch.object(requests.Session,'request',get_only):
        plan = execute_pipeline(engine,load_batch_config()['us_pipeline'],'q051-readiness',True,
                                now=session.close_at_utc+timedelta(minutes=30)).details
        for account in [plan['account_id'],*plan['other_paper_accounts']]:
            repo, broker, cfg = make_broker(engine,account)
            try:
                context = capture(repo,broker,account,day,datetime.now(UTC))
                complete = complete_context(context,engine,protocol['universe'])
                qualified = complete['returns'].notna().all()
                missing_held = [p['symbol'] for p in context['positions'] if not qualified.get(p['symbol'],False)]
                checks.append(dict(account_id=account,broker_mode='paper',status='READY' if not missing_held else 'MISSING_HELD_COVARIANCE',
                    equity=context['equity'],buying_power=context['available_buying_power'],
                    positions=len(context['positions']),pending_entries=len(context['pending_entries']),
                    regime_allows_new_entries=context['regime_allowed'],qualified_covariance_symbols=int(qualified.sum()),
                    missing_held_covariance=missing_held))
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
        strategy_profile=plan['strategy_profile'],accounts=checks,required_schema_columns=required,
        stages=[s for s in plan['steps'] if s['number'] in ('10','11','12')],
        other_accounts=plan['additional_account_workflows'],HTTP_methods=sorted(set(methods)),
        SQL_writes=0,orders=0,watchers_started=0,predictions_generated=0)
    output.mkdir(parents=True,exist_ok=False)
    (output/'readiness.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    engine.dispose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('stages','other_accounts')}
        | {'report_path':str((output/'readiness.json').resolve())},ensure_ascii=False,default=str),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('artifacts/operations/q051_paper_activation')/datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))
    logging.basicConfig(level=logging.WARNING)
    result=run(parser.parse_args().output_dir)
    raise SystemExit(0 if result['status']=='PASS' else 1)
