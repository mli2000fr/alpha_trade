from __future__ import annotations

import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path

from service.market.cn_canonicalizer import PILOT_QUOTAS, _latest, _pit_close, _spread_pick, write_pilot_manifest

ROOT = Path(__file__).resolve().parents[1]


def _migration_module():
    path = ROOT / "alembic_cn" / "versions" / "0004_canonical_market_pilot.py"
    spec = importlib.util.spec_from_file_location("cn_migration_0004", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sprint7a_migration_is_chained_after_provider_neutral_staging() -> None:
    module = _migration_module()
    assert module.revision == "0004_canonical_market_pilot"
    assert module.down_revision == "0003_provider_neutral_staging"


def test_sprint7a_schema_keeps_raw_prices_and_factors_separate() -> None:
    sql = (ROOT / "database" / "sql" / "cn" / "migration_cn_0004_canonical_market_pilot.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS stock_bars_daily" in sql
    assert "PRIMARY KEY (instrument_id, `date`)" in sql
    assert "data_adjustment = 'raw'" in sql
    assert "adj_close = `close`" in sql
    assert "CREATE TABLE IF NOT EXISTS instrument_adjustment_factors" in sql
    assert "CREATE TABLE IF NOT EXISTS cn_canonicalization_runs" in sql
    assert "alpha_trade`" not in sql


def test_pilot_contract_contains_eighty_stratified_equities() -> None:
    assert PILOT_QUOTAS == {"SH_MAIN": 25, "SZ_MAIN": 25, "STAR": 15, "CHINEXT": 15}
    assert sum(PILOT_QUOTAS.values()) == 80


def test_spread_pick_is_deterministic_and_covers_extremes() -> None:
    values = [f"sh.{index:06d}" for index in range(100)]
    selected = _spread_pick(values, 5)
    assert selected == _spread_pick(list(reversed(values)), 5)
    assert selected[0] == values[0]
    assert selected[-1] == values[-1]
    assert len(selected) == 5


def test_latest_revision_uses_available_at_then_staging_id() -> None:
    instant = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    rows = [
        {"symbol": "x", "available_at": instant, "staging_id": 1, "value": "old"},
        {"symbol": "x", "available_at": instant, "staging_id": 2, "value": "new"},
    ]
    latest, duplicates = _latest(rows, ("symbol",))
    assert duplicates == 1
    assert latest[0]["value"] == "new"


def test_manifest_format_is_comma_separated_without_spaces(tmp_path: Path) -> None:
    path = tmp_path / "pilot.txt"
    digest = write_pilot_manifest(["sz.000002", "sh.600000", "sh.600000"], path)
    assert path.read_text(encoding="utf-8") == "sh.600000,sz.000002\n"
    assert len(digest) == 64


def test_sprint7a_cli_defaults_to_bounded_historical_period() -> None:
    source = (ROOT / "dataIntegrityEngine" / "cn_sprint7a_pilot.py").read_text(encoding="utf-8")
    assert 'default=date(2018, 1, 1)' in source
    assert 'default=date(2025, 12, 31)' in source
    assert 'choices=("select", "collect", "promote", "audit", "all")' in source


def test_cn_daily_pit_close_is_0700_utc() -> None:
    value = _pit_close(date(2025, 1, 2))
    assert value == datetime(2025, 1, 2, 7, 0)
