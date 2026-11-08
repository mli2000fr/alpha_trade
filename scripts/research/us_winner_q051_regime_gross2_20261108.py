"""Matched Q051_050 H10 replays: SPY entry regime, or gross entry cap 2x.

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

import pandas as pd
import requests

from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

BASE = shared.ROOT
ROOT = Path('artifacts/research/us_winner_q051_regime_gross2/20261108-v1')
VARIANTS = ('REGIME', 'GROSS2')


def matched_configuration(plan, saved, variant):
    if variant not in VARIANTS:
        raise ValueError('Variante inconnue')
    case = deepcopy(plan['cases']['Q051_050'])
    baseline = shared.configuration(plan['reference'], case)
    normalized = json.loads(json.dumps(asdict(baseline), default=str))
    if normalized != saved['portfolio']:
        raise ValueError('Configuration du témoin Q051_050 non reproduite')
    if variant == 'GROSS2':
        case['gross'] = 2.
    cfg = shared.configuration(plan['reference'], case)
    if variant == 'REGIME':
        from backtesting.risk_overlay import RegimeFilterConfig
        cfg.risk_overlay.regime_filter = RegimeFilterConfig(enabled=True, sma_window=200, bear_threshold=-.02)
    expected = deepcopy(normalized)
    if variant == 'REGIME':
        expected['risk_overlay']['regime_filter']['enabled'] = True
    else:
        expected['risk_config']['max_gross_exposure'] = 2.
    if json.loads(json.dumps(asdict(cfg), default=str)) != expected:
        raise ValueError('Une différence dépasse le filtre régime ou le plafond 2x')
    risk = cfg.risk_config
    if cfg.winner_drawdown_controller_enabled or risk.force_close_on_breaker:
        raise ValueError('Les deux variantes doivent rester sans B4/DD15')
    return case, cfg


class RegimeEntryGate:
    """Gate fixed candidates using prior close only; never liquidate held lots.

    Winner does not consume the legacy overlay itself: explicitly connect the
    existing pure entry rule through its daily selection-source interface.
    """
    def __init__(self, close, rule):
        self.close = close.sort_index()
        self.rule = rule
        self.receipts = []

    def __call__(self, signal_day, rows, cutoff):
        day = pd.Timestamp(signal_day)
        if pd.Timestamp(cutoff).tz_convert('America/New_York').date() <= day.date():
            raise ValueError('Décision régime sans clôture précédente qualifiée')
        history = self.close.loc[:day].tail(self.rule.sma_window)
        if (len(history) != self.rule.sma_window or history.index[-1] != day
                or not history.map(lambda v: pd.notna(v) and 0 < float(v) < float('inf')).all()):
            raise ValueError('Historique SPY insuffisant/non qualifié pour le régime')
        allowed = self.rule.is_entry_allowed(self.close, day)
        self.receipts.append(dict(signal_date=str(day.date()), cutoff=str(cutoff),
            spy_close=float(history.iloc[-1]), sma200=float(history.mean()),
            distance=float(history.iloc[-1]/history.mean()-1), entry_allowed=bool(allowed),
            candidates=len(rows), blocked_candidates=0 if allowed else len(rows)))
        return dict(selected=rows.symbol.tolist() if allowed else [], incomplete=False)


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
            'only_changes': ['risk_overlay.regime_filter.enabled'] if variant == 'REGIME' else ['risk_config.max_gross_exposure'],
            'regime_execution': 'prior_SPY_close > 0.98*SMA200; block new entries only; no candidate refill; no held liquidation' if variant == 'REGIME' else None,
            'replay_command': [sys.executable, '-m', 'scripts.research.us_winner_q051_regime_gross2_20261108', '--output-dir', str(root.parent)],
            'started_at_utc': datetime.now(timezone.utc).isoformat()}
        atomic_json(root/'protocol.json', protocol)
        atomic_json(out/'configuration.json', dict(profile=case, portfolio=asdict(cfg)))
        pivots, sectors, actions = shared.market_data(BASE)
        gate = RegimeEntryGate(pivots['close']['SPY'], cfg.risk_overlay.regime_filter) if variant == 'REGIME' else None
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
                winner_corporate_actions=actions.to_dict('records'), winner_selection_source=gate)
            if gate is not None:
                pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv', index=False)
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
            report.update(case='Q051_050_'+variant, profile=case, annual_models=plan['annual_models'],
                annual_reset=False, selected_signals=len(signals), provider_calls=0, broker_calls=0,
                SQL_writes=0, strict_pit=False, finished_at_utc=datetime.now(timezone.utc).isoformat())
            if gate is not None:
                report['regime_filter_audit'] = dict(decisions=len(gate.receipts),
                    blocked_sessions=sum(not r['entry_allowed'] for r in gate.receipts),
                    blocked_candidates=sum(r['blocked_candidates'] for r in gate.receipts))
            atomic_json(out/'report.json', report)
            keys = ['final_equity', 'return_pct', 'max_drawdown_pct', 'closed_lot_trades', 'win_pct', 'average_gross_capital']
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
        initial_equity_USD=4000., gross2_initial_capacity_USD=8000., gross2_basis='CURRENT_EQUITY',
        B4_enabled=False, market_prices_and_models='UNCHANGED_FROZEN_BASELINE',
        sources={str(Path(__file__)): digest(Path(__file__))}))
    results = []
    failures = []
    atomic_json(root/'progress.json', dict(status='RUNNING_TWO_CASES', completed=0, total=2))
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context('spawn')) as pool:
        futures = {pool.submit(run_case, str(root/v), v): v for v in VARIANTS}
        for future in as_completed(futures):
            variant = futures[future]
            try:
                value = future.result()
                from ihm.services.backtesting_import import import_continuous_winner
                description = 'filtre régime SPY SMA200' if variant == 'REGIME' else 'plafond achat 2×, margin 2×'
                record = import_continuous_winner(value['folder'], run_id=f'20261108_continu_Q051_050_{variant}_v1',
                    label=f'Continu H10 2021–2026 — Q051 seuils 0,50 sans B4 — {description}', result_subdir='result')
                value['ihm_run_id'] = record['run_id']
                results.append(value)
            except Exception as exc:
                failures.append(dict(variant=variant, error_type=type(exc).__name__, error=str(exc)))
            atomic_json(root/'progress.json', dict(status='RUNNING_TWO_CASES', completed=len(results)+len(failures),
                total=2, results=results, failures=failures))
    baseline = shared.read(BASE/'cases/Q051_050/result/report.json')
    keys = ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital']
    pd.DataFrame([dict(variant='BASELINE', **{k: baseline[k] for k in keys}),
        *[dict(variant=r['variant'], **r['report']) for r in results]]).to_csv(root/'comparison.csv', index=False)
    report = dict(status='COMPLETED_EXPLORATORY' if not failures else 'INCOMPLETE_CASES', results=results, failures=failures)
    atomic_json(root/'report.json', report)
    atomic_json(root/'progress.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.output_dir)
