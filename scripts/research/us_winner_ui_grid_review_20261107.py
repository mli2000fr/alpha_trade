"""Explain the frozen UI sweep; no new simulation, fit or data collection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from scripts.research.us_winner_ui_grid_20261107 import ROOT,read,digest,atomic_json


def recommend(frame,reference_return):
    valid=frame.loc[frame.return_pct.notna() & frame.name.ne('REFERENCE') & frame.closed_lot_trades.ge(30)].copy()
    valid=valid.loc[valid.return_pct.gt(0)]
    if valid.empty:
        return []
    valid['dominated']=[bool(((valid.return_pct>=r.return_pct)&(valid.max_drawdown_pct>=r.max_drawdown_pct)&
        ((valid.return_pct>r.return_pct)|(valid.max_drawdown_pct>r.max_drawdown_pct))).any()) for r in valid.itertuples()]
    valid=valid.loc[~valid.dominated].copy()
    # Fixed before reading grid results. It is a descriptive trade-off, not a
    # forecast probability or an optimization objective for future production.
    valid['balanced_score']=valid.return_pct/valid.max_drawdown_pct.abs().clip(lower=5.)
    choices=[]
    orders=[('COMPROMIS_RENDEMENT_DD',['balanced_score','return_pct','name'],[False,False,True]),
            ('RENDEMENT_MAXIMAL',['return_pct','max_drawdown_pct','name'],[False,False,True]),
            ('DD_REDUIT_RENDEMENT_AU_MOINS_REFERENCE',['max_drawdown_pct','return_pct','name'],[False,False,True])]
    used=set()
    for label,columns,directions in orders:
        candidates=valid
        if label.startswith('DD_'):
            candidates=candidates[candidates.return_pct.ge(reference_return)]
        candidates=candidates[~candidates.name.isin(used)].sort_values(columns,ascending=directions)
        if not candidates.empty:
            choice={k:(None if pd.isna(v) else v.item() if isinstance(v,np.generic) else v)
                    for k,v in candidates.iloc[0].to_dict().items()}
            choice['recommendation']=label
            choices.append(choice);used.add(choice['name'])
    return choices


def configuration_signature(conf):
    flattened={f'selection.{k}':v for k,v in conf['selection'].items()}
    flattened.update({f'policy.{k}':v for k,v in conf['policy'].items()})
    flattened.update({f'risk.{k}':v for k,v in conf['risk'].items()
        if k not in ('fixed_stop_pct','force_close_on_breaker','max_long_positions')})
    flattened.update(controller=conf['controller'],daily_entry=conf['daily_entry'])
    return {k:json.dumps(v,sort_keys=True) for k,v in flattened.items()}


def neighbor_statistics(root,reports,name):
    chosen=configuration_signature(read(root/'cases'/name/'configuration.json'))
    found={}
    for key,report in reports.items():
        path=root/'cases'/key/'configuration.json'
        if report['status']=='FAILED' or not path.exists():continue
        signature=configuration_signature(read(path))
        changes=[k for k in chosen if signature.get(k)!=chosen[k]]
        if len(changes)!=1:continue
        identity=json.dumps(signature,sort_keys=True)
        found.setdefault(identity,dict(name=key,changed=changes[0],return_pct=report['return_pct'],
            max_drawdown_pct=report['max_drawdown_pct'],trades=report['closed_lot_trades']))
    rows=list(found.values())
    return dict(distinct_immediate_neighbors=len(rows),
        positive_fraction=sum(r['return_pct']>0 for r in rows)/len(rows) if rows else None,
        median_return_pct=float(np.median([r['return_pct'] for r in rows])) if rows else None,
        worst_return_pct=min(r['return_pct'] for r in rows) if rows else None,
        worst_drawdown_pct=min(r['max_drawdown_pct'] for r in rows) if rows else None,cases=rows)


def concentration(root,name):
    trades=pd.read_csv(root/'cases'/name/'trades.csv')
    wins=trades.loc[trades.pnl.gt(0),'pnl'].sort_values(ascending=False)
    total=float(wins.sum())
    return dict(gross_winning_pnl=total,top_trade_share_of_gross_wins=float(wins.head(1).sum()/total) if total else None,
        top3_trade_share_of_gross_wins=float(wins.head(3).sum()/total) if total else None,
        realized_symbol_count=int(trades.symbol.nunique()))


def review(root,partial=False):
    plan=read(root/'protocol.json')
    reports={p.parent.name:read(p) for p in (root/'cases').glob('*/report.json')}
    if not partial and len(reports)!=len(plan['cases']):
        raise ValueError('Grid unfinished; use --partial for a clearly marked provisional review')
    frame=pd.read_csv(root/'comparison.csv')
    choices=recommend(frame,reports['REFERENCE']['return_pct'])
    label='PARTIAL_EXPLORATORY' if len(reports)!=len(plan['cases']) else 'COMPLETED_EXPLORATORY'
    output=root/('review-partial' if label.startswith('PARTIAL') else 'review')
    output.mkdir(exist_ok=True)
    for choice in choices:
        report=reports[choice['name']]
        choice['quarters']=report['quarters']
        choice['configuration']=read(root/'cases'/choice['name']/'configuration.json')
        choice['coverage_status']=report['status']
        choice['neighbors']=neighbor_statistics(root,reports,choice['name'])
        choice['concentration']=concentration(root,choice['name'])
    pd.DataFrame([{k:v for k,v in c.items() if k not in ('configuration','quarters','neighbors','concentration')}
                  for c in choices]).to_csv(output/'recommendations.csv',index=False)
    summary=dict(status=label,reference_run=plan['reference_run'],batch_id=plan['batch_id'],period=[plan['start'],plan['end']],
        completed=len(reports),total=len(plan['cases']),failed=[k for k,v in reports.items() if v['status']=='FAILED'],
        criteria='Positive return; >=30 closed trades; Pareto; balanced return/max(5,abs DD). '
                 'Then distinct maximum-return and smaller-DD cases with return>=reference.',
        independent_holdout=False,production_changed=False,choices=choices,
        sources={str(root/'protocol.json'):digest(root/'protocol.json'),str(root/'comparison.csv'):digest(root/'comparison.csv'),
                 str(Path(__file__)):digest(__file__)})
    atomic_json(output/'report.json',summary)
    lines=['# Comparaison Winner — paramètres IHM', '',
        f"Statut : **{label}**, {len(reports)}/{len(plan['cases'])} cas. Année 2025, même batch, capital 4 000 $, levier autorisé 2×.",
        '', 'Résultats exploratoires : optimisation sur une année déjà consultée, protections parfois sur OHLC daily. '
        'Aucune validation indépendante ni modification de production.', '',
        '| Cas | Capital final | Rendement | DD max | Gagnants | Trades | Capital engagé moyen | Exposition moyenne |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name in ['REFERENCE',*[c['name'] for c in choices]]:
        r=reports[name]
        lines.append(f"| {name} | {r['final_equity']:.2f} $ | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | "
            f"{r['win_pct']:.2f} % | {r['closed_lot_trades']} | {r['average_gross_capital']:.2f} $ | {100*r['average_gross_equity_ratio']:.2f} % |")
    for c in choices:
        conf=c['configuration'];sel=conf['selection'];risk=conf['risk'];wp=conf['policy']
        lines += ['',f"## {c['name']} — {c['recommendation']}", '',
            f"TOP Oracle : {sel['oracle_top_n']} titres ({100*sel['oracle_top_n']/1790:.2f} % de l'univers), "
            f"puis TOP{sel['long_top_n']} LONG ; score strict > {sel['min_long_probability']}, AUC minimale {sel['min_long_auc']}.",
            f"Budget de risque : {100*risk['risk_per_trade_pct']:.2f} % ; poids maximal : {100*risk['max_position_weight']:.2f} % ; "
            f"{risk['max_positions']} positions ; minimum {risk['min_position_notional']:.2f} $.",
            f"SL {100*wp['stop_loss_pct']:.2f} % ; TP {wp['take_profit_pct']} ; trailing {wp['trailing_stop_pct']} ; "
            f"horizon {wp['horizon_sessions']} séances ; fraction initiale {wp['initial_position_fraction']} ; "
            f"renforcement {wp['reinforcement_enabled']} ; contrôleur {conf['controller']} ; entrée journalière {conf['daily_entry']}.",
            f"Voisins distincts ne différant que par un contrôle : {c['neighbors']['distinct_immediate_neighbors']}. "
            f"Fraction positive : {c['neighbors']['positive_fraction']}. "
            f"Part des trois meilleurs trades dans les gains bruts : {c['concentration']['top3_trade_share_of_gross_wins']}."]
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if choices:
        import os
        cache=output/'.matplotlib';cache.mkdir(exist_ok=True);os.environ['MPLCONFIGDIR']=str(cache.resolve())
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,gridspec_kw={'height_ratios':[2,1]})
        for name in ['REFERENCE',*[c['name'] for c in choices]]:
            curve=pd.read_parquet(root/'cases'/name/'equity-5m.parquet')
            dates=pd.to_datetime(curve.timestamp,utc=True)
            eq=curve.equity.to_numpy(float)
            peak=np.maximum.accumulate(np.r_[4000.,eq])[1:]
            axes[0].plot(dates,eq,label=name,lw=1.4)
            axes[1].plot(dates,100*(eq/peak-1),label=name,lw=1.1)
        axes[0].set_ylabel('Capital valorisé ($)');axes[1].set_ylabel('Drawdown (%)')
        axes[0].legend(ncol=2);axes[0].set_title('2025 — comparaison exploratoire, même modèle et même bande de prix')
        for ax in axes:ax.grid(alpha=.25)
        fig.tight_layout();fig.savefig(output/'capital-drawdown.png',dpi=150);plt.close(fig)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--partial',action='store_true')
    parser.add_argument('--wait',action='store_true',help='Finish the same experiment after its running simulations complete')
    args=parser.parse_args()
    if args.wait:
        while not (args.root/'report.json').exists():
            progress=read(args.root/'progress.json')
            if progress.get('status')=='FAILED':
                raise RuntimeError('Financial sweep failed: '+str(progress.get('error')))
            active={}
            for path in (args.root/'cases').glob('*/progress.json'):
                try:
                    payload=read(path)
                    if payload.get('status')=='RUNNING':active[path.parent.name]=payload
                except (OSError,ValueError):pass
            complete=list((args.root/'cases').glob('*/report.json'))
            atomic_json(args.root/'live-status.json',dict(status='RUNNING',completed=len(complete),total=269,
                active_cases=active,updated_at_utc=pd.Timestamp.now(tz='UTC').isoformat()))
            time.sleep(30)
    result=review(args.root,args.partial)
    atomic_json(args.root/'live-status.json',dict(status=result['status'],completed=result['completed'],
        total=result['total'],review='review/summary.md',choices=[c['name'] for c in result['choices']]))
    print(json.dumps(dict(status=result['status'],completed=result['completed'],total=result['total'],
        choices=[c['name'] for c in result['choices']]),indent=2))
