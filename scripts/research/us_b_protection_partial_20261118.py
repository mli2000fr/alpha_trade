"""Frozen four-way protection replay on B+anti-SL TOP10, no live edits/SQL/HTTP."""
import argparse
from copy import deepcopy
from pathlib import Path
import json
import os
import shutil
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_b_early_sl_20261116 as source
from scripts.research import us_q051_internal_liquidation_20261118 as old
from scripts.research.us_b_protection_partial_policy_20261118 import recovery_states,CorePilotEntries,PilotLiquidation
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_b_protection_partial/20261118-v1')
CASES={'SL10':dict(fraction=.5,mode='CONTROL'),
    'FULL_OLD':dict(fraction=1.,mode='OLD'),'HALF_OLD':dict(fraction=.5,mode='OLD'),
    'FULL_PROGRESSIVE':dict(fraction=1.,mode='PROGRESSIVE'),
    'HALF_PROGRESSIVE':dict(fraction=.5,mode='PROGRESSIVE')}
LABELS={'SL10':'B + anti-SL témoin','FULL_OLD':'Liquidation totale / ancienne sortie',
    'HALF_OLD':'Partie pilotée 50 % / ancienne sortie',
    'FULL_PROGRESSIVE':'Liquidation totale / reprise progressive',
    'HALF_PROGRESSIVE':'Partie pilotée 50 % / reprise progressive'}
read=source.read


def prepare():
    if (ROOT/'protocol.json').exists():return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True,exist_ok=True)
    original=read(old.ROOT/'protocol.json');sources={};changes=[]
    allowed={Path(n).resolve() for n in ['tests/test_q051_b_early_sl.py','backtesting/per_symbol_selection.py',
        'modelFactory/oracle_path/directional.py','modelFactory/oracle_path/train.py',
        'scripts/research/us_q051_b_early_sl_20261116.py','scripts/research/us_q051_internal_liquidation_20261118.py',
        'scripts/research/us_q051_internal_liquidation_policy_20261118.py','tests/test_q051_internal_liquidation.py']}
    for name,expected in original['sources'].items():
        actual=digest(Path(name))
        if actual!=expected:
            if Path(name).resolve() not in allowed:raise ValueError('Unexpected source drift: '+name)
            changes.append(dict(file=name,archived=expected,current=actual,
                reason='Existing research/serving additions; frozen selections only; exact matched controls required'))
        sources[name]=actual
    for file in ['selection-validation.json','oracle-oof-causality.json']:
        if read(source.ROOT/file)['status']!='PASS':raise ValueError('Frozen selection not validated')
    states=pd.read_parquet(old.ROOT/'inputs/SL10_SHADOW-states.parquet')
    shadow_file=source.ROOT/'cases/SL10/result/equity-daily.csv'
    shadow=pd.read_csv(shadow_file,index_col=0,parse_dates=True).equity
    sources[str(shadow_file)]=digest(shadow_file)
    sources[str(old.ROOT/'inputs/SL10_SHADOW-states.parquet')]=digest(old.ROOT/'inputs/SL10_SHADOW-states.parquet')
    for mode in ['OLD','PROGRESSIVE']:
        frame=recovery_states(states,shadow,mode)
        for cut in ['2022-12-30','2024-11-29','2025-05-30']:
            pd.testing.assert_frame_equal(frame.loc[:cut],recovery_states(states.loc[:cut],shadow.loc[:cut],mode))
        target=ROOT/'inputs'/(mode+'-states.parquet');target.parent.mkdir(exist_ok=True)
        frame.to_parquet(target);sources[str(target)]=digest(target)
        if not frame.transition.eq('ON').equals(states.transition.eq('ON')):raise ValueError('Activation schedule changed')
    normal=recovery_states(states,shadow,'OLD');normal['active']=False;normal['phase']='NORMAL';normal['transition']=''
    normal.to_parquet(ROOT/'inputs/CONTROL-states.parquet');sources[str(ROOT/'inputs/CONTROL-states.parquet')]=digest(ROOT/'inputs/CONTROL-states.parquet')
    signal=source.ROOT/'variants/SL10/signals.parquet'
    sources[str(signal)]=digest(signal)
    for case in CASES:
        target=ROOT/'variants'/case/'signals.parquet';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(signal,target);sources[str(target)]=digest(target)
    # Read-only identical supplements, hard-linked locally to avoid duplicateGB.
    tape=ROOT/'inputs/intraday';tape.mkdir(exist_ok=True)
    market=read(old.ROOT/'inputs/manifest.json');files=dict(market['files'])
    for name,expected in files.items():
        if digest(Path(name))!=expected:raise ValueError('Changed market tape')
    for file in (old.ROOT/'inputs/intraday').iterdir():
        if not file.is_file():continue
        target=tape/file.name
        if not target.exists():
            try:os.link(file,target)
            except OSError:shutil.copyfile(file,target)
        files[str(target)]=digest(target)
    atomic_json(ROOT/'inputs/manifest.json',dict(files=files,SQL_reads=0,provider_calls=0))
    for name in [Path(__file__),Path('scripts/research/us_b_protection_partial_policy_20261118.py'),
        Path('tests/test_b_protection_partial_20261118.py')]:sources[str(name)]=digest(name)
    plan=deepcopy(original);plan.update(sources=sources,cases=CASES,legacy_source_changes=changes,
        study='B+anti-SL core/pilot fraction x old/progressive recovery',
        activation='Identical causal background SHADOW observer ON dates for all4cases: mature rate20 vs previous120, -5pp/3closes',
        rearm='Background observer independently keeps its old return20>5%/5closes reset; early recovery never manufactures extra ON dates',
        old_recovery='Background shadow return20>5%/5closes, same original observer',
        progressive_recovery='Shadow return10>0 for2closes -> half pilot normal budget; then5consecutive closes ret10>0 and shadow>=probe anchor -> full normal',
        failed_probe='Reset5close stability count, keep half-pilot recovery; no automatic full exit or new ON before fresh background alert',
        core='Single account/order; core ceil(native quantity/2) fixed per campaign, remainder pilot;1share stays core',
        half_liquidation='Sell only remaining pilot quantities once per background ON; core is never sold by this overlay, unchanged SL/open11',
        protected_entries='Core native, pilot SPY>98%SMA200 and vol20/cov60 against pilot equity allocation; no whole-account volatility guarantee',
        progressive_entries='Half pilot quantity, no SPY/vol gate; integer/native min-notional recheck preserved',
        partial_exit_journal='Research REDUCE + native book_sell + native REARM; avoids treating partial reduction as terminal horizon EXIT',
        comparison_rate='Completed campaigns aggregate split exits; native fragment counts also retained; native loss trackers unchanged',
        matched_controls=['SL10 vs original SL10','FULL_OLD vs original SL10_SHADOW'],
        new_training=0,new_labels=0,recalibrations=0,SQL_reads=0,SQL_writes=0,provider_calls=0,orders=0,production_changes=False)
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'preflight.json',dict(status='PASS',state_prefix_checks=6,common_ON_schedule=True,
        identical_signals=True,source_changes=changes,matched_controls_required=True))
    return plan


