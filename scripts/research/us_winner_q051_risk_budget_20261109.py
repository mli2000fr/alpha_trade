"""Matched Q051_050 H10: smaller sizing, portfolio vol budget, vol plus regime.

Reuse sealed market and signal archives read-only; no inference/provider/orders.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from multiprocessing import get_context
import sys
from unittest.mock import patch
from dataclasses import replace

import pandas as pd
import numpy as np
import requests

from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

BASE = shared.ROOT
from scripts.research.us_winner_q051_regime_gross2_20261108 import RegimeEntryGate
from scripts.research.us_q051_portfolio_risk_policy_20261109 import PortfolioRiskPolicy

ROOT = Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1')
VARIANTS = ('STATIC75', 'VOL20', 'REGIME_VOL20')
ALL_VARIANTS = ('BASELINE', *VARIANTS)
CASE_LABELS = dict(STATIC75='risque 0,90 %, poids 15 %, plafond 0,75×',
    VOL20='budget volatilité portefeuille 20 %', REGIME_VOL20='budget volatilité 20 % + régime SPY')


def matched_configuration(plan, saved, variant):
    if variant not in ALL_VARIANTS:
        raise ValueError('Variante inconnue')
    case = deepcopy(plan['cases']['Q051_050'])
    baseline = shared.configuration(plan['reference'], case)
    normalized = json.loads(json.dumps(asdict(baseline), default=str))
    if normalized != saved['portfolio']:
        raise ValueError('Configuration du témoin Q051_050 non reproduite')
    cfg = shared.configuration(plan['reference'], case)
    if variant == 'STATIC75':
        cfg.risk_config = replace(cfg.risk_config,risk_per_trade_pct=.009,max_position_weight=.15,max_gross_exposure=.75)
    if variant == 'REGIME_VOL20':
        from backtesting.risk_overlay import RegimeFilterConfig
        cfg.risk_overlay.regime_filter = RegimeFilterConfig(enabled=True, sma_window=200, bear_threshold=-.02)
    expected = deepcopy(normalized)
    if variant == 'REGIME_VOL20':
        expected['risk_overlay']['regime_filter']['enabled'] = True
    if variant == 'STATIC75':
        expected['risk_config'].update(risk_per_trade_pct=.009,max_position_weight=.15,max_gross_exposure=.75)
    if json.loads(json.dumps(asdict(cfg), default=str)) != expected:
        raise ValueError('Différence hors protection de risque préspécifiée')
    if cfg.winner_drawdown_controller_enabled or cfg.risk_config.force_close_on_breaker:
        raise ValueError('Les deux variantes doivent rester sans B4/DD15')
    case.update(gross=cfg.risk_config.max_gross_exposure,risk_per_trade_pct=cfg.risk_config.risk_per_trade_pct,
        max_position_weight=cfg.risk_config.max_position_weight,risk_variant=variant)
    return case, cfg


def daily_metrics(curve,initial=4000.):
    return dict(final_equity=float(curve.iloc[-1]),return_pct=100*(float(curve.iloc[-1])/initial-1),
        daily_max_drawdown_pct=float(100*(curve/curve.cummax().clip(lower=initial)-1).min()))


def run_case(root, variant):
    root = Path(root)
    from backtesting.simulator import BacktestEngine, BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry

    root.mkdir(parents=True, exist_ok=False)
    out = root/'result'
    out.mkdir()
    atomic_json(root/'progress.json', dict(status='VERIFYING_FROZEN_INPUTS'))
    try:
        plan = shared.read(BASE/'protocol.json')
        for file, sha in plan['sources'].items():
            if digest(Path(file)) != sha:
                raise ValueError('Source de moteur modifiée : '+file)
        manifest = shared.read(BASE/'inputs/manifest.json')
        for file, sha in manifest['files'].items():
            if digest(BASE/'inputs'/file) != sha:
                raise ValueError('Entrée figée modifiée : '+file)
        saved = shared.read(BASE/'cases/Q051_050/result/configuration.json')
        case, cfg = matched_configuration(plan, saved, variant)
        signals_path = BASE/'inputs/signals-Q051_050.parquet'
        signals = pd.read_parquet(signals_path)
        baseline = shared.read(BASE/'cases/Q051_050/result/report.json')
        if len(signals) != baseline['selected_signals']:
            raise ValueError('Candidatures différentes du témoin')
        reference = deepcopy(plan['reference'])
        reference['risk'] = asdict(cfg.risk_config)
        reference['arguments'].update(top_n=179, per_symbol_top_long=5,
            per_symbol_min_long_probability=.5, per_symbol_min_long_auc=.5,
            drawdown_controller=False)
        reference['drawdown_controller'] = {'enabled': False}
        reference['per_symbol_selection'] = shared.settings(case, 1790).snapshot()
        protocol = {**plan, 'reference': reference, 'profile': case,
            'case': 'Q051_050_'+variant, 'baseline_root': str(BASE),
            'baseline_report_sha256': digest(BASE/'cases/Q051_050/result/report.json'),
            'signals_sha256': digest(signals_path), 'baseline_inputs_manifest_sha256': digest(BASE/'inputs/manifest.json'),
            'requested_variant': variant,
            'portfolio_risk_policy': dict(target_annual_vol=.20 if variant in ('VOL20','REGIME_VOL20') else None,
                covariance_sessions=60,annualization=252,prior_session_only=True,
                max_quantity='native first, then portfolio covariance root, then native again',
                affects='new entries only; no forced sale of held lots',never_increases_native_quantity=True),
            'regime_execution': 'prior_SPY_close > 0.98*SMA200; new entries only' if variant == 'REGIME_VOL20' else None,
            'research_sources':{str(Path(__file__)):digest(Path(__file__)),
                'scripts/research/us_q051_portfolio_risk_policy_20261109.py':digest(Path('scripts/research/us_q051_portfolio_risk_policy_20261109.py'))},
            'replay_command': [sys.executable, '-m', 'scripts.research.us_winner_q051_risk_budget_20261109', '--output-dir', str(root.parent)],
            'started_at_utc': datetime.now(timezone.utc).isoformat()}
        atomic_json(root/'protocol.json', protocol)
        atomic_json(out/'configuration.json', dict(profile=case, portfolio=asdict(cfg)))
        pivots, sectors, actions = shared.market_data(BASE)
        gate = RegimeEntryGate(pivots['close']['SPY'], cfg.risk_overlay.regime_filter) if variant == 'REGIME_VOL20' else None
        risk_policy = PortfolioRiskPolicy(pivots['close'],target=.20 if variant in ('VOL20','REGIME_VOL20') else None)
        def no_http(*args, **kwargs):
            raise ValueError('HTTP interdit dans le replay figé')
        with ReadOnlyReplay(root).install(), replay_market_registry(shared.restore_registry(BASE)), patch.object(requests.Session, 'request', no_http),risk_policy.install():
            def progress(done, total, day):
                state = dict(status='REPLAYING_CONTINUOUS', completed=done, total=total, last_date=str(day))
                atomic_json(root/'progress.json', state)
                atomic_json(out/'progress.json', state)
            result = BacktestEngine(cfg).run(open_df=pivots['open'], close=pivots['close'],
                high=pivots['high'], low=pivots['low'], volume=pivots['volume'], signals_df=signals,
                sector_map=sectors.set_index('symbol').sector.to_dict(), intraday_source=shared.FrozenPrices(BASE),
                winner_research_assumptions=True, winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'), winner_selection_source=gate)
            if gate is not None:
                pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv', index=False)
            pd.DataFrame(risk_policy.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet', index=False)
            result.closed_trades_df.to_csv(out/'trades.csv', index=False)
            result.trade_events_df.to_csv(out/'events.csv', index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv', index=False)
            report = metrics(result, 4000.)
            report.update(daily_metrics(result.equity_curve))
            annual = []
            opening = 4000.
            for year in sorted(result.equity_curve.index.year.unique()):
                curve = result.equity_curve[result.equity_curve.index.year == year]
                trades = result.closed_trades_df
                closed = trades[pd.to_datetime(trades.exit_date, utc=True).dt.year.eq(year)] if len(trades) else trades
                marks = result.intraday_equity_curve
                part = BacktestResult(equity_curve=curve, closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp, utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay': dict(status=report['status'], full_live_parity=False)})
                row = metrics(part, opening)
                row.update(year=int(year), model=plan['annual_models'][str(year)]['batch_id'])
                annual.append(row)
                opening = float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv', index=False)
            report.update(case='Q051_050_'+variant, profile=case, annual_models=plan['annual_models'],
                annual_reset=False, selected_signals=len(signals), provider_calls=0, broker_calls=0,
                SQL_writes=0, strict_pit=False, finished_at_utc=datetime.now(timezone.utc).isoformat())
            if gate is not None:
                report['regime_filter_audit'] = dict(decisions=len(gate.receipts),
                    blocked_sessions=sum(not r['entry_allowed'] for r in gate.receipts),
                    blocked_candidates=sum(r['blocked_candidates'] for r in gate.receipts))
            report['portfolio_risk_audit'] = dict(target=risk_policy.target,decisions=len(risk_policy.receipts),
                missing_history=sum(r['status']=='UNQUALIFIED_HISTORY' for r in risk_policy.receipts),
                reductions=sum(r.get('final_quantity',0)<r['native_quantity'] for r in risk_policy.receipts),
                entry_only=True,held_position_liquidation=False)
            atomic_json(out/'report.json', report)
            keys = ['final_equity', 'return_pct', 'max_drawdown_pct', 'daily_max_drawdown_pct','closed_lot_trades', 'win_pct', 'average_gross_capital']
            baseline.update(daily_metrics(pd.read_csv(BASE/'cases/Q051_050/result/equity-daily.csv',index_col=0,parse_dates=True).equity))
            pd.DataFrame([dict(case='Q051_050_BASELINE', **{k: baseline[k] for k in keys}),
                dict(case='Q051_050_'+variant, **{k: report[k] for k in keys})]).to_csv(root/'comparison.csv', index=False)
            atomic_json(root/'progress.json', dict(status='COMPLETED_EXPLORATORY'))
        return dict(variant=variant, folder=str(root), report={k: report[k] for k in keys})
    except Exception as exc:
        atomic_json(root/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


def run(root):
    root.mkdir(parents=True, exist_ok=False)
    atomic_json(root/'request.json', dict(variants=list(VARIANTS), baseline=str(BASE),
        created_at_utc=datetime.now(timezone.utc).isoformat(), regime_rule='SPY prior close > 98% of SMA200',
        initial_equity_USD=4000., static_case=dict(budget=.009,max_weight=.15,gross=.75),
        vol_cases=dict(target=.20,lookback=60,annualization=252,entry_only=True,no_B4=True),
        B4_enabled=False, market_prices_and_models='UNCHANGED_FROZEN_BASELINE',
        criterion='Maximize return among cases with daily DD magnitude <= same-period SPY daily DD; exploratory, no guaranteed future cap',
        sources={str(Path(__file__)): digest(Path(__file__)),
            'scripts/research/us_q051_portfolio_risk_policy_20261109.py':digest(Path('scripts/research/us_q051_portfolio_risk_policy_20261109.py'))}))
    results = []
    failures = []
    atomic_json(root/'progress.json', dict(status='VALIDATING_BASELINE',completed=0,total=3))
    validation=run_case(str(root/'BASELINE'),'BASELINE')
    actual=shared.read(root/'BASELINE/result/report.json')
    expected=shared.read(BASE/'cases/Q051_050/result/report.json')
    for key in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','margin_interest','average_gross_capital']:
        if not np.isclose(actual[key],expected[key],rtol=1e-10,atol=1e-6):
            raise ValueError('Baseline with inactive research hook differs: '+key)
    atomic_json(root/'baseline-validation.json',dict(status='PASS',report=validation,
        metrics_checked=9,source_report_sha256=digest(BASE/'cases/Q051_050/result/report.json')))
    with ProcessPoolExecutor(max_workers=3, mp_context=get_context('spawn')) as pool:
        futures = {pool.submit(run_case, str(root/v), v): v for v in VARIANTS}
        atomic_json(root/'progress.json',dict(status='RUNNING_THREE_CASES',completed=0,total=3,variants=list(VARIANTS)))
        atomic_json(root/'workers-started.json',dict(variants=list(VARIANTS),workers=3))
        for future in as_completed(futures):
            variant = futures[future]
            try:
                value = future.result()
                from ihm.services.backtesting_import import import_continuous_winner
                description = CASE_LABELS[variant]
                record = import_continuous_winner(value['folder'], run_id=f'20261109_continu_Q051_050_{variant}_v1',
                    label=f'Continu H10 2021–2026 — Q051 seuils 0,50 sans B4 — {description}', result_subdir='result')
                value['ihm_run_id'] = record['run_id']
                results.append(value)
            except Exception as exc:
                failures.append(dict(variant=variant, error_type=type(exc).__name__, error=str(exc)))
            atomic_json(root/'progress.json', dict(status='RUNNING_THREE_CASES', completed=len(results)+len(failures),
                total=3, results=results, failures=failures))
    baseline = shared.read(BASE/'cases/Q051_050/result/report.json')
    baseline.update(daily_metrics(pd.read_csv(BASE/'cases/Q051_050/result/equity-daily.csv',index_col=0,parse_dates=True).equity))
    keys = ['final_equity','return_pct','max_drawdown_pct','daily_max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital']
    price_pivots=shared.market_data(BASE)[0]
    pivot=price_pivots['close']['SPY'].loc['2021-01-01':'2026-10-01']
    opening=price_pivots['open']['SPY'].loc['2021-01-01':'2026-10-01'].iloc[0]
    spy=daily_metrics(4000*pivot/opening)
    atomic_json(root/'spy-benchmark.json',dict(**spy,fees=False,dividends=False,leverage=1.,data='same frozen archive'))
    pd.DataFrame([dict(variant='BASELINE', **{k: baseline[k] for k in keys}),
        *[dict(variant=r['variant'], **r['report']) for r in results]]).to_csv(root/'comparison.csv', index=False)
    eligible=[r for r in results if r['report']['daily_max_drawdown_pct']>=spy['daily_max_drawdown_pct']]
    report = dict(status='COMPLETED_EXPLORATORY' if not failures else 'INCOMPLETE_CASES', results=results, failures=failures,
        spy=spy,eligible_daily_DD_not_worse_than_SPY=[r['variant'] for r in eligible],
        best_eligible_by_return=max(eligible,key=lambda r:r['report']['return_pct'])['variant'] if eligible else None,
        independent_holdout=False,provider_calls=0,broker_calls=0,SQL_writes=0)
    atomic_json(root/'report.json', report)
    atomic_json(root/'progress.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    try:run(args.output_dir)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
