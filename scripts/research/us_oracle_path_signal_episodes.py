"""One actual entry per observable TOP5 episode, isolated offline research."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from functools import partial
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_path_atr_stop as fixed
from scripts.research import us_oracle_path_protection_selector as archived
from scripts.research import us_oracle_path_top5_leverage_grid as grid
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes

SOURCE = fixed.SOURCE
ARMS = ('REFERENCE', 'ONE_ENTRY_PER_EPISODE')
LOG = logging.getLogger(__name__)


def build_episodes(candidates, calendars):
    """Original TOP5 BEFORE J quality/risk filters, backward-only episode starts.

    No future episode end/duration belongs in the decision table. Start of each
    test year is left-censored and reset just as its portfolio capital/state.
    """
    if candidates.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate TOP5 membership')
    out = []
    for year, days in calendars.items():
        sub = candidates[candidates.year.eq(year)].sort_values(['date', 'oracle_rank'])
        if set(sub.date) != set(days) or not sub.groupby('date').size().eq(5).all():
            raise ValueError('Complete original daily TOP5 required; unknown day is not an exit')
        if not sub.groupby('date').oracle_rank.apply(lambda x: set(x) == set(range(1, 6))).all():
            raise ValueError('Original TOP5 ranks must be exactly 1..5')
        last_seen, starts = {}, {}
        for t in sub.itertuples(index=False):
            j = days.get_loc(t.date)
            if last_seen.get(t.symbol, -2) != j-1:
                starts[t.symbol] = (t.date, j)
            start, start_index = starts[t.symbol]
            out.append(dict(date=t.date, symbol=t.symbol, year=year, episode_start=start,
                episode_id=f'{year}:{t.symbol}:{start.date()}', episode_age_sessions=j-start_index+1,
                left_censored_at_year_start=start_index == 0))
            last_seen[t.symbol] = j
    return pd.DataFrame(out)


class EpisodeBook:
    def __init__(self, membership):
        if membership.duplicated(['date', 'symbol']).any():
            raise ValueError('Duplicate episode key')
        self.lookup = membership.set_index(['date', 'symbol']).episode_id.to_dict()
        self.used = Counter()

    def token(self, day, symbol):
        key = (pd.Timestamp(day).normalize(), symbol)
        if key not in self.lookup:
            raise ValueError(f'No original TOP5 episode for {symbol}/{day}')
        return self.lookup[key]

    def consumed(self, day, symbol):
        return self.used[self.token(day, symbol)] > 0

    def record_actual_entry(self, day, symbol, *, enforce):
        token = self.token(day, symbol)
        if enforce and self.used[token]:
            raise ValueError('Duplicate actual entry in a consumed TOP5 episode')
        self.used[token] += 1
        return token


class EpisodeSession(fixed.ATRStopSession):
    def __init__(self, *args, membership, enforce, **kwargs):
        super().__init__(*args, **kwargs)
        self.book, self.enforce = EpisodeBook(membership), enforce
        self.pending_episode_decisions = {}
        self.gate_audits, self.episode_fill_audits = [], []

    def decide(self, day, *, scores, **kwargs):
        allowed = []
        ledger = self.ledger_ref[0]
        for t in scores.itertuples(index=False):
            token = self.book.token(day, t.symbol)
            used = self.book.used[token]
            blocked = self.enforce and used > 0
            self.gate_audits.append(dict(decision_date=str(day), symbol=t.symbol, episode_id=token,
                earlier_actual_entries=used, blocked=blocked, already_held=t.symbol in ledger.state.positions,
                reason='EPISODE_ALREADY_EXECUTED' if blocked else 'EPISODE_AVAILABLE_OR_REFERENCE'))
            if not blocked:
                allowed.append(t.symbol)
        entries = super().decide(day, scores=scores[scores.symbol.isin(allowed)], **kwargs)
        self.pending_episode_decisions = {e.symbol: pd.Timestamp(day) for e in entries if e.approved_shares > 0}
        return entries

    def record_fill(self, event_id, *, day, symbol, entry, realized_pnl=None):
        duplicate = event_id in self.events
        if entry and not duplicate:
            if symbol not in self.pending_episode_decisions:
                raise ValueError('Executed buy without preceding episode decision')
            decision = self.pending_episode_decisions[symbol]
            if not decision < pd.Timestamp(day):
                raise ValueError('Episode must be known before fill')
            if self.enforce and self.book.consumed(decision, symbol):
                raise ValueError('Episode consumed before this fill')
        super().record_fill(event_id, day=day, symbol=symbol, entry=entry, realized_pnl=realized_pnl)
        if entry and not duplicate:
            token = self.book.record_actual_entry(decision, symbol, enforce=self.enforce)
            self.episode_fill_audits.append(dict(symbol=symbol, decision_date=str(decision.date()),
                fill_date=str(day), episode_id=token, execution_event_id=event_id,
                entry_number_in_episode=self.book.used[token]))


def freeze(root):
    marker = root/'protocol.json'
    if marker.exists():
        p = grid.read(marker); verify_hashes(Path('.'), p['sources']); return p
    prior, report = grid.read(SOURCE/'protocol.json'), grid.read(SOURCE/'report.json')
    verify_hashes(Path('.'), prior['sources']); verify_hashes(SOURCE, report['files'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or grid.read(SOURCE/'completion-audit.json')[
            'status'] != 'TWELVE_CASES_AND_FROZEN_DECISIONS_VERIFIED':
        raise ValueError('Audited annual same-model baseline required')
    sources = dict(prior['sources']); sources.update(code_hashes())
    paths = [SOURCE/'protocol.json', SOURCE/'report.json', SOURCE/'candidates.parquet', SOURCE/'completion-audit.json',
        Path(__file__), Path('scripts/research/us_oracle_path_signal_episodes_review.py'),
        Path('tests/test_us_oracle_path_signal_episodes.py'), Path(fixed.__file__),
        Path('doc/ml/oracle_path_signal_episodes_20261014.md')]
    for y in grid.ENDS:
        folder = SOURCE/f'{y}-FIXED_REFERENCE'
        case = grid.read(folder/'case-report.json'); verify_hashes(folder, case['files'])
        paths.extend(folder/n for n in ['case-report.json', 'daily.parquet', 'trades.parquet', 'opened-profiles.json'])
    sources.update({str(path): digest(path) for path in paths})
    p = dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(), source=str(SOURCE),
        annual_models=prior['annual_models'], years=grid.ENDS, arms=ARMS,
        membership='original daily TOP5, before J quality/risk; consecutive NYSE sessions',
        episode_reset='one observed absence from TOP5; no optimized cooldown; no rank6 replacement',
        state='one ACTUAL executed buy consumes episode; rejection/approval alone never consumes it',
        signal_day='episode of J decision, not TOP5 at future J+1 close',
        boundary='cash and used-episode state reset annually; initial episode left censored',
        audit_gate='at least10 actual same-episode reentries in EACH year; counts only, not selected PnL',
        top=5, sl=.05, tp=.20, trailing=.15, risk_budget_fraction=.02, capital_usd=4000, leverage_cap=2,
        no_time_or_terminal_sale=True, no_reinforcement=True, native_guards_unchanged=True,
        promotion_gate='six complete; exact reference; rule return higher and DD no worse in every period',
        no_threshold_retune=True, training=False, sql_writes=False, broker_calls=False,
        production_changed=False, independent_holdout=False, reserves=prior['reserves'],
        sources=sources, prices=prior['prices'], macro=prior['macro'], market=prior['market'], events=prior['events'])
    atomic_json(marker, p)
    return p


def classify_reference(root, membership, protocol):
    lookup = membership.set_index(['date', 'symbol']).episode_id.to_dict()
    rows, summaries = [], []
    days = grid.nyse_sessions('2023-01-01', '2026-10-09')
    for year in grid.ENDS:
        folder = SOURCE/f'{year}-FIXED_REFERENCE'
        opened = sorted(grid.read(folder/'opened-profiles.json'), key=lambda a: (pd.Timestamp(a['fill_date']), a['symbol']))
        trades = pd.read_parquet(folder/'trades.parquet')
        seen_symbol, seen_episode = set(), Counter()
        for a in opened:
            entry = pd.Timestamp(a['fill_date']); decision = days[days.get_loc(entry)-1]
            symbol = a['symbol']; token = lookup[(decision, symbol)]
            category = 'SAME_EPISODE_REENTRY' if seen_episode[token] else 'RENEWED_EPISODE_ENTRY' if symbol in seen_symbol else 'FIRST_SYMBOL_ENTRY'
            matching = []
            for t in trades[trades.entry_date.eq(entry)].itertuples(index=False):
                alias = symbol
                for e in protocol['events']:
                    if alias == e['source'] and entry <= pd.Timestamp(e['day']) <= t.exit_date:
                        alias = e['target']
                if alias == t.symbol:
                    matching.append(t)
            if len(matching) > 1:
                raise ValueError('Reference closed lot lineage ambiguous')
            t = matching[0] if matching else None
            rows.append(dict(year=year, symbol=symbol, decision_date=decision, entry_date=entry,
                episode_id=token, category=category, entry_number_in_episode=seen_episode[token]+1,
                closed=t is not None, pnl_usd=float(t.pnl) if t else None, exit_reason=t.exit_reason if t else None))
            seen_symbol.add(symbol); seen_episode[token] += 1
        sub = pd.DataFrame(rows); sub = sub[sub.year.eq(year)]
        categories = []
        for name, g in sub.groupby('category'):
            closed = g[g.closed]
            categories.append(dict(category=name, actual_entries=len(g), closed=len(closed), open=int((~g.closed).sum()),
                realized_pnl_usd=float(closed.pnl_usd.sum()), winners_pct=float(100*closed.pnl_usd.gt(0).mean()) if len(closed) else None))
        summaries.append(dict(year=year, categories=categories, actual_entries=len(sub),
            same_episode_reentries=int(sub.category.eq('SAME_EPISODE_REENTRY').sum()),
            episode_count=int(membership[membership.year.eq(year)].episode_id.nunique())))
    frame = pd.DataFrame(rows)
    frame.to_parquet(root/'reference-entry-diagnostic.parquet', index=False)
    material = all(s['same_episode_reentries'] >= 10 for s in summaries)
    diagnostic = dict(status='COMPLETED_DIAGNOSTIC', technical_materiality_gate=material, years=summaries,
        interpretation='attribution is hindsight; removing PnL does not simulate alternative capital/reinvestment',
        files={'reference-entry-diagnostic.parquet': digest(root/'reference-entry-diagnostic.parquet')})
    atomic_json(root/'diagnostic.json', diagnostic)
    return diagnostic


_CACHE = None


def worker_init(output):
    global _CACHE
    archived.worker_init(SOURCE)
    _CACHE = dict(archived._CACHE, root=Path(output), protocol=grid.read(Path(output)/'protocol.json'),
        membership=pd.read_parquet(Path(output)/'membership.parquet'))


def run_case(case):
    year, arm = case; folder = _CACHE['root']/f'{year}-{arm}'; folder.mkdir(exist_ok=True)
    marker = folder/'case-report.json'
    if marker.exists():
        old = grid.read(marker)
        if old['status'] == 'COMPLETED':
            verify_hashes(folder, old['files']); return old
    refs, sessions = [], []
    def factory(cfg, **kwargs):
        ledger = fixed.ATRStopLedger(cfg, arm=fixed.ARMS[0], study_end=grid.ENDS[year],
            cash_policy='STRICT', events=_CACHE['protocol']['events'], **kwargs)
        refs.append(ledger); return ledger
    def session_factory(*args, **kwargs):
        session = EpisodeSession(*args, membership=_CACHE['membership'][_CACHE['membership'].year.eq(year)],
            enforce=arm == ARMS[1], ledger_ref=refs, **kwargs)
        sessions.append(session); return session
    try:
        with (folder/'stderr.log').open('a', encoding='utf-8') as log, redirect_stderr(log), redirect_stdout(log):
            logging.basicConfig(level=logging.WARNING, stream=log, force=True)
            result = run_portfolio(frames=_CACHE['frames'], scores=_CACHE['candidates'][_CACHE['candidates'].year.eq(year)],
                sectors=_CACHE['sectors'], macro=_CACHE['macro'], market_config=_CACHE['market'], policy='selected',
                variant='CURRENT_NO_EXPIRY', output=folder, start_date=f'{year}-01-01', end_date=grid.ENDS[year],
                quality=_CACHE['prices'][['date', 'symbol', 'is_filled', 'instrument_id']], ledger_factory=factory,
                session_factory=session_factory, protection_options=dict(take_profit_enabled=True, trailing_enabled=True),
                daily_exit_policy=grid.margin_policy, reject_constrained_entries=True)
        ledger, session = refs[0], sessions[0]
        daily, trades = (pd.read_parquet(folder/n) for n in ['daily.parquet', 'trades.parquet'])
        fills = fixed.committed_fills(ledger); fixed.verify_closed_stops(trades, fills, _CACHE['protocol']['events'])
        if len(fills) != len(session.episode_fill_audits):
            raise ValueError('Episode consumption differs from actual buys')
        if arm == ARMS[1] and any(v > 1 for v in session.book.used.values()):
            raise ValueError('Multiple executed entries per episode')
        open_rows = [dict(symbol=s, entry_date=str(p.entry_date.date()), quantity=p.quantity, entry_cost=p.entry_cost,
            unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(grid.ENDS[year]), s])-p.entry_cost)
                    for s, p in ledger.state.positions.items()]
        realized = float(trades.pnl.sum()) if len(trades) else 0.
        latent = sum(a['unrealized_pnl_usd'] for a in open_rows)
        if not np.isclose(4000+realized+latent-ledger.interest, daily.equity.iloc[-1], atol=1e-6):
            raise ValueError('Final wealth does not reconcile')
        parity = False
        if arm == ARMS[0]:
            for name in ['trades.parquet', 'daily.parquet']:
                pd.testing.assert_frame_equal(pd.read_parquet(folder/name),
                    pd.read_parquet(SOURCE/f'{year}-FIXED_REFERENCE'/name), check_exact=True)
            parity = True
        for name, data in [('episode-decisions.json', session.gate_audits), ('episode-fills.json', session.episode_fill_audits),
            ('stop-decisions.json', ledger.decision_audits), ('committed-fills.json', fills),
            ('open-positions.json', open_rows), ('maintenance.json', ledger.margin_audits)]:
            atomic_json(folder/name, data)
        pnl = trades.groupby(['symbol', 'entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
        result.update(status='COMPLETED', case=f'{year}-{arm}', year=year, arm=arm,
            final_capital_usd=float(daily.equity.iloc[-1]), net_return_pct=100*result['return_pct'],
            dd_pct=100*result['max_drawdown'], realized_pnl_usd=realized, unrealized_pnl_usd=latent,
            gains_usd=float(pnl[pnl > 0].sum()), losses_usd=float(pnl[pnl < 0].sum()),
            executed_positions=len(fills), open_positions=len(open_rows), baseline_exact=parity,
            episode_blocked_candidate_days=sum(a['blocked'] for a in session.gate_audits),
            episode_blocked_unheld_candidate_days=sum(a['blocked'] and not a['already_held'] for a in session.gate_audits),
            executed_same_episode_reentries=sum(max(0, v-1) for v in session.book.used.values()),
            max_entries_per_episode=max(session.book.used.values(), default=0),
            mean_gross_leverage=float((daily.gross_notional/daily.equity).mean()),
            risk_budget_fraction=.02, initial_sl=.05, tp=.20, trailing=.15,
            files={f.name: digest(f) for f in folder.iterdir() if f.suffix in ['.json', '.parquet'] and f.name != 'case-report.json'})
    except Exception as exc:
        import traceback
        (folder/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        result = dict(status='FAILED', case=f'{year}-{arm}', year=year, arm=arm, error_type=type(exc).__name__, error=str(exc))
    atomic_json(marker, result)
    return result


def run(output, phase='all', workers=3):
    root = Path(output)
    with exclusive_run(root):
        protocol = freeze(root)
        candidates = pd.read_parquet(SOURCE/'candidates.parquet')
        calendars = {y: grid.nyse_sessions(f'{y}-01-01', end) for y, end in grid.ENDS.items()}
        membership = build_episodes(candidates, calendars)
        membership.to_parquet(root/'membership.parquet', index=False)
        diagnostic = classify_reference(root, membership, protocol)
        if phase == 'audit' or not diagnostic['technical_materiality_gate']:
            atomic_json(root/'progress.json', dict(status='AUDIT_READY' if diagnostic['technical_materiality_gate'] else 'NO_GO_LOW_EPISODE_REPETITION',
                portfolio_launched=False))
            return diagnostic
        reports = []
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(str(root),)) as pool:
            futures = [pool.submit(run_case, (y, arm)) for y in grid.ENDS for arm in ARMS]
            for future in as_completed(futures):
                r = future.result(); reports.append(r)
                atomic_json(root/'progress.json', dict(status='RUNNING', finished=len(reports), total=6,
                    failed=sum(r['status'] == 'FAILED' for r in reports), last=r['case']))
                atomic_json(root/'report.partial.json', dict(cases=reports))
                LOG.info('%s %s %s/6', r['case'], r['status'], len(reports))
        verify_hashes(Path('.'), protocol['sources'])
        comparisons = []
        for year in grid.ENDS:
            group = {r['arm']: r for r in reports if r['year'] == year and r['status'] == 'COMPLETED'}
            if len(group) == 2:
                a, b = group[ARMS[0]], group[ARMS[1]]
                comparisons.append(dict(year=year, reference_net_pct=a['net_return_pct'], episode_net_pct=b['net_return_pct'],
                    delta_return_points=b['net_return_pct']-a['net_return_pct'],
                    reference_dd_pct=a['dd_pct'], episode_dd_pct=b['dd_pct'], delta_dd_points=b['dd_pct']-a['dd_pct']))
        failed = sum(r['status'] == 'FAILED' for r in reports)
        gate = not failed and len(comparisons) == 3 and all(c['delta_return_points'] > 0 and c['delta_dd_points'] >= 0 for c in comparisons)
        verdict = 'PARTIAL_FAILED' if failed else 'EXPLORATORY_EPISODE_GAIN_TO_CONFIRM' if gate else 'NO_GO_STABLE_EPISODE_ENTRY_ADVANTAGE'
        report = dict(status='PARTIAL_FAILED' if failed else 'COMPLETED_EXPLORATORY', verdict=verdict, cases=reports,
            comparisons=comparisons, diagnostic=diagnostic, training=False, sql_writes=False, broker_calls=False,
            production_changed=False, independent_holdout=False, source_hashes_verified=True,
            files={str(f.relative_to(root)): digest(f) for f in root.rglob('*')
                   if f.suffix in ['.json', '.parquet'] and f.name not in ['report.json', 'progress.json']})
        pd.DataFrame([{k: v for k, v in r.items() if k != 'files'} for r in reports]).to_csv(root/'annual-summary.csv', index=False)
        atomic_json(root/'report.json', report)
        atomic_json(root/'progress.json', dict(status=report['status'], verdict=verdict, finished=6, failed=failed, total=6))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    parser.add_argument('--phase', choices=['all', 'audit'], default='all')
    parser.add_argument('--workers', choices=[1, 2, 3], type=int, default=3)
    args = parser.parse_args(); Path(args.output).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(),
        logging.FileHandler(Path(args.output)/'stderr.log', encoding='utf-8')])
    try:
        run(**vars(args))
    except Exception as exc:
        atomic_json(Path(args.output)/'progress.json', dict(status='FAILED', error=str(exc), error_type=type(exc).__name__))
        raise
