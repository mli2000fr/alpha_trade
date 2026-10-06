import pytest

from scripts.research.us_2026_regime_refresh import forbid_writes


@pytest.mark.parametrize('statement',['SELECT 1',' SHOW TABLES','DESCRIBE table1','EXPLAIN SELECT 1'])
def test_read_statements_allowed(statement):
    forbid_writes(None,None,statement,None,None,False)


@pytest.mark.parametrize('statement',['INSERT INTO x VALUES (1)','UPDATE x SET y=1','DELETE FROM x','CREATE TABLE x(y INT)','CALL mutate()'])
def test_write_statements_rejected(statement):
    with pytest.raises(RuntimeError,match='Read-only'):
        forbid_writes(None,None,statement,None,None,False)
