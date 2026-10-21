"""Frozen offline TP10/SL5 evaluator. Prepare now; no price read before full H10 maturity.

No database, supplier, broker, LLM, training, portfolio accounting or net PnL.
Later evaluation accepts only an explicitly qualified, hashed price snapshot.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import json
import math
from pathlib import Path
import uuid

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_public_information_followup import ancestor_sources

DEFAULT_CONFIG = Path('config/research/us_consensus_revenue_h10_evaluation_20261020.json')
READ = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
PRICE_COLUMNS = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume',
                 'is_filled', 'instrument_id', 'data_source', 'data_adjustment']
WINDOW_FIELDS = ['symbol', 'entry_date', 'last_session', 'currency', 'instrument_id',
                 'data_source', 'data_adjustment', 'corporate_actions_status', 'final_sessions_verified',
                 'status', 'evidence_paths']


def stamp(value):
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is None:
        raise ValueError('Explicit UTC/timezone timestamp required')
    return result.tz_convert('UTC')


@lru_cache(maxsize=256)
def _calendar_window(entry, sessions=10):
    day = pd.Timestamp(entry)
    if day.tzinfo is not None or day != day.normalize():
        raise ValueError('Entry must be a session date, not an intraday timestamp')
    schedule = mcal.get_calendar('NYSE').schedule(start_date=day - pd.Timedelta(days=10),
                                                end_date=day + pd.Timedelta(days=sessions * 4 + 15))
    if day not in schedule.index:
        raise ValueError('Entry outside NYSE session')
    pos = schedule.index.get_loc(day)
    dates = schedule.index[pos:pos + sessions]
    if len(dates) != sessions:
        raise ValueError('Incomplete calendar')
    return (tuple(str(d)[:10] for d in dates), stamp(schedule.iloc[pos].market_open),
            str(schedule.index[pos - 1])[:10], stamp(schedule.iloc[pos + sessions - 1].market_close))


def calendar_window(entry, sessions=10):
    dates, opening, prior, maturity = _calendar_window(str(entry), sessions)
    return dict(dates=list(dates), entry_open=opening, prior_session=prior, maturity=maturity)


def validate_config(config):
    fixed = dict(schema='us_consensus_revenue_h10_evaluation_v1', take_profit_pct=.10,
                 stop_loss_pct=.05, sessions=10, calendar='NYSE', ambiguous_day='STOP_FIRST',
                 entry='FIRST_SESSION_OPEN', expiry='TENTH_SESSION_CLOSE',
                 adverse_stop_gap='OPEN_PRICE', favorable_target_gap='TARGET_PRICE_CONSERVATIVE',
                 aggregate_coverage='STRICT_ALL_EXPECTED_EPISODES_PER_ARM', production_admission=False,
                 short_borrow_verified=False, net_costs_qualified=False)
    if any(config.get(key) != value for key, value in fixed.items()):
        raise ValueError('Frozen TP10/SL5/H10 protocol changed; use a separate experiment')


def supported_cohort(frame, contexts, config):
    """Keep complete Oracle membership, no replacement and no backdated context proof."""
    f = frame.copy()
    if len(f) != config['expected_members'] or f.duplicated(['entry_date', 'symbol']).any():
        raise ValueError('Oracle membership missing or duplicated')
    if set(f.oracle_rank) != set(range(1, len(f) + 1)):
        raise ValueError('Oracle ranks incomplete')
    originals = set(config['original_supported_symbols'])
    extras = set(config['addendum_supported_symbols'])
    if originals & extras or set(contexts.loc[contexts.context_complete.eq(True), 'symbol']) != extras:
        raise ValueError('Context qualification membership changed')
    if contexts.symbol.duplicated().any():
        raise ValueError('Duplicate context evidence')
    additions = contexts.set_index('symbol').to_dict('index')
    rows = []
    for r in f.sort_values('oracle_rank').to_dict('records'):
        window = calendar_window(r['entry_date'])
        if str(pd.Timestamp(r['entry_date']))[:10] != config['entry_date']:
            raise ValueError('Unexpected entry cohort')
        if str(r['prediction_date'])[:10] != window['prior_session']:
            raise ValueError('Oracle must refer to exact prior session')
        if pd.to_datetime(r['created_at'], utc=True) >= window['entry_open']:
            raise ValueError('Oracle unavailable before entry')
        # No consensus pair means its copied feature timestamp is NaT. Calendar
        # membership remains known and must not drop this Oracle control case.
        if ((pd.notna(r.get('entry_open_utc')) and stamp(r['entry_open_utc']) != window['entry_open'])
                or (r['pair_present'] == True and pd.isna(r.get('entry_open_utc')))
                or stamp(r['maturity_utc']) != window['maturity']):
            raise ValueError('Frozen calendar mismatch')
        symbol = r['symbol']; group = 'NOT_CONTEXT_QUALIFIED'; signal = 'ABSTAIN'
        if symbol in originals or symbol in extras:
            if not (r['pair_present'] == True and r['technical_pair'] == True and r['envelope_verified'] == True
                    and r['count_group'] == 'UNCHANGED_COUNT' and r['numeric_pattern'] in ('LONG', 'SHORT')):
                raise ValueError('Supported case no longer has a coherent archived pair')
            if not (r['old_count'] >= 3 and r['old_count'] == r['new_count']):
                raise ValueError('Analyst-count contract changed')
            if not (stamp(r['old_available']) < stamp(r['prior_entry_open_utc']) < window['entry_open']
                    and stamp(r['new_available']) < window['entry_open']):
                raise ValueError('Consensus unavailable before decisions')
            if symbol in originals:
                if r['supported_research_feature'] != True or r['qualified_pattern'] != r['numeric_pattern']:
                    raise ValueError('Original qualification mismatch')
                group = 'ORIGINAL_SUPPORT'
            else:
                context = additions[symbol]
                if (context['reporting_currency'] != 'USD' or context['provider_anchor'] != r['fiscal_anchor']
                        or context['numeric_pattern'] != r['numeric_pattern']):
                    raise ValueError('Public context does not match vendor period/pattern')
                group = 'LATER_PUBLIC_CONTEXT_EXPLORATORY'
            # Recompute the sign, not just reuse a preexisting signal column.
            old, new = float(r['old_revenue']), float(r['new_revenue'])
            if not (math.isfinite(old) and math.isfinite(new) and min(old, new) > 0 and old != new):
                raise ValueError('Invalid changed revenues')
            signal = 'LONG' if new > old else 'SHORT'
            if signal != r['numeric_pattern']:
                raise ValueError('Revenue sign mismatch')
        rows.append(dict(symbol=symbol, entry_date=config['entry_date'], oracle_rank=int(r['oracle_rank']),
            stratum='TOP10' if r['oracle_rank'] <= 10 else 'RANK11_TO_TOP20_PERCENT',
            prediction_date=window['prior_session'], signal=signal, support_group=group,
            entry_open_utc=window['entry_open'], maturity_utc=window['maturity'],
            last_session=window['dates'][-1], qualification_known_before_entry=False,
            live_admission=False))
    if {r['symbol'] for r in rows if r['signal'] != 'ABSTAIN'} != originals | extras:
        raise ValueError('Supported symbol absent from frozen Oracle selection')
    return pd.DataFrame(rows)


def prepare(root, config_path=DEFAULT_CONFIG):
    if (root / 'protocol.json').exists():
        protocol = READ(root / 'protocol.json')
        verify_hashes(Path('.'), protocol['sources'])
        verify_hashes(root, READ(root / 'ready.json')['files'])
        return protocol
    if root.exists():
        raise ValueError('New experiment directory required')
    config = READ(config_path); validate_config(config)
    parent = Path(config['cohort_root']); context = Path(config['context_root'])
    reconciled = []
    for base in (parent, context):
        reconciled += ancestor_sources(READ(base / 'protocol.json')['sources'])
        verify_hashes(base, READ(base / 'report.json')['files'])
    if not READ(context / 'audit.json')['status'] == 'PASS':
        raise ValueError('Public context not audited')
    if not READ(parent / 'audit.json')['status'].startswith('PASS'):
        raise ValueError('Parent cohort not audited')
    frame = supported_cohort(pd.read_parquet(parent / 'qualified-cohort.parquet'),
        pd.read_parquet(context / 'consensus-context-review.parquet'), config)
    root.mkdir(parents=True)
    paths = [Path(__file__), Path('tests/test_us_consensus_revenue_h10_evaluation.py'), config_path,
             Path('scripts/research/us_public_information_followup.py'),
             parent / 'protocol.json', parent / 'report.json', parent / 'audit.json', parent / 'qualified-cohort.parquet',
             context / 'protocol.json', context / 'report.json', context / 'audit.json',
             context / 'consensus-context-review.parquet']
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), config=config,
        sources={str(p): digest(p) for p in paths}, ancestor_newlines=reconciled,
        hypotheses='Up revenue LONG/down SHORT; unchanged analyst count>=3. EPS excluded. No threshold optimization.',
        comparison='Matched always-LONG/always-SHORT plus full unfiltered Oracle arms. TOP10 and remaining ranks separate; union overlaps.',
        inference='Exploratory after entry, later public qualifications not backdated. Six cases cannot establish robustness.',
        execution='Barrier diagnostics only: no sizing/capital/fees/borrow/liquidity fills. Not an executable portfolio or net PnL.',
        maturity_gate='Wait for the tenth NYSE close for ALL planned members even if a barrier might have been reached earlier.',
        price_contract='Qualified identity/currency/source/adjustment/corporate-actions per whole window; all ten bars required, strict per-arm denominators.',
        sql=False, supplier_calls=0, llm_calls=0, training=False, orders=False, production_changes=False)
    atomic_json(root / 'protocol.json', protocol)
    frame.to_parquet(root / 'evaluation-cohort.parquet', index=False)
    keys = []; windows = []
    for r in frame.to_dict('records'):
        dates = calendar_window(r['entry_date'])['dates']
        keys.extend(dict(symbol=r['symbol'], date=day) for day in dates)
        windows.append(dict(symbol=r['symbol'], entry_date=r['entry_date'], last_session=dates[-1],
            status='REQUIRES_QUALIFICATION', currency=None, instrument_id=None, data_source=None,
            data_adjustment=None, corporate_actions_status='UNKNOWN', final_sessions_verified=False, evidence_paths=[]))
    pd.DataFrame(keys).to_csv(root / 'required-price-keys.csv', index=False)
    atomic_json(root / 'price-requirements.json', dict(schema='us_consensus_h10_prices_v1',
        status='REQUIREMENTS_ONLY_NOT_A_QUALIFIED_MANIFEST', required_columns=PRICE_COLUMNS,
        expected_keys=len(keys), windows=windows,
        evidence='Every QUALIFIED window needs archived identity, currency/basis and corporate-action evidence, bound to its exact dates. No guessed CLEAR status.',
        retrieved_at_utc=None, prices_sha256=None, evidence_files={}))
    atomic_json(root / 'ready.json', dict(status='PREPARED_AWAITING_MATURITY', members=len(frame),
        supported=int(frame.signal.ne('ABSTAIN').sum()), earliest_evaluation_utc=frame.maturity_utc.max(),
        price_data_read=False, files={n: digest(root / n) for n in
            ['protocol.json', 'evaluation-cohort.parquet', 'required-price-keys.csv', 'price-requirements.json']}))
    return protocol


def ge(a, b):
    return a > b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0)


def le(a, b):
    return a < b or math.isclose(a, b, rel_tol=1e-12, abs_tol=0)


def quality_window(bars, dates, qualification):
    reasons = []
    if qualification is None or qualification.get('status') != 'QUALIFIED':
        reasons.append('WINDOW_NOT_QUALIFIED')
    elif (qualification.get('currency') != 'USD' or qualification.get('corporate_actions_status') not in ('CLEAR_VERIFIED', 'RESOLVED_VERIFIED')
          or qualification.get('final_sessions_verified') is not True
          or not qualification.get('evidence_paths')):
        reasons.append('IDENTITY_CURRENCY_BASIS_OR_ACTIONS_UNQUALIFIED')
    f = bars.copy()
    if f.empty:
        return ['MISSING_BARS'] + reasons
    required = set(PRICE_COLUMNS)
    if not required.issubset(f.columns):
        return ['MISSING_PRICE_COLUMNS'] + reasons
    converted = pd.to_datetime(f.date, errors='coerce')
    if converted.isna().any() or getattr(converted.dt, 'tz', None) is not None or not converted.eq(converted.dt.normalize()).all():
        return ['INVALID_SESSION_DATE'] + reasons
    f['date'] = converted.dt.strftime('%Y-%m-%d')
    if f.date.duplicated().any():
        reasons.append('DUPLICATE_SESSION')
    if set(f.date) != set(dates) or len(f) != len(dates):
        reasons.append('INCOMPLETE_OR_EXTRANEOUS_WINDOW')
    for key in ('open', 'high', 'low', 'close', 'volume'):
        values = pd.to_numeric(f[key], errors='coerce')
        if not (np.isfinite(values) & values.gt(0)).all():
            reasons.append('INVALID_' + key.upper())
    o, h, l, c = [pd.to_numeric(f[k], errors='coerce') for k in ('open', 'high', 'low', 'close')]
    if not (h.ge(pd.concat([o, c], axis=1).max(axis=1)) & l.le(pd.concat([o, c], axis=1).min(axis=1)) & h.ge(l)).all():
        reasons.append('INVALID_OHLC_GEOMETRY')
    if not f.is_filled.eq(0).all():
        reasons.append('FILLED_OR_UNKNOWN_BAR')
    for key in ('instrument_id', 'data_source', 'data_adjustment'):
        if f[key].isna().any() or f[key].nunique() != 1 or f[key].astype(str).str.upper().isin(['', 'NONE', 'NAN', 'UNKNOWN']).any():
            reasons.append('UNKNOWN_OR_CHANGED_' + key.upper())
        elif qualification is not None and str(f[key].iloc[0]) != str(qualification.get(key)):
            reasons.append('MANIFEST_MISMATCH_' + key.upper())
    if f.data_source.astype(str).str.upper().str.contains('IEX', regex=False).any():
        reasons.append('IEX_NOT_QUALIFIED_FOR_THIS_EXPERIMENT')
    return sorted(set(reasons))


def barrier_path(bars, side, tp=.10, sl=.05):
    """Pure kernel: caller must validate the entire mature window first."""
    if len(bars) != 10 or side not in ('LONG', 'SHORT') or not (0 < tp < 1 and 0 < sl < 1):
        raise ValueError('Invalid barrier side or percentages')
    f = bars.sort_values('date'); entry = float(f.iloc[0].open); direction = 1 if side == 'LONG' else -1
    target = entry * (1 + direction * tp); stop = entry * (1 - direction * sl)
    for i, row in enumerate(f.itertuples(index=False), start=1):
        opening = float(row.open)
        stop_gap = le(opening, stop) if side == 'LONG' else ge(opening, stop)
        target_gap = ge(opening, target) if side == 'LONG' else le(opening, target)
        stop_touch = le(float(row.low), stop) if side == 'LONG' else ge(float(row.high), stop)
        target_touch = ge(float(row.high), target) if side == 'LONG' else le(float(row.low), target)
        outcome = None; ambiguous = False
        if stop_gap:
            outcome, price, why = 'SL_FIRST', opening, 'ADVERSE_OPEN_GAP'
        elif target_gap:
            outcome, price, why = 'TP_FIRST', target, 'FAVORABLE_OPEN_GAP_CAPPED_AT_TARGET'
        elif stop_touch:
            outcome, price, why = 'SL_FIRST', stop, 'STOP_TOUCH'
            ambiguous = target_touch
            if ambiguous:
                why = 'BOTH_BARRIERS_SAME_DAY_STOP_FIRST'
        elif target_touch:
            outcome, price, why = 'TP_FIRST', target, 'TARGET_TOUCH'
        if outcome is not None:
            break
    else:
        i = len(f); row = f.iloc[-1]; price = float(row.close); outcome = 'EXPIRED'; why = 'TENTH_SESSION_CLOSE'; ambiguous = False
    return dict(barrier_outcome=outcome, entry_price=entry, exit_price=float(price),
        exit_date=str(pd.Timestamp(row.date))[:10], exit_session=i, exit_reason=why,
        ambiguous_same_day=bool(ambiguous), gross_return=direction * (price / entry - 1),
        executable_fill_verified=False, net_return=None)


def manifest_windows(manifest, price_path, as_of):
    if manifest.get('schema') != 'us_consensus_h10_prices_v1' or manifest.get('status') != 'QUALIFIED_RESEARCH_INPUT':
        raise ValueError('Requirements template is not qualified price evidence')
    if stamp(manifest['retrieved_at_utc']) > as_of:
        raise ValueError('Price snapshot not available at evaluation cutoff')
    if digest(price_path) != manifest.get('prices_sha256'):
        raise ValueError('Price snapshot checksum mismatch')
    evidence = manifest.get('evidence_files', {})
    if not evidence:
        raise ValueError('No archived price qualification evidence')
    for name, expected in evidence.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not path.as_posix().startswith('artifacts/research/'):
            raise ValueError('Evidence must be a research archive within workspace')
        if digest(path) != expected:
            raise ValueError('Price qualification evidence checksum mismatch')
    windows = {}
    for row in manifest['windows']:
        key = (row['symbol'], row['entry_date'])
        if key in windows:
            raise ValueError('Duplicate qualified window')
        if set(row.get('evidence_paths', [])) - set(evidence):
            raise ValueError('Window evidence missing from manifest')
        if stamp(manifest['retrieved_at_utc']) < calendar_window(row['entry_date'])['maturity']:
            raise ValueError('Snapshot captured before the complete H10 window')
        windows[key] = row
    return windows


def arm_summaries(results, cohort):
    summaries = []
    strata = [('TOP10', cohort[cohort.stratum.eq('TOP10')]),
              ('RANK11_TO_TOP20_PERCENT', cohort[cohort.stratum.ne('TOP10')]),
              ('ALL_TOP20_PERCENT_OVERLAPPING_UNION', cohort)]
    for stratum, group in strata:
        all_keys = set(zip(group.entry_date, group.symbol))
        groups = [('ALL_ORACLE', all_keys, ('ORACLE_LONG_UNFILTERED', 'ORACLE_SHORT_UNFILTERED'))]
        qualified = group[group.signal.ne('ABSTAIN')]
        for support in ('ORIGINAL_SUPPORT', 'LATER_PUBLIC_CONTEXT_EXPLORATORY', 'COMBINED_EXPLORATORY_OVERLAPPING_UNION'):
            f = qualified if support.startswith('COMBINED') else qualified[qualified.support_group.eq(support)]
            groups.append((support, set(zip(f.entry_date, f.symbol)), ('CONSENSUS_DIRECTION', 'ALWAYS_LONG_MATCHED', 'ALWAYS_SHORT_MATCHED')))
        for support, keys, arms in groups:
            for arm in arms:
                selected = [r for r in results if (r['entry_date'], r['symbol']) in keys
                            and (arm != 'CONSENSUS_DIRECTION' or r['side'] == r['signal'])
                            and (arm not in ('ORACLE_LONG_UNFILTERED', 'ALWAYS_LONG_MATCHED') or r['side'] == 'LONG')
                            and (arm not in ('ORACLE_SHORT_UNFILTERED', 'ALWAYS_SHORT_MATCHED') or r['side'] == 'SHORT')]
                valid = [r for r in selected if r['status'] == 'EVALUATED']
                expected = len(keys); complete = expected > 0 and len(valid) == expected
                counts = Counter(r['barrier_outcome'] for r in valid)
                summaries.append(dict(stratum=stratum, support_group=support, arm=arm, expected=expected,
                    evaluated=len(valid), missing=expected - len(valid), entry_sessions=len({k[0] for k in keys}),
                    status='COMPLETE_DESCRIPTIVE_ONLY' if complete else 'EMPTY' if expected == 0 else 'INCOMPLETE_NO_AGGREGATE_RATE',
                    tp_first_count=counts['TP_FIRST'], sl_first_count=counts['SL_FIRST'], expired_count=counts['EXPIRED'],
                    tp_first_pct=100 * counts['TP_FIRST'] / expected if complete else None,
                    sl_first_pct=100 * counts['SL_FIRST'] / expected if complete else None,
                    positive_gross_pct=100 * sum(r['gross_return'] > 1e-12 for r in valid) / expected if complete else None,
                    mean_gross_return=sum(r['gross_return'] for r in valid) / expected if complete else None,
                    costs_qualified=False, borrow_qualified=False, robustness_established=False))
    return summaries


def evaluate(root, price_path=None, manifest_path=None, *, as_of=None, now=None):
    protocol = prepare(root); cohort = pd.read_parquet(root / 'evaluation-cohort.parquet')
    real_now = stamp(now if now is not None else datetime.now(timezone.utc))
    cutoff = stamp(as_of) if as_of is not None else real_now
    if cutoff > real_now:
        raise ValueError('Future evaluation cutoff forbidden')
    attempt = root / 'attempts' / (real_now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True)
    maturity = pd.to_datetime(cohort.maturity_utc, utc=True).max()
    base = dict(as_of_utc=cutoff, evaluated_at_utc=real_now, maturity_utc=maturity,
        cohort_sha256=digest(root / 'evaluation-cohort.parquet'), expected_members=len(cohort),
        supported_episodes=int(cohort.signal.ne('ABSTAIN').sum()), training=False, orders=False,
        sql=False, supplier_calls=0, llm_calls=0, net_pnl=False)
    # Critically, no stat/hash/open/read of supplied price or manifest paths before this gate.
    if cutoff < maturity:
        report = dict(base, status='WAITING_H10_MATURITY', prices_read=False, qualified_results=0,
                      instruction='Rerun only after maturity with a separately qualified price snapshot. Do not infer early results.')
        atomic_json(attempt / 'report.json', report)
        return report, attempt
    if price_path is None or manifest_path is None:
        report = dict(base, status='BLOCKED_MISSING_QUALIFIED_PRICE_SNAPSHOT', prices_read=False)
        atomic_json(attempt / 'report.json', report)
        return report, attempt
    try:
        manifest = READ(manifest_path); windows = manifest_windows(manifest, price_path, cutoff)
        expected_keys = set()
        for r in cohort.to_dict('records'):
            expected_keys.update((r['symbol'], d) for d in calendar_window(r['entry_date'])['dates'])
        # Narrow columns/date/symbol filters; never inspect later price paths or price-derived selection.
        prices = pd.read_parquet(price_path, columns=PRICE_COLUMNS,
            filters=[('symbol', 'in', sorted({s for s, _ in expected_keys})),
                     ('date', 'in', [pd.Timestamp(d) for d in sorted({d for _, d in expected_keys})])])
        prices = prices[[key in expected_keys for key in zip(prices.symbol, pd.to_datetime(prices.date).dt.strftime('%Y-%m-%d'))]]
        results = []
        for row in cohort.to_dict('records'):
            dates = calendar_window(row['entry_date'])['dates']
            bars = prices[prices.symbol.eq(row['symbol'])].copy()
            q = windows.get((row['symbol'], row['entry_date']))
            issues = quality_window(bars, dates, q)
            if q is not None and q.get('last_session') != dates[-1]:
                issues.append('WRONG_QUALIFICATION_WINDOW')
            for side in ('LONG', 'SHORT'):
                result = dict(row, side=side, status='BLOCKED_PRICE_QUALITY' if issues else 'EVALUATED',
                              reasons=sorted(set(issues)))
                if not issues:
                    result.update(barrier_path(bars, side))
                results.append(result)
        pd.DataFrame(results).to_parquet(attempt / 'outcomes.parquet', index=False)
        prices.to_parquet(attempt / 'price-inputs.parquet', index=False)
        atomic_json(attempt / 'arms.json', arm_summaries(results, cohort))
        valid = sum(r['status'] == 'EVALUATED' for r in results)
        report = dict(base, status='COMPLETE_EXPLORATORY_BARRIER_DIAGNOSTIC' if valid == 2 * len(cohort) else 'INCOMPLETE_PRICE_QUALITY',
            prices_read=True, expected_side_paths=2 * len(cohort), evaluated_side_paths=valid,
            qualified_results=valid, same_assistant_not_independent_review=True,
            reasons=dict(Counter(reason for r in results for reason in r['reasons'])),
            price_manifest_sha256=digest(manifest_path), price_snapshot_sha256=digest(price_path),
            files={p.name: digest(p) for p in attempt.iterdir() if p.is_file()},
            inference='Counts are descriptive; six retrospective supported cases and one date do not establish directional utility. No net portfolio performance or live admission.')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        atomic_json(attempt / 'report.json', dict(base, status='FAILED_INPUT_VALIDATION', error_type=type(exc).__name__, error=str(exc)))
        raise
    atomic_json(attempt / 'report.json', report)
    return report, attempt


def audit_preparation(root):
    protocol = prepare(root)
    if (root / 'preparation-audit.json').exists():
        raise ValueError('Preparation audit immutable')
    cfg = protocol['config']; parent = Path(cfg['cohort_root']); context = Path(cfg['context_root'])
    reproduced = supported_cohort(pd.read_parquet(parent / 'qualified-cohort.parquet'),
        pd.read_parquet(context / 'consensus-context-review.parquet'), cfg)
    frozen = pd.read_parquet(root / 'evaluation-cohort.parquet')
    pd.testing.assert_frame_equal(frozen, reproduced)
    keys = pd.read_csv(root / 'required-price-keys.csv')
    expected = {(r.symbol, day) for r in frozen.itertuples(index=False)
                for day in calendar_window(r.entry_date)['dates']}
    if len(keys) != len(expected) or set(zip(keys.symbol, keys.date)) != expected:
        raise ValueError('Required price keys differ from frozen calendar')
    req = READ(root / 'price-requirements.json')
    if (len(req['windows']) != len(frozen) or req['status'] != 'REQUIREMENTS_ONLY_NOT_A_QUALIFIED_MANIFEST'
            or any(w['status'] != 'REQUIRES_QUALIFICATION' or w['final_sessions_verified'] for w in req['windows'])):
        raise ValueError('Requirements improperly presented as qualification')
    result = dict(status='PASS_PREPARATION_NO_PRICES', created_at_utc=datetime.now(timezone.utc).isoformat(),
        oracle_members=len(frozen), required_price_keys=len(keys), supported=int(frozen.signal.ne('ABSTAIN').sum()),
        supported_groups=frozen.loc[frozen.signal.ne('ABSTAIN'), 'support_group'].value_counts().to_dict(),
        maturity_utc=frozen.maturity_utc.max(), results_computed=False, prices_read=False,
        sql=False, training=False, api_calls=0, orders=False, independent_human_review=False,
        files={'protocol.json': digest(root / 'protocol.json'), 'ready.json': digest(root / 'ready.json')})
    atomic_json(root / 'preparation-audit.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'audit', 'evaluate'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prices', type=Path)
    parser.add_argument('--price-manifest', type=Path)
    parser.add_argument('--as-of', help='Timezone required, no future cutoff allowed')
    args = parser.parse_args()
    if args.phase in ('prepare', 'audit'):
        if args.prices or args.price_manifest or args.as_of:
            parser.error('Preparation must not inspect outcome prices')
        result = audit_preparation(args.output) if args.phase == 'audit' else (prepare(args.output) and READ(args.output / 'ready.json'))
        print(json.dumps(result, default=str, ensure_ascii=False))
    else:
        report, attempt = evaluate(args.output, args.prices, args.price_manifest, as_of=args.as_of)
        print(json.dumps(dict(report=report, attempt=str(attempt)), default=str, ensure_ascii=False))
        if report['status'].startswith('WAITING_'):
            raise SystemExit(3)
        if report['status'].startswith(('BLOCKED_', 'INCOMPLETE_')):
            raise SystemExit(2)


if __name__ == '__main__':
    main()
