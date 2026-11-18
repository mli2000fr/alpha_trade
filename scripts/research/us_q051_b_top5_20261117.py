"""TOP5 B / TOP5 B+SL10 against the two immutable TOP10 replays.

Reuse models, calibrated SL cutoffs, daily/5m tapes and native replay. No fit,
provider/LLM calls, SQL access, orders or production configuration changes.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_b_early_sl_20261116 as source
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_b_top5_vs_top10/20261117-v1')
SOURCE=source.ROOT
NEW_CASES=['B5','SL5']


def read(p):return source.read(p)


def top_long_before_filter(signals,count=5):
    """Retain the pre-threshold LONG rank, never refill a rejected TOP5 slot."""
    if type(count) is not int or count<1:raise ValueError('Positive TOP count required')
    if 'long_rank' not in signals:raise ValueError('Original pre-threshold LONG rank required')
    a=signals.copy()
    if a.duplicated(['trade_date','symbol']).any():raise ValueError('Duplicate signal')
    rank=pd.to_numeric(a.long_rank,errors='coerce')
    if rank.isna().any() or rank.lt(1).any():raise ValueError('Invalid LONG rank')
    return a[rank.le(count)].copy()


def keys(frame):
    return frame[['trade_date','symbol','rank']].sort_values(['trade_date','rank','symbol']).reset_index(drop=True)


def prepare():
    if (ROOT/'protocol.json').exists():
        p=read(ROOT/'protocol.json')
        if p['sources'][str(Path(__file__))]!=digest(Path(__file__)):raise ValueError('Sealed launcher changed')
        return p
    ROOT.mkdir(parents=True,exist_ok=True)
    old=read(SOURCE/'protocol.json')
    if read(SOURCE/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('TOP10 study not complete')
    for case in ['CONTROL','SL10']:
        if read(SOURCE/'cases'/case/'validation.json')['status']!='PASS':raise ValueError('TOP10 case not validated')
    sources=dict(old['sources'])
    for file,h in sources.items():
        if digest(Path(file))!=h:raise ValueError('Changed frozen source '+file)
    b=pd.read_parquet(SOURCE/'variants/CONTROL/signals.parquet')
    risk=pd.read_parquet(SOURCE/'test-labels-and-risks.parquet')
    # End-to-end check of exactly the same gate before changing only N.
    reconstructed=source.meta_filter(b.rename(columns={'trade_date':'date'}),risk,'SL10')
    reconstructed=reconstructed[reconstructed.selected].rename(columns={'date':'trade_date'})
    expected=pd.read_parquet(SOURCE/'variants/SL10/signals.parquet')
    if not keys(reconstructed).equals(keys(expected)):raise ValueError('Archived TOP10 SL filter not reproduced')
    b5=top_long_before_filter(b)
    decisions=source.meta_filter(b5.rename(columns={'trade_date':'date'}),risk,'SL10')
    sl5=decisions[decisions.selected].rename(columns={'date':'trade_date'})
    for case,f in [('B5',b5),('SL5',sl5)]:
        f['selected']=True;f['side']='long';f['rank']=f['rank'].astype(int)
        folder=ROOT/'variants'/case;folder.mkdir(parents=True,exist_ok=True)
        file=folder/'signals.parquet';f.to_parquet(file,index=False);sources[str(file)]=digest(file)
    decisions.to_parquet(ROOT/'filter-decisions.parquet',index=False)
    sources[str(ROOT/'filter-decisions.parquet')]=digest(ROOT/'filter-decisions.parquet')
    inputs=ROOT/'inputs';tape=inputs/'intraday';tape.mkdir(parents=True,exist_ok=True)
    market=read(SOURCE/'inputs/manifest.json');files=dict(market['files'])
    for file,h in market['files'].items():
        if digest(Path(file))!=h:raise ValueError('Changed frozen market input '+file)
    # Only ~1.4 MB of supplementary parquet, plus receipts. Daily bars and
    # the large original tape stay shared/read-only; no new downloads/queries.
    for file in (SOURCE/'inputs/intraday').iterdir():
        if not file.is_file():continue
        target=tape/file.name;shutil.copyfile(file,target);files[str(target)]=digest(target)
    atomic_json(inputs/'manifest.json',dict(files=files,identical_to=str(SOURCE/'inputs/manifest.json'),
        SQL_reads=0,SQL_writes=0,provider_calls=0))
    for file in [Path(__file__),Path('tests/test_q051_b_top5.py'),SOURCE/'protocol.json',
                 SOURCE/'variants/CONTROL/signals.parquet',SOURCE/'variants/SL10/signals.parquet',
                 SOURCE/'test-labels-and-risks.parquet']:
        sources[str(file)]=digest(file)
    for case in ['CONTROL','SL10']:
        for name in ['report.json','configuration.json','equity-daily.csv','annual-summary.csv','trades.csv']:
            file=SOURCE/'cases'/case/'result'/name;sources[str(file)]=digest(file)
    for file in (SOURCE/'heads').glob('*/models.json'):
        sources[str(file)]=digest(file)
        for m in read(file)['models']:
            if m['variant']=='SL10' and 'file' in m:
                if digest(Path(m['file']))!=m['sha256']:raise ValueError('Changed frozen SL10 weights')
                sources[m['file']]=m['sha256']
    plan=deepcopy(old)
    plan.update(cases=NEW_CASES,sources=sources,source_campaign=str(SOURCE),study='TOP5 versus archived TOP10, B and B+SL10',
        new_training=0,recalibrations=0,reference_cases=['CONTROL','SL10'],
        selection='Same fixed TOP179 Oracle -> TOP5 by original LONG rank -> score>.50/AUCcal>=.50 -> optional existing SL10 veto; no refill',
        same_SL10_cutoffs=True,SQL_reads=0,SQL_writes=0,provider_calls=0,orders=0,production_changes=False,
        created_at_utc=datetime.now(timezone.utc).isoformat())
    plan['reference_settings']['arguments']['per_symbol_top_long']=5
    plan['reference_settings'].setdefault('per_symbol_selection',{})['long_top_n']=5
    current=source.base.shared.configuration(plan['reference_settings'],source.base.shared.CASES['Q051_050'])
    import json
    snapshot=json.loads(json.dumps(asdict(current),default=str))
    if snapshot!=read(SOURCE/'cases/CONTROL/result/configuration.json')['portfolio']:
        raise ValueError('Portfolio parameters differ from TOP10 reference')
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'selection-validation.json',dict(status='PASS',archived_TOP10_gate_reproduced=True,
        B5_signals=len(b5),SL5_signals=len(sl5),excluded_by_SL10=int(decisions.excluded_by_sl.sum()),
        original_rank_before_thresholds=True,no_refill=True,models_and_cutoffs_unchanged=True,portfolio_identical=True))
    atomic_json(ROOT/'progress.json',dict(status='READY',cases=NEW_CASES,new_training=0))
    return plan


def run_case(case):
    if case not in NEW_CASES:raise ValueError('Unrequested case')
    with patch.object(source,'ROOT',ROOT):source.run_case(case)


def finish():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    for case in NEW_CASES:validate_case(ROOT/'cases'/case)
    with patch.object(source,'ROOT',ROOT),patch.object(source,'CASES',NEW_CASES):
        review=source.post_review(pd.read_parquet(SOURCE/'test-labels-and-risks.parquet'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    specs=[('B seul — TOP10',SOURCE/'cases/CONTROL'),('B + anti-SL10 — TOP10',SOURCE/'cases/SL10'),
        ('B seul — TOP5',ROOT/'cases/B5'),('B + anti-SL10 — TOP5',ROOT/'cases/SL5')]
    rows=[];curves=[];annual=[]
    for label,folder in specs:
        out=folder/'result';r=read(out/'report.json')
        metrics=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_gross_capital',
            'average_gross_equity_ratio','average_winning_pnl','average_losing_pnl','stop_exits','first_session_stop_exits']
        rows.append(dict(case=label,**{k:r.get(k) for k in metrics}))
        curves.append(pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity.rename(label))
        a=pd.read_csv(out/'annual-summary.csv');a['case']=label;annual.append(a)
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    frame=pd.concat(curves,axis=1);frame.to_csv(ROOT/'capital-curves.csv')
    ax=frame.plot(figsize=(13,7),title='B seul et B + anti-SL dix séances — TOP5 / TOP10')
    ax.set_ylabel('Capital valorisé ($), départ 4 000');ax.grid(alpha=.2)
    ax.figure.tight_layout();ax.figure.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(ax.figure)
    decisions=pd.read_parquet(ROOT/'filter-decisions.parquet')
    labels=pd.read_parquet(SOURCE/'test-labels-and-risks.parquet')
    audit=decisions.merge(labels[['date','symbol','first_session_sl','net_long','long_available']],on=['date','symbol'],how='left',validate='one_to_one')
    diag=[]
    for rejected,g in audit.groupby('excluded_by_sl'):
        mature=g.net_long.notna()&g.long_available.le(pd.Timestamp('2026-10-01'))
        diag.append(dict(excluded=bool(rejected),signals=len(g),known_first_session_labels=int(g.first_session_sl.notna().sum()),
            first_session_sl_pct=100*g.first_session_sl.mean(),known_net_long_labels=int(mature.sum()),
            profitable_long_labels=int(g.loc[mature,'net_long'].sum()),profitable_long_pct=100*g.loc[mature,'net_long'].mean()))
    pd.DataFrame(diag).to_csv(ROOT/'filter-diagnostics.csv',index=False)
    text=['# B seul / B + anti-SL10 — TOP5 contre TOP10','',
        '2021–1er octobre2026,4000$ continus, TOP10% Oracle inchangé, mêmes modèles et seuils calibrés. '
        'Seul le TOP LONG passe de10 à5, avant le filtre anti-SL et sans remplacement. '
        'SL5/open11, entrée J+1, mêmes frais/financement et portefeuille ; sans vol20/régime/B4/pause100.',
        'Les deux TOP10 sont les archives validées, sans recalcul ni modification.','',
        '| Cas | Capital final | Rendement | DD max | Gagnants | Trades | SL première séance |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:text.append(f"| {r['case']} | {r['final_equity']:.2f}$ | {r['return_pct']:+.2f}% | {r['max_drawdown_pct']:.2f}% | {r['win_pct']:.2f}% | {r['closed_lot_trades']} | {r['first_session_stop_exits']} |")
    text+=['',f"Revue des nouvelles détentions : {review['status']}. Prix : {len(review['price_reserves'])} réserves ; "
        f"labels première séance : {review['event_label_mismatches']}/{review['known_event_labels']} écarts.",
        'Intraday partiel/repli OHLC, univers contemporain, données et périodes déjà explorées ; recherche sans certification PIT ni parité live. '
        'Les labels gagnants écartés sont des occasions théoriques, pas des trades réellement exécutés. '
        'Aucun ordre ou changement de production.',
        'Archives : `'+str(ROOT)+'`. Voir `comparison.csv`, `annual-comparison.csv`, `filter-diagnostics.csv`, `capital-comparison.png`.']
    message='\n'.join(text)+'\n';(ROOT/'results.md').write_text(message,encoding='utf-8')
    marker='<!-- Q051_B_TOP5_VS_TOP10_RESULTS_20261117 -->'
    for file in [Path('doc/ml/q051_b_top5_20261117.md'),Path('doc/ml/experiences_done.md')]:
        if marker not in file.read_text(encoding='utf-8'):
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+message)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,review=review['status'],production_changes=False))


def run():
    prepare()
    try:
        pending=[c for c in NEW_CASES if not (ROOT/'cases'/c/'validation.json').exists()]
        with patch.object(source,'ROOT',ROOT),patch.object(source,'__spec__',__spec__):source.launch(pending,'case',2)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['all','prepare','case','finish'],required=True);p.add_argument('--key');a=p.parse_args()
    if a.phase=='all':run()
    elif a.phase=='prepare':prepare()
    elif a.phase=='case':run_case(a.key)
    else:finish()
