"""Synthetic trade-count projection, NOT a historical or native portfolio backtest.

No data, API, SQL, model, broker or production configuration is accessed.
The assumed success rate is imposed, not learned or demonstrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def net_return(gross, entry_cost=.0008, exit_cost=.0008):
    """Return on all-in entry cash; exit costs apply to exit notional."""
    if not (-1 <= gross and 0 <= entry_cost and 0 <= exit_cost < 1):
        raise ValueError('Invalid gross return or costs')
    return (1 + gross) * (1 - exit_cost) / (1 + entry_cost) - 1


def paths(wins, *, gain=.20, loss=.10, allocation=.25, capital=4000.,
          entry_cost=.0008, exit_cost=.0008):
    """Sequential unleveraged trades: no overlapping positions or calendar claim."""
    if not 0 < allocation <= 1 or capital <= 0:
        raise ValueError('Unleveraged allocation and positive capital required')
    if not 0 <= gain or not 0 < loss <= 1:
        raise ValueError('Invalid gain/loss')
    flags = np.asarray(wins, dtype=bool)
    if flags.ndim != 2 or not flags.shape[1]:
        raise ValueError('Expected nonempty simulations x trades array')
    returns = np.where(flags, net_return(gain, entry_cost, exit_cost),
                       net_return(-loss, entry_cost, exit_cost))
    curve = capital * np.concatenate([np.ones((len(flags), 1)),
        np.cumprod(1 + allocation * returns, axis=1)], axis=1)
    peaks = np.maximum.accumulate(curve, axis=1)
    drawdown = -(curve / peaks - 1).min(axis=1)
    return curve, drawdown


def distribution(values):
    return {name: float(x) for name, x in zip(('p05', 'median', 'p95'),
        np.quantile(values, [.05, .5, .95]))}


def case(trades, rng, simulations, *, exact, gain=.20):
    if exact:
        winners = round(.7 * trades)
        if not math.isclose(winners / trades, .7):
            raise ValueError('Exact 70 percent requires compatible trade count')
        # Every row has exactly 70% winners, ordering alone is randomized.
        flags = np.argsort(rng.random((simulations, trades)), axis=1) < winners
    else:
        flags = rng.random((simulations, trades)) < .7
    curves, dd = paths(flags, gain=gain)
    return dict(trades=trades, exact_win_count=exact, assumed_probability=.7,
        average_winning_gross_return=gain, final_capital_usd=distribution(curves[:, -1]),
        return_pct=distribution(100 * (curves[:, -1] / 4000 - 1)),
        closed_equity_drawdown_pct=distribution(100 * dd),
        realized_win_rate=distribution(flags.mean(axis=1)),
        probability_final_loss=float((curves[:, -1] < 4000).mean()))


def run(output, simulations=10000, seed=20261015):
    if simulations < 100:
        raise ValueError('At least 100 simulations required')
    if output.exists():
        raise FileExistsError('Use a fresh output path; do not overwrite research')
    output.mkdir(parents=True)
    rng = np.random.default_rng(seed)
    protocol = dict(experiment='SYNTHETIC_ASSUMED_70_PERCENT_WINNERS_TP20_SL10',
        historical_backtest=False, assumed_not_estimated=True, initial_capital_usd=4000,
        tp=.20, sl=.10, equity_allocation_per_trade=.25, reinvestment=True,
        entry_cost_bps=8, exit_cost_bps=8, costs='hypothetical all-in proportional costs per notional per leg',
        cost_components_bps_per_leg=dict(commission=1, half_spread=5, slippage=2),
        simultaneous_positions=1, leverage=1, financing_cost=0, cash_interest=0,
        holding_duration='unspecified; no annualization and no calendar years assigned',
        expiry='not simulated; gain sensitivity stands for smaller average winners',
        assumptions=['constant payoffs within each sign, no gaps, no intraday paths',
            'no margin, no sector/volume/gap guards, no availability constraint',
            'drawdown on closed-trade equity only, NOT intraday or portfolio MTM drawdown',
            'no native engine parity or real model success claimed',
            '70% winning trades is not 70% correct terminal or excursion directions'],
        simulations_per_case=simulations, seed=seed, new_training=0, sql_writes=0,
        api_calls=0, broker_orders=0, production_changes=False,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    gain, loss = net_return(.2), net_return(-.1)
    expectancy = .7 * gain + .3 * loss
    exact = [case(n, rng, simulations, exact=True) for n in (20, 50, 100)]
    uncertain = [case(n, rng, simulations, exact=False) for n in (20, 50, 100)]
    sensitivity = [case(100, rng, simulations, exact=True, gain=g) for g in (.03, .05, .10, .15)]
    ordered = np.array([[False] * 30 + [True] * 70, [True] * 70 + [False] * 30])
    curves, dd = paths(ordered)
    stress = dict(trades=100, winners=70, losers=30,
        loss_cluster_first_final_usd=float(curves[0, -1]),
        loss_cluster_last_final_usd=float(curves[1, -1]),
        closed_equity_drawdown_pct=[float(x * 100) for x in dd],
        caveat='same final equity because proportional returns commute; different path and capital trough')
    break_even_gain = ((1.0008 / .9992) - 1 + .3 * .10) / .7
    report = dict(status='COMPLETED_HYPOTHETICAL_NOT_A_MODEL_RESULT',
        gross_expectancy_per_unit_notional=.7 * .2 - .3 * .1,
        net_expectancy_per_unit_all_in_cash=expectancy,
        net_expected_pnl_per_1000_all_in_usd=1000 * expectancy,
        net_profit_factor=(.7 * gain) / (-.3 * loss),
        break_even_win_rate=-loss / (gain - loss),
        average_gross_gain_needed_if_70_percent_win_and_10_percent_loss=break_even_gain,
        fixed_exact_70_percent=exact, iid_70_percent_probability=uncertain,
        smaller_average_winner_sensitivity=sensitivity, loss_clustering=stress,
        annual_return=None, historical_year_results=None,
        verdict='CONDITIONAL_PROJECTION_ONLY_NO_EVIDENCE_THAT_70_PERCENT_IS_ACHIEVABLE')
    for name, data in [('protocol.json', protocol), ('report.json', report)]:
        (output / name).write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--simulations', type=int, default=10000)
    args = parser.parse_args()
    report = run(args.output, args.simulations)
    print(json.dumps(report, allow_nan=False))
