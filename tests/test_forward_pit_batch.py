from __future__ import annotations

from pathlib import Path
import pytest

from service.forward_pit.batch import (
    HANDLERS,
    PENDING_BATCHES,
    _data_blocks,
    _hash,
    _market_dt,
    _schema_hash,
    _security_changes,
    daily_bars_sync,
)

ROOT = Path(__file__).resolve().parents[1]


def test_all_enabled_forward_batches_have_handlers() -> None:
    expected = {
        "daily_bars_sync", "security_master_snapshot", "corporate_actions_sync",
        "sec_edgar_incremental", "pit_data_quality_daily", "borrow_status_snapshot",
        "business_quant_analyst_snapshot", "oracle_options_indicative_snapshot",
        "oracle_opening_window_sync", "sec_corporate_events_normalize",
        "sec_institutional_ownership_normalize", "fred_alfred_vintage_sync",
    }
    assert expected == set(HANDLERS)
    assert PENDING_BATCHES == {
        "finra_short_volume_sync", "auction_imbalance_sync",
        "securities_lending_sync", "official_options_nbbo_sync",
    }


def test_business_quant_single_and_multi_ticker_envelopes() -> None:
    single = {"metadata": {"ticker": "AAPL"}, "data": [{"close": 1}]}
    multi = {"AAPL": single, "MSFT": {"metadata": {"ticker": "MSFT"}, "data": [{"close": 2}]}}
    assert list(_data_blocks(single))[0][0] == "AAPL"
    assert [row[0] for row in _data_blocks(multi)] == ["AAPL", "MSFT"]


def test_payload_and_schema_hashes_are_stable_but_distinct() -> None:
    assert _hash({"a": 1, "b": 2}) == _hash({"b": 2, "a": 1})
    assert _schema_hash({"a": 1}) == _schema_hash({"a": 2})
    assert _hash({"a": 1}) != _hash({"a": 2})


def test_security_master_change_detection_is_conservative() -> None:
    previous = {
        "AAA": {"company_name": "Alpha", "exchange": "N"},
        "OLD": {"company_name": "Old", "exchange": "N"},
    }
    current = {
        "AAA": {"company_name": "Alpha Inc", "exchange": "N"},
        "NEW": {"company_name": "New", "exchange": "Q"},
    }
    changes = _security_changes(previous, current)
    types = {(item["symbol"], item["type"]) for item in changes}
    assert ("AAA", "FIELD_COMPANY_NAME") in types
    assert ("NEW", "NEW_SYMBOL") in types
    assert ("OLD", "MISSING_FROM_DIRECTORY") in types
    assert all(item["confirmed"] is False for item in changes)


def test_forward_pit_sql_reference_and_migration_cover_all_tables() -> None:
    ddl = (ROOT / "database/sql/forward_pit/forward_pit_tables.sql").read_text(encoding="utf-8")
    expected = {
        "pit_collection_runs", "pit_raw_payloads", "stock_bars_daily_versions",
        "security_master_snapshots", "security_master_changes",
        "corporate_action_source_events", "sec_filing_raw",
        "stock_borrow_status_snapshots", "stock_analyst_consensus_snapshots",
        "stock_option_snapshots", "stock_opening_window_bars", "sec_corporate_events",
        "sec_ownership_snapshots", "macro_vintage_observations",
        "pit_data_quality_metrics", "pit_data_quality_issues",
    }
    assert {name for name in expected if f"alpha_trade.{name}" in ddl} == expected
    migration = (ROOT / "alembic/versions/0075_forward_pit_collection_foundation.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0074_fundamental_pit_contract"' in migration


def test_launcher_invokes_service_layer() -> None:
    launcher = (ROOT / "scripts/windows/forward_pit_launcher.ps1").read_text(encoding="utf-8")
    assert "service.forward_pit.batch" in launcher
    assert "modelFactory.forward_pit_batch" not in launcher
    assert "-Force contourne l'horaire, jamais enabled=false" in launcher


def test_all_forward_batches_use_existing_email_and_telegram_notifier() -> None:
    launcher = (ROOT / "scripts/windows/forward_pit_launcher.ps1").read_text(encoding="utf-8")
    notifier = (ROOT / "scripts/send_batch_email.py").read_text(encoding="utf-8")
    installer = (ROOT / "scripts/windows/install_forward_pit_task.ps1").read_text(encoding="utf-8")
    assert "scripts\\send_batch_email.py" in launcher
    assert "--event $BatchName" in launcher
    assert "forward_pit_launcher.ps1" in installer
    assert "send_notification" in notifier
    assert "send_telegram_message" in notifier


def test_raw_business_quant_bars_cannot_be_mislabeled_as_canonical() -> None:
    with pytest.raises(RuntimeError, match="OHLCV Business Quant sont RAW"):
        daily_bars_sync(None, {"canonical_upsert": True}, "run", True)  # type: ignore[arg-type]


def test_new_york_provider_timestamp_is_normalized_to_utc() -> None:
    local_dt, utc_dt = _market_dt("2026-09-10 16:00:00")
    assert local_dt.hour == 16
    assert utc_dt.hour == 20
