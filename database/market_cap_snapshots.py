"""Derived US cap observations: separate from original SEC filing facts."""
from __future__ import annotations

from sqlalchemy import (BigInteger, Column, Date, DateTime, Float, Index, Integer,
                        MetaData, String, Table, Text, UniqueConstraint, inspect)

metadata = MetaData()
snapshots = Table(
    'stock_market_cap_daily', metadata,
    Column('id', BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True),
    Column('symbol', String(32), nullable=False),
    Column('observation_date', Date, nullable=False),
    Column('available_date', Date, nullable=False),
    Column('computed_at', DateTime, nullable=False),
    Column('source', String(24), nullable=False),
    Column('market_cap', Float(53), nullable=False),
    Column('currency', String(3), nullable=False),
    Column('shares_outstanding', Float(53)),
    Column('reference_close', Float(53)),
    Column('price_date', Date),
    Column('price_source', String(64)),
    Column('source_record_id', BigInteger, nullable=False),
    Column('source_trade_date', Date, nullable=False),
    Column('source_available_date', Date, nullable=False),
    Column('shares_basis_date', Date),
    Column('accession_number', String(64)),
    Column('run_id', String(96), nullable=False),
    Column('input_hash', String(64), nullable=False),
    Column('details_json', Text, nullable=False),
    UniqueConstraint('input_hash', name='uq_market_cap_input'),
    Index('ix_market_cap_symbol_available', 'symbol', 'available_date'),
    Index('ix_market_cap_observation_source', 'observation_date', 'source'),
)


def require_schema(engine):
    if engine.dialect.name != 'sqlite' and engine.url.database != 'alpha_trade':
        raise ValueError('Calcul de capitalisation réservé à alpha_trade US')
    inspector = inspect(engine)
    if not inspector.has_table(snapshots.name):
        raise RuntimeError('Migration 0109_market_cap_daily requise avant market_cap_sync')
    if not set(snapshots.c.keys()).issubset({c['name'] for c in inspector.get_columns(snapshots.name)}):
        raise RuntimeError('Schéma stock_market_cap_daily incomplet ; vérifier migration 0109')


def install_schema(engine):
    """Add this table only, without running unrelated migrations or stamping heads."""
    if engine.dialect.name != 'sqlite' and engine.url.database != 'alpha_trade':
        raise ValueError('Installation réservée à alpha_trade US')
    snapshots.create(engine, checkfirst=True)
    require_schema(engine)


def store(engine, rows):
    """One atomic provider tranche; repeated identical observations are ignored."""
    if not rows:
        return 0
    require_schema(engine)
    if engine.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
        statement = insert(snapshots).on_conflict_do_nothing(index_elements=['input_hash'])
    else:
        from sqlalchemy.dialects.mysql import insert
        # Values are validated by the calculator before reaching the database.
        statement = insert(snapshots).prefix_with('IGNORE')
    count = 0
    with engine.begin() as conn:
        for offset in range(0, len(rows), 200):
            count += max(0, conn.execute(statement, rows[offset:offset+200]).rowcount)
    return count


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Installation additive de stock_market_cap_daily uniquement')
    parser.add_argument('--install-schema', action='store_true', required=True)
    parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    install_schema(get_sqlalchemy_engine())
    print('stock_market_cap_daily prêt ; autres tables et versions Alembic inchangées')
