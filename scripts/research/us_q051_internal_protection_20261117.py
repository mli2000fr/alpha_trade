"""Four frozen native replays, internal rate trigger and half-size new entries.

Same B TOP10 rate trigger for both families, before anti-SL. Recovery is either
rate recovery or each family's continuous unprotected shadow-account return20.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import json
import shutil
from unittest.mock import patch

import pandas as pd

from scripts.research import us_q051_b_early_sl_20261116 as source
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_internal_protection_policy_20261117 import internal_states,HalfNewEntry

ROOT=Path('artifacts/research/us_q051_internal_protection/20261117-v1')
SOURCE=source.ROOT
AUDIT=Path('artifacts/research/us_q051_winrate_recovery_audit/20261117-v1')
DOC=Path('doc/ml/q051_internal_protection_20261117.md')
CASES={f'{family}_{mode}':dict(family=family,mode=mode) for family in ['B','SL10'] for mode in ['RATE','SHADOW']}
REFERENCES={'B témoin':SOURCE/'cases/CONTROL','B + anti-SL témoin':SOURCE/'cases/SL10'}


def read(p):return source.read(p)


def prepare():
    if (ROOT/'protocol.json').exists():
        p=read(ROOT/'protocol.json')
        for file,h in p['sources'].items():
            if digest(Path(file))!=h:raise ValueError('Changed sealed source '+file)
        return p
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    from scripts.research.us_q051_winrate_recovery_audit_20261117 import rate_switch
    ROOT.mkdir(parents=True,exist_ok=True);old=read(SOURCE/'protocol.json');sources=dict(old['sources'])
    for file,h in sources.items():
        if digest(Path(file))!=h:raise ValueError('Changed original source '+file)
    if read(AUDIT/'validation.json')['status']!='PASS':raise ValueError('Winrate audit not validated')
    for folder in REFERENCES.values():
        validate_case(folder)
        for name in ['configuration.json','report.json','trades.csv','events.csv','equity-daily.csv','equity-5m.parquet','annual-summary.csv']:
            p=folder/'result'/name;sources[str(p)]=digest(p)
    cfg=source.base.shared.configuration(old['reference_settings'],source.base.shared.CASES['Q051_050'])
    snap=json.loads(json.dumps(asdict(cfg),default=str))
    for c in ['CONTROL','SL10']:
        if snap!=read(SOURCE/'cases'/c/'result/configuration.json')['portfolio']:raise ValueError('Portfolio differs from witness')
    if cfg.risk_overlay.regime_filter.enabled or cfg.exec_config.winner_pyramiding.reinforcement_enabled:
        raise ValueError('Unrequested static regime/reinforcement')
    rates_path=AUDIT/'PER_B10-timeline.parquet';rates=pd.read_parquet(rates_path)
    source_files=[rates_path,AUDIT/'protocol.json',AUDIT/'validation.json',
        Path('scripts/research/us_q051_winrate_recovery_audit_20261117.py'),
        Path('scripts/research/us_q051_internal_protection_policy_20261117.py'),
        Path('tests/test_q051_internal_protection.py'),Path(__file__)]
    snapshots={};counts={}
    for case,spec in CASES.items():
        origin='CONTROL' if spec['family']=='B' else 'SL10'
        equity=pd.read_csv(SOURCE/'cases'/origin/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        states=internal_states(rates,equity,spec['mode'])
        for cut in ['2022-12-30','2024-11-29','2025-05-30']:
            pd.testing.assert_frame_equal(states.loc[:cut],internal_states(rates.loc[:cut],equity.loc[:cut],spec['mode']))
        if spec['mode']=='RATE':
            previous=rate_switch(rates)
            pd.testing.assert_series_equal(states.active,previous.active,check_names=False)
            pd.testing.assert_series_equal(states.transition,previous.transition,check_names=False)
        inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True)
        p=inputs/(case+'-states.parquet');states.to_parquet(p);source_files.append(p);snapshots[case]=str(p)
        original=SOURCE/'variants'/origin/'signals.parquet';target=ROOT/'variants'/case/'signals.parquet'
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
        if digest(original)!=digest(target):raise ValueError('Candidate selection changed')
        source_files.extend([original,target])
        view=states.loc['2020-12-31':'2026-09-30']
        counts[case]=dict(signals=len(pd.read_parquet(target)),active_sessions=int(view.active.sum()),
            on=int(view.transition.eq('ON').sum()),off=int(view.transition.eq('OFF').sum()),
            unqualified_rate_sessions=int((~view.qualified).sum()))
    # RATE decisions are common; each family's shadow return is logged for
    # inspection but never used by this recovery mode.
    decision_columns=['qualified','active','anchor','transition','rate20','reference120','below_count','recovery_count','previous_active']
    pd.testing.assert_frame_equal(pd.read_parquet(snapshots['B_RATE'])[decision_columns],
        pd.read_parquet(snapshots['SL10_RATE'])[decision_columns])
    tape=ROOT/'inputs/intraday';tape.mkdir(parents=True,exist_ok=True)
    files=dict(read(SOURCE/'inputs/manifest.json')['files'])
    for file,h in files.items():
        if digest(Path(file))!=h:raise ValueError('Changed frozen market input '+file)
    for file in (SOURCE/'inputs/intraday').iterdir():
        if file.is_file():
            p=tape/file.name;shutil.copyfile(file,p);files[str(p)]=digest(p)
    atomic_json(ROOT/'inputs/manifest.json',dict(files=files,source=str(SOURCE/'inputs/manifest.json'),SQL_reads=0,provider_calls=0))
    for p in [*source_files,SOURCE/'protocol.json']:sources[str(p)]=digest(p)
    plan=deepcopy(old)
    plan.update(cases=CASES,sources=sources,states=snapshots,source_campaign=str(SOURCE),
        study='Half-size internal protection: shared per-symbol B winrate activation, two recoveries',
        rate_cohort='PER_B10, before optional anti-SL, common to both families',
        activation='rate20 < previous120 reference-5pp, three qualified consecutive closes',
        recovery_A='rate20 >= reference frozen at activation-2pp, five qualified consecutive closes',
        recovery_B='unprotected continuous shadow account return20 >5%, five consecutive closes',
        quantity_policy='floor(native approved integer quantity/2) while active, followed by native recheck',
        unknowns='No new activation without qualified rate; retain current state. RATE recovery needs qualified rate, SHADOW recovery needs qualified shadow return.',
        start='2021-01-01',end='2026-10-01',new_training=0,new_labels=0,recalibrations=0,
        held_positions='Unchanged SL5/open11, no forced liquidation',SQL_reads=0,SQL_writes=0,
        provider_calls=0,orders=0,production_changes=False,references={k:str(v) for k,v in REFERENCES.items()},
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'preflight.json',dict(status='PASS',base_portfolio_identical=True,signals_identical=True,
        prefix_state_checks=12,rate_state_equivalence_checks=2,shared_activation_cohort=True,cases=counts))
    atomic_json(ROOT/'progress.json',dict(status='READY',total=4,completed=0))
    return plan


def protected_run(original,out,states):
    def run(engine,*args,**kwargs):
        if any(kwargs.get(k) is not None for k in ['winner_selection_source','winner_entry_risk_policy']):
            raise ValueError('Existing callback would be replaced')
        policy=HalfNewEntry(states);kwargs['winner_entry_risk_policy']=policy
        result=original(engine,*args,**kwargs)
        pd.DataFrame(policy.receipts).to_csv(out/'half-sizing-decisions.csv',index=False)
        states.loc['2020-12-31':'2026-09-30'].to_csv(out/'internal-protection-timeline.csv')
        atomic_json(out/'entry-protections.json',dict(half_size_only=True,held_positions_unchanged=True,
            new_entry_checks=len(policy.receipts),static_SPY=False,volatility_budget=False,drawdown_liquidation=False))
        return result
    return run


def run_case(case):
    from backtesting.simulator import BacktestEngine
    if case not in CASES:raise ValueError('Unrequested case')
    plan=read(ROOT/'protocol.json');states=pd.read_parquet(plan['states'][case]);native=BacktestEngine.run
    with patch.object(source,'ROOT',ROOT),patch.object(BacktestEngine,'run',protected_run(native,ROOT/'cases'/case/'result',states)):
        source.run_case(case)


def finish():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    for case in CASES:validate_case(ROOT/'cases'/case)
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',list(CASES)):
        review=source.post_review(pd.read_parquet(SOURCE/'test-labels-and-risks.parquet'))
    labels={'B_RATE':'B — demi-taille / sortie taux','B_SHADOW':'B — demi-taille / sortie témoin+5%',
        'SL10_RATE':'B + anti-SL — demi-taille / sortie taux','SL10_SHADOW':'B + anti-SL — demi-taille / sortie témoin+5%'}
    specs=[*REFERENCES.items(),*[(labels[c],ROOT/'cases'/c) for c in CASES]]
    rows=[];curves={};annual=[];windows=[];switches=[];sizing=[]
    keys=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_gross_capital',
        'maximum_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl',
        'average_winning_holding_days','average_losing_holding_days','stop_exits','first_session_stop_exits']
    for label,folder in specs:
        out=folder/'result';r=read(out/'report.json');rows.append(dict(case=label,**{k:r.get(k) for k in keys}))
        curve=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity;curves[label]=curve
        a=pd.read_csv(out/'annual-summary.csv');a['case']=label;annual.append(a)
        for start,end in [('2024-11-06','2025-04-04'),('2024-11-06','2025-06-30')]:
            w=curve.loc[start:end]
            windows.append(dict(case=label,start=start,end=end,start_equity=float(w.iloc[0]),end_equity=float(w.iloc[-1]),
                return_pct=100*(w.iloc[-1]/w.iloc[0]-1),close_dd_pct=100*(w/w.cummax()-1).min()))
    for case in CASES:
        states=pd.read_parquet(ROOT/'inputs'/(case+'-states.parquet')).loc['2020-12-31':'2026-09-30']
        for year,g in states.groupby(states.index.year):
            switches.append(dict(case=case,signal_year=int(year),sessions=len(g),active_sessions=int(g.active.sum()),
                active_pct=100*g.active.mean(),activations=int(g.transition.eq('ON').sum()),deactivations=int(g.transition.eq('OFF').sum()),
                unqualified_rate_sessions=int((~g.qualified).sum())))
        receipts=pd.read_csv(ROOT/'cases'/case/'result/half-sizing-decisions.csv')
        receipts['year']=pd.to_datetime(receipts.time,utc=True).dt.year
        for (year,active),g in receipts.groupby(['year','protection_active']):
            sizing.append(dict(case=case,year=int(year),active=bool(active),checks=len(g),
                native_positive=int(g.native_quantity.gt(0).sum()),final_zero=int(g.final_quantity.eq(0).sum()),
                native_quantity=float(g.native_quantity.sum()),final_quantity=float(g.final_quantity.sum())))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.DataFrame(windows).to_csv(ROOT/'drawdown-windows.csv',index=False)
    pd.DataFrame(switches).to_csv(ROOT/'switches-by-year.csv',index=False)
    pd.DataFrame(sizing).to_csv(ROOT/'sizing-by-year.csv',index=False)
    frame=pd.concat(curves,axis=1)
    spy=pd.read_parquet(source.FULL/'inputs/close.parquet',columns=['SPY']).SPY
    prior=spy.loc[spy.index<frame.index[0]].iloc[-1];frame['SPY prix seuls']=4000*spy.reindex(frame.index)/prior
    frame.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for target,window in [('capital-comparison.png',None),('late2024-mid2025.png',slice('2024-11-06','2025-06-30'))]:
        fig,axes=plt.subplots(2,1,figsize=(14,11))
        for ax,family in zip(axes,['B','B + anti-SL']):
            names=[n for n in frame if n=='SPY prix seuls' or (n.startswith('B + anti-SL') if family!='B' else n.startswith('B ') and not n.startswith('B +'))]
            f=frame[names] if window is None else frame.loc[window,names]
            if window is not None:f=100*f/f.iloc[0]
            f.plot(ax=ax);ax.set_title(family+' TOP10 — témoin et protection interne demi-taille')
            ax.set_ylabel('Capital ($), départ4 000' if window is None else 'Base100 début de fenêtre');ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(ROOT/target,dpi=150);plt.close(fig)
    text=['# B / B + anti-SL TOP10 — protection interne, nouvelles entrées à demi-taille','',
        '2021–1er octobre2026,4000$ continus. Quatre replays natifs. Déclencheur commun : taux LONG profitable du TOP10 per-symbol B avant anti-SL, '
        '20 séances mûres contre les120précédentes. Baisse>5points pendant3clôtures pour activer. '
        'Sortie A : retour à référence figée moins2points pendant5clôtures. Sortie B : compte témoin virtuel de la famille >+5% sur20séances pendant5clôtures. '
        'Décisions àJ pourJ+1 ; étiquettes connues à maturité complèteopen11. Taux inconnu : pas de nouvelle activation ; état existant conservé.',
        'Protection : floor(quantité approuvée native/2), puis revalidation native ; minimums et quantités entières conservés. '
        'Elle ne divise pas nécessairement l’exposition globale par deux : positions existantes, candidats suivants et capital disponible restent dans le moteur. '
        'Positions détenues : SL5/open11 inchangés. Sans TP/trailing, sans SPY/vol20/B4/DD/pause100 supplémentaires. '
        'Modèles/signaux/risque de base, frais et financement identiques aux témoins.',
        '', '| Cas | Capital final | Rendement | DD intraday | Gagnants | Trades | Capital engagé moyen |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:text.append(f"| {r['case']} | {r['final_equity']:.2f}$ | {r['return_pct']:+.2f}% | {r['max_drawdown_pct']:.2f}% | {r['win_pct']:.2f}% | {r['closed_lot_trades']} | {r['average_gross_capital']:.2f}$ |")
    text += ['',f"Revue : {review['status']}. Réserves prix {len(review['price_reserves'])}, écarts de labels première séance {review['event_label_mismatches']}/{review['known_event_labels']}.",
        'Les deux témoins continus existaient avant ce test et servent aussi de comptes virtuels pour la sortie B ; leurs cours/capitaux futurs ne sont jamais lus à une décisionJ. '
        'Les labels de fin d’année manquants restent inconnus ; le warmup qualifié débute en août2021, sans inventer une protection sur le début2021. '
        'Les taux sont des proportions de LONG profitables parmi les sélections, pas la précision d’amplitude Oracle ni l’AUC du modèle.',
        'Recherche rétrospective sur années déjà explorées, univers contemporain et prix révisés ; intraday partiel avec repli OHLC. '
        'Aucun nouvel entraînement, label, SQL, fournisseur/LLM, ordre ou changement de production ; pas de holdout neuf ou de parité live.',
        'Archives : `'+str(ROOT)+'`. Voir comparaisons annuelles, fenêtres de baisse, basculements et reçus de dimensionnement.']
    message='\n'.join(text)+'\n';(ROOT/'results.md').write_text(message,encoding='utf-8')
    marker='<!-- Q051_INTERNAL_HALF_PROTECTION_RESULTS_20261117 -->'
    for path in [DOC,Path('doc/ml/experiences_done.md')]:
        if marker not in path.read_text(encoding='utf-8'):
            with path.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+message)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,review=review['status'],production_changes=False))


def run():
    prepare()
    try:
        pending=[c for c in CASES if not (ROOT/'cases'/c/'validation.json').exists()]
        with patch.object(source,'ROOT',ROOT),patch.object(source,'__spec__',__spec__):source.launch(pending,'case',4)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','case','finish'],required=True);p.add_argument('--key');a=p.parse_args()
    if a.phase=='all':run()
    elif a.phase=='prepare':prepare()
    elif a.phase=='case':run_case(a.key)
    else:finish()
