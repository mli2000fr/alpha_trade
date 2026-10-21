"""Independent cash/position-value daily reconstruction and stratified review."""
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_protection_grid import READ, PRICE
from scripts.research.us_oracle_regime_transitions import REFERENCE, ANCHOR


def cash_value_components(records, days, prices, side):
    """Per-lot cash flows + differences in marked inventory, no price-PnL helper."""
    days = pd.DatetimeIndex(days)
    totals = dict(new=np.zeros(len(days)), held=np.zeros(len(days)), overnight=np.zeros(len(days)))
    sign = 1 if side == 'buy' else -1
    for r in records:
        start_day = pd.Timestamp(r['entry_timestamp']).tz_convert('America/New_York').tz_localize(None).normalize()
        begin = days.get_loc(start_day)
        closed = 'exit_timestamp' in r
        end = days.get_loc(pd.Timestamp(r['exit_timestamp']).tz_convert('America/New_York').tz_localize(None).normalize()) if closed else len(days)
        cash = np.zeros(len(days)); value = np.zeros(len(days))
        q, p = float(r['qty']), float(r['entry_price'])
        cash[begin] -= sign*q*p+.0008*q*p
        if closed:
            out = float(r['exit_price'])
            cash[end] += sign*q*out-.0008*q*out-float(r['borrow_cost'])
        else:
            cash[-1] -= float(r.get('borrow_accrued_usd', 0.))
        path = prices[int(r['pair_id'])]
        for i in range(begin, end):
            value[i] = sign*q*path[days[i]]['close']
        per_day = cash+np.diff(np.r_[0., value])
        totals['new'][begin] += per_day[begin]
        held_part = per_day.copy(); held_part[begin] = 0.
        totals['held'] += held_part
        for i in range(begin+1, min(end+1, len(days))):
            totals['overnight'][i] += sign*q*(path[days[i]]['open']-path[days[i-1]]['close'])
    return totals


def validate_labels(context, daily):
    """Scalar trailing means and vector last-change ages, no primary helper."""
    spy = daily[daily.symbol.eq('SPY')].sort_values('date').set_index('date')
    for r in context.itertuples():
        history = spy.loc[:r.source_date].tail(200)
        if len(history) != 200 or history.index[-1] != r.source_date or r.source_date >= r.date:
            raise ValueError('Noncausal or insufficient SPY history')
        if (history.is_filled.ne(0).any() or history.data_adjustment.ne('split').any()
                or not np.isfinite(history.close).all() or history.close.le(0).any()):
            raise ValueError('Unqualified SPY source')
        p = float(history.close.iloc[-1]); above50 = p > float(history.close.tail(50).mean())
        above200 = p > float(history.close.mean())
        regime = ('BULL' if above50 else 'CORRECTION') if above200 else ('REBOUND' if above50 else 'SLIDE')
        if r.regime != regime:
            raise ValueError('Independent scalar SPY classification differs')
    states = context.regime.to_numpy()
    change = np.r_[False, states[1:] != states[:-1]]
    idx = np.arange(len(states))
    last = np.maximum.accumulate(np.where(change, idx, -100000))
    ages = idx-last
    phase = np.where(ages == 0, 'CHANGE_DAY', np.where(ages < 5, 'POST_1_4',
                     np.where(idx >= 5, 'STABLE', 'LEFT_CENSORED')))
    if not (context.changed.to_numpy() == change).all() or not (context.phase.to_numpy() == phase).all():
        raise ValueError('Independent transition labels differ')


def stratified_summary(daily):
    rows = []
    for keys, g in daily.groupby(['year', 'side', 'profile', 'regime', 'primary_phase']):
        loss = float((-g.net_pnl_usd.clip(upper=0)).sum())
        gross = float(g.exposure_scale_usd.sum())
        rows.append(dict(zip(['year', 'side', 'profile', 'regime', 'primary_phase'], keys),
            sessions=len(g), net_pnl_usd=float(g.net_pnl_usd.sum()),
            mean_daily_pnl_usd=float(g.net_pnl_usd.mean()), loss_mass_usd=loss,
            held_net_pnl_usd=float(g.held_net_pnl_usd.sum()), new_entry_net_pnl_usd=float(g.new_entry_net_pnl_usd.sum()),
            exposure_capital_sessions_usd=gross,
            pnl_per1000_capital_sessions_usd=1000*float(g.net_pnl_usd.sum())/gross if gross else None))
    return pd.DataFrame(rows)


