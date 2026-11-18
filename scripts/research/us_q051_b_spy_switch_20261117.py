"""Six frozen replays: B / B+SL10 times SPY hysteresis SMA20/50/100.

Two immutable controls per family: no protection and permanent vol20/regime.
No training, SQL, provider calls, orders or production configuration changes.
"""
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
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_spy_switch_policy_20261117 import switch_states,SwitchedBudget,SwitchedRegime

ROOT=Path('artifacts/research/us_q051_b_spy_switch/20261117-v1')
SOURCE=source.ROOT
DOC=Path('doc/ml/q051_b_spy_switch_20261117.md')
CASES={f'{family}_MA{window}':dict(family=family,window=window) for family in ['B','SL10'] for window in [20,50,100]}
REFERENCES={
    'B sans protection':SOURCE/'cases/CONTROL',
    'B protection permanente':source.REFERENCE/'variants/B/cases/B_VOL20_REGIME',
    'B + anti-SL10 sans protection':SOURCE/'cases/SL10',
    'B + anti-SL10 protection permanente':Path('artifacts/research/us_q051_b_sl10_vol20_regime/20261117-v1/cases/SL10_VOL20_REGIME')}


def read(p):return source.read(p)


def prepare():
    if (ROOT/'protocol.json').exists():
        p=read(ROOT/'protocol.json')
        for file,h in p['sources'].items():
            if digest(Path(file))!=h:raise ValueError('Changed sealed source '+file)
        return p
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    ROOT.mkdir(parents=True,exist_ok=True)
    old=read(SOURCE/'protocol.json');sources=dict(old['sources'])
    for file,h in sources.items():
        if digest(Path(file))!=h:raise ValueError('Changed original source '+file)
    for folder in REFERENCES.values():
        validate_case(folder)
        for name in ['configuration.json','report.json','trades.csv','equity-daily.csv','annual-summary.csv','equity-5m.parquet']:
            p=folder/'result'/name;sources[str(p)]=digest(p)
    cfg=source.base.shared.configuration(old['reference_settings'],source.base.shared.CASES['Q051_050'])
    snap=json.loads(json.dumps(asdict(cfg),default=str))
    for case in ['CONTROL','SL10']:
        if snap!=read(SOURCE/'cases'/case/'result/configuration.json')['portfolio']:
            raise ValueError('Base portfolio differs from archived reference')
    if cfg.risk_overlay.regime_filter.enabled:raise ValueError('Static regime would override dynamic switch')
    spy=pd.read_parquet(source.FULL/'inputs/close.parquet',columns=['SPY']).SPY
    state_files={}
    for window in [20,50,100]:
        states=switch_states(spy,window)
        check=states.loc['2020-12-31':'2026-09-30']
        if not check.qualified.all():raise ValueError('SPY switch warmup/history insufficient')
        # Prefix reconstruction must not depend on the future price series.
        prefix=spy.loc[:'2024-12-31'];pd.testing.assert_frame_equal(switch_states(prefix,window),states.loc[:'2024-12-31'])
        p=ROOT/'inputs'/f'spy-states-MA{window}.parquet';p.parent.mkdir(exist_ok=True)
        states.to_parquet(p);sources[str(p)]=digest(p);state_files[str(window)]=str(p)
    for case,spec in CASES.items():
        original=SOURCE/'variants'/('CONTROL' if spec['family']=='B' else 'SL10')/'signals.parquet'
        p=ROOT/'variants'/case/'signals.parquet';p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,p)
        if digest(p)!=digest(original):raise ValueError('Candidate selection changed')
        sources[str(p)]=digest(p);sources[str(original)]=digest(original)
    tape=ROOT/'inputs/intraday';tape.mkdir(parents=True,exist_ok=True)
    files=dict(read(SOURCE/'inputs/manifest.json')['files'])
    for file,h in files.items():
        if digest(Path(file))!=h:raise ValueError('Changed frozen market input '+file)
    for file in (SOURCE/'inputs/intraday').iterdir():
        if file.is_file():
            p=tape/file.name;shutil.copyfile(file,p);files[str(p)]=digest(p)
    atomic_json(ROOT/'inputs/manifest.json',dict(files=files,SQL_reads=0,SQL_writes=0,provider_calls=0,
        source=str(SOURCE/'inputs/manifest.json')))
    for file in [Path(__file__),Path('scripts/research/us_q051_spy_switch_policy_20261117.py'),
        Path('tests/test_q051_spy_switch.py'),Path('backtesting/winner_portfolio_budget.py'),
        Path('backtesting/risk_overlay.py'),Path('risk_management/portfolio_volatility.py'),SOURCE/'protocol.json',
        SOURCE/'test-labels-and-risks.parquet']:
        sources[str(file)]=digest(file)
    plan=deepcopy(old)
    plan.update(cases=CASES,sources=sources,states=state_files,source_campaign=str(SOURCE),
        study='B and B+SL10 TOP10: causal SPY switch, MA20/50/100',
        switch=dict(on_buffer=-.02,on_sessions=2,off_buffer=.01,off_sessions=5,
            neutral_zone='retain previous state',initial_state='NORMAL before first valid historical SMA',
            warmup='all frozen SPY closes from 2019-03-22, before first 2021 entry',effect='next session only'),
        active_protection=dict(volatility_target=.20,covariance_lookback=60,regime_sma=200,regime_threshold=-.02),
        held_positions='unchanged SL5/open11; no forced liquidation',new_training=0,recalibrations=0,
        SQL_reads=0,SQL_writes=0,provider_calls=0,orders=0,production_changes=False,
        references={k:str(v) for k,v in REFERENCES.items()},created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'preflight.json',dict(status='PASS',base_portfolio_identical=True,signals_identical=True,
        static_regime_disabled=True,causal_prefix_checks=3,reference_accounting_checks=4,cases=CASES))
    atomic_json(ROOT/'progress.json',dict(status='READY',total=6,completed=0))
    return plan


