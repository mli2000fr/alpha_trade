"""Matched risk-only follow-up for Q051/Q088; frozen 2025 tape, no providers."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import product
import argparse
import json
import logging
from pathlib import Path
import shutil
import time
import traceback

import numpy as np
import pandas as pd

from scripts.research import us_winner_ui_grid_20261107 as grid
from scripts.research.oracle_path_confirmation import exclusive_run


TAPE = grid.ROOT
ROOT = Path('artifacts/research/us_winner_risk_tradeoff/20261107-v1')
DATA = None


def build_cases(anchors):
    cases = []
    for anchor in anchors:
        for half,cap,control in product((False,True),repeat=3):
            case = deepcopy(anchor)
            case['anchor'] = anchor['name']
            case['name'] = anchor['name']+'_'+('BASE' if not any((half,cap,control)) else
                '_'.join(n for n,v in (('SIZE125',half),('GROSS1',cap),('B4DD15',control)) if v))
            case['family'] = 'MATCHED_RISK_ONLY'
            case['risk_axes'] = dict(reduce_entry_size=half,gross_entry_cap_1x=cap,b4_dd15=control)
            if half:
                case['risk'].update(risk_per_trade_pct=.0125,max_position_weight=.20)
            if cap:
                case['risk']['max_gross_exposure'] = 1.
            case['controller'] = control
            case['risk']['force_close_on_breaker'] = control
            if control:
                case['risk'].update(force_close_pct=.5,max_portfolio_drawdown_pct=.15,max_daily_loss_pct=.03)
            cases.append(case)
    return cases


def freeze(root,workers):
    plan = grid.read(TAPE/'protocol.json')
    for name,sha in plan['sources'].items():
        if grid.digest(Path(name))!=sha:
            raise ValueError('Source originale modifiée : '+name)
    manifest = grid.verify_inputs(TAPE)
    anchors = [next(c for c in plan['cases'] if c['name']==name) for name in ('Q051','Q088')]
    root.mkdir(parents=True,exist_ok=False)
    inputs = root/'inputs';inputs.mkdir()
    origins = {}
    for anchor in anchors:
        settings = grid.selection_settings(plan['reference'],anchor)
        file = TAPE/'inputs'/manifest['selections'][grid.selection_id(settings)]
        dest = inputs/f"signals-{anchor['name']}.parquet"
        shutil.copyfile(file,dest)
        if grid.digest(file)!=grid.digest(dest):
            raise ValueError('Copie de sélection différente')
        report = TAPE/'cases'/anchor['name']/'report.json'
        origins[anchor['name']] = dict(report_path=str(report),sha256=grid.digest(report),
            selected_signals=grid.read(report)['selected_signals'],signals_sha256=grid.digest(dest))
    deps = dict(plan['sources'])
    deps.update({str(Path(__file__)):grid.digest(Path(__file__)),
        str(TAPE/'protocol.json'):grid.digest(TAPE/'protocol.json'),
        str(TAPE/'inputs/manifest.json'):grid.digest(TAPE/'inputs/manifest.json')})
    frozen = dict(status='FROZEN_BEFORE_RISK_REPLAYS',created_at_utc=datetime.now(timezone.utc).isoformat(),
        tape=str(TAPE),reference=plan['reference'],cases=build_cases(anchors),sources=deps,anchors=origins,
        workers=workers,start='2025-01-01',end='2025-12-31',initial_equity=4000.,
        hypothesis='Reduce drawdown with lower entry sizing, lower gross-entry cap, B4/DD15; selection and exits unchanged',
        ranking='Report every case and return/DD Pareto per anchor; no winner promoted',
        invariants=['Same anchor candidate dates/order; same model and prices','SL5/no TP/no trailing/H10/open11',
            'Daily J+1 entry; initial fraction 1; no reinforcement','Same costs, margin financing and OHLC fallback',
            'No future-data entry exclusions or portfolio resets'],
        risk_axes=dict(entry_size=['budget2.5%/weight40%','budget1.25%/weight20%'],
                       gross_entry_cap=[2.,1.],controller=['off','B4 DD15, daily loss3%, liquidate50%']),
        limitations=['Chosen on repeatedly inspected 2025; no independent holdout',
            'DD15 is an action trigger, not a guaranteed drawdown maximum',
            'Gross-entry cap is not continuous rebalancing of existing positions',
            'Returns and DD do not scale exactly because of integer sizing, minimum notionals, capital and compounding',
            'Same mixed daily/5m coverage limitations as original grid'],
        sql_writes=False,provider_calls=0,broker_calls=0,training=False,production_changed=False)
    grid.atomic_json(root/'protocol.json',frozen)
    return frozen


def initialize(root):
    global DATA
    root = Path(root)
    grid.initialize_worker(TAPE)  # Frozen market inputs, all requests HTTP forbidden.
    DATA = dict(grid.DATA,output=root,risk_plan=grid.read(root/'protocol.json'))


def check_reproduction(report,original):
    for key in ('final_equity','return_pct','max_drawdown_pct','average_gross_capital','maximum_gross_capital',
                'costs','margin_interest','closed_lot_trades','winners','losers'):
        if not np.isclose(report[key],original[key],rtol=1e-10,atol=1e-6):
            raise ValueError('Reproduction différente : '+key)


def run_case(case):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    root = DATA['output'];folder = root/'cases'/case['name'];folder.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    try:
        with ReadOnlyReplay(folder).install():
            cfg = grid.configuration(DATA['risk_plan']['reference'],case)
            signals = pd.read_parquet(root/'inputs'/f"signals-{case['anchor']}.parquet")
            if len(signals)!=DATA['risk_plan']['anchors'][case['anchor']]['selected_signals']:
                raise ValueError('Nombre de candidatures différent de la sélection figée')
            grid.atomic_json(folder/'configuration.json',dict(case=case,risk=asdict(cfg.risk_config),
                policy=asdict(cfg.exec_config.winner_pyramiding),leverage=asdict(cfg.exec_config.leverage),
                daily_entry=cfg.winner_daily_entry_enabled,controller=cfg.winner_drawdown_controller_enabled))
            def progress(done,total,day):
                grid.atomic_json(folder/'progress.json',dict(status='RUNNING',completed=done,total=total,
                    last_date=day,elapsed_seconds=time.monotonic()-started))
            result = BacktestEngine(cfg).run(open_df=DATA['pivots']['open'],close=DATA['pivots']['close'],
                high=DATA['pivots']['high'],low=DATA['pivots']['low'],volume=DATA['pivots']['volume'],
                signals_df=signals,sector_map=DATA['sectors'],intraday_source=DATA['source'],
                winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=DATA['actions'])
            report = metrics(result,4000.)
            report.update(name=case['name'],anchor=case['anchor'],case=case,
                elapsed_seconds=time.monotonic()-started,selected_signals=len(signals),
                selected_symbols=int(signals.symbol.nunique()),sql_writes=False,provider_calls=0,broker_calls=0)
            if not any(case['risk_axes'].values()):
                original = grid.read(TAPE/'cases'/case['anchor']/'report.json')
                check_reproduction(report,original)
                report['anchor_reproduction'] = 'PASS_IDENTICAL_FINANCIAL_RESULTS'
            result.equity_curve.rename('equity').to_csv(folder/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(folder/'trades.csv',index=False)
            result.trade_events_df.to_csv(folder/'events.csv',index=False)
            grid.atomic_json(folder/'report.json',report)
            grid.atomic_json(folder/'progress.json',dict(status=report['status'],completed=250,total=250))
            return report
    except Exception as exc:
        report = dict(status='FAILED',name=case['name'],anchor=case['anchor'],error_type=type(exc).__name__,
            error=str(exc),elapsed_seconds=time.monotonic()-started)
        (folder/'traceback.txt').write_text(traceback.format_exc(),encoding='utf8')
        grid.atomic_json(folder/'report.json',report);grid.atomic_json(folder/'progress.json',report)
        return report


def consolidate(root):
    reports = [grid.read(p) for p in (root/'cases').glob('*/report.json')]
    originals = {n:grid.read(TAPE/'cases'/n/'report.json') for n in ('Q051','Q088')}
    rows = []
    keys = ('name','anchor','status','final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct',
            'average_winning_pnl','average_losing_pnl','average_winning_holding_days','average_losing_holding_days',
            'average_gross_capital','maximum_gross_capital','average_gross_equity_ratio','costs','margin_interest','error')
    for r in reports:
        row = {k:r.get(k) for k in keys}
        if r.get('return_pct') is not None:
            base = originals[r['anchor']]
            row.update(return_retained_pct=100*r['return_pct']/base['return_pct'],
                drawdown_reduction_pct=100*(1-abs(r['max_drawdown_pct'])/abs(base['max_drawdown_pct'])),
                drawdown_improvement_points=r['max_drawdown_pct']-base['max_drawdown_pct'])
        rows.append(row)
    frame = pd.DataFrame(rows).sort_values(['anchor','name'])
    frame.to_csv(root/'comparison.csv',index=False)
    lines = ['# Risque Q051/Q088 — 2025 exploratoire','',
        '| Cas | Rendement | DD max | Rendement conservé | Réduction du DD | Capital engagé moyen |',
        '|---|---:|---:|---:|---:|---:|']
    for r in frame.to_dict('records'):
        if pd.notna(r.get('return_pct')):
            lines.append(f"| {r['name']} | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | "
                f"{r['return_retained_pct']:.1f} % | {r['drawdown_reduction_pct']:.1f} % | {r['average_gross_capital']:.2f} $ |")
        else:
            lines.append(f"| {r['name']} | ÉCHEC | — | — | — | — |")
    lines += ['', 'Mêmes candidats et protections ; seule la gestion du risque change. '
        'DD15 déclenche une réaction sans garantir une perte maximale de 15 %. '
        'Paramètres choisis après observation de 2025 : résultats exploratoires, aucune promotion en production.']
    (root/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return reports


def run(root,workers):
    plan = freeze(root,workers)
    with exclusive_run(root):
        completed = [];started = time.monotonic()
        with ProcessPoolExecutor(max_workers=workers,initializer=initialize,initargs=(str(root),)) as pool:
            groups = [[c for c in plan['cases'] if not any(c['risk_axes'].values())],
                      [c for c in plan['cases'] if any(c['risk_axes'].values())]]
            for phase,cases in zip(('REPRODUCE_ANCHORS','RISK_VARIANTS'),groups):
                pending = {pool.submit(run_case,c):c['name'] for c in cases}
                while pending:
                    done,_ = wait(pending,timeout=10,return_when=FIRST_COMPLETED)
                    for future in done:
                        name = pending.pop(future);r = future.result();completed.append(r)
                        print(json.dumps({k:r.get(k) for k in ('name','status','return_pct','max_drawdown_pct','error')}),flush=True)
                    active = {}
                    for name in pending.values():
                        p = root/'cases'/name/'progress.json'
                        if p.exists():active[name] = grid.read(p)
                    grid.atomic_json(root/'progress.json',dict(status='RUNNING',phase=phase,
                        completed=len(completed),total=len(plan['cases']),workers=workers,active_cases=active,
                        elapsed_seconds=time.monotonic()-started,updated_at_utc=datetime.now(timezone.utc).isoformat()))
                if phase=='REPRODUCE_ANCHORS' and any(r['status']=='FAILED' for r in completed):
                    consolidate(root)
                    grid.atomic_json(root/'progress.json',dict(status='FAILED_ANCHOR_REPRODUCTION',completed=len(completed),total=16))
                    return
        reports = consolidate(root)
        grid.atomic_json(root/'progress.json',dict(status='COMPLETED_WITH_FAILED_CASES' if any(r['status']=='FAILED' for r in reports)
            else 'COMPLETED_EXPLORATORY',completed=len(reports),total=len(plan['cases']),
            failed=[r['name'] for r in reports if r['status']=='FAILED'],elapsed_seconds=time.monotonic()-started,
            independent_holdout=False,production_changed=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=ROOT)
    p.add_argument('--workers',type=int,default=4,choices=range(1,9))
    a = p.parse_args();run(a.output_dir,a.workers)


if __name__=='__main__':main()
