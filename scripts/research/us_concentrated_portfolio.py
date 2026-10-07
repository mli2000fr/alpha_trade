"""Research portfolio adapter: real PositionSizer and simulator cashflows.

Not live parity: open-time decisions, conservative unknown-sector bucket,
entry-before-exit daily ordering and immutable explicit variant exits.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.simulator import BacktestEngine, BacktestResult, BacktestDiagnostics, _RunState
from backtesting.risk_overlay import compute_portfolio_vol_scaler
from risk_management.position_sizer import PositionSizer
from risk_management.models import PriceInfo
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes, digest, apply_overlay
from scripts.research.us_concentrated_exit_variants import VARIANTS

LOG = logging.getLogger(__name__)


class PortfolioEvidenceError(ValueError):
    pass


class StatefulVariantPortfolio(BacktestEngine):
    """Reuse native entry/exit ledgers; do not pre-approve one unit as real size."""

    def run_tape(self, signals, opens, close, high, low, volume, sector_map=None):
        cfg = self.config
        signals = signals.copy()
        signals['signal_date'] = pd.to_datetime(signals.trade_date)
        if (not cfg.use_canonical_costs or cfg.use_tiered_commission
                or cfg.risk_overlay.drawdown_breaker.force_close_on_breaker
                or cfg.entry_limit_offset_pct != 0
                or cfg.cost_round_trip_bps != 0
                or cfg.microstructure.slippage.base_bps != 0
                or cfg.microstructure.slippage.impact_coef != 0
                or cfg.exposure_multiplier != 1
                or cfg.microstructure.execution_model.model != 'next_open'):
            raise ValueError('Unsupported portfolio contract')
        if signals.side.ne('buy').any():
            raise ValueError('LONG-only adapter')
        if signals.duplicated(['symbol', 'execution_date']).any():
            raise ValueError('Duplicate portfolio candidate')
        self._validate_replay_protections(signals, opens)
        days = pd.DatetimeIndex(close.index)
        state = _RunState(settled_cash=float(cfg.initial_equity), peak_equity=float(cfg.initial_equity))
        diagnostics = BacktestDiagnostics()
        groups = {day: group.sort_values(['rank', 'symbol']) for day, group in signals.groupby('execution_date')}
        # Unknown is one conservative shared bucket, NOT one invented sector per ticker.
        sectors = {symbol: (sector_map or {}).get(symbol, 'UNQUALIFIED_PIT_SECTOR') for symbol in close.columns}
        mtm = close.ffill()
        decision_prices = mtm.copy()
        approval_rows = []
        exposure_rows = []
        previous_returns = []
        last_equity = float(cfg.initial_equity)
        adv = (close * volume).rolling(20, min_periods=20).mean().shift(1)
        breaker = cfg.risk_overlay.drawdown_breaker
        for idx, day in enumerate(days):
            if day.date() < cfg.start_date or day.date() > cfg.end_date:
                continue
            self._apply_settlements(state, idx)
            # A missing open of a held position cannot be replaced with today's future close.
            for symbol in state.positions:
                if not np.isfinite(opens.at[day, symbol]) or opens.at[day, symbol] <= 0:
                    raise PortfolioEvidenceError(f'Missing held-position open {symbol}/{day.date()}')
            decision_prices.loc[day] = opens.loc[day]
            equity = state.settled_cash + state.unsettled_cash + self._mark_to_market(state.positions, decision_prices, day)
            state.peak_equity = max(state.peak_equity, equity)
            allowed = breaker.update(equity, state.peak_equity)
            # No SPY/macro regime is fabricated from absent historical context.
            breaker.update_regime_streak(cfg.exec_config.entry_mode, equity)
            scale = breaker.allocation_scale(entry_mode=cfg.exec_config.entry_mode)
            candidates = self._select_candidate_rows(state=state, trade_day=day,
                day_signals=groups.get(day), close_columns=close.columns,
                entries_allowed_by_breaker=allowed, drawdown_allocation_scale=scale,
                entries_allowed_by_regime=True, diagnostics=diagnostics)
            if candidates and self._breakout_tracker is not None:
                self._breakout_tracker.record_selections([str(row['symbol']) for row in candidates], day.date())
                candidates = [row for row in candidates if self._breakout_tracker.allow_entry(str(row['symbol']))]
            vol_scale = compute_portfolio_vol_scaler(pd.Series(previous_returns, dtype=float),
                target_annual_vol=cfg.risk_overlay.target_annual_vol) if cfg.risk_overlay.target_annual_vol else 1.
            for original in candidates:
                row = original.copy()
                symbol = str(row['symbol'])
                equity = state.settled_cash + state.unsettled_cash + self._mark_to_market(state.positions, decision_prices, day)
                risk = cfg.risk_config.with_overrides(account_equity=float(equity))
                atr = float(row['decision_atr'])
                if not np.isfinite(atr) or atr <= 0:
                    raise PortfolioEvidenceError(f'Missing decision ATR {symbol}/{day.date()}')
                proposal = PositionSizer(risk).compute(PriceInfo(symbol, float(row['decision_close']), atr))
                price = float(row['fill_price'])
                gross = self._compute_gross_notional(state.positions, decision_prices, day)
                budget = self._resolve_available_entry_budget(constraints=cfg.trading_constraints,
                    settled_cash=state.settled_cash, current_equity=equity, current_gross_notional=gross)
                fee = self._effective_fees_pct + self._spread_fallback_bps / 2 / 10000
                gross_limit = self._resolve_max_gross_exposure_limit(equity)
                sector = sectors[symbol]
                sector_notional = sum(abs(p.quantity) * float(opens.at[day, s])
                    for s, p in state.positions.items() if sectors[s] == sector)
                sector_room = max(equity * cfg.risk_overlay.sectoral_cap.max_sector_exposure_pct-sector_notional, 0.) if cfg.risk_overlay.sectoral_cap.enabled else float('inf')
                gross_room = max(equity * gross_limit-gross, 0.) if gross_limit is not None else float('inf')
                side_limit = risk.max_long_exposure
                if side_limit is not None:
                    gross_room = min(gross_room, max(equity*side_limit-gross, 0.))
                qty = min(proposal.proposed_shares * max(float(vol_scale), 0.) * max(float(scale), 0.),
                    max(budget, 0.) / (price*(1+fee)), equity*risk.max_position_weight/price,
                    sector_room/price, gross_room/price)
                if risk.max_position_pct_of_adv is not None:
                    liquidity = adv.at[day, symbol]
                    if not np.isfinite(liquidity):
                        raise PortfolioEvidenceError(f'Missing prior ADV {symbol}/{day.date()}')
                    qty = min(qty, liquidity*risk.max_position_pct_of_adv/price)
                qty = self._normalize_trade_quantity(max(qty, 0.))
                if qty*price < risk.effective_min_notional:
                    qty = 0.
                approval = {'date': day, 'symbol': symbol, 'equity_at_open': equity,
                    'proposed_qty_atr': proposal.proposed_shares, 'approved_qty': qty,
                    'cash_before': state.settled_cash, 'gross_before': gross,
                    'sector': sector, 'vol_scale': vol_scale, 'drawdown_scale': scale,
                    'sector_room': sector_room if np.isfinite(sector_room) else None}
                if qty <= 0:
                    approval.update(executed=False, reason='SIZING_OR_PORTFOLIO_CAP')
                    approval_rows.append(approval)
                    continue
                # Check future path evidence only after PIT sizing: an unfinanced
                # candidate cannot create a held position. Never replace an
                # approved candidate on the basis of its future evidence status.
                if row['variant_path_status'] == 'BLOCKED_PRICE_PATH':
                    raise PortfolioEvidenceError(f'Selected path unqualified {symbol}/{day.date()}: {row.get("variant_path_flags", "")}')
                if pd.isna(row.get('replay_exit_date')):
                    raise PortfolioEvidenceError(f'Missing explicit variant exit {symbol}/{day.date()}')
                row['filled_qty'] = qty
                row['approved_shares'] = qty
                row['target_shares'] = qty
                row['target_weight'] = qty*price/equity
                row['target_notional'] = qty*price
                row['quantity_scope'] = 'STATEFUL_RESEARCH_APPROVED_QUANTITY'
                row['decision_reason'] = 'RESEARCH_STATEFUL_ATR_APPROVAL'
                row['sector'] = sector
                # Dynamic scales already applied exactly once, not again in native sizing.
                super()._try_open_entries(state=state, candidate_rows=[row], open_df=opens,
                    high_df=high, low_df=low, close=decision_prices, trade_day=day,
                    day_idx=idx, trading_days=days, adv_usd_df=adv, sector_map=sectors,
                    current_equity=equity, drawdown_allocation_scale=1., diagnostics=diagnostics)
                executed = symbol in state.positions
                if executed and abs(state.positions[symbol].quantity-qty) > 1e-6:
                    raise AssertionError('Approved quantity changed in engine')
                approval.update(executed=executed, reason='ENGINE_ACCEPTED' if executed else 'ENGINE_REJECTED')
                approval_rows.append(approval)
            decision_prices.loc[day] = mtm.loc[day]
            # No same-day proceeds used to finance today's earlier open entries.
            super()._try_close_positions(state=state, close=close, high=high, low=low,
                trade_day=day, day_idx=idx, trading_days=days, adv_usd_df=adv,
                rng=None, diagnostics=diagnostics, current_equity=equity)
            charge = self._accrue_margin_interest(state, annual_rate=cfg.margin_interest_rate_annual)
            self._margin_interest_total += charge
            for symbol in state.positions:
                if not np.isfinite(close.at[day, symbol]) or close.at[day, symbol] <= 0:
                    raise PortfolioEvidenceError(f'Missing held-position close {symbol}/{day.date()}')
            final_equity = state.settled_cash+state.unsettled_cash+self._mark_to_market(state.positions, mtm, day)
            state.equity_points.append(final_equity)
            previous_returns.append(final_equity/last_equity-1)
            last_equity = final_equity
            state.peak_equity = max(state.peak_equity, final_equity)
            if len(state.positions) > cfg.max_positions:
                raise AssertionError('Position capacity exceeded')
            exposure_rows.append({'date': day, 'positions': len(state.positions), 'cash': state.settled_cash,
                'equity': final_equity, 'gross_notional': self._compute_gross_notional(state.positions, mtm, day),
                'margin_interest': charge})
        if state.positions:
            raise PortfolioEvidenceError('Missing terminal liquidation for held positions')
        result = BacktestResult(equity_curve=pd.Series(state.equity_points,
            index=[r['date'] for r in exposure_rows], name='portfolio_value', dtype=float),
            closed_trades_df=pd.DataFrame(state.closed_trades), trade_events_df=pd.DataFrame(state.trade_events),
            diagnostics=diagnostics, tracker_snapshot=self.tracker_snapshot)
        return result, pd.DataFrame(approval_rows), pd.DataFrame(exposure_rows)


def merge_variant_signals(original, variant):
    if variant.variant.nunique() != 1:
        raise ValueError('One variant per portfolio')
    columns = ['candidate_id', 'status', 'exit_date', 'exit_price', 'exit_reason',
               'watcher_effective_date', 'path_flags']
    base = original.drop(columns=['replay_exit_date', 'replay_exit_price', 'replay_exit_reason',
        'status', 'exit_date', 'exit_price', 'exit_reason', 'watcher_effective_date', 'path_flags'], errors='ignore')
    merged = base.merge(variant[columns], on='candidate_id', validate='one_to_one')
    if len(merged) != len(original):
        raise ValueError('Variant candidates do not match original entries')
    merged['execution_date'] = pd.to_datetime(merged.execution_date)
    merged['replay_exit_date'] = pd.to_datetime(merged.exit_date)
    merged['replay_exit_price'] = merged.exit_price
    merged['replay_exit_reason'] = merged.exit_reason
    merged['variant_path_status'] = merged.status
    merged['variant_path_flags'] = merged.path_flags
    merged['watcher_transition_effective_date'] = pd.to_datetime(merged.watcher_effective_date)
    merged['watcher_transition_state'] = np.where(merged.watcher_effective_date.notna(), 'transitioned', 'pending')
    merged['replay_exit_intent_role'] = 'research_explicit_exit'
    merged['replay_oco_sibling_canceled'] = True
    merged['selected'] = True
    merged['side'] = 'buy'
    return merged


def run(source, variants, archive, contract, output, policy='ORACLE_TOP10'):
    source, variants, archive, contract, output = map(Path, (source, variants, archive, contract, output))
    output.mkdir(parents=True, exist_ok=True)
    if (output/'report.json').exists():
        raise ValueError('Output already exists; preserve prior qualification')
    completed = json.loads((variants/'progress.json').read_text())
    if completed['status'] != 'COMPLETED' or completed['completed_dates'] != 437:
        raise ValueError('Incomplete variant tapes')
    originals, tapes = [], []
    for shard in completed['shards']:
        day = shard['date'].replace('-', '')
        verify_hashes(variants/day, shard['files_sha256'])
        marker = json.loads((source/f'{day}-buy'/'report.json').read_text())
        verify_hashes(source/f'{day}-buy', marker['files_sha256'])
        originals.append(pd.read_parquet(source/f'{day}-buy'/'signals.parquet'))
        tapes.append(pd.read_parquet(variants/day/'variant_tapes.parquet'))
    original = pd.concat(originals, ignore_index=True)
    tape = pd.concat(tapes, ignore_index=True)
    original = original[original[policy]].copy()
    tape = tape[tape[policy]].copy()
    raw = json.loads((archive/'report.json').read_text())
    verify_hashes(archive, raw['files_sha256'])
    bars = pd.concat([pd.read_parquet(archive/n) for n in raw['files_sha256'] if n.startswith('bars-')])
    bars['date'] = pd.to_datetime(bars.date)
    cert = json.loads((contract/'report.json').read_text())
    verify_hashes(Path('.'), cert['source_hashes'])
    verify_hashes(contract, {'band_volume_overlay.parquet': cert['band_overlay_sha256']})
    bars = apply_overlay(bars, pd.read_parquet(contract/'band_volume_overlay.parquet'))
    days = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0) & bars.is_filled.eq(0), 'date']).sort_values()
    symbols = sorted(original.symbol.unique())
    market = {c: bars.pivot(index='date', columns='symbol', values=c).reindex(index=days, columns=symbols)
              for c in ('open', 'high', 'low', 'close', 'volume')}
    decision_closes = bars[['date', 'symbol', 'close']].rename(columns={'date': 'trade_date', 'close': 'decision_close'})
    original['trade_date'] = pd.to_datetime(original.trade_date)
    original = original.merge(decision_closes, on=['trade_date', 'symbol'], validate='many_to_one')
    # Recompute the same lagged-to-decision rolling TR20 as the unit assembler.
    atr = BacktestEngine._compute_atr(market['high'], market['low'], market['close'])
    complete = (market['high'].notna() & market['low'].notna() & market['close'].notna()).rolling(20).sum().eq(20)
    atr = atr.where(complete)
    original['decision_atr'] = [atr.at[d, s] for d, s in zip(original.trade_date, original.symbol)]
    original['rank'] = original.selection_rank
    manifest = {'policy': policy, 'variants': VARIANTS, 'adapter_sha256': digest(__file__),
        'variant_report_sha256': digest(variants/'report.json'), 'source_manifest_sha256': digest(source/'manifest.json'),
        'decision_marks': 'open_only', 'entry_exit_order': 'entry_open_before_all_daily_exits',
        'sector_policy': 'ALL_UNQUALIFIED_ONE_SHARED_BUCKET_CAP_50PCT_NOT_PIT_SECTORS',
        'macro_regime': 'NOT_REPLAYED_NO_CONTEXT_ARCHIVE', 'database_writes': False,
        'qualification': 'EXPLORATORY_ADAPTER_NOT_PRODUCTION_PARITY'}
    atomic_json(output/'protocol.json', manifest)
    reports = {}
    for variant in VARIANTS:
        config = frozen_backtest_config('2025-01-01', '2026-09-30')
        signals = merge_variant_signals(original, tape[tape.variant.eq(variant)])
        engine = StatefulVariantPortfolio(config)
        atomic_json(output/f'{variant}-config.json', asdict(config))
        try:
            result, approvals, exposure = engine.run_tape(signals, market['open'], market['close'],
                market['high'], market['low'], market['volume'])
            result.closed_trades_df.to_parquet(output/f'{variant}-trades.parquet', index=False)
            approvals.to_parquet(output/f'{variant}-approvals.parquet', index=False)
            exposure.to_parquet(output/f'{variant}-exposure.parquet', index=False)
            result.trade_events_df.to_parquet(output/f'{variant}-events.parquet', index=False)
            trades = result.closed_trades_df
            gross_pnl = float(((trades.exit_price-trades.entry_price)*trades.quantity).sum()) if len(trades) else 0.
            net_pnl = float(trades.pnl.sum()) if len(trades) else 0.
            identity_error = result.final_value()-(config.initial_equity+net_pnl-engine._margin_interest_total)
            if abs(identity_error) > 1e-6:
                raise AssertionError(f'Cashflow reconciliation failed: {identity_error}')
            reports[variant] = {'status': 'EXPLORATORY_PORTFOLIO_COMPLETED',
                'trades': len(result.closed_trades_df), 'final_equity': result.final_value(),
                'return_pct': (result.final_value()/config.initial_equity-1)*100,
                'max_positions_observed': int(exposure.positions.max()),
                'margin_interest': engine._margin_interest_total,
                'gross_realized_pnl': gross_pnl, 'net_realized_pnl': net_pnl,
                'commission_spread_slippage_total': gross_pnl-net_pnl,
                'cashflow_reconciliation_error': identity_error,
                'max_drawdown_pct': float((result.equity_curve / result.equity_curve.cummax()-1).min()*100),
                'mean_gross_exposure_pct': float((exposure.gross_notional/exposure.equity).mean()*100)}
        except PortfolioEvidenceError as exc:
            reports[variant] = {'status': 'BLOCKED_SELECTED_EVIDENCE', 'error': str(exc)}
        atomic_json(output/'progress.json', {'variants': reports, 'completed_variants': len(reports)})
    report = {'status': 'EXPLORATORY_ADAPTER_QUALIFICATION_NOT_CERTIFIED', 'variants': reports,
        'reserves': ['NON_PIT_SECTORS_CONSERVATIVE_SHARED_BUCKET', 'NO_HISTORICAL_MACRO_REGIME_REPLAY',
                     'SCORE_LINEAGE_AND_CORPORATE_ACTIONS_NOT_CERTIFIED', 'NOT_FULL_PORTFOLIOBUILDER_LIVE_SELECTION_PARITY'],
        'database_writes': False, 'production_changed': False}
    atomic_json(output/'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = 'artifacts/research/us_concentrated_replay/'
    parser.add_argument('--source', default=base+'tapes-history-20261006-v1')
    parser.add_argument('--variants', default=base+'exit-variants-history-20261007-v1')
    parser.add_argument('--archive', default=base+'prepare-20261006-v1')
    parser.add_argument('--contract', default=base+'contract-validation-20261006-v3')
    parser.add_argument('--policy', choices=['ORACLE_TOP10', 'ORACLE_TOP20'], default='ORACLE_TOP10')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    print(json.dumps(run(**vars(args)), default=str))


if __name__ == '__main__':
    main()