def switched_run(original,out,window):
    def run(engine,*args,**kwargs):
        if any(kwargs.get(k) is not None for k in ['winner_selection_source','winner_entry_risk_policy']):
            raise ValueError('Existing callback would be replaced')
        if engine.config.risk_overlay.regime_filter.enabled:raise ValueError('Unexpected static regime')
        close=kwargs['close'];states=switch_states(close.SPY,window)
        expected=pd.read_parquet(ROOT/'inputs'/f'spy-states-MA{window}.parquet')
        pd.testing.assert_frame_equal(states,expected)
        budget=SwitchedBudget(close,states);gate=SwitchedRegime(close,states)
        kwargs.update(winner_selection_source=gate,winner_entry_risk_policy=budget)
        result=original(engine,*args,**kwargs)
        pd.DataFrame(budget.receipts).to_csv(out/'sizing-decisions.csv',index=False)
        pd.DataFrame(budget.defensive.receipts).to_csv(out/'active-budget-decisions.csv',index=False)
        pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
        pd.DataFrame(gate.defensive.receipts).to_csv(out/'active-regime-decisions.csv',index=False)
        states.loc['2020-12-31':'2026-09-30'].to_csv(out/'spy-state-timeline.csv')
        atomic_json(out/'entry-protections.json',dict(window=window,only_new_entries=True,
            static_regime=False,on_buffer=-.02,on_sessions=2,off_buffer=.01,off_sessions=5,
            active_vol_target=.20,active_covariance_lookback=60,active_spy_sma=200,active_spy_threshold=-.02,
            sizing_checks=len(budget.receipts),regime_checks=len(gate.receipts)))
        return result
    return run


def run_case(case):
    from backtesting.simulator import BacktestEngine
    if case not in CASES:raise ValueError('Unrequested case')
    native=BacktestEngine.run
    with patch.object(source,'ROOT',ROOT),patch.object(BacktestEngine,'run',switched_run(native,ROOT/'cases'/case/'result',CASES[case]['window'])):
        source.run_case(case)


