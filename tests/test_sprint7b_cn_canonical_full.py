from __future__ import annotations

import importlib.util
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from dataIntegrityEngine.cn_sprint7b_full import Sprint7BState
from service.market.cn_canonical_full import derived_limit_for_bar, price_limit_policy, write_chunks
from service.market.cn_canonicalizer import canonical_trading_status

ROOT = Path(__file__).resolve().parents[1]


def _migration_module():
    path = ROOT / "alembic_cn" / "versions" / "0005_canonical_full_coverage.py"
    spec = importlib.util.spec_from_file_location("cn_migration_0005", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sprint7b_migration_is_chained_after_pilot() -> None:
    module = _migration_module()
    assert module.revision == "0005_canonical_full_coverage"
    assert module.down_revision == "0004_canonical_market_pilot"


def test_sprint7b_schema_preserves_derived_and_unclassified_semantics() -> None:
    sql = (ROOT / "database" / "sql" / "cn" / "migration_cn_0005_canonical_full_coverage.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS cn_daily_price_limits" in sql
    assert "derivation_method" in sql
    assert "CREATE TABLE IF NOT EXISTS cn_corporate_actions" in sql
    assert "classification_status" in sql
    assert "CREATE TABLE IF NOT EXISTS cn_canonical_coverage_metrics" in sql


@pytest.mark.parametrize(
    ("board", "session", "is_st", "observation", "expected_policy", "expected_pct"),
    [
        ("SH_MAIN", date(2025, 1, 2), False, 1, "IPO_FIRST_5_OBS_NO_LIMIT_CONSERVATIVE", None),
        ("SH_MAIN", date(2025, 1, 2), True, 6, "CN_ST_5PCT_V1", Decimal("0.05")),
        ("SH_MAIN", date(2026, 7, 5), True, 6, "CN_ST_5PCT_V1", Decimal("0.05")),
        ("SH_MAIN", date(2026, 7, 6), True, 6, "CN_MAIN_ST_10PCT_POST_20260706_V1", Decimal("0.10")),
        ("SZ_MAIN", date(2026, 7, 6), True, 6, "CN_MAIN_ST_10PCT_POST_20260706_V1", Decimal("0.10")),
        ("STAR", date(2020, 1, 2), False, 6, "CN_STAR_20PCT_V1", Decimal("0.20")),
        ("STAR", date(2024, 1, 2), True, 6, "CN_STAR_20PCT_V1", Decimal("0.20")),
        ("CHINEXT", date(2020, 8, 23), False, 6, "CN_MAIN_10PCT_V1", Decimal("0.10")),
        ("CHINEXT", date(2020, 8, 23), True, 6, "CN_ST_5PCT_V1", Decimal("0.05")),
        ("CHINEXT", date(2020, 8, 24), False, 6, "CN_CHINEXT_20PCT_POST_20200824_V1", Decimal("0.20")),
        ("CHINEXT", date(2020, 8, 24), True, 6, "CN_CHINEXT_20PCT_POST_20200824_V1", Decimal("0.20")),
        ("SZ_MAIN", date(2025, 1, 2), False, 6, "CN_MAIN_10PCT_V1", Decimal("0.10")),
    ],
)
def test_price_limit_policy_is_explicit_and_conservative(
    board: str,
    session: date,
    is_st: bool,
    observation: int,
    expected_policy: str,
    expected_pct: Decimal | None,
) -> None:
    policy, pct, exception = price_limit_policy(
        board=board,
        session_date=session,
        is_st=is_st,
        observed_number=observation,
    )
    assert policy == expected_policy
    assert pct == expected_pct
    assert exception is (observation <= 5)


def test_derived_limit_quarantines_observed_break_without_inventing_official_limit() -> None:
    valid = derived_limit_for_bar(
        board="CHINEXT", session_date=date(2024, 1, 2), is_st=True,
        observed_number=100, pre_close=Decimal("10"), high=Decimal("11.50"), low=Decimal("9"),
    )
    assert valid["policy"] == "CN_CHINEXT_20PCT_POST_20200824_V1"
    assert valid["up"] == Decimal("12.00")
    assert valid["exception"] is False

    unverified = derived_limit_for_bar(
        board="SH_MAIN", session_date=date(2024, 1, 2), is_st=False,
        observed_number=100, pre_close=Decimal("10"), high=Decimal("12.50"), low=Decimal("9"),
    )
    assert unverified["policy"] == "OBSERVED_OUTSIDE_DERIVED_LIMIT_V1"
    assert unverified["derivation"] == "observed_break_v1"
    assert unverified["exception"] is True
    assert unverified["up"] is None and unverified["down"] is None
    assert unverified["locked_up"] is None and unverified["locked_down"] is None


def test_conflicting_suspension_remains_non_tradable_and_is_idempotently_tagged() -> None:
    assert canonical_trading_status("SUSPENDED", 123, 0) == "SUSPENDED|SOURCE_CONFLICT"
    assert canonical_trading_status("SUSPENDED|ST", 0, 1) == "SUSPENDED|ST|SOURCE_CONFLICT"
    assert canonical_trading_status("SUSPENDED", 0, 0) == "SUSPENDED"
    assert canonical_trading_status("TRADE", 123, 100) == "TRADE"
    assert canonical_trading_status("SUSPENDED|SOURCE_CONFLICT", 123, 0) == "SUSPENDED|SOURCE_CONFLICT"
    assert not canonical_trading_status("SUSPENDED", 123, 0).startswith("TRADE")


def test_chunk_manifests_are_deterministic_and_indexed(tmp_path: Path) -> None:
    symbols = ["sz.000003", "sh.600000", "sz.000002", "sh.600001", "sh.600002"]
    paths = write_chunks(symbols, tmp_path, chunk_size=2)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [path.name for path in paths] == ["chunk_0000.txt", "chunk_0001.txt", "chunk_0002.txt"]
    assert index["symbol_count"] == 5
    assert index["chunk_size"] == 2
    assert index["chunk_count"] == 3
    assert paths[0].read_text(encoding="utf-8") == "sh.600000,sz.000003\n"


def test_state_is_atomic_and_allows_resume(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = Sprint7BState(path)
    state.update(12, status="COMPLETED", details={"bars": 123})
    reloaded = Sprint7BState(path)
    assert reloaded.status(12) == "COMPLETED"
    assert reloaded.payload["chunks"]["12"]["details"]["bars"] == 123
    assert not path.with_suffix(".tmp").exists()


def test_full_backfill_is_sequential_resumable_and_includes_inactive() -> None:
    source = (ROOT / "dataIntegrityEngine" / "cn_sprint7b_full.py").read_text(encoding="utf-8")
    assert "include_inactive=True" in source
    assert "resume=True" in source
    assert "default=25" in source
    assert "for index in range(args.start_chunk, stop):" in source
    assert "ThreadPoolExecutor" not in source


def test_cn_bootstrap_expects_sprint7b_revision_and_tables() -> None:
    source = (ROOT / "service" / "tushare" / "bootstrap_database.py").read_text(encoding="utf-8")
    assert 'EXPECTED_REVISION = "0005_canonical_full_coverage"' in source
    assert '"cn_daily_price_limits"' in source
    assert '"cn_corporate_actions"' in source
    assert '"cn_canonical_coverage_metrics"' in source
