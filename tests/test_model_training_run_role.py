from __future__ import annotations

from contextlib import contextmanager

from modelFactory.db_registry import insert_training_run


class _Connection:
    def __init__(self) -> None:
        self.sql = ""
        self.params = {}

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = dict(params)


class _Engine:
    def __init__(self) -> None:
        self.connection = _Connection()

    @contextmanager
    def begin(self):
        yield self.connection


def test_insert_training_run_persists_directional_role() -> None:
    engine = _Engine()

    insert_training_run(
        engine,
        "AAPL_direction_long_20260902_abcdef12",
        1,
        "AAPL",
        batch_id="batch-1",
        model_role="direction_long",
    )

    assert "model_role" in engine.connection.sql
    assert engine.connection.params["role"] == "direction_long"
