"""The research inventory only accepts SELECTs and binds symbols as values."""
import pytest
from sqlalchemy import create_engine

from scripts.research.us_llm_batch_evidence_audit import query,TABLES


@pytest.mark.parametrize('sql',['DELETE FROM x','UPDATE x SET y=1','INSERT INTO x VALUES(1)',
    'CREATE TABLE x(id INT)','DROP TABLE x'])
def test_inventory_query_rejects_mutations(sql):
    with pytest.raises(ValueError,match='SELECT only'):
        query(None,sql,{})


def test_inventory_query_binds_symbol_values():
    engine=create_engine('sqlite:///:memory:')
    symbol="ABC'); DROP TABLE x; --"
    with engine.connect() as conn:
        result=query(conn,'SELECT :name AS name WHERE :name IN :symbols',dict(name=symbol),symbols=[symbol])
    assert result==[dict(name=symbol)]
    assert 'stock_analyst_consensus_eodhd_history' in TABLES
    assert not any('analyst_eps_revision_history' in t or 'short_volume' in t for t in TABLES)
