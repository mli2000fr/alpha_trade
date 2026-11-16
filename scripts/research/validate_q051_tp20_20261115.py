"""Independent reconciliation of the completed TP20 counterfactual files."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_vol20_regime_tp20/20261115-v1')
BASE=Path('artifacts/research/us_q051_global_rank_h10/20261115-v1/cases/Q051_REFERENCE')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def validate(root=ROOT):
    root=Path(root);out=root/'result';r=read(out/'report.json');plan=read(root/'protocol.json')
    if read(root/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Run not complete')
    isolation=read(root/'isolation.json')
    if isolation['status']!='COMPLETED' or isolation.get('violations'):raise ValueError('Isolation not clean')
    before=read(BASE/'result/configuration.json')['portfolio']
    after=read(out/'configuration.json')['portfolio']
    before['exec_config']['winner_pyramiding']['take_profit_pct']=.20
    if before!=after:raise ValueError('Difference outside TP20')
    for file,sha in plan['sources'].items():
        if digest(Path(file))!=sha:raise ValueError('Changed source: '+file)
    if r['SQL_writes'] or r['provider_calls'] or r['orders']:raise ValueError('External side effects')
    trades=pd.read_csv(out/'trades.csv');curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
    marks=pd.read_parquet(out/'equity-5m.parquet');annual=pd.read_csv(out/'annual-summary.csv')
    if len(curve)!=1443 or not np.isclose(curve.iloc[-1],r['final_equity'],atol=1e-7):raise ValueError('Wrong final curve')
    values=pd.concat([pd.Series([4000.]),marks.equity],ignore_index=True)
    dd=100*(values/values.cummax()-1).min()
    checks=[(100*(curve.iloc[-1]/4000.-1),r['return_pct']), (dd,r['max_drawdown_pct']),
        (marks.gross.mean(),r['average_gross_capital']),((marks.gross/marks.equity).mean(),r['average_gross_equity_ratio']),
        (4000.*np.prod(1+annual.return_pct/100),r['final_equity'])]
    if not all(np.isclose(a,b,rtol=1e-10,atol=1e-6) for a,b in checks):raise ValueError('Capital/risk reconciliation failed')
    if len(trades)!=r['closed_lot_trades'] or int(trades.pnl.gt(0).sum())!=r['winners'] or int(trades.pnl.lt(0).sum())!=r['losers']:
        raise ValueError('Trade counts mismatch')
    expected=(trades.quantity*(trades.exit_price-trades.entry_price)-trades.entry_fees-trades.exit_fees+trades.dividends)
    if not np.allclose(expected,trades.pnl,rtol=1e-10,atol=1e-7):raise ValueError('Net trade PnL mismatch')
    if not np.allclose(trades.pnl/(trades.quantity*trades.entry_price),trades.return_pct,atol=1e-10):raise ValueError('Net return mismatch')
    tp=trades[trades.exit_reason.str.startswith('TP')]
    if tp.empty:raise ValueError('No effective TP exit; cannot certify connection')
    limits=tp.entry_price.map(lambda p:round(float(p)*1.2,2))
    if not tp.exit_price.ge(limits-1e-8).all():raise ValueError('TP sold below configured limit')
    events=pd.read_csv(out/'events.csv');fees=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
    if not np.isclose(fees,r['costs'],atol=1e-7):raise ValueError('Execution fees do not reconcile')
    imported=read(root/'ihm.json')['run_id']
    ui=read(Path('artifacts/ihm_backtesting_runs/run')/imported/'artifacts/report.json')
    for u,v in [('final_value','final_equity'),('total_return_pct','return_pct'),('win_rate_pct','win_pct')]:
        if not np.isclose(ui['summary'][u],r[v],atol=1e-7):raise ValueError('IHM mismatch')
    result=dict(status='PASS',sole_delta='take_profit_pct null -> .20',sessions=len(curve),
        trades=len(trades),tp_exits=len(tp),exit_reasons=trades.exit_reason.value_counts().to_dict(),
        final_equity=r['final_equity'],return_pct=r['return_pct'],max_drawdown_pct=r['max_drawdown_pct'],
        win_pct=r['win_pct'],fees_reconciled=float(fees),capital_and_annual_compounding=True,
        average_gross_capital=r['average_gross_capital'],average_gross_equity_ratio=r['average_gross_equity_ratio'],
        IHM=imported,SQL_writes=0,orders=0,provider_calls=0)
    atomic_json(root/'validation-independent.json',result)
    return result


if __name__=='__main__':print(json.dumps(validate(),ensure_ascii=False))
