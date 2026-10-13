"""Sequential offline challengers authorized on 2026-10-13.

Separate research models, immutable Oracle and baseline, no SQL/broker access.
Never fit or select hyperparameters on the already observed 2024-2026 tests.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout, redirect_stderr
from functools import partial
import logging
from pathlib import Path
import shutil

import lightgbm as lgb
import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_barrier import SCORES
from common.trading_costs import DEFAULT_COST_MODEL
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import freeze_candidates
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_tp20_sl10_campaign import (
    YEARS, COUNTS, MODEL, code_hashes, model_contract, read, run_case, annual_metrics,
)
from scripts.research.us_oracle_tp20_sl10_lifecycle import load_events
from scripts.research.us_oracle_tp20_sl10_models import (
    FEATURES as CANDIDATE_FEATURES, SCORE_FEATURES, PROFILES, input_matrix, unit_path, train_head,
    state_values, split_fit_validation, SizedSession, PersonalizedLedger,
)

LOG = logging.getLogger(__name__)
BASELINE = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6')
STAGES = ('ENTRY_FILTER', 'DAILY_EXIT', 'PERSONAL_TP_SL')
# The baseline's archived serving contract omits these two Oracle extras.
# Follow the preregistered availability rule, without fabricating test features.
FEATURES = [f for f in CANDIDATE_FEATURES if f not in ('drawdown_20', 'high_low_position_20')]


def label_availability(declared, path_days, exits):
    """Use all target observations, including the expiry open, before purging."""
    return max(pd.Timestamp(declared), *(pd.Timestamp(path_days[e[0]]) for e in exits))


def source_manifest():
    return {**code_hashes(), str(Path(__file__)): digest(__file__)}


def initialize(root, baseline, model):
    root.mkdir(parents=True, exist_ok=True)
    _, profile, _ = model_contract(model)
    if not set(FEATURES) <= set(profile['feature_columns']):
        raise ValueError('Frozen challenger features missing from Oracle profile')
    ready = read(baseline/'ready.json')
    verify_hashes(baseline, ready['files'])
    audit = read(baseline/'completion-audit.json')
    if audit['status'] != 'ALL_NINE_BASELINE_CASES_VERIFIED':
        raise ValueError('Nine audited baseline cases required')
    verify_hashes(Path('.'), audit['source_hashes'])
    verify_hashes(Path('.'), read(baseline/'baseline-source-manifest.json')['files'])
    verify_hashes(Path('.'), read(baseline/'protocol.json')['model_files'])
    protocol = dict(
        baseline=str(baseline), model=str(model), original_batch='model-factory-20261012183840-6d6569',
        source_hashes=source_manifest(), baseline_audit_sha256=digest(baseline/'completion-audit.json'),
        baseline_ready_sha256=digest(baseline/'ready.json'), stages=STAGES,
        years=YEARS, counts=COUNTS, primary_count=10, fit_end='2021-12-31', validation_year=2022,
        features=FEATURES, score_features=SCORE_FEATURES, threshold=.5,
        entry_filter='LONG unit net win probability >= .5; no replacement beyond TOPN',
        daily_exit='negative predicted KEEP advantage; close decision, next-open execution; hard SL10/TP20',
        profiles=PROFILES, profile_objective='predicted unit net return / SL',
        profile_sizing='native approved quantity capped by original risk budget / (SL * J close * 1.03)',
        same_sizing_control='fixed TP20/SL10, separate replay',
        stages_independent=True, progressive_exposure_guard=False,
        sql_writes=False, broker_calls=False, live_changes=False, original_oracle_retrained=False,
        holdout_is_virgin=False, no_automatic_promotion=True,
        tail_source='causal rolling features from already qualified local OHLCV; no SQL',
        target_costs='canonical flat unit approximation; actual portfolio costs measured by replay',
    )
    marker = root/'challenger-protocol.json'
    if marker.exists():
        saved = read(marker)
        verify_hashes(Path('.'), saved['source_hashes'])
        if saved['baseline_ready_sha256'] != protocol['baseline_ready_sha256']:
            raise ValueError('Baseline changed; new campaign required')
    else:
        atomic_json(marker, protocol)
    for name in (*ready['files'], 'baseline-report.json'):
        target = root/name
        if not target.exists():
            shutil.copy2(baseline/name, target)
    if not (root/'ready.json').exists():
        atomic_json(root/'ready.json', ready)
    verify_hashes(root, ready['files'])
    return protocol


def oof_candidates(model):
    parts = []
    hashes = {}
    for fold in sorted((model/'folds').iterdir()):
        done = read(fold/'done.json')
        verify_hashes(fold, done['files'])
        for head in done['metrics']['heads'].values():
            if pd.Timestamp(head['val_available_max']) >= pd.Timestamp(fold.name):
                raise ValueError('Oracle fold sees test-period labels')
        hashes[str(fold/'done.json')] = digest(fold/'done.json')
        frame = pd.read_parquet(fold/'oof.parquet')
        frame = frame.sort_values(['date', SCORES['long'], 'symbol'], ascending=[True, False, True])
        frame['selection_rank'] = frame.groupby('date').cumcount()+1
        parts.append(frame.loc[frame.selection_rank.le(50) & frame.date.lt('2023-01-01')])
    result = pd.concat(parts, ignore_index=True)
    if result.duplicated(['date', 'symbol']).any():
        raise ValueError('Overlapping OOF candidates')
    return result, hashes


def build_training_chunk(selected, raw, bars, calendar):
    entries, states, excluded = [], [], {}

    def reject(reason):
        excluded[reason] = excluded.get(reason, 0)+1

    cost = DEFAULT_COST_MODEL.round_trip_cost_pct
    for symbol, group in selected.groupby('symbol'):
        b = bars.loc[bars.symbol.eq(symbol)].set_index('date').reindex(calendar)
        factor = b.adj_close.where(b.adj_close.notna(), b.close)/b.close
        b[['open', 'high', 'low', 'close']] = b[['open', 'high', 'low', 'close']].mul(factor, axis=0)
        f = raw.loc[raw.symbol.eq(symbol)].set_index('date')
        for row in group.itertuples(index=False):
            if not row.path_qualified or pd.isna(row.long_gross_return):
                reject('unqualified_original_label'); continue
            j = calendar.get_indexer([pd.Timestamp(row.date)])[0]
            if j < 0:
                raise ValueError('Training signal outside calendar')
            path = b.iloc[j+1:j+22]
            if len(path) != 21 or path.volume.isna().any() or path.volume.le(0).any():
                reject('missing_or_nonpositive_volume'); continue
            if path.is_filled.fillna(0).ne(0).any() or path.instrument_id.dropna().nunique() > 1:
                reject('filled_or_changed_identity'); continue
            entry, previous = float(path.open.iloc[0]), float(b.close.iloc[j])
            if not np.isfinite(entry) or not np.isfinite(previous) or previous <= 0 or abs(entry/previous-1) > .03:
                reject('entry_gap_or_price'); continue
            exits = [unit_path(path.open.to_numpy(), path.high.to_numpy(), path.low.to_numpy(), entry, tp=tp, sl=sl)
                     for tp, sl in PROFILES]
            if any(x is None for x in exits):
                reject('invalid_ohlc_path'); continue
            base = exits[1]
            available = label_availability(row.oracle_available_date, path.index, exits)
            record = {k: getattr(row, k) for k in FEATURES+list(SCORES.values())}
            record.update(date=row.date, symbol=symbol, selection_rank=int(row.selection_rank),
                score_difference=getattr(row, SCORES['long'])-getattr(row, SCORES['short']),
                label_available=available, unit_net_return=base[1]/entry-1-cost,
                label_win=float(base[1]/entry-1-cost > 0))
            for k, exit_ in enumerate(exits):
                record[f'profile_target_{k}'] = (exit_[1]/entry-1-cost)/PROFILES[k][1]
            entries.append(record)
            # No close-state on the day on which the hard barrier already exited.
            for k in range(min(base[0], 20)):
                day = path.index[k]
                if day not in f.index:
                    reject('missing_close_state_features'); continue
                closed = float(path.close.iloc[k]); history = path.iloc[:k+1]
                if not np.isfinite(closed) or closed <= 0:
                    reject('invalid_close_state'); continue
                state = {x: float(f.at[day, x]) for x in FEATURES}
                state.update({x: getattr(row, x) for x in SCORES.values()})
                state['score_difference'] = record['score_difference']
                state.update(state_values(k, entry, closed, float(history.high.max()), float(history.low.min()), 0.))
                state.pop('relative_since_entry')
                state.update(date=day, symbol=symbol, entry_date=path.index[0], trade_id=f'{symbol}/{row.date}',
                    label_available=available, keep_advantage=(base[1]-float(path.open.iloc[k+1]))/closed,
                    weight=1./max(1, min(base[0], 20)))
                states.append(state)
    return pd.DataFrame(entries), pd.DataFrame(states), excluded


def training_data(root, model):
    root.mkdir(parents=True, exist_ok=True)
    marker = root/'training-source-manifest.json'
    if marker.exists():
        saved = read(marker)
        verify_hashes(Path('.'), saved['files']); verify_hashes(root, saved['dataset_hashes'])
        return pd.read_parquet(root/'entry-training.parquet'), pd.read_parquet(root/'exit-training.parquet')
    candidates, hashes = oof_candidates(model)
    chunks = sorted((model/'chunks').iterdir())
    calendar = nyse_sessions(pd.Timestamp('2016-01-01').date(), pd.Timestamp('2023-12-31').date())
    parts, states, exclusions = [], [], {}
    for i, chunk in enumerate(chunks):
        done = read(chunk/'done.json'); verify_hashes(chunk, done['files'])
        hashes[str(chunk/'done.json')] = digest(chunk/'done.json')
        target = root/f'chunk-{i:03d}'; target.mkdir(exist_ok=True)
        selected = candidates.loc[candidates.symbol.isin(done['symbols'])]
        if (target/'ready.json').exists():
            saved = read(target/'ready.json'); verify_hashes(target, saved['files'])
            if saved['source_sha256'] != digest(chunk/'done.json'):
                raise ValueError('Changed training chunk')
            entry, state = pd.read_parquet(target/'entries.parquet'), pd.read_parquet(target/'states.parquet')
            excluded = saved['excluded']
        else:
            raw = pd.read_parquet(chunk/'features.parquet', columns=['date', 'symbol', *FEATURES])
            selected = selected.merge(raw, on=['date', 'symbol'], how='left', validate='one_to_one')
            entry, state, excluded = build_training_chunk(selected, raw, pd.read_parquet(chunk/'bars.parquet'), calendar)
            entry.to_parquet(target/'entries.parquet', index=False)
            state.to_parquet(target/'states.parquet', index=False)
            atomic_json(target/'ready.json', dict(source_sha256=digest(chunk/'done.json'), excluded=excluded,
                files={n:digest(target/n) for n in ('entries.parquet', 'states.parquet')}))
        if len(entry): parts.append(entry)
        if len(state): states.append(state)
        for key, value in excluded.items(): exclusions[key] = exclusions.get(key, 0)+value
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='OOF_training_dataset',
            completed_chunks=i+1, total_chunks=len(chunks), entry_rows=sum(map(len, parts)), state_rows=sum(map(len, states))))
        LOG.info('OOF chunk %s/%s: %s entries, %s states', i+1, len(chunks), len(entry), len(state))
    entries, daily = pd.concat(parts, ignore_index=True), pd.concat(states, ignore_index=True)
    if entries.duplicated(['date', 'symbol']).any() or daily.duplicated(['trade_id', 'date']).any():
        raise ValueError('Duplicate training keys')
    for frame in (entries, daily): split_fit_validation(frame)
    entries.to_parquet(root/'entry-training.parquet', index=False)
    daily.to_parquet(root/'exit-training.parquet', index=False)
    atomic_json(marker, dict(files=hashes, features=FEATURES, excluded=exclusions,
        candidates=len(candidates), entries=len(entries), daily_states=len(daily),
        dataset_hashes={n:digest(root/n) for n in ('entry-training.parquet', 'exit-training.parquet')},
        target_costs='canonical flat unit approximation; not actual portfolio PnL',
        all_targets_observed_before_fit_cut=True, no_test_labels_used=True))
    atomic_json(root/'progress.json', dict(status='COMPLETED', entries=len(entries), daily_states=len(daily)))
    return entries, daily


def entry_identity(pos, current_symbol):
    return pos.signal_context.get('entry_symbol') or current_symbol


class CausalDailyExit:
    """Immutable entry scores and same-lot observed path survive a ticker change."""
    def __init__(self, model, features):
        if features.duplicated(['date', 'symbol']).any():
            raise ValueError('Duplicate daily decision feature keys')
        self.model, self.columns = model, model.feature_name()
        self.features = features.set_index(['date', 'symbol'])
        self.orders = []
        self.audit = []

    def __call__(self, day, ledger, frames):
        if any(f.index.max() > day for f in frames.values()):
            raise ValueError('Daily policy received future prices')
        rows = []
        for symbol, pos in ledger.state.positions.items():
            original = entry_identity(pos, symbol)
            current_key = (pd.Timestamp(day), symbol)
            signal_day = ledger.days[pos.entry_idx-1]
            entry_key = (signal_day, original)
            if current_key not in self.features.index or entry_key not in self.features.index:
                raise ValueError(f'Missing current features or immutable entry scores {symbol}/{day}')
            row = self.features.loc[current_key].to_dict()
            for c in SCORE_FEATURES: row[c] = self.features.loc[entry_key, c]
            # MergerLedger rebases its own histories; use those, not another
            # instrument's pre-conversion history or unrebased runner frames.
            row.update(state_values(ledger.days.get_loc(day)-pos.entry_idx, pos.entry_price,
                float(ledger.close.at[day, symbol]), float(ledger.high.loc[pos.entry_date:day, symbol].max()),
                float(ledger.low.loc[pos.entry_date:day, symbol].min()), 0.))
            prediction = float(self.model.predict(input_matrix(pd.DataFrame([row]), self.columns), num_threads=1)[0])
            if not np.isfinite(prediction): raise ValueError('Invalid daily exit prediction')
            audit = dict(symbol=symbol, entry_symbol=original, entry_date=pos.entry_date,
                entry_signal_date=signal_day, decision_date=day, predicted_keep_advantage=prediction,
                action='EXIT_NEXT_OPEN' if prediction < 0 else 'KEEP',
                initial_stop_price=pos.replay_initial_stop_price, take_profit_price=pos.replay_take_profit_price)
            self.audit.append(audit)
            if prediction < 0: rows.append(dict(audit))
        self.orders = rows
        return rows

    def remap_pending(self, conversions):
        # Mutate the same research-only order dictionaries queued by the runner.
        for source, target, _ in conversions:
            for order in self.orders:
                if order['symbol'] == source:
                    order.update(symbol=target, converted_from=source)


class DailyExitLedger(GridLedger):
    def __init__(self, *args, daily_policy, **kwargs):
        self.daily_policy = daily_policy
        super().__init__(*args, tp_pct=.2, sl_pct=.1, **kwargs)

    def corporate_action_open(self, session, pending, steps, day):
        result = super().corporate_action_open(session, pending, steps, day)
        self.daily_policy.remap_pending(self.today_conversions)
        return result

    def corporate_action_report(self):
        return dict(super().corporate_action_report(), daily_policy_observations=len(self.daily_policy.audit))


class LifecyclePersonalizedLedger(PersonalizedLedger):
    def _convert(self, event, day):
        source, target = event['source'], event['target']
        had_position = source in self.state.positions
        super()._convert(event, day)
        if had_position and target in self.state.positions:
            self.active_profiles[target] = self.active_profiles.pop(source)

    def corporate_action_report(self):
        report = GridLedger.corporate_action_report(self)
        choices = {(r['symbol'], pd.Timestamp(r['entry_date'])):r for r in self.profile_audits}
        verified = []
        for t in self.state.closed_trades:
            original = t.get('entry_symbol') or t['symbol']
            # Pandas NaN is not a usable entry identity.
            if pd.isna(original): original = t['symbol']
            key = (original, pd.Timestamp(t['entry_date']))
            if key not in choices: raise ValueError('Missing immutable profile identity')
            choice = choices[key]; tp, sl = choice['tp'], choice['sl']
            if not np.isclose(t['replay_initial_stop_price'], t['entry_price']*(1-sl), rtol=1e-8, atol=1e-7):
                raise ValueError('Personalized stop changed after entry')
            if not np.isclose(t['replay_take_profit_price'], t['entry_price']*(1+tp), rtol=1e-8, atol=1e-7):
                raise ValueError('Personalized target changed after entry')
            duration = self.days.get_loc(pd.Timestamp(t['exit_date']))-self.days.get_loc(pd.Timestamp(t['entry_date']))
            if not 0 <= duration <= 20 or (t['exit_reason'] == 'expiry_open' and duration != 20):
                raise ValueError('Personalized expiry chronology changed')
            if choice.get('booked_stop_risk', 0) > float(choice['risk_budget'])+1e-6:
                raise ValueError('Actual stop risk exceeded entry budget')
            verified.append(dict(symbol=t['symbol'], entry_symbol=original, entry_date=t['entry_date'], tp=tp, sl=sl))
        return dict(report, profile_choices=self.profile_audits,
            personalized_trade_profiles=verified,
            personalized_protection_audit=dict(trades=len(verified), verified=True))


def daily_feature_tail(root):
    """No database/network: qualified archived bars, causal rolling features.

    The successor uses its predecessor's prefix on the qualified common basis.
    Synthetic lineage is local only and explicitly not an independent PIT source.
    """
    target = root/'daily-tail'; target.mkdir(exist_ok=True)
    if (target/'ready.json').exists():
        verify_hashes(target, read(target/'ready.json')['files'])
        return pd.read_parquet(target/'features.parquet')
    from modelFactory.features import compute_features
    prices = pd.read_parquet(root/'prices.parquet')
    candidates = freeze_candidates(pd.read_parquet(root/'scores.parquet'), 50, 'NEW_BARRIER_LONG')
    required = set(candidates.loc[candidates.date.dt.year.eq(2026)].symbol)
    events = load_events(root)
    for e in events:
        if e['source'] in required: required.add(e['target'])
    benchmark = prices.loc[prices.symbol.eq('SPY')].sort_values('date').copy()
    benchmark['adj_close'] = benchmark.close
    output = []
    for i, symbol in enumerate(sorted(required)):
        bars = prices.loc[prices.symbol.eq(symbol)].copy()
        for e in events:
            if e['target'] == symbol and e.get('event_type') == 'NAME_CHANGE':
                prefix = prices.loc[prices.symbol.eq(e['source']) & prices.date.lt(e['day'])].copy()
                ratio = float(e['ratio'])
                prefix[['open', 'high', 'low', 'close']] /= ratio
                prefix['volume'] *= ratio
                prefix['symbol'] = symbol
                bars = pd.concat([prefix, bars.loc[bars.date.ge(e['day'])]], ignore_index=True)
        bars = bars.sort_values('date'); bars['adj_close'] = bars.close
        bars['vwap'] = np.nan
        frame = compute_features(bars, benchmark_df=benchmark, feature_set='expert')
        frame['drawdown_20'] = frame.adj_close/frame.adj_close.rolling(20).max()-1
        roll_min, roll_max = frame.adj_close.rolling(20).min(), frame.adj_close.rolling(20).max()
        frame['high_low_position_20'] = (frame.adj_close-roll_min)/(roll_max-roll_min).clip(lower=1e-8)
        tail = frame.loc[frame.date.gt('2026-09-03'), ['date', 'symbol', *FEATURES]]
        output.append(tail)
        atomic_json(target/'progress.json', dict(status='RUNNING', completed=i+1, total=len(required)))
    result = pd.concat(output, ignore_index=True)
    if result.duplicated(['date', 'symbol']).any(): raise ValueError('Duplicate tail keys')
    result.to_parquet(target/'features.parquet', index=False)
    atomic_json(target/'ready.json', dict(files={'features.parquet':digest(target/'features.parquet')},
        rows=len(result), symbols=int(result.symbol.nunique()),
        source='same adjusted price archive and explicit predecessor/successor lineage; no SQL',
        price_basis_reserve='vendor adjusted retrospective basis; not independent availability proof'))
    atomic_json(target/'progress.json', dict(status='COMPLETED', rows=len(result)))
    return result


def head(frame, columns, target, binary, output):
    marker = output.with_suffix('.json')
    if output.exists() and marker.exists():
        if digest(output) != read(marker)['model_sha256']: raise ValueError('Changed challenger weights')
        return lgb.Booster(model_file=str(output))
    return train_head(frame, columns, target, binary=binary, output=output)


def worker(root, name, year, count):
    root = Path(root); case = root/name/f'{year}-TOP{count}'; case.mkdir(parents=True, exist_ok=True)
    with (case/'stdout.log').open('a', encoding='utf-8') as stdout, (case/'stderr.log').open('a', encoding='utf-8') as stderr:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            extras = {}; policy = None
            if name == 'ENTRY_FILTER':
                extras['scores_override'] = pd.read_parquet(root/name/'models'/'filter-decisions.parquet')
            elif name == 'DAILY_EXIT':
                policy = CausalDailyExit(lgb.Booster(model_file=str(root/name/'models'/'keep_advantage.txt')),
                    pd.read_parquet(root/name/'models'/'observed-features.parquet'))
                extras.update(daily_exit_policy=policy,
                    ledger_factory=partial(DailyExitLedger, daily_policy=policy, cash_policy='STRICT', events=load_events(root)))
            elif name in ('PERSONAL_TP_SL', 'FIXED_SL10_SIZING_CONTROL'):
                f = pd.read_parquet(root/'PERSONAL_TP_SL'/'models'/'profile-decisions.parquet')
                profiles = {(pd.Timestamp(r.date), r.symbol): (r.tp, r.sl) for r in f.itertuples(index=False)}
                if name == 'FIXED_SL10_SIZING_CONTROL': profiles = {key:(.2,.1) for key in profiles}
                extras['session_factory'] = partial(SizedSession, profiles=profiles)
                if name == 'PERSONAL_TP_SL':
                    extras['ledger_factory'] = partial(LifecyclePersonalizedLedger, profiles=profiles,
                        cash_policy='STRICT', events=load_events(root))
            else: raise ValueError('Unknown experiment')
            result = run_case(root, year, count, experiment=name, **extras)
            if policy is not None and result['status'] != 'FAILED':
                # A resumed completed case must not overwrite its prior diary.
                diary = case/'daily-model-decisions.parquet'
                if policy.audit or not diary.exists():
                    pd.DataFrame(policy.audit).to_parquet(diary, index=False)
                result['files'][diary.name] = digest(diary)
                result['learned_exit_orders_sha256'] = digest(case/'learned_exit_orders.json')
                atomic_json(case/'case-report.json', result)
            return result


def audit_stage(root, name, reports):
    expected = {(y,n) for y in YEARS for n in COUNTS}
    if len(reports) != 9 or {(r['year'],r['count']) for r in reports} != expected:
        raise ValueError('Missing or duplicated annual replay')
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp('2026-10-09').date())
    checks = []
    selected = freeze_candidates(pd.read_parquet(root/'scores.parquet'), 50, 'NEW_BARRIER_LONG')
    selection = selected.set_index(['date','symbol'])['selection_rank']
    for r in reports:
        if r['status'] != 'COMPLETED_EXPLORATORY': raise ValueError(f"Failed case {r['year']}/{r['count']}: {r.get('error')}")
        case = root/name/f"{r['year']}-TOP{r['count']}"; verify_hashes(case, r['files'])
        trades, daily = pd.read_parquet(case/'trades.parquet'), pd.read_parquet(case/'daily.parquet')
        if annual_metrics(r, trades, daily, r['year']) != r['annual_metrics']:
            raise ValueError('Trade/summary mismatch')
        if daily.positions.iloc[-1] != 0 or abs(r['cash_reconciliation_error']) > 1e-6 or not r['account_wealth_complete']:
            raise ValueError('Unclosed/incomplete/unreconciled portfolio')
        if not trades.empty:
            if not trades.side.eq('buy').all(): raise ValueError('Non-LONG challenger trade')
            ids = trades.symbol if 'entry_symbol' not in trades else trades.entry_symbol.fillna(trades.symbol)
            keys = pd.MultiIndex.from_arrays([pd.to_datetime(trades.signal_date), ids])
            ranks = selection.reindex(keys)
            if ranks.isna().any() or ranks.gt(r['count']).any():
                raise ValueError('Challenger substituted a candidate below TOPN')
            if name == 'ENTRY_FILTER':
                flags = pd.read_parquet(root/name/'models'/'filter-decisions.parquet').set_index(['date','symbol']).entry_allowed
                if not flags.reindex(keys).fillna(False).all(): raise ValueError('Entry filter bypassed')
        if name != 'PERSONAL_TP_SL':
            protection = verify_trade_contract(trades, .2, .1, calendar)
        else:
            protection = r['personalized_protection_audit']
            if not protection['verified'] or protection['trades'] != len(trades): raise ValueError('Unverified profiles')
        if name == 'DAILY_EXIT':
            diary = pd.read_parquet(case/'daily-model-decisions.parquet')
            if len(diary) and not pd.to_datetime(diary.entry_signal_date).lt(pd.to_datetime(diary.decision_date)).all():
                raise ValueError('Daily model lost original entry chronology')
            executions = pd.DataFrame(read(case/'learned_exit_orders.json'))
            if len(executions) and not pd.to_datetime(executions.execution_date).gt(pd.to_datetime(executions.decision_date)).all():
                raise ValueError('Daily model executed before the next session')
            if digest(case/'learned_exit_orders.json') != r.get('learned_exit_orders_sha256'):
                raise ValueError('Learned execution journal changed')
        checks.append(dict(year=r['year'], count=r['count'], protection=protection, cash_error=r['cash_reconciliation_error']))
    verify_hashes(Path('.'), read(root/'challenger-protocol.json')['source_hashes'])
    verify_hashes(root, read(root/'ready.json')['files'])
    out = dict(status='NINE_CHALLENGER_CASES_VERIFIED', experiment=name, checks=checks,
        independent_experiment=True, no_automatic_promotion=True)
    atomic_json(root/name/'audit.json', out)
    return out


def replay_stage(root, name, workers):
    reports = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(worker, str(root), name, y, n):(y,n) for y in YEARS for n in COUNTS}
        for future in as_completed(tasks):
            y, n = tasks[future]
            try: result = future.result()
            except Exception as exc:
                result = dict(status='FAILED', experiment=name, year=y, count=n, error_type=type(exc).__name__, error=str(exc))
            reports.append(result)
            atomic_json(root/'progress.json', dict(status='RUNNING', phase=name, completed_runs=len(reports), total_runs=9,
                failed_runs=sum(r['status']=='FAILED' for r in reports), last_year=y, last_count=n))
            atomic_json(root/name/'report.partial.json', dict(portfolios=reports))
            LOG.info('%s %s TOP%s: %s %s', name, y, n, result['status'], result.get('error',''))
    reports.sort(key=lambda r:(r['year'],r['count']))
    if any(r['status'] == 'FAILED' for r in reports):
        atomic_json(root/name/'report.json', dict(status='FAILED', portfolios=reports))
        raise RuntimeError(f'{name} failed; subsequent experiments NOT started')
    audit_stage(root, name, reports)
    atomic_json(root/name/'report.json', dict(status='COMPLETED_EXPLORATORY', portfolios=reports, audited=True))
    return reports


def comparisons(root):
    base = {(r['year'],r['count']):r['annual_metrics'] for r in read(root/'baseline-report.json')['portfolios']}
    rows = []
    for name in (*STAGES, 'FIXED_SL10_SIZING_CONTROL'):
        path = root/name/'report.json'
        if not path.exists() or read(path)['status'] != 'COMPLETED_EXPLORATORY': continue
        for r in read(path)['portfolios']:
            m, ref = r['annual_metrics'], base[(r['year'],r['count'])]
            row = dict(experiment=name, year=r['year'], count=r['count'], **m,
                delta_return_points=m['return_pct']-ref['return_pct'],
                delta_drawdown_points=m['max_drawdown_pct']-ref['max_drawdown_pct'])
            if name == 'PERSONAL_TP_SL':
                control = next(x['annual_metrics'] for x in read(root/'FIXED_SL10_SIZING_CONTROL'/'report.json')['portfolios']
                    if (x['year'],x['count']) == (r['year'],r['count']))
                row['delta_return_vs_same_sizing'] = m['return_pct']-control['return_pct']
            rows.append(row)
    atomic_json(root/'comparisons.json', dict(status='EXPLORATORY', comparisons=rows, no_automatic_promotion=True))
    lines = ['# Trois challengers Oracle TP20/SL10', '',
        'LONG, capital annuel 4 000 USD. 2026 partiel. Tests déjà observés : pas de promotion automatique.', '',
        '| Expérience | Année | TOP | Capital final $ | Gains $ | Pertes $ | Gagnants % | DD % | Rendement % | Écart baseline pts |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        values = [r[k] for k in ('final_capital_usd','winning_amount_usd','losing_amount_usd','winning_pct',
                                'max_drawdown_pct','return_pct','delta_return_points')]
        lines.append(f"| {r['experiment']} | {r['year']} | {r['count']} | "+' | '.join(
            f'{v:.2f}' if v is not None else '—' for v in values)+' |')
    (root/'comparisons.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def run(root, baseline, model, workers=3, through='PERSONAL_TP_SL'):
    initialize(root, baseline, model)
    entries, states = training_data(root/'fit-data', model)
    external = pd.read_parquet(root/'features.parquet', columns=['date','symbol',*FEATURES]).merge(
        pd.read_parquet(root/'scores.parquet'), on=['date','symbol'], validate='one_to_one')
    external['score_difference'] = external[SCORES['long']]-external[SCORES['short']]
    columns = FEATURES+SCORE_FEATURES
    for name in STAGES[:STAGES.index(through)+1]:
        marker = root/name/'report.json'
        if marker.exists() and read(marker)['status'] == 'COMPLETED_EXPLORATORY':
            audit_stage(root, name, read(marker)['portfolios']); continue
        models = root/name/'models'; models.mkdir(parents=True, exist_ok=True)
        atomic_json(root/'progress.json', dict(status='RUNNING', phase=name, activity='fit_causal_challenger'))
        if name == 'ENTRY_FILTER':
            model_ = head(entries, columns, 'label_win', True, models/'label_win.txt')
            scored = external.copy()
            scored['entry_filter_probability'] = model_.predict(input_matrix(scored, columns), num_threads=3)
            scored['entry_allowed'] = scored.entry_filter_probability.ge(.5)
            scored.to_parquet(models/'filter-decisions.parquet', index=False)
        elif name == 'DAILY_EXIT':
            state_cols = columns+['age','pnl','mfe','mae','distance_stop','distance_tp']
            head(states, state_cols, 'keep_advantage', False, models/'keep_advantage.txt')
            observed = pd.concat([external, daily_feature_tail(root)], ignore_index=True)
            observed.to_parquet(models/'observed-features.parquet', index=False)
        else:
            predicted = np.stack([head(entries, columns, f'profile_target_{k}', False,
                models/f'profile_target_{k}.txt').predict(input_matrix(external, columns), num_threads=3)
                for k in range(len(PROFILES))], axis=1)
            choices = predicted.argmax(axis=1)
            f = external[['date','symbol']].copy()
            f['tp'] = [PROFILES[k][0] for k in choices]; f['sl'] = [PROFILES[k][1] for k in choices]
            for k in range(len(PROFILES)): f[f'predicted_profile_{k}'] = predicted[:,k]
            f.to_parquet(models/'profile-decisions.parquet', index=False)
            replay_stage(root, 'FIXED_SL10_SIZING_CONTROL', workers)
        replay_stage(root, name, workers)
        comparisons(root)
    atomic_json(root/'progress.json', dict(status='COMPLETED', through=through,
        original_model_unchanged=True, sql_writes=False, live_changes=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--model', type=Path, default=MODEL)
    parser.add_argument('--workers', type=int, choices=(1,2,3), default=3)
    parser.add_argument('--through', choices=STAGES, default='PERSONAL_TP_SL')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        run(args.output, args.baseline, args.model, args.workers, args.through)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        atomic_json(args.output/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc),
            subsequent_experiments_started=False))
        raise
