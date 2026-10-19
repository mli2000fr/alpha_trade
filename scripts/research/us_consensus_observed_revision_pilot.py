"""Received-snapshot changes, not reconstructed historical analyst consensus.

READ ONLY snapshot/proofs, offline pairing and fail-closed qualification. No
returns, LLM, provider request, training, SQL update or production change.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from scripts.research import us_directional_information_readiness as inventory
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from service.eodhd.consensus_snapshot import FIELDS, number
from service.eodhd.symbols import to_eodhd

PARENT = Path('artifacts/research/us_directional_information/20261019-v2')
BATCH = 'model-factory-20261016180250-3b0515'
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
GOOD_STATUSES = {'QUALIFIED', 'VALIDATED', 'PROSPECTIVE_QUALIFIED'}


def payload_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def utc(value):
    if value is None or pd.isna(value): return None
    stamp = pd.Timestamp(value)
    return stamp.tz_localize('UTC') if stamp.tzinfo is None else stamp.tz_convert('UTC')


def row_checks(row, runs):
    reasons = []
    try:
        raw = json.loads(row['raw_payload_json'])
        if payload_hash(raw) != row['raw_hash']: reasons.append('RAW_HASH_MISMATCH')
        if (raw.get('code') != to_eodhd(row['symbol']) or str(raw.get('date')) != str(row['fiscal_period_end'])[:10]
                or raw.get('period') != row['horizon_raw']): reasons.append('RAW_IDENTITY_MISMATCH')
        for field, native in FIELDS.items():
            a = number(raw.get(native)); b = row.get(field)
            b = None if b is None or pd.isna(b) else float(b)
            if (a is None) != (b is None) or (a is not None and not np.isclose(a, b, rtol=0, atol=1e-10)):
                reasons.append('NORMALIZED_VALUE_MISMATCH:'+field)
    except (ValueError, TypeError, KeyError):
        reasons.append('INVALID_RAW_ITEM')
    run = runs.get(row['run_id'])
    observed, available, ingested = [utc(row.get(k)) for k in ['observed_at', 'available_at', 'ingestion_at']]
    finished = utc(run.get('finished_at')) if run else None
    if run is None or run.get('status') != 'COMPLETED' or finished is None:
        reasons.append('RUN_NOT_COMPLETED')
    if observed is None or available is None or ingested is None or available < observed:
        reasons.append('INVALID_RECEIPT_TIMESTAMPS')
    if finished is not None and observed is not None and finished < observed:
        reasons.append('RUN_FINISHED_BEFORE_RECEIPT')
    for metric in ['eps', 'revenue']:
        lo, avg, hi = [row.get(metric+'_'+suffix) for suffix in ['low', 'avg', 'high']]
        lo, avg, hi = [None if x is None or pd.isna(x) else float(x) for x in [lo, avg, hi]]
        if ((lo is not None and hi is not None and lo > hi)
            or (lo is not None and avg is not None and avg < lo)
            or (hi is not None and avg is not None and avg > hi)):
            reasons.append('INCONSISTENT_'+metric.upper()+'_RANGE')
    timestamps = [x for x in [observed, available, ingested, finished] if x is not None]
    conservative = max(timestamps) if len(timestamps) == 4 else None
    return dict(technical_reasons=reasons, technically_consistent=not reasons,
                conservative_available_at=conservative)


def change(old, new):
    if old is None or new is None or pd.isna(old) or pd.isna(new):
        return None, None
    old, new = float(old), float(new)
    if not np.isfinite([old, new]).all(): return None, None
    delta = new-old
    return delta, delta/abs(old) if old != 0 else None


def pair_rows(frame, runs):
    keys = ['provider', 'symbol', 'fiscal_period_end', 'horizon_raw']
    if frame.duplicated(keys+['snapshot_date']).any(): raise ValueError('Duplicate logical snapshot')
    checks = {int(r['id']): row_checks(r, runs) for r in frame.to_dict('records')}
    pairs = []
    for _, group in frame.groupby(keys, sort=True):
        rows = group.sort_values(['snapshot_date', 'observed_at', 'id']).to_dict('records')
        for old, new in zip(rows, rows[1:]):
            a, b = checks[int(old['id'])], checks[int(new['id'])]
            gap = (utc(new['observed_at'])-utc(old['observed_at'])).total_seconds()/86400
            reasons = list(dict.fromkeys(a['technical_reasons']+b['technical_reasons']))
            if not 0 < gap <= 3: reasons.append('SNAPSHOT_GAP_OVER_72H_OR_NONCAUSAL')
            before, after = a['conservative_available_at'], b['conservative_available_at']
            if before is None or after is None or not before < after:
                reasons.append('NONCAUSAL_AVAILABILITY')
            if not all(bool(r.get('fiscal_identity_qualified')) for r in [old, new]): reasons.append('FISCAL_IDENTITY_UNQUALIFIED')
            if not all(bool(r.get('units_qualified')) for r in [old, new]): reasons.append('UNITS_UNQUALIFIED')
            if any(r.get('qualification_status') not in GOOD_STATUSES for r in [old, new]): reasons.append('UPSTREAM_RESEARCH_ONLY')
            currencies = [r.get('currency') for r in [old, new]]
            if any(x is None or pd.isna(x) or not str(x).strip() for x in currencies): reasons.append('CURRENCY_UNKNOWN')
            elif currencies[0] != currencies[1]: reasons.append('CURRENCY_CHANGED')
            eps_delta, eps_ratio = change(old.get('eps_avg'), new.get('eps_avg'))
            rev_delta, rev_ratio = change(old.get('revenue_avg'), new.get('revenue_avg'))
            if eps_delta is None or rev_delta is None: reasons.append('MISSING_EPS_OR_REVENUE')
            if any(pd.isna(r.get(k)) or r.get(k) < 3 for r in [old, new] for k in ['eps_analyst_count', 'revenue_analyst_count']):
                reasons.append('ANALYST_COUNTS_MISSING_OR_LT3')
            if any(r is not None and abs(r) >= 9 for r in [eps_ratio, rev_ratio]): reasons.append('POSSIBLE_SCALE_JUMP')
            proposed = ('LONG' if eps_delta is not None and rev_delta is not None and eps_delta > 0 and rev_delta > 0
                else 'SHORT' if eps_delta is not None and rev_delta is not None and eps_delta < 0 and rev_delta < 0
                else 'ABSTAIN')
            pairs.append(dict(pair_id=f"{old['id']}:{new['id']}", symbol=new['symbol'],
                fiscal_period_end=new['fiscal_period_end'], horizon_raw=new['horizon_raw'],
                old_id=int(old['id']), new_id=int(new['id']), old_snapshot_date=old['snapshot_date'], new_snapshot_date=new['snapshot_date'],
                old_available_at=before, available_at=after, gap_days=gap,
                old_eps=old.get('eps_avg'), new_eps=new.get('eps_avg'), eps_delta=eps_delta, eps_change_ratio=eps_ratio,
                old_revenue=old.get('revenue_avg'), new_revenue=new.get('revenue_avg'), revenue_delta=rev_delta, revenue_change_ratio=rev_ratio,
                numeric_pattern=proposed, technical_pair=a['technically_consistent'] and b['technically_consistent'] and 0 < gap <= 3
                    and before is not None and after is not None and before < after,
                qualification_reasons=sorted(set(reasons)), qualified_before_receipt_check=not reasons,
                direction='ABSTAIN' if reasons else proposed))
    return pd.DataFrame(pairs), checks


def prepare(root):
    if (root/'protocol.json').exists():
        p = READ(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    if root.exists(): raise ValueError('Fresh directory required')
    verify_hashes(PARENT, READ(PARENT/'inventory-seal.json')['files'])
    inv = READ(PARENT/'inventory.json'); old = READ(PARENT/'protocol.json')
    files = [Path(__file__), Path('tests/test_us_consensus_observed_revision_pilot.py'),
        Path('service/eodhd/consensus_snapshot.py'), Path('database/repositories/eodhd_consensus.py'),
        PARENT/'protocol.json', PARENT/'inventory.json', PARENT/'inventory-seal.json', inventory.UNIVERSE,
        Path(f'artifacts/models/{BATCH}/oracle_path/protocol.json')]
    root.mkdir(parents=True)
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), inventory=str(PARENT),
        sources={str(f): digest(f) for f in files}, symbols=old['symbols'], cutoff_utc=inv['finished_at_utc'],
        snapshot_start='2026-10-11', snapshot_end='2026-10-18',
        fiscal_export_start='2026-06-13', fiscal_export_end='2027-11-22', max_rows=200000,
        primary='New aggregate EPS AND revenue changes agree between actual received adjacent snapshots of same provider/symbol/fiscal-end/raw-horizon. Not rolling 7/30/90d values backdated.',
        signal='Both strictly up: LONG; both strictly down: SHORT; mixed, unchanged, missing or unqualified: ABSTAIN. No amplitude threshold search.',
        requirements='Same verified fiscal identity, currency, units, comparable estimate definition; >=3 EPS AND revenue analysts at BOTH ends; no scale discontinuity; completed runs, normalized/raw item hash and source envelope verified.',
        observed_pair='At most72h between adjacent actual observed snapshots; no bridge across fiscal/raw-horizon changes; never treat observation date as fiscal end or old estimate vintage.',
        availability='Conservative max(row observed/available/ingestion, parent run finished); both snapshots strictly before entry. Source timestamps do not certify all original analyst publication times.',
        primary_scope='Exact latest current H20-path Oracle batch/date from inventory, first10 ranks over current tradable universe before feature/outcome filtering, stable symbol ties; no GPT filter or replacement.',
        oracle_batch=BATCH, prediction_date='2026-10-16', entry_cutoff_utc='2026-10-19T13:30:00+00:00',
        readiness_only=True, horizon_sessions=10, eventual_primary_target='First TP10% before SL5% in10 sessions, entry next open; same-bar ambiguity loss-first; absent hit remains distinct expiry. No PnL until qualified features/paths and independent sample.',
        minimum_confirmation='At least50 distinct entry sessions and100 non-overlapping qualified TOP10 episodes; next unseen periods, never label this already viewed 8-day pilot independent confirmation.',
        current_period='Raw horizon labels repeat across old fiscal ends. Keep period-level pairs, do not guess current quarter or collapse ambiguous periods into one direction per stock.',
        proof_sample='Before any returns: all latest near-period pairs for TOP10 before entry; first20 changed issuers and10 unchanged witnesses sorted symbol/fiscal/horizon/IDs, one per issuer per sample. No outcome-based selection, no recall claim.',
        secondary_families='Guidance and earnings surprise readiness only. No replay of old failed extraction or surprise from mutable earnings calendar as if estimates were PIT.',
        forbidden=['SQL writes','provider/LLM calls','Yahoo restoration','new model training','production/batch changes','orders','price outcomes or PnL in readiness pilot'])
    atomic_json(root/'protocol.json', p)
    return p


def connect_readonly():
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade': raise ValueError('US only')
    conn = engine.connect()
    conn.execute(text("SET SESSION time_zone='+00:00'"))
    conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
    conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
    return engine, conn


def snapshot(root):
    p = prepare(root)
    if (root/'snapshot-ready.json').exists(): raise ValueError('Immutable snapshot')
    engine, conn = connect_readonly()
    params = dict(start=p['snapshot_start'], end=p['snapshot_end'], low=p['fiscal_export_start'], high=p['fiscal_export_end'],
                  cutoff=utc(p['cutoff_utc']).tz_localize(None).to_pydatetime())
    try:
        where = '''provider='eodhd' AND symbol IN :symbols AND snapshot_date BETWEEN :start AND :end
            AND fiscal_period_end BETWEEN :low AND :high AND observed_at<:cutoff AND available_at<:cutoff
            AND ingestion_at<:cutoff'''
        count = inventory.query(conn, 'SELECT COUNT(*) n FROM stock_analyst_consensus_eodhd_history WHERE '+where, p['symbols'], **params)[0]['n']
        if count > p['max_rows']: raise ValueError('Explicit size bound reached: partition before proceeding')
        rows = inventory.query(conn, 'SELECT * FROM stock_analyst_consensus_eodhd_history WHERE '+where+
            ' ORDER BY symbol,fiscal_period_end,horizon_raw,snapshot_date,id', p['symbols'], **params)
        pd.DataFrame(rows).to_parquet(root/'consensus.parquet', index=False)
        runs = inventory.query(conn, '''SELECT run_id,status,started_at,finished_at FROM pit_collection_runs
            WHERE batch_name='eodhd_consensus_snapshot' AND started_at<:cutoff''', cutoff=params['cutoff'])
        pd.DataFrame(runs).to_parquet(root/'runs.parquet', index=False)
        scores = inventory.query(conn, '''SELECT p.prediction_date,p.symbol,p.proba_extreme,p.fold_start,p.batch_id,p.created_at,
            l.target_name,l.target_horizon,l.model_available_date,l.model_sha256,l.feature_profile_sha256
            FROM oracle_extreme_predictions p JOIN oracle_path_prediction_lineage l
              ON p.batch_id=l.batch_id AND p.prediction_date=l.prediction_date AND p.symbol=l.symbol
            WHERE p.symbol IN :symbols AND p.batch_id=:batch AND p.prediction_date=:day''', p['symbols'], batch=p['oracle_batch'], day=p['prediction_date'])
        pd.DataFrame(scores).to_parquet(root/'oracle-scores.parquet', index=False)
        clock = inventory.query(conn, 'SELECT UTC_TIMESTAMP(6) clock_utc,NOW(6) clock_session')[0]
        conn.rollback()
    finally:
        conn.close(); engine.dispose()
    atomic_json(root/'snapshot-ready.json', dict(finished_at_utc=datetime.now(timezone.utc).isoformat(), rows=len(rows),
        scores=len(scores), sql='REPEATABLE READ / READ ONLY / UTC session / ROLLBACK', server_clock=clock,
        files={n: digest(root/n) for n in ['consensus.parquet', 'runs.parquet', 'oracle-scores.parquet']}))
    print('Read-only snapshot:', len(rows), 'forecast rows;', len(scores), 'scores', flush=True)


def build(root):
    p = prepare(root); verify_hashes(root, READ(root/'snapshot-ready.json')['files'])
    if (root/'pair-ready.json').exists(): raise ValueError('Immutable pairs')
    rows = pd.read_parquet(root/'consensus.parquet'); runs = {r['run_id']: r for r in pd.read_parquet(root/'runs.parquet').to_dict('records')}
    pairs, checks = pair_rows(rows, runs)
    for col in ['qualification_reasons']:
        pairs[col] = pairs[col].map(lambda x: json.dumps(x, sort_keys=True))
    pairs.to_parquet(root/'pairs.parquet', index=False)
    scores = pd.read_parquet(root/'oracle-scores.parquet')
    if scores.symbol.duplicated().any() or scores.empty: raise ValueError('Missing/duplicate Oracle universe')
    if not (scores.target_name.eq('oracle_path_extreme20') & scores.target_horizon.eq(20)).all(): raise ValueError('Wrong Oracle target')
    if not pd.to_datetime(scores.model_available_date).lt(pd.to_datetime(scores.prediction_date)).all(): raise ValueError('Model unavailable before signal')
    if not pd.to_datetime(scores.created_at, utc=True).lt(utc(p['entry_cutoff_utc'])).all(): raise ValueError('Oracle score unavailable before entry')
    top = scores.sort_values(['proba_extreme', 'symbol'], ascending=[False, True]).head(10).copy()
    top['oracle_rank'] = np.arange(1, len(top)+1); top.to_parquet(root/'oracle-top10.parquet', index=False)
    cohort = pairs[pairs.symbol.isin(top.symbol) & pd.to_datetime(pairs.available_at, utc=True).lt(utc(p['entry_cutoff_utc']))].copy()
    # Latest actual pair per exact period identity; do not collapse periods into a guessed current-quarter signal.
    cohort = cohort.sort_values(['available_at', 'new_id']).drop_duplicates(['symbol', 'fiscal_period_end', 'horizon_raw'], keep='last')
    cohort.to_parquet(root/'top10-period-pairs.parquet', index=False)
    changed = pairs[pairs.eps_delta.fillna(0).ne(0) | pairs.revenue_delta.fillna(0).ne(0)]
    unchanged = pairs[pairs.eps_delta.eq(0) & pairs.revenue_delta.eq(0)]
    sort = ['symbol', 'fiscal_period_end', 'horizon_raw', 'old_id', 'new_id']
    sample = pd.concat([changed.sort_values(sort).drop_duplicates('symbol').head(20),
        unchanged.sort_values(sort).drop_duplicates('symbol').head(10), cohort], ignore_index=True).drop_duplicates('pair_id')
    sample.to_parquet(root/'proof-sample.parquet', index=False)
    ids = sorted(set(sample.old_id) | set(sample.new_id))
    selected = rows[rows.id.isin(ids)]
    request = dict(pair_ids=sample.pair_id.tolist(), row_ids=ids,
        receipts=selected[['run_id', 'observed_at']].drop_duplicates().to_dict('records'),
        selection='Feature-only lexical sample and frozen TOP10 cohort; no future price or direction-label access')
    atomic_json(root/'proof-request.json', request)
    problems = {}
    for q in pairs.qualification_reasons:
        for reason in json.loads(q): problems[reason] = problems.get(reason, 0)+1
    result = dict(rows=len(rows), pairs=len(pairs), symbols=int(pairs.symbol.nunique()),
        snapshot_dates=sorted(str(x)[:10] for x in rows.snapshot_date.unique()),
        technical_pairs=int(pairs.technical_pair.sum()), numeric_patterns=pairs.numeric_pattern.value_counts().to_dict(),
        before_receipt_qualified=int(pairs.qualified_before_receipt_check.sum()), reasons=problems,
        proof_pairs=len(sample), proof_rows=len(selected), top10=top[['oracle_rank','symbol','proba_extreme']].to_dict('records'),
        top10_period_pairs=len(cohort), cohort_symbols=int(cohort.symbol.nunique()),
        files={n: digest(root/n) for n in ['pairs.parquet','oracle-top10.parquet','top10-period-pairs.parquet','proof-sample.parquet','proof-request.json']})
    atomic_json(root/'pair-ready.json', result)
    print({k: v for k, v in result.items() if k not in ('files', 'top10')}, flush=True)


def proofs(root):
    p = prepare(root); ready = READ(root/'pair-ready.json'); verify_hashes(root, ready['files'])
    if (root/'proof-ready.json').exists(): raise ValueError('Immutable proofs')
    request = READ(root/'proof-request.json')
    runids = sorted({r['run_id'] for r in request['receipts']})
    stamps = sorted({utc(r['observed_at']).tz_localize(None).to_pydatetime() for r in request['receipts']})
    from sqlalchemy import bindparam
    engine, conn = connect_readonly()
    try:
        stmt = text('''SELECT id,run_id,entity_key,observed_at,available_at,http_status,payload_hash,payload_json
            FROM pit_raw_payloads WHERE batch_name='eodhd_consensus_snapshot' AND provider='eodhd'
            AND endpoint='/calendar/trends' AND run_id IN :runs AND observed_at IN :stamps ORDER BY id''')
        stmt = stmt.bindparams(bindparam('runs', expanding=True), bindparam('stamps', expanding=True))
        rows = [dict(r) for r in conn.execute(stmt, dict(runs=runids, stamps=stamps)).mappings()]
        conn.rollback()
    finally:
        conn.close(); engine.dispose()
    pd.DataFrame(rows).to_parquet(root/'raw-proof-receipts.parquet', index=False)
    atomic_json(root/'proof-ready.json', dict(receipts=len(rows), requested_pairs=ready['proof_pairs'],
        finished_at_utc=datetime.now(timezone.utc).isoformat(), files={'raw-proof-receipts.parquet': digest(root/'raw-proof-receipts.parquet')}))
    print('Archived existing source envelopes:', len(rows), flush=True)


def finalize(root):
    p = prepare(root); ready = READ(root/'pair-ready.json'); verify_hashes(root, ready['files'])
    verify_hashes(root, READ(root/'snapshot-ready.json')['files']); verify_hashes(root, READ(root/'proof-ready.json')['files'])
    if (root/'report.json').exists(): raise ValueError('Immutable completed report')
    sample = pd.read_parquet(root/'proof-sample.parquet'); rows = pd.read_parquet(root/'consensus.parquet')
    proof = pd.read_parquet(root/'raw-proof-receipts.parquet')
    matching = {}; envelope_errors = []
    for r in proof.to_dict('records'):
        obj = json.loads(r['payload_json'])
        if r['http_status'] != 200 or payload_hash(obj) != r['payload_hash'] or utc(r['available_at']) < utc(r['observed_at']):
            envelope_errors.append(int(r['id'])); continue
        for group in obj.get('trends', []):
            for item in group:
                matching[(r['run_id'], utc(r['observed_at']), payload_hash(item))] = int(r['id'])
    requested = set(sample.old_id) | set(sample.new_id); receipt_checks = []
    for r in rows[rows.id.isin(requested)].to_dict('records'):
        match = matching.get((r['run_id'], utc(r['observed_at']), r['raw_hash']))
        receipt_checks.append(dict(row_id=int(r['id']), receipt_id=match, matched=match is not None))
    atomic_json(root/'receipt-checks.json', dict(rows=receipt_checks, bad_envelopes=envelope_errors,
        caveat='Only the explicit proof sample is envelope-qualified; no claim for all normalized rows or all issuer/fiscal/unit identities.'))
    top = pd.read_parquet(root/'oracle-top10.parquet')
    cohort = pd.read_parquet(root/'top10-period-pairs.parquet')
    matched_ids = {x['row_id'] for x in receipt_checks if x['matched']}
    qualified = sample[sample.qualified_before_receipt_check & sample.old_id.isin(matched_ids) & sample.new_id.isin(matched_ids)]
    qualified_signals = qualified[qualified.numeric_pattern.ne('ABSTAIN')]
    bysymbol = []
    for r in top.to_dict('records'):
        f = cohort[cohort.symbol.eq(r['symbol'])]
        verified = qualified_signals[qualified_signals.pair_id.isin(f.pair_id) & qualified_signals.horizon_raw.eq('0q')]
        direction = verified.numeric_pattern.iloc[0] if len(verified) == 1 else 'ABSTAIN'
        reasons = sorted({x for q in f.qualification_reasons for x in json.loads(q)})
        bysymbol.append(dict(symbol=r['symbol'], oracle_rank=int(r['oracle_rank']), period_pairs=len(f),
            direction=direction, status='NO_PERIOD_PAIR' if f.empty else 'QUALIFIED_SINGLE_PERIOD' if len(verified) == 1
                else 'QUALIFICATION_OR_CURRENT_PERIOD_UNRESOLVED', reasons=reasons,
            patterns=f.numeric_pattern.value_counts().to_dict()))
    report = dict(status='BLOCKED_QUALIFICATION_AND_INDEPENDENT_HISTORY_NOT_NEGATIVE_SIGNAL_RESULT' if len(qualified_signals) == 0
        else 'BOUNDED_QUALIFICATION_ONLY_INDEPENDENT_HISTORY_PENDING',
        completed='Read-only inventory, observed snapshot-pair construction, bounded raw-envelope checks and frozen TOP10 pack.',
        not_completed='Directional efficacy, historical H10 backtest and economic PnL; no qualified samples to evaluate.',
        pair_summary={k: v for k, v in ready.items() if k not in ('files', 'top10')},
        checked_receipt_rows=len(receipt_checks), matched_receipt_rows=sum(x['matched'] for x in receipt_checks),
        bad_envelopes=envelope_errors, qualified_signals=len(qualified_signals), top10=bysymbol,
        entry_cutoff_utc=p['entry_cutoff_utc'], earliest_primary_maturity='2026-10-30 after NYSE close, conditional on qualified completed price paths; not supplied by this pilot.',
        minimum_history_met=False, horizon_sessions=p['horizon_sessions'], new_performance_computed=False,
        guidance='No new qualified old/new metric-period-unit-basis pairs supplied; existing E21 extraction failure not relabelled as a signal.',
        surprise='Mutable earnings calendar has no preserved pre-announcement estimate vintage; no strict historical surprise reconstructed from it.',
        next_actions=['Validate exact current fiscal record, EPS/revenue definition and currency/scale for a bounded issuer set before signals.',
            'Preserve existing daily snapshots and source envelopes; do not backdate 7/30/90-day fields.',
            'Wait for target maturity AND independent dates, not merely a larger row count. Do not train or trade this numeric-pattern diagnostic.'],
        files={n: digest(root/n) for n in ['receipt-checks.json','oracle-top10.parquet','pairs.parquet','top10-period-pairs.parquet','proof-sample.parquet']},
        sql_writes=False, api_calls=0, model_changes=False, orders=False)
    atomic_json(root/'report.json', report)
    print(dict(status=report['status'], pairs=ready['pairs'], qualified=report['qualified_signals'],
        receipt_rows=len(receipt_checks), matched=report['matched_receipt_rows'], top10=bysymbol), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--phase', required=True,
        choices=['prepare','snapshot','build','proofs','finalize']); parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args(); {'prepare': prepare,'snapshot': snapshot,'build': build,'proofs': proofs,'finalize': finalize}[a.phase](a.output)


if __name__ == '__main__': main()