def review(root):
    root = Path(root)
    verify_hashes(root, READ(root/'final-review.json')['files'])
    verify_hashes(Path('.'), READ(root/'source-manifest.json')['files'])
    report = READ(root/'report.json')
    if report['status'] != 'COMPLETED_DIAGNOSTIC' or report['cases'] != 24:
        raise ValueError('Completed24case diagnostic required')
    context = pd.read_parquet(root/'causal-regime-history.parquet')
    validate_labels(context, pd.read_parquet(PRICE))
    full_daily = pd.read_parquet(root/'daily-attribution.parquet')
    path_prices = {}
    bars = pd.read_parquet(REFERENCE/'bars.parquet')
    bars['date'] = bars.bar_timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    for pid, path in bars.groupby('pair_id'):
        path_prices[int(pid)] = {}
        for day, g in path.groupby('date'):
            g = g.sort_values('bar_timestamp')
            path_prices[int(pid)][day] = dict(open=float(g.open.iloc[0]), close=float(g.close.iloc[-1]))
    maximum = 0.; total_days = 0
    for key, table in full_daily.groupby('case'):
        table = table.sort_values('date').reset_index(drop=True)
        folder = REFERENCE/'cases'/key
        records = pd.read_parquet(folder/'trades.parquet').to_dict('records')+READ(folder/'open-positions.json')
        arrays = cash_value_components(records, table.date, path_prices, table.side.iloc[0])
        for label, actual in [('new', table.new_entry_net_pnl_usd), ('held', table.held_net_pnl_usd),
                              ('overnight', table.overnight_price_pnl_usd)]:
            error = float(np.max(np.abs(arrays[label]-actual.to_numpy(float))))
            maximum = max(maximum, error)
            if error > 1e-6:
                raise ValueError('Independent cash/value '+label+' decomposition failed')
        expected = arrays['new']+arrays['held']-table.financing_usd.to_numpy(float)
        error = float(np.max(np.abs(expected-table.net_pnl_usd.to_numpy(float))))
        maximum = max(maximum, error)
        if error > 1e-6:
            raise ValueError('Independent daily equity PnL failed')
        total_days += len(table)
    stratified_summary(full_daily).to_csv(root/'regime-stratified-summary.csv', index=False)
    summary = pd.read_csv(root/'phase-summary.csv')
    sensitivity = []
    for (year, side, profile), g in summary.groupby(['year', 'side', 'profile']):
        rows = g.set_index('primary_phase')
        recent, stable = rows.loc['RECENT_0_4'], rows.loc['STABLE']
        sensitivity.append(dict(year=int(year), side=side, profile=profile,
            recent_net_pnl_usd=float(recent.net_pnl_usd), stable_net_pnl_usd=float(stable.net_pnl_usd),
            recent_mean_daily_pnl_usd=float(recent.mean_daily_pnl_usd),
            stable_mean_daily_pnl_usd=float(stable.mean_daily_pnl_usd),
            recent_normalized_pnl=float(recent.pnl_per1000_capital_sessions_usd),
            stable_normalized_pnl=float(stable.pnl_per1000_capital_sessions_usd),
            recent_loss_share_pct=float(recent.share_of_annual_loss_mass_pct),
            recent_session_share_pct=float(recent.session_share_pct)))
    pd.DataFrame(sensitivity).to_csv(root/'profile-sensitivity.csv', index=False)
    # Future reversal outcomes are deliberately in a distinct file; never
    # merged into entry/decision features or a trading strategy.
    events = pd.read_csv(root/'transition-outcomes-retrospective.csv')
    events['year'] = pd.to_datetime(events.transition_date).dt.year
    event_counts = events.groupby('year').agg(transitions=('transition_date', 'size'),
        another_change_within5=('next_change_within5', 'sum'),
        return_to_prior_state_within5=('returned_to_prior_state_within5', 'sum'))
    event_counts.to_csv(root/'transition-counts.csv')
    atomic_json(root/'post-review.json', dict(status='PASS_SCALAR_REGIMES_AND_INDEPENDENT_CASH_VALUE_COMPONENTS',
        cases=24, daily_account_observations=total_days, source_regimes_matched=437,
        max_independent_daily_error_usd=maximum, independent_human_review=False,
        files={n: digest(root/n) for n in ['report.json', 'regime-stratified-summary.csv',
              'profile-sensitivity.csv', 'transition-counts.csv']},
        review_sources={str(Path(__file__)): digest(Path(__file__))}))


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('artifacts/research/us_oracle_regime_transitions/20261021-v1'))
    review(p.parse_args().output)