def protected_run(original,out,states,fraction):
    def run(engine,*args,**kwargs):
        from backtesting import winner_global_liquidation as native
        if any(kwargs.get(k) is not None for k in ['winner_selection_source','winner_entry_risk_policy']):
            raise ValueError('Would overwrite existing replay policy')
        policy=CorePilotEntries(states,kwargs['close'],fraction);liquidator=PilotLiquidation(states,policy)
        kwargs.update(winner_selection_source=policy.select,winner_entry_risk_policy=policy)
        with patch.object(native,'GlobalLiquidation',lambda *a:liquidator):result=original(engine,*args,**kwargs)
        states.loc['2020-12-31':'2026-09-30'].to_csv(out/'protection-states.csv')
        pd.DataFrame(policy.receipts).to_csv(out/'sizing-decisions.csv',index=False)
        pd.DataFrame(policy.full.gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
        pd.DataFrame(policy.full.budget.receipts).to_csv(out/'volatility-decisions.csv',index=False)
        atomic_json(out/'liquidations.json',dict(events=liquidator.events,pending=liquidator.pending,
            pilot_fraction=fraction,allocations=policy.allocations,summary=liquidator.summary()))
        return result
    return run


def run_case(case):
    from backtesting.simulator import BacktestEngine
    plan=read(ROOT/'protocol.json');spec=CASES[case]
    states=pd.read_parquet(ROOT/'inputs'/(spec['mode']+'-states.parquet'))
    native=BacktestEngine.run
    with patch.object(source,'ROOT',ROOT),patch.object(BacktestEngine,'run',protected_run(native,ROOT/'cases'/case/'result',states,spec['fraction'])):
        source.run_case(case)


def validate_controls():
    for case,other in [('SL10',source.ROOT/'cases/SL10/result'),('FULL_OLD',old.ROOT/'cases/SL10_SHADOW/result')]:
        out=ROOT/'cases'/case/'result'
        for name in ['equity-daily.csv','trades.csv']:
            pd.testing.assert_frame_equal(pd.read_csv(out/name),pd.read_csv(other/name),check_exact=False,rtol=0,atol=1e-8)
        pd.testing.assert_frame_equal(pd.read_parquet(out/'equity-5m.parquet'),pd.read_parquet(other/'equity-5m.parquet'),check_exact=False,rtol=0,atol=1e-8)
    atomic_json(ROOT/'matched-controls.json',dict(status='PASS',equity_daily=True,equity_intraday=True,trades=True))


def finish():
    validate_controls();rows=[];curves={};annual=[];phases=[]
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    for case in CASES:
        out=ROOT/'cases'/case/'result';report=validate_case(ROOT/'cases'/case)
        curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity;curves[LABELS[case]]=curve
        t=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
        buys=events[events.event.eq('BUY_FILL')].copy();buys['entry_date']=pd.to_datetime(buys.time,utc=True)
        t['entry_date']=pd.to_datetime(t.entry_date,utc=True)
        grouped=t.groupby(['campaign_id','symbol','entry_date'],as_index=False).agg(quantity=('quantity','sum'),pnl=('pnl','sum'),last_exit=('exit_date','max'))
        campaigns=grouped.merge(buys[['symbol','entry_date','quantity']].rename(columns={'quantity':'entry_quantity'}),on=['symbol','entry_date'],validate='one_to_one')
        if len(campaigns)!=len(grouped) or campaigns.quantity.gt(campaigns.entry_quantity).any():raise ValueError('Campaign aggregation mismatch')
        complete=campaigns[campaigns.quantity.eq(campaigns.entry_quantity)]
        campaigns.to_csv(out/'campaigns.csv',index=False)
        receipt=read(out/'liquidations.json')
        if receipt['pending'] is not None:raise ValueError('Pending protection sale at end')
        fields=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital',
            'maximum_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl']
        rows.append(dict(case=case,label=LABELS[case],**{k:report.get(k) for k in fields},
            completed_campaigns=len(complete),campaign_win_pct=float(100*complete.pnl.gt(0).mean()),
            protection_events=len(receipt['events']),pilot_fraction=CASES[case]['fraction']))
        a=pd.read_csv(out/'annual-summary.csv');a['case']=case;annual.append(a)
        state=pd.read_csv(out/'protection-states.csv',index_col=0,parse_dates=True)
        for year,g in state.groupby(state.index.year):
            phases.append(dict(case=case,year=int(year),sessions=len(g),protected=int(g.phase.eq('PROTECTED').sum()),
                probe=int(g.phase.eq('PROBE').sum()),normal=int(g.phase.eq('NORMAL').sum()),
                on=int(g.transition.eq('ON').sum()),off=int(g.transition.eq('OFF').sum())))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False);pd.concat(annual).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.DataFrame(phases).to_csv(ROOT/'phases-by-year.csv',index=False)
    labels=pd.read_parquet(Path('artifacts/research/us_q051_b_early_sl/20261116-v1/test-labels-and-risks.parquet'))
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',list(CASES)):
        review=source.post_review(labels)
    chart=pd.DataFrame(curves)
    chart['SPY prix seuls']=pd.read_csv(old.ROOT/'capital-curves.csv',index_col=0,parse_dates=True)['SPY prix seuls']
    chart.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=['#1d4ed8','#a8a29e','#d97706','#a855f7','#059669','#475569']
    for name,window in [('capital-comparison.png',None),('late2024-mid2025.png',slice('2024-11-06','2025-06-30'))]:
        view=chart if window is None else chart.loc[window]
        fig,(ax,dd)=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[2,1]},facecolor='#f7f9fc')
        for (label,values),color in zip(view.items(),colors):
            ax.plot(values.index,values,color=color,label=label,lw=1.4)
            seed=4000 if window is None else values.iloc[0]
            dd.plot(values.index,100*(values/values.cummax().clip(lower=seed)-1),color=color,lw=1)
        ax.set_ylabel('Capital ($)');dd.set_ylabel('DD de clôture (%)');ax.legend(fontsize=8,ncol=2,frameon=False)
        for a in [ax,dd]:a.grid(alpha=.2);a.spines[['top','right']].set_visible(False)
        fig.suptitle('B + anti-SL TOP10 — protection partielle et reprise progressive',fontsize=15,fontweight='bold')
        fig.text(.09,.025,'4 000 $ continus ; 2021 au 1er octobre 2026 ; mêmes signaux et alertes ON.\n'
            'SL5/open11, frais/financement natifs. Tableau : DD intraday ; graphique inférieur : DD de clôture. Résultats exploratoires.',fontsize=9)
        fig.subplots_adjust(left=.09,right=.98,top=.91,bottom=.14,hspace=.12);fig.savefig(ROOT/name,dpi=150);plt.close(fig)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',completed=5,total=5,results=rows,review=review))
    print(json.dumps(rows,indent=2,ensure_ascii=False))


def run():
    prepare()
    def launch(keys,limit):
        pending=[k for k in keys if not (ROOT/'cases'/k/'validation.json').exists()]
        with patch.object(source,'ROOT',ROOT),patch.object(source,'__spec__',__spec__):source.launch(pending,'case',limit)
    launch(['SL10','FULL_OLD'],2);validate_controls()
    launch(['HALF_OLD','FULL_PROGRESSIVE','HALF_PROGRESSIVE'],3);finish()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','case','finish'],default='all');p.add_argument('--key');a=p.parse_args()
    if a.phase=='case':run_case(a.key)
    elif a.phase=='prepare':prepare()
    elif a.phase=='finish':finish()
    else:run()
