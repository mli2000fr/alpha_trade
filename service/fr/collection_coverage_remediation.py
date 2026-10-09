"""Read-only FR SQL/files coverage audit and bounded licensed EODHD recheck.

No SQL writes, canonical promotion, broker calls or scheduled-task changes.
Rechecks archive new observations separately; they do not overwrite collectors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import text

from common.market_calendar import get_market_calendar
from database.router import get_market_engine
from service.fr.eodhd_daily_15b import atomic, symbols_from_identities
from service.fr.load_eodhd_staging import classify_bar

ROOT = Path(__file__).resolve().parents[2]
TABLES = ('stock_bars_daily', 'fr_provider_bars_staging', 'fr_provider_bars_daily',
          'fr_corporate_actions', 'fr_provider_actions_staging', 'fr_raw_payloads',
          'instruments', 'market_sessions')
TARGETS = ('LHYFE.PA', 'PERR.PA', 'ALBOU.PA', 'ARTO.PA', 'MLCHE.PA', 'MLNMA.PA')


def coverage(symbols, sessions, observed):
    """Provider records are presence, not tradability or independent proof."""
    details = []
    for symbol in symbols:
        seen = set(observed.get(symbol, ()))
        missing = [str(d) for d in sessions if str(d) not in seen]
        details.append({'symbol': symbol, 'present': len(sessions)-len(missing),
                        'missing_sessions': missing})
    expected = len(symbols)*len(sessions)
    present = sum(r['present'] for r in details)
    return {'symbols': len(symbols), 'sessions': [str(d) for d in sessions],
            'expected_symbol_sessions': expected, 'present_symbol_sessions': present,
            'coverage_pct': 100*present/expected if expected else None,
            'missing': [r for r in details if r['missing_sessions']],
            'tradability_inferred': False}


def audit_sql(conn, symbols, sessions):
    if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade_fr':
        raise ValueError('FR audit refuses another database')
    result = {'database': 'alpha_trade_fr', 'sql_writes': False, 'tables': {}}
    for name in TABLES:
        result['tables'][name] = {'rows': conn.execute(text(f'SELECT COUNT(*) FROM {name}')).scalar()}
    for name in TABLES[:3]:
        row = conn.execute(text(f'SELECT MIN(session_date) AS first_day, MAX(session_date) AS last_day FROM {name}')).mappings().one()
        result['tables'][name].update(dict(row))
    rows = conn.execute(text('''SELECT provider_symbol,session_date,COUNT(*) AS versions
        FROM fr_provider_bars_staging WHERE provider='EODHD'
        AND session_date BETWEEN :start AND :end GROUP BY provider_symbol,session_date'''),
        {'start': sessions[0], 'end': sessions[-1]}).mappings().all()
    observed = {}
    for row in rows:
        observed.setdefault(row['provider_symbol'], set()).add(str(row['session_date']))
    result['staging_presence'] = coverage(symbols, sessions, observed)
    result['multiple_version_keys'] = sum(row['versions'] > 1 for row in rows)
    result['extra_versions'] = sum(row['versions']-1 for row in rows)
    result['version_note'] = 'Distinct raw_payload_id versions are not automatically business duplicates'
    result['staging_quality'] = [dict(r) for r in conn.execute(text('''SELECT quality_code,COUNT(*) AS rows_count
        FROM fr_provider_bars_staging WHERE session_date BETWEEN :start AND :end
        GROUP BY quality_code'''), {'start': sessions[0], 'end': sessions[-1]}).mappings()]
    daily = [dict(r) for r in conn.execute(text('''SELECT b.* FROM fr_provider_bars_staging b
        JOIN fr_raw_payloads p ON p.raw_payload_id=b.raw_payload_id
        WHERE p.provider='EODHD' AND p.dataset='eod_daily'
        AND b.session_date BETWEEN :start AND :end
        ORDER BY b.provider_symbol,b.session_date,b.raw_payload_id'''),
        {'start':sessions[0],'end':sessions[-1]}).mappings()]
    result['daily_staging_snapshot'] = {'rows':len(daily),
        'sha256':hashlib.sha256(json.dumps(daily,sort_keys=True,default=str).encode()).hexdigest(),
        'includes_values_and_original_timestamps':True}
    return result


def audit_files(symbols, sessions, *, root=ROOT, daily_root=None):
    observed = {}; malformed = []; retained = []
    daily_root = daily_root or root/'artifacts/fr/operations/eodhd_daily'
    latest = daily_root/'latest'
    for symbol in symbols:
        path = latest/(hashlib.sha256(symbol.encode()).hexdigest()+'.json')
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload.get('market_code') != 'FR_EQ' or payload.get('symbol') != symbol:
            malformed.append(symbol); continue
        reserve = payload.get('last_coverage', {}).get('retained_old_rows_not_reconfirmed', [])
        retained.extend({'symbol': symbol, 'date': d} for d in reserve if d in {str(s) for s in sessions})
        for day, record in payload.get('bars', {}).items():
            if day not in {str(d) for d in sessions}:
                continue
            try:
                parsed, quality, _ = classify_bar(record['row'], set(sessions))
                stamp = datetime.fromisoformat(record['available_at'])
                raw = daily_root/'raw'/f"{record['raw_sha256']}.json"
                if (str(parsed) != day or quality not in ('VALID', 'ZERO_VOLUME')
                        or stamp.tzinfo is None or not raw.exists()
                        or hashlib.sha256(raw.read_bytes()).hexdigest() != record['raw_sha256']):
                    raise ValueError('Invalid evidence')
                original = json.loads(raw.read_text(encoding='utf-8'))
                if original.get('symbol') != symbol or record['row'] not in original.get('rows', []):
                    raise ValueError('Row absent from referenced raw payload')
            except (ValueError, KeyError, TypeError):
                malformed.append(f'{symbol}/{day}'); continue
            observed.setdefault(symbol, set()).add(day)
    result = coverage(symbols, sessions, observed)
    result['malformed_or_unverifiable'] = malformed
    result['retained_rows_not_reconfirmed'] = retained
    unconfirmed = sum(r['date'] in observed.get(r['symbol'], ()) for r in retained)
    result['current_response_confirmed_symbol_sessions'] = result['present_symbol_sessions']-unconfirmed
    denominator = result['expected_symbol_sessions']
    result['current_response_confirmed_coverage_pct'] = 100*(result['present_symbol_sessions']-unconfirmed)/denominator if denominator else None
    result['scope'] = 'LOCAL_PROVIDER_FILES_NOT_SQL_NOT_INDEPENDENT_PRICE_PROOF'
    return result


def dila_reserves(*, root=ROOT):
    directory = root/'artifacts/fr/operations/fr_dila_disclosures_sync'
    findings = []
    for path in sorted((directory/'quarantine').glob('*.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        for row in payload.get('rejected', []):
            from service.fr.event_data_qualification_11b import public_day
            findings.append({'raw_sha256': path.stem,
                             'identifier_present': bool(row.get('uin_idt_uin')),
                             'publication_day': public_day(row),
                             'isin': row.get('identificationsociete_iso_cd_isi')})
    return findings


def recheck(output, sessions):
    from service.fr.eodhd_backfill import _fetch
    token = os.environ.get('EODHD_API_TOKEN')
    if not token:
        raise ValueError('EODHD_API_TOKEN absent')
    findings = []
    for symbol in TARGETS:
        try:
            rows = _fetch('eod/'+quote(symbol, safe='.'), token,
                          {'from': str(sessions[0]), 'to': str(sessions[-1]), 'period': 'd'}, pace=.5)
            observed = datetime.now(UTC).isoformat()
            atomic(output/(symbol+'.json'), {'symbol': symbol, 'rows': rows,
                   'observed_at': observed, 'available_at': observed,
                   'scope': 'NEW_PROVIDER_OBSERVATION_NOT_HISTORICAL_PIT'})
            accepted = []; rejected = []
            for row in rows:
                day, quality, _ = classify_bar(row, set(sessions))
                if quality in ('VALID', 'ZERO_VOLUME'):
                    accepted.append(str(day))
                else:
                    rejected.append({'date': str(day), 'quality': quality})
            findings.append({'symbol': symbol, 'received': len(rows), 'accepted_days': accepted,
                             'missing_sessions': [str(d) for d in sessions if str(d) not in accepted],
                             'rejected': rejected, 'observed_at': observed})
        except Exception as exc:
            # Never expose arbitrary exception text or signed URLs.
            findings.append({'symbol': symbol, 'error_type': type(exc).__name__})
        atomic(output/'progress.json', {'completed': len(findings), 'total': len(TARGETS), 'findings': findings})
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, default=date(2026, 10, 2))
    parser.add_argument('--end', type=date.fromisoformat, default=date(2026, 10, 8))
    parser.add_argument('--recheck-provider', action='store_true')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to((ROOT/'artifacts/fr/research').resolve()):
        raise ValueError('Audit output outside FR research')
    sessions = get_market_calendar('FR_EQ').session_dates(args.start, args.end)
    if not sessions or (args.end-args.start).days > 31:
        raise ValueError('Nonempty bounded session window required')
    output.mkdir(parents=True, exist_ok=False)
    symbols = symbols_from_identities(ROOT/'artifacts/fr/sprint6c_reference/identities.jsonl.gz')
    engine = get_market_engine('FR_EQ', database_alias='fr_primary')
    try:
        with engine.connect() as conn:
            # MySQL transaction is explicitly read-only, including future edits.
            conn.execute(text('SET TRANSACTION READ ONLY'))
            sql = audit_sql(conn, symbols, sessions)
            conn.rollback()
    finally:
        engine.dispose()
    report = {'market_code': 'FR_EQ', 'observed_at': datetime.now(UTC).isoformat(),
              'sql': sql, 'files': audit_files(symbols, sessions),
              'canonical_promotion': False, 'trading_enabled': False,
              'dila_quarantine': dila_reserves()}
    if args.recheck_provider:
        report['provider_recheck'] = recheck(output, sessions)
    atomic(output/'report.json', report)
    print('Audit FR terminé : '+str(output/'report.json'))


if __name__ == '__main__':
    main()
