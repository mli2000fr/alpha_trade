from __future__ import annotations

import warnings
from contextlib import contextmanager

import pytest

from common.run_market_scope import (
    compute_scope_universe_fingerprint,
    read_manifest_market_scope,
    resolve_run_market_scope,
)
from modelFactory.db_registry import insert_training_run


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar(self):
        return self.value


class _Connection:
    def __init__(self, parent_market: str = "US_EQ") -> None:
        self.parent_market = parent_market
        self.writes = []

    def execute(self, statement, params):
        sql = str(statement)
        if "SELECT market_code FROM model_training_batch" in sql:
            return _Result(self.parent_market)
        self.writes.append((sql, dict(params)))
        return _Result()


class _Engine:
    def __init__(self, parent_market: str = "US_EQ") -> None:
        self.connection = _Connection(parent_market)

    @contextmanager
    def connect(self):
        yield self.connection

    @contextmanager
    def begin(self):
        yield self.connection


def test_us_batch_scope_is_the_default() -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        scope = resolve_run_market_scope(None)
    assert scope.market_code == "US_EQ"
    assert scope.calendar_id == "NYSE"
    assert any("fallback" in str(item.message) for item in captured)


def test_cn_batch_scope_must_be_explicit_and_changes_manifest() -> None:
    us = resolve_run_market_scope("US_EQ")
    cn = resolve_run_market_scope("CN_A")
    assert cn.market_code == "CN_A"
    assert cn.calendar_id == "CN_A"
    assert cn.base_currency == "CNY"
    assert cn.market_context_fingerprint != us.market_context_fingerprint
    assert compute_scope_universe_fingerprint(
        market_code="CN_A", symbol_source="universe-file:test.txt", symbols=["600000.SH"]
    ) != compute_scope_universe_fingerprint(
        market_code="US_EQ", symbol_source="universe-file:test.txt", symbols=["600000.SH"]
    )


def test_incompatible_training_child_is_rejected() -> None:
    engine = _Engine(parent_market="CN_A")
    with pytest.raises(ValueError, match="incompatible"):
        insert_training_run(
            engine, "run-1", 1, "600000.SH", batch_id="batch-cn", market_code="US_EQ"
        )


def test_legacy_manifest_is_read_as_us_with_warning() -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        scope = read_manifest_market_scope({"batch_id": "legacy"})
    assert scope.market_code == "US_EQ"
    assert captured
