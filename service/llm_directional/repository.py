"""Append-only assessments; run state transitions are explicit and transactional."""
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import (MetaData, Table, Column, String, Text, Integer, Float,
                        Date, DateTime, Boolean, ForeignKey, select, update)
from sqlalchemy.dialects.mysql import LONGTEXT

metadata = MetaData()
payload_type = Text().with_variant(LONGTEXT(), 'mysql')
runs = Table('llm_directional_runs', metadata,
    Column('run_id', String(80), primary_key=True),
    Column('trade_date', Date, nullable=False),
    Column('batch_id', String(255), nullable=False),
    Column('account_id', String(40), nullable=False),
    Column('status', String(24), nullable=False),
    Column('started_at', DateTime, nullable=False),
    Column('completed_at', DateTime),
    Column('config_json', payload_type, nullable=False),
    Column('input_json', payload_type, nullable=False),
    Column('input_sha256', String(64), nullable=False),
    Column('protocol_version', String(40), nullable=False),
    Column('selected_json', payload_type),
    Column('error_message', Text),
    Column('risk_started_at', DateTime),
    Column('risk_run_id', String(100)),
    Column('execution_started_at', DateTime))
assessments = Table('llm_directional_assessments', metadata,
    Column('run_id', String(80), ForeignKey(runs.c.run_id), primary_key=True),
    Column('symbol', String(20), primary_key=True),
    Column('oracle_rank', Integer, nullable=False),
    Column('oracle_score', Float, nullable=False),
    Column('observed_at', DateTime, nullable=False),
    Column('request_json', payload_type, nullable=False),
    Column('response_json', payload_type),
    Column('response_sha256', String(64)),
    Column('assessment_json', payload_type),
    Column('sources_json', payload_type),
    Column('status', String(24), nullable=False),
    Column('selected', Boolean, nullable=False, default=False),
    Column('error_message', Text))
evaluations = Table('llm_directional_evaluations', metadata,
    Column('run_id', String(80), ForeignKey(runs.c.run_id), primary_key=True),
    Column('symbol', String(20), primary_key=True),
    Column('horizon', Integer, primary_key=True),
    Column('evaluated_at', DateTime, nullable=False),
    Column('entry_date', Date, nullable=False),
    Column('exit_date', Date, nullable=False),
    Column('return_pct', Float, nullable=False),
    Column('signal_return_pct', Float, nullable=False),
    Column('selected', Boolean, nullable=False),
    Column('oracle_decile', Integer),
    Column('lineage_json', payload_type, nullable=False))

for table in metadata.tables.values():
    table.dialect_options['mysql']['charset'] = 'utf8mb4'
    table.dialect_options['mysql']['engine'] = 'InnoDB'


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def dumps(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str)


def digest(value):
    return hashlib.sha256(dumps(value).encode('utf-8')).hexdigest()


class Repository:
    def __init__(self, engine):
        self.engine = engine
        if engine.dialect.name == 'mysql' and engine.url.database != 'alpha_trade':
            raise ValueError('Le filtre LLM est réservé à alpha_trade (US)')

    def create(self, **values):
        with self.engine.begin() as conn:
            conn.execute(runs.insert().values(**values))

    def record(self, **values):
        with self.engine.begin() as conn:
            conn.execute(assessments.insert().values(**values))

    def finish(self, run_id, status, selected, error=None):
        with self.engine.begin() as conn:
            result = conn.execute(update(runs).where(runs.c.run_id == run_id,
                runs.c.status == 'RUNNING').values(status=status, selected_json=dumps(selected),
                    completed_at=utcnow(), error_message=error))
            if result.rowcount != 1:
                raise ValueError('Run absent ou déjà finalisé')
            for symbol in selected:
                conn.execute(update(assessments).where(assessments.c.run_id == run_id,
                    assessments.c.symbol == symbol).values(selected=True))

    def finalize_assessment(self, run_id, symbol, *, status, parsed, error=None):
        # Only derived verdict fields may transition; raw request/response are never overwritten.
        with self.engine.begin() as conn:
            result = conn.execute(update(assessments).where(assessments.c.run_id == run_id,
                assessments.c.symbol == symbol, assessments.c.status == 'RECEIVED').values(
                status=status, assessment_json=dumps(parsed) if parsed else None,
                sources_json=dumps(parsed['sources']) if parsed else None, error_message=error))
            if result.rowcount != 1:
                raise ValueError('Assessment absent ou déjà finalisé')

    def get(self, run_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(runs).where(runs.c.run_id == run_id)).mappings().one()
            items = conn.execute(select(assessments).where(assessments.c.run_id == run_id)
                                 .order_by(assessments.c.oracle_rank)).mappings().all()
        return dict(row), [dict(item) for item in items]

    def bind_risk(self, run_id, risk_run_id):
        with self.engine.begin() as conn:
            result = conn.execute(update(runs).where(runs.c.run_id == run_id,
                runs.c.status == 'COMPLETED', runs.c.risk_run_id.is_(None))
                .values(risk_run_id=risk_run_id))
            if result.rowcount != 1:
                raise ValueError('Risque déjà lié ou run LLM invalide; pas de rejeu automatique')

    def claim_risk(self, run_id):
        with self.engine.begin() as conn:
            result = conn.execute(update(runs).where(runs.c.run_id == run_id,
                runs.c.status == 'COMPLETED', runs.c.risk_started_at.is_(None),
                runs.c.risk_run_id.is_(None)).values(risk_started_at=utcnow()))
            if result.rowcount != 1:
                raise ValueError('Risque déjà tenté pour cette analyse; vérifier avant reprise')

    def claim_execution(self, run_id):
        with self.engine.begin() as conn:
            result = conn.execute(update(runs).where(runs.c.run_id == run_id,
                runs.c.status == 'COMPLETED', runs.c.risk_run_id.is_not(None),
                runs.c.execution_started_at.is_(None)).values(execution_started_at=utcnow()))
            if result.rowcount != 1:
                raise ValueError('Exécution déjà tentée ou risque non lié; vérifier les ordres avant reprise')
