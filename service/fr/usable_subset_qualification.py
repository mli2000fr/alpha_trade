"""Bounded FR subset audit: observed research inputs, never trading admission.

SQL is explicitly read-only. Existing feature and identity gates are reused;
provider collection coverage is not independent corporate-action proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.router import get_market_engine
from service.fr.collection_coverage_remediation import audit_files
from service.fr.eodhd_daily_15b import symbols_from_identities
from service.fr.daily_feature_adapter_16b import assemble, identity_resolution, master_at
from service.fr.prediction_contract_16a import ROOT, aware


def classify(identity, diagnostic, resolution, *, missing, retained, nonpositive,
             sql_missing, archive_errors):
    """Three levels of use; no count or vendor score can authorize shadow."""
    price_reasons = []
    if missing:
        price_reasons.append('MISSING_RECENT_PROVIDER_BARS')
    if retained:
        price_reasons.append('RECENT_PRICE_NOT_RECONFIRMED')
    if nonpositive:
        price_reasons.append('NONPOSITIVE_RECENT_VOLUME')
    if sql_missing:
        price_reasons.append('RECENT_BARS_NOT_AVAILABLE_IN_SQL_AT_AUDIT')
    if archive_errors:
        price_reasons.append('ARCHIVE_INTEGRITY_ERRORS')
    input_reasons = sorted(set(price_reasons + resolution['reasons'] +
                              diagnostic['reasons']))
    # Continuity remains a release gate, not proof of bad price-only features.
    provider_blocks = [r for r in input_reasons if r not in {
        'MASTER_CONTINUITY_UNQUALIFIED'}]
    price_ready = not price_reasons
    feature_ready = price_ready and diagnostic['features_computed'] and not provider_blocks
    return {'symbol': identity['provider_symbol'], 'isin': identity['isin'],
            'research_uid': identity['research_uid'], 'resolved_mic': resolution['mic'],
            'price_only_recent_panel_usable': price_ready,
            'observed_provider_feature_inputs_usable': feature_ready,
            'features_computed': diagnostic['features_computed'],
            'missing_recent_sessions': missing, 'not_reconfirmed_sessions': retained,
            'nonpositive_volume_sessions': nonpositive, 'sql_missing_sessions': sql_missing,
            'missing_warmup_sessions': diagnostic['missing_sessions'],
            'input_reserves': input_reasons,
            'independent_currency_and_actions_qualification': 'NOT_PROMOTED_BY_THIS_AUDIT',
            'shadow_eligible': False, 'orders_allowed': False,
            'release_reserves': ['INDEPENDENT_PRICE_CURRENCY_ACTIONS_AND_REFERENCE_REVIEW',
                                 'MODEL_NOT_RELEASED', 'OPERATIONAL_RELEASE_NOT_GRANTED']}


def run(output: Path, *, decision_day: date, bootstrap: Path, start: date):
    now = datetime.now(UTC)
    output = output.resolve()
    allowed = (ROOT/'artifacts/fr/research/usable_subset').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        raise ValueError('New FR usable_subset output directory required')
    calendar = get_market_calendar('FR_EQ', allow_us_weekday_fallback=False)
    if calendar.session(decision_day).open_at_utc > now:
        raise ValueError('Future decision forbidden')
    result = assemble(decision_day, bootstrap_dir=bootstrap)
    end = date.fromisoformat(result['report']['feature_session'])
    if start > end or (end-start).days > 31:
        raise ValueError('Recent window must be nonempty and bounded to 31 days')
    sessions = calendar.session_dates(start, end)
    identities = result['manifest']['universe']
    symbols = [r['provider_symbol'] for r in identities]
    collection_symbols = symbols_from_identities(ROOT/'artifacts/fr/sprint6c_reference/identities.jsonl.gz')
    files = audit_files(symbols, sessions)
    missing = {r['symbol']: r['missing_sessions'] for r in files['missing']}
    retained = {}
    for row in files['retained_rows_not_reconfirmed']:
        retained.setdefault(row['symbol'], []).append(row['date'])
    engine = get_market_engine('FR_EQ', database_alias='fr_primary')
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade_fr':
                raise ValueError('Wrong database')
            # This checks actual publication, not the provider collection time.
            sql_rows = conn.execute(text('''SELECT b.provider_symbol,b.session_date,
                b.available_at FROM fr_provider_bars_staging b
                JOIN fr_raw_payloads p ON p.raw_payload_id=b.raw_payload_id
                WHERE p.dataset='eod_daily' AND b.provider='EODHD'
                AND b.session_date BETWEEN :start AND :end
                AND b.available_at<=:cutoff'''),
                {'start': start, 'end': end, 'cutoff': now.replace(tzinfo=None)}).mappings().all()
            conn.rollback()
    finally:
        engine.dispose()
    sql_days = {}
    for row in sql_rows:
        sql_days.setdefault(row['provider_symbol'], set()).add(str(row['session_date']))
    proofs = {}
    master, master_reserves, master_errors = master_at(
        ROOT/'artifacts/fr/operations/fr_security_master_sync',
        aware(result['report']['decision_at']), end, ROOT, proofs)
    diagnostics = {r['symbol']: r for r in result['report']['diagnostics']}
    errors = bool(files['malformed_or_unverifiable'] or master_errors or
                  any(result['report']['archive_errors'].values()))
    rows = []
    for identity in identities:
        symbol = identity['provider_symbol']
        path = ROOT/'artifacts/fr/operations/eodhd_daily/latest'/(
            hashlib.sha256(symbol.encode()).hexdigest()+'.json')
        latest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        nonpositive = [str(day) for day in sessions
            if str(day) in latest.get('bars', {}) and
            float(latest['bars'][str(day)]['row'].get('volume') or 0) <= 0]
        rows.append(classify(identity, diagnostics[symbol], identity_resolution(master, identity, end),
            missing=missing.get(symbol, []), retained=retained.get(symbol, []),
            nonpositive=nonpositive,
            sql_missing=[str(d) for d in sessions if str(d) not in sql_days.get(symbol, set())],
            archive_errors=errors))
    reasons = Counter(r for row in rows for r in row['input_reserves'])
    report = {'schema_version': 1, 'market_code': 'FR_EQ', 'database': 'alpha_trade_fr',
        'status': 'BOUNDED_RESEARCH_SUBSET_SHADOW_NOT_RELEASED', 'audit_at': now.isoformat(),
        'decision_at': result['report']['decision_at'], 'feature_session': str(end),
        'recent_sessions': [str(d) for d in sessions],
        'warmup_sessions': result['report']['required_sessions'],
        'sql_presence_asof': now.isoformat(),
        'sql_presence_is_not_historical_decision_availability': True,
        'subset_is_audit_time_inventory_not_historical_selection': True,
        'universe_count': len(rows),
        'configured_collection_universe_count': len(collection_symbols),
        'price_only_recent_panel_count': sum(r['price_only_recent_panel_usable'] for r in rows),
        'observed_provider_feature_inputs_count': sum(r['observed_provider_feature_inputs_usable'] for r in rows),
        'features_computed_count': sum(r['features_computed'] for r in rows),
        'shadow_eligible_count': 0, 'input_reserve_counts': dict(sorted(reasons.items())),
        'xpar_observed_provider_feature_inputs_count': sum(
            r['observed_provider_feature_inputs_usable'] and r['resolved_mic']=='XPAR' for r in rows),
        'master_reserves': master_reserves, 'source_file_coverage': files,
        'sql_writes': False, 'training_launched': False, 'orders_allowed': False,
        'canonical_promotion': False, 'serving_enabled': False,
        'scope': 'RECENT_OBSERVED_INPUTS_NOT_2018_2026_HISTORICAL_OR_TRADABILITY_ADMISSION',
        'instruments': rows}
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in [('report', report), ('feature_assembly', result['report'])]:
        (output/(name+'.json')).write_text(json.dumps(payload, ensure_ascii=False, indent=2,
            allow_nan=False), encoding='utf-8')
    for name, subset in [('research_provider_inputs', [r for r in rows
            if r['observed_provider_feature_inputs_usable']]),
            ('research_provider_inputs_xpar', [r for r in rows
            if r['observed_provider_feature_inputs_usable'] and r['resolved_mic']=='XPAR'])]:
        (output/(name+'.json')).write_text(json.dumps({'market_code':'FR_EQ',
            'audit_at':now.isoformat(), 'serving_enabled':False,
            'historical_selection_allowed':False, 'instruments':subset},
            ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status','universe_count',
        'price_only_recent_panel_count','observed_provider_feature_inputs_count',
        'features_computed_count','shadow_eligible_count','input_reserve_counts')}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decision-date', type=date.fromisoformat, required=True)
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--bootstrap-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir, decision_day=args.decision_date, bootstrap=args.bootstrap_dir, start=args.start)


if __name__ == '__main__':
    main()
