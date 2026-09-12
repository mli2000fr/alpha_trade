from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from service.forward_pit.batch import (
    HANDLERS,
    PENDING_BATCHES,
    _assets_in_universe,
    _collection_symbols,
    _configure_alpaca_session,
    _data_blocks,
    _hash,
    _market_dt,
    _nearest_option_expirations,
    _option_contract_parts,
    _option_is_liquid,
    _paginated_json,
    _parse_finra_short_volume,
    _schema_hash,
    _security_changes,
    _select_option_surface_contracts,
    _underlying_price,
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
        "finra_short_volume_sync",
    }
    assert expected == set(HANDLERS)
    assert PENDING_BATCHES == {
        "auction_imbalance_sync", "securities_lending_sync",
        "official_options_nbbo_sync",
    }


def test_business_quant_single_and_multi_ticker_envelopes() -> None:
    single = {"metadata": {"ticker": "AAPL"}, "data": [{"close": 1}]}
    multi = {"AAPL": single, "MSFT": {"metadata": {"ticker": "MSFT"}, "data": [{"close": 2}]}}
    assert list(_data_blocks(single))[0][0] == "AAPL"
    assert [row[0] for row in _data_blocks(multi)] == ["AAPL", "MSFT"]


def test_collection_universe_is_complete_unless_smoke_limit_is_explicit(tmp_path: Path) -> None:
    universe = tmp_path / "universe.txt"
    universe.write_text("CCC,AAA,BBB", encoding="utf-8")
    assert _collection_symbols({"symbols_file": str(universe)}) == ["AAA", "BBB", "CCC"]
    assert _collection_symbols({"symbols_file": str(universe), "max_symbols": 2}) == ["AAA", "BBB"]
    with pytest.raises(ValueError, match="strictement positif"):
        _collection_symbols({"symbols_file": str(universe), "max_symbols": 0})


def test_borrow_assets_are_restricted_to_the_stable_universe() -> None:
    assets = [
        {"symbol": "AAA", "class": "us_equity"},
        {"symbol": "BBB", "class": "us_equity"},
        {"symbol": "AAA", "class": "crypto"},
    ]
    assert _assets_in_universe(assets, ["aaa", "CCC"]) == [assets[0]]


def test_finra_short_volume_parser_skips_header_trailer_and_bad_rows() -> None:
    content = "\n".join([
        "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market",
        "20260911|AAPL|120|5|300|Q",
        "bad|MSFT|x|0|10|N",
        "2",
    ])
    assert _parse_finra_short_volume(content) == [{
        "trade_date": datetime(2026, 9, 11).date(),
        "symbol": "AAPL", "short_volume": 120, "short_exempt_volume": 5,
        "total_volume": 300, "market": "Q",
    }]


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
        "stock_short_volume_daily",
    }
    assert {name for name in expected if f"alpha_trade.{name}" in ddl} == expected
    migration = (ROOT / "alembic/versions/0075_forward_pit_collection_foundation.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0074_fundamental_pit_contract"' in migration
    finra_migration = (ROOT / "alembic/versions/0076_finra_short_volume_daily.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0075_forward_pit_collection"' in finra_migration


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


def test_option_contract_parser_and_nearest_target_expirations() -> None:
    assert _option_contract_parts("AAPL260918C00150000") == (
        datetime(2026, 9, 18).date(), 150.0, "CALL",
    )
    assert _option_contract_parts("BAD") == (None, None, None)
    contracts = [
        "AAPL260918C00150000", "AAPL260925P00150000",
        "AAPL261002C00150000",
    ]
    assert _nearest_option_expirations(
        contracts, (5, 10, 20), datetime(2026, 9, 12).date(),
    ) == {
        datetime(2026, 9, 18).date(),
        datetime(2026, 9, 25).date(),
        datetime(2026, 10, 2).date(),
    }


def test_option_liquidity_filter_rejects_missing_and_excessive_spreads() -> None:
    assert _option_is_liquid(
        {"latestQuote": {"bp": 1.0, "ap": 1.2}},
        min_bid=0.01, max_relative_spread=0.50,
        require_two_sided_quote=True,
    )
    assert not _option_is_liquid(
        {"latestQuote": {"bp": 0.0, "ap": 1.0}},
        min_bid=0.01, max_relative_spread=1.0,
        require_two_sided_quote=True,
    )
    assert not _option_is_liquid(
        {"latestQuote": {"bp": 0.1, "ap": 1.0}},
        min_bid=0.01, max_relative_spread=1.0,
        require_two_sided_quote=True,
    )


def test_underlying_price_uses_freshest_available_positive_price() -> None:
    assert _underlying_price({
        "latestTrade": {"p": None},
        "minuteBar": {"c": 12.5},
        "dailyBar": {"c": 12.0},
    }) == 12.5


def test_option_surface_sampling_keeps_one_contract_per_target_side_and_expiry() -> None:
    snapshots = {
        "AAPL260918C00090000": {},
        "AAPL260918C00100000": {},
        "AAPL260918C00110000": {},
        "AAPL260918P00090000": {},
        "AAPL260918P00100000": {},
        "AAPL260918P00110000": {},
        "AAPL260925C00100000": {},
    }
    selected = _select_option_surface_contracts(
        snapshots,
        expirations={datetime(2026, 9, 18).date()},
        spot=100.0,
        moneyness_targets=(0.90, 1.00, 1.10),
    )
    assert selected == {
        "AAPL260918C00090000", "AAPL260918C00100000",
        "AAPL260918C00110000", "AAPL260918P00090000",
        "AAPL260918P00100000", "AAPL260918P00110000",
    }


def test_alpaca_pagination_follows_tokens_without_silent_truncation(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_request(_session, _url, *, params, headers):
        calls.append(dict(params))
        if len(calls) == 1:
            return {"snapshots": {"A": {}}, "next_page_token": "next"}, 200
        return {"snapshots": {"B": {}}}, 200

    monkeypatch.setattr("service.forward_pit.batch._request_json", fake_request)
    pages = _paginated_json(
        object(), "https://example.invalid", params={"limit": 1000},
        headers={"x": "y"}, page_key="next_page_token", max_pages=3,
    )
    assert len(pages) == 2
    assert "page_token" not in calls[0]
    assert calls[1]["page_token"] == "next"


def test_alpaca_system_trust_adapter_is_only_mounted_when_requested(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.mounts: list[tuple[str, object]] = []

        def mount(self, prefix: str, adapter: object) -> None:
            self.mounts.append((prefix, adapter))

    monkeypatch.setattr("service.forward_pit.batch.sys.platform", "win32")
    session = FakeSession()
    _configure_alpaca_session(session, use_system_trust_store=False)  # type: ignore[arg-type]
    assert session.mounts == []
    _configure_alpaca_session(session, use_system_trust_store=True)  # type: ignore[arg-type]
    assert session.mounts[0][0] == "https://"
