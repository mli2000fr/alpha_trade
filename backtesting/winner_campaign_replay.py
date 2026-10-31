"""Read-only US Oracle-path -> five-minute campaign replay, no broker/provider.

Example: python -m backtesting.winner_campaign_replay --help
Outputs are local, new-directory-only. Existing predictions are required; no
training, automatic prediction, missing-bar download or production SQL write.
"""
import argparse
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import logging
import math
from pathlib import Path
import time
import uuid

import pandas as pd
from sqlalchemy import bindparam, text

LOG = logging.getLogger(__name__)


def atomic_json(path, value):
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')
        for attempt in range(12):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(.1*(attempt+1))
    finally:
        temporary.unlink(missing_ok=True)


class SqlIntradaySource:
    def __init__(self, conn):
        self.conn = conn
        self.receipts = []

    def __call__(self, day, symbols):
        if not symbols:
            return pd.DataFrame()
        query = text('SELECT symbol, bar_timestamp AS timestamp, bar_end_timestamp, '
            'open, high, low, close, volume, payload_hash FROM stock_bars_intraday '
            "WHERE trade_date=:day AND symbol IN :symbols AND interval_code='5m' "
            "AND data_source='alpaca_sip' AND provider='alpaca' AND market_code='US_EQ' "
            "AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 "
            'ORDER BY symbol, bar_timestamp').bindparams(bindparam('symbols', expanding=True))
        frame = pd.read_sql(query, self.conn, params={'day': day, 'symbols': symbols})
        if not frame.empty:
            start, end = pd.to_datetime(frame.timestamp, utc=True), pd.to_datetime(frame.bar_end_timestamp, utc=True)
            if not (end-start).eq(pd.Timedelta(minutes=5)).all() or frame.payload_hash.isna().any():
                raise ValueError('Intraday duration/provenance unqualified')
        self.receipts.append(dict(day=day, symbols=list(symbols), rows=len(frame), sha256=
            hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()))
        return frame


def validate_scores(frame, *, profile_hash, folds, expected_days, top_n, horizon=20,
                    universe_size=None, min_coverage=.9):
    """Validate the complete scoring set BEFORE ranking; never read labels."""
    from modelFactory.oracle_path import target_name
    target = target_name(horizon)
    if frame.empty or frame.duplicated(['trade_date', 'symbol']).any():
        raise ValueError('Empty or duplicate Oracle predictions')
    days = pd.to_datetime(frame.trade_date)
    scores = pd.to_numeric(frame.proba_extreme, errors='coerce')
    expected_hash = pd.to_datetime(frame.fold_start).dt.strftime('%Y-%m-%d').map(
        {k: v['model_sha256'] for k, v in folds.items()})
    # SQL lineage must agree with the immutable training receipt, not merely
    # assert an arbitrary past availability for future-trained weights.
    availability = {}
    for name, fold in folds.items():
        metrics = fold.get('metrics', {})
        bounds = [pd.Timestamp(metrics.get(k)) for k in ('train_available_max', 'val_available_max')]
        if any(pd.isna(value) for value in bounds):
            raise ValueError('Oracle-path lineage: archived availability missing')
        availability[name] = max(bounds).normalize()
    expected_available = pd.to_datetime(frame.fold_start).dt.strftime('%Y-%m-%d').map(availability)
    if (not scores.between(0, 1).all() or not pd.to_datetime(frame.model_available_date).lt(days).all()
            or not frame.target_name.eq(target).all() or not frame.target_horizon.eq(horizon).all()
            or not frame.feature_profile_sha256.eq(profile_hash).all()
            or expected_hash.isna().any() or not frame.model_sha256.eq(expected_hash).all()
            or not pd.to_datetime(frame.model_available_date).eq(expected_available).all()
            or not pd.to_datetime(frame.fold_start).le(days).all()
            or not pd.to_datetime(frame.fold_start).eq(pd.to_datetime(frame.lineage_fold_start)).all()):
        raise ValueError('Oracle-path lineage absent, non-causal or inconsistent with archived model')
    frame = frame.copy()
    frame['trade_date'] = days.dt.date
    counts = frame.groupby('trade_date').size()
    minimum = max(top_n, math.ceil((universe_size or top_n)*min_coverage))
    missing = [f'{day} ({counts.get(day,0)}/{universe_size or top_n})'
               for day in expected_days if counts.get(day, 0) < minimum]
    if missing:
        raise ValueError(f'Couverture Oracle insuffisante (minimum {minimum}) : '+', '.join(missing[:30]))
    ordered = frame.sort_values(['trade_date', 'proba_extreme', 'symbol'], ascending=[True, False, True])
    ordered['rank'] = ordered.groupby('trade_date').cumcount()+1
    ordered['selected'] = ordered['rank'] <= top_n
    ordered['side'] = 'long'
    return ordered.loc[ordered.selected].copy()