def finish():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    for case in CASES:validate_case(ROOT/'cases'/case)
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',list(CASES)):
        review=source.post_review(pd.read_parquet(SOURCE/'test-labels-and-risks.parquet'))
    specs=list(REFERENCES.items())
    specs += [(('B' if c['family']=='B' else 'B + anti-SL10')+f" bascule MA{c['window']}",ROOT/'cases'/name) for name,c in CASES.items()]
    rows=[];curves={};annual=[];window_rows=[]
    for name,folder in specs:
        out=folder/'result';r=read(out/'report.json')
        keys=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_gross_capital',
            'average_gross_equity_ratio','average_winning_pnl','average_losing_pnl','stop_exits','first_session_stop_exits']
        rows.append(dict(case=name,**{k:r.get(k) for k in keys}))
        curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity;curves[name]=curve
        a=pd.read_csv(out/'annual-summary.csv');a['case']=name;annual.append(a)
        w=curve.loc['2024-11-06':'2025-04-04']
        window_rows.append(dict(case=name,start_equity=float(w.iloc[0]),end_equity=float(w.iloc[-1]),
            return_pct=100*(w.iloc[-1]/w.iloc[0]-1),close_dd_pct=100*(w/w.cummax()-1).min()))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.DataFrame(window_rows).to_csv(ROOT/'late2024-early2025-comparison.csv',index=False)
    close=pd.read_parquet(source.FULL/'inputs/close.parquet',columns=['SPY']).SPY
    dates=next(iter(curves.values())).index;prior=close.loc[close.index<dates[0]].iloc[-1]
    curves['SPY prix seuls']=4000*close.reindex(dates)/prior
    frame=pd.concat(curves,axis=1);frame.to_csv(ROOT/'capital-curves.csv')
    timeline=[];switch_annual=[]
    for window in [20,50,100]:
        states=pd.read_parquet(ROOT/'inputs'/f'spy-states-MA{window}.parquet').loc['2020-12-31':'2026-09-30']
        timeline.append(dict(window=window,signal_sessions=len(states),protected_sessions=int(states.active.sum()),
            protected_pct=100*states.active.mean(),switches=int(states.transition.ne('').sum()),
            activations=int(states.transition.eq('ON').sum()),deactivations=int(states.transition.eq('OFF').sum())))
        for year,g in states.groupby(states.index.year):
            switch_annual.append(dict(window=window,signal_year=int(year),sessions=len(g),protected_pct=100*g.active.mean(),
                activations=int(g.transition.eq('ON').sum()),deactivations=int(g.transition.eq('OFF').sum())))
    pd.DataFrame(timeline).to_csv(ROOT/'switch-summary.csv',index=False)
    pd.DataFrame(switch_annual).to_csv(ROOT/'switch-annual.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(14,12))
    for ax,family in zip(axes,['B','B + anti-SL10']):
        names=[n for n in frame if n=='SPY prix seuls' or (n.startswith('B + anti-SL10') if family!='B' else n.startswith('B ') and not n.startswith('B +'))]
        frame[names].plot(ax=ax);ax.set_title(family+' TOP10 — protection désactivée, permanente ou bascule SPY')
        ax.set_ylabel('Capital valorisé ($), départ 4 000');ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(14,10))
    for ax,family in zip(axes,['B','B + anti-SL10']):
        names=[n for n in frame if n=='SPY prix seuls' or (n.startswith('B + anti-SL10') if family!='B' else n.startswith('B ') and not n.startswith('B +'))]
        w=frame.loc['2024-11-06':'2025-04-04',names];(100*w/w.iloc[0]).plot(ax=ax)
        ax.set_title(family+' — baisse fin2024/début2025, même fenêtre');ax.set_ylabel('Base100');ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'drawdown-window-comparison.png',dpi=150);plt.close(fig)
    text=['# B / B + anti-SL10 TOP10 — bascule SPY vol20 + régime','',
        '2021–1er octobre2026, 4000$ continus. Six nouveaux replays figés : deux familles × moyennes SPY20/50/100. '
        'Activation après deux clôtures SPY sous98% de la moyenne ; désactivation après cinq clôtures au-dessus de101%. '
        'Entre les seuils : état conservé. État calculé sur chaque séance, même sans candidat, depuis le warmup2019. '
        'Données arrêtées à J pour les nouvelles entrées J+1. Aucune liquidation des positions détenues.',
        'En mode actif seulement : covariance60 séances/budget annualisé20% et filtre SPY>98% SMA200. '
        'Mode normal : approbation native inchangée. Modèles, signaux TOP179 Oracle→TOP10 LONG et veto anti-SL10 éventuel identiques. '
        'SL5/open11, sans TP/trailing, risque1,25%, poids20%, plafond achats1×/capacité margin2×, frais8pb/côté et financement6,5%. '
        'Sans B4/DD/pause100. Les quatre témoins sont archivés et non recalculés.','',
        '| Cas | Capital final | Rendement | DD intraday | Gagnants | Trades |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:text.append(f"| {r['case']} | {r['final_equity']:.2f}$ | {r['return_pct']:+.2f}% | {r['max_drawdown_pct']:.2f}% | {r['win_pct']:.2f}% | {r['closed_lot_trades']} |")
    text+=['',f"Revue des nouvelles détentions : {review['status']}, {len(review['price_reserves'])} réserves de prix, "
        f"{review['event_label_mismatches']}/{review['known_event_labels']} écarts de labels première séance.",
        'Recherche rétrospective sur des années déjà explorées, intraday incomplet avec repli OHLC, univers contemporain et prix révisés. '
        'Un seuil retenu ici ne sera pas une validation indépendante. Aucun modèle réentraîné, accès SQL, appel fournisseur/LLM, ordre ou changement de production.',
        'Les comparaisons dans la baisse utilisent la même fenêtre clôture6novembre2024–4avril2025 ; elles ne remplacent pas le DD intraday global. '
        'La volatilité cible20% ne plafonne pas le DD. Lire les résultats annuels et les basculements avant toute conclusion.',
        'Archives : `'+str(ROOT)+'`.']
    message='\n'.join(text)+'\n';(ROOT/'results.md').write_text(message,encoding='utf-8')
    marker='<!-- Q051_B_SPY_SWITCH_RESULTS_20261117 -->'
    for file in [DOC,Path('doc/ml/experiences_done.md')]:
        if marker not in file.read_text(encoding='utf-8'):
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+message)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,review=review['status'],production_changes=False))


def run():
    prepare()
    try:
        pending=[c for c in CASES if not (ROOT/'cases'/c/'validation.json').exists()]
        with patch.object(source,'ROOT',ROOT),patch.object(source,'__spec__',__spec__):source.launch(pending,'case',3)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','case','finish'],required=True);p.add_argument('--key');a=p.parse_args()
    if a.phase=='all':run()
    elif a.phase=='prepare':prepare()
    elif a.phase=='case':run_case(a.key)
    else:finish()
