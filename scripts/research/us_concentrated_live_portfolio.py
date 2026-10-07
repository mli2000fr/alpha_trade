"""Chronological research portfolio using shared risk/execution/lifecycle.

No training, broker calls or SQL writes. Current sectors are an explicitly
accepted NON-PIT assumption. OHLC fills are simulated, never broker evidence.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, replace
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from common.config_loader import load_config
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.regime_state_machine import RegimeState, RegimeStateMachine
from risk_management.transition_handler import TransitionHandler, OrderAction
from service.market import build_snapshot, parse_market_regimes
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_exit_variants import VARIANTS
from scripts.research.us_concentrated_historical_tapes import (
    atomic_json, verify_hashes, apply_overlay, decision_rows, digest,
)

LOG = logging.getLogger(__name__)


def apply_verified_volume_overlay(bars, path):
    """Require archived response, qualification and hashes, never a naked repair."""
    path = Path(path)
    report = json.loads((path.parent/'report.json').read_text(encoding='utf-8'))
    if (report.get('status') != 'VENDOR_VOLUME_CORRECTION_NON_PIT'
            or report.get('overlay_sha256') != digest(path)
            or report.get('raw_sha256') != digest(path.parent/'provider-response.json')):
        raise ValueError('Unqualified or changed volume-overlay evidence')
    overlay = pd.read_parquet(path)
    if (len(overlay) != 1 or overlay.symbol.iloc[0] != report['symbol']
            or pd.Timestamp(overlay.date.iloc[0]).date().isoformat() != report['date']
            or not overlay.raw_sha256.eq(report['raw_sha256']).all()):
        raise ValueError('Volume overlay does not match its qualified evidence')
    from scripts.research.us_concentrated_volume_refresh import qualify
    if qualify(report['original'], report['refreshed']) != report['status']:
        raise ValueError('Invalid volume qualification')
    if float(overlay.replacement_volume.iloc[0]) != float(report['refreshed']['volume']):
        raise ValueError('Overlay volume differs from provider response')
    return apply_overlay(bars, overlay)


class ArchivedMacro:
    """Strict as-of archive: no forward fill from a future observation."""
    def __init__(self, frame):
        self.frame = frame.copy()
        self.frame.index = pd.to_datetime(self.frame.trade_date).dt.normalize()
        if not self.frame.index.is_unique:
            raise ValueError('Duplicate macro dates')
        self.frame = self.frame.sort_index()

    def value(self, day, key):
        timestamp = pd.Timestamp(day)
        if timestamp not in self.frame.index:
            return None
        value = self.frame.at[timestamp, key]
        return float(value) if pd.notna(value) and np.isfinite(float(value)) else None

    def get_vix_close(self, day): return self.value(day, 'vix')
    def get_vix_short_term_close(self, day): return self.value(day, 'vix9d')
    def get_vxn_close(self, day): return self.value(day, 'vxn')
    def get_vix3m_close(self, day): return self.value(day, 'vix3m')
    def get_move_close(self, day): return self.value(day, 'move')
    def get_rvx_close(self, day): return self.value(day, 'rvx')
    def get_us10y_history(self, day, lookback_days):
        return self.frame.loc[:pd.Timestamp(day), 'ten_y'].dropna().tail(lookback_days).astype(float).tolist()


def run_portfolio(*, frames, scores, sectors, macro, market_config, policy, variant,
                  output, max_days=None, quality=None, initial_stop_pct=None,
                  reject_constrained_entries=False,
                  start_date='2025-01-01', end_date='2026-09-30',
                  early_weakness_fraction=None, session_factory=OraclePortfolioSession):
    if early_weakness_fraction is not None and early_weakness_fraction not in (.5, 1.):
        raise ValueError('Early weakness fraction must be 0.5 or 1')
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError('Invalid replay date range')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    days = frames['close'].index
    days = days[(days >= start) & (days <= end)]
    if max_days:
        days = days[:max_days]
    if days.empty:
        raise ValueError('Empty replay calendar')
    cfg = frozen_backtest_config(days[0], days[-1])
    cfg.reject_constrained_replay_entries = reject_constrained_entries
    if initial_stop_pct is None:
        ledger = OraclePortfolioLedger(cfg, **frames, sector_map=sectors)
    else:
        from scripts.research.us_concentrated_fixed_stop import FixedInitialStopLedger
        ledger = FixedInitialStopLedger(cfg, **frames, sector_map=sectors,
                                       initial_stop_pct=initial_stop_pct)
    session = session_factory(cfg.risk_config, sector_map=sectors,
        market_regimes_config=market_config, account_long_only=False)
    breaker = CircuitBreaker(cfg.risk_config)
    spy = frames['close'].SPY
    sma50, sma200 = spy.rolling(50, min_periods=50).mean(), spy.rolling(200, min_periods=200).mean()
    spy_regimes = {}
    for day in days:
        if pd.isna(sma200.at[day]):
            spy_regimes[day.date()] = None
        else:
            above200, above50 = spy.at[day] > sma200.at[day], spy.at[day] > sma50.at[day]
            spy_regimes[day.date()] = ('BULL' if above50 else 'CORRECTION') if above200 else ('REBOUND' if above50 else 'SLIDE')
    groups = {d: g for d, g in scores.loc[scores[policy]].groupby('date')}
    pending, queued_steps, regime_state = [], [], None
    previous_mode, previous_equity = RegimeState.NORMAL, cfg.initial_equity
    decisions, regimes, transitions = [], [], []
    queued_weakness, weakness_audits = [], []
    v = VARIANTS[variant]
    options = dict(take_profit_enabled=v['tp'], trailing_enabled=v['trailing'])

    def record_exits(trades, day):
        for trade in trades:
            symbol = trade['symbol']
            # A partial reduction is not a completed losing streak observation.
            if symbol not in ledger.state.positions:
                same_position = [t for t in ledger.state.closed_trades
                    if t['symbol'] == symbol and t['entry_date'] == trade['entry_date']]
                session.record_fill(f'exit-{symbol}-{trade["entry_date"]}-{day}', day=day.date(),
                    symbol=symbol, entry=False, realized_pnl=sum(t['pnl'] for t in same_position))

    try:
        for index, day in enumerate(days):
            ledger.begin_day(day)
            for symbol in ledger.state.positions:
                if not pd.notna(frames['volume'].at[day, symbol]) or frames['volume'].at[day, symbol] <= 0:
                    raise ValueError(f'Unqualified held-position volume {symbol}/{day.date()}')
                if quality is not None:
                    observed = quality.loc[(quality.symbol == symbol) & quality.date.between(
                        ledger.state.positions[symbol].entry_date, day)]
                    if observed.is_filled.fillna(0).ne(0).any() or observed.instrument_id.dropna().nunique() > 1:
                        raise ValueError(f'Unqualified held-position filled/identity path {symbol}/{day.date()}')
            record_exits(ledger.apply_observed_protections(phase='open', **options), day)
            for step in queued_steps:
                if step.action in {OrderAction.REDUCE, OrderAction.LIQUIDATE} and step.symbol in ledger.state.positions:
                    quantity = min(float(step.quantity), ledger.state.positions[step.symbol].quantity)
                    record_exits(ledger.close_resolved([dict(symbol=step.symbol, exit_date=day,
                        exit_price=ledger.opens.at[day, step.symbol], exit_reason='regime_'+step.action.value,
                        quantity=quantity)], phase='open'), day)
                elif step.action == OrderAction.HEDGE:
                    raise ValueError('Unapproved short hedge in frozen LONG-only experiment')
                # CANCEL is represented by replacing the atomic protection group
                # on its remaining quantity; the position is never unprotected.
            for order in queued_weakness:
                position = ledger.state.positions.get(order['symbol'])
                if position is None or position.entry_date != order['entry_date']:
                    weakness_audits.append(dict(order, execution_date=day, status='ALREADY_CLOSED'))
                    continue
                quantity = min(order['quantity'], position.quantity)
                record_exits(ledger.close_resolved([dict(symbol=order['symbol'], exit_date=day,
                    exit_price=ledger.opens.at[day, order['symbol']], quantity=quantity,
                    exit_reason='early_weakness_j5')], phase='open'), day)
                weakness_audits.append(dict(order, execution_date=day, executed_quantity=quantity,
                                            status='EXECUTED'))
            queued_weakness = []
            if pending:
                # Risk owns completed-position concentration history. Native
                # primitives may record partial legs; synchronize before entry
                # rechecks rather than counting a reduction as a full loss.
                ledger._concentration_trade_tracker = deepcopy(session.trades)
                ledger._concentration_loss_tracker = deepcopy(session.losses)
                _, opened = ledger.execute_approved(pending, execution_config=cfg.exec_config)
                for symbol in opened:
                    session.record_fill(f'entry-{symbol}-{day}', day=day.date(), symbol=symbol, entry=True)
            record_exits(ledger.apply_observed_protections(phase='intraday', **options), day)
            scheduled = []
            for symbol, position in ledger.state.positions.items():
                age = ledger.days.get_loc(day)-position.entry_idx
                if day == days[-1] or (v['holding_sessions'] is not None and age >= v['holding_sessions']):
                    scheduled.append(dict(symbol=symbol, exit_date=day,
                        exit_price=ledger.close.at[day, symbol],
                        exit_reason='terminal_close' if day == days[-1] else 'expiry_20_after_entry'))
            record_exits(ledger.close_resolved(scheduled, phase='close'), day)
            if early_weakness_fraction is not None and day != days[-1]:
                for symbol, position in ledger.state.positions.items():
                    # Fifth session including entry: entry_idx +4. Close-only
                    # decision, next-open execution; no repeated half reductions.
                    if ledger.days.get_loc(day)-position.entry_idx != 4:
                        continue
                    spy_entry = float(frames['opens'].at[position.entry_date, 'SPY'])
                    spy_close = float(frames['close'].at[day, 'SPY'])
                    if not np.isfinite(spy_entry) or spy_entry <= 0 or not np.isfinite(spy_close) or spy_close <= 0:
                        raise ValueError('Invalid SPY early weakness reference')
                    ret = float(frames['close'].at[day, symbol]/position.entry_price-1)
                    relative = ret-(spy_close/spy_entry-1)
                    if ret < 0 and relative < 0:
                        queued_weakness.append(dict(symbol=symbol, entry_date=position.entry_date,
                            decision_date=day, quantity=position.quantity*early_weakness_fraction,
                            return_at_decision=ret, relative_spy_at_decision=relative))
            equity = ledger.mark_close()
            if pd.Timestamp(day) not in macro.frame.index:
                raise ValueError(f'Missing macro date {day.date()}')
            regime = build_snapshot(day.date(), config=market_config, equity=equity,
                execution_context='backtest', macro_provider=macro, use_cache=False,
                sentiment_score_provider=lambda lookback: macro.value(day, 'sentiment_score'),
                previous_state=regime_state)
            regime_state = regime.next_state
            transition = RegimeStateMachine().evaluate_from_snapshot(previous_mode, regime)
            previous_mode = transition.to_state
            snapshot = ledger.snapshot(**options)
            queued_steps = []
            if transition.action.is_destructive:
                plan = TransitionHandler().build_plan(transition, list(snapshot.positions), list(snapshot.open_orders))
                queued_steps = list(plan.steps)
                transitions.append({'date': day, 'transition': asdict(transition), 'steps': [asdict(s) for s in plan.steps]})
            pnl = PnLSnapshot(portfolio_high_watermark=max(ledger.state.peak_equity, equity),
                portfolio_current_value=equity, daily_pnl=equity-previous_equity)
            breaker._pnl = pnl
            breaker._cfg = cfg.risk_config.with_overrides(spy_regime_map=spy_regimes)
            breaker.set_spy_regime(day)
            if breaker.is_adaptive:
                window = cfg.risk_config.rolling_peak_window_days
                history = ledger.state.equity_points + [equity]
                breaker.update_adaptive(equity, max(history[-window:]) if window > 0 else max(history))
            breaker.update_regime_streak(regime.mode, equity)
            day_scores = groups.get(day, scores.iloc[:0]).rename(columns={'date': 'trade_date'})
            # Contemporaneous eligibility only. Never use retrospective path flags.
            valid = frames['close'].loc[day].gt(0) & frames['volume'].loc[day].gt(0)
            day_scores = day_scores.loc[day_scores.symbol.isin(valid.index[valid])]
            if quality is not None:
                filled = quality.loc[quality.date.eq(day) & quality.is_filled.fillna(0).ne(0), 'symbol']
                day_scores = day_scores.loc[~day_scores.symbol.isin(filled)]
            pending = session.decide(day.date(), scores=day_scores, snapshot=snapshot, regime=regime,
                close=frames['close'], high=frames['high'], low=frames['low'], volume=frames['volume'],
                transition=transition, pnl=pnl, circuit_breaker=breaker)
            pending = [entry for entry in pending if entry.approved_shares > 0]
            cfg.risk_config = session.resolved_config
            cfg.exec_config = replace(cfg.exec_config, entry_mode=regime.mode,
                regime_max_gross_exposure=session.resolved_config.max_gross_exposure)
            if day == days[-1]:
                pending = []
            decisions.extend({'decision_date': day, **asdict(entry)} for entry in pending)
            regimes.append({'date': day, 'mode': regime.mode, 'data_quality': regime.data_quality,
                'allow_long': regime.allowed_long_entries, 'risk_multiplier': session.resolved_config.risk_multiplier,
                'breaker_scale': breaker.allocation_scale(entry_mode=regime.mode),
                'spy_regime': spy_regimes[day.date()], 'queued_entries': len(pending)})
            previous_equity = equity
            ledger.finish_day()
            ledger.daily[-1]['gross_notional'] = sum(p.quantity*frames['close'].at[day, s]
                for s, p in ledger.state.positions.items())
            if index % 10 == 0 or day == days[-1]:
                pd.DataFrame(ledger.daily).to_parquet(output/'daily.partial.parquet', index=False)
                atomic_json(output/'progress.json', {'status': 'RUNNING', 'completed': index+1,
                    'total': len(days), 'date': str(day.date()), 'positions': len(ledger.state.positions),
                    'closed_legs': len(ledger.state.closed_trades)})
                LOG.info('%s %s %s %d/%d equity=%.2f', policy, variant, day.date(), index+1, len(days), equity)
        error = ledger.reconciliation_error()
        if abs(error) > 1e-6:
            raise AssertionError(f'Cash reconciliation error {error}')
        daily = pd.DataFrame(ledger.daily)
        trades = pd.DataFrame(ledger.state.closed_trades)
        daily.to_parquet(output/'daily.parquet', index=False)
        trades.to_parquet(output/'trades.parquet', index=False)
        atomic_json(output/'decisions.json', decisions)
        atomic_json(output/'regimes.json', regimes)
        atomic_json(output/'transitions.json', transitions)
        atomic_json(output/'early_weakness_orders.json', weakness_audits)
        atomic_json(output/'executions.json', ledger.execution_audits)
        atomic_json(output/'entry_rejections.json', [r for a in ledger.execution_audits
            for r in a.get('explicit_entry_rejections', [])])
        curve = pd.concat([pd.Series([cfg.initial_equity]), daily.equity], ignore_index=True)
        returns = curve.pct_change(fill_method=None).dropna()
        positions_pnl = trades.groupby(['symbol', 'entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
        report = {'status': 'COMPLETED', 'policy': policy, 'variant': variant,
            'requested_start_date': str(start.date()), 'requested_end_date': str(end.date()),
            'first_session': str(days[0].date()), 'terminal_session': str(days[-1].date()),
            'sessions': len(days), 'return_pct': float(daily.equity.iloc[-1]/cfg.initial_equity-1),
            'max_drawdown': float((curve/curve.cummax()-1).min()),
            'sharpe': float(returns.mean()/returns.std()*np.sqrt(252)) if returns.std() > 0 else None,
            'closed_legs': len(trades), 'closed_positions': len(positions_pnl),
            'win_rate': float(positions_pnl.gt(0).mean()) if len(positions_pnl) else None,
            'margin_interest': ledger.interest, 'cash_reconciliation_error': error,
            'mean_gross_exposure_over_equity': float((daily.gross_notional/daily.equity).mean()),
            'current_sectors_non_pit': True, 'simulated_ohlc_not_real_broker_fills': True,
            'macro_lineage': 'daily archived values, not certified per-field publication vintage',
            'phase3_fills_not_committed': sum(len(a['hypothetical_fills_not_committed']) for a in ledger.execution_audits),
            'spy_sma200_warmup_missing_days': sum(value is None for value in spy_regimes.values()),
            'database_writes': False, 'training': False,
            'research_initial_stop_pct': initial_stop_pct,
            'reject_constrained_entries': reject_constrained_entries,
            'early_weakness_fraction': early_weakness_fraction,
            'early_weakness_executions': sum(a['status']=='EXECUTED' for a in weakness_audits),
            'explicit_entry_rejections': sum(len(a.get('explicit_entry_rejections', []))
                for a in ledger.execution_audits),
            'sizing_unchanged': True, 'trailing_unchanged': True}
        atomic_json(output/'report.json', report)
        atomic_json(output/'progress.json', {'status': 'COMPLETED', 'completed': len(days), 'total': len(days)})
        return report
    except Exception as exc:
        atomic_json(output/'progress.json', {'status': 'FAILED', 'error': str(exc),
            'completed': len(ledger.daily), 'total': len(days)})
        pd.DataFrame(ledger.state.closed_trades).to_parquet(output/'trades.partial.parquet', index=False)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('artifacts/research/us_concentrated_replay/prepare-20261006-v1'))
    parser.add_argument('--evidence', type=Path, default=Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1'))
    parser.add_argument('--contract', type=Path, default=Path('artifacts/research/us_concentrated_replay/contract-validation-20261006-v3'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--policy', choices=['ORACLE_TOP10', 'ORACLE_TOP20',
                        'INTERSECTION_ORACLE_TOP10'], default='ORACLE_TOP10')
    parser.add_argument('--variant', choices=['ALL', *VARIANTS], default='ALL')
    parser.add_argument('--max-days', type=int)
    parser.add_argument('--start-date', default='2025-01-01')
    parser.add_argument('--end-date', default='2026-09-30')
    parser.add_argument('--reject-constrained-entries', action='store_true',
        help='Reject whole opening orders incompatible with available portfolio budget, never resize')
    parser.add_argument('--initial-stop-pct', type=float,
        help='Research only: fixed initial stop fraction from actual fill; sizing/TP/trailing unchanged')
    parser.add_argument('--volume-overlay', type=Path, action='append', default=[])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.source/'report.json').read_text(encoding='utf-8'))
    verify_hashes(args.source, manifest['files_sha256'])
    bars = pd.concat([pd.read_parquet(args.source/f'bars-{year}.parquet') for year in (2024, 2025, 2026)])
    bars['date'] = pd.to_datetime(bars.date)
    overlay_path = args.contract/'band_volume_overlay.parquet'
    if overlay_path.exists():
        bars = apply_overlay(bars, pd.read_parquet(overlay_path))
    for path in args.volume_overlay:
        bars = apply_verified_volume_overlay(bars, path)
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0), 'date'].unique()).sort_values()
    frames = {key: bars.pivot(index='date', columns='symbol', values=column).reindex(calendar)
        for key, column in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
    sectors = pd.read_parquet(args.evidence/'current-sector-mapping.parquet').set_index('symbol').sector.to_dict()
    # Read-only archive with enough pre-period yield/SPY warm-up; no collector.
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import event, text
    from scripts.research.us_extreme50_capture import forbid_writes
    engine = get_sqlalchemy_engine()
    event.listen(engine, 'before_cursor_execute', forbid_writes)
    with engine.connect() as conn:
        macro_frame = pd.read_sql(text("SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2024-01-01' AND '2026-09-30'"), conn)
        spy_warmup = pd.read_sql(text("SELECT date, close FROM stock_bars_daily WHERE symbol='SPY' AND date BETWEEN '2024-01-01' AND '2024-09-30'"), conn)
    engine.dispose()
    macro_frame.to_parquet(args.output/'macro-evidence.parquet', index=False)
    spy_warmup['date'] = pd.to_datetime(spy_warmup.date)
    # Only the benchmark needs the extra history; no unobserved equity bars filled.
    extra = pd.DatetimeIndex(spy_warmup.date)
    for key in frames:
        frames[key] = frames[key].reindex(extra.union(frames[key].index)).sort_index()
        if key == 'close':
            frames[key].loc[extra, 'SPY'] = spy_warmup.set_index('date')['close']
    market_config = parse_market_regimes((load_config() or {}).get('market_regimes'))
    if market_config.earnings_shield.enabled or market_config.buyback_blackout.enabled:
        raise ValueError('Historical earnings evidence required before replay')
    scores = decision_rows(pd.read_parquet(args.source/'candidates.parquet'))
    atomic_json(args.output/'contract.json', {'risk': asdict(frozen_backtest_config(calendar[0], calendar[-1]).risk_config),
        'market': asdict(market_config), 'variants': VARIANTS,
        'research_initial_stop_pct': args.initial_stop_pct,
        'requested_start_date': args.start_date, 'requested_end_date': args.end_date,
        'reject_constrained_entries': args.reject_constrained_entries,
        'source_sha256': manifest['files_sha256'], 'sector_sha256': digest(args.evidence/'current-sector-mapping.parquet'),
        'volume_overlays': [{'path': str(p), 'sha256': digest(p), 'non_pit_correction': True}
            for p in args.volume_overlay],
        'code_sha256': {str(p): digest(p) for p in [Path(__file__), Path('backtesting/oracle_portfolio_session.py'),
            Path('backtesting/oracle_portfolio_ledger.py'), Path('backtesting/exit_lifecycle_replay.py')]}})
    reports = []
    variants = list(VARIANTS) if args.variant == 'ALL' else [args.variant]
    atomic_json(args.output/'progress.json', {'status': 'RUNNING', 'completed_runs': 0,
        'total_runs': len(variants)})
    for variant in variants:
        reports.append(run_portfolio(frames=frames, scores=scores, sectors=sectors,
            macro=ArchivedMacro(macro_frame), market_config=market_config, policy=args.policy,
            variant=variant, output=args.output/variant, max_days=args.max_days,
            quality=bars[['date', 'symbol', 'is_filled', 'instrument_id']],
            initial_stop_pct=args.initial_stop_pct,
            reject_constrained_entries=args.reject_constrained_entries,
            start_date=args.start_date, end_date=args.end_date))
        atomic_json(args.output/'progress.json', {'status': 'RUNNING',
            'completed_runs': len(reports), 'total_runs': len(variants), 'last_variant': variant})
    atomic_json(args.output/'report.json', {'status': 'COMPLETED', 'runs': reports})
    atomic_json(args.output/'progress.json', {'status': 'COMPLETED',
        'completed_runs': len(reports), 'total_runs': len(variants)})


if __name__ == '__main__':
    main()