def metrics(result, initial):
    curve = result.intraday_equity_curve
    values = pd.concat([pd.Series([initial]), curve.equity], ignore_index=True)
    trades = result.closed_trades_df
    pnl = trades.pnl if not trades.empty else pd.Series(dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    mean = lambda x: float(x.mean()) if len(x) else None
    final = result.final_value()
    meta = result.tracker_snapshot['winner_replay']
    return meta | dict(initial_equity=initial,
        final_equity=final, return_pct=100*(final/initial-1),
        max_drawdown_pct=100*float((values/values.cummax()-1).min()),
        closed_lot_trades=len(pnl), winners=len(wins), losers=len(losses), flat=int(pnl.eq(0).sum()),
        win_pct=100*len(wins)/len(pnl) if len(pnl) else None,
        loss_pct=100*len(losses)/len(pnl) if len(pnl) else None,
        gross_winning_pnl=float(wins.sum()), gross_losing_pnl=float(losses.sum()),
        average_winning_pnl=mean(wins), average_losing_pnl=mean(losses),
        average_winning_holding_days=mean(trades.loc[trades.pnl.gt(0), 'holding_days']) if len(pnl) else None,
        average_losing_holding_days=mean(trades.loc[trades.pnl.lt(0), 'holding_days']) if len(pnl) else None,
        average_gross_capital=mean(curve.gross), maximum_gross_capital=float(curve.gross.max()),
        average_gross_equity_ratio=mean(curve.gross/curve.equity))


def run(args):
    from backtesting.simulator import BacktestConfig, BacktestEngine
    from backtesting.trading_constraints import TradingConstraintConfig
    from common.market_calendar import get_market_calendar
    from common.universe_files import load_universe_file_symbols
    from common.winner_pyramiding import load_winner_pyramiding_config
    from common.daily_bar_sources import preferred_daily_source
    from database.connection import get_sqlalchemy_engine
    from execution_engine.config import ExecutionConfig, load_leverage_config_from_yaml
    from modelFactory.oracle_path.predict import load_contract
    from modelFactory.oracle_path.train import digest
    from risk_management.config import load_risk_config

    if not args.research_assumptions:
        raise ValueError('--research-assumptions required: no historical bid/ask/fill/sector-PIT certification')
    if args.end_date < args.start_date or args.initial_equity <= 0 or not 1 <= args.top_n <= 1000:
        raise ValueError('Invalid dates, equity or TOP-N')
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    atomic_json(output/'progress.json', dict(status='RUNNING', completed=0, phase='READ_ONLY_INPUTS'))
    try:
        root, protocol, _, folds = load_contract(args.artifacts_dir, args.oracle_batch_id)
        from service.options_directional.config import load_options_filter_config
        options_config=load_options_filter_config()
        options_enabled=getattr(args,'options_filter',False)
        if options_enabled is None:
            options_enabled=options_config.enabled
        if options_enabled:
            options_config=replace(options_config,enabled=True,oracle_top_n=args.top_n)
        policy = replace(load_winner_pyramiding_config(), enabled=True)
        leverage = load_leverage_config_from_yaml()
        # An explicit limit may LOWER production leverage, never grant more.
        allowed = min(args.max_leverage, leverage.max_leverage if leverage.enabled else 1.,
            1. if args.account_type == 'cash' else 2.)
        leverage = replace(leverage, max_leverage=allowed, dry_run_simulated_leverage=allowed,
            enabled=allowed > 1, mode='regt_swing' if allowed > 1 else 'disabled')
        exec_cfg = ExecutionConfig(winner_pyramiding=policy, account_type=args.account_type,
            dry_run=True, simulated_account_equity=args.initial_equity, leverage=leverage,
            simulated_margin_buying_power_multiplier=allowed)
        risk = load_risk_config(equity=args.initial_equity)
        if getattr(args, 'factor_model', None) is not None:
            risk = replace(risk, enable_factor_model=args.factor_model)
        if getattr(args, 'max_positions', None) is not None:
            if args.max_positions < 1:
                raise ValueError('Maximum positions must be positive')
            risk = replace(risk, max_positions=args.max_positions)
        risk = replace(risk, max_gross_exposure=min(risk.max_gross_exposure, allowed))
        cfg = BacktestConfig(start_date=args.start_date, end_date=args.end_date, initial_equity=args.initial_equity,
            risk_config=risk, exec_config=exec_cfg, use_canonical_costs=True,
            margin_interest_rate_annual=args.margin_interest_annual,
            cost_round_trip_bps=(2*args.cost_per_leg_bps if getattr(args, 'cost_per_leg_bps', None) is not None else 0.),
            trading_constraints=TradingConstraintConfig(account_type=args.account_type, swing_only=False))
        cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        sessions = [s.session_date for s in cal.sessions(args.start_date-timedelta(days=14), args.end_date) if s.is_open]
        actual = [d for d in sessions if d >= args.start_date]
        if not actual:
            raise ValueError('No requested US sessions')
        prior = max(d for d in sessions if d < actual[0])
        signal_days = [prior]+actual[:-1]
        universe = load_universe_file_symbols(args.symbol_source)
        if not universe:
            raise ValueError('Empty universe')
        engine = get_sqlalchemy_engine(db_name='alpha_trade')
        with engine.connect() as conn, conn.begin():
            # Database-enforced, next transaction read-only; no ensure_table or
            # prediction loader with hidden fallback CREATE is called here.
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('US alpha_trade required')
            query = text('SELECT p.prediction_date AS trade_date, p.symbol, p.proba_extreme, p.fold_start, '
                'l.fold_start AS lineage_fold_start, l.model_available_date, l.target_name, l.target_horizon, '
                'l.model_sha256, l.feature_profile_sha256 FROM oracle_extreme_predictions p '
                'LEFT JOIN oracle_path_prediction_lineage l ON p.batch_id=l.batch_id '
                'AND p.symbol=l.symbol AND p.prediction_date=l.prediction_date '
                'WHERE p.batch_id=:batch AND p.prediction_date>=:start AND p.prediction_date<:end '
                'AND p.symbol IN :symbols').bindparams(bindparam('symbols', expanding=True))
            scores = pd.read_sql(query, conn, params=dict(batch=args.oracle_batch_id, start=prior,
                end=actual[-1], symbols=universe))
            selected = validate_scores(scores, profile_hash=digest(root/'feature_profile.json'),
                folds=folds, expected_days=signal_days, top_n=args.top_n, horizon=protocol['horizon'],
                universe_size=len(universe), min_coverage=getattr(args,'min_oracle_coverage',.9))
            from backtesting.winner_data import daily_bars, HistoricalFactorSource, HistoricalOptionsSource
            symbols = sorted(set(selected.symbol)|({'SPY','IWM','MTUM'} if risk.enable_factor_model else {'SPY'}))
            bars = daily_bars(conn, symbols, prior-timedelta(days=650), actual[-1])
            pivots = {k: bars.pivot(index='date', columns='symbol', values=k).astype(float)
                for k in ('open', 'high', 'low', 'close', 'volume')}
            sectors = pd.read_sql(text('SELECT symbol, sector FROM stock_metadata WHERE symbol IN :symbols').bindparams(
                bindparam('symbols', expanding=True)), conn, params={'symbols': symbols})
            if sectors.duplicated('symbol').any():
                raise ValueError('Ambiguous current sector metadata')
            ca = pd.read_sql(text('SELECT symbol, ca_type, ex_date, payable_date, amount_per_share, currency FROM corporate_actions_events '
                'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end').bindparams(
                bindparam('symbols', expanding=True)), conn, params=dict(symbols=symbols, start=prior, end=args.end_date))
            source = SqlIntradaySource(conn)
            factors = HistoricalFactorSource(conn, pivots['close']) if risk.enable_factor_model else None
            options_source=HistoricalOptionsSource(conn,options_config) if options_enabled else None
            frozen = dict(arguments=vars(args), winner_policy=asdict(policy), risk=asdict(risk),
                leverage=asdict(leverage), costs='canonical BacktestEngine cost model',
                requested_max_leverage=args.max_leverage, allowed_max_leverage=allowed,
                selection='Oracle TOP-N -> CALL/PUT + OI -> risque -> Winner' if options_enabled else 'Oracle TOP-N -> risque -> Winner',
                options_filter=options_config.snapshot() if options_enabled else None,
                options_decision_cutoff='next_entry_session_open_minus_1_second',
                daily_bars_preference=preferred_daily_source(), daily_rows=len(bars),
                daily_sha256=hashlib.sha256(bars.to_csv(index=False).encode()).hexdigest(),
                sectors_sha256=hashlib.sha256(sectors.to_csv(index=False).encode()).hexdigest(),
                corporate_actions_sha256=hashlib.sha256(ca.to_csv(index=False).encode()).hexdigest(),
                current_sectors_non_pit=True, observed_at_utc=datetime.now(UTC),
                model_protocol_sha256=digest(root/'protocol.json'),
                signals_sha256=hashlib.sha256(selected.to_csv(index=False).encode()).hexdigest())
            atomic_json(output/'protocol.json', frozen)
            selected.to_csv(output/'signals.csv', index=False)
            def progress(done, total, day):
                elapsed = time.monotonic()-started
                atomic_json(output/'progress.json', dict(status='RUNNING', completed=done, total=total,
                    last_date=day, elapsed_seconds=elapsed, remaining_seconds_estimate=elapsed*(total-done)/done))
                LOG.info('%d/%d sessions; %s', done, total, day)
            result = BacktestEngine(cfg).run(open_df=pivots['open'], close=pivots['close'], high=pivots['high'],
                low=pivots['low'], volume=pivots['volume'], signals_df=selected,
                sector_map=sectors.set_index('symbol').sector.to_dict(), intraday_source=source,
                winner_research_assumptions=True, winner_progress=progress, winner_corporate_actions=ca.to_dict('records'),
                winner_factor_source=factors,winner_selection_source=options_source)
            atomic_json(output/'data-receipts.json', source.receipts)
            atomic_json(output/'factor-receipts.json', factors.receipts if factors else [])
            atomic_json(output/'options-receipts.json',options_source.receipts if options_source else [])
            if options_source:
                pd.DataFrame([dict(trade_date=r['trade_date'],cutoff_utc=r['cutoff_utc'],**row)
                    for r in options_source.receipts for row in r['rows']]).to_csv(output/'options-selection.csv',index=False)
        result.closed_trades_df.to_csv(output/'trades.csv', index=False)
        result.trade_events_df.to_csv(output/'events.csv', index=False)
        result.intraday_equity_curve.to_csv(output/'equity-5m.csv', index=False)
        result.equity_curve.to_csv(output/'equity-daily.csv')
        result.drawdown_breaker_df.to_csv(output/'risk-5m.csv', index=False)
        report = metrics(result, args.initial_equity)
        from backtesting.simulator import BacktestResult
        annual, opening_equity = [], args.initial_equity
        intraday = result.intraday_equity_curve
        for year in sorted(result.equity_curve.index.year.unique()):
            daily = result.equity_curve.loc[result.equity_curve.index.year == year]
            closed = result.closed_trades_df
            closed = closed.loc[pd.to_datetime(closed.exit_date, utc=True).dt.year.eq(year)] if not closed.empty else closed
            year_result = BacktestResult(equity_curve=daily, closed_trades_df=closed,
                intraday_equity_curve=intraday.loc[pd.to_datetime(intraday.timestamp).dt.year.eq(year)],
                tracker_snapshot={'winner_replay': {'status': report['status'], 'full_live_parity': False}})
            row = metrics(year_result, opening_equity)
            events = result.trade_events_df
            events = events.loc[pd.to_datetime(events.time, utc=True).dt.year.eq(year)]
            row['costs_and_financing'] = float(pd.to_numeric(events.get('costs', pd.Series(dtype=float)), errors='coerce').sum())
            row['year'] = int(year)
            annual.append(row)
            opening_equity = float(daily.iloc[-1])
        pd.DataFrame(annual).to_csv(output/'annual-summary.csv', index=False)
        report.update(allowed_max_leverage=allowed, elapsed_seconds=time.monotonic()-started,
            limitations=['OHLC prices + configurable costs, no historical quotes/fill queue',
                'Current non-PIT sectors; canonical daily history may be revised',
                'Stops can gap; risk caps do not guarantee maximum drawdown',
                'Cash dividends require USD/amount/payment date; share actions abort while held; coverage not certified',
                'Final equity includes marked open holdings; no forced terminal liquidation',
                'Native breaker, sizing/constraints, correlation/concentration and vol target; no full macro tape'])
        export_ui_report(result, report, frozen, output, args.initial_equity)
        atomic_json(output/'report.json', report)
        atomic_json(output/'progress.json', dict(status=report['status'], completed=len(actual), total=len(actual),
            elapsed_seconds=report['elapsed_seconds']))
        LOG.info('Replay %s; final equity %.2f', report['status'], report['final_equity'])
        return report
    except Exception as exc:
        atomic_json(output/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc),
            elapsed_seconds=time.monotonic()-started))
        raise


