"""Frozen small protection selector and paired native annual portfolios.

Research-only auxiliary fit; Oracle weights/live/SQL/batches remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from functools import partial
import gc
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from modelFactory.oracle.security_continuity import load_security_discontinuities
from scripts.research import us_oracle_path_protection_dataset as dataset
from scripts.research import us_oracle_path_top5_leverage_grid as grid
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import parametric_protections
from scripts.research.us_oracle_barrier_trailing_grid import trailing_protections
from scripts.research.us_oracle_path_dynamic_protections import subset_protection
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes
from service.market import parse_market_regimes

LOG = logging.getLogger(__name__)
DATA = Path('artifacts/research/us_oracle_path_protection_dataset/20261014-v1')
PROFILES = dataset.PROFILES
ARMS = ('FIXED_COURT', 'FIXED_REFERENCE', 'FIXED_LARGE', 'LEARNED')
PARAMS = dict(objective='regression', metric='l2', max_depth=2, num_leaves=4,
    min_data_in_leaf=150, learning_rate=.03, lambda_l1=.1, lambda_l2=10.,
    feature_fraction=1., bagging_fraction=1., bagging_freq=0, seed=731,
    num_threads=2, verbosity=-1, device_type='cpu', force_col_wise=True)


def choose_profiles(court, large):
    court, large = np.asarray(court, float), np.asarray(large, float)
    if court.shape != large.shape or not np.isfinite(court).all() or not np.isfinite(large).all():
        raise ValueError('Nonfinite/misaligned predicted advantage')
    values = np.column_stack([np.zeros(len(court)), court, large])
    tied = np.isclose(values, values.max(axis=1)[:, None], rtol=0, atol=1e-10)
    return np.asarray(['REFERENCE', 'COURT', 'LARGE'])[tied.argmax(axis=1)]


def constant_on_validation(frame):
    means = {p: float(frame[f'{p}_net_pct'].mean()) for p in ['REFERENCE', 'COURT', 'LARGE']}
    if not np.isfinite(list(means.values())).all():
        raise ValueError('Invalid constant validation objective')
    best = max(means.values())
    return next(p for p, v in means.items() if np.isclose(v, best, atol=1e-10, rtol=0))


def equal_date_weights(frame):
    weights = 1/frame.groupby('date').date.transform('size').astype(float)
    return (weights/weights.mean()).to_numpy()


def freeze_protocol(output):
    marker = output/'protocol.json'
    if marker.exists():
        saved = grid.read(marker); verify_hashes(Path('.'), saved['sources']); return saved
    prepared = grid.read(DATA/'protocol.json'); report = grid.read(DATA/'report.json')
    verify_hashes(Path('.'), prepared['sources']); verify_hashes(DATA, report['files'])
    if report['verdict'] != 'READY_FOR_EXPLORATORY_PILOT_NOT_TRAINED' or grid.read(DATA/'completion-audit.json')[
            'status'] != 'DATASET_KEYS_TARGETS_AND_PURGES_VERIFIED':
        raise ValueError('Qualified purged OOF dataset required')
    ready = grid.read(grid.BASE/'manifest.json')
    source_ready = grid.read(Path('artifacts/research/us_oracle_path_top5_leverage/20261014-v3')/'ready.json')
    sources = dict(prepared['sources'])
    sources.update(code_hashes())
    paths = [DATA/'protocol.json', DATA/'report.json', DATA/'completion-audit.json',
        DATA/'decision-features.parquet', DATA/'outcomes.parquet', grid.BASE/'manifest.json',
        Path('artifacts/research/us_oracle_path_top5_leverage/20261014-v3/ready.json'),
        Path(source_ready['prices']), Path(source_ready['macro']), grid.SECTORS,
        Path(__file__), Path('tests/test_us_oracle_path_protection_selector.py'),
        Path('scripts/research/us_oracle_path_dynamic_protections.py'),
        Path('scripts/research/us_oracle_path_top5_leverage_grid.py')]
    # Original archived prices/macro must still match their original checksum.
    for name in [source_ready['prices'], source_ready['macro'], str(grid.SECTORS)]:
        matches = [v for p, v in source_ready['sources'].items() if Path(p) == Path(name)]
        if len(set(matches)) != 1 or digest(name) != matches[0]:
            raise ValueError(f'Changed archived portfolio tape: {name}')
    for folder in sorted((grid.ARCHIVE/'chunks').iterdir()):
        saved = grid.read(folder/'done.json')
        verify_hashes(folder, {'features.parquet': saved['files']['features.parquet']})
        paths.extend([folder/'done.json', folder/'features.parquet'])
    paths.append(grid.ARCHIVE/'scores.parquet')
    sources.update({str(p): digest(p) for p in paths})
    value = dict(dataset=str(DATA), profiles=PROFILES, features=dataset.FEATURES,
        params=PARAMS, max_iterations=150, early_stopping=15, weighting='equal total per decision date; mean weight one',
        annual_models=prepared['annual_test_models'], arms=ARMS, cases=12,
        years=grid.ENDS, decision='highest positive predicted unit advantage, ties reference/court/large',
        constant_selection='validation2022 mean net unit return only',
        label_horizon=60, actual_portfolio_expiry=None, no_terminal_sale=True,
        sl=.05, capital_usd=4000, max_entry_leverage=2, no_reinforcement=True,
        reference_is_new_models_and_shared_strict_admission=True,
        selector_training=True, oracle_training=False, sql_writes=False, broker_calls=False,
        production_changed=False, independent_holdout=False, sources=sources,
        prices=source_ready['prices'], macro=source_ready['macro'], events=source_ready['events'], market=source_ready['market'],
        protocol_document_sha256=digest('doc/ml/oracle_path_selecteur_protections_20261014.md'),
        inherited_tape_manifest_sha256=digest(grid.BASE/'manifest.json'),
        promotion_gate='complete12; learned return >each fixed all years; DD >=reference and validation-constant each year',
        reserves=grid.read('artifacts/research/us_oracle_path_top5_leverage/20261014-v3/protocol.json')['reserves'])
    atomic_json(marker, value)
    return value


def fit_selector(output, protocol):
    folder = output/'selector'; folder.mkdir(exist_ok=True)
    marker = folder/'fit.json'
    if marker.exists():
        saved = grid.read(marker); verify_hashes(folder, saved['files'])
        if not (folder/'unit-comparison.json').exists() or not (folder/'historical-decisions.parquet').exists():
            historical_comparison(folder)
        return saved
    import lightgbm as lgb
    outcomes = pd.read_parquet(DATA/'outcomes.parquet')
    x = pd.read_parquet(DATA/'decision-features.parquet')
    frame = outcomes.drop(columns='oracle_rank').merge(x, on=['date', 'symbol'], validate='one_to_one')
    fit = frame[frame.split.eq('FIT_2018_2021')].copy()
    val = frame[frame.split.eq('VALIDATION_2022')].copy()
    if not fit.label_available.lt('2022-01-01').all() or not val.label_available.lt('2023-01-01').all():
        raise ValueError('Unpurged fit/validation labels')
    if not np.isfinite(frame[dataset.FEATURES]).all().all():
        raise ValueError('Nonfinite input in qualified dataset')
    heads = {}
    for profile in ['COURT', 'LARGE']:
        target = f'target_{profile.lower()}_advantage_pct'
        train = lgb.Dataset(fit[dataset.FEATURES], label=fit[target], weight=equal_date_weights(fit))
        valid = lgb.Dataset(val[dataset.FEATURES], label=val[target], weight=equal_date_weights(val), reference=train)
        booster = lgb.train(PARAMS, train, num_boost_round=150, valid_sets=[valid],
            callbacks=[lgb.early_stopping(15, verbose=False)])
        booster.save_model(str(folder/f'{profile.lower()}.txt'))
        heads[profile] = dict(iterations=booster.best_iteration, best_validation_l2=booster.best_score['valid_0']['l2'])
    saved = dict(heads=heads, fit_rows=len(fit), validation_rows=len(val),
        fit_available_max=str(fit.label_available.max()), val_available_max=str(val.label_available.max()),
        fixed_validation_constant=constant_on_validation(val),
        validation_constant_means={p: float(val[f'{p}_net_pct'].mean()) for p in PROFILES},
        features=dataset.FEATURES, trained_on_control_or_annual_results=False,
        files={n: digest(folder/n) for n in ['court.txt', 'large.txt']})
    atomic_json(marker, saved)  # Selection fixed before any 2023/external evaluation.
    historical_comparison(folder)
    return saved


def historical_comparison(folder):
    outcomes = pd.read_parquet(DATA/'outcomes.parquet')
    x = pd.read_parquet(DATA/'decision-features.parquet')
    frame = outcomes.drop(columns='oracle_rank').merge(x, on=['date', 'symbol'], validate='one_to_one')
    decisions = predict_profiles(folder, frame[['date', 'symbol', *dataset.FEATURES]])
    decisions.to_parquet(folder/'historical-decisions.parquet', index=False)
    summaries = []
    for split in ['VALIDATION_2022', 'CONTROL_2023']:
        sub = frame[frame.split.eq(split)].merge(decisions, on=['date', 'symbol'], validate='one_to_one')
        chosen = np.asarray([sub[f'{p}_net_pct'].iloc[i] for i, p in enumerate(sub.chosen_profile)])
        summaries.append(dict(split=split, rows=len(sub), profiles=sub.chosen_profile.value_counts().to_dict(),
            learned_mean_pct=float(chosen.mean()), learned_median_pct=float(np.median(chosen)),
            constants={p: float(sub[f'{p}_net_pct'].mean()) for p in PROFILES},
            portfolio_performance=False, unbiased_validation_performance=False))
    atomic_json(folder/'unit-comparison.json', summaries)


def predict_profiles(folder, frame):
    import lightgbm as lgb
    verify_hashes(folder, grid.read(folder/'fit.json')['files'])
    if frame.duplicated(['date', 'symbol']).any() or not np.isfinite(frame[dataset.FEATURES]).all().all():
        raise ValueError('Invalid decision inputs')
    heads = {p: lgb.Booster(model_file=str(folder/f'{p.lower()}.txt')) for p in ['COURT', 'LARGE']}
    if any(model.feature_name() != dataset.FEATURES for model in heads.values()):
        raise ValueError('Selector feature order differs')
    values = {p: model.predict(frame[dataset.FEATURES], num_threads=2) for p, model in heads.items()}
    result = frame[['date', 'symbol']].copy()
    result['court_advantage_pct'] = values['COURT']; result['large_advantage_pct'] = values['LARGE']
    result['chosen_profile'] = choose_profiles(values['COURT'], values['LARGE'])
    return result


def prepare_annual(output, protocol):
    marker = output/'ready.json'
    if marker.exists():
        saved = grid.read(marker); verify_hashes(output, saved['files']); return saved
    profile = grid.read(DATA/'protocol.json')['features_profile']
    parts = []
    for year, contract in protocol['annual_models'].items():
        year = int(year); selected_path = output/f'candidates-{year}.parquet'
        score_marker = output/f'candidates-{year}.json'
        if score_marker.exists():
            verify_hashes(output, grid.read(score_marker)['files']); parts.append(pd.read_parquet(selected_path)); continue
        rows = []
        for i, folder in enumerate(sorted((grid.ARCHIVE/'chunks').iterdir())):
            frame = pd.read_parquet(folder/'features.parquet',
                filters=[('date', '>=', pd.Timestamp(f'{year}-01-01')), ('date', '<=', pd.Timestamp(grid.ENDS[year]))])
            frame = frame.drop(columns=[c for c in frame if c.endswith('_xs_rank')])
            rows.append(frame)
            if i % 12 == 0:
                atomic_json(output/'progress.json', dict(status='SCORING_ANNUAL', year=year, chunk=i, total_chunks=72))
        matrix = grid.restore_ranks(pd.concat(rows, ignore_index=True), profile['generator_options'])
        del rows; gc.collect()
        observable = pd.read_parquet(grid.ARCHIVE/'scores.parquet', columns=['date', 'symbol'])
        matrix = matrix.merge(observable, on=['date', 'symbol'], how='inner', validate='one_to_one')
        from catboost import CatBoostClassifier
        _, _, _, folds = grid.load_contract('artifacts/models', contract['batch_id'])
        model = CatBoostClassifier().load_model(folds[contract['fold']]['model_file'])
        columns = profile['feature_columns']
        if model.feature_names_ != columns:
            raise ValueError('Annual CatBoost feature order mismatch')
        scores = matrix[['date', 'symbol']].copy()
        scores['score'] = model.predict_proba(matrix[columns].replace([np.inf, -np.inf], np.nan).astype(np.float32), thread_count=2)[:, 1]
        scores['proba_extreme'] = scores.groupby('date').score.rank(method='average', pct=True)
        chosen = dataset.freeze_top5(scores)
        chosen['year'] = year; chosen['fold_start'] = contract['fold']; chosen['backend'] = 'catboost'
        chosen.to_parquet(selected_path, index=False)
        atomic_json(score_marker, dict(model_sha256=contract['model_sha256'], observable_rows=len(scores),
            original_top5=len(chosen), files={selected_path.name: digest(selected_path)}))
        parts.append(chosen); del model, matrix, scores; gc.collect()
    candidates = pd.concat(parts, ignore_index=True)
    prices = pd.read_parquet(protocol['prices']); prices.date = pd.to_datetime(prices.date)
    calendar = grid.nyse_sessions('2023-01-01', '2026-10-09')
    spy = prices[prices.symbol.eq('SPY')].set_index('date')
    benchmark = (spy.adj_close.where(spy.adj_close.notna(), spy.close)).reindex(calendar)
    features, checks = [], []
    registry = load_security_discontinuities()
    from modelFactory.oracle.security_continuity import split_frame_on_discontinuities
    for symbol, group in candidates.groupby('symbol'):
        bars = prices[prices.symbol.eq(symbol)]
        calculated, quality = [], []
        for part in split_frame_on_discontinuities(bars, symbol, registry):
            calculated.append(dataset.decision_features(part, benchmark))
            segment = part.set_index('date').reindex(calendar[(calendar >= part.date.min()) & (calendar <= part.date.max())])
            quality.append(dataset.j_history_quality(segment, benchmark, calendar))
        if not calculated:
            raise ValueError(f'Missing annual candidate tape: {symbol}')
        calc, valid = pd.concat(calculated), pd.concat(quality)
        sub = group[['date', 'symbol', 'oracle_rank']].merge(calc[dataset.STOCK+dataset.MARKET],
            left_on='date', right_index=True, how='left', validate='one_to_one')
        sub['selected'] = sub.date.map(valid).fillna(False) & np.isfinite(sub[dataset.FEATURES]).all(axis=1)
        sub['entry_quality_reason'] = np.where(sub.selected, '', 'J_HISTORY_OR_SELECTOR_INPUT_UNQUALIFIED_ALL_ARMS')
        for day in sorted(set(group.date.iloc[[0, len(group)//2, -1]])):
            part = next(p for p in split_frame_on_discontinuities(bars, symbol, registry) if p.date.min() <= day <= p.date.max())
            prefix = dataset.decision_features(part[part.date.le(day)], benchmark[benchmark.index <= day])
            pd.testing.assert_series_equal(calc.loc[day, dataset.STOCK+dataset.MARKET],
                prefix.loc[day, dataset.STOCK+dataset.MARKET], check_exact=True)
        checks.append(dict(symbol=symbol, prefix_exact=True, candidates=len(sub), qualified=int(sub.selected.sum())))
        features.append(sub)
    x = pd.concat(features, ignore_index=True)
    candidates = candidates.merge(x[['date', 'symbol', 'selected', 'entry_quality_reason']], on=['date', 'symbol'], validate='one_to_one')
    decisions = predict_profiles(output/'selector', x[x.selected][['date', 'symbol', *dataset.FEATURES]])
    x.to_parquet(output/'annual-features.parquet', index=False)
    candidates.to_parquet(output/'candidates.parquet', index=False)
    decisions.to_parquet(output/'profile-decisions.parquet', index=False)
    atomic_json(output/'annual-feature-canaries.json', checks)
    ready = dict(files={n: digest(output/n) for n in ['annual-features.parquet', 'candidates.parquet',
        'profile-decisions.parquet', 'annual-feature-canaries.json', 'selector/fit.json', 'selector/court.txt',
        'selector/large.txt', 'selector/unit-comparison.json', 'selector/historical-decisions.parquet']},
        annual_input_coverage=candidates.groupby('year').selected.agg(['size', 'sum']).reset_index().to_dict('records'))
    atomic_json(marker, ready)
    return ready


class SelectorSession(grid.MarginAwareSession):
    def decide(self, day, *, scores, regime, **kwargs):
        entries = super().decide(day, scores=scores, regime=regime, **kwargs)
        ledger = self.ledger_ref[0]
        for row in scores.itertuples(index=False):
            key = (pd.Timestamp(day), row.symbol)
            context = ledger.profile_decisions.loc[key]
            profile = context.chosen_profile if ledger.arm == 'LEARNED' else ledger.arm.removeprefix('FIXED_')
            audit = dict(decision_date=str(pd.Timestamp(day).date()), symbol=row.symbol, profile=profile,
                court_advantage_pct=float(context.court_advantage_pct), large_advantage_pct=float(context.large_advantage_pct),
                approved=any(e.symbol == row.symbol and e.approved_shares > 0 for e in entries),
                sl=.05, trailing=PROFILES[profile][0], tp=PROFILES[profile][1])
            ledger.profile_audits.append(audit); ledger.approval_profiles[key] = audit
        return entries


class SelectorLedger(grid.UnlimitedLedger):
    def __init__(self, *args, profile_decisions, arm, **kwargs):
        self.arm = arm
        self.profile_decisions = profile_decisions.set_index(['date', 'symbol'])
        self.approval_profiles, self.profile_audits, self.fill_profile_audits = {}, [], []
        profile = 'REFERENCE' if arm == 'LEARNED' else arm.removeprefix('FIXED_')
        trail, tp = PROFILES[profile]
        super().__init__(*args, sl=.05, trail=trail, tp=tp, **kwargs)

    def _build_entry_protections(self, phase3, *, execution_config):
        if self.arm != 'LEARNED':
            return super()._build_entry_protections(phase3, execution_config=execution_config)
        native = OraclePortfolioLedger._build_entry_protections(self, phase3, execution_config=execution_config)
        if native.signals_df.empty:
            return native
        parts = []
        for row in native.signals_df.itertuples(index=False):
            day = pd.Timestamp(row.trade_date).normalize()
            if day >= self.current_day:
                raise ValueError('Selector decision does not precede fill')
            audit = self.approval_profiles[(day, row.symbol)]
            if not audit['approved']:
                raise ValueError('Profile without risk approval')
            trail, tp = PROFILES[audit['profile']]
            p = parametric_protections(subset_protection(native, row.symbol), tp_pct=tp, sl_pct=.05)
            parts.append(trailing_protections(p, trail))
            self.fill_profile_audits.append(dict(audit, fill_date=str(self.current_day.date()),
                fill_price=float(row.fill_price), planned_fill_qty=float(row.filled_qty),
                actual_commit_source='executions.json, not this attempted fill'))
        frames = {n: pd.concat([getattr(p, n) for p in parts], ignore_index=True)
                  for n in ['signals_df', 'protection_frame', 'order_lifecycle_frame', 'broker_event_frame']}
        return replace(native, **frames)


_CACHE = None


def worker_init(output):
    global _CACHE
    root = Path(output); p = grid.read(root/'protocol.json')
    candidates = pd.read_parquet(root/'candidates.parquet')
    prices = pd.read_parquet(p['prices']); prices.date = pd.to_datetime(prices.date)
    required = set(candidates.symbol)|{'SPY', 'VMRK'}
    for event in p['events']:
        if event['source'] in required:
            required.add(event['target'])
    prices = prices[prices.symbol.isin(required)].copy()
    days = grid.nyse_sessions('2023-01-01', '2026-10-09')
    frames = {k: prices.pivot(index='date', columns='symbol', values=c).reindex(days)
              for k, c in [('opens', 'open'), ('close', 'close'), ('high', 'high'), ('low', 'low'), ('volume', 'volume')]}
    sectors = pd.read_parquet(grid.SECTORS).set_index('symbol').sector.to_dict()
    sectors['VMRK'] = sectors['EQR']; sectors['TELWY'] = sectors.get('TOELY', sectors.get('TELWY', 'Unknown'))
    _CACHE = dict(root=root, protocol=p, candidates=candidates, prices=prices, frames=frames, sectors=sectors,
        profiles=pd.read_parquet(root/'profile-decisions.parquet'), macro=ArchivedMacro(pd.read_parquet(p['macro'])),
        market=parse_market_regimes(p['market']))


def run_case(case):
    year, arm = case
    folder = _CACHE['root']/f'{year}-{arm}'; folder.mkdir(exist_ok=True)
    marker = folder/'case-report.json'
    if marker.exists():
        old = grid.read(marker)
        if old['status'] == 'COMPLETED':
            verify_hashes(folder, old['files']); return old
    ref = []
    def factory(cfg, **kwargs):
        ledger = SelectorLedger(cfg, profile_decisions=_CACHE['profiles'], arm=arm, study_end=grid.ENDS[year],
            cash_policy='STRICT', events=_CACHE['protocol']['events'], **kwargs)
        ref.append(ledger); return ledger
    try:
        with (folder/'stderr.log').open('a', encoding='utf-8') as log, redirect_stderr(log), redirect_stdout(log):
            logging.basicConfig(level=logging.WARNING, stream=log, force=True)
            result = run_portfolio(frames=_CACHE['frames'], scores=_CACHE['candidates'][_CACHE['candidates'].year.eq(year)],
                sectors=_CACHE['sectors'], macro=_CACHE['macro'], market_config=_CACHE['market'], policy='selected',
                variant='CURRENT_NO_EXPIRY', output=folder, start_date=f'{year}-01-01', end_date=grid.ENDS[year],
                quality=_CACHE['prices'][['date', 'symbol', 'is_filled', 'instrument_id']], ledger_factory=factory,
                session_factory=partial(SelectorSession, ledger_ref=ref),
                protection_options=dict(take_profit_enabled=True, trailing_enabled=True),
                daily_exit_policy=grid.margin_policy, reject_constrained_entries=True)
        ledger = ref[0]
        daily, trades = (pd.read_parquet(folder/n) for n in ['daily.parquet', 'trades.parquet'])
        open_rows = [dict(symbol=s, quantity=p.quantity, entry_date=str(p.entry_date.date()), entry_cost=p.entry_cost,
            unrealized_pnl_usd=p.quantity*float(ledger.close.at[pd.Timestamp(grid.ENDS[year]), s])-p.entry_cost)
                    for s, p in ledger.state.positions.items()]
        realized = float(trades.pnl.sum()) if len(trades) else 0.
        unrealized = sum(r['unrealized_pnl_usd'] for r in open_rows)
        requirement = grid.maintenance_requirement(ledger.state.positions, _CACHE['frames']['close'].loc[grid.ENDS[year]])
        ledger.margin_audits.append(dict(date=grid.ENDS[year], equity=float(daily.equity.iloc[-1]),
            required=requirement, breach=float(daily.equity.iloc[-1]) < requirement, final_mark_only=True))
        if not np.isclose(4000+realized+unrealized-ledger.interest, daily.equity.iloc[-1], atol=1e-6, rtol=1e-10):
            raise ValueError('Final wealth does not reconcile')
        if len(trades):
            if not trades.side.eq('buy').all() or not np.isclose(trades.replay_initial_stop_price, trades.entry_price*.95, atol=1e-6).all():
                raise ValueError('Unexpected side or hard SL')
            if trades.exit_reason.isin(['terminal_close', 'expiry_open', 'expiry_20_after_entry']).any():
                raise ValueError('Unexpected time/terminal liquidation')
        for name, value in [('profiles.json', ledger.profile_audits), ('fill-profiles.json', ledger.fill_profile_audits),
                            ('open-positions.json', open_rows), ('maintenance.json', ledger.margin_audits)]:
            atomic_json(folder/name, value)
        pnl = trades.groupby(['symbol', 'entry_date']).pnl.sum() if len(trades) else pd.Series(dtype=float)
        opened_profiles = []
        for event in ledger.execution_audits:
            fill_day = pd.Timestamp(event['date'])
            previous = ledger.days[ledger.days.get_loc(fill_day)-1]
            for symbol in event['opened']:
                audit = ledger.approval_profiles[(previous, symbol)]
                opened_profiles.append(dict(symbol=symbol, fill_date=fill_day, profile=audit['profile']))
        for trade in trades.itertuples(index=False):
            matches = []
            for opened in opened_profiles:
                if opened['fill_date'] != trade.entry_date:
                    continue
                alias = opened['symbol']
                for event in _CACHE['protocol']['events']:
                    if alias == event['source'] and trade.entry_date <= pd.Timestamp(event['day']) <= trade.exit_date:
                        alias = event['target']
                if alias == trade.symbol:
                    matches.append(opened['profile'])
            if len(matches) != 1:
                raise ValueError('Closed lot profile lineage is ambiguous')
            trail, tp = PROFILES[matches[0]]
            if not np.isclose(trade.replay_take_profit_price, trade.entry_price*(1+tp), atol=1e-6) or not np.isclose(
                    trade.replay_trailing_stop_pct, trail, atol=1e-12):
                raise ValueError('Closed lot TP/trailing differs from entry profile')
        atomic_json(folder/'opened-profiles.json', opened_profiles)
        gross = daily.gross_notional/daily.equity
        result.update(status='COMPLETED', year=year, arm=arm, case=f'{year}-{arm}',
            batch_id=_CACHE['protocol']['annual_models'][str(year)]['batch_id'],
            final_capital_usd=float(daily.equity.iloc[-1]), net_return_pct=100*result['return_pct'],
            dd_pct=100*result['max_drawdown'], realized_pnl_usd=realized, unrealized_pnl_usd=unrealized,
            gains_usd=float(pnl[pnl > 0].sum()), losses_usd=float(pnl[pnl < 0].sum()),
            open_positions=len(open_rows), mean_gross_leverage=float(gross.mean()), max_gross_leverage=float(gross.max()),
            margin_breaches=sum(a['breach'] for a in ledger.margin_audits),
            decision_profiles=dict(Counter(a['profile'] for a in ledger.profile_audits)),
            approved_profiles=dict(Counter(a['profile'] for a in ledger.profile_audits if a['approved'])),
            attempted_fill_profiles=dict(Counter(a['profile'] for a in ledger.fill_profile_audits)),
            executed_profiles=dict(Counter(a['profile'] for a in opened_profiles)),
            closed_lot_profiles_verified=len(trades),
            no_daily_protection_revisions=True, dividends_complete=False, historical_marginability_certified=False,
            files={p.name: digest(p) for p in folder.iterdir() if p.suffix in ['.json', '.parquet'] and p.name != 'case-report.json'})
    except Exception as exc:
        import traceback
        (folder/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        result = dict(status='FAILED', year=year, arm=arm, case=f'{year}-{arm}', error=str(exc), error_type=type(exc).__name__)
    atomic_json(marker, result)
    return result


def run(output, phase='all', workers=3):
    output = Path(output)
    with exclusive_run(output):
        protocol = freeze_protocol(output)
        fit = fit_selector(output, protocol)
        ready = prepare_annual(output, protocol)
        if phase == 'prepare':
            atomic_json(output/'progress.json', dict(status='READY_FOR_PORTFOLIOS', completed=0, total=12))
            return
        cases = [(year, arm) for year in dataset.ANNUAL_MODELS for arm in ARMS]
        reports = []
        with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(str(output),)) as pool:
            futures = [pool.submit(run_case, case) for case in cases]
            for future in as_completed(futures):
                result = future.result(); reports.append(result)
                atomic_json(output/'progress.json', dict(status='RUNNING', completed=len(reports), total=12,
                    failed=sum(r['status'] == 'FAILED' for r in reports), last=result['case']))
                atomic_json(output/'report.partial.json', dict(cases=reports))
                LOG.info('%s finished %s/12 %s', result['case'], len(reports), result['status'])
        verify_hashes(Path('.'), protocol['sources']); verify_hashes(output, ready['files'])
        comparisons = []
        for year in dataset.ANNUAL_MODELS:
            group = {r['arm']: r for r in reports if r['year'] == year and r['status'] == 'COMPLETED'}
            if len(group) != 4:
                continue
            learned, reference = group['LEARNED'], group['FIXED_REFERENCE']
            chosen = group[f'FIXED_{fit["fixed_validation_constant"]}']
            comparisons.append(dict(year=year, learned_net_pct=learned['net_return_pct'],
                reference_net_pct=reference['net_return_pct'], validation_constant=fit['fixed_validation_constant'],
                validation_constant_net_pct=chosen['net_return_pct'],
                best_fixed_test_net_pct=max(group[a]['net_return_pct'] for a in ARMS if a != 'LEARNED'),
                delta_reference_points=learned['net_return_pct']-reference['net_return_pct'],
                delta_validation_constant_points=learned['net_return_pct']-chosen['net_return_pct'],
                learned_dd_pct=learned['dd_pct'], reference_dd_pct=reference['dd_pct'], validation_constant_dd_pct=chosen['dd_pct']))
        failed = sum(r['status'] == 'FAILED' for r in reports)
        gate = not failed and len(comparisons) == 3 and all(
            c['learned_net_pct'] > c['best_fixed_test_net_pct'] and
            c['learned_dd_pct'] >= c['reference_dd_pct'] and c['learned_dd_pct'] >= c['validation_constant_dd_pct']
            for c in comparisons)
        verdict = 'PARTIAL_FAILED' if failed else 'EXPLORATORY_GAIN_TO_CONFIRM' if gate else 'NO_GO_STABLE_PERSONALIZATION'
        report = dict(status='PARTIAL_FAILED' if failed else 'COMPLETED_EXPLORATORY', verdict=verdict,
            cases=reports, comparisons=comparisons, fixed_validation_constant=fit['fixed_validation_constant'],
            selector_trained=True, oracle_retrained=False, production_changed=False, sql_writes=False, broker_calls=False,
            source_hashes_verified=True, independent_holdout=False,
            files={str(p.relative_to(output)): digest(p) for p in output.rglob('*')
                   if p.suffix in ['.json', '.parquet', '.txt'] and p.name not in ['report.json', 'progress.json', 'stderr.log']})
        pd.DataFrame([{k: v for k, v in r.items() if k != 'files'} for r in reports]).to_csv(output/'annual-summary.csv', index=False)
        atomic_json(output/'report.json', report)
        atomic_json(output/'progress.json', dict(status=report['status'], verdict=verdict, completed=12-failed, failed=failed, total=12))
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    parser.add_argument('--phase', choices=['all', 'prepare', 'run'], default='all')
    parser.add_argument('--workers', type=int, choices=[1, 2, 3], default=3)
    args = parser.parse_args(); Path(args.output).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(Path(args.output)/'stderr.log', encoding='utf-8')])
    try:
        run(**vars(args))
    except Exception as exc:
        atomic_json(Path(args.output)/'failure.json', dict(status='FAILED', error=str(exc), error_type=type(exc).__name__))
        raise
