"""Read-only matched-asof IEX/SIP audit on pre-existing Oracle TOP20/50.

No SQL writes, inference, LLM, orders, live provider change or economic backtest.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy import text

UTC = timezone.utc
DEFAULT_BATCH = 'model-factory-20261016180250-3b0515'
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
SLOTS = ('open_plus_5m', 'open_plus_150m', 'close_minus_5m')
SCENARIOS = {'risk': (300, False), 'pre_submission': (30, False), 'winner': (60, True)}


def utc(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_localize('UTC').to_pydatetime() if stamp.tzinfo is None else stamp.tz_convert('UTC').to_pydatetime()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, payload):
    raw = json.dumps(payload, indent=2, sort_keys=True, default=str, allow_nan=False).encode()
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    temporary.write_bytes(raw)
    for attempt in range(6):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.1 * (attempt+1))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def quote_metrics(quote, at, opening):
    result = dict(quote_present=isinstance(quote, dict), valid=False, age_seconds=None,
                  spread_bps=None, mid=None, bid=None, ask=None, sizes_valid=False)
    if not isinstance(quote, dict):
        return result
    try:
        bid, ask = float(quote['bp']), float(quote['ap'])
        stamp = utc(quote['t'])
        # IEX and SIP are distinct as-of states, not necessarily identical event times.
        age = (at-stamp).total_seconds()
        result.update(age_seconds=age, quote_time=stamp.isoformat())
        sizes = [float(quote[k]) for k in ('bs', 'as')]
        result['sizes_valid'] = all(math.isfinite(v) and v > 0 for v in sizes)
        if (not all(math.isfinite(v) and v > 0 for v in (bid, ask)) or ask <= bid
                or stamp < opening or age < 0):
            return result
        result.update(valid=True, bid=bid, ask=ask, mid=(ask+bid)/2,
                      spread_bps=(ask-bid)/((ask+bid)/2)*10000)
    except (KeyError, ValueError, TypeError, OverflowError):
        pass
    return result


def gate(metrics, *, age_seconds, sizes_required, max_spread_bps):
    if not metrics['quote_present']:
        return 'MISSING'
    if not metrics['valid']:
        return 'INVALID'
    if metrics['age_seconds'] > age_seconds:
        return 'STALE'
    if sizes_required and not metrics['sizes_valid']:
        return 'INVALID_SIZE'
    if metrics['spread_bps'] > max_spread_bps:
        return 'WIDE'
    return 'PASS'


def freeze(root, args):
    from common.market_calendar import get_market_calendar
    from common.universe_files import load_universe_file_symbols
    from database.connection import get_sqlalchemy_engine
    from modelFactory.oracle_path.predict import load_contract
    from risk_management.liquidity import LiquidityGate

    cutoff = datetime.now(UTC)
    root.mkdir(parents=True, exist_ok=False)
    (root/'raw').mkdir()
    symbols = load_universe_file_symbols('universe-file:' + UNIVERSE.as_posix())
    model_root, protocol, profile, folds = load_contract('artifacts/models', args.batch_id)
    profile_sha = digest(model_root/'feature_profile.json')
    engine = get_sqlalchemy_engine()
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database alpha_trade required')
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET SESSION time_zone='+00:00'")
            conn.exec_driver_sql('START TRANSACTION READ ONLY')
            scores = pd.read_sql(text('''SELECT p.prediction_date,p.symbol,p.proba_extreme,p.fold_start,
                p.created_at prediction_created_at,l.fold_start lineage_fold_start,l.created_at lineage_created_at,
                l.model_available_date,l.model_sha256,l.feature_profile_sha256,l.target_name,l.target_horizon
                FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l
                ON p.prediction_date=l.prediction_date AND p.symbol=l.symbol AND p.batch_id=l.batch_id
                WHERE p.batch_id=:batch AND p.prediction_date BETWEEN :start AND :end
                ORDER BY p.prediction_date,p.proba_extreme DESC,p.symbol ASC'''), conn,
                params=dict(batch=args.batch_id, start=date.fromisoformat(args.since), end=cutoff.date()))
            conn.rollback()
    finally:
        engine.dispose()
    scores = scores[scores.symbol.isin(symbols)].copy()
    if scores.empty or scores.duplicated(['prediction_date', 'symbol']).any():
        raise ValueError('Oracle scores empty or duplicated')
    if not (np.isfinite(scores.proba_extreme) & scores.proba_extreme.between(0, 1)).all():
        raise ValueError('Invalid Oracle scores')
    for row in scores.to_dict('records'):
        fold_day = str(pd.Timestamp(row['fold_start']).date())
        fold = folds[fold_day]
        available = max(pd.Timestamp(fold['metrics'][k]) for k in ('train_available_max', 'val_available_max'))
        signal = pd.Timestamp(row['prediction_date'])
        if (not available < signal or pd.Timestamp(row['model_available_date']) != available.normalize()
                or pd.Timestamp(row['lineage_fold_start']) != pd.Timestamp(row['fold_start'])
                or row['target_name'] != 'oracle_path_extreme20' or row['target_horizon'] != 20
                or row['model_sha256'] != fold['model_sha256'] or row['feature_profile_sha256'] != profile_sha):
            raise ValueError('Oracle lineage incompatible or noncausal')
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    coverage, selected = [], []
    for day, frame in scores.groupby('prediction_date', sort=True):
        following = [s for s in cal.sessions(day, day+timedelta(days=10)) if s.is_open and s.session_date > day]
        if not following:
            raise ValueError('Missing next official session')
        session = following[0]
        observed = all(utc(r[k]) < session.open_at_utc for r in frame.to_dict('records')
                       for k in ('prediction_created_at', 'lineage_created_at'))
        eligible = session.close_at_utc < cutoff-timedelta(minutes=15) and observed and len(frame) >= 50
        coverage.append(dict(signal_day=day, quote_day=session.session_date, scores=len(frame),
            universe_size=len(symbols), coverage=len(frame)/len(symbols),
            original_model_min_coverage=protocol['min_daily_coverage'],
            score_observed_before_open=observed, eligible=eligible))
        if not eligible:
            continue
        frame = frame.sort_values(['proba_extreme', 'symbol'], ascending=[False, True]).head(50)
        for rank, row in enumerate(frame.to_dict('records'), 1):
            for slot in SLOTS:
                at = {'open_plus_5m': session.open_at_utc+timedelta(minutes=5),
                      'open_plus_150m': session.open_at_utc+timedelta(minutes=150),
                      'close_minus_5m': session.close_at_utc-timedelta(minutes=5)}[slot]
                selected.append(dict(symbol=row['symbol'], oracle_rank=rank,
                    signal_day=str(day), quote_day=str(session.session_date), slot=slot,
                    opening=session.open_at_utc.isoformat(), at=at.isoformat(),
                    oracle_score=float(row['proba_extreme'])))
    if not selected:
        raise ValueError('No prior Oracle TOP50 with auditable following closed session')
    scores.to_parquet(root/'oracle_scores.parquet', index=False)
    sources = [Path(__file__), Path('tests/test_us_oracle_iex_sip_quote_audit.py'), UNIVERSE,
               Path('config.yaml'), model_root/'protocol.json', model_root/'feature_profile.json', model_root/'report.json']
    plan = dict(schema_version=1, created_at_utc=cutoff.isoformat(), batch_id=args.batch_id,
        account_id=args.account, source_hashes={str(p): digest(p) for p in sources},
        archive_hashes={'oracle_scores.parquet': digest(root/'oracle_scores.parquet')},
        universe=str(UNIVERSE), universe_size=len(symbols), coverage=coverage, cases=selected,
        max_requests=2*len(selected), interval_seconds=args.interval,
        max_spread_bps=LiquidityGate().max_spread_bps, scenarios=SCENARIOS,
        rank_rule='Existing Oracle score descending, symbol ascending; no post-event filtering',
        mapping='Signal J to next official US session; quotes as of fixed regular-session instants',
        sql_read_only=True, SQL_writes=False, economic_backtest=False, model_inference=False,
        current_quote_spread_check_enabled=False,
        limitations=['Only dates with stored pre-open Oracle and a completed next session.',
                    'Existing score coverage is recorded; TOP50 of available scores, not a claim of full-universe completeness.',
                    'Counterfactual quote guard only; no portfolio/fills/returns or new-trading permission.',
                    'Repeated dates/times/symbols are correlated; no independence or live latency certification.',
                    'IEX audit requests do not change production feed requirements.'])
    save(root/'plan.json', plan)
    return plan


def collect(root, plan):
    from common.verified_http import verified_session
    from service.alpaca.clientAlpaca import get_alpaca_credentials
    from service._http_retry import RetryPolicy, request_with_retry
    key, secret = get_alpaca_credentials(plan['account_id'])
    headers = {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}
    total = plan['max_requests']
    done, calls, halt = 0, 0, None
    with verified_session() as client:
        for case in plan['cases']:
            for feed in ('iex', 'sip'):
                signature = json.dumps([case['symbol'], case['at'], feed], separators=(',', ':'))
                name = hashlib.sha256(signature.encode()).hexdigest() + '.json'
                target = root/'raw'/name
                if target.exists():
                    done += 1
                    continue
                # Bounded pacing; same cutoff and symbol on each feed, never latest/current.
                time.sleep(plan['interval_seconds'])
                params = dict(start=case['opening'], end=case['at'], feed=feed, sort='desc', limit=1, asof='-')
                endpoint = f"https://data.alpaca.markets/v2/stocks/{case['symbol']}/quotes"
                evidence = dict(symbol=case['symbol'], at=case['at'], feed=feed, params=params,
                                endpoint=endpoint, queried_at_utc=datetime.now(UTC).isoformat())
                try:
                    response = request_with_retry(client, 'GET', endpoint, headers=headers, params=params,
                        policy=RetryPolicy(max_attempts=3, timeout_seconds=15, base_delay_seconds=5, max_delay_seconds=60))
                    calls += 1
                    evidence.update(http_status=response.status_code, payload=response.json(),
                        quota_headers={k: response.headers.get(k) for k in
                            ('X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset')})
                except Exception as exc:
                    calls += 1
                    status = getattr(getattr(exc, 'response', None), 'status_code', None)
                    evidence.update(http_status=status, error_type=type(exc).__name__)
                    if status in (401, 403, 429) or status is None:
                        halt = dict(reason='Provider access/quota/network error; no fallback', http_status=status,
                                    error_type=type(exc).__name__, symbol=case['symbol'], feed=feed)
                save(target, evidence)
                done += 1
                save(root/'progress.json', dict(status='RUNNING' if halt is None else 'HALTED', completed=done,
                    total=total, logical_calls_this_process=calls, last_symbol=case['symbol'], last_feed=feed,
                    updated_at_utc=datetime.now(UTC).isoformat(), halt=halt))
                if done % 20 == 0 or halt:
                    print(f"Quotes audit {done}/{total} {case['quote_day']} {case['slot']} {case['symbol']} {feed}", flush=True)
                if halt:
                    return halt
    return None


def stats(values):
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    return dict(n=len(series), **{k: float(series.quantile(q)) if len(series) else None
        for k, q in [('median', .5), ('p90', .9), ('p95', .95), ('max', 1)]})


def summarize(root, plan, halt=None):
    pairs, raw_hashes = [], {}
    errors = []
    for case in plan['cases']:
        pair = dict(case)
        at, opening = utc(case['at']), utc(case['opening'])
        for feed in ('iex', 'sip'):
            signature = json.dumps([case['symbol'], case['at'], feed], separators=(',', ':'))
            path = root/'raw'/(hashlib.sha256(signature.encode()).hexdigest()+'.json')
            evidence = read(path) if path.exists() else {}
            if path.exists():
                raw_hashes[str(path.relative_to(root))] = digest(path)
            status = evidence.get('http_status')
            if status != 200:
                errors.append(dict(symbol=case['symbol'], at=case['at'], feed=feed, http_status=status,
                                   error_type=evidence.get('error_type', 'NOT_REQUESTED')))
                pair[feed+'_status'] = 'TECHNICAL_ERROR'
                quote = None
            else:
                payload = evidence.get('payload')
                rows = payload.get('quotes') if isinstance(payload, dict) else 'INVALID'
                if rows is None:
                    rows = []
                if not isinstance(rows, list) or len(rows) > 1 or any(not isinstance(r, dict) for r in rows):
                    errors.append(dict(symbol=case['symbol'], at=case['at'], feed=feed, error_type='MALFORMED_PAYLOAD'))
                    pair[feed+'_status'] = 'TECHNICAL_ERROR'
                    quote = None
                else:
                    quote = rows[0] if rows else None
                    pair[feed+'_status'] = 'RECEIVED' if quote else 'NO_QUOTE'
            metrics = quote_metrics(quote, at, opening)
            pair.update({feed+'_'+k: v for k, v in metrics.items()})
            for scenario, (age, sizes) in plan['scenarios'].items():
                pair[feed+'_'+scenario] = ('TECHNICAL_ERROR' if pair[feed+'_status'] == 'TECHNICAL_ERROR' else
                    gate(metrics, age_seconds=age, sizes_required=sizes, max_spread_bps=plan['max_spread_bps']))
        pairs.append(pair)
    frame = pd.DataFrame(pairs)
    frame.to_csv(root/'pairs.csv', index=False)
    groups = {}
    for n in (10, 20, 50):
        group = frame[frame.oracle_rank <= n]
        scenarios = {}
        for scenario in plan['scenarios']:
            i, s = group['iex_'+scenario], group['sip_'+scenario]
            known = ~i.eq('TECHNICAL_ERROR') & ~s.eq('TECHNICAL_ERROR')
            both_fresh = known & group.iex_valid & group.sip_valid & group.iex_age_seconds.le(plan['scenarios'][scenario][0]) & group.sip_age_seconds.le(plan['scenarios'][scenario][0])
            scenarios[scenario] = dict(comparable_cases=int(known.sum()),
                iex_status_counts=i.value_counts().to_dict(), sip_status_counts=s.value_counts().to_dict(),
                both_pass=int((known & i.eq('PASS') & s.eq('PASS')).sum()),
                iex_refuses_sip_passes=int((known & ~i.eq('PASS') & s.eq('PASS')).sum()),
                iex_passes_sip_refuses=int((known & i.eq('PASS') & ~s.eq('PASS')).sum()),
                both_refuse=int((known & ~i.eq('PASS') & ~s.eq('PASS')).sum()),
                iex_refusals_among_sip_pass_pct=(100*int((known & ~i.eq('PASS') & s.eq('PASS')).sum())/int((known & s.eq('PASS')).sum()) if (known & s.eq('PASS')).any() else None),
                both_fresh=int(both_fresh.sum()),
                excess_spread_bps=stats((group.loc[both_fresh, 'iex_spread_bps']-group.loc[both_fresh, 'sip_spread_bps']).tolist()),
                abs_mid_difference_bps=stats((10000*(group.loc[both_fresh, 'iex_mid']-group.loc[both_fresh, 'sip_mid']).abs()/group.loc[both_fresh, 'sip_mid']).tolist()))
        groups['TOP'+str(n)] = dict(cases=len(group), symbols=int(group.symbol.nunique()),
            sessions=int(group.quote_day.nunique()), scenarios=scenarios,
            spread_bps={feed: stats(group.loc[group[feed+'_valid'], feed+'_spread_bps'].tolist()) for feed in ('iex', 'sip')},
            age_seconds={feed: stats(group[feed+'_age_seconds'].tolist()) for feed in ('iex', 'sip')})
    frame[frame.iex_risk.ne('PASS') & frame.sip_risk.eq('PASS')].sort_values(
        ['oracle_rank', 'quote_day', 'slot']).to_csv(root/'iex_additional_refusals.csv', index=False)
    status = 'COMPLETED' if not errors and halt is None else 'PARTIAL_FAILED'
    report = dict(status=status, completed_at_utc=datetime.now(UTC).isoformat(),
        batch_id=plan['batch_id'], cases=len(frame), archived_requests=len(raw_hashes),
        expected_requests=plan['max_requests'], errors=errors, halt=halt, groups=groups,
        per_date={str(d): {feed: frame.loc[frame.quote_day.eq(d), feed+'_winner'].value_counts().to_dict()
            for feed in ('iex', 'sip')} for d in sorted(frame.quote_day.unique())},
        per_slot={slot: {feed: frame.loc[frame.slot.eq(slot), feed+'_winner'].value_counts().to_dict()
            for feed in ('iex', 'sip')} for slot in SLOTS},
        limitations=plan['limitations'], no_production_change=True)
    save(root/'report.json', report)
    save(root/'progress.json', dict(status=status, completed=len(raw_hashes), total=plan['max_requests'], halt=halt))
    save(root/'seal.json', dict(files={**raw_hashes, **{name: digest(root/name) for name in
        ['plan.json', 'oracle_scores.parquet', 'pairs.csv', 'iex_additional_refusals.csv', 'report.json']}}))
    print(json.dumps(dict(status=status, output=str(root), cases=len(frame), groups=groups), default=str), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--batch-id', default=DEFAULT_BATCH)
    parser.add_argument('--since', default='2026-10-01')
    parser.add_argument('--account', default='default')
    parser.add_argument('--interval', type=float, default=.6)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval < .4:
        parser.error('Minimum 0.4 second between logical requests')
    root = Path(args.output)
    if args.resume or args.summarize_only:
        plan = read(root/'plan.json')
        for name, sha in {**plan['source_hashes'], **{str(root/k): v for k, v in plan['archive_hashes'].items()}}.items():
            if digest(name) != sha:
                raise ValueError('Frozen input changed: '+name)
    else:
        plan = freeze(root, args)
    halt = None if args.summarize_only else collect(root, plan)
    report = summarize(root, plan, halt)
    return 0 if report['status'] == 'COMPLETED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