def export_ui_report(result, report, protocol, output, initial_equity):
    """Keep research metrics and add the standard Backtest page manifest."""
    from backtesting.report import generate_report, save_equity_curve_csv, save_equity_curve
    summary = generate_report(result, initial_equity).to_serializable_dict()
    # Winner observes drawdown intraday, unlike the generic daily summary.
    summary['max_drawdown_pct'] = abs(report['max_drawdown_pct'])
    artifacts = dict(equity_curve_csv=str(save_equity_curve_csv(result, output)),
        equity_curve_png=str(save_equity_curve(result, output)), trades_csv=str(output/'trades.csv'),
        annual_summary_csv=str(output/'annual-summary.csv'))
    report.update(summary=summary, artifacts=artifacts, params=protocol,
        diagnostics=dict(status=report['status'], coverage_gaps=report.get('coverage_gaps', []),
                         limitations=report['limitations']),
        run_metadata=dict(engine='winner_campaign_replay', full_live_parity=False,
                          observed_at_utc=protocol['observed_at_utc']))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle-batch-id', required=True)
    parser.add_argument('--artifacts-dir', default='artifacts/models')
    parser.add_argument('--start-date', type=date.fromisoformat, required=True)
    parser.add_argument('--end-date', type=date.fromisoformat, required=True)
    parser.add_argument('--symbol-source', default='universe-file:config/univers_batch/univers_filtred_tradable.txt')
    parser.add_argument('--top-n', type=int, default=20)
    parser.add_argument('--min-oracle-coverage', type=float, default=.9)
    parser.add_argument('--initial-equity', type=float, default=4000.)
    parser.add_argument('--account-type', choices=['cash', 'margin'], default='margin')
    parser.add_argument('--max-leverage', type=float, choices=[1., 2.], default=2.)
    parser.add_argument('--margin-interest-annual', type=float, default=.065)
    parser.add_argument('--cost-per-leg-bps', type=float, default=None,
        help='Explicit total commission + slippage per leg; omitted = canonical costs')
    parser.add_argument('--max-positions', type=int, default=None, help='Omitted = production risk preset')
    parser.add_argument('--factor-model', action=argparse.BooleanOptionalAction, default=None,
        help='Omitted = production risk config; requires genuinely archived factor inputs')
    parser.add_argument('--options-filter',action=argparse.BooleanOptionalAction,default=None,
        help='Omitted = options_directional_filter.enabled in config.yaml; no historical OI imputation')
    parser.add_argument('--research-assumptions', action='store_true')
    parser.add_argument('--output-dir', required=True)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not 0 < args.min_oracle_coverage <= 1:
        parser.error('Oracle coverage must be in (0,1]')
    if not 0 <= args.margin_interest_annual <= 1:
        parser.error('Invalid annual financing rate')
    if args.cost_per_leg_bps is not None and not 0 < args.cost_per_leg_bps <= 1000:
        parser.error('Cost per leg must be positive and <=1000 bps')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run(args)


if __name__ == '__main__':
    main()
