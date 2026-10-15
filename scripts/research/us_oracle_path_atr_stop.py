"""Frozen SL5 versus one entry ATR rule; native offline TOP5 portfolios only."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from decimal import Decimal
from functools import partial
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from risk_management.config import RiskConfig
from scripts.research import us_oracle_path_top5_leverage_grid as grid
from scripts.research import us_oracle_path_protection_selector as archived
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import parametric_protections
from scripts.research.us_oracle_barrier_trailing_grid import trailing_protections
from scripts.research.us_oracle_path_dynamic_protections import subset_protection
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes

SOURCE = Path('artifacts/research/us_oracle_path_protection_selector/20261014-v1')
ARMS = ('FIXED_SL5', 'ATR1_BOUNDED_5_10')
RISK_FRACTION, TP, TRAIL = .02, .20, .15
LOG = logging.getLogger(__name__)


def sizing_metadata(arm):
    if arm not in ARMS:
        raise ValueError('Unfrozen arm')
    return dict(sizing_unchanged=arm == ARMS[0], sizing_stop_distance_modified=arm != ARMS[0],
        risk_budget_unchanged=True, native_quantity_no_hidden_resize=True,
        trailing_fraction_unchanged=True, trailing_activation_depends_on_initial_stop=True)


def atr_stop_fraction(price, atr):
    if any(isinstance(x, bool) or x is None or not np.isfinite(x) or x <= 0 for x in (price, atr)):
        raise ValueError('Positive finite known price/ATR required; no fallback')
    return float(np.clip(float(atr)/float(price), .05, .10))


@dataclass(frozen=True, slots=True)
class ATRRiskConfig(RiskConfig):
    """Keep observed native ATR unmodified; override ONLY sizing stop distance.

    Base with_overrides returns RiskConfig, so recast after its native conversion
    and validation. Regime dataclass.replace retains this research subtype.
    """
    def stop_distance(self, price, atr):
        return float(Decimal(str(price))*Decimal(str(atr_stop_fraction(price, atr))))

    def with_overrides(self, **overrides):
        native = super(ATRRiskConfig, self).with_overrides(**overrides)
        return type(self)(**{f.name: getattr(native, f.name) for f in fields(RiskConfig) if f.init})


class ATRStopSession(grid.MarginAwareSession):
    def decide(self, day, *, scores, **kwargs):
        entries = super().decide(day, scores=scores, **kwargs)
        ledger = self.ledger_ref[0]
        if not np.isclose(self.resolved_config.risk_per_trade_pct, RISK_FRACTION):
            raise ValueError('Risk budget must not rise with stop width')
        if ledger.arm != ARMS[0] and not isinstance(self.resolved_config, ATRRiskConfig):
            raise ValueError('ATR sizing contract lost in native regime application')
        for e in entries:
            sl = .05 if ledger.arm == ARMS[0] else atr_stop_fraction(e.entry_price, e.atr_20)
            approved = e.approved_shares > 0
            distance = float(Decimal(str(e.entry_price))*Decimal(str(sl)))
            if approved and not np.isclose(e.risk_per_share, distance, atol=1e-10):
                raise ValueError('Risk sizing and frozen entry stop disagree')
            budget = self.resolved_config.account_equity*RISK_FRACTION
            effective = budget*max(0., self.resolved_config.risk_multiplier)
            risk = e.approved_shares*distance
            if approved and risk > effective+1e-6:
                raise ValueError('Native approval exceeds unchanged nominal risk budget')
            audit = dict(decision_date=str(pd.Timestamp(day).date()), symbol=e.symbol, sl=sl,
                atr20_j=float(e.atr_20), close_j=float(e.entry_price), tp=TP, trailing=TRAIL,
                approved=approved, proposed_shares=float(e.proposed_shares), approved_shares=float(e.approved_shares),
                equity_j=float(self.resolved_config.account_equity), risk_budget_fraction=RISK_FRACTION,
                base_risk_budget_usd=budget, native_risk_multiplier=float(self.resolved_config.risk_multiplier),
                effective_risk_budget_usd=effective, approved_nominal_risk_usd=risk,
                decision=str(e.decision), reason=e.decision_reason)
            ledger.stop_decisions[(pd.Timestamp(day), e.symbol)] = audit
            ledger.decision_audits.append(audit)
        return entries


class ATRStopLedger(grid.UnlimitedLedger):
    def __init__(self, cfg, *args, arm, **kwargs):
        if arm not in ARMS:
            raise ValueError('Unfrozen arm')
        self.arm, self.stop_decisions = arm, {}
        self.decision_audits, self.fill_audits = [], []
        super().__init__(cfg, *args, sl=.05, trail=TRAIL, tp=TP, **kwargs)
        # UnlimitedLedger's original grid budget .4*SL must NOT be recomputed
        # for a wider stop: both arms retain .4*.05=2% of equity.
        if not np.isclose(cfg.risk_config.risk_per_trade_pct, RISK_FRACTION):
            raise ValueError('Unexpected initial risk budget')
        if arm != ARMS[0]:
            native = replace(cfg.risk_config, fixed_stop_pct=None)
            cfg.risk_config = ATRRiskConfig(**{f.name: getattr(native, f.name) for f in fields(RiskConfig) if f.init})

    def _build_entry_protections(self, phase3, *, execution_config):
        if self.arm == ARMS[0]:
            result = super()._build_entry_protections(phase3, execution_config=execution_config)
        else:
            native = OraclePortfolioLedger._build_entry_protections(self, phase3, execution_config=execution_config)
            if native.signals_df.empty:
                return native
            parts = []
            for row in native.signals_df.itertuples(index=False):
                decision = pd.Timestamp(row.trade_date).normalize()
                if decision >= self.current_day:
                    raise ValueError('Stop must be selected before actual fill')
                audit = self.stop_decisions[(decision, row.symbol)]
                if not audit['approved']:
                    raise ValueError('Stop without prior risk approval')
                p = parametric_protections(subset_protection(native, row.symbol), sl_pct=audit['sl'], tp_pct=TP)
                parts.append(trailing_protections(p, TRAIL))
            frames = {n: pd.concat([getattr(p, n) for p in parts], ignore_index=True)
                for n in ['signals_df', 'protection_frame', 'order_lifecycle_frame', 'broker_event_frame']}
            result = replace(native, **frames)
        for row in result.signals_df.itertuples(index=False):
            audit = self.stop_decisions[(pd.Timestamp(row.trade_date).normalize(), row.symbol)]
            self.fill_audits.append(dict(audit, fill_date=str(self.current_day.date()),
                fill_price=float(row.fill_price), attempted_qty=float(row.filled_qty),
                attempted_nominal_risk_usd=float(row.filled_qty)*float(row.fill_price)*audit['sl'],
                stop_price=float(row.replay_initial_stop_price),
                note='synthetic fill attempt; actual commit audited via executions.json'))
        return result


def freeze(output):
    marker = output/'protocol.json'
    if marker.exists():
        p = grid.read(marker); verify_hashes(Path('.'), p['sources']); return p
    prior = grid.read(SOURCE/'protocol.json'); report = grid.read(SOURCE/'report.json')
    verify_hashes(SOURCE, report['files'])
    verify_hashes(Path('.'), prior['sources'])
    if report['status'] != 'COMPLETED_EXPLORATORY' or grid.read(SOURCE/'completion-audit.json')[
            'status'] != 'TWELVE_CASES_AND_FROZEN_DECISIONS_VERIFIED':
        raise ValueError('Qualified same-model baseline archives required')
    sources = dict(prior['sources']); sources.update(code_hashes())
    for path in [SOURCE/'protocol.json', SOURCE/'report.json', SOURCE/'completion-audit.json',
        SOURCE/'ready.json', SOURCE/'candidates.parquet', SOURCE/'annual-features.parquet',
        Path(__file__), Path('tests/test_us_oracle_path_atr_stop.py'),
        Path('scripts/research/us_oracle_path_atr_stop_review.py'),
        Path('doc/ml/oracle_path_atr_stop_20261014.md'), Path('risk_management/config.py'),
        Path('risk_management/position_sizer.py'), Path('risk_management/portfolio_builder.py'),
        Path('risk_management/regime_apply.py'), Path('backtesting/risk_bridge.py'),
        Path('backtesting/oracle_portfolio_session.py'), Path('scripts/research/us_oracle_path_protection_selector.py')]:
        sources[str(path)] = digest(path)
    for year in grid.ENDS:
        folder = SOURCE/f'{year}-FIXED_REFERENCE'
        case = grid.read(folder/'case-report.json'); verify_hashes(folder, case['files'])
        for name in ['case-report.json', 'daily.parquet', 'trades.parquet']:
            sources[str(folder/name)] = digest(folder/name)
    p = dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(), source=str(SOURCE), annual_models=prior['annual_models'],
        years=grid.ENDS, arms=ARMS, cases=6, top=5, direction='EXPLICIT_LONG_NOT_LEARNED',
        atr_rule='SL fraction = clip(native raw-split ATR20 at J / close_J, .05, .10); one ATR, not tuned',
        atr_basis='native risk _build_prices: rolling20 true range on raw split-adjusted OHLC, history <=J',
        tp=TP, trailing=TRAIL, risk_fraction=RISK_FRACTION,
        risk='same nominal 2% equity budget; native regime/vol/circuit constraints unchanged; wider stop -> fewer shares',
        timing='SL percentage chosen at J, anchored to fill J+1, never widened subsequently',
        entry_gap='native absolute gap<=3%; approved quantities not increased at next-open commit',
        capital_usd=4000, leverage_cap=2, position_cap=.4, no_reinforcement=True,
        no_time_or_terminal_sale=True, annual_capital_reset=True,
        costs_financing_margin='identical native canonical costs, debit6.5% ACT360 and maintenance guards',
        reference_must_equal_archived_native_trades_and_daily_curve=True,
        fixed_prior_knowledge='2024-2026 already inspected; bounds inherited from fixed-stop grid, not optimization',
        promotion_gate='six complete, reference exact, ATR return higher and DD no worse in every period',
        training=False, sql_writes=False, broker_calls=False, production_changed=False,
        independent_holdout=False, reserves=prior['reserves'], sources=sources,
        prices=prior['prices'], macro=prior['macro'], market=prior['market'], events=prior['events'])
    atomic_json(marker, p)
    return p


_CACHE = None


def worker_init(output):
    global _CACHE
    archived.worker_init(SOURCE)  # archived prices/context only; no fit or inference
    _CACHE = dict(archived._CACHE, root=Path(output), protocol=grid.read(Path(output)/'protocol.json'))


def committed_fills(ledger):
    result = []
    for event in ledger.execution_audits:
        day = pd.Timestamp(event['date'])
        for symbol in event['opened']:
            matches = [a for a in ledger.fill_audits if pd.Timestamp(a['fill_date']) == day and a['symbol'] == symbol]
            if len(matches) != 1:
                raise ValueError('Actual fill without unique entry stop/risk audit')
            a = matches[0]
            if not .05 <= a['sl'] <= .10 or not np.isclose(a['stop_price'], a['fill_price']*(1-a['sl']), atol=1e-8):
                raise ValueError('Actual fill SL differs from frozen percentage')
            # Next-open gap can change nominal risk, never silently claim exact
            # same dollar risk at the fill as at previous close.
            if a['attempted_nominal_risk_usd'] > a['effective_risk_budget_usd']*1.03+1e-5:
                raise ValueError('Actual initial risk exceeds J budget plus allowed 3% gap')
            result.append(a)
    return result


def verify_closed_stops(trades, fills, events):
    for t in trades.itertuples(index=False):
        matches = []
        for a in fills:
            if pd.Timestamp(a['fill_date']) != t.entry_date:
                continue
            alias, ratio = a['symbol'], 1.
            for e in events:
                if alias == e['source'] and t.entry_date <= pd.Timestamp(e['day']) <= t.exit_date:
                    alias = e['target']; ratio *= float(e['ratio'])
            if alias == t.symbol:
                matches.append((a, ratio))
        if len(matches) != 1:
            raise ValueError('Closed lot entry/CA lineage ambiguous')
        a, ratio = matches[0]
        if t.side != 'buy' or not np.isclose(t.replay_initial_stop_price, a['fill_price']*(1-a['sl'])/ratio, atol=1e-6):
            raise ValueError('Closed lot initial stop was revised')
        if not np.isclose(t.replay_take_profit_price, a['fill_price']*1.2/ratio, atol=1e-6) or not np.isclose(
                t.replay_trailing_stop_pct, TRAIL, atol=1e-12):
            raise ValueError('TP20/trailing15 changed')
    if len(trades) and trades.exit_reason.isin(['terminal_close', 'expiry_open', 'expiry_20_after_entry']).any():
        raise ValueError('Unexpected forced/time liquidation')


def run_case(case):
    year, arm = case
    folder = _CACHE['root']/f'{year}-{arm}'; folder.mkdir(exist_ok=True)
    marker = folder/'case-report.json'
    if marker.exists():
        saved = grid.read(marker)
        if saved['status'] == 'COMPLETED':
            verify_hashes(folder, saved['files']); return saved
    refs = []
    def factory(cfg, **kwargs):
        ledger = ATRStopLedger(cfg, arm=arm, study_end=grid.ENDS[year], cash_policy='STRICT',
            events=_CACHE['protocol']['events'], **kwargs)
        refs.append(ledger); return ledger
    try:
        with (folder/'stderr.log').open('a', encoding='utf-8') as log, redirect_stderr(log), redirect_stdout(log):
            logging.basicConfig(level=logging.WARNING, stream=log, force=True)
            result = run_portfolio(frames=_CACHE['frames'], scores=_CACHE['candidates'][_CACHE['candidates'].year.eq(year)],
                sectors=_CACHE['sectors'], macro=_CACHE['macro'], market_config=_CACHE['market'], policy='selected',
                variant='CURRENT_NO_EXPIRY', output=folder, start_date=f'{year}-01-01', end_date=grid.ENDS[year],
                quality=_CACHE['prices'][['date', 'symbol', 'is_filled', 'instrument_id']], ledger_factory=factory,
                session_factory=partial(ATRStopSession, ledger_ref=refs),
                protection_options=dict(take_profit_enabled=True, trailing_enabled=True),
                daily_exit_policy=grid.margin_policy, reject_constrained_entries=True)
        ledger = refs[0]
        daily, trades = (pd.read_parquet(folder/n) for n in ['daily.parquet', 'trades.parquet'])
        fills = committed_fills(ledger)
        verify_closed_stops(trades, fills, _CACHE['protocol']['events'])
        open_rows = [dict(symbol=s, entry_date=str(p.entry_date.date()), quantity=p.quantity,
            entry_cost=p.entry_cost, mark_price=float(ledger.close.at[pd.Timestamp(grid.ENDS[year]), s]),
            unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(grid.ENDS[year]), s])-p.entry_cost)
                    for s, p in ledger.state.positions.items()]
        realized = float(trades.pnl.sum()) if len(trades) else 0.
        unrealized = sum(a['unrealized_pnl_usd'] for a in open_rows)
        if not np.isclose(4000+realized+unrealized-ledger.interest, daily.equity.iloc[-1], atol=1e-6):
            raise ValueError('Final net wealth does not reconcile')
        parity = False
        if arm == ARMS[0]:
            for name in ['trades.parquet', 'daily.parquet']:
                pd.testing.assert_frame_equal(pd.read_parquet(folder/name),
                    pd.read_parquet(SOURCE/f'{year}-FIXED_REFERENCE'/name), check_exact=True)
            parity = True
        for name, value in [('stop-decisions.json', ledger.decision_audits), ('attempted-fills.json', ledger.fill_audits),
            ('committed-fills.json', fills), ('open-positions.json', open_rows), ('maintenance.json', ledger.margin_audits)]:
            atomic_json(folder/name, value)
        pnl = trades.groupby(['symbol', 'entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
        gross = daily.gross_notional/daily.equity
        sls = np.asarray([a['sl'] for a in fills])
        result.update(status='COMPLETED', year=year, arm=arm, case=f'{year}-{arm}',
            batch_id=_CACHE['protocol']['annual_models'][str(year)]['batch_id'],
            final_capital_usd=float(daily.equity.iloc[-1]), net_return_pct=100*result['return_pct'],
            dd_pct=100*result['max_drawdown'], realized_pnl_usd=realized, unrealized_pnl_usd=unrealized,
            gains_usd=float(pnl[pnl > 0].sum()), losses_usd=float(pnl[pnl < 0].sum()),
            executed_positions=len(fills), open_positions=len(open_rows),
            mean_gross_leverage=float(gross.mean()), max_gross_leverage=float(gross.max()),
            committed_stop_min_pct=float(sls.min()*100) if len(sls) else None,
            committed_stop_median_pct=float(np.median(sls)*100) if len(sls) else None,
            committed_stop_max_pct=float(sls.max()*100) if len(sls) else None,
            committed_at_upper_bound=int(np.isclose(sls, .10).sum()),
            baseline_native_curve_trades_exact=parity, closed_stop_contracts_verified=len(trades),
            risk_budget_fraction=RISK_FRACTION, no_stop_widening_after_entry=True,
            exit_reasons=trades.exit_reason.value_counts().to_dict() if len(trades) else {},
            margin_breaches=sum(a['breach'] for a in ledger.margin_audits),
            **sizing_metadata(arm))
        # Replace a legacy generic-report flag, not any trades/curve/parameters.
        atomic_json(folder/'report.json', dict(grid.read(folder/'report.json'), **sizing_metadata(arm)))
        result['files'] = {f.name: digest(f) for f in folder.iterdir()
            if f.suffix in ['.json', '.parquet'] and f.name != 'case-report.json'}
    except Exception as exc:
        import traceback
        (folder/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        result = dict(status='FAILED', year=year, arm=arm, case=f'{year}-{arm}', error_type=type(exc).__name__, error=str(exc))
    atomic_json(marker, result)
    return result


def run(output, workers=3):
    root = Path(output)
    with exclusive_run(root):
        protocol = freeze(root)
        reports = []
        cases = [(y, arm) for y in grid.ENDS for arm in ARMS]
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(str(root),)) as pool:
            futures = [pool.submit(run_case, c) for c in cases]
            for future in as_completed(futures):
                result = future.result(); reports.append(result)
                atomic_json(root/'progress.json', dict(status='RUNNING', finished=len(reports), total=6,
                    failed=sum(r['status'] == 'FAILED' for r in reports), last=result['case']))
                atomic_json(root/'report.partial.json', dict(cases=reports))
                LOG.info('%s %s; %s/6', result['case'], result['status'], len(reports))
        verify_hashes(Path('.'), protocol['sources'])
        comparisons = []
        for year in grid.ENDS:
            group = {r['arm']: r for r in reports if r['year'] == year and r['status'] == 'COMPLETED'}
            if len(group) != 2:
                continue
            a, b = group[ARMS[0]], group[ARMS[1]]
            comparisons.append(dict(year=year, fixed_return_pct=a['net_return_pct'], atr_return_pct=b['net_return_pct'],
                delta_return_points=b['net_return_pct']-a['net_return_pct'], fixed_dd_pct=a['dd_pct'], atr_dd_pct=b['dd_pct'],
                delta_dd_points=b['dd_pct']-a['dd_pct']))
        failed = sum(r['status'] == 'FAILED' for r in reports)
        passed = len(comparisons) == 3 and not failed and all(
            c['delta_return_points'] > 0 and c['delta_dd_points'] >= 0 for c in comparisons)
        verdict = 'PARTIAL_FAILED' if failed else 'EXPLORATORY_ATR_GAIN_TO_CONFIRM' if passed else 'NO_GO_STABLE_ATR_STOP_ADVANTAGE'
        report = dict(status='PARTIAL_FAILED' if failed else 'COMPLETED_EXPLORATORY', verdict=verdict,
            cases=reports, comparisons=comparisons, training=False, sql_writes=False, broker_calls=False,
            production_changed=False, independent_holdout=False, source_hashes_verified=True,
            files={str(f.relative_to(root)): digest(f) for f in root.rglob('*')
                if f.suffix in ['.json', '.parquet'] and f.name not in ['report.json', 'progress.json']})
        pd.DataFrame([{k: v for k, v in r.items() if k != 'files'} for r in reports]).to_csv(root/'annual-summary.csv', index=False)
        atomic_json(root/'report.json', report)
        atomic_json(root/'progress.json', dict(status=report['status'], verdict=verdict, finished=6, failed=failed, total=6))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, choices=[1, 2, 3], default=3)
    args = parser.parse_args(); Path(args.output).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(),
        logging.FileHandler(Path(args.output)/'stderr.log', encoding='utf-8')])
    try:
        run(**vars(args))
    except Exception as exc:
        atomic_json(Path(args.output)/'progress.json', dict(status='FAILED', error=str(exc), error_type=type(exc).__name__))
        raise
