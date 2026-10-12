"""Audit every completed grid trade and compare to the common reference offline."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_barrier_exit_grid import PROFILES
from modelFactory.oracle.build_labels import nyse_sessions


def verify_trade_contract(trades, tp, sl, calendar):
    if trades.empty:
        return dict(trades=0,expiry_exits=0,exceeding_stop_on_gap=0)
    required={'entry_price','replay_initial_stop_price','replay_take_profit_price','entry_date','exit_date','exit_reason','exit_price'}
    if not required.issubset(trades):
        raise ValueError(f'Missing trade audit columns {required-set(trades)}')
    if not np.isclose(trades.replay_initial_stop_price,trades.entry_price*(1-sl),atol=1e-7,rtol=1e-8).all():
        raise ValueError('Executed SL differs from requested profile')
    if not np.isclose(trades.replay_take_profit_price,trades.entry_price*(1+tp),atol=1e-7,rtol=1e-8).all():
        raise ValueError('Executed TP differs from requested profile')
    entry_idx=calendar.get_indexer(pd.to_datetime(trades.entry_date))
    exit_idx=calendar.get_indexer(pd.to_datetime(trades.exit_date))
    if (entry_idx<0).any() or (exit_idx<0).any():
        raise ValueError('Trade outside session calendar')
    holding=exit_idx-entry_idx
    if (holding<0).any() or (holding>20).any():
        raise ValueError('Trade held past the 21st-session open')
    expiry=trades.exit_reason.eq('expiry_open')
    if not (holding[expiry.to_numpy()]==20).all():
        raise ValueError('Expiry does not preserve entry chronology')
    # A gap can exceed the chosen stop. Count it, do not cap the realised loss.
    below_stop=trades.exit_price.lt(trades.replay_initial_stop_price-1e-7)
    return dict(trades=len(trades),expiry_exits=int(expiry.sum()),
                exceeding_stop_on_gap=int(below_stop.sum()))


def summarize(root):
    report=read(root/'report.json')
    if report['status'] not in ('COMPLETED','COMPLETED_WITH_RESERVES') \
            or not report.get('input_hashes_verified_after_all_runs'):
        raise ValueError('Grid not complete or not hash-verified')
    protocol = read(root/'protocol.json')
    inputs = Path(protocol['inputs'])
    if digest(inputs/'prepared.json') != protocol['prepared_sha256']:
        raise ValueError('Prepared input manifest changed')
    verify_hashes(inputs, read(inputs/'prepared.json')['files'])
    verify_hashes(Path('.'), protocol['source_hashes'])
    # Include the sector map, frozen models and raw feature/price evidence,
    # not only the final prepared parquet files read by the workers.
    source_hashes = read(inputs/'input-protocol.json')['source_hashes']
    verify_hashes(Path('.'), source_hashes)
    profiles={p[0]:(p[1],p[2]) for p in PROFILES}
    expected={(y,n,a,p) for y in (2025,2026) for n in (10,20,50)
        for a in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG') for p in profiles}
    actual={(r['year'],r['count'],r['arm'],r['profile']) for r in report['portfolios']}
    if actual!=expected or len(report['portfolios'])!=len(expected):
        raise ValueError('Missing or duplicated case')
    calendar=nyse_sessions(pd.Timestamp('2024-01-01').date(),pd.Timestamp('2026-10-07').date())
    checks,rows,paths=[],[],[root/'report.json',root/'protocol.json']
    for r in report['portfolios']:
        tp,sl=profiles[r['profile']]
        if r['tp_pct']!=tp or r['sl_pct']!=sl:
            raise ValueError('Profile metadata differs')
        if r['status']=='FAILED' or abs(r['cash_reconciliation_error'])>1e-6:
            raise ValueError('Unqualified failed/cash portfolio')
        output=Path(r['output'])
        trades=pd.read_parquet(output/'trades.parquet')
        checks.append(dict(year=r['year'],count=r['count'],arm=r['arm'],profile=r['profile'],
                           **verify_trade_contract(trades,tp,sl,calendar)))
        paths.extend([output/'trades.parquet',output/'daily.parquet'])
        rows.append(dict(year=r['year'],count=r['count'],arm=r['arm'],profile=r['profile'],
            tp_pct=tp,sl_pct=sl,return_pct=r['return_pct'],max_drawdown=r['max_drawdown'],
            calendar_return=r['periods']['calendar_mark_to_market_return'],
            status=r['status'],closed_positions=r['closed_positions'],
            margin_interest=r['margin_interest'],cash_error=r['cash_reconciliation_error']))
    table=pd.DataFrame(rows)
    reference=table.loc[table.profile.eq('REFERENCE_TP20_SL7'),['year','count','arm','return_pct']]
    reference=reference.rename(columns={'return_pct':'reference_return'})
    table=table.merge(reference,on=['year','count','arm'],validate='many_to_one')
    table['delta_vs_reference']=table.return_pct-table.reference_return
    # Exact baseline reproduction on the unaffected 2025 price/features input.
    original=read(Path('artifacts/research/us_oracle_barrier_comparison/compare-top10-20-50-20261012-v2')/'report.json')
    for old in original['portfolios']:
        if old['year']!=2025:
            continue
        match=table.loc[table.year.eq(2025)&table['count'].eq(old['count'])
                        &table.arm.eq(old['arm'])&table.profile.eq('REFERENCE_TP20_SL7')]
        if len(match)!=1 or abs(match.return_pct.iloc[0]-old['return_pct'])>1e-9:
            raise ValueError('2025 reference portfolio changed')
    pairs=[]
    lines=['# Grille TP/SL — comparaison auditée', '',
        '**LONG uniquement.** Même capital, coûts, risque et scores réparés pour toutes les variantes.',
        'Rendements des cohortes closes ; 2025 ajoute les dernières sorties de janvier 2026.',
        '2026 couvre les décisions jusqu’au 3 septembre, sorties jusqu’au 5 octobre.',
        'Tous les couples sont exploratoires ; aucun optimum déployable n’est déclaré.', '']
    for year in (2025,2026):
        lines.extend([f'## {year}', '', '| N | TP / SL | Ancien | Nouveau LONG | DD ancien | DD nouveau |',
                      '| ---: | --- | ---: | ---: | ---: | ---: |'])
        for n in (10,20,50):
            for name,tp,sl in PROFILES:
                group=table.loc[table.year.eq(year)&table['count'].eq(n)&table.profile.eq(name)].set_index('arm')
                old,new=group.loc['OLD_TERMINAL_LONG'],group.loc['NEW_BARRIER_LONG']
                pairs.append(dict(year=year,count=n,profile=name,old_return=float(old.return_pct),
                    new_return=float(new.return_pct),delta_new_vs_old=float(new.return_pct-old.return_pct)))
                lines.append(f'| {n} | {tp:.0%} / {sl:.0%} | {old.return_pct:+.2%} | {new.return_pct:+.2%} | '
                             f'{old.max_drawdown:.2%} | {new.max_drawdown:.2%} |')
        lines.append('')
    lines.extend(['## Contrôles', '',
        '72 cas présents, protections vérifiées sur chaque trade, expiry et cash contrôlés.',
        'Références 2025 identiques aux résultats précédents. Les scores 2025 sont inchangés.',
        'Les pertes sur gap ne sont pas artificiellement plafonnées au SL.',
        'Sizing ATR natif inchangé : les variantes n’ont pas un risque monétaire par trade égal.',
        'Secteurs actuels/non PIT et versions macro/screener non certifiées restent réservés.',
        'Pas de modèle entraîné, de SQL écrit ou de courtier contacté par cette grille.'])
    result=dict(status='ALL_CASES_AND_TRADE_CONTRACTS_VERIFIED',case_count=len(table),checks=checks,
        comparisons=pairs,rows=table.to_dict('records'),baseline_2025_reproduced=True,
        source_lineage_hashes_verified=True, source_lineage_hashes=source_hashes,
        max_cash_error=float(table.cash_error.abs().max()),
        complete_wealth=all(r['account_wealth_complete'] for r in report['portfolios']),
        sources={str(p):digest(p) for p in paths},no_model_promotion=True)
    atomic_json(root/'summary.json',result)
    (root/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(result['status'],len(table),'cases; cash max',result['max_cash_error'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    summarize(args.root)
