"""Reconciled supplier-assumed metrics, distinct from qualified 13B reporting."""
from decimal import Decimal
import numpy as np

def ledger_metrics(result: dict, *, data_kind: str) -> dict:
    """Metrics from a completed, reconciled LONG EUR ledger, never a partial one."""
    if data_kind not in {'EXPLORATORY_PROVIDER_ASSUMED'}:
        raise ValueError('Origine des données explicite requise')
    if result.get('status') != 'COMPLETED_EXPLORATORY_PROVIDER_ASSUMED':
        raise ValueError('Ledger bloqué/partiel : aucune performance calculable')
    initial = Decimal(str(result['initial_equity']))
    rows = result['ledger']['equity']
    if not rows or [r['session'] for r in rows] != sorted({r['session'] for r in rows}):
        raise ValueError('Courbe d’equity absente/dupliquée/non ordonnée')
    if rows[-1]['session'] > '2025-12-31':
        raise ValueError('Confirmation réservée')
    values = np.array([float(r['equity']) for r in rows])
    if initial <= 0 or not np.isfinite(values).all() or (values <= 0).any() \
            or any(float(r['market_value'])<0 or float(r['cash'])<0 for r in rows):
        raise ValueError('Equity positive finie requise')
    final = Decimal(str(rows[-1]['equity']))
    if final != Decimal(str(result['final_equity'])) or final-initial != Decimal(str(result['net_pnl'])):
        raise ValueError('PnL/equity non réconciliés')
    trades = result['ledger']['trades']
    if sum((Decimal(str(t['net_pnl'])) for t in trades), Decimal(0)) != final-initial:
        raise ValueError('Trades/equity non réconciliés')
    equity = np.r_[float(initial),values]
    returns = equity[1:]/equity[:-1]-1
    sigma = returns.std(ddof=1) if len(returns)>1 else 0
    orders = [r for r in result['ledger']['orders'] if r['side'] in ('BUY','SELL')]
    costs = {k:sum((Decimal(str(o[k])) for o in orders),Decimal(0)) for k in ('commission','spread','slippage','taxes')}
    if any(costs[k] != Decimal(str(result['costs'][k])) for k in costs):
        raise ValueError('Frais du ledger non réconciliés')
    exposure = np.array([float(r['market_value'])/float(r['equity']) for r in rows])
    dividends = sum((Decimal(str(m['amount'])) for m in result['ledger']['cash_movements']
                     if m['kind']=='DIVIDEND_PAYMENT'),Decimal(0))
    by_symbol = {}
    for t in trades:
        by_symbol[t['uid']] = by_symbol.get(t['uid'],Decimal(0))+Decimal(str(t['net_pnl']))
    by_semester = []
    previous = initial
    for semester in sorted({r['session'][:4]+'H'+('1' if int(r['session'][5:7])<=6 else '2') for r in rows}):
        group = [r for r in rows if r['session'][:4]+'H'+('1' if int(r['session'][5:7])<=6 else '2')==semester]
        end = Decimal(str(group[-1]['equity']))
        by_semester.append({'semester':semester,'net_pnl_eur':str(end-previous),
                            'net_return_pct':float((end/previous-1)*100),'sessions':len(group)})
        previous = end
    return {'data_kind':data_kind,'not_production_evidence':True,'net_pnl_eur':str(final-initial),
            'net_return_pct':float((final/initial-1)*100),
            'daily_sharpe':float(returns.mean()/sigma*np.sqrt(252)) if sigma>0 else None,
            'sharpe_convention':'sample_std_ddof1_rf0_252_sessions_including_initial_to_first_close',
            'max_drawdown_pct':float((1-equity/np.maximum.accumulate(equity)).max()*100),
            'mean_gross_exposure_pct':float(exposure.mean()*100),
            'mean_net_exposure_pct':float(exposure.mean()*100),
            'turnover':float(sum((Decimal(str(o['notional'])) for o in orders),Decimal(0)))/values.mean(),
            'turnover_convention':'two_way_notional_divided_by_mean_closing_equity_not_annualized',
            'executed_orders':len(orders),'closed_trades':len(trades),
            'win_rate':sum(Decimal(str(t['net_pnl']))>0 for t in trades)/len(trades) if trades else None,
            'costs_eur':{k:str(v) for k,v in costs.items()},'dividend_cashflows_eur':str(dividends),
            'by_symbol_net_pnl_eur':{k:str(v) for k,v in by_symbol.items()}, 'by_semester':by_semester,
            'serving_enabled':False,'economic_go_allowed':False}


