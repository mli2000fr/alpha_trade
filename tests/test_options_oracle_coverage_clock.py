"""UTC cutoff vs MySQL local TIMESTAMP; genuine missing coverage still blocks."""
from datetime import date, datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from service.options_directional.runner import _load_oracle_rows, OracleCoverageError


DAY = date(2026, 10, 26)
CREATED = datetime(2026, 10, 27, 0, 17, 54, tzinfo=timezone.utc)


class Connection:
    def __init__(self, offset):
        self.offset, self.queries = offset, []

    def execute(self, query, params):
        sql = str(query)
        self.queries.append(sql)
        assert sql.lstrip().startswith('SELECT')
        assert 'UNIX_TIMESTAMP(p.created_at)<=:cutoff_epoch' in sql
        assert 'UNIX_TIMESTAMP(l.created_at)<=:cutoff_epoch' in sql
        assert params['batch'] == 'model-exact' and params['day'] == DAY
        assert params['symbols'] == ['AAA']
        # The epoch is stable even when the session renders 01:17 or 02:17.
        rows = ([dict(symbol='AAA', proba_extreme=.8, fold_start='2026-01-08',
                     created_at_epoch=CREATED.timestamp())]
                if CREATED.timestamp() <= params['cutoff_epoch'] else [])
        return SimpleNamespace(mappings=lambda: rows)


@pytest.mark.parametrize('offset', [0, 1, 2, -4])
def test_sql_timezone_cannot_hide_predictions_already_created(offset):
    c = Connection(offset)
    cutoff = CREATED+timedelta(seconds=10)
    rows = _load_oracle_rows(c, dialect='mysql', batch_id='model-exact', day=DAY,
                            symbols=['AAA'], cutoff=cutoff)
    assert len(rows) == 1 and rows[0]['created_at'] == CREATED
    assert 'created_at_epoch' not in rows[0]


def test_future_creation_is_still_excluded_not_fixed_by_removing_cutoff():
    rows = _load_oracle_rows(Connection(1), dialect='mysql', batch_id='model-exact', day=DAY,
                            symbols=['AAA'], cutoff=CREATED-timedelta(seconds=1))
    assert rows == []


def test_offset_aware_python_cutoff_is_normalized_to_same_instant():
    rows = _load_oracle_rows(Connection(1), dialect='mysql', batch_id='model-exact', day=DAY,
        symbols=['AAA'], cutoff=CREATED.astimezone(timezone(timedelta(hours=1))))
    assert rows[0]['created_at'] == CREATED


def test_naive_cutoff_is_refused():
    with pytest.raises(ValueError, match='horodaté'):
        _load_oracle_rows(Connection(1), dialect='mysql', batch_id='model-exact', day=DAY,
                         symbols=['AAA'], cutoff=CREATED.replace(tzinfo=None))


def test_real_92_percent_coverage_does_not_become_complete():
    error = OracleCoverageError(rows=[dict(symbol=f'S{i}') for i in range(1647)],
        symbols=[f'S{i}' for i in range(1790)], batch_id='model-exact', trade_date=DAY, required_ratio=.95)
    assert '1647/1790' in str(error) and 'minimum 95.00%' in str(error)
    assert len(error.diagnostics['missing_symbols']) == 143
    assert error.diagnostics['coverage_ratio'] == pytest.approx(1647/1790)
