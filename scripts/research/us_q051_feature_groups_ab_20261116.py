"""Single prespecified A+B feature union, unprotected Q051 witness only."""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_feature_groups_cd_20261116 as cd
from scripts.research import us_q051_feature_groups_20261116 as base
from scripts.research import us_q051_feature_groups_replay_20261116 as replay
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

REFERENCE=cd.REFERENCE
CD_ROOT=cd.ROOT
ROOT=Path('artifacts/research/us_q051_feature_groups/20261116-lot3-ab-temoin')
GROUPS={'AB':[*cd.AB['A'],*cd.AB['B']]}
read=cd.read


@contextmanager
def scope():
    with patch.object(cd,'ROOT',ROOT),patch.object(cd,'GROUPS',GROUPS):yield


def common_panel(bars,benchmark,calendar):
    # The original shared panel already contains exactly 24 + A + B columns.
    with patch.object(base,'GROUPS',cd.AB):return cd._original_common(bars,benchmark,calendar)


def publication_lock(source=None,target=None):
    """Share the NTFS byte-lock file with the ongoing C/D case publications."""
    source=Path(source) if source is not None else CD_ROOT/'history-import.lock'
    target=Path(target) if target is not None else ROOT/'history-import.lock'
    source.parent.mkdir(parents=True,exist_ok=True);target.parent.mkdir(parents=True,exist_ok=True)
    with source.open('a+b') as stream:
        if stream.tell()==0:stream.write(b'0');stream.flush()
    if not target.exists():os.link(source,target)
    if not os.path.samefile(source,target):raise ValueError('Publication lock must share the same file identity')


def prepare():
    if (ROOT/'protocol.json').exists():
        p=read(ROOT/'protocol.json')
        if p['sources'].get(str(Path(__file__)))!=digest(Path(__file__)):raise ValueError('Sealed AB launcher changed')
        return p
    with scope():plan=cd.prepare()
    plan.update(study='Single 33-input A+B LONG model; unprotected witness only; no score averaging',
        groups=GROUPS,case_scope=['AB_SIMPLE'],reference_root=str(REFERENCE),
        common_model_eligibility='Frozen qualified T0 cohort; AB constant calibration abstains',
        eligibility_mask='Exact original shared compact+A+B mask, unchanged',
        training_workers=2,reference_refits=0,production_changes=False)
    plan['sources'][str(Path(__file__))]=digest(Path(__file__))
    atomic_json(ROOT/'protocol.json',plan);publication_lock()
    atomic_json(ROOT/'progress.json',dict(status='READY',variant='AB',features=33,new_replays=1,reference_refits=0))
    return plan


def worker(key):
    with scope(),patch.object(cd,'common_panel',common_panel):cd.worker(key)


def launch(tasks,limit,phase):
    # Reuse the tested subprocess coordinator but dispatch this module.
    with scope(),patch.object(cd,'__spec__',__spec__):cd.launch(tasks,limit,phase)


def run_case(key):
    if key!='AB_SIMPLE':raise ValueError('Only the requested unprotected AB witness is enabled')
    publication_lock()
    with scope():cd.run_case(key)


