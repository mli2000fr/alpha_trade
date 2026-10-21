"""Frozen price-only held-position correlation gate, offline annual replay.

Baseline, correlation and predetermined half-size control; no threshold search.
No SQL/provider/training/broker calls or change to production configuration.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from risk_management.correlation_filter import filter_correlated_signed
from risk_management.models import EnrichedSelection
from scripts.research import us_oracle_persistent_trend as precedent
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

BASE, RISK, REFERENCE = precedent.BASE, precedent.risk, precedent.REFERENCE
OUTPUT = Path('artifacts/research/us_oracle_portfolio_correlation/20261021-v1')
RULE = dict(threshold=.9, lookback_returns=40, min_overlap=25)
ARM = RETURNS = SESSIONS = ORIGINAL_CACHE = None


def prior_returns(frame, sessions):
    """Split-adjusted archive close returns; missing/synthetic bars never filled."""
    g = frame.copy()
    if g.duplicated(['symbol', 'date']).any():
        raise ValueError('Duplicate symbol/session')
    fields = ['open', 'high', 'low', 'close', 'volume']
    valid = np.isfinite(g[fields]).all(axis=1) & g[fields].gt(0).all(axis=1)
    valid &= (g.high.ge(g[['open', 'close']].max(axis=1))
              & g.low.le(g[['open', 'close']].min(axis=1))
              & g.is_filled.eq(0) & g.data_adjustment.eq('split'))
    g['usable_close'] = g.close.where(valid)
    closes = g.pivot(index='date', columns='symbol', values='usable_close').reindex(sessions)
    return closes.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)


def selection(symbol, side):
    return EnrichedSelection(symbol=symbol, side=side, sector='RESEARCH_NO_SECTOR',
        score_used=1., score_source='HELD_POSITION_PRIORITY', predicted_proba=None,
        historical_win_rate=None, conviction_score=1.)


def evaluate_pair(matrix, candidate, held, side, held_side, rule=RULE):
    if candidate not in matrix or held not in matrix:
        return dict(held_symbol=held, status='MISSING_PAIR', overlap=0, correlation=None)
    pair = matrix[[candidate, held]].dropna()
    n = len(pair)
    if n < rule['min_overlap'] or (pair.std(ddof=1) <= 0).any():
        return dict(held_symbol=held, status='MISSING_PAIR', overlap=n, correlation=None)
    rho = float(pair[candidate].corr(pair[held]))
    if not np.isfinite(rho):
        return dict(held_symbol=held, status='MISSING_PAIR', overlap=n, correlation=None)
    # Pairwise held prefix: never let greedy filtering discard an existing
    # holding and thereby hide its correlation with the proposed candidate.
    _, rejected = filter_correlated_signed([selection(held, held_side), selection(candidate, side)],
        pair, threshold=rule['threshold'], min_overlap=rule['min_overlap'])
    return dict(held_symbol=held, status='CORRELATED' if rejected else 'PASS',
                overlap=n, correlation=rho)


class CorrelationLedger(RISK.ProductionRiskGridLedger):
    def __init__(self, calendar, **kwargs):
        super().__init__(calendar, **kwargs)
        if ARM == 'half_size':
            # Only the control's full target risk/weight budgets are halved.
            # Native HALF fraction, B4 allocation, costs, admission1x unchanged.
            self.risk = replace(self.risk, risk_per_trade_pct=self.risk.risk_per_trade_pct/2,
                                max_position_weight=self.risk.max_position_weight/2)
            self.engine.config.risk_config = self.risk
        self.correlation_events = []
        self.concentration_events = []
        self.context_day = None
        self.return_window = None

    def window(self):
        if self.context_day != self.day:
            i = SESSIONS.get_loc(self.day)
            self.return_window = RETURNS.iloc[max(0, i-RULE['lookback_returns']):i]
            if len(self.return_window) and self.return_window.index[-1] >= self.day:
                raise ValueError('Current/future return in admission context')
            self.context_day = self.day
        return self.return_window

    def enter(self, symbol, side, price_info, **kwargs):
        matrix = self.window()
        event = dict(time=self.now, bar_number=self.bar_number, symbol=symbol, side=side,
            pair_id=self.entry_context['pair_id'], source_date=matrix.index[-1], arm=ARM,
            held={s: dict(side=p.side, quantity=p.quantity, mark=self.prices[s])
                  for s, p in self.state.positions.items()}, pairs=[], gate='NOT_APPLIED')
        if ARM == 'correlation' and symbol not in self.state.positions:
            event['pairs'] = [evaluate_pair(matrix, symbol, s, side, p.side)
                              for s, p in sorted(self.state.positions.items())]
            statuses = {p['status'] for p in event['pairs']}
            event['gate'] = ('MISSING_PAIR' if 'MISSING_PAIR' in statuses else
                             'CORRELATED' if 'CORRELATED' in statuses else 'PASS')
            if event['gate'] != 'PASS':
                self.audit.append(dict(time=self.now, symbol=symbol, side=side,
                    status='BLOCKED', reasons=['PORTFOLIO_CORRELATION:'+event['gate']]))
                event['opened'] = False
                self.correlation_events.append(event)
                return False
        event['opened'] = bool(super().enter(symbol, side, price_info, **kwargs))
        self.correlation_events.append(event)
        return event['opened']

    def finish_day(self):
        eq = super().finish_day()
        matrix = self.window()
        held = list(self.state.positions.items())
        pairs = []
        for i, (a, pa) in enumerate(held):
            for b, pb in held[i+1:]:
                row = evaluate_pair(matrix, a, b, pa.side, pb.side)
                row.update(symbol=a, weight=(pa.quantity*self.prices[a])*(pb.quantity*self.prices[b]))
                pairs.append(row)
        known = [p for p in pairs if p['correlation'] is not None]
        denom = sum(p['weight'] for p in known)
        gross = self.gross()
        self.concentration_events.append(dict(date=self.day, equity=eq, gross=gross,
            held_count=len(held), known_pairs=len(known), missing_pairs=len(pairs)-len(known),
            high_correlation_pairs=sum(p['correlation'] > RULE['threshold'] for p in known),
            weighted_pair_correlation=sum(p['weight']*p['correlation'] for p in known)/denom if denom else None,
            position_hhi=sum((p.quantity*self.prices[s]/gross)**2 for s, p in held) if gross else None))
        if self.day == self.days[-1]:
            atomic_json(self.guard_output/'correlation-events.json', self.correlation_events)
            atomic_json(self.guard_output/'concentration-events.json', self.concentration_events)
        return eq


def prepare(root):
    root = Path(root)
    if root.resolve() == REFERENCE.resolve() or REFERENCE.resolve() in root.resolve().parents:
        raise ValueError('Preserve sealed reference')
    if root.exists() and any(p.name != 'run.lock' for p in root.iterdir()):
        raise ValueError('Fresh output required')
    review = BASE.READ(REFERENCE/'final-review.json')
    verify_hashes(REFERENCE, review['files'])
    report = BASE.READ(REFERENCE/'report.json')
    if report['completed'] != 576 or report['failed']:
        raise ValueError('Complete DD15 reference required')
    previous = BASE.READ(REFERENCE/'protocol.json')
    sources, drift = precedent.replay_sources(previous)
    ready = BASE.READ(REFERENCE/'prepared.json')
    verify_hashes(REFERENCE, ready['files'])
    profile = BASE.READ(REFERENCE/'production-risk.json')['canonical_risk_configuration']
    if (profile['correlation_threshold'], profile['correlation_lookback_days'],
        profile['correlation_min_overlap']) != (.9, 40, 25):
        raise ValueError('Declared rule must match frozen canonical Pearson settings')
    for name in [__file__, 'tests/test_us_oracle_portfolio_correlation.py',
                 'risk_management/correlation_filter.py', 'risk_management/models.py',
                 'scripts/research/us_oracle_persistent_trend.py', BASE.PRICE,
                 REFERENCE/'report.json', REFERENCE/'final-review.json']:
        sources[str(name)] = digest(name)
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(root/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources, declared_source_changes=drift, rule=RULE, reference=str(REFERENCE),
        hypothesis='One price-only entry correlation constraint against actual held positions, no direction model.',
        evaluation='40daily split-adjusted close returns ending previous exchange session;25common finite returns. '
                   'No ffill. Same-side native filter_correlated_signed; threshold strictly>0.9. '
                   'Insufficient/constant/ambiguous pair blocks proposed new entry only. '
                   'Existing holdings never forced out on correlation and retain chronological priority. '
                   'Oracle score priority among simultaneous ORIGINAL signals; no retries/rerank/TOP11.',
        arms=['baseline', 'correlation', 'half_size'],
        sizing_control='Predetermined half risk budget AND half max-position-weight full target, '
                       'same native HALF multiplier,1x/B4/constraints and fees. '
                       'Approximate low-exposure control, NOT exact exposure-matched or a calibrated optimizer.',
        unchanged='Same213campaigns/72symbols,2025/2026toSept30,4kannual1x,SL7/TR15/noTP/OracleJ20expiry, '
                  'B4DD15,8bps/leg,assumed0.3%annual252borrow,6.5%ACT360finance. '
                  'Four baseline transactions must reproduce sealed reference exactly.',
        scope='Separate all-LONG/all-SHORT accounts, NOT mixed-side covariance/factor/sector allocation. '
              'No sector metadata or PCA. Pearson co-movement is not all economic common exposure.',
        limitations=previous.get('limitations', [])+[
            'Cohort conditional on complete future prices/current survivor universe; not original entireTOP10. '
            'ResearchCatBoostPATH_H20,not productionLightGBM.2024intraday unavailable.',
            'Historic restated split-adjusted price correlations are causal by timestamp but not certified applicationPIT receipts.',
            '2025/2026 already studied; not pristine holdout. No grid/search after results.',
            'Unknown history is distinct from high correlation; both refusal categories reported.',
            'Lower DD with lower exposure alone does not prove diversification alpha. No exact exposure-matched claim.',
            'OldJ+20fromOracle expiry, not new20holding-session live runtime. No full live parity.'],
        training=False, sql_writes=False, provider_calls=False, broker_calls=False, full_live_parity=False))
    for name in ready['files']:
        shutil.copyfile(REFERENCE/name, root/name)
    candidates = pd.read_parquet(root/'candidates.parquet')
    daily = pd.read_parquet(BASE.PRICE)
    from modelFactory.oracle.build_labels import nyse_sessions
    sessions = nyse_sessions(pd.to_datetime(daily.date).min(), pd.to_datetime(daily.date).max())
    returns = prior_returns(daily[daily.symbol.isin(candidates.symbol.unique())], sessions)
    returns.to_parquet(root/'returns.parquet')
    hashes = dict(ready['files']); hashes['returns.parquet'] = digest(root/'returns.parquet')
    atomic_json(root/'prepared.json', dict(files=hashes, candidate_signals=len(candidates),
                                         symbols=len(returns.columns)))
    for arm in ['baseline', 'correlation', 'half_size']:
        folder = root/arm; folder.mkdir()
        for name in ['production-risk.json', 'risk-regimes.parquet']:
            shutil.copyfile(root/name, folder/name)


def worker_init(root):
    global ORIGINAL_CACHE, RETURNS, SESSIONS
    RISK.worker_init(root)
    BASE.GridLedger = CorrelationLedger
    ORIGINAL_CACHE = BASE.CACHE
    RETURNS = pd.read_parquet(Path(root)/'returns.parquet')
    SESSIONS = RETURNS.index


def worker_case(root, arm, year, side):
    global ARM
    ARM = arm
    c = dict(year=year, side=side, sl=.07, trailing=.15, horizon=20, tp=None)
    directory = Path(root)/arm
    RISK.ACTIVE_OUTPUT = directory/'cases'/BASE.case_key(c)
    result = BASE.run_case(directory, c)
    result['arm'] = arm
    if result['status'] == 'COMPLETED_EXPLORATORY':
        trades = pd.read_parquet(RISK.ACTIVE_OUTPUT/'trades.parquet')
        opened = BASE.READ(RISK.ACTIVE_OUTPUT/'open-positions.json')
        if arm == 'baseline':
            old = next(r for r in BASE.READ(REFERENCE/'report.json')['cases'] if r['case'] == result['case'])
            for key in ['return_pct', 'max_drawdown_pct', 'mean_capital_used_usd', 'trades', 'open_positions']:
                if not np.isclose(result[key], old[key], atol=1e-7, rtol=1e-12):
                    raise ValueError('Baseline reproduction failed: '+key)
            pd.testing.assert_frame_equal(trades, pd.read_parquet(REFERENCE/'cases'/result['case']/'trades.parquet'))
            if opened != BASE.READ(REFERENCE/'cases'/result['case']/'open-positions.json'):
                raise ValueError('Baseline open positions mismatch')
        result['baseline_reproduction'] = 'PASS' if arm == 'baseline' else 'NOT_APPLICABLE'
        events = BASE.READ(RISK.ACTIVE_OUTPUT/'correlation-events.json')
        result['correlation_refusals'] = sum(e['gate'] == 'CORRELATED' for e in events)
        result['missing_pair_refusals'] = sum(e['gate'] == 'MISSING_PAIR' for e in events)
    return result


def run(root, workers=2):
    from scripts.research.oracle_path_confirmation import exclusive_run
    root = Path(root)
    with exclusive_run(root):
        prepare(root)
        plan = [(a, y, s) for a in ['baseline', 'correlation', 'half_size']
                for y in [2025, 2026] for s in ['buy', 'sell']]
        rows = []; start = time.monotonic()
        atomic_json(root/'progress.json', dict(status='RUNNING', completed=0, failed=0, total=12))
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(str(root),)) as pool:
            futures = {pool.submit(worker_case, str(root), *case): case for case in plan}
            for future in as_completed(futures):
                try:
                    row = future.result()
                except Exception as exc:
                    a, y, s = futures[future]
                    row = dict(status='FAILED', arm=a, year=y, side=s, error=repr(exc))
                rows.append(row)
                atomic_json(root/'progress.json', dict(status='RUNNING', completed=len(rows), total=12,
                    failed=sum(r['status'] != 'COMPLETED_EXPLORATORY' for r in rows),
                    last=f"{row['arm']}/{row['year']}/{row['side']}", elapsed_seconds=time.monotonic()-start))
        verify_hashes(Path('.'), BASE.READ(root/'protocol.json')['sources'])
        verify_hashes(root, BASE.READ(root/'prepared.json')['files'])
        for row in rows:
            if row['status'] == 'COMPLETED_EXPLORATORY':
                verify_hashes(root/row['arm']/'cases'/row['case'], row['files'])
        count = sum(r['status'] == 'COMPLETED_EXPLORATORY' for r in rows)
        report = dict(status='COMPLETED_EXPLORATORY' if count == 12 else 'PARTIAL_FAILED',
            completed=count, failed=12-count, total=12, cases=rows,
            elapsed_seconds=time.monotonic()-start, full_live_parity=False)
        pd.DataFrame([{k: v for k, v in r.items() if k not in ['audit', 'files', 'traceback']}
                      for r in rows]).to_csv(root/'annual-summary.csv', index=False)
        atomic_json(root/'report.json', report)
        atomic_json(root/'progress.json', {k: v for k, v in report.items() if k != 'cases'})
        atomic_json(root/'final-review.json', dict(status='PASS_12_PAIRED_CASES' if count == 12 else 'FAILED',
            independent_human_review=False,
            files={n: digest(root/n) for n in ['protocol.json', 'prepared.json', 'report.json', 'annual-summary.csv']}))
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    a = p.parse_args()
    run(a.output, a.workers)
