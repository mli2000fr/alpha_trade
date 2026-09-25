from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from service.market.cn_universe_pit import CNUniversePolicy, _fingerprint, decide_member

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2024, 6, 3)
DECISION = datetime(2024, 6, 3, 1, 30)
PREVIOUS = date(2024, 5, 31)
POLICY = CNUniversePolicy()


def _instrument(**changes):
    row = {
        "instrument_id": 12, "provider_symbol": "sh.600000", "exchange_mic": "XSHG",
        "instrument_type": "equity", "listing_date": date(2010, 1, 1), "delisting_date": None,
    }
    return row | changes


def _observation(**changes):
    row = {
        "history_bars": 60, "recent_bars": 20, "last_bar_date": PREVIOUS,
        "last_close": Decimal("12"), "avg_amount_cny": Decimal("10000000"),
        "last_status": "TRADE", "source_available_at": DECISION - timedelta(days=1),
    }
    return row | changes


def _decide(instrument=None, observation=None):
    return decide_member(instrument or _instrument(), observation or _observation(),
                         session_date=DAY, decision_at=DECISION, previous_session=PREVIOUS, policy=POLICY)


def test_sprint8_cn_migration_and_isolated_schema() -> None:
    path = ROOT / "alembic_cn" / "versions" / "0006_universe_pit.py"
    spec = importlib.util.spec_from_file_location("cn_migration_0006", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "0005_canonical_full_coverage"
    sql = (ROOT / "database" / "sql" / "cn" / "migration_cn_0006_universe_pit.sql").read_text(encoding="utf-8")
    assert all(name in sql for name in (
        "cn_universe_runs", "cn_universe_decisions", "cn_universe_execution_audit",
    ))
    assert "alpha_trade." not in sql


def test_sprint8_audit_indexes_are_cn_only_and_chained() -> None:
    path = ROOT / "alembic_cn" / "versions" / "0007_universe_audit_indexes.py"
    spec = importlib.util.spec_from_file_location("cn_migration_0007", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "0006_universe_pit"
    sql = (ROOT / "database" / "sql" / "cn" / "migration_cn_0007_universe_audit_indexes.sql").read_text(encoding="utf-8")
    assert "ix_cn_daily_status_date" in sql
    assert "ix_cn_limits_policy_date" in sql
    assert "alpha_trade." not in sql


def test_policy_file_is_cn_only_and_validated(tmp_path: Path) -> None:
    loaded = CNUniversePolicy.from_yaml(ROOT / "config" / "universe_cn.yaml")
    assert loaded == POLICY
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("market_code: US_EQ\ndatabase_alias: cn_primary\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exclusivement"):
        CNUniversePolicy.from_yaml(invalid)


def test_delisted_equity_remains_a_candidate_before_delisting() -> None:
    assert _decide(_instrument(delisting_date=date(2025, 6, 3)))["decision_state"] == "CANDIDATE"
    assert _decide(_instrument(delisting_date=DAY))["decision_state"] == "CANDIDATE"
    assert _decide(_instrument(delisting_date=date(2024, 5, 31)))["primary_reason"] == "AFTER_DELISTING_DATE"


def test_future_ipo_and_unknown_listing_are_excluded() -> None:
    assert _decide(_instrument(listing_date=DAY + timedelta(days=1)))["primary_reason"] == "NOT_YET_LISTED_OR_UNKNOWN_LISTING"
    assert _decide(_instrument(listing_date=None))["primary_reason"] == "NOT_YET_LISTED_OR_UNKNOWN_LISTING"


def test_suspension_and_missing_previous_bar_are_distinct_reasons() -> None:
    assert _decide(observation=_observation(last_status="SUSPENDED"))["primary_reason"] == "KNOWN_SUSPENSION"
    assert "NO_PREVIOUS_SESSION_BAR" in _decide(observation=_observation(last_bar_date=date(2024, 5, 30)))["reasons"]
    assert _decide(observation=_observation(last_status="TRADE|ST"))["decision_state"] == "CANDIDATE"


def test_history_and_liquidity_thresholds_are_explicit() -> None:
    result = _decide(observation=_observation(history_bars=39, recent_bars=14, avg_amount_cny=Decimal("1")))
    assert result["reasons"] == ["INSUFFICIENT_HISTORY", "INSUFFICIENT_RECENT_BARS", "LIQUIDITY_BELOW_MINIMUM_OR_MISSING"]


def test_decision_does_not_use_status_unavailable_at_open() -> None:
    result = _decide(observation=_observation(last_status="SUSPENDED|SOURCE_CONFLICT", source_available_at=DECISION + timedelta(hours=6)))
    assert result["decision_state"] == "CANDIDATE"


def test_fingerprint_is_stable_and_changes_with_inputs() -> None:
    assert _fingerprint({"a": 1, "b": 2}) == _fingerprint({"b": 2, "a": 1})
    assert _fingerprint({"a": 1}) != _fingerprint({"a": 2})
