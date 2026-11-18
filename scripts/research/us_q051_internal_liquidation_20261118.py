"""Frozen B / anti-SL replay: liquidate on ON, trade with vol20+SPY until OFF."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import json
import shutil
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_b_early_sl_20261116 as source
from scripts.research import us_q051_internal_protection_20261117 as previous
from scripts.research.us_q051_internal_liquidation_policy_20261118 import ProtectedEntries,InternalLiquidation,internal_states
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_internal_liquidation/20261118-v1')
SOURCE=source.ROOT
DOC=Path('doc/ml/q051_internal_liquidation_20261118.md')
CASES=previous.CASES
LABELS={'CONTROL':'B témoin','SL10':'B + anti-SL témoin',
    'B_RATE':'B — liquidation / vol20+régime / sortie taux',
    'B_SHADOW':'B — liquidation / vol20+régime / sortie témoin+5%',
    'SL10_RATE':'B + anti-SL — liquidation / vol20+régime / sortie taux',
    'SL10_SHADOW':'B + anti-SL — liquidation / vol20+régime / sortie témoin+5%'}
read=source.read


def prepare():
    if (ROOT/'protocol.json').exists():
        plan=read(ROOT/'protocol.json')
        for name,h in plan['sources'].items():
            if digest(Path(name))!=h:raise ValueError('Changed frozen source '+name)
        return plan
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    ROOT.mkdir(parents=True,exist_ok=True);old=read(source.ROOT/'protocol.json');sources={};changes=[]
    # The preceding native anti-SL UI work touched these serving/training files.
    # This experiment consumes frozen selections, not those prediction paths.
    # Two fresh baseline replays must nevertheless reproduce the archived books.
    explainable={'backtesting/per_symbol_selection.py','backtesting/winner_campaign_replay.py',
        'modelFactory/oracle_path/directional.py','modelFactory/oracle_path/predict.py','modelFactory/oracle_path/train.py'}
    for name,h in old['sources'].items():
        current=digest(Path(name))
        if current!=h:
            if name.replace('\\','/') not in explainable:raise ValueError('Unexpected changed source '+name)
            changes.append(dict(file=name,archived=h,current=current,reason='Native anti-SL integration; frozen selections reused; matched controls required'))
        sources[name]=current
    for name in ['selection-validation.json','oracle-oof-causality.json']:
        if read(source.ROOT/name)['status']!='PASS':raise ValueError('Original inputs not qualified')
    for key in ['CONTROL','SL10']:validate_case(source.ROOT/'cases'/key)
    inputs=ROOT/'inputs';tape=inputs/'intraday';tape.mkdir(parents=True,exist_ok=True)
    market=read(source.ROOT/'inputs/manifest.json')
    for name,h in market['files'].items():
        if digest(Path(name))!=h:raise ValueError('Changed market input '+name)
    for file in (source.ROOT/'inputs/intraday').iterdir():
        if file.is_file():shutil.copyfile(file,tape/file.name)
    atomic_json(inputs/'manifest.json',market)
    rates_path=previous.AUDIT/'PER_B10-timeline.parquet';rates=pd.read_parquet(rates_path);sources[str(rates_path)]=digest(rates_path)
    states_paths={}
    for case in LABELS:
        family=CASES[case]['family'] if case in CASES else ('B' if case=='CONTROL' else 'SL10')
        origin='CONTROL' if family=='B' else 'SL10'
        folder=ROOT/'variants'/case;folder.mkdir(parents=True,exist_ok=True)
        src=source.ROOT/'variants'/origin/'signals.parquet';dst=folder/'signals.parquet'
        shutil.copyfile(src,dst);sources[str(dst)]=digest(dst)
        if digest(src)!=digest(dst):raise ValueError('Signal set changed')
        if case not in CASES:continue
        equity_path=source.ROOT/'cases'/origin/'result/equity-daily.csv'
        equity=pd.read_csv(equity_path,index_col=0,parse_dates=True).equity
        states=internal_states(rates,equity,CASES[case]['mode'])
        pd.testing.assert_frame_equal(states,pd.read_parquet(previous.ROOT/'inputs'/(case+'-states.parquet')))
        for cut in ['2022-12-30','2024-11-29','2025-05-30']:
            pd.testing.assert_frame_equal(states.loc[:cut],internal_states(rates.loc[:cut],equity.loc[:cut],CASES[case]['mode']))
        target=inputs/(case+'-states.parquet');states.to_parquet(target);sources[str(target)]=digest(target)
        sources[str(equity_path)]=digest(equity_path);states_paths[case]=str(target)
    for file in [Path(__file__),Path('scripts/research/us_q051_internal_liquidation_policy_20261118.py'),
            Path('tests/test_q051_internal_liquidation.py'),source.ROOT/'protocol.json',previous.ROOT/'protocol.json',
            source.ROOT/'post-run-review.json',source.ROOT/'selection-validation.json',source.ROOT/'oracle-oof-causality.json']:
        sources[str(file)]=digest(file)
    cfg=source.base.shared.configuration(old['reference_settings'],source.base.shared.CASES['Q051_050'])
    if json.loads(json.dumps(asdict(cfg),default=str))!=read(source.ROOT/'cases/CONTROL/result/configuration.json')['portfolio']:
        raise ValueError('Base portfolio differs')
    plan=deepcopy(old);plan.update(sources=sources,states=states_paths,cases=CASES,legacy_source_changes=changes,
        study='Internal ON: full next-open liquidation then vol20 + SPY200 until OFF',
        activation='same frozen PER_B10 rate, 20 matured sessions vs prior120, drop>5pp for3closes',
        recovery_A='same rate >= frozen activation reference-2pp for5closes',
        recovery_B='same continuous unprotected family shadow account return20>5% for5closes',
        quantity_policy='native full quantity, portfolio vol target20/covariance60 only while active',
        held_positions='Full liquidation once per ON, next official open after standing stops/open11; later holdings SL5/open11 unchanged',
        protected_regime='SPY prior close > .98*SMA200; no extra cash waiting session',
        same_open_reentry='Allowed after complete liquidation if existing candidates, regime and native limits pass',
        deactivation='Disable vol20 and regime for next-session new entries; keep held SL/open11',
        start='2021-01-01',end='2026-10-01',new_training=0,new_labels=0,recalibrations=0,
        SQL_reads=0,SQL_writes=0,provider_calls=0,orders=0,production_changes=False,
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'preflight.json',dict(status='PASS',signals_identical=True,states_identical=True,
        prefix_state_checks=12,legacy_source_changes=changes,matched_baselines_required=True))
    atomic_json(ROOT/'progress.json',dict(status='READY',completed=0,total=6))
    return plan


def protected_run(original,out,states):
    def run(engine,*args,**kwargs):
        from backtesting import winner_global_liquidation as native
        if any(kwargs.get(k) is not None for k in ['winner_selection_source','winner_entry_risk_policy']):
            raise ValueError('Existing research callback would be overwritten')
        policy=ProtectedEntries(states,kwargs['close']);liquidator=InternalLiquidation(states)
        kwargs.update(winner_selection_source=policy.select,winner_entry_risk_policy=policy)
        with patch.object(native,'GlobalLiquidation',lambda *args:liquidator):result=original(engine,*args,**kwargs)
        states.loc['2020-12-31':'2026-09-30'].to_csv(out/'internal-protection-timeline.csv')
        pd.DataFrame(policy.receipts).to_csv(out/'regime-state-decisions.csv',index=False)
        pd.DataFrame(policy.gate.receipts).to_csv(out/'protected-regime-decisions.csv',index=False)
        pd.DataFrame(policy.budget.receipts).to_csv(out/'protected-volatility-decisions.csv',index=False)
        atomic_json(out/'internal-liquidations.json',dict(events=liquidator.events,pending=liquidator.pending,
            drawdown_controller=False,half_size=False,vol_target=.20,covariance_sessions=60,SPY_SMA=200,SPY_threshold=.98))
        return result
    return run


def run_case(case):
    from backtesting.simulator import BacktestEngine
    if case not in LABELS:raise ValueError('Unexpected case')
    plan=read(ROOT/'protocol.json');native=BacktestEngine.run
    with patch.object(source,'ROOT',ROOT):
        if case in CASES:
            states=pd.read_parquet(plan['states'][case])
            with patch.object(BacktestEngine,'run',protected_run(native,ROOT/'cases'/case/'result',states)):source.run_case(case)
        else:source.run_case(case)


def validate_controls():
    for key in ['CONTROL','SL10']:
        a=ROOT/'cases'/key/'result';b=source.ROOT/'cases'/key/'result'
        for file in ['equity-daily.csv','trades.csv']:
            pd.testing.assert_frame_equal(pd.read_csv(a/file),pd.read_csv(b/file),check_exact=False,rtol=0,atol=1e-8)
        pd.testing.assert_frame_equal(pd.read_parquet(a/'equity-5m.parquet'),pd.read_parquet(b/'equity-5m.parquet'),check_exact=False,rtol=0,atol=1e-8)
    atomic_json(ROOT/'matched-controls.json',dict(status='PASS',controls=['CONTROL','SL10'],
        equity_daily=True,equity_5m=True,trades_quantities_prices_fees=True))


def finish():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    validate_controls()
    for case in LABELS:validate_case(ROOT/'cases'/case)
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',list(LABELS)):
        review=source.post_review(pd.read_parquet(SOURCE/'test-labels-and-risks.parquet'))
    rows=[];curves={};annual=[];windows=[];liquidations=[]
    keys=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_gross_capital',
        'maximum_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl',
        'average_winning_holding_days','average_losing_holding_days','stop_exits','first_session_stop_exits']
    for case,label in LABELS.items():
        out=ROOT/'cases'/case/'result';report=read(out/'report.json')
        rows.append(dict(case=case,label=label,**{k:report.get(k) for k in keys}))
        curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity;curves[label]=curve
        a=pd.read_csv(out/'annual-summary.csv');a['case']=case;annual.append(a)
        for start,end in [('2024-11-06','2025-04-04'),('2024-11-06','2025-06-30')]:
            w=curve.loc[start:end];windows.append(dict(case=case,start=start,end=end,
                return_pct=100*(w.iloc[-1]/w.iloc[0]-1),close_dd_pct=100*(w/w.cummax()-1).min()))
        if case in CASES:
            receipt=read(out/'internal-liquidations.json')
            if receipt['pending'] is not None:raise ValueError('Pending liquidation at end')
            for event in receipt['events']:liquidations.append(dict(case=case,**event))
            forced=pd.read_csv(out/'trades.csv').exit_reason.eq('INTERNAL_PROTECTION').sum()
            rows[-1].update(liquidations=len(receipt['events']),forced_exit_trades=int(forced))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False);pd.concat(annual).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.DataFrame(windows).to_csv(ROOT/'drawdown-windows.csv',index=False);atomic_json(ROOT/'liquidations.json',liquidations)
    chart=pd.DataFrame(curves)
    chart['SPY prix seuls']=pd.read_csv(previous.ROOT/'capital-curves.csv',index_col=0,parse_dates=True)['SPY prix seuls']
    if chart.isna().any().any():raise ValueError('Mismatched chart periods')
    chart.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for name,window in [('capital-comparison.png',None),('late2024-mid2025.png',slice('2024-11-06','2025-06-30'))]:
        fig,axes=plt.subplots(2,1,figsize=(14,11))
        for ax,family in zip(axes,['B','B + anti-SL']):
            names=[label for key,label in LABELS.items() if (key.startswith('SL10') if family!='B' else not key.startswith('SL10'))]
            names+=['SPY prix seuls'];frame=chart[names] if window is None else chart.loc[window,names]
            if window is not None:frame=100*frame/frame.iloc[0]
            frame.plot(ax=ax);ax.set_title(family+' — liquidation puis vol20 + régime pendant la protection')
            ax.set_ylabel('Capital ($), départ 4 000' if window is None else 'Base 100 au début de la fenêtre');ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(ROOT/name,dpi=150);plt.close(fig)
    lines=['# B / B + anti-SL — liquidation puis vol20 + régime','',
        '2021–1er octobre2026, 4000$ continus, deux témoins rejoués identiques aux archives. '
        'Activation/reprise figées comme les tests demi-taille ; liquidation à l’ouverture suivante, '
        'puis vol20/covariance60 et filtre SPY>98%SMA200 seulement en protection. '
        'À OFF : retour aux règles habituelles. Rachat à la même ouverture possible après liquidation si les limites passent.',
        '', '| Cas | Capital final | Rendement | DD intraday | Gagnants | Trades | Engagé moyen |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:lines.append(f"| {row['label']} | {row['final_equity']:.2f}$ | {row['return_pct']:+.2f}% | {row['max_drawdown_pct']:.2f}% | {row['win_pct']:.2f}% | {row['closed_lot_trades']} | {row['average_gross_capital']:.2f}$ |")
    lines+=['',f"Revue : {review['status']}. Réserves prix {len(review['price_reserves'])} ; écarts de labels {review['event_label_mismatches']}/{review['known_event_labels']}.",
        'Frais et financement natifs, capital partagé, quantités entières, SL5/open11 et mêmes signaux. '
        'Aucun appel fournisseur/LLM, entraînement, SQL ou ordre réel ; pas de changement de production. '
        'Historique déjà exploré, univers contemporain, prix révisés et intraday incomplet/repli OHLC : résultat exploratoire.',
        'Archives : `'+str(ROOT)+'`.']
    text='\n'.join(lines)+'\n';(ROOT/'results.md').write_text(text,encoding='utf-8')
    marker='<!-- Q051_INTERNAL_LIQUIDATION_RESULTS_20261118 -->'
    for file in [DOC,Path('doc/ml/experiences_done.md')]:
        if marker not in file.read_text(encoding='utf-8'):
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+text)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',completed=6,total=6,cases=rows,review=review['status'],production_changes=False))


def run():
    prepare()
    try:
        def launch(keys,limit):
            pending=[k for k in keys if not (ROOT/'cases'/k/'validation.json').exists()]
            with patch.object(source,'ROOT',ROOT),patch.object(source,'__spec__',__spec__):source.launch(pending,'case',limit)
        launch(['CONTROL','SL10'],2);validate_controls()
        launch(list(CASES),4);finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','prepare','case','finish'],required=True);parser.add_argument('--key');args=parser.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='case':run_case(args.key)
    else:finish()
