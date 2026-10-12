"""Frozen LONG model comparison, explicit TP/SL grid; no fit, SQL write or broker order."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
from functools import partial
import json
import logging
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from common.config_loader import load_config
from execution_engine.models import IntentRole
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_fixed_stop import fixed_stop_protections
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import SECTORS, freeze_candidates, read
from scripts.research.us_oracle_barrier_comparison_summary import portfolio_periods
from scripts.research.us_oracle_merger_ledger import MergerLedger
from service.market import parse_market_regimes

PROFILES = (
    ('REFERENCE_TP20_SL7', .20, .07),
    ('TP10_SL10', .10, .10),
    ('TP20_SL10', .20, .10),
    ('TP10_SL7', .10, .07),
    ('TP20_SL5', .20, .05),
    ('TP25_SL7', .25, .07),
)


def parametric_protections(protection, *, tp_pct, sl_pct):
    if any(isinstance(v, bool) or not math.isfinite(v) or not 0 < v < 1 for v in (tp_pct, sl_pct)):
        raise ValueError('Positive TP/SL fractions below one required')
    result = fixed_stop_protections(protection, sl_pct)
    signals, frame, orders = (result.signals_df.copy(), result.protection_frame.copy(),
                              result.order_lifecycle_frame.copy())
    if not signals.empty:
        anchors = signals.set_index('symbol').fill_price.astype(float)*(1+tp_pct)
        if not anchors.index.is_unique or not np.isfinite(anchors).all() or anchors.le(0).any():
            raise ValueError('Invalid TP anchors')
        for f in (signals, frame):
            if not f.empty:
                f['replay_take_profit_price'] = f.symbol.map(anchors)
        if not orders.empty:
            mask = orders.intent_role.eq(IntentRole.TAKE_PROFIT)
            orders.loc[mask, 'limit_price'] = orders.loc[mask, 'symbol'].map(anchors)
    return replace(result, signals_df=signals, protection_frame=frame,
        order_lifecycle_frame=orders, diagnostics=dict(result.diagnostics,
            research_take_profit_pct=tp_pct, research_initial_stop_pct=sl_pct,
            take_profit_unchanged=False, research_trailing_enabled=False))


class GridLedger(MergerLedger):
    def __init__(self, *args, tp_pct, sl_pct, **kwargs):
        if any(isinstance(v, bool) or not math.isfinite(v) or not 0 < v < 1 for v in (tp_pct, sl_pct)):
            raise ValueError('Invalid TP/SL')
        self.tp_pct, self.sl_pct = tp_pct, sl_pct
        super().__init__(*args, **kwargs)

    def _build_entry_protections(self, phase3, *, execution_config):
        # Deliberately skip the old fixed 20/7 wrapper. Both arms get the same
        # requested protection levels, anchored to the ACTUAL next-open fill.
        native = OraclePortfolioLedger._build_entry_protections(self, phase3, execution_config=execution_config)
        return parametric_protections(native, tp_pct=self.tp_pct, sl_pct=self.sl_pct)


def case_key(case):
    year, count, arm, profile, tp, sl = case
    return f'{year}-TOP{count}-{arm}-{profile}'


_CACHE = None


def worker_init(inputs):
    global _CACHE
    prices = pd.read_parquet(Path(inputs)/'prices.parquet')
    scores = pd.read_parquet(Path(inputs)/'scores.parquet')
    original = read(Path(read(Path(inputs)/'input-protocol.json')['source'])/'protocol.json')
    calendar = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp(original['as_of']).date())
    sectors = pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    if sectors.get('AVB') != sectors.get('EQR'):
        raise ValueError('Unqualified successor sector')
    sectors['VMRK'] = sectors['EQR']
    _CACHE = dict(prices=prices, scores=scores, calendar=calendar, sectors=sectors,
        macro=pd.read_parquet(Path(inputs)/'macro.parquet'),
        market=parse_market_regimes((load_config() or {}).get('market_regimes')))


def run_case(case, output):
    year, count, arm, profile, tp, sl = case
    root = Path(output)/case_key(case)
    root.mkdir(parents=True, exist_ok=True)
    if (root/'case-report.json').exists():
        previous = read(root/'case-report.json')
        if previous['status'] != 'FAILED':
            return previous
    candidates = freeze_candidates(_CACHE['scores'].loc[_CACHE['scores'].date.dt.year.eq(year)], count, arm)
    required = set(candidates.symbol) | {'SPY', 'VMRK'}
    subset = _CACHE['prices'].loc[_CACHE['prices'].symbol.isin(required)]
    missing = required-{'SPY'}-set(_CACHE['sectors'])
    if missing:
        raise ValueError(f'Missing candidate sector {missing}')
    calendar = _CACHE['calendar']
    cutoff = '2025-12-31' if year == 2025 else '2026-09-03'
    final = calendar[calendar <= cutoff][-1]
    end = calendar[calendar.get_loc(final)+21]
    base = dict(year=year,count=count,arm=arm,profile=profile,tp_pct=tp,sl_pct=sl,
        side='LONG', decision_cutoff=cutoff, terminal_date=str(end.date()))
    attempts = []
    for policy in ('STRICT', 'UNVALUED_RECEIVABLE'):
        destination = root/policy
        destination.mkdir(parents=True, exist_ok=True)
        frames = {key: subset.pivot(index='date', columns='symbol', values=column).reindex(calendar)
            for key,column in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
        try:
            with (destination/'stderr.log').open('a', encoding='utf-8') as log:
                logging.basicConfig(level=logging.WARNING, stream=log, force=True)
                with redirect_stderr(log), redirect_stdout(log):
                    result = run_portfolio(frames=frames, scores=candidates, sectors=_CACHE['sectors'],
                        macro=ArchivedMacro(_CACHE['macro']), market_config=_CACHE['market'],
                        policy='selected', variant='CURRENT_NO_EXPIRY', output=destination,
                        start_date=f'{year}-01-01', end_date=str(end.date()), decision_end_date=str(final.date()),
                        quality=subset[['date','symbol','is_filled','instrument_id']],
                        ledger_factory=partial(GridLedger, tp_pct=tp, sl_pct=sl, cash_policy=policy),
                        expiry_open_sessions=20, protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
        except Exception as exc:
            failure = dict(policy=policy,error_type=type(exc).__name__,error=str(exc))
            attempts.append(failure)
            atomic_json(root/'attempts.json', attempts)
            # Never paper over any other data/ledger error with a fallback.
            if policy == 'STRICT' and 'Unqualified cash-in-lieu' in str(exc):
                continue
            result = dict(base,status='FAILED',failures=attempts)
            atomic_json(root/'case-report.json', result)
            return result
        trades = pd.read_parquet(destination/'trades.parquet')
        if not trades.empty:
            signed = trades.get('direction', pd.Series('long', index=trades.index))
            if not signed.astype(str).str.lower().isin(['long','buy']).all():
                raise ValueError('Unexpected SHORT portfolio')
        if abs(result['cash_reconciliation_error']) > 1e-6:
            raise ValueError('Cash does not reconcile')
        result.update(base, cash_policy=policy, attempts=attempts,
            output=str(destination), periods=portfolio_periods(pd.read_parquet(destination/'daily.parquet'),year,cutoff),
            exit_reasons=trades.exit_reason.value_counts().to_dict() if not trades.empty else {},
            net_total_wealth_return=result['return_pct'] if result['account_wealth_complete'] else None,
            feature_units_corrected=True, probabilities_recalibrated=False,
            status='COMPLETED' if result['account_wealth_complete'] else 'SCENARIO_UNVALUED_RECEIVABLE')
        atomic_json(root/'case-report.json', result)
        return result


def report_results(output, reports, total, *, verified=False):
    complete = sum(r['status']=='COMPLETED' for r in reports)
    partial = sum(r['status']=='SCENARIO_UNVALUED_RECEIVABLE' for r in reports)
    failed = sum(r['status']=='FAILED' for r in reports)
    status = ('VERIFYING_INPUTS' if len(reports)==total and not verified else
              'COMPLETED' if complete == total else 'COMPLETED_WITH_RESERVES' if len(reports)==total and not failed
              else 'PARTIAL_FAILED' if len(reports)==total else 'RUNNING')
    result = dict(status=status,finished=len(reports),total=total,complete=complete,
        scenarios_with_unvalued_claims=partial,failed=failed,portfolios=reports,
        training=False,sql_writes=False,broker_orders=False,production_changed=False,
        parameter_grid_is_exploratory_not_holdout=True,promotion=False)
    result['input_hashes_verified_after_all_runs'] = verified
    atomic_json(output/'report.json', result)
    rows = ['# TP/SL — modèles LONG figés, features AVB corrigées', '',
        'Cohortes annuelles, mêmes prix et contraintes, sans trailing. Pas une promotion.',
        'Une créance non valorisée exclut un rendement complet du patrimoine ; voir statut.', '',
        '| Année | N | TP / SL | Modèle | À la coupe | Cohorte close | DD | Statut |',
        '| ---: | ---: | --- | --- | ---: | ---: | ---: | --- |']
    for r in sorted(reports,key=lambda r:(r['year'],r['count'],r['profile'],r['arm'])):
        if r['status']=='FAILED':
            rows.append(f"| {r['year']} | {r['count']} | {r['profile']} | {r['arm']} | — | — | — | FAILED |")
        else:
            rows.append(f"| {r['year']} | {r['count']} | {r['tp_pct']:.0%} / {r['sl_pct']:.0%} | {r['arm']} | "
                f"{r['periods']['calendar_mark_to_market_return']:+.2%} | {r['return_pct']:+.2%} | {r['max_drawdown']:.2%} | {r['status']} |")
    rows += ['', f'{complete} complets, {partial} scénarios avec réserve de créance, {failed} échecs / {total}.',
        'Les modèles restent entraînés sur leurs labels initiaux ; les nouveaux couples sont uniquement des règles de sortie.',
        'Secteurs actuels/non PIT, ajustements actuels et macro/screener non certifiés restent des réserves.']
    (output/'report.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    return result


def run(inputs, output, workers=3, smoke=False):
    output.mkdir(parents=True, exist_ok=True)
    prepared = read(inputs/'prepared.json')
    verify_hashes(inputs, prepared['files'])
    original = read(Path(read(inputs/'input-protocol.json')['source'])/'protocol.json')
    risk = frozen_backtest_config('2025-01-01', original['as_of'])
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    if json.loads(json.dumps(asdict(risk.risk_config),default=str)) != original['portfolio']['risk'] \
            or json.loads(json.dumps(asdict(market),default=str)) != original['portfolio']['market']:
        raise ValueError('Original risk/market settings changed')
    cases = [(year,n,arm,name,tp,sl) for year in (2025,2026) for n in (10,20,50)
        for arm in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG') for name,tp,sl in PROFILES]
    if smoke:
        cases = [(2026,10,arm,'REFERENCE_TP20_SL7',.20,.07)
                 for arm in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG')]
    code = [Path(__file__), Path('scripts/research/us_concentrated_live_portfolio.py'),
        Path('scripts/research/us_oracle_merger_ledger.py'), Path('backtesting/oracle_portfolio_ledger.py'),
        Path('backtesting/oracle_portfolio_session.py'), Path('config.yaml')]
    hashes = {str(p):digest(p) for p in code}
    protocol = dict(inputs=str(inputs),prepared_sha256=digest(inputs/'prepared.json'),
        source_hashes=hashes,cases=cases,smoke=smoke,profiles=PROFILES,
        entry='J+1 open',expiry='21st session open including entry',trailing=False,
        native_atr_sizing_unchanged=True,side='LONG',frozen_models=True,
        strict_first=True,unvalued_fraction_only_fallback=True,sql_writes=False,broker_orders=False)
    if (output/'protocol.json').exists() and read(output/'protocol.json') != json.loads(json.dumps(protocol,default=str)):
        raise ValueError('Grid resume protocol changed; use a new output')
    atomic_json(output/'protocol.json',protocol)
    reports, pending = [], []
    for case in cases:
        path = output/case_key(case)/'case-report.json'
        if path.exists():
            prior = read(path)
            if prior['status'] != 'FAILED':
                reports.append(prior)
                continue
            # Failed native portfolios restart completely; no ledger checkpoint resurrection.
        pending.append(case)
    atomic_json(output/'progress.json',dict(status='RUNNING',finished=len(reports),total=len(cases),workers=workers))
    # Scoped to this research process and its workers, not user/system settings.
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name] = '1'
    with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(inputs),)) as executor:
        futures = {executor.submit(run_case,c,str(output)):c for c in pending}
        for future in as_completed(futures):
            case = futures[future]
            try:
                r = future.result()
            except Exception as exc:
                r = dict(year=case[0],count=case[1],arm=case[2],profile=case[3],status='FAILED',error=str(exc))
            reports.append(r)
            result = report_results(output,reports,len(cases))
            atomic_json(output/'progress.json',dict(status=result['status'],finished=len(reports),total=len(cases),
                complete=result['complete'],reserved=result['scenarios_with_unvalued_claims'],failed=result['failed'],last=case_key(case)))
            print(f"{len(reports)}/{len(cases)} {case_key(case)} {r['status']}",flush=True)
    for path,checksum in hashes.items():
        if digest(path)!=checksum:
            raise ValueError(f'Code/config changed during grid {path}')
    verify_hashes(inputs,prepared['files'])
    result = report_results(output,reports,len(cases),verified=True)
    atomic_json(output/'progress.json',dict(status=result['status'],finished=len(reports),total=len(cases),
        complete=result['complete'],reserved=result['scenarios_with_unvalued_claims'],failed=result['failed'],
        input_hashes_verified=True))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    run(**vars(args))
