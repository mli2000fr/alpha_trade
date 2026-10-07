"""Bounded MP/BAND refresh and execution-contract audit; no SQL or replay.

Provider responses are evidence as observed now, never silent historical repairs.
Only research artifacts are written. Production defaults are not modified.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import json
from pathlib import Path
import ssl

import pandas as pd

from common.trading_costs import TradingCostModel
from execution_engine.config import ExecutionConfig, TimeStopConfig, load_time_stop_config_from_yaml
from risk_management.config import load_risk_config


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str,
                               allow_nan=False), encoding='utf-8')


def frozen_configs():
    """Explicit historical research intent, NOT a claim of current live parity."""
    risk = load_risk_config(equity=4000, preset_key='capital_2001_5000', cli_overrides={
        'account_equity': 4000, 'max_positions': 8, 'allow_fractional_shares': True, 'best_horizon': 20,
        'max_sector_weight': .5, 'max_portfolio_drawdown_pct': .15,
        'recovery_pct': .92, 'target_annual_vol': .13,
        '_atr_stop_multiple_map': {20: 2.5},
        '_tp_atr_multiple_map': {20: 3.0}, '_tp_max_pct_map': {20: .07},
    })
    execution = ExecutionConfig(broker_mode='paper', dry_run=True, account_type='margin',
        execution_profile='custom', swing_only=False, max_entry_gap_pct=.03,
        regime_max_gross_exposure=risk.max_gross_exposure,
        allow_fractional_shares=True, simulated_account_equity=4000, trailing_pct_override=None,
        trailing_pct_long_override=None, trailing_pct_short_override=None,
        trailing_activation_r_multiple=0, time_stop=TimeStopConfig(enabled=False))
    return risk, execution


def frozen_backtest_config(start, end):
    """Single constructor for the future replay; no global defaults changed."""
    from backtesting.simulator import BacktestConfig
    from backtesting.microstructure import MicrostructureConfig
    from backtesting.risk_overlay import RiskOverlayConfig, SectoralCapConfig, DrawdownCircuitBreaker
    from backtesting.trading_constraints import TradingConstraintConfig
    risk, execution = frozen_configs()
    return BacktestConfig(
        start_date=pd.Timestamp(start).date(), end_date=pd.Timestamp(end).date(),
        initial_equity=4000, risk_config=risk, exec_config=execution,
        use_canonical_costs=True, margin_interest_rate_annual=.075,
        atr_risk_stop_multiple=2.5, tp_atr_multiple=3, tp_max_pct=.07,
        trailing_stop_long_pct=None, trailing_stop_short_pct=None,
        min_score_threshold=0, research_sizing=False, require_replay_quantities=True,
        require_replay_protections=True,
        execution_replay_mode='execution_replay', protection_replay_mode='protection_replay',
        watcher_replay_mode='watcher_replay', exit_lifecycle_replay_mode='exit_lifecycle_replay',
        trading_constraints=TradingConstraintConfig(account_type='margin', swing_only=False),
        microstructure=MicrostructureConfig(max_entry_gap_pct=.03, intrabar_priority='conservative'),
        risk_overlay=RiskOverlayConfig(
            sectoral_cap=SectoralCapConfig(enabled=True, max_sector_exposure_pct=.5),
            target_annual_vol=.13,
            drawdown_breaker=DrawdownCircuitBreaker(enabled=True, max_dd_pct=.15,
                recovery_pct=.92, rolling_peak_window_days=risk.rolling_peak_window_days,
                degraded_entry_allocation_pct=risk.degraded_entry_allocation_pct,
                regime_ramp_up_enabled=risk.regime_ramp_up_enabled,
                regime_ramp_up_pct_per_day=risk.regime_ramp_up_pct_per_day,
                regime_ramp_up_max_pct=risk.regime_ramp_up_max_pct,
                regime_ramp_up_peak_window_days=risk.regime_ramp_up_peak_window_days,
                policy=risk.policy)),
    )


def validate_replay_tape(signals, calendar):
    """Reject missing/ambiguous lifecycle anchors before invoking the engine."""
    import numpy as np
    days = pd.DatetimeIndex(calendar)
    if not days.is_monotonic_increasing or days.has_duplicates:
        raise ValueError('Invalid trading calendar')
    required = ['symbol', 'trade_date', 'execution_date', 'filled_qty', 'fill_price',
                'replay_take_profit_price', 'replay_initial_stop_price', 'replay_trailing_stop_pct']
    if any(c not in signals for c in required):
        raise ValueError('Incomplete replay tape columns')
    if signals.duplicated(['symbol', 'execution_date']).any():
        raise ValueError('Ambiguous duplicate replay entries')
    for row in signals.to_dict('records'):
        values = [float(row[c]) for c in required[3:]]
        if not np.isfinite(values).all() or min(values) <= 0:
            raise ValueError('Invalid replay protection/quantity')
        signal, entry = pd.Timestamp(row['trade_date']), pd.Timestamp(row['execution_date'])
        pos = days.searchsorted(signal, side='right')
        if pos >= len(days) or days[pos] != entry:
            raise ValueError('Replay entry is not next session')
        short = row.get('side') == 'sell'
        fill, stop, tp = row['fill_price'], row['replay_initial_stop_price'], row['replay_take_profit_price']
        if not ((tp < fill < stop) if short else (stop < fill < tp)):
            raise ValueError('Invalid directional protection anchors')
        transition = row.get('watcher_transition_effective_date')
        if transition is not None and pd.notna(transition) and pd.Timestamp(transition) <= entry:
            raise ValueError('Watcher transition must follow entry session')
        exit_day = row.get('replay_exit_date')
        if exit_day is not None and pd.notna(exit_day):
            if pd.Timestamp(exit_day) < entry or pd.Timestamp(exit_day) not in days:
                raise ValueError('Invalid replay exit date')
            exit_price = float(row.get('replay_exit_price', float('nan')))
            if not np.isfinite(exit_price) or exit_price <= 0 or not row.get('replay_exit_reason'):
                raise ValueError('Invalid replay exit')


def classify_bar(symbol, archived, refreshed):
    """A repeated vendor value alone is not independent certification."""
    if refreshed is None:
        return 'BLOCKED_PROVIDER_REFRESH'
    for column in ('open', 'high', 'low', 'close'):
        if column in archived and (refreshed.get(column) is None or
                abs(float(archived[column]) - float(refreshed[column])) > .005):
            return 'RESERVED_PRICE_DISAGREEMENT'
    if symbol == 'BAND':
        volume = refreshed.get('volume')
        if volume is None or pd.isna(volume) or float(volume) <= 0:
            return 'RESERVED_ZERO_VOLUME_REPRODUCED_BY_VENDOR'
        return 'VENDOR_VOLUME_CORRECTION_AVAILABLE_NOT_APPLIED'
    close = refreshed.get('close')
    if close is None or abs(float(close) - float(archived['close'])) > .005:
        return 'RESERVED_PRICE_DISAGREEMENT'
    return 'JUMP_CORROBORATED_EVENT_AND_INDEPENDENT_CLOSE'


def require_economic_gate(report, root=Path('.')):
    """Fail closed for future callers; fingerprints do not mean parity passed."""
    for path, expected in report['source_hashes'].items():
        actual = hashlib.sha256((Path(root)/path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Execution source changed: {path}')
    if report['status'] != 'READY_FOR_ECONOMIC_REPLAY' or report['contract']['blockers']:
        raise ValueError('Economic replay blocked: contract parity not certified')


def run(source, output, refresh=False):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cases = [('MP', '2025-07-10', '2025-07-08', '2025-07-11'),
             ('BAND', '2026-06-18', '2026-06-15', '2026-06-23')]
    session = tracker = None
    if refresh:
        import requests
        from service.eodhd.quota import EodhdQuotaTracker
        trust = output/'windows-trust.pem'
        trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in
                         ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
        session = requests.Session()
        session.verify = str(trust.resolve())
        tracker = EodhdQuotaTracker(cache_dir=output/'provider_quota')
    results = []
    for symbol, day, start, end in cases:
        bars = pd.read_parquet(source/f'bars-{day[:4]}.parquet')
        match = bars[bars.symbol.eq(symbol) & pd.to_datetime(bars.date).eq(pd.Timestamp(day))]
        if len(match) != 1:
            raise ValueError(f'Expected exactly one archived bar: {symbol}/{day}')
        archived = {k: match.iloc[0][k] for k in ('open', 'high', 'low', 'close', 'adj_close', 'volume')}
        payload, error = [], None
        if not refresh and (output/f'{symbol}_eod.json').exists():
            payload = json.loads((output/f'{symbol}_eod.json').read_text(encoding='utf-8'))
        if refresh:
            from service.eodhd.clientEodhd import fetch_eod
            try:
                payload = fetch_eod(symbol, start=start, end=end, session=session,
                                    tracker=tracker, feature='concentrated_contract_audit')
                dump(output/f'{symbol}_eod.json', payload)
            except Exception as exc:
                # Exception text/URLs can contain credentials: deliberately omit them.
                error = type(exc).__name__
        refreshed = next((b for b in payload if b.get('date') == day), None)
        results.append(dict(symbol=symbol, date=day, archived=archived, refreshed=refreshed,
                            raw_payload_sha256=(hashlib.sha256((output/f'{symbol}_eod.json').read_bytes()).hexdigest()
                                                if (output/f'{symbol}_eod.json').exists() else None),
                            error_class=error, status=classify_bar(symbol, archived, refreshed)))
    if session:
        session.close()
    risk, execution = frozen_configs()
    current = load_risk_config(equity=4000, preset_key='capital_2001_5000',
                              cli_overrides={'account_equity': 4000, 'max_positions': 8})
    actual_time = load_time_stop_config_from_yaml()
    contract = dict(
        research_intent=dict(risk=asdict(risk), execution=asdict(execution)),
        current_resolution_without_explicit_overrides=dict(
            default_horizon=current.best_horizon, default_stop_atr=current.atr_stop_multiple_for(),
            default_tp=current.tp_params_for(), h20_stop_atr=current.atr_stop_multiple_for(20),
            h20_tp=current.tp_params_for(20), time_stop=asdict(actual_time),
            execution_dataclass_long_trailing_override=ExecutionConfig().trailing_pct_long_override),
        equity_wiring='CLI already overrides account_equity explicitly; equity argument alone is insufficient for a custom research adapter',
        required_replay_path=dict(engine_mode='pipeline', phase2='risk_execution',
            phase3='execution_replay', phase4='protection_replay', phase5='watcher_replay',
            phase7='exit_lifecycle_replay', research_sizing=False,
            quantities=['filled_qty', 'approved_shares', 'target_shares'],
            missing_quantity='FAIL_CLOSED_IN_RESEARCH_ADAPTER_NOT_SIMULATOR_FALLBACK',
            entry='next session open', intrabar='conservative',
            end='2026-09-30 terminal liquidation, not forced H20 exit'),
        cost_semantics=dict(canonical_half_spread_bps=5, commission_bps_per_leg=1,
            slippage_bps_per_leg=2, margin_interest_annual=.075,
            simulator_extra_entry_penalty_bps=0,
            simulator_full_spread_fallback_bps=10,
            simulator_quote_spread_semantics='full spread divided by two per leg',
            indicative_first_order_round_trip_bps=[
                dict(spread_parameter=s, canonical=TradingCostModel(spread_bps=s).round_trip_cost_bps,
                     simulator_without_microstructure=2*(1+2+s))
                for s in (5, 10)],
            warning='First-order component audit only, not an executed trade PnL or certified fill model'),
        blockers=[
            'HISTORICAL_TAPES_NOT_YET_ASSEMBLED_OR_COMPARED',
            'SHORT_BORROW_AVAILABILITY_AND_FEES_NOT_CERTIFIED',
            'TOP20_OTHER_PRICE_PATH_RESERVATIONS_REMAIN'],
    )
    paths = ['config.yaml', 'risk_management/config.py', 'risk_management/position_sizer.py',
             'common/trading_costs.py', 'backtesting/simulator.py', 'backtesting/cli/_impl.py',
             'execution_engine/config.py', 'execution_engine/protection_watcher.py']
    report = dict(as_of=str(date.today()), database_writes=False, economic_replay=False,
        status='BLOCKED_BEFORE_ECONOMIC_PERFORMANCE', cases=results, contract=contract,
        source_hashes={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
        independent_evidence=dict(
            mp_event='https://www.sec.gov/Archives/edgar/data/1801368/000119312525157310/d43796d8k.htm',
            mp_close='https://www.cnbc.com/2025/07/10/pentagon-to-become-largest-shareholder-in-rare-earth-magnet-maker-mp-materials.html',
            mp_close_scope='Search-index corroboration of 45.23 USD; page robots denied; not whole-path certification',
            band_volume='No independent volume certification obtained'))
    dump(output/'report.json', report)
    print(json.dumps(dict(status=report['status'], cases=[{'symbol': r['symbol'], 'status': r['status']}
                                                         for r in results]), ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='artifacts/research/us_concentrated_replay/prepare-20261006-v1')
    parser.add_argument('--output', required=True)
    parser.add_argument('--refresh', action='store_true', help='Two bounded EODHD requests; no SQL')
    run(**vars(parser.parse_args()))
