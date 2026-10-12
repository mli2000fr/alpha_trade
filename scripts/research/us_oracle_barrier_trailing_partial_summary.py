"""Audit finished trailing cases WITHOUT concealing failed portfolios or completing their PnL."""
import argparse
from pathlib import Path

import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_barrier_trailing_grid import verify_baseline, validate_trailing_contract, require_long_trades
from scripts.research.us_oracle_barrier_trailing_audit import audit_trailing_paths


def run(root):
    protocol,report=read(root/'protocol.json'),read(root/'report.json')
    if report['status'] not in ('PARTIAL_FAILED','COMPLETED','COMPLETED_WITH_RESERVES') \
            or not report['input_hashes_verified']:
        raise ValueError('Campaign still running or not hash-verified')
    inputs,baseline=Path(protocol['inputs']),Path(protocol['baseline'])
    if digest(inputs/'prepared.json')!=protocol['prepared_sha256']:
        raise ValueError('Input manifest changed')
    verify_hashes(inputs,read(inputs/'prepared.json')['files'])
    verify_hashes(Path('.'),protocol['source_hashes'])
    verify_hashes(Path('.'),read(inputs/'input-protocol.json')['source_hashes'])
    base=verify_baseline(inputs,baseline)
    off={(r['year'],r['count'],r['arm'],r['profile']):r for r in base['portfolios']}
    actual=[(r['year'],r['count'],r['arm'],r['profile'],r['tp_pct'],r['sl_pct'],r['trailing_pct'])
            for r in report['portfolios']]
    if set(actual)!=set(map(tuple,protocol['cases'])) or len(actual)!=len(protocol['cases']):
        raise ValueError('Incomplete/duplicated case inventory')
    frame=pd.read_parquet(inputs/'prices.parquet',columns=['date','symbol','open','high','low'])
    prices={s:g for s,g in frame.groupby('symbol',sort=False)}
    calendar=nyse_sessions(pd.Timestamp('2024-01-01').date(),pd.Timestamp('2026-10-07').date())
    rows,failed,checks,sources=[],[],[],{}
    for r in sorted(report['portfolios'],key=lambda r:(r['year'],r['count'],r['arm'],r['trailing_pct'])):
        if r['status']!='COMPLETED':
            failed.append(r)
            continue
        if not r['account_wealth_complete'] or abs(r['cash_reconciliation_error'])>1e-6:
            raise ValueError('Unqualified account/cash')
        folder=Path(r['output'])
        trades=pd.read_parquet(folder/'trades.parquet')
        require_long_trades(trades)
        contract=validate_trailing_contract(trades,r['tp_pct'],r['sl_pct'],r['trailing_pct'],calendar)
        paths=audit_trailing_paths(trades,prices,read(folder/'corporate-actions.json'))
        checks.append(dict(year=r['year'],count=r['count'],arm=r['arm'],trailing_pct=r['trailing_pct'],
            **contract,paths=paths,cash_error=r['cash_reconciliation_error']))
        b=off[(r['year'],r['count'],r['arm'],r['profile'])]
        rows.append(dict(year=r['year'],count=r['count'],arm=r['arm'],trailing_pct=r['trailing_pct'],
            return_pct=r['return_pct'],off_return=b['return_pct'],delta_return=r['return_pct']-b['return_pct'],
            max_drawdown=r['max_drawdown'],off_max_drawdown=b['max_drawdown'],
            delta_drawdown=r['max_drawdown']-b['max_drawdown'],
            closed_positions=r['closed_positions'],trailing_exits=contract.get('trailing_exits',0)))
        for name in ('trades.parquet','daily.parquet','corporate-actions.json'):
            path=folder/name
            sources[str(path)]=digest(path)
    result=dict(status='PARTIAL_VERIFIED' if failed else 'ALL_VERIFIED',complete=len(rows),failed=len(failed),
        expected=len(protocol['cases']),rows=rows,failures=failed,checks=checks,sources=sources,
        audited_trades=sum(c['trades'] for c in checks),audited_trailing_exits=sum(c.get('trailing_exits',0) for c in checks),
        max_cash_error=max(abs(c['cash_error']) for c in checks),
        comparisons_do_not_include_failed_portfolios=True,promotion=False,
        code_sha256={str(p):digest(p) for p in [Path(__file__),Path('scripts/research/us_oracle_barrier_trailing_audit.py')]})
    verify_hashes(Path('.'),protocol['source_hashes'])
    verify_hashes(Path('.'),sources)
    atomic_json(root/'partial-summary.json',result)
    lines=['# Trailing TP20 / SL10 — résultats vérifiés, campagne partielle', '',
        f'**{len(rows)} portefeuilles vérifiés sur {len(protocol["cases"])} ; {len(failed)} non terminé(s).**',
        'Le PnL incomplet du cas échoué n’est ni publié ni ajouté aux comparaisons.',
        'LONG uniquement, 4 000 USD par cas annuel. Décisions 2026 jusqu’au 03/09.',
        'Rendements des cohortes closes, après coûts ; même convention quotidienne conservative.', '',
        '| Année | N | Modèle | Trail | OFF | Avec | Delta pp | DD OFF | DD avec |',
        '| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f'| {r["year"]} | {r["count"]} | {r["arm"]} | {r["trailing_pct"]:.0%} | '
            f'{r["off_return"]:+.2%} | {r["return_pct"]:+.2%} | {r["delta_return"]*100:+.2f} | '
            f'{r["off_max_drawdown"]:.2%} | {r["max_drawdown"]:.2%} |')
    lines.extend(['','## Cas non qualifiés',''])
    for r in failed:
        lines.append(f'- {r["year"]}, TOP{r["count"]}, {r["arm"]}, trailing {r["trailing_pct"]:.0%} : '
                     f'{r.get("failures",r.get("error"))}.')
    lines.extend(['','Tous les rendements restent exploratoires, sans optimum validé ou promotion live.',
        f'{result["audited_trades"]} transactions, {result["audited_trailing_exits"]} sorties trailing '
        'contrôlées contre le sommet antérieur, le stop initial et le prix de gap.'])
    (root/'partial-summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(result['status'],len(rows),'complete;',len(failed),'failed;',result['audited_trailing_exits'],'trailing exits')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    run(args.root)
