"""Summarize C/D against immutable lot1, with observed-price scope checks."""
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def finish_review():
    from scripts.research.us_q051_feature_groups_cd_20261116 import ROOT,REFERENCE,GROUPS,read,PRICE_EVIDENCE,provider_frame
    from scripts.research.us_q051_features173_finalize_20261116 import observed_windows
    from scripts.research.us_h10_price_readiness import FLAGGED
    from ihm.services import backtesting_registry as registry
    atomic_json(ROOT/'progress.json',dict(status='VALIDATING_AND_CONSOLIDATING'))
    plan=read(ROOT/'protocol.json')
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:raise ValueError('Sealed source changed: '+file)
    old=pd.read_csv(REFERENCE/'comparison.csv');new=pd.read_csv(ROOT/'comparison.csv')
    old_annual=pd.read_csv(REFERENCE/'annual-comparison.csv');new_annual=pd.read_csv(ROOT/'annual-comparison.csv')
    combined=pd.concat([old,new],ignore_index=True);annual=pd.concat([old_annual,new_annual],ignore_index=True)
    if combined['case'].duplicated().any():raise ValueError('Duplicate comparison case')
    new.to_csv(ROOT/'comparison-cd-only.csv',index=False)
    combined.to_csv(ROOT/'comparison.csv',index=False);annual.to_csv(ROOT/'annual-comparison.csv',index=False)
    previous=pd.read_csv(REFERENCE/'capital-curves.csv',index_col=0,parse_dates=True)
    current=pd.read_csv(ROOT/'capital-curves.csv',index_col=0,parse_dates=True)
    curves=pd.concat([previous,current],axis=1)
    if curves.columns.duplicated().any():raise ValueError('Duplicate equity curve')
    curves.to_csv(ROOT/'capital-curves.csv')
    evidence={p.stem:provider_frame(p) for p in (PRICE_EVIDENCE/'evidence').glob('*.json')}
    checks=[];reserves=[];histories=[]
    for variant in GROUPS:
        for profile in ['SIMPLE','VOL20_REGIME']:
            name=variant+'_'+profile;folder=ROOT/'variants'/variant/'cases'/name;out=folder/'result'
            t=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
            e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
            windows=observed_windows(t,events,e.index[-1].tz_localize('America/New_York')+pd.Timedelta(hours=16))
            start=pd.to_datetime(windows.entry_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
            end=pd.to_datetime(windows.exit_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
            crossed=windows.symbol.eq('DD')&start.lt('2025-11-03')&end.ge('2025-11-03')
            for i in windows.index[crossed]:reserves.append(dict(case=name,symbol='DD',reason='UNQUALIFIED_QNITY_ENTITLEMENT',entry=str(start[i].date()),exit=str(end[i].date())))
            unknown=windows.symbol.eq('TOELY')&end.ge('2026-07-13')
            for i in windows.index[unknown]:reserves.append(dict(case=name,symbol='TOELY',reason='UNSUPPORTED_ADR_BASIS',entry=str(start[i].date()),exit=str(end[i].date())))
            for symbol,g in windows.groupby('symbol'):
                if symbol not in FLAGGED:continue
                if symbol not in evidence or evidence[symbol].empty:
                    reserves.append(dict(case=name,symbol=symbol,reason='FLAGGED_WITHOUT_SIP_EVIDENCE'));continue
                known=set(evidence[symbol].date)
                for i in g.index:
                    missing=[str(day.date()) for day in e.index[(e.index>=start[i])&(e.index<=end[i])] if day not in known]
                    if missing:reserves.append(dict(case=name,symbol=symbol,reason='SIP_HOLDING_WINDOW_GAP',dates=missing))
            status='PRICE_RESERVES_REMAIN' if any(r['case']==name for r in reserves) else 'OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY'
            checks.append(dict(case=name,status=status,holding_windows=len(windows),open_lots=int(windows.open_at_end.sum())))
            histories.append((read(folder/'ihm.json')['run_id'],status))
    audit=dict(status='PRICE_RESERVES_REMAIN' if reserves else 'OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY',
        checks=checks,reserves=reserves,strict_pit=False,full_live_parity=False,entire_corpus_certified=False,
        reference_price_validation=str(REFERENCE/'price-window-validation.json'))
    atomic_json(ROOT/'price-window-validation.json',audit)
    for rid,status in histories:
        file=registry.RUNS_DIR/'run'/rid/'artifacts/report.json';r=read(file)
        r.setdefault('diagnostics',{})['feature_group_price_scope']=status
        r.setdefault('run_metadata',{})['price_scope_review']=str(ROOT/'price-window-validation.json')
        warning='Recherche : intraday partiel/repli OHLC ; prix contrôlés sur le périmètre signalé, sans certification PIT ou parité live.'
        if warning not in r.setdefault('limitations',[]):r['limitations'].append(warning)
        atomic_json(file,r)
    with registry._REGISTRY_LOCK:
        index=registry._read_history_index()
        for rid,status in histories:index[rid]['price_qualification']=status
        registry._write_history_index(index)
    history=read(ROOT/'history.json');history['reference_runs']=read(REFERENCE/'history.json')['run_ids'];history['reference_refits']=0
    atomic_json(ROOT/'history.json',history)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels={'T0':'24 — référence','A':'24 + marché','B':'24 + volatilité','C':'24 + structure de tendance','D':'24 + volumes'}
    colors={'T0':'#2563eb','A':'#15803d','B':'#9333ea','C':'#b45309','D':'#be123c'}
    fig,axes=plt.subplots(2,1,figsize=(13,10),sharex=True)
    for ax,profile in zip(axes,['SIMPLE','VOL20_REGIME']):
        for variant,label in labels.items():
            name=variant+'_'+profile;e=curves[name].dropna().copy();e.loc[pd.Timestamp('2021-01-01')]=4000.;e=e.sort_index()
            ax.plot(e.index,e,label=label,color=colors[variant])
        ax.set_title('Témoin' if profile=='SIMPLE' else 'Volatilité 20 % + régime');ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.text(.06,.01,'2021–1 octobre 2026 · 4 000 $ continus · Oracle TOP10 % → TOP10 LONG · SL5/open11 · frais inclus.\nRéférence T0/A/B conservée ; C/D ajoutés séparément. Intraday partiel, repli OHLC ; résultats exploratoires.',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=140);plt.close(fig)
    lines=['# Q051 — C/D après T0/A/B','',
        'Quatre nouveaux replays C/D terminés, comparés aux six résultats T0/A/B conservés. Aucun réentraînement de la référence.',
        '2021-01-01–2026-10-01 ; 4 000 $ continus ; TOP10 % Oracle → TOP10 LONG ; score >0,50 ; AUC calibration ≥0,50 ; sans remplacement.',
        'Entrée J+1, SL5/open11, position complète, aucun TP/trailing/confirmation/B4 ; plafond achat 1×, capacité margin 2× ; frais et financement inclus.','',
        '| Variables | Gestion | Capital final | Rendement | DD max | Gagnants | Capital engagé moyen |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in combined.itertuples():
        lines.append(f"| {labels[r.variant]} | {'Témoin' if r.profile=='SIMPLE' else 'Vol20 + régime'} | {r.final_equity:.2f} $ | {r.return_pct:+.2f} % | {r.max_drawdown_pct:.2f} % | {r.win_pct:.2f} % | {r.average_gross_capital:.2f} $ |")
    lines+=['','## Méthode et limites','',
        'C ajoute trois écarts entre moyennes mobiles (27 entrées), D quatre indicateurs de volume (28). Les deux conservent les 24 entrées exactes du compact.',
        'Pour chaque titre et année, les dates et valeurs communes sont comparées au premier lot, les signatures fit/calibration sont identiques et les probabilités T0 sont reproduites à 1e-12 près.',
        'Seule la population disposant déjà d’un modèle T0 qualifié est utilisée. Une éventuelle calibration constante de C ou D produit une abstention propre à cette variante, comptabilisée dans les audits.',
        'Les archives du premier lot sont inchangées. Les nouvelles requêtes SQL de préparation sont en lecture seule et ne remplissent pas rétroactivement ses réponses vides connues.',
        f"Qualification ciblée des fenêtres de prix C/D : {audit['status']} ; réserves : {len(reserves)}. Voir `price-window-validation.json`.",
        'L’intraday reste partiel avec repli OHLC. Univers contemporain, cours révisés et période déjà explorée : aucune certification PIT, parité live ou validation future indépendante.',
        'Aucun ordre, appel fournisseur/LLM ou changement du modèle/configuration de production.','',
        'Archives : `artifacts/research/us_q051_feature_groups/20261116-lot2-cd/`. Détails : `comparison.csv`, `annual-comparison.csv`, `capital-comparison.png`, `history.json`.']
    result='\n'.join(lines)+'\n';(ROOT/'results.md').write_text(result,encoding='utf-8')
    for file in [Path('doc/ml/q051_feature_groups_proposal_20261116.md'),Path('doc/ml/experiences_done.md')]:
        marker='<!-- Q051_FEATURE_GROUPS_CD_RESULTS_20261116 -->';prior=file.read_text(encoding='utf-8')
        if marker not in prior:
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+result)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',new_replays=4,compared_replays=len(combined),
        price_qualification=audit['status'],reference_refits=0,history_published=True,finished_at_utc=datetime.now(timezone.utc).isoformat()))
