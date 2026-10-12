"""Independent offline check: trailing exits use a prior observed peak, never today's high."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read


def lot_path(trade, prices, actions):
    entry, exit_day = pd.Timestamp(trade.entry_date), pd.Timestamp(trade.exit_date)
    def symbol_frame(symbol):
        if isinstance(prices,dict):
            if symbol not in prices:
                raise ValueError(f'Missing held symbol {symbol}')
            return prices[symbol]
        return prices.loc[prices.symbol.eq(symbol)]
    own=symbol_frame(trade.symbol)
    path = own.loc[own.date.between(entry,exit_day)].copy()
    conversions = [a for a in actions if a.get('status')=='CONVERTED' and a['target']==trade.symbol
                   and pd.Timestamp(a['preserved_entry_date'])==entry and pd.Timestamp(a['day'])<=exit_day]
    if len(conversions)>1:
        raise ValueError('Ambiguous corporate-action lot lineage')
    if conversions:
        event=conversions[0]
        predecessor=symbol_frame(event['source'])
        before=predecessor.loc[predecessor.date.ge(entry)
                              &predecessor.date.lt(pd.Timestamp(event['day']))].copy()
        for field in ('open','high','low'):
            before[field]=before[field]/float(event['ratio'])
        path=pd.concat([before,path.loc[path.date.ge(pd.Timestamp(event['day']))]],ignore_index=True)
    path=path.sort_values('date').set_index('date')
    if path.index.has_duplicates or path.empty or path.index[0]!=entry or path.index[-1]!=exit_day:
        raise ValueError('Missing/duplicated held price path')
    if not np.isfinite(path[['open','high','low']].to_numpy()).all():
        raise ValueError('Nonfinite observed held prices')
    return path


def audit_trailing_paths(trades, prices, actions=()):
    trailing=trades.loc[trades.exit_reason.astype(str).str.startswith('trailing_stop')]
    results=[]
    for trade in trailing.itertuples():
        path=lot_path(trade,prices,actions)
        history=path.iloc[:-1]
        # Same-day high is intentionally absent from both activation and peak.
        if history.empty:
            raise ValueError('Trailing used entry-day/future high')
        trigger=history.high.ge(trade.replay_trailing_activation_price)
        if not trigger.any():
            raise ValueError('Trailing exited before qualified activation')
        peak=max(float(trade.entry_price),float(history.high.max()))
        stop=peak*(1-float(trade.replay_trailing_stop_pct))
        if stop+1e-7<trade.replay_initial_stop_price:
            raise ValueError('Active trailing loosened SL')
        opening,low=float(path.open.iloc[-1]),float(path.low.iloc[-1])
        if trade.exit_reason=='trailing_stop_gap_open':
            if opening>stop+1e-7 or not np.isclose(trade.exit_price,opening,rtol=1e-8,atol=1e-7):
                raise ValueError('Wrong gap trailing fill')
        elif trade.exit_reason=='trailing_stop':
            if opening<=stop-1e-7 or low>stop+1e-7 \
                    or not np.isclose(trade.exit_price,stop,rtol=1e-8,atol=1e-7):
                raise ValueError('Wrong intraday/prior-peak trailing fill')
        else:
            raise ValueError('Unknown trailing exit convention')
        results.append(dict(symbol=trade.symbol,entry_date=trade.entry_date,exit_date=trade.exit_date,
            exit_reason=trade.exit_reason,activation_observed_date=history.index[trigger][0],
            prior_peak=peak,working_stop=stop,initial_stop=trade.replay_initial_stop_price,
            opening=opening,exit_price=trade.exit_price))
    return results


def run(root):
    protocol,report=read(root/'protocol.json'),read(root/'report.json')
    if report['status'] not in ('COMPLETED','COMPLETED_WITH_RESERVES') \
            or not report['trade_contracts_audited'] or not report['input_hashes_verified']:
        raise ValueError('Campaign not complete and contract-audited')
    inputs=Path(protocol['inputs'])
    if digest(inputs/'prepared.json')!=protocol['prepared_sha256']:
        raise ValueError('Prepared input manifest changed')
    verify_hashes(inputs,read(inputs/'prepared.json')['files'])
    verify_hashes(Path('.'),protocol['source_hashes'])
    verify_hashes(Path('.'),read(root/'summary.json')['sources'])
    frame=pd.read_parquet(inputs/'prices.parquet',columns=['date','symbol','open','high','low'])
    prices={symbol:g for symbol,g in frame.groupby('symbol',sort=False)}
    checks,sources=[],{}
    for case in report['portfolios']:
        if case['trailing_pct'] is None:
            continue
        folder=Path(case['output'])
        trades=pd.read_parquet(folder/'trades.parquet')
        paths=audit_trailing_paths(trades,prices,read(folder/'corporate-actions.json'))
        cash_error=float(case['cash_reconciliation_error'])
        if abs(cash_error)>1e-6:
            raise ValueError('Cash discrepancy')
        checks.append(dict(year=case['year'],count=case['count'],arm=case['arm'],
            trailing_pct=case['trailing_pct'],trades=len(trades),audited_trailing_exits=len(paths),
            cash_error=cash_error,paths=paths))
        for name in ('trades.parquet','corporate-actions.json'):
            path=folder/name
            sources[str(path)]=digest(path)
    result=dict(status='PRIOR_PEAK_AND_GAP_FILLS_VERIFIED',cases=len(checks),checks=checks,
        trailing_exits=sum(c['audited_trailing_exits'] for c in checks),sources=sources,
        max_cash_error=max(abs(c['cash_error']) for c in checks),
        complete_wealth=all(c['account_wealth_complete'] for c in report['portfolios']),
        audit_source_sha256=digest(Path(__file__)))
    atomic_json(root/'trailing-price-audit.json',result)
    (root/'trailing-price-audit.md').write_text(
        '# Contrôle indépendant des sorties trailing\n\n'
        f'{result["cases"]} portefeuilles, {result["trailing_exits"]} sorties trailing vérifiées.\n'
        'Activation observée avant la sortie ; sommet des séances précédentes ; '
        'SL initial jamais relâché ; gap au prix d’ouverture et stop intraday au niveau causal.\n'
        'Ce contrôle ne certifie ni le PIT fournisseur ni une exécution intraday réelle.\n',encoding='utf-8')
    print(result['status'],result['cases'],'portfolios;',result['trailing_exits'],'exits')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    run(args.root)
