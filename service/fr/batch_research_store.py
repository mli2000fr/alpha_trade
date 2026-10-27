"""FR operational archives in SQL, with typed research tables and no serving.

Original payloads remain intact. Missing availability is NULL, never file mtime.
Existing market-specific SQL publishers are not replaced by this archive mirror.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from service.fr.event_data_qualification_11b import parse_positions, public_day
from service.inpi.files import atomic

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / 'artifacts/fr/operations'
DOCUMENTS = 'fr_batch_research_documents'
FILES = 'fr_batch_research_file_versions'
TYPED = ('fr_calendar_sessions_research', 'fr_reference_versions_research',
         'fr_corporate_actions_research', 'fr_amf_positions_research', 'fr_dila_disclosures_research')
FOLDERS = dict(fr_calendar_snapshot='calendar', fr_security_master_sync='fr_security_master_sync',
    fr_daily_bars_sync='eodhd_daily', fr_corporate_actions_sync='fr_corporate_actions_sync',
    fr_amf_short_sync='fr_amf_short_sync', fr_dila_disclosures_sync='fr_dila_disclosures_sync',
    fr_fundamentals_sync='fr_fundamentals_sync', fr_consensus_snapshot='fr_consensus_snapshot',
    fr_options_mifir_trade_sync='fr_options_mifir_trade_sync', fr_pit_quality_daily='quality',
    fr_options_open_interest_sync='fr_options_open_interest_sync')
PROVIDERS = dict(fr_calendar_snapshot='library_XPAR', fr_security_master_sync='ESMA_FIRDS',
    fr_daily_bars_sync='EODHD', fr_corporate_actions_sync='EODHD', fr_amf_short_sync='AMF',
    fr_dila_disclosures_sync='DILA', fr_fundamentals_sync='INPI_mapping_quarantine',
    fr_consensus_snapshot='eodhd_or_archived_legacy', fr_options_mifir_trade_sync='Euronext_ESMA',
    fr_pit_quality_daily='local', fr_db_backup='local_mysql', fr_artifacts_backup='local_archive',
    fr_borrow_snapshot='unqualified', fr_options_snapshot='unqualified',
    fr_options_open_interest_sync='Euronext_public')
PARSER = 'fr_batch_sql_v1'
HASH_NAMED_FILES = {'fr_daily_bars_sync', 'fr_corporate_actions_sync',
                    'fr_amf_short_sync', 'fr_dila_disclosures_sync', 'fr_security_master_sync'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def document_key(batch, content_hash):
    return sha((batch+':'+PARSER+':'+content_hash).encode())


def engine_fr():
    return get_market_engine('FR_EQ', database_alias='fr_primary')


def check_schema(engine):
    if engine.url.database != 'alpha_trade_fr':
        raise ValueError('Stockage batchs limité à alpha_trade_fr')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade_fr':
            raise ValueError('Base FR physique contradictoire')
        for table in (DOCUMENTS, FILES, *TYPED):
            conn.execute(text(f'SELECT * FROM {table} LIMIT 0'))


def clock(value, *, allow_future=False):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.year >= 8887 or (not allow_future and stamp > datetime.now(UTC)):
            return None
        return stamp.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return None


def day(value):
    try:
        result = date.fromisoformat(str(value)[:10])
        return result if result.year < 8887 else None
    except ValueError:
        return None


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) >= Decimal('1e26') or result.as_tuple().exponent < -12:
            return None
        return format(result, 'f')
    except (ValueError, InvalidOperation):
        return None


def identity_map():
    path = ROOT / 'artifacts/fr/sprint6c_reference/identities.jsonl.gz'
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return {r['isin']: r.get('provider_symbol') for line in stream if line.strip()
                if (r := json.loads(line)).get('identity_state') == 'VERIFIED_RESEARCH'}


def observation_index(folder):
    """Bind immutable RAW content to real receipt clocks, not filename dates."""
    result = {}
    for p in (folder/'observations').rglob('*.json'):
        row = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(row, dict):
            continue
        key = row.get('raw_sha256')
        observed, available = clock(row.get('observed_at')), clock(row.get('available_at'))
        if key and observed and available and available >= observed:
            prior = result.get(key)
            if prior is None or available < prior[1]:
                result[key] = (observed, available)
    return result


def files_for(batch, operations=OPS):
    if batch not in PROVIDERS:
        raise ValueError('Batch FR inconnu')
    operations = Path(operations).resolve()
    folders = [operations/'runs'/batch]
    if batch in FOLDERS:
        folders.append(operations/FOLDERS[batch])
    paths = []
    for folder in folders:
        if folder.exists():
            paths.extend(folder.rglob('*.json'))
    for path in sorted(set(paths)):
        if not path.resolve().is_relative_to(operations) or path.is_symlink():
            raise ValueError('Chemin archive hors opérations FR')
        yield path


def normalized(batch, rel, data, identities):
    rows, table = [], None
    if not isinstance(data, dict):
        return None, []
    if batch == 'fr_calendar_snapshot' and rel.startswith('calendar/') and 'sessions' in data:
        if data.get('market_code') != 'FR_EQ':
            raise ValueError('Calendrier hors FR')
        table = TYPED[0]
        for row in data['sessions']:
            session = day(row.get('session_date'))
            if not session:
                raise ValueError('Séance calendrier invalide')
            rows.append(dict(session_date=session, status=row['status'],
                open_at_utc=clock(row.get('open_at_utc'), allow_future=True),
                close_at_utc=clock(row.get('close_at_utc'), allow_future=True),
                source=row.get('source'), details_json=encode(row)))
    elif batch == 'fr_security_master_sync' and 'base_sha256' in data and 'symbols' in data:
        if data.get('market_code') != 'FR_EQ' or data.get('canonical_go') is not False:
            raise ValueError('Référentiel hors contrat recherche FR')
        table = TYPED[1]
        for issuer in data['symbols']:
            for venue in issuer['market_reference']:
                for row in venue['versions']:
                    detail = dict(isin=issuer['isin'], mic=venue['mic'], version=row)
                    rows.append(dict(isin=issuer['isin'], symbol=identities.get(issuer['isin']), mic=venue['mic'],
                        asof_from=day(row.get('asof_from')), asof_to=day(row.get('asof_to')),
                        company_name=row.get('name'), currency=row.get('currency'), event_type=row.get('event'),
                        details_json=encode(detail)))
    elif batch == 'fr_corporate_actions_sync' and '/raw/' in rel and 'rows' in data:
        if data.get('kind') not in ('div', 'splits') or not data.get('symbol', '').endswith('.PA'):
            raise ValueError('Action fournisseur hors périmètre FR')
        table = TYPED[2]
        for row in data['rows']:
            parts = str(row.get('split', '')).split('/')
            numerator, denominator = (number(parts[0]), number(parts[1])) if len(parts) == 2 else (None, None)
            cash, event_date = number(row.get('value')), day(row.get('date'))
            valid = bool(event_date and data['window'][0] <= str(event_date) <= data['window'][1]
                         and (cash is not None and Decimal(cash) > 0 if data['kind'] == 'div'
                         else numerator is not None and denominator is not None
                         and Decimal(numerator) > 0 and Decimal(denominator) > 0))
            rows.append(dict(symbol=data['symbol'], event_type=data['kind'], event_date=event_date,
                cash_amount=cash, currency=row.get('currency'), split_numerator=numerator,
                split_denominator=denominator, validation_status='VENDOR_VALID' if valid else 'INVALID',
                details_json=encode(row)))
    elif batch == 'fr_amf_short_sync' and '/raw/' in rel and 'csv_utf8' in data:
        table = TYPED[3]
        parsed, _ = parse_positions(data['csv_utf8'].encode('utf-8'))
        for row in parsed:
            if row['isin'] not in identities:
                continue
            detail = {k: v for k, v in row.items() if k != 'source_line'}
            rows.append(dict(isin=row['isin'], symbol=identities.get(row['isin']), holder=row['holder'],
                position_date=day(row['position_date']), publication_date=day(row['publication_date']),
                publication_end=day(row['publication_end']), ratio_percent=number(row['ratio_percent']),
                details_json=encode(detail)))
    elif batch == 'fr_dila_disclosures_sync' and '/raw/' in rel and 'records' in data:
        table = TYPED[4]
        for row in data['records']:
            isin = row.get('identificationsociete_iso_cd_isi')
            if isin not in identities:
                continue
            publication = public_day(row)
            valid = bool(publication and row.get('uin_idt_uin')
                         and (not data.get('query_window') or publication <= data['query_window'][1]))
            rows.append(dict(isin=isin, symbol=identities.get(isin), announcement_id=row.get('uin_idt_uin'),
                publication_day=day(publication), title=row.get('informationdeposee_inf_tit_inf'),
                document_path=row.get('fichierdecontenu_inf_fic_nom'),
                validation_status='METADATA_VALID' if valid else 'INVALID', details_json=encode(row)))
    # Source row equality, not order or a guessed economic identifier.
    unique = {sha(row['details_json'].encode()): dict(record_sha256=sha(row['details_json'].encode()), **row)
              for row in rows}
    return table, list(unique.values())


def prepare(path, batch, operations, identities, receipts):
    raw = path.read_bytes()
    content_hash = sha(raw)
    rel = path.relative_to(operations).as_posix()
    if (batch in HASH_NAMED_FILES and path.parent.name in ('raw', 'versions')
            and len(path.stem) == 64 and path.stem != content_hash):
        raise ValueError(f'Archive {batch} corrompue : {rel}')
    data = json.loads(raw)
    observed, available = receipts.get(content_hash, (None, None))
    if isinstance(data, dict):
        observed = observed or clock(data.get('observed_at') or data.get('last_observed_at'))
        available = available or clock(data.get('available_at') or data.get('last_observed_at'))
        if available and observed and available < observed:
            raise ValueError('Disponibilité source contradictoire')
    document_id = document_key(batch, content_hash)
    table, rows = normalized(batch, rel, data, identities)
    for row in rows:
        row['document_id'] = document_id
    document = dict(document_id=document_id, batch_name=batch, market_code='FR_EQ', provider=PROVIDERS[batch],
        parser_version=PARSER,
        content_sha256=content_hash, source_observed_at=observed, source_available_at=available,
        sql_available_at=datetime.now(UTC).replace(tzinfo=None), document_json=raw.decode('utf-8'),
        record_count=len(rows), ml_eligible=False, canonical=False, historical_pit_qualified=False)
    receipt = dict(batch_name=batch, path_sha256=sha(rel.encode()), document_id=document_id,
        relative_path=rel, archived_role=path.parent.name[:32],
        file_modified_at=datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(tzinfo=None),
        imported_at=datetime.now(UTC).replace(tzinfo=None))
    return document, receipt, table, rows


def insert(conn, table, rows):
    if table not in (DOCUMENTS, FILES, *TYPED):
        raise ValueError('Table recherche FR inconnue')
    if rows:
        sql = text(f'INSERT INTO {table} ({",".join(rows[0])}) VALUES '
                   f'({",".join(":"+k for k in rows[0])})')
        for start in range(0, len(rows), 500):
            conn.execute(sql, rows[start:start+500])


def publish_batch(engine, batch, *, operations=OPS, apply=True, identities=None, paths=None):
    kwargs = dict(operations=operations, apply=apply, identities=identities, paths=paths)
    if apply and engine.dialect.name == 'mysql':
        check_schema(engine)
        # A manual offline import and the scheduled collector can finish together.
        # Serialize per batch before loading the set of already imported versions.
        lock_name = 'AlphaTradeFRArchive:' + sha(batch.encode())[:32]
        with engine.connect() as gate:
            acquired = gate.execute(text('SELECT GET_LOCK(:name,300)'), dict(name=lock_name)).scalar_one()
            if acquired != 1:
                raise RuntimeError('Archivage SQL FR déjà occupé : '+batch)
            try:
                return _publish_batch(engine, batch, **kwargs)
            finally:
                gate.execute(text('SELECT RELEASE_LOCK(:name)'), dict(name=lock_name))
    return _publish_batch(engine, batch, **kwargs)


def _publish_batch(engine, batch, *, operations=OPS, apply=True, identities=None, paths=None):
    operations = Path(operations).resolve()
    identities = identity_map() if identities is None else identities
    paths = list(files_for(batch, operations)) if paths is None else list(paths)
    if any(not path.resolve().is_relative_to(operations) or path.is_symlink() for path in paths):
        raise ValueError('Chemin archive hors opérations FR')
    folder = operations/FOLDERS[batch] if batch in FOLDERS else operations/'runs'/batch
    receipts = observation_index(folder) if any('/runs/' not in p.as_posix() for p in paths) else {}
    known, linked = {}, set()
    if apply:
        check_schema(engine)
        with engine.connect() as conn:
            known = dict(conn.execute(text(f'SELECT document_id,content_sha256 FROM {DOCUMENTS} '
                'WHERE batch_name=:batch'), dict(batch=batch)).all())
            linked = set(conn.execute(text(f'SELECT path_sha256,document_id FROM {FILES} '
                'WHERE batch_name=:batch'), dict(batch=batch)).all())
    stats = Counter(files_scanned=0, documents_inserted=0, documents_reused=0,
                    file_versions_inserted=0, records_inserted=0)
    pending, pending_size = [], 0

    def flush():
        if not apply or not pending:
            return
        with engine.begin() as conn:
            for document, receipt, table, rows in pending:
                key = document['document_id']
                if key not in known:
                    insert(conn, DOCUMENTS, [document])
                    if table:
                        insert(conn, table, rows)
                    stats['documents_inserted'] += 1
                    stats['records_inserted'] += len(rows)
                    stats[table or 'unstructured_documents'] += len(rows) if table else 1
                    known[key] = document['content_sha256']
                else:
                    stats['documents_reused'] += 1
                link = (receipt['path_sha256'], key)
                if link not in linked:
                    insert(conn, FILES, [receipt])
                    stats['file_versions_inserted'] += 1
                    linked.add(link)
        pending.clear()

    for path in paths:
        # Read every file, including known ones, to check immutable hashes. A
        # successful import must not silently bless a subsequently corrupted RAW.
        raw = path.read_bytes()
        content_hash = sha(raw)
        rel = path.relative_to(operations).as_posix()
        if (batch in HASH_NAMED_FILES and path.parent.name in ('raw', 'versions')
                and len(path.stem) == 64 and path.stem != content_hash):
            raise ValueError('Archive FR corrompue : ' + rel)
        key = document_key(batch, content_hash)
        stats['files_scanned'] += 1
        if key in known and (sha(rel.encode()), key) in linked:
            stats['documents_reused'] += 1
            continue
        item = prepare(path, batch, operations, identities, receipts)
        if item[0]['document_id'] != key:
            raise ValueError('Fichier remplacé pendant la lecture, reprise requise')
        pending.append(item)
        pending_size += len(raw)
        stats['records_verified'] += len(item[3])
        if len(pending) >= 30 or pending_size >= 8_000_000:
            flush()
            if not apply:
                pending.clear()
            pending_size = 0
    flush()
    return dict(batch=batch, status='IMPORTED' if apply else 'VERIFIED_READ_ONLY',
        **stats, ml_eligible=False, api_calls=0)


def main():
    parser = argparse.ArgumentParser(description='Miroir SQL des archives opérationnelles FR, sans réseau fournisseur')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--batch', choices=sorted(PROVIDERS))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError('Rapport existant')
    engine = engine_fr() if args.apply else None
    report = dict(status='RUNNING', database='alpha_trade_fr', batches=[], api_calls=0)
    try:
        for batch in ([args.batch] if args.batch else PROVIDERS):
            result = publish_batch(engine, batch, apply=args.apply)
            report['batches'].append(result)
            atomic(args.report, report)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        report['status'] = 'IMPORTED' if args.apply else 'VERIFIED_READ_ONLY'
    except Exception as exc:
        report.update(status='FAILED', error=str(exc))
        raise
    finally:
        atomic(args.report, report)
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    main()
