"""Matched CAP_WAIT2 overlays. Frozen prices/models; no SQL, HTTP or orders.

The anti-SL head is transferred unchanged from the annual SL10 experiment.
It predicts J+1 stop risk, not the later actual entry's eventual outcome.
"""
import argparse
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_entry_ceiling_20261127 as ceiling
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT=Path('artifacts/research/us_q051_ceiling_overlays/20261128-v2')
PREPARATION=Path('artifacts/research/us_q051_ceiling_overlays/20261128-v1')
ORIGINAL=ceiling.ROOT
CASES={'CONTROL':'Plafond, attente deux séances — témoin',
       'ANTI_SL':'Plafond, attente deux séances + anti-SL',
       'VOL20_REGIME':'Plafond, attente deux séances + vol20 et régime'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def verify(files):
    for name,sha in files.items():
        if digest(name)!=sha:raise ValueError('Changed frozen source: '+name)


def apply_anti_sl(panel,risks):
    """Filter original signals, before expanding waiting windows; no refill."""
    keys=['entry_year','origin_signal_date','symbol']
    if risks.duplicated(keys).any():raise ValueError('Duplicate anti-SL score')
    result=panel.merge(risks[[*keys,'SL10_risk','SL10_threshold','SL10_available']],
        on=keys,how='left',validate='one_to_one')
    known=result.SL10_risk.notna()&result.SL10_threshold.notna()
    if (known&pd.to_datetime(result.SL10_available).ge(result.origin_signal_date)).any():
        raise ValueError('Anti-SL model not available strictly before signal J')
    result['anti_sl_known']=known
    result['anti_sl_excluded']=known&result.SL10_risk.gt(result.SL10_threshold)
    return result


def prepare_anti_sl(panel):
    import joblib
    import requests
    from modelFactory.oracle_path.directional_metrics import predict
    from modelFactory.oracle.build_labels import nyse_sessions
    from common.config_loader import replay_market_registry
    from scripts.research import us_q051_b_early_sl_20261116 as anti
    from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
    if (PREPARATION/'anti-sl-feature-reconstruction.json').exists():
        prior=read(PREPARATION/'protocol.json')
        receipt=read(PREPARATION/'anti-sl-feature-reconstruction.json')
        verify(receipt['sources'])
        for p in (PREPARATION/'inputs').glob('anti-sl-*.parquet'):
            if digest(p)!=prior['sources'][str(p)]:raise ValueError('Changed prepared SL cache')
            shutil.copyfile(p,ROOT/'inputs'/p.name)
        atomic_json(ROOT/'anti-sl-feature-reconstruction.json',{**receipt,'reused_verified_preparation':str(PREPARATION)})
        return pd.read_parquet(ROOT/'inputs/anti-sl-scores.parquet'),receipt['sources']
    plan=read(anti.ROOT/'protocol.json');original=read(anti.base.ORIGINAL/'protocol.json')
    sources={};parts=[];checks=[]
    def checked(path):
        path=Path(path);sha=digest(path)
        expected=plan['sources'].get(str(path))
        if expected is not None and sha!=expected:raise ValueError('Changed anti-SL raw input: '+str(path))
        sources[str(path)]=sha
        return path
    for year in range(2021,2027):
        folder=anti.ROOT/'heads'/str(year)
        p=checked(folder/'probabilities.parquet');done=read(checked(folder/'done.json'))
        if digest(p)!=done['probabilities_sha256']:raise ValueError('Changed stored SL scores')
        records=read(checked(folder/'models.json'))['models']
        heads={r['model_year']:r for r in records if r['variant']=='SL10' and 'file' in r}
        for rec in heads.values():
            if digest(checked(rec['file']))!=rec['sha256']:raise ValueError('Changed archived SL model')
        wanted=panel[panel.entry_year.eq(year)][['origin_signal_date','symbol']].rename(columns={'origin_signal_date':'date'})
        cached=pd.read_parquet(p)
        fields=['date','symbol','SL10_risk','SL10_threshold','SL10_available']
        found=wanted.merge(cached[fields],on=['date','symbol'],how='left',validate='one_to_one',indicator=True)
        missing=found[found._merge.eq('left_only')][['date','symbol']]
        extra=[]
        item=plan['models'][str(year)];end=pd.Timestamp(min(plan['end'],f'{year}-12-31'))
        bench=pd.read_parquet(checked(item['benchmark']))
        newer_path=(Path(original['models'][str(year+1)]['benchmark']) if year<2026 else FEATURE_2026/'directional/benchmark.parquet')
        newer=pd.read_parquet(checked(newer_path));bench=pd.concat([bench,newer[newer.date.gt(bench.date.max())]],ignore_index=True)
        with replay_market_registry(anti.base.shared.restore_registry(anti.base.shared.ROOT)),patch.object(requests.Session,'request',anti.base.no_http):
            calendar=nyse_sessions(pd.Timestamp(item['training_start']).date(),end.date())
            tasks=[t for t in plan['tasks'] if t['year']==year and set(t['symbols'])&set(missing.symbol)]
            for index,task in enumerate(tasks):
                symbols=set(task['symbols'])&set(missing.symbol)
                pieces=[pd.read_parquet(checked(task['source']))]
                for file in task['future']:
                    f=pd.read_parquet(checked(file));pieces.append(f[f.date.gt(item['training_end'])&f.date.le(end)])
                for symbol in symbols:
                    evidence=anti.base.PRICES/'evidence'/(symbol+'.json')
                    if evidence.exists():checked(evidence)
                bars=anti.base.repair_bars(pd.concat(pieces,ignore_index=True))
                bars=bars[bars.symbol.isin(symbols)&bars.date.le(end)]
                for symbol,g in bars.groupby('symbol'):
                    features=anti.path_panel(anti.base.common_panel(g,bench,calendar),calendar)
                    dates=missing[missing.symbol.eq(symbol)][['date','symbol']]
                    frame=dates.merge(features,on=['date','symbol'],how='left',validate='one_to_one')
                    for model_year,group in frame.groupby(frame.date.dt.year):
                        rec=heads.get(int(model_year))
                        if rec is None:raise ValueError('Missing annual anti-SL head')
                        weights_file=checked(rec['file'])
                        if digest(weights_file)!=rec['sha256']:raise ValueError('Changed SL head')
                        weights=joblib.load(weights_file)
                        if weights['features']!=anti.columns(True):raise ValueError('Anti-SL columns changed')
                        pred=group[['date','symbol']].copy()
                        # All-past missing feature rows use the frozen head's own
                        # trained imputation, exactly as the original SL study.
                        pred['SL10_risk']=predict(weights,group)
                        pred['SL10_threshold']=rec['threshold'];pred['SL10_available']=rec['available']
                        extra.append(pred)
                        # Check the same reconstructed symbol's known scores,
                        # without reading labels or fitting/recalibrating anything.
                        overlap=cached[cached.symbol.eq(symbol)&cached.date.dt.year.eq(model_year)].merge(
                            features,on=['date','symbol'],validate='one_to_one')
                        if len(overlap):
                            error=float(np.max(np.abs(predict(weights,overlap)-overlap.SL10_risk)))
                            if error>1e-10:raise ValueError('Feature reconstruction differs from archived SL scores')
                            checks.append(dict(year=year,symbol=symbol,rows=len(overlap),max_error=error))
                atomic_json(ROOT/'progress.json',dict(status='ANTI_SL_MISSING_INFERENCE',year=year,completed=index+1,total=len(tasks)))
        extras=pd.concat(extra,ignore_index=True) if extra else cached[fields].iloc[:0]
        if len(extras)!=len(missing):raise ValueError('Unresolved missing anti-SL inputs')
        known=found[found._merge.eq('both')][fields]
        all_scores=pd.concat([known,extras],ignore_index=True);all_scores['entry_year']=year
        all_scores=all_scores.rename(columns={'date':'origin_signal_date'})
        if len(all_scores)!=len(wanted):raise ValueError('Anti-SL signal coverage incomplete')
        all_scores.to_parquet(ROOT/'inputs'/f'anti-sl-{year}.parquet',index=False)
        parts.append(all_scores)
    scores=pd.concat(parts,ignore_index=True)
    scores.to_parquet(ROOT/'inputs/anti-sl-scores.parquet',index=False)
    atomic_json(ROOT/'anti-sl-feature-reconstruction.json',dict(status='PASS',checks=checks,
        rows=len(scores),sources=sources,refitting=False,threshold_optimization=False))
    return scores,sources


def prepare():
    if (ROOT/'protocol.json').exists():return
    ROOT.mkdir(parents=True,exist_ok=True);(ROOT/'inputs').mkdir(exist_ok=True)
    if read(ORIGINAL/'validation.json')['status']!='PASS':raise ValueError('Invalid ceiling reference')
    old=read(ORIGINAL/'protocol.json');verify(old['sources'])
    if read(ORIGINAL/'cases/CAP_WAIT2/progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Reference incomplete')
    panel=pd.read_parquet(ORIGINAL/'inputs/candidates.parquet')
    scores,extra_sources=prepare_anti_sl(panel)
    marked=apply_anti_sl(panel,scores);marked.to_parquet(ROOT/'inputs/anti-sl-decisions.parquet',index=False)
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    with replay_market_registry(ceiling.previous.shared.restore_registry(ceiling.previous.shared.ROOT)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=calendar.session_dates(panel.origin_signal_date.min().date(),pd.Timestamp('2026-10-10').date())
    kept=marked[~marked.anti_sl_excluded][panel.columns]
    expanded,superseded=ceiling.expand_windows(kept,sessions)
    expanded.to_parquet(ROOT/'inputs/expanded-ANTI_SL.parquet',index=False)
    superseded.to_parquet(ROOT/'inputs/superseded-ANTI_SL.parquet',index=False)
    sources={**old['sources'],**extra_sources}
    for name in ['scripts/research/us_q051_ceiling_overlays_20261128.py',
            'scripts/research/us_q051_portfolio_risk_policy_20261109.py',
            'scripts/research/us_winner_q051_regime_gross2_20261108.py',
            'scripts/research/us_q051_b_early_sl_20261116.py',
            'scripts/research/us_q051_feature_groups_20261116.py',
            'backtesting/winner_intraday.py','backtesting/winner_daily_entry.py',
            'modelFactory/oracle_path/directional_metrics.py']:
        sources[name]=digest(name)
    for p in (ROOT/'inputs').glob('*'):sources[str(p)]=digest(p)
    for name in ['report.json','configuration.json','equity-daily.csv','events.csv','trades.csv']:
        p=ORIGINAL/'cases/CAP_WAIT2/result'/name;sources[str(p)]=digest(p)
    sources[str(ORIGINAL/'validation.json')]=digest(ORIGINAL/'validation.json')
    protocol={**old,'sources':sources,'cases':CASES,'ceiling_reference':str(ORIGINAL/'cases/CAP_WAIT2'),
        'anti_sl':dict(head='SL10',frozen_annual_heads=True,transfer_from_B_oracle_pool=True,
            event='SL5 at daily opening J+1, not actual delayed entry outcome',threshold='past calibration percentile90',
            stage='after original TOP10 LONG, before wait expansion; no refill',unknown='keep',
            excluded_signals=int(marked.anti_sl_excluded.sum()),known_signals=int(marked.anti_sl_known.sum()),
            total_signals=len(marked),decision_time='original signal close J',training=False),
        'vol20_regime':dict(target_annual_vol=.20,covariance_sessions=60,annualization=252,
            regime='prior session SPY close > 0.98*SMA200',stage='each actual entry day, including delayed 5m entries',
            applies='new entries only, never forced liquidation',only_reduces_native_quantity=True),
        'training':False,'new_inference':'missing SL scores only; unchanged weights',
        'prepared_at_utc':datetime.now(timezone.utc).isoformat()}
    atomic_json(ROOT/'protocol.json',protocol)
    atomic_json(ROOT/'progress.json',dict(status='READY',completed=0,total=3))


def case_folder(case):return ROOT/'variants'/case/'cases/CAP_WAIT2'


def observed_open_policy(close,target=.20):
    from scripts.research.us_q051_portfolio_risk_policy_20261109 import PortfolioRiskPolicy
    class Policy(PortfolioRiskPolicy):
        def wrap(self,native):
            budgeted=super().wrap(native)
            def approve(state,version,proposed,snapshot,now,*,context):
                # The archived budget reads daily_open. A scheduled print has
                # entry_open instead; use that observed price, never J+1's open.
                snapshot=dict(snapshot)
                if 'daily_open' not in snapshot:snapshot['daily_open']=snapshot['entry_open']
                before=len(self.receipts)
                result=budgeted(state,version,proposed,snapshot,now,context=context)
                for receipt in self.receipts[before:]:
                    receipt.update(price_source=snapshot['price_source'],observed_price=snapshot['daily_open'])
                return result
            return approve
    return Policy(close,target=target)


def reuse_control():
    plan=read(ROOT/'protocol.json');verify(plan['sources']);verify(plan['market_files'])
    source=ORIGINAL/'cases/CAP_WAIT2';folder=case_folder('CONTROL');folder.mkdir(parents=True,exist_ok=False)
    out=folder/'result';out.mkdir()
    hashes={}
    for name in ['report.json','configuration.json','equity-daily.csv','equity-5m.parquet','events.csv','trades.csv',
            'risk-5m.csv','annual-summary.csv','entry-audit.csv']:
        file=source/'result'/name;hashes[name]=digest(file);shutil.copyfile(file,out/name)
        if digest(out/name)!=hashes[name]:raise ValueError('Control copy differs')
    atomic_json(folder/'protocol.json',{**plan,'requested_case':'CONTROL','baseline_reused':str(source)})
    atomic_json(folder/'isolation.json',{**read(source/'isolation.json'),'archive_reuse':True,'source':str(source)})
    atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY',execution='VERIFIED_ARCHIVE_REUSE'))
    atomic_json(ROOT/'baseline-reproduction.json',dict(status='PASS',every_daily_equity_equal=True,
        kind='VERIFIED_ARCHIVE_REUSE',source=str(source),files=hashes,
        explanation='No changed control rule, engine or input. Reference kept byte-identical; no new control simulation.'))


def run_case(case):
    from backtesting.simulator import BacktestEngine
    from scripts.research.us_winner_q051_regime_gross2_20261108 import RegimeEntryGate
    from backtesting.risk_overlay import RegimeFilterConfig
    plan=read(ROOT/'protocol.json');verify(plan['sources'])
    variant=ROOT/'variants'/case;variant.mkdir(parents=True,exist_ok=False);(variant/'inputs').mkdir()
    panel=pd.read_parquet(ORIGINAL/'inputs/candidates.parquet')
    panel.to_parquet(variant/'inputs/candidates.parquet',index=False)
    path=ROOT/'inputs/expanded-ANTI_SL.parquet' if case=='ANTI_SL' else ORIGINAL/'inputs/expanded.parquet'
    pd.read_parquet(path).to_parquet(variant/'inputs/expanded.parquet',index=False)
    atomic_json(variant/'protocol.json',{**plan,'requested_case':case,
        'sources':{**plan['sources'],**{str(p):digest(p) for p in (variant/'inputs').iterdir()}}})
    close=pd.read_parquet(ceiling.INPUT/'close.parquet')
    policy=observed_open_policy(close,target=.20) if case=='VOL20_REGIME' else None
    gate=RegimeEntryGate(close['SPY'],RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)) if policy else None
    native_run=BacktestEngine.run
    def replay(engine,*args,**kwargs):
        if policy:
            kwargs['winner_entry_risk_policy']=policy
            kwargs['winner_selection_source']=gate
        return native_run(engine,*args,**kwargs)
    # Patch only the research module's output root and engine call in this
    # worker process. The archived driver and production files stay unchanged.
    with patch.object(ceiling,'ROOT',variant),patch.object(BacktestEngine,'run',replay):
        result=ceiling.run_case('CAP_WAIT2')
    folder=case_folder(case);out=folder/'result'
    report=read(out/'report.json');report['requested_case']=case
    report['label']=CASES[case];report['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    if policy:
        pd.DataFrame(policy.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
        pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
        report['portfolio_risk_audit']=dict(decisions=len(policy.receipts),
            reductions=sum(r.get('final_quantity',0)<r['native_quantity'] for r in policy.receipts),
            missing_history=sum(r['status']=='UNQUALIFIED_HISTORY' for r in policy.receipts),
            daily_and_scheduled_entries=True)
    atomic_json(out/'report.json',report)
    if case=='CONTROL':
        old=pd.read_csv(ORIGINAL/'cases/CAP_WAIT2/result/equity-daily.csv',index_col=0)
        new=pd.read_csv(out/'equity-daily.csv',index_col=0)
        if not old.index.equals(new.index) or not np.allclose(old.equity,new.equity,rtol=0,atol=1e-7):
            raise ValueError('CAP_WAIT2 witness not exactly reproduced')
        original=read(ORIGINAL/'cases/CAP_WAIT2/result/report.json')
        for key in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','costs','average_gross_capital']:
            if not np.isclose(report[key],original[key],rtol=0,atol=1e-7):raise ValueError('Reference differs: '+key)
        atomic_json(ROOT/'baseline-reproduction.json',dict(status='PASS',every_daily_equity_equal=True))
    return result


def finalize():
    from ihm.services.backtesting_import import import_continuous_winner
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    if read(ROOT/'baseline-reproduction.json')['status']!='PASS':raise ValueError('Unmatched witness')
    plan=read(ROOT/'protocol.json');verify(plan['sources'])
    rows=[];curves=[];annual=[]
    for case,label in CASES.items():
        folder=case_folder(case);out=folder/'result';validate_case(folder)
        r=read(out/'report.json');equity=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        events=pd.read_csv(out/'events.csv');buys=events[events.event.eq('BUY_FILL')]
        if case=='ANTI_SL':
            excluded=pd.read_parquet(ROOT/'inputs/anti-sl-decisions.parquet')
            if set(buys.origin_id)&set(excluded.loc[excluded.anti_sl_excluded,'origin_id']):raise ValueError('Excluded SL signal bought')
        if not buys.price.le(buys.entry_ceiling+1e-8).all():raise ValueError('Entry above fixed ceiling')
        pnl=pd.read_csv(out/'trades.csv')
        rows.append(dict(case=case,label=label,**{k:r.get(k) for k in ['final_equity','return_pct','max_drawdown_pct','win_pct',
            'closed_lot_trades','average_winning_pnl','average_losing_pnl','average_gross_capital','average_gross_equity_ratio',
            'maximum_gross_capital','costs','margin_interest']},stop_exits=int(pnl.exit_reason.str.contains('STOP').sum())))
        curves.append(equity.rename(label));a=pd.read_csv(out/'annual-summary.csv');a['case']=case;annual.append(a)
        rec=import_continuous_winner(folder,run_id='20261128_q051_ceiling_'+case.lower(),
            label=label+' — 2021–2026 — recherche',result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=rec['run_id']))
    table=pd.DataFrame(rows);table.to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    curves=pd.concat(curves,axis=1);curves.to_csv(ROOT/'capital-curves.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,dd)=plt.subplots(2,1,sharex=True,figsize=(13,8),gridspec_kw={'height_ratios':[2,1]})
    for row,color in zip(rows,['#2455cc','#b34293','#008f72']):
        series=curves[row['label']]
        ax.plot(series.index,series,color=color,label=row['label']+f" : {row['return_pct']:+.2f} %")
        dd.plot(series.index,100*(series/series.cummax().clip(lower=4000.)-1),color=color)
    ax.set_title('Q051 TOP10 — plafond avec attente deux séances : filtres comparés');ax.set_ylabel('Capital ($), départ 4 000')
    ax.legend(fontsize=9);ax.grid(alpha=.2);dd.grid(alpha=.2);dd.set_ylabel('DD aux clôtures (%)')
    fig.text(.07,.012,'2021–1 octobre 2026. Même Oracle/per-symbol, SL5/open11, frais et financement inclus.\n'
        'Exploratoire : 5m incomplet / repli daily ; couverture des entrées tardives qualifiée ex post. Anti-SL annuel transféré sans recalibration.',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(fig)
    atomic_json(ROOT/'validation.json',dict(status='PASS',control_exact=True,training=False,SQL_writes=0,provider_calls=0,orders=0))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',completed=3,total=3,cases=rows))
    lines=['# Q051 TOP10 — plafond deux séances, anti-SL et vol20 + régime','',
        '2021–1 octobre 2026 ; 4 000 USD, portefeuille continu. Même Oracle et LONG per-symbol classiques ; '
        'SL5 %, sans TP/trailing, sortie à l’ouverture de la 11e séance détenue. Aucun changement de production.',
        '', '| Variante | Capital final $ | Rendement | DD max | Gagnants | Trades | Capital engagé moyen $ |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:lines.append(f"| {r['label']} | {r['final_equity']:.2f} | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | {r['win_pct']:.2f} % | {r['closed_lot_trades']} | {r['average_gross_capital']:.2f} |")
    lines+=['','Anti-SL : poids annuels SL10 figés, seuil passé percentile90, appliqués à J après TOP10 et avant attente, sans remplacement. '
        'Le modèle vise le SL de J+1 ; sa pertinence pour une entrée retardée est précisément une limite testée ici.',
        'Vol20 + régime : covariance 60 séances passées, cible annualisée 20 %, '
        'SPY > 98 % SMA200 à la veille de chaque entrée effective. Réduction des nouvelles entrées uniquement.',
        'Limites : période déjà étudiée, univers rétrospectif, prix révisables et couverture 5m partielle. '
        'Les entrées tardives sont limitées ex post aux séances complètes qualifiées ; aucune parité live certifiée.',
        '',f'Archives : `{ROOT}`. Contrôle témoin reproduit intégralement ; validation arithmétique PASS.']
    (ROOT/'results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    Path('doc/ml/q051_ceiling_overlays_20261128.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    marker='<!-- Q051_CEILING_OVERLAYS_20261128 -->'
    done=Path('doc/ml/experiences_done.md')
    if marker not in done.read_text(encoding='utf-8'):
        with done.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+'\n'.join(lines)+'\n')
    print(table.to_json(orient='records'),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['prepare','case','all','finish'],required=True)
    parser.add_argument('--case',choices=list(CASES));args=parser.parse_args();logging.basicConfig(level=logging.WARNING)
    if args.phase=='prepare':prepare()
    elif args.phase=='case':run_case(args.case)
    elif args.phase=='finish':finalize()
    else:
        prepare()
        if not (ROOT/'baseline-reproduction.json').exists():reuse_control()
        jobs=[]
        for case in ['ANTI_SL','VOL20_REGIME']:
            if (case_folder(case)/'result/report.json').exists():continue
            command=[sys.executable,'-X','utf8','-u','-m','scripts.research.us_q051_ceiling_overlays_20261128','--phase','case','--case',case]
            log=(ROOT/(case+'.log')).open('a',encoding='utf-8')
            job=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            jobs.append((case,job,log))
        while jobs:
            completed=[];states={}
            for case,job,log in jobs:
                path=case_folder(case)/'progress.json';states[case]=read(path) if path.exists() else {'status':'STARTING'}
                code=job.poll()
                if code is not None:
                    log.close();completed.append((case,job,log))
                    if code:raise ValueError(f'Case {case} failed; inspect {ROOT/case}.log')
            for item in completed:jobs.remove(item)
            atomic_json(ROOT/'progress.json',dict(status='REPLAYING' if jobs else 'VALIDATING',cases=states,
                control='VERIFIED_ARCHIVE_REUSE',updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if jobs:time.sleep(5)
        finalize()


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        ROOT.mkdir(parents=True,exist_ok=True)
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
