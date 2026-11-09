"""Matched Q051_050 H10 replay: enable native B4/DD15 and 50% liquidation only.

Reuse sealed market and signal archives read-only; no inference/provider/orders.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd
import requests

from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

BASE = shared.ROOT
ROOT = Path('artifacts/research/us_winner_q051_050_b4/20261108-v1')
RUN_ID = '20261108_continu_Q051_050_B4DD15_v1'


def matched_configuration(plan, saved):
    case = deepcopy(plan['cases']['Q051_050'])
    baseline = shared.configuration(plan['reference'], case)
    normalized = json.loads(json.dumps(asdict(baseline), default=str))
    if normalized != saved['portfolio']:
        raise ValueError('Configuration du témoin Q051_050 non reproduite')
    case['controller'] = True
    cfg = shared.configuration(plan['reference'], case)
    expected = deepcopy(normalized)
    expected['winner_drawdown_controller_enabled'] = True
    expected['risk_config']['force_close_on_breaker'] = True
    if json.loads(json.dumps(asdict(cfg), default=str)) != expected:
        raise ValueError('Une différence dépasse le contrôleur B4 et sa liquidation')
    risk = cfg.risk_config
    if (risk.policy != 'b4' or risk.max_portfolio_drawdown_pct != .15
            or risk.force_close_pct != .5 or risk.max_gross_exposure != 1.):
        raise ValueError('Contrat B4/DD15, liquidation 50%, plafond 1x incompatible')
    return case, cfg


def run(root):
    from backtesting.simulator import BacktestEngine, BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from ihm.services.backtesting_import import import_continuous_winner

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
        case, cfg = matched_configuration(plan, saved)
        signals_path = BASE/'inputs/signals-Q051_050.parquet'
        signals = pd.read_parquet(signals_path)
        baseline = shared.read(BASE/'cases/Q051_050/result/report.json')
        if len(signals) != baseline['selected_signals']:
            raise ValueError('Candidatures différentes du témoin')
        reference = deepcopy(plan['reference'])
        reference['risk'] = asdict(cfg.risk_config)
        reference['arguments'].update(top_n=179, per_symbol_top_long=5,
            per_symbol_min_long_probability=.5, per_symbol_min_long_auc=.5,
            drawdown_controller=True)
        reference['drawdown_controller'] = {'enabled': True}
        reference['per_symbol_selection'] = shared.settings(case, 1790).snapshot()
        protocol = {**plan, 'reference': reference, 'profile': case,
            'case': 'Q051_050_B4DD15', 'baseline_root': str(BASE),
            'baseline_report_sha256': digest(BASE/'cases/Q051_050/result/report.json'),
            'signals_sha256': digest(signals_path), 'baseline_inputs_manifest_sha256': digest(BASE/'inputs/manifest.json'),
            'only_changes': ['winner_drawdown_controller_enabled', 'risk_config.force_close_on_breaker'],
            'replay_command': [sys.executable, '-m', 'scripts.research.us_winner_q051_050_b4_20261108', '--output-dir', str(root)],
            'started_at_utc': datetime.now(timezone.utc).isoformat()}
        atomic_json(root/'protocol.json', protocol)
        atomic_json(out/'configuration.json', dict(profile=case, portfolio=asdict(cfg)))
        pivots, sectors, actions = shared.market_data(BASE)
        def no_http(*args, **kwargs):
            raise ValueError('HTTP interdit dans le replay figé')
        with ReadOnlyReplay(root).install(), replay_market_registry(shared.restore_registry(BASE)), patch.object(requests.Session, 'request', no_http):
            def progress(done, total, day):
                state = dict(status='REPLAYING_CONTINUOUS', completed=done, total=total, last_date=str(day))
                atomic_json(root/'progress.json', state)
                atomic_json(out/'progress.json', state)
            result = BacktestEngine(cfg).run(open_df=pivots['open'], close=pivots['close'],
                high=pivots['high'], low=pivots['low'], volume=pivots['volume'], signals_df=signals,
                sector_map=sectors.set_index('symbol').sector.to_dict(), intraday_source=shared.FrozenPrices(BASE),
                winner_research_assumptions=True, winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'))
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet', index=False)
            result.closed_trades_df.to_csv(out/'trades.csv', index=False)
            result.trade_events_df.to_csv(out/'events.csv', index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv', index=False)
            report = metrics(result, 4000.)
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
            report.update(case='Q051_050_B4DD15', profile=case, annual_models=plan['annual_models'],
                annual_reset=False, selected_signals=len(signals), provider_calls=0, broker_calls=0,
                SQL_writes=0, strict_pit=False, finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json', report)
            keys = ['final_equity', 'return_pct', 'max_drawdown_pct', 'closed_lot_trades', 'win_pct', 'average_gross_capital']
            pd.DataFrame([dict(case='Q051_050_BASELINE', **{k: baseline[k] for k in keys}),
                dict(case='Q051_050_B4DD15', **{k: report[k] for k in keys})]).to_csv(root/'comparison.csv', index=False)
            atomic_json(root/'progress.json', dict(status='COMPLETED_EXPLORATORY'))
        record = import_continuous_winner(root, run_id=RUN_ID,
            label='Continu H10 2021–2026 — Q051 seuils 0,50 + B4/DD15 liquidation 50 % — open11', result_subdir='result')
        atomic_json(root/'progress.json', dict(status='COMPLETED_EXPLORATORY', ihm_run_id=record['run_id'],
            report={k: report[k] for k in keys}))
        return report
    except Exception as exc:
        atomic_json(root/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.output_dir)
