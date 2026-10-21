"""Read-only diagnostic of SPY price-regime transitions on sealed portfolios.

No new backtest, trading filter, forecast, provider/LLM/SQL call or model fit.
Labels are causal by source session; event-aligned PRE windows are retrospective.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_protection_grid import READ, PRICE

REFERENCE = Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1')
OUTPUT = Path('artifacts/research/us_oracle_regime_transitions/20261021-v1')
PROFILES = ['SL7-TR15-H20-TPOFF', 'SL5-TR15-H20-TPOFF', 'SL7-TR10-H20-TPOFF',
            'SL7-TR20-H20-TPOFF', 'SL7-TR15-H15-TPOFF', 'SL7-TR15-H20-TP10']
ANCHOR = PROFILES[0]


def annotate_history(regimes):
    """Last observed transition only; never use the next transition as a feature."""
    if regimes.date.duplicated().any() or not regimes.date.is_monotonic_increasing:
        raise ValueError('Unique sorted decision sessions required')
    rows = []; previous = None; last_change = None; last_change_day = None
    change_indices = []
    for i, r in enumerate(regimes.itertuples()):
        if pd.isna(r.regime) or pd.Timestamp(r.source_date) >= pd.Timestamp(r.date):
            raise ValueError('Missing or noncausal regime')
        change = previous is not None and r.regime != previous
        if change:
            last_change = i; last_change_day = r.date; change_indices.append(i)
        age = i-last_change if last_change is not None else None
        phase = ('CHANGE_DAY' if age == 0 else 'POST_1_4' if age is not None and age < 5
                 else 'STABLE' if i >= 5 else 'LEFT_CENSORED')
        rows.append(dict(date=r.date, source_date=r.source_date, regime=r.regime,
            previous_regime=previous, changed=change, phase=phase,
            primary_phase='RECENT_0_4' if phase in ['CHANGE_DAY', 'POST_1_4'] else phase,
            sessions_since_change=age, last_change_date=last_change_day,
            changes_in_last20=sum(j >= i-19 for j in change_indices)))
        previous = r.regime
    return pd.DataFrame(rows)


def causal_spy_history(daily):
    from modelFactory.oracle.build_labels import nyse_sessions
    g = daily[daily.symbol.eq('SPY')].copy().set_index('date').sort_index()
    if g.index.has_duplicates:
        raise ValueError('Ambiguous SPY daily archive')
    sessions = nyse_sessions(g.index.min(), g.index.max())
    g = g.reindex(sessions)
    valid = (np.isfinite(g[['open', 'high', 'low', 'close', 'volume']]).all(axis=1)
        & g[['open', 'high', 'low', 'close', 'volume']].gt(0).all(axis=1)
        & g.high.ge(g[['open', 'close']].max(axis=1)) & g.low.le(g[['open', 'close']].min(axis=1))
        & g.is_filled.eq(0) & g.data_adjustment.eq('split'))
    close = g.close.where(valid)
    sma50, sma200 = close.rolling(50, min_periods=50).mean(), close.rolling(200, min_periods=200).mean()
    rows = []
    for i in range(1, len(sessions)):
        source = sessions[i-1]
        if pd.isna(sma200.loc[source]):
            continue
        p, a, b = float(close.loc[source]), float(sma50.loc[source]), float(sma200.loc[source])
        regime = ('BULL' if p > a else 'CORRECTION') if p > b else ('REBOUND' if p > a else 'SLIDE')
        rows.append(dict(date=sessions[i], source_date=source, regime=regime, source_close=p, sma50=a, sma200=b))
    base = pd.DataFrame(rows)
    result = annotate_history(base)
    return result.merge(base[['date', 'source_close', 'sma50', 'sma200']], on='date', validate='one_to_one')


def path_sessions(path):
    g = path.sort_values('bar_timestamp').copy()
    g['date'] = g.bar_timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    return {day: dict(open=float(v.open.iloc[0]), close=float(v.close.iloc[-1])) for day, v in g.groupby('date')}


def lot_daily_attribution(record, case_days, session_prices, side, fee=.0008):
    """Actual booking decomposition. Borrow is booked on exit/annual MTM day.

    Economic daily loan accrual would have a different timing and is NOT
    substituted for the historical engine's posted fees/cash convention.
    """
    days = pd.DatetimeIndex(case_days)
    entry = pd.Timestamp(record['entry_timestamp']).tz_convert('America/New_York').tz_localize(None).normalize()
    closed = 'exit_timestamp' in record
    end = (pd.Timestamp(record['exit_timestamp']).tz_convert('America/New_York').tz_localize(None).normalize()
           if closed else days[-1])
    sign = 1 if side == 'buy' else -1
    qty = float(record['qty']); price = float(record['entry_price'])
    rows = []
    for day in days[(days >= entry) & (days <= end)]:
        i = days.get_loc(day)
        new = day == entry
        if day not in session_prices or not new and (i == 0 or days[i-1] not in session_prices):
            raise ValueError('Missing actual held-session prices')
        before = price if new else session_prices[days[i-1]]['close']
        after = float(record['exit_price']) if closed and day == end else session_prices[day]['close']
        price_pnl = sign*qty*(after-before)
        entry_fee = fee*qty*price if new else 0.
        exit_fee = fee*qty*float(record['exit_price']) if closed and day == end else 0.
        borrow = (float(record.get('borrow_cost', 0.)) if closed else float(record.get('borrow_accrued_usd', 0.))) if day == end else 0.
        overnight = 0. if new else sign*qty*(session_prices[day]['open']-before)
        rows.append(dict(date=day, symbol=record['symbol'], pair_id=int(record['pair_id']),
            cohort='NEW_ENTRY' if new else 'HELD_OVERNIGHT', price_pnl_usd=price_pnl,
            entry_fees_usd=entry_fee, exit_fees_usd=exit_fee, borrow_posted_usd=borrow,
            overnight_price_pnl_usd=overnight, net_pnl_usd=price_pnl-entry_fee-exit_fee-borrow))
    return rows


def phase_summary(daily):
    rows = []
    for (year, side, profile), part in daily.groupby(['year', 'side', 'profile']):
        all_losses = float((-part.net_pnl_usd.clip(upper=0)).sum())
        for phase, g in part.groupby('primary_phase'):
            losses = float((-g.net_pnl_usd.clip(upper=0)).sum())
            scale = float(g.exposure_scale_usd.sum())
            rows.append(dict(year=int(year), side=side, profile=profile, primary_phase=phase,
                sessions=len(g), session_share_pct=100*len(g)/len(part),
                negative_sessions=int(g.net_pnl_usd.lt(-1e-8).sum()),
                net_pnl_usd=float(g.net_pnl_usd.sum()), mean_daily_pnl_usd=float(g.net_pnl_usd.mean()),
                mean_daily_return_pct=float(g.daily_return_pct.mean()),
                loss_mass_usd=losses, share_of_annual_loss_mass_pct=100*losses/all_losses if all_losses else None,
                mean_exposure_scale_usd=float(g.exposure_scale_usd.mean()),
                pnl_per1000_capital_sessions_usd=1000*float(g.net_pnl_usd.sum())/scale if scale else None,
                held_net_pnl_usd=float(g.held_net_pnl_usd.sum()), new_entry_net_pnl_usd=float(g.new_entry_net_pnl_usd.sum()),
                overnight_price_pnl_usd=float(g.overnight_price_pnl_usd.sum()),
                risk_trips=int(g.just_tripped.sum()), degraded_sessions=int(g.allocation_scale.lt(1).sum())))
    return pd.DataFrame(rows)


def transition_windows(history, days):
    """Future-aligned event metadata ONLY. Never joins into causal entry labels."""
    history = history.reset_index(drop=True)
    positions = {d: i for i, d in enumerate(history.date)}
    valid = set(days)
    rows = []
    for r in history[history.changed & history.date.isin(valid)].itertuples():
        i = positions[r.date]
        next_events = history[(history.index > i) & history.changed]
        next_i = int(next_events.index[0]) if len(next_events) else None
        future5 = history.iloc[i+1:i+6]
        rows.append(dict(transition_date=r.date, from_regime=r.previous_regime, to_regime=r.regime,
            next_change_sessions=next_i-i if next_i is not None else None,
            next_change_within5=next_i is not None and next_i-i <= 5,
            returned_to_prior_state_within5=bool(future5.regime.eq(r.previous_regime).any()),
            full_followup5_available=len(future5) == 5))
    return pd.DataFrame(rows)


def analyze_case(root, row, labels, paths, source):
    folder = REFERENCE/'cases'/row['case']
    for name in ['trades.parquet', 'marks.parquet', 'open-positions.json', 'production-risk-events.json']:
        if digest(folder/name) != row['files'][name]:
            raise ValueError('Sealed case input changed: '+row['case']+'/'+name)
        source[str(folder/name)] = row['files'][name]
    trades = pd.read_parquet(folder/'trades.parquet'); opened = READ(folder/'open-positions.json')
    marks = pd.read_parquet(folder/'marks.parquet')
    marks['date'] = marks.time.dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
    day_end = marks.groupby('date').tail(1).set_index('date')
    days = pd.DatetimeIndex(day_end.index)
    risk_events = pd.DataFrame(READ(folder/'production-risk-events.json'))
    risk_events['date'] = pd.to_datetime(risk_events.date)
    if len(risk_events) != len(days) or risk_events.date.duplicated().any():
        raise ValueError('Incomplete daily risk events')
    daily = pd.DataFrame(index=days)
    daily['equity_close_usd'] = day_end.equity
    previous = day_end.equity.shift(1, fill_value=4000.)
    daily['net_pnl_usd'] = day_end.equity-previous
    daily['daily_return_pct'] = 100*(day_end.equity/previous-1)
    daily['prior_close_gross_usd'] = day_end.gross.shift(1, fill_value=0.)
    daily['mean_intraday_gross_usd'] = marks.groupby('date').gross.mean()
    daily['exposure_scale_usd'] = daily[['prior_close_gross_usd', 'mean_intraday_gross_usd']].max(axis=1)
    charges = pd.Series({pd.Timestamp(e['date']): float(e['interest']) for e in READ(folder/'maintenance.json')})
    daily['financing_usd'] = charges.reindex(days)
    if daily.financing_usd.isna().any():
        raise ValueError('Financing session missing')
    records = trades.to_dict('records')+opened
    lot_rows = []
    entry_rows = []
    for r in records:
        lot_rows.extend(lot_daily_attribution(r, days, paths[int(r['pair_id'])], row['side']))
        d = pd.Timestamp(r['entry_timestamp']).tz_convert('America/New_York').tz_localize(None).normalize()
        entry_rows.append(dict(case=row['case'], year=row['year'], side=row['side'], profile=row['case'].split('LONG-', 1)[-1]
            if row['side'] == 'buy' else row['case'].split('SHORT-', 1)[-1], date=d,
            symbol=r['symbol'], pair_id=int(r['pair_id']), closed='exit_timestamp' in r,
            net_pnl_usd=float(r['pnl']) if 'exit_timestamp' in r else float(r['unrealized_pnl_usd']),
            holding_sessions=float(r['holding_sessions']) if 'exit_timestamp' in r else None))
    lot = pd.DataFrame(lot_rows)
    if lot.empty:
        raise ValueError('No lot attribution to check')
    components = lot.groupby(['date', 'cohort']).net_pnl_usd.sum().unstack(fill_value=0.)
    for cohort, column in [('NEW_ENTRY', 'new_entry_net_pnl_usd'), ('HELD_OVERNIGHT', 'held_net_pnl_usd')]:
        daily[column] = components.get(cohort, pd.Series(dtype=float)).reindex(days, fill_value=0.)
    daily['overnight_price_pnl_usd'] = lot.groupby('date').overnight_price_pnl_usd.sum().reindex(days, fill_value=0.)
    daily['held_intraday_and_costs_usd'] = daily.held_net_pnl_usd-daily.overnight_price_pnl_usd
    daily['reconstructed_net_pnl_usd'] = daily.new_entry_net_pnl_usd+daily.held_net_pnl_usd-daily.financing_usd
    error = float((daily.net_pnl_usd-daily.reconstructed_net_pnl_usd).abs().max())
    if error > 1e-6 or abs(float(daily.net_pnl_usd.sum())-row['net_pnl_usd']) > 1e-6:
        raise ValueError('Daily lot/fees/overnight decomposition failed')
    daily = daily.reset_index(names='date').merge(labels, on='date', validate='one_to_one')
    if len(daily) != len(days) or daily.primary_phase.eq('LEFT_CENSORED').any():
        raise ValueError('Missing qualified preperiod regime context')
    daily = daily.merge(risk_events[['date', 'just_tripped', 'allocation_scale', 'drawdown_pct',
        'equity_before', 'reference_peak', 'forced_symbols', 'regime_source_date']], on='date', validate='one_to_one')
    if not pd.to_datetime(daily.regime_source_date).eq(daily.source_date).all():
        raise ValueError('Risk used a different source session')
    profile = row['case'].split('LONG-', 1)[-1] if row['side'] == 'buy' else row['case'].split('SHORT-', 1)[-1]
    daily['year'], daily['side'], daily['profile'], daily['case'] = row['year'], row['side'], profile, row['case']
    daily['forced_exits'] = daily.forced_symbols.map(len)
    entries = pd.DataFrame(entry_rows).merge(labels[['date', 'regime', 'primary_phase']], on='date', validate='many_to_one')
    trip_rows = []
    for i, r in daily[daily.just_tripped].iterrows():
        after = daily.iloc[i+1:]
        recovered = after[after.allocation_scale.ge(1.-1e-12)]
        trip_rows.append(dict(case=row['case'], year=row['year'], side=row['side'], profile=profile,
            trip_date=r.date, regime=r.regime, primary_phase=r.primary_phase,
            last_change_date=r.last_change_date, sessions_since_change=r.sessions_since_change,
            drawdown_at_guard_pct=r.drawdown_pct, forced_exits=r.forced_exits,
            first_full_allocation_date=recovered.date.iloc[0] if len(recovered) else None,
            sessions_to_first_full_allocation=int(recovered.index[0]-i) if len(recovered) else None,
            recovery_right_censored=not len(recovered),
            note='Temporal association only; B4 responds to account drawdown, not an obligation to react to regime changes.'))
    windows = []
    transition_days = daily[daily.changed].date
    for transition in transition_days:
        i = daily.index[daily.date.eq(transition)][0]
        for offset in range(-5, 11):
            j = i+offset
            if 0 <= j < len(daily):
                r = daily.iloc[j]
                windows.append(dict(case=row['case'], year=row['year'], side=row['side'], profile=profile,
                    transition_date=transition, offset=offset, date=r.date, regime=r.regime,
                    net_pnl_usd=r.net_pnl_usd, held_net_pnl_usd=r.held_net_pnl_usd,
                    new_entry_net_pnl_usd=r.new_entry_net_pnl_usd, allocation_scale=r.allocation_scale,
                    retrospectively_aligned=True))
    return daily, entries, trip_rows, windows, error


def run(root):
    root = Path(root)
    if root.exists():
        raise ValueError('Fresh immutable output required')
    review = READ(REFERENCE/'final-review.json'); verify_hashes(REFERENCE, review['files'])
    report = READ(REFERENCE/'report.json')
    if report['completed'] != 576 or report['failed']:
        raise ValueError('Completed sealed grid required')
    prepared = READ(REFERENCE/'prepared.json'); verify_hashes(REFERENCE, prepared['files'])
    source = {str(p): digest(p) for p in [REFERENCE/'report.json', REFERENCE/'final-review.json',
        REFERENCE/'prepared.json', PRICE, Path(__file__), Path('tests/test_us_oracle_regime_transitions.py')]}
    source.update({str(REFERENCE/n): h for n, h in prepared['files'].items()})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=source, reference=str(REFERENCE), primary_profile=ANCHOR, sensitivity_profiles=PROFILES[1:],
        hypothesis='Descriptive transition vs stable loss attribution; no learned filter or new portfolio simulation.',
        definition='SPY prior-completed-session close relative SMA50/SMA200: BULL above both, '
                   'CORRECTION above200/not50, REBOUND above50/not200, SLIDE belowboth. '
                   'Previous200complete closes, no ffill. Reconstruct warmup before2025 and match437sealed regimes.',
        primary_partition='Latest observed change only: day0 and days1..4=RECENT_0_4; no change in last5decision sessions=STABLE. '
                          'No next change or future outcomes used to label a decision. No threshold grid.',
        decomposition='Daily after-cost equity changes partitioned into today entry lots and lots held from prior close; '
                      'held overnight OPEN-minus-priorCLOSE price PnL separately. Borrow posted on exit/annual MTM as historical engine, '
                      'not synthetic daily accrual. Financing separate. Daily and annual conservation required.',
        exposure='Descriptive normalizer=max(previous-close gross, mean regular5m gross); USD per1000capital-sessions, '
                 'NOT an exposure-matched replay, cumulative return, causal effect or signal.',
        cohorts='Entry-phase closed-trade winrate/PnL separate from open-marked positions; duration/selection/right-censoring retained.',
        event_study='PRE-5..-1 and POST0..10 align to an observed change retrospectively. Overlapping windows can repeat dates, '
                    'never summed as independent portfolio PnL. Later reversals within5sessions are outcomes, not available features.',
        b4='Trip timing relative latest regime change and first later full allocation; no expected immediate regime veto. '
           'Annual accounts reset; recoveries censored at account-year end, no crossyear fake continuation.',
        limitations=['Same213campaigns/72symbols/conditionalfuturecoverage/survivor universe, researchCatBoostPATH_H20, not fullTOP10.',
            '2025/2026toSept30alreadyexamined,24overlapping cases not independent replicates, no newholdout/p-values.',
            'SMA-SPY price proxy only, NOT full production macroVIX/VXN/MOVE regime and no macro causal attribution.',
            'Restated historical daily, hypothetical fills/borrow/CA, no certified applicationPIT or full live parity.',
            'OldOracleJ+H includes entry waiting, not newruntime20holdingsessions/open21. No protection/model change.'],
        new_backtest=False, training=False, provider_calls=False, sql_writes=False, llm_calls=False, broker_calls=False))
    atomic_json(root/'progress.json', dict(status='RUNNING', completed=0, total=24))
    labels = causal_spy_history(pd.read_parquet(PRICE))
    sealed = pd.read_parquet(REFERENCE/'risk-regimes.parquet')
    matched = sealed.merge(labels, on='date', suffixes=('_sealed', ''), validate='one_to_one')
    if len(matched) != 437 or not matched.regime.eq(matched.regime_sealed).all() or not matched.source_date.eq(matched.source_date_sealed).all():
        raise ValueError('Causal reconstruction differs from frozen437session contexts')
    labels.to_parquet(root/'causal-regime-history.parquet', index=False)
    paths = {int(k): path_sessions(g) for k, g in pd.read_parquet(REFERENCE/'bars.parquet').groupby('pair_id')}
    planned = [r for r in report['cases'] if any(r['case'].endswith(p) for p in PROFILES)]
    if len(planned) != 24:
        raise ValueError('Exactly six profiles x two sides x two years required')
    daily_frames = []; entry_frames = []; trips = []; windows = []; errors = []
    started = time.monotonic()
    for i, r in enumerate(planned):
        d, e, t, w, error = analyze_case(root, r, labels, paths, source)
        daily_frames.append(d); entry_frames.append(e); trips.extend(t); windows.extend(w); errors.append(error)
        atomic_json(root/'progress.json', dict(status='RUNNING', completed=i+1, total=24,
            last=r['case'], elapsed_seconds=time.monotonic()-started))
    daily = pd.concat(daily_frames, ignore_index=True)
    entries = pd.concat(entry_frames, ignore_index=True)
    daily.to_parquet(root/'daily-attribution.parquet', index=False)
    entries.to_parquet(root/'entry-cohorts.parquet', index=False)
    summary = phase_summary(daily); summary.to_csv(root/'phase-summary.csv', index=False)
    cohort_rows = []
    for keys, g in entries.groupby(['year', 'side', 'profile', 'primary_phase']):
        closed = g[g.closed]; opened = g[~g.closed]
        cohort_rows.append(dict(zip(['year', 'side', 'profile', 'primary_phase'], keys),
            entries=len(g), closed=len(closed), open_count=len(opened),
            closed_win_rate_pct=100*float(closed.net_pnl_usd.gt(0).mean()) if len(closed) else None,
            closed_net_pnl_usd=float(closed.net_pnl_usd.sum()), open_marked_pnl_usd=float(opened.net_pnl_usd.sum()),
            mean_closed_holding_sessions=float(closed.holding_sessions.mean()) if len(closed) else None))
    pd.DataFrame(cohort_rows).to_csv(root/'entry-cohort-summary.csv', index=False)
    pd.DataFrame(trips).to_csv(root/'b4-trip-timing.csv', index=False)
    pd.DataFrame(windows).to_csv(root/'event-windows-retrospective.csv', index=False)
    transition_windows(labels, sealed.date).to_csv(root/'transition-outcomes-retrospective.csv', index=False)
    # Source file manifest is separate from the protocol: outcomes never alter
    # predefined windows/definitions, all raw inputs are byte-verified at end.
    verify_hashes(Path('.'), source)
    atomic_json(root/'source-manifest.json', dict(files=source))
    report_out = dict(status='COMPLETED_DIAGNOSTIC', cases=24, unique_sessions=437,
        primary_profile=ANCHOR, reconstruction_matches_sealed_sessions=437,
        max_daily_decomposition_error_usd=max(errors), new_backtest=False, full_live_parity=False,
        elapsed_seconds=time.monotonic()-started,
        primary_summary=summary[summary.profile.eq(ANCHOR)].to_dict('records'))
    atomic_json(root/'report.json', report_out)
    atomic_json(root/'progress.json', {k: v for k, v in report_out.items() if k != 'primary_summary'})
    atomic_json(root/'final-review.json', dict(status='PASS_DAILY_CONSERVATION_AND_CAUSAL_REGIME_LABELS',
        independent_human_review=False, files={p.name: digest(p) for p in root.iterdir()
            if p.is_file() and p.name not in ['final-review.json', 'progress.json']}))
    return report_out


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=OUTPUT)
    run(p.parse_args().output)
