"""One frozen TOP10 B+SL10 replay, adding the existing vol20/SPY regime rules.

No training, SQL, provider calls or production changes. The older studies stay
immutable. Runtime adapters apply only inside this new replay process.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import time
from unittest.mock import patch

import pandas as pd

from scripts.research import us_q051_b_early_sl_20261116 as source
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT=Path('artifacts/research/us_q051_b_sl10_vol20_regime/20261117-v1')
SOURCE=source.ROOT
TOP5=Path('artifacts/research/us_q051_b_top5_vs_top10/20261117-v1')
CASE='SL10_VOL20_REGIME'
DOC=Path('doc/ml/q051_b_sl10_vol20_regime_20261117.md')


def read(path):return source.read(path)


def protected_configuration(original):
    def build(*args,**kwargs):
        from backtesting.risk_overlay import RegimeFilterConfig
        cfg=original(*args,**kwargs)
        cfg.risk_overlay.regime_filter=RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)
        return cfg
    return build


def protected_run(original,out):
    def run(engine,*args,**kwargs):
        from backtesting.winner_portfolio_budget import replay_protections
        if any(kwargs.get(k) is not None for k in ['winner_selection_source','winner_entry_risk_policy']):
            raise ValueError('Existing selection/risk callback: refuse double protection')
        policy,gate=replay_protections(kwargs['close'],daily_entry=True,target=.20,lookback=60,
            regime=True,sma_window=200,bear_threshold=-.02)
        kwargs.update(winner_entry_risk_policy=policy,winner_selection_source=gate)
        result=original(engine,*args,**kwargs)
        # out belongs to this case and is inside its read-only replay write scope.
        pd.DataFrame(policy.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
        pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
        atomic_json(out/'entry-protections.json',dict(target=.20,lookback=60,sma_window=200,bear_threshold=-.02,
            sizing_decisions=len(policy.receipts),regime_decisions=len(gate.receipts),daily_J1=True))
        return result
    return run


def prepare():
    if (ROOT/'protocol.json').exists():
        plan=read(ROOT/'protocol.json')
        for file,h in plan['sources'].items():
            if digest(Path(file))!=h:raise ValueError('Changed sealed source '+file)
        return plan
    ROOT.mkdir(parents=True,exist_ok=True)
    old=read(SOURCE/'protocol.json');sources=dict(old['sources'])
    for c in ['CONTROL','SL10']:
        if read(SOURCE/'cases'/c/'validation.json')['status']!='PASS':raise ValueError('Unvalidated reference')
    for file,h in sources.items():
        if digest(Path(file))!=h:raise ValueError('Changed frozen source '+file)
    target=ROOT/'variants'/CASE/'signals.parquet';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(SOURCE/'variants/SL10/signals.parquet',target)
    if digest(target)!=digest(SOURCE/'variants/SL10/signals.parquet'):raise ValueError('Changed signal selection')
    inputs=ROOT/'inputs';tape=inputs/'intraday';tape.mkdir(parents=True,exist_ok=True)
    files=dict(read(SOURCE/'inputs/manifest.json')['files'])
    for file,h in files.items():
        if digest(Path(file))!=h:raise ValueError('Changed frozen market input '+file)
    for file in (SOURCE/'inputs/intraday').iterdir():
        if file.is_file():
            copied=tape/file.name;shutil.copyfile(file,copied);files[str(copied)]=digest(copied)
    atomic_json(inputs/'manifest.json',dict(files=files,source=str(SOURCE/'inputs/manifest.json'),
        SQL_reads=0,SQL_writes=0,provider_calls=0))
    for file in [Path(__file__),Path('tests/test_q051_b_sl10_vol20_regime.py'),
                 Path('backtesting/winner_portfolio_budget.py'),Path('risk_management/portfolio_volatility.py'),
                 Path('backtesting/risk_overlay.py'),SOURCE/'protocol.json',target,
                 SOURCE/'variants/SL10/signals.parquet',SOURCE/'test-labels-and-risks.parquet']:
        sources[str(file)]=digest(file)
    for c in ['CONTROL','SL10']:
        for name in ['report.json','configuration.json','equity-daily.csv','annual-summary.csv','trades.csv']:
            file=SOURCE/'cases'/c/'result'/name;sources[str(file)]=digest(file)
    cfg=source.base.shared.configuration(old['reference_settings'],source.base.shared.CASES['Q051_050'])
    snapshot=json.loads(json.dumps(asdict(cfg),default=str))
    if snapshot!=read(SOURCE/'cases/SL10/result/configuration.json')['portfolio']:
        raise ValueError('Base portfolio changed from SL10 reference')
    plan=deepcopy(old)
    plan.update(cases=[CASE],sources=sources,source_campaign=str(SOURCE),
        study='TOP10 B + existing SL10 veto + portfolio vol20 and prior-session SPY regime',
        entry_budget=dict(target=.20,lookback=60),regime=dict(enabled=True,sma_window=200,bear_threshold=-.02),
        selection='Identical archived SL10 signals; TOP179 Oracle -> TOP10 LONG -> fixed SL10 veto; no refill',
        new_training=0,recalibrations=0,SQL_reads=0,SQL_writes=0,provider_calls=0,orders=0,
        production_changes=False,created_at_utc=datetime.now(timezone.utc).isoformat())
    plan['reference_settings']['arguments'].update(portfolio_vol_target=.20,portfolio_vol_lookback=60,
        entry_regime_filter=True,regime_sma_window=200,regime_bear_threshold=-.02)
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'selection-validation.json',dict(status='PASS',identical_SL10_signals=True,
        selected_signals=len(pd.read_parquet(target)),base_portfolio_identical=True,
        changes=['entry covariance budget 20% / 60 sessions','SPY close J > 98% SMA200 J'],no_refill=True))
    atomic_json(ROOT/'progress.json',dict(status='READY',cases=[CASE]))
    return plan


def run_case(case):
    if case!=CASE:raise ValueError('Unrequested case')
    from backtesting.simulator import BacktestEngine
    out=ROOT/'cases'/case/'result'
    build=source.base.shared.configuration
    native=BacktestEngine.run
    with patch.object(source,'ROOT',ROOT),patch.object(source.base.shared,'configuration',protected_configuration(build)),\
            patch.object(BacktestEngine,'run',protected_run(native,out)):
        source.run_case(case)


def finish():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    validate_case(ROOT/'cases'/CASE)
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',[CASE]):
        review=source.post_review(pd.read_parquet(SOURCE/'test-labels-and-risks.parquet'))
    specs=[('B seul — TOP10',SOURCE/'cases/CONTROL'),('B + anti-SL10 — TOP10',SOURCE/'cases/SL10'),
        ('B + anti-SL10 + vol20/régime — TOP10',ROOT/'cases'/CASE)]
    top5_status=read(TOP5/'progress.json').get('status')
    if top5_status!='COMPLETED_EXPLORATORY':raise ValueError('TOP5 comparison not yet complete: '+top5_status)
    for label,c in [('B seul — TOP5','B5'),('B + anti-SL10 — TOP5','SL5')]:
        folder=TOP5/'cases'/c
        if read(folder/'validation.json')['status']!='PASS':raise ValueError('Unvalidated TOP5 case')
        specs.append((label,folder))
    rows=[];curves=[];annual=[];comparison_sources={}
    for label,folder in specs:
        out=folder/'result';r=read(out/'report.json')
        metrics=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_gross_capital',
            'average_gross_equity_ratio','average_winning_pnl','average_losing_pnl','stop_exits','first_session_stop_exits']
        rows.append(dict(case=label,**{k:r.get(k) for k in metrics}))
        curves.append(pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity.rename(label))
        a=pd.read_csv(out/'annual-summary.csv');a['case']=label;annual.append(a)
        for n in ['report.json','equity-daily.csv','annual-summary.csv','trades.csv']:
            p=out/n;comparison_sources[str(p)]=digest(p)
    atomic_json(ROOT/'comparison-sources.json',comparison_sources)
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    frame=pd.concat(curves,axis=1);frame.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ax=frame.plot(figsize=(14,8),title='B / anti-SL dix séances — TOP5, TOP10 et protection volatilité/régime')
    ax.set_ylabel('Capital valorisé ($), départ 4 000');ax.grid(alpha=.2)
    ax.figure.tight_layout();ax.figure.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(ax.figure)
    text=['# B + anti-SL10 avec volatilité 20 % et régime — TOP10','',
        '2021–1er octobre 2026, 4 000 $ continus. Modèles annuels et signaux SL10 TOP10 identiques ; '
        'aucun réentraînement ni changement de seuil. Seul ajout : covariance des 60 séances antérieures '
        'pour limiter les nouveaux achats à un budget annualisé de 20 %, et SPY J > 98 % de sa moyenne '
        '200 séances pour autoriser une entrée J+1. Aucun filtre de rendement futur.',
        'Portefeuille inchangé : risque 1,25 %, poids 20 %, 20 positions, minimum 50 $, plafond achats 1×, '
        'capacité margin 2×, position entière, SL5 %, sans TP/trailing, sortie open11, frais 8 pb par côté '
        'et financement 6,5 % annualisé. Sans B4/DD ni pause100.', '',
        '| Cas | Capital final | Rendement | DD max | Gagnants | Trades |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        text.append(f"| {r['case']} | {r['final_equity']:.2f} $ | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | {r['win_pct']:.2f} % | {r['closed_lot_trades']} |")
    text+=['',f"Revue des nouvelles détentions : {review['status']}. Prix : {len(review['price_reserves'])} réserves ; "
        f"labels première séance : {review['event_label_mismatches']}/{review['known_event_labels']} écarts.",
        'La volatilité cible n’est pas un plafond de drawdown. Les règles limitent les nouvelles entrées, '
        'sans liquider les positions existantes. Intraday partiel/repli OHLC, univers contemporain et prix révisés ; '
        'périodes déjà explorées, sans certification PIT ni parité live. Aucun changement de production.',
        'Archives : `'+str(ROOT)+'` ; courbes, comparaison annuelle et reçus des décisions dans ce dossier.']
    message='\n'.join(text)+'\n';(ROOT/'results.md').write_text(message,encoding='utf-8')
    marker='<!-- Q051_B_SL10_VOL20_REGIME_RESULTS_20261117 -->'
    for file in [DOC,Path('doc/ml/experiences_done.md')]:
        if marker not in file.read_text(encoding='utf-8'):
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+message)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,review=review['status'],production_changes=False))


def run():
    prepare()
    try:
        pending=[] if (ROOT/'cases'/CASE/'validation.json').exists() else [CASE]
        with patch.object(source,'ROOT',ROOT),patch.object(source,'__spec__',__spec__):source.launch(pending,'case',1)
        while read(TOP5/'progress.json').get('status')!='COMPLETED_EXPLORATORY':
            state=read(TOP5/'progress.json')
            if state.get('status')=='FAILED':raise ValueError('TOP5 comparison failed; protected result preserved')
            atomic_json(ROOT/'progress.json',dict(status='WAITING_FOR_TOP5_COMPARISON',protected_case='COMPLETED_EXPLORATORY',
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            time.sleep(10)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','case','finish'],required=True);p.add_argument('--key');a=p.parse_args()
    if a.phase=='all':run()
    elif a.phase=='prepare':prepare()
    elif a.phase=='case':run_case(a.key)
    else:finish()
