"""Prospective, immutable risk-factor inputs, independent of selection outputs."""
from sqlalchemy import (BigInteger, Column, Date, DateTime, Float, Index, Integer,
    MetaData, String, Table, Text, UniqueConstraint, inspect)

metadata = MetaData()
snapshots = Table('stock_risk_factor_inputs', metadata,
    Column('id', BigInteger().with_variant(Integer, 'sqlite'), primary_key=True, autoincrement=True),
    Column('run_id', String(64), nullable=False), Column('symbol', String(32), nullable=False),
    Column('asof_date', Date, nullable=False), Column('observed_at', DateTime, nullable=False),
    Column('universe_sha256', String(64), nullable=False), Column('input_sha256', String(64), nullable=False),
    Column('beta_126', Float(53)), Column('trend_score', Float(53)), Column('market_cap', Float(53)),
    Column('quality', String(16), nullable=False), Column('details_json', Text, nullable=False),
    UniqueConstraint('run_id', 'symbol', name='uq_risk_factor_run_symbol'),
    Index('ix_risk_factor_asof_universe', 'asof_date', 'universe_sha256', 'observed_at'))


def install_schema(engine):
    if engine.dialect.name != 'sqlite' and engine.engine.url.database != 'alpha_trade':
        raise ValueError('US alpha_trade required')
    snapshots.create(engine, checkfirst=True)


def require_schema(engine):
    if not inspect(engine).has_table(snapshots.name):
        raise ValueError('stock_risk_factor_inputs absent : installer le schéma avant publication')