def finish():
    from scripts.research.us_q051_features173_finalize_20261116 import observed_windows
    from scripts.research.us_h10_price_readiness import FLAGGED
    from scripts.research.us_q051_features173_sip_replay_20261116 import provider_frame
    from ihm.services import backtesting_registry as registry
    folder=ROOT/'variants/AB/cases/AB_SIMPLE';out=folder/'result'
    r=replay.validate_case(folder);t=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
    e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
    windows=observed_windows(t,events,e.index[-1].tz_localize('America/New_York')+pd.Timedelta(hours=16))
    start=pd.to_datetime(windows.entry_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    end=pd.to_datetime(windows.exit_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    reserves=[];evidence={p.stem:provider_frame(p) for p in (cd.PRICE_EVIDENCE/'evidence').glob('*.json')}
    cross=windows.symbol.eq('DD')&start.lt('2025-11-03')&end.ge('2025-11-03')
    for i in windows.index[cross]:reserves.append(dict(symbol='DD',reason='UNQUALIFIED_QNITY_ENTITLEMENT',entry=str(start[i].date()),exit=str(end[i].date())))
    unknown=windows.symbol.eq('TOELY')&end.ge('2026-07-13')
    for i in windows.index[unknown]:reserves.append(dict(symbol='TOELY',reason='UNSUPPORTED_ADR_BASIS',entry=str(start[i].date()),exit=str(end[i].date())))
    for symbol,g in windows.groupby('symbol'):
        if symbol not in FLAGGED:continue
        if symbol not in evidence or evidence[symbol].empty:
            reserves.append(dict(symbol=symbol,reason='FLAGGED_WITHOUT_SIP_EVIDENCE'));continue
        known=set(evidence[symbol].date)
        for i in g.index:
            missing=[str(day.date()) for day in e.index[(e.index>=start[i])&(e.index<=end[i])] if day not in known]
            if missing:reserves.append(dict(symbol=symbol,reason='SIP_HOLDING_WINDOW_GAP',dates=missing))
    plan=read(ROOT/'protocol.json')
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:raise ValueError('Sealed source changed: '+file)
    price_status='PRICE_RESERVES_REMAIN' if reserves else 'OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY'
    atomic_json(ROOT/'validation.json',dict(status='ARITHMETIC_CHECKS_PASS_RESEARCH_ONLY',price_scope=price_status,
        reserves=reserves,holding_windows=len(windows),open_lots=int(windows.open_at_end.sum()),reference_refits=0,
        strict_pit=False,full_live_parity=False,entire_corpus_certified=False))
    columns=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl']
    row=dict(case='AB_SIMPLE',variant='AB',profile='SIMPLE',**{k:r.get(k) for k in columns})
    control=pd.read_csv(REFERENCE/'comparison.csv');control=control[control.profile.eq('SIMPLE')]
    combined=pd.concat([control,pd.DataFrame([row])],ignore_index=True);combined.to_csv(ROOT/'comparison.csv',index=False)
    old_annual=pd.read_csv(REFERENCE/'annual-comparison.csv');old_annual=old_annual[old_annual['case'].isin(control['case'])]
    new_annual=pd.read_csv(out/'annual-summary.csv');new_annual['case']='AB_SIMPLE'
    pd.concat([old_annual,new_annual],ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    old_curves=pd.read_csv(REFERENCE/'capital-curves.csv',index_col=0,parse_dates=True)[list(control['case'])]
    curves=pd.concat([old_curves,e.rename('AB_SIMPLE')],axis=1);curves.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels={'T0_SIMPLE':'24 — référence','A_SIMPLE':'24 + marché','B_SIMPLE':'24 + volatilité','AB_SIMPLE':'24 + marché + volatilité'}
    plot=curves.rename(columns=labels);plot.loc[pd.Timestamp('2021-01-01')]=4000.;plot=plot.sort_index()
    ax=plot.plot(figsize=(13,7),title='Q051 témoin — référence / A / B / A+B')
    ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2)
    ax.figure.text(.06,.01,'2021–1 octobre 2026 · 4 000 $ · TOP10 % Oracle → TOP10 LONG · SL5/open11 · frais inclus.\nSans vol20 ni régime ni B4. Références conservées ; intraday partiel/repli OHLC ; résultats exploratoires.',fontsize=9)
    ax.figure.tight_layout(rect=(0,.06,1,1));ax.figure.savefig(ROOT/'capital-comparison.png',dpi=140);plt.close(ax.figure)
    rid=read(folder/'ihm.json')['run_id'];file=registry.RUNS_DIR/'run'/rid/'artifacts/report.json';report=read(file)
    report.setdefault('diagnostics',{})['feature_group_price_scope']=price_status
    report.setdefault('run_metadata',{})['price_scope_review']=str(ROOT/'validation.json');atomic_json(file,report)
    atomic_json(ROOT/'history.json',dict(status='PUBLISHED',run_ids=[rid],reference_cases=list(control['case'])))
    lines=['# Q051 témoin — ajout conjoint de A et B','',
        'Un seul nouveau modèle LONG à 33 variables : les 24 entrées exactes + les quatre variables marché A + les cinq variables volatilité B.',
        'Aucune moyenne des scores existants et aucune addition des rendements. Modèles annuels passés, même Oracle, cohorte T0, dates fit/calibration et seuils.',
        '2021–1er octobre 2026, 4 000 $ continus, TOP10 % Oracle → TOP10 LONG, score >0,50/AUC calibration ≥0,50 ; SL5/open11 ; sans TP/trailing/confirmation/B4/vol20/régime ; plafond achat 1×, capacité margin 2× ; frais inclus.','',
        '| Modèle | Capital final | Rendement | DD max | Gagnants | Trades |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for x in combined.itertuples():lines.append(f"| {labels[x.case]} | {x.final_equity:.2f} $ | {x.return_pct:+.2f} % | {x.max_drawdown_pct:.2f} % | {x.win_pct:.2f} % | {x.closed_lot_trades} |")
    lines+=['',f'Contrôle de prix ciblé : {price_status}, réserves : {len(reserves)}.',
        'Les références T0/A/B et le lot C/D ne sont pas modifiés. Intraday partiel avec repli OHLC, univers contemporain, prix révisés et période déjà explorée ; aucune certification PIT ou parité live.',
        'Aucun ordre, appel fournisseur/LLM, écriture SQL ou changement de production.',
        'Archives : `artifacts/research/us_q051_feature_groups/20261116-lot3-ab-temoin/`. Détails : `comparison.csv`, `annual-comparison.csv`, `validation.json`, `capital-comparison.png`.']
    text='\n'.join(lines)+'\n';(ROOT/'results.md').write_text(text,encoding='utf-8')
    for path in [Path('doc/ml/q051_feature_groups_proposal_20261116.md'),Path('doc/ml/experiences_done.md')]:
        s=path.read_text(encoding='utf-8');marker='<!-- Q051_FEATURE_GROUPS_AB_RESULTS_20261116 -->'
        if marker not in s:
            with path.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+text)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',new_replays=1,reference_refits=0,
        price_scope=price_status,history_published=True,finished_at_utc=datetime.now(timezone.utc).isoformat()))


def run():
    plan=prepare()
    try:
        pending=[t['key'] for t in plan['tasks'] if not (ROOT/'jobs'/t['key']/'done.json').exists()]
        launch(pending,2,'worker')
        with patch.object(base,'ROOT',ROOT),patch.object(base,'GROUPS',GROUPS):base.assemble()
        with scope():cd.prepare_market()
        if not (ROOT/'variants/AB/cases/AB_SIMPLE/ihm.json').exists():launch(['AB_SIMPLE'],1,'case')
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','prepare','worker','case'],required=True);parser.add_argument('--key')
    args=parser.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='worker':worker(args.key)
    else:run_case(args.key)
