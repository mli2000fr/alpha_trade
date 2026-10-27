"""Append-only SQL mirror of verified FR MiFIR research archives.

Historical file availability and the actual SQL import time are separate.
No price table, feature store, eligibility flag or US schema is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from service.fr import mifir_options_poc as source
from service.inpi.files import atomic

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = ROOT / 'artifacts/fr/operations/fr_options_mifir_trade_sync'
TABLES = ('fr_option_mifir_snapshots', 'fr_option_mifir_contracts',
          'fr_option_mifir_trades', 'fr_option_mifir_observations')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stamp(value):
    return source.instant(value).replace(tzinfo=None)


def engine_fr():
    return get_market_engine('FR_EQ', database_alias='fr_primary')


def check_schema(engine):
    if engine.url.database != 'alpha_trade_fr':
        raise ValueError('Options MiFIR réservées à alpha_trade_fr, aucun fallback US')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade_fr':
            raise ValueError('Base physique FR contradictoire')
        for table in TABLES:
            conn.execute(text(f'SELECT * FROM {table} LIMIT 0'))


def _inside(root, value):
    root = Path(root).resolve()
    value = Path(value)
    resolved = (value if value.is_absolute() else ROOT / value).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('Archive options hors du dossier de collecte FR')
    return resolved


def load_snapshot(path, root=ARCHIVES):
    """Check source hashes and replay the archived parser, without network calls."""
    root = Path(root).resolve()
    path = _inside(root / 'snapshots', path)
    raw = path.read_bytes()
    data = json.loads(raw)
    for flag in ('ml_eligible', 'canonical', 'historical_pit_qualified'):
        if data.get(flag) is not False:
            raise ValueError(f'Archive options promue ou statut absent : {flag}')
    observed, available = stamp(data['observed_at']), stamp(data['available_at'])
    if available < observed:
        raise ValueError('Disponibilité antérieure à la réception')
    universe = data['universe']
    if (not universe or len(set(universe.values())) != len(universe)
            or any(not source.valid_isin(i) or not s.endswith('.PA') for i, s in universe.items())):
        raise ValueError('Univers FR ambigu ou invalide')
    receipts = data['reference_receipts']
    if len(receipts) < 3 or receipts[0]['url'] != source.TRADES_PAGE or receipts[1]['url'] != source.TRADES_URL:
        raise ValueError('Sources MiFIR/FIRDS absentes')
    docs, trades = [], None
    for index, receipt in enumerate(receipts):
        key = receipt['sha256']
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Empreinte source invalide')
        blob = (root / 'objects' / key).read_bytes()
        if digest(blob) != key:
            raise ValueError('Source brute options corrompue')
        if stamp(receipt['received_at']) > observed:
            raise ValueError('Reçu source postérieur au snapshot')
        if index == 1:
            trades, _ = source.read_trades(blob)
        elif index >= 2:
            if not receipt['url'].startswith(source.REFERENCE_URL + '?'):
                raise ValueError('Source FIRDS inattendue')
            response = json.loads(blob)['response']
            if response['numFound'] != len(response['docs']):
                raise ValueError('Archive FIRDS tronquée')
            docs.extend(response['docs'])
    # This is the exact historical key, including its original JSON encoding.
    key = digest(json.dumps(dict(trades=receipts[1]['sha256'], docs=docs,
                                 universe=universe), sort_keys=True).encode())
    if path.stem != key:
        raise ValueError('Identifiant du snapshot incompatible avec les sources')
    analysis = source.analyze(trades, docs, data['observed_at'], universe=universe)
    if encoded(analysis) != encoded(data['analysis']):
        raise ValueError('Analyse archivée différente des données sources vérifiées')
    return dict(path=path, raw=raw.decode('utf-8'), sha256=digest(raw),
                key=key, data=data, observed=observed, available=available)


def _number_or_none(value):
    try:
        number = source.number(value)
        # Preserve exact source precision in JSON; reject silent DECIMAL rounding.
        if number.as_tuple().exponent < -12 or abs(number) >= Decimal('1e26'):
            raise ValueError('Nombre hors précision SQL, source conservée')
        return number
    except (ValueError, TypeError):
        return None


def _clock_or_none(value):
    try:
        return stamp(value)
    except (ValueError, TypeError, AttributeError):
        return None


def prepare_snapshot(archive):
    data, key = archive['data'], archive['key']
    analysis = data['analysis']
    contracts = []
    by_isin = {c['option_isin']: c for c in analysis['contracts']}
    if len(by_isin) != len(analysis['contracts']):
        raise ValueError('Contrats dupliqués')
    for c in by_isin.values():
        if any(_number_or_none(c[name]) is None or Decimal(c[name]) <= 0 for name in ('strike', 'multiplier')):
            raise ValueError('Strike/multiplicateur hors précision SQL')
        contracts.append(dict(snapshot_id=key, option_isin=c['option_isin'], symbol=c['symbol'],
            underlying_isin=c['underlying_isin'], option_type=c['side'], strike=Decimal(c['strike']),
            strike_currency=c['strike_currency'], expiration_date=datetime.fromisoformat(c['expiry']).date(),
            multiplier=Decimal(c['multiplier']), exercise_style=c.get('exercise_style'),
            delivery_type=c.get('delivery_type'), cfi=c.get('cfi'), details_json=encoded(c),
            adjustment_history_qualified=False, historical_reference_pit_qualified=False))
    records = {}

    def add(raw, status, reason):
        row_hash = digest(encoded(raw).encode())
        if row_hash in records:
            if records[row_hash]['acceptance_status'] != status:
                raise ValueError('Transaction à la fois acceptée et rejetée')
            records[row_hash]['source_occurrences'] += 1
            return
        c = by_isin[raw['MifidInstrumentID']]
        traded, published = _clock_or_none(raw['TradingDateTime']), _clock_or_none(raw['PublicationDateTime'])
        price, quantity = _number_or_none(raw['MifidPrice']), _number_or_none(raw['MifidQuantity'])
        if status == 'ACCEPTED' and (None in (traded, published, price, quantity)
                                      or price <= 0 or quantity <= 0 or published > archive['available']):
            raise ValueError('Transaction acceptée invalide pour le stockage SQL')
        records[row_hash] = dict(snapshot_id=key, source_row_sha256=row_hash,
            option_isin=c['option_isin'], symbol=c['symbol'], option_type=c['side'],
            trade_uid=raw['TradeUniqueIdentifier'], venue=raw['Venue'], publication_venue=raw['VenueOfPublication'],
            trade_date=traded.date() if traded else None, traded_at=traded, published_at=published,
            price=price, reported_quantity=quantity, currency=raw.get('MifidCurrency'),
            acceptance_status=status, rejection_reason=reason, source_occurrences=1,
            raw_row_json=encoded(raw), quantity_unit_qualified=False, ml_eligible=False)

    for trade in analysis['accepted']:
        if trade.get('ml_eligible') is not False or trade.get('quantity_unit_qualified') is not False:
            raise ValueError('Qualification implicite interdite')
        add({k: v for k, v in trade.items() if k not in
             {'contract', 'available_at', 'ml_eligible', 'quantity_unit_qualified'}}, 'ACCEPTED', None)
    for rejected in analysis['rejected']:
        for raw in rejected['rows']:
            add(raw, 'REJECTED', rejected['reason'])
    partial = (any(source.valid_isin(i) for i in analysis['reference_unmatched_instruments'])
               or analysis['ambiguous_reference_isins'] or analysis['contract_errors'])
    row = dict(snapshot_id=key, archive_sha256=archive['sha256'], source_sha256=data['reference_receipts'][1]['sha256'],
        market_code='FR_EQ', provider='euronext_mifir_esma_firds', observed_at=archive['observed'],
        available_at=archive['available'], imported_at=datetime.now(UTC).replace(tzinfo=None),
        first_trade_date=datetime.fromisoformat(min(analysis['trade_dates'])).date(),
        last_trade_date=datetime.fromisoformat(max(analysis['trade_dates'])).date(),
        collection_status='PARTIAL' if partial else 'COMPLETE', contract_count=len(contracts),
        accepted_trade_rows=len(analysis['accepted']),
        rejected_trade_rows=sum(len(r['rows']) for r in analysis['rejected']),
        universe_count=len(data['universe']), coverage_json=encoded(analysis['coverage']),
        source_receipts_json=encoded(data['reference_receipts']), archive_path=str(archive['path']),
        archive_json=archive['raw'], ml_eligible=False, historical_pit_qualified=False, canonical=False)
    return row, contracts, list(records.values())


def _insert(conn, table, rows):
    if not rows:
        return
    columns = ','.join(rows[0])
    binds = ','.join(':' + key for key in rows[0])
    for offset in range(0, len(rows), 500):
        # Decimal strings keep exact values in MySQL DECIMAL, without a float
        # conversion, and are also supported by the isolated SQLite tests.
        params = [{k: format(v, 'f') if isinstance(v, Decimal) else v for k, v in row.items()}
                  for row in rows[offset:offset+500]]
        conn.execute(text(f'INSERT INTO {table} ({columns}) VALUES ({binds})'), params)


def store_prepared(conn, prepared):
    """Single caller transaction: a snapshot and all child rows commit together."""
    row, contracts, trades = prepared
    existing = conn.execute(text('SELECT archive_sha256 FROM fr_option_mifir_snapshots '
                                 'WHERE snapshot_id=:id'), dict(id=row['snapshot_id'])).scalar_one_or_none()
    if existing is not None:
        if existing != row['archive_sha256']:
            raise ValueError('Snapshot SQL existant différent, écrasement interdit')
        counts = [conn.execute(text(f'SELECT COUNT(*) FROM {table} WHERE snapshot_id=:id'),
                  dict(id=row['snapshot_id'])).scalar_one() for table in TABLES[1:3]]
        if counts != [len(contracts), len(trades)]:
            raise ValueError('Snapshot SQL incomplet, reprise automatique interdite')
        return dict(sql_snapshots=0, sql_contracts=0, sql_trades=0, sql_snapshots_reused=1)
    _insert(conn, TABLES[0], [row])
    _insert(conn, TABLES[1], contracts)
    _insert(conn, TABLES[2], trades)
    return dict(sql_snapshots=1, sql_contracts=len(contracts), sql_trades=len(trades), sql_snapshots_reused=0)


def load_attempt(path, root=ARCHIVES):
    path = _inside(Path(root) / 'attempts', path)
    raw = path.read_bytes()
    data = json.loads(raw)
    result = data['result']
    if result.get('ml_eligible') is not False or result.get('historical_pit_qualified') is not False:
        raise ValueError('Statuts de recherche absents du reçu')
    snapshot_path = result.get('snapshot_path')
    snapshot = _inside(Path(root) / 'snapshots', snapshot_path) if snapshot_path else None
    row = dict(observation_id=digest(raw), snapshot_id=snapshot.stem if snapshot else None,
        collection_complete=data['collection_complete'] is True, finished_at=stamp(data['finished_at']),
        imported_at=datetime.now(UTC).replace(tzinfo=None), requested_count=result.get('requested_count', 0),
        received_count=result.get('received_count', 0), archive_persisted_count=result.get('persisted_count', 0),
        receipt_path=str(path), receipt_json=raw.decode('utf-8'))
    return row, snapshot


def persist_archive(engine, root, snapshot_path=None, attempt_path=None):
    check_schema(engine)
    archive = load_snapshot(snapshot_path, root) if snapshot_path else None
    prepared = prepare_snapshot(archive) if archive else None
    attempt, linked = load_attempt(attempt_path, root) if attempt_path else (None, None)
    if linked and (not archive or linked.stem != archive['key']):
        raise ValueError('Reçu et snapshot incompatibles')
    stats = dict(sql_snapshots=0, sql_contracts=0, sql_trades=0, sql_observations=0, sql_snapshots_reused=0)
    with engine.begin() as conn:
        if prepared:
            stats.update(store_prepared(conn, prepared))
        if attempt and not conn.execute(text('SELECT 1 FROM fr_option_mifir_observations '
            'WHERE observation_id=:id'), dict(id=attempt['observation_id'])).scalar_one_or_none():
            _insert(conn, TABLES[3], [attempt])
            stats['sql_observations'] = 1
    return stats


def backfill(engine, root=ARCHIVES, *, apply=False):
    """Preflight every archive first, then import without downloading anything."""
    root = Path(root).resolve()
    if apply:
        check_schema(engine)
    snapshots = sorted((root / 'snapshots').glob('*.json'))
    attempts = sorted((root / 'attempts').glob('*.json'))
    if not snapshots:
        raise ValueError('Aucun snapshot MiFIR archivé')
    prepared = {p: prepare_snapshot(load_snapshot(p, root)) for p in snapshots}
    receipts = [load_attempt(p, root) for p in attempts]
    if any(link and link not in prepared for _, link in receipts):
        raise ValueError('Reçu de collecte lié à un snapshot absent')
    totals = Counter(dict(sql_snapshots=0, sql_contracts=0, sql_trades=0,
                          sql_observations=0, sql_snapshots_reused=0))
    if apply:
        for value in prepared.values():
            with engine.begin() as conn:
                totals.update(store_prepared(conn, value))
        for row, _ in receipts:
            with engine.begin() as conn:
                if not conn.execute(text('SELECT 1 FROM fr_option_mifir_observations '
                    'WHERE observation_id=:id'), dict(id=row['observation_id'])).scalar_one_or_none():
                    _insert(conn, TABLES[3], [row])
                    totals['sql_observations'] += 1
    return dict(status='IMPORTED' if apply else 'VERIFIED_READ_ONLY', database='alpha_trade_fr',
        archived_snapshots=len(snapshots), archived_receipts=len(attempts),
        accepted_rows=sum(p[0]['accepted_trade_rows'] for p in prepared.values()),
        rejected_rows=sum(p[0]['rejected_trade_rows'] for p in prepared.values()),
        first_trade_date=str(min(p[0]['first_trade_date'] for p in prepared.values())),
        last_trade_date=str(max(p[0]['last_trade_date'] for p in prepared.values())),
        sql_counts=dict(totals), ml_eligible=False, api_calls=0)


def main():
    parser = argparse.ArgumentParser(description='Import offline des archives options FR vers SQL recherche')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--archive-root', type=Path, default=ARCHIVES)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError('Rapport existant, utiliser un nouveau chemin')
    engine = engine_fr() if args.apply else None
    try:
        report = backfill(engine, args.archive_root, apply=args.apply)
        if args.report:
            atomic(args.report, report)
        print(json.dumps(report, ensure_ascii=False, default=str))
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    main()
