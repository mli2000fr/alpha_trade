from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from service.forward_pit import batch as batch_module
from service.forward_pit.batch import (
    HANDLERS,
    PENDING_BATCHES,
    _alpaca_opening_row,
    _apply_market_cap_coverage_policy,
    _assets_in_universe,
    _collection_symbols,
    _configure_alpaca_session,
    _data_blocks,
    _download_sec_document,
    _hash,
    _market_dt,
    _nearest_option_expirations,
    _option_contract_parts,
    _option_is_liquid,
    _paginated_json,
    _parse_finra_short_volume,
    _schema_hash,
    _sec_submission_header,
    _sec_filing_index_documents,
    _selected_sec_exhibits,
    _read_response_bytes_limited,
    _previous_weekdays,
    _safe_error_message,
    _security_changes,
    _select_option_surface_contracts,
    _underlying_price,
    daily_bars_sync,
    database_backup,
    latest_quotes_sync_batch,
    ml_artifacts_backup,
)

ROOT = Path(__file__).resolve().parents[1]


def test_all_enabled_forward_batches_have_handlers() -> None:
    expected = {
        "ml_artifacts_backup",
        "db_core_backup", "db_news_raw_backup",
        "daily_bars_sync", "market_cap_sync", "security_master_snapshot", "corporate_actions_sync",
        "sec_edgar_incremental", "pit_data_quality_daily", "borrow_status_snapshot",
        "business_quant_analyst_snapshot", "oracle_options_indicative_snapshot",
        "oracle_opening_window_sync", "sec_corporate_events_normalize",
        "sec_institutional_ownership_normalize", "fred_alfred_vintage_sync",
        "finra_short_volume_sync",
        "latest_quotes_sync",
        "options_delayed_bars_sync", "option_contract_adjustment_sync",
    }
    assert expected == set(HANDLERS)
    assert PENDING_BATCHES == {
        "auction_imbalance_sync", "securities_lending_sync",
        "official_options_nbbo_sync",
    }


def test_ml_artifacts_backup_uses_only_runtime_model_directory(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class Report:
        errors: list[str] = []
        artifacts_dir = str(tmp_path / "artifacts" / "models")
        dest_dir = str(tmp_path / "backups" / "ml")
        archive_path = str(tmp_path / "backups" / "ml" / "ml_artifacts_test.tar.gz")
        archive_size_bytes = 123
        rotated_files: list[str] = []
        kept_files = [archive_path]

    monkeypatch.setattr(
        "scripts.backup_ml_artifacts.backup",
        lambda **kwargs: captured.update(kwargs) or Report(),
    )
    monkeypatch.setattr(batch_module, "ROOT", tmp_path)
    outcome = ml_artifacts_backup(
        object(),
        {"artifacts_dir": "artifacts/models", "dest_dir": "backups/ml", "keep": 3},
        "backup-run",
        False,
    )
    assert captured["artifacts_dir"] == tmp_path / "artifacts" / "models"
    assert captured["dest_dir"] == tmp_path / "backups" / "ml"
    assert captured["keep"] == 3
    assert outcome.persisted == 1
    assert outcome.details["excluded_non_runtime_paths"] == ["catboost_info"]


def test_database_backup_forwards_table_scope_and_retention(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class Report:
        errors: list[str] = []
        host = "localhost"
        db = "alpha_trade"
        dest_dir = str(tmp_path / "backups" / "db")
        dump_path = str(tmp_path / "backups" / "db" / "alpha_trade_news_raw_test.sql.gz")
        dump_size_bytes = 123
        archive_prefix = "alpha_trade_news_raw"
        include_tables = ["news_raw"]
        exclude_tables: list[str] = []
        rotated_files: list[str] = []
        kept_files = [dump_path]

    monkeypatch.setattr(
        "scripts.backup_db.backup_db",
        lambda **kwargs: captured.update(kwargs) or Report(),
    )
    monkeypatch.setattr(batch_module, "ROOT", tmp_path)
    outcome = database_backup(
        object(),
        {
            "dest_dir": "backups/db", "keep": 3,
            "archive_prefix": "alpha_trade_news_raw",
            "include_tables": "news_raw", "include_routines": False,
        },
        "db-backup-run",
        False,
    )

    assert captured["dest_dir"] == tmp_path / "backups" / "db"
    assert captured["include_tables"] == ["news_raw"]
    assert captured["exclude_tables"] == []
    assert captured["include_routines"] is False
    assert captured["keep"] == 3
    assert outcome.persisted == 1


def test_latest_quotes_batch_delegates_to_idempotent_historical_sync(monkeypatch) -> None:
    captured: dict[str, object] = {}
    audits: list[dict[str, object]] = []

    monkeypatch.setattr(batch_module, "_collection_symbols", lambda _cfg: ["AAPL", "MSFT"])
    monkeypatch.setattr(
        "dataIntegrityEngine.sync_latest_quotes.sync_latest_quotes",
        lambda **kwargs: captured.update(kwargs) or {"symbols": 2, "rows_upserted": 4},
    )
    monkeypatch.setattr(
        "database.cleaning_audits.record_quotes_audit_run",
        lambda **kwargs: audits.append(kwargs),
    )

    outcome = latest_quotes_sync_batch(
        object(),
        {
            "symbols_file": "config/univers_batch/univers_filtred_tradable.txt",
            "lookback_days": 7,
            "batch_size": 200,
            "timezone": "America/New_York",
        },
        "latest-quotes-run",
        False,
    )

    assert captured["batch_size"] == 200
    assert captured["symbol_source"] == (
        "universe-file:config/univers_batch/univers_filtred_tradable.txt"
    )
    assert (captured["to_date"] - captured["from_date"]).days == 7
    assert outcome.requested == 2
    assert outcome.received == 4
    assert outcome.persisted == 4
    assert outcome.failed == 0
    assert audits[0]["status"] == "success"


def test_market_cap_sync_uses_targeted_sec_yahoo_finnhub_fallbacks(monkeypatch) -> None:
    from modelFactory import fundamental_features

    monkeypatch.setattr(batch_module, "_symbols", lambda _cfg: ["AAA", "BBB", "CCC"])

    calls: list[tuple[str, list[str]]] = []

    def fetch(_symbols, *, engine, provider, **_kwargs):
        assert engine is not None
        calls.append((provider, list(_symbols)))
        return {"stored": len(_symbols), "failed": 0, "errors": []}

    def covered(_engine, symbols, _as_of, _max_age, sources):
        if sources == ("SEC_EDGAR",):
            return {"AAA", "BBB"}
        if sources == ("YAHOO FINANCE",):
            return set()
        if sources == ("FINNHUB",):
            return set(symbols)
        raise AssertionError(sources)

    monkeypatch.setattr(fundamental_features, "fetch_and_store_fundamentals", fetch)
    monkeypatch.setattr(batch_module, "_market_cap_covered_symbols", covered)
    outcome = batch_module.market_cap_sync(
        object(),
        {
            "primary_provider": "sec",
            "fallback_providers": "yahoo_finance,finnhub",
            "min_coverage_ratio": 0.99,
        },
        "market-cap-run",
        False,
    )

    assert calls == [
        ("sec", ["AAA", "BBB", "CCC"]),
        ("yahoo_finance", ["CCC"]),
        ("finnhub", ["CCC"]),
    ]
    assert outcome.requested == 3
    assert outcome.received == 3
    assert outcome.persisted == 5
    assert outcome.failed == 0
    assert outcome.warnings == []
    assert outcome.details["strategy"] == "sec_edgar_then_yahoo_then_finnhub"
    assert outcome.details["providers"]["sec"]["eligible_symbols"] == 2


def test_market_cap_accepted_coverage_keeps_gaps_as_diagnostics_only() -> None:
    outcome = batch_module.Outcome(requested=100, received=95, empty=5)
    _apply_market_cap_coverage_policy(
        outcome, [f"MISS{i}" for i in range(5)], 0.95, 0.95,
    )
    assert outcome.failed == 0
    assert outcome.warnings == []


def test_market_cap_below_coverage_threshold_is_blocking() -> None:
    outcome = batch_module.Outcome(requested=100, received=94, empty=6)
    with pytest.raises(batch_module.BatchRunError, match="94.00% < 95.00%"):
        _apply_market_cap_coverage_policy(
            outcome, [f"MISS{i}" for i in range(6)], 0.94, 0.95,
        )
    assert outcome.failed == 6


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


def test_previous_weekdays_exclude_current_date_and_weekends() -> None:
    # Sunday 2026-09-13: inspect Friday, Thursday and Wednesday, never Sunday/Saturday.
    assert _previous_weekdays(datetime(2026, 9, 13).date(), 3) == [
        datetime(2026, 9, 11).date(),
        datetime(2026, 9, 10).date(),
        datetime(2026, 9, 9).date(),
    ]


def test_previous_weekdays_keep_requested_business_day_depth() -> None:
    # Monday must cross the weekend to retain the configured number of candidates.
    assert _previous_weekdays(datetime(2026, 9, 14).date(), 2) == [
        datetime(2026, 9, 11).date(),
        datetime(2026, 9, 10).date(),
    ]


def test_sec_incremental_skips_unpublished_index_and_processes_available_one(monkeypatch) -> None:
    index_dates = [
        datetime(2026, 9, 11).date(),
        datetime(2026, 9, 10).date(),
    ]
    monkeypatch.setattr(batch_module, "_previous_weekdays", lambda *_args: index_dates)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "alpha-trade test@example.com")

    class Result:
        @staticmethod
        def fetchall():
            return []

        def mappings(self):
            return self

        @staticmethod
        def first():
            return None

    class Connection:
        @staticmethod
        def execute(*_args, **_kwargs):
            return Result()

    class Begin:
        @staticmethod
        def __enter__():
            return Connection()

        @staticmethod
        def __exit__(*_args):
            return False

    class Engine:
        @staticmethod
        def begin():
            return Begin()

        @staticmethod
        def connect():
            return Begin()

    class Response:
        def __init__(self, status_code: int, text: str = ""):
            self.status_code = status_code
            self.text = text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected HTTP {self.status_code}")

    available = (
        "header\n--------------------------------------------------------------------------------\n"
        "1234|Example Corp|8-K|2026-09-10|edgar/data/1234/000000123426000001/a.txt\n"
    )

    class Session:
        @staticmethod
        def __enter__():
            return Session()

        @staticmethod
        def __exit__(*_args):
            return False

        @staticmethod
        def get(url, **_kwargs):
            return Response(403) if "20260911" in url else Response(200, available)

    monkeypatch.setattr(batch_module.requests, "Session", Session)
    outcome = batch_module.sec_edgar_incremental(
        Engine(),
        {"lookback_days": 2, "forms": "8-K", "download_primary_documents": True},
        "sec-run",
        True,
    )

    assert outcome.requested == 2
    assert outcome.received == 1
    assert outcome.failed == 0
    assert outcome.details["accessible_indexes"] == 1
    assert outcome.details["unavailable_indexes"] == [
        {"date": "2026-09-11", "status": 403}
    ]
    assert outcome.warnings == [
        "Index SEC non encore disponible: 2026-09-11 (HTTP 403)"
    ]


def test_sec_submission_header_finds_acceptance_and_expected_primary_document() -> None:
    prefix = """<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20260911081822\n</SEC-HEADER>
<DOCUMENT>\n<TYPE>EX-99.1\n<SEQUENCE>2\n<FILENAME>exhibit.htm\n<TEXT>
<DOCUMENT>\n<TYPE>8-K\n<SEQUENCE>1\n<FILENAME>aa-20260911.htm\n<TEXT>"""
    acceptance, primary = _sec_submission_header(prefix, "8-K")
    assert acceptance == datetime(2026, 9, 11, 8, 18, 22)
    assert primary == "aa-20260911.htm"


def test_sec_filing_index_selects_only_configured_ex99_exhibits() -> None:
    index_html = """
    <table>
      <tr><td>1</td><td>FORM 8-K</td><td><a href="main.htm">main.htm</a></td><td>8-K</td><td>1,024</td></tr>
      <tr><td>3</td><td>Press release</td><td><a href="release.htm">release.htm</a></td><td>EX-99.1</td><td>2,048</td></tr>
      <tr><td>2</td><td>Presentation</td><td><a href="slides.pdf">slides.pdf</a></td><td>EX-99.2</td><td>3,072</td></tr>
      <tr><td>4</td><td>Contract</td><td><a href="contract.htm">contract.htm</a></td><td>EX-10.1</td><td>4,096</td></tr>
    </table>
    """
    documents = _sec_filing_index_documents(
        index_html, "https://www.sec.gov/Archives/edgar/data/1/2",
    )
    selected = _selected_sec_exhibits(documents, ("EX-99",), 10)
    assert [item["document_type"] for item in selected] == ["EX-99.2", "EX-99.1"]
    assert selected[0]["url"].endswith("/slides.pdf")
    assert selected[1]["declared_size"] == 2048


def test_sec_exhibit_binary_reader_rejects_oversized_payload() -> None:
    class Response:
        headers = {"Content-Length": "100"}

        @staticmethod
        def iter_content(chunk_size=65536):
            del chunk_size
            yield b"x" * 100

    body, size = _read_response_bytes_limited(Response(), 50)
    assert body is None
    assert size == 100


def test_oversized_sec_submission_falls_back_to_bounded_primary_document() -> None:
    prefix = b"""<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20260911081822\n</SEC-HEADER>
<DOCUMENT>\n<TYPE>8-K\n<SEQUENCE>1\n<FILENAME>primary.htm\n<TEXT>"""

    class Response:
        encoding = "utf-8"

        def __init__(self, body: bytes, declared: int):
            self.body = body
            self.headers = {"Content-Length": str(declared)}
            self.closed = False

        @staticmethod
        def raise_for_status():
            return None

        def iter_content(self, chunk_size=65536):
            del chunk_size
            yield self.body

        def close(self):
            self.closed = True

    submission = Response(prefix, 96_533_876)
    primary = Response(b"<html>primary filing</html>", 27)

    class Session:
        def __init__(self):
            self.urls = []

        def get(self, url, **_kwargs):
            self.urls.append(url)
            return submission if len(self.urls) == 1 else primary

    session = Session()
    result = _download_sec_document(
        session,
        "https://www.sec.gov/Archives/edgar/data/1/submission.txt",
        "8-K",
        {"User-Agent": "test test@example.com"},
        max_submission_bytes=1024,
        max_primary_document_bytes=1024,
        probe_bytes=1024,
    )
    assert result["content"] == "<html>primary filing</html>"
    assert result["primary_document"] == "primary.htm"
    assert result["content_url"].endswith("/primary.htm")
    assert result["used_primary_fallback"] is True
    assert result["oversized_primary"] is False
    assert submission.closed and primary.closed


def test_forward_pit_sql_reference_and_migration_cover_all_tables() -> None:
    ddl = (ROOT / "database/sql/forward_pit/forward_pit_tables.sql").read_text(encoding="utf-8")
    expected = {
        "pit_collection_runs", "pit_raw_payloads", "stock_bars_daily_versions",
        "security_master_snapshots", "security_master_changes",
        "corporate_action_source_events", "sec_filing_raw", "sec_filing_documents",
        "stock_borrow_status_snapshots", "stock_analyst_consensus_snapshots",
        "stock_option_snapshots", "stock_opening_window_bars",
        "stock_opening_window_bar_versions", "sec_corporate_events",
        "sec_ownership_snapshots", "macro_vintage_observations",
        "pit_data_quality_metrics", "pit_data_quality_issues",
        "stock_short_volume_daily",
        "stock_option_contract_versions", "stock_option_bars_delayed",
        "option_contract_adjustments",
    }
    assert {name for name in expected if f"alpha_trade.{name}" in ddl} == expected
    migration = (ROOT / "alembic/versions/0075_forward_pit_collection_foundation.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0074_fundamental_pit_contract"' in migration
    finra_migration = (ROOT / "alembic/versions/0076_finra_short_volume_daily.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0075_forward_pit_collection"' in finra_migration
    opening_migration = (ROOT / "alembic/versions/0078_alpaca_opening_window_pit.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0077_yahoo_analyst_trends"' in opening_migration

    options_migration = (ROOT / "alembic/versions/0079_delayed_options_and_occ_adjustments.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0078_alpaca_opening_window_pit"' in options_migration

    provider_migration = (
        ROOT / "alembic/versions/0080_widen_pit_collection_run_provider.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0079_delayed_options_occ"' in provider_migration
    assert "type_=sa.String(255)" in provider_migration
    assert ddl.count("provider VARCHAR(255)") == 18
    assert "provider VARCHAR(32)" not in ddl
    assert "provider VARCHAR(16)" not in ddl

    all_provider_migration = (
        ROOT / "alembic/versions/0081_widen_forward_pit_providers.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0080_widen_pit_run_provider"' in all_provider_migration

    exhibit_migration = (
        ROOT / "alembic/versions/0082_sec_filing_documents.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0081_widen_forward_pit_providers"' in exhibit_migration
    assert "mysql.LONGBLOB()" in exhibit_migration


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
    assert "--passage $passage" in launcher



def test_forward_launcher_captures_native_stderr_without_error_records() -> None:
    launcher = (ROOT / "scripts/windows/forward_pit_launcher.ps1").read_text(
        encoding="utf-8"
    )
    assert "$batchProcess = Start-Process" in launcher
    assert "-RedirectStandardOutput $stdoutTmp" in launcher
    assert "-RedirectStandardError $stderrTmp" in launcher


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


def test_alpaca_opening_bar_maps_minute_volume_trade_count_vwap_and_session() -> None:
    observed = datetime(2026, 9, 11, 14, 50)
    row = _alpaca_opening_row(
        "AAPL",
        {"t": "2026-09-11T13:31:00Z", "o": 100, "h": 102, "l": 99,
         "c": 101, "v": 1234, "n": 87, "vw": 100.8},
        observed=observed, cumulative_volume=4321, run_id="run",
        feed="sip", adjustment="raw",
    )
    assert row["minute"] == 1234
    assert row["cum"] == 4321
    assert row["trade_count"] == 87
    assert row["vwap"] == 100.8
    assert row["session"] == "OPEN"
    assert row["available"] == observed
    assert row["provider"] == "alpaca"


def test_alpaca_opening_bar_classifies_premarket_in_new_york() -> None:
    row = _alpaca_opening_row(
        "AAPL",
        {"t": "2026-09-11T08:15:00Z", "o": 100, "h": 100, "l": 100,
         "c": 100, "v": 1, "n": 1, "vw": 100},
        observed=datetime(2026, 9, 11, 14, 50), cumulative_volume=1,
        run_id="run", feed="sip", adjustment="raw",
    )
    assert row["session"] == "PRE"


def test_opening_window_catchup_skips_complete_sessions(monkeypatch) -> None:
    sessions = [date(2026, 9, 10), date(2026, 9, 11)]
    fetched: list[str] = []
    monkeypatch.setattr(batch_module, "_collection_symbols", lambda _cfg: ["AAPL", "MSFT"])
    monkeypatch.setattr(batch_module, "nyse_session_dates", lambda _start, _end: sessions)
    monkeypatch.setattr(
        batch_module,
        "_opening_window_session_complete",
        lambda _engine, _cfg, session_date, _count: session_date == sessions[0],
    )

    def fake_single(_engine, cfg, _run_id, _dry):
        fetched.append(cfg["_session_date"])
        return batch_module.Outcome(requested=2, received=6, persisted=6)

    monkeypatch.setattr(batch_module, "_opening_window_single_session", fake_single)
    outcome = batch_module.opening_window_sync(
        object(), {"timezone": "America/New_York", "lookback_days": 7}, "run", False,
    )

    assert fetched == ["2026-09-11"]
    assert outcome.requested == 2
    assert outcome.persisted == 6
    assert outcome.details["sessions_skipped_existing"] == ["2026-09-10"]


def _summary_from_stdout(stdout: str) -> dict:
    marker = "::alpha_trade_run_summary::"
    line = next(item for item in stdout.splitlines() if marker in item)
    return json.loads(line.split(marker, 1)[1])


def test_main_emits_normalized_success_summary(monkeypatch, capsys) -> None:
    outcome = batch_module.Outcome(
        requested=10,
        received=9,
        persisted=8,
        failed=1,
        warnings=["quota"],
    )
    monkeypatch.setattr(batch_module, "execute", lambda *args, **kwargs: ("COMPLETED", outcome))
    monkeypatch.setattr(
        batch_module.sys,
        "argv",
        ["service.forward_pit.batch", "--batch", "daily_bars_sync"],
    )
    batch_module.main()
    summary = _summary_from_stdout(capsys.readouterr().out)
    assert summary["status"] == "COMPLETED"
    assert summary["requested"] == 10
    assert len(summary["warnings"]) == 1


def test_main_emits_normalized_failure_summary(monkeypatch, capsys) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(batch_module, "execute", fail)
    monkeypatch.setattr(
        batch_module.sys,
        "argv",
        ["service.forward_pit.batch", "--batch", "daily_bars_sync"],
    )
    with pytest.raises(RuntimeError, match="provider unavailable"):
        batch_module.main()
    summary = _summary_from_stdout(capsys.readouterr().out)
    assert summary["status"] == "FAILED"
    assert summary["failed"] == 1
    assert summary["error_message"] == "provider unavailable"


def test_quality_failed_runs_check_excludes_its_own_failures(monkeypatch) -> None:
    statements: list[str] = []

    class Result:
        @staticmethod
        def scalar():
            return 0

    class Connection:
        def execute(self, statement, _params=None):
            statements.append(str(statement))
            return Result()

    class Begin:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Engine:
        @staticmethod
        def begin():
            return Begin()

    monkeypatch.setattr(batch_module, "_symbols", lambda _cfg: [])
    outcome = batch_module.quality_daily(
        Engine(), {"fail_on_critical": True}, "quality-run", True
    )
    assert outcome.failed == 0
    failed_runs_query = next(sql for sql in statements if "failed_runs_24h" not in sql and "INTERVAL 24 HOUR" in sql)
    assert "batch_name <> 'pit_data_quality_daily'" in failed_runs_query
    assert "MAX(started_at)" in failed_runs_query
    assert "current_run.status='FAILED'" in failed_runs_query


def test_http_error_message_redacts_query_credentials() -> None:
    message = _safe_error_message(
        RuntimeError("400 url=https://example.test?a=1&api_key=very-secret&series=x")
    )
    assert "very-secret" not in message
    assert "api_key=***" in message


def test_main_preserves_quality_failure_counters(monkeypatch, capsys) -> None:
    outcome = batch_module.Outcome(
        requested=6,
        received=6,
        persisted=6,
        failed=3,
        warnings=["one warning"],
        details={
            "critical": 3,
            "critical_checks": [
                {"name": "borrow_age_hours", "value": None, "threshold": 30.0}
            ],
        },
    )

    def fail(*_args, **_kwargs):
        raise batch_module.BatchRunError("3 contrôles PIT critiques en échec", outcome)

    monkeypatch.setattr(batch_module, "execute", fail)
    monkeypatch.setattr(
        batch_module.sys,
        "argv",
        ["service.forward_pit.batch", "--batch", "pit_data_quality_daily"],
    )
    with pytest.raises(batch_module.BatchRunError):
        batch_module.main()
    summary = _summary_from_stdout(capsys.readouterr().out)
    assert summary["requested"] == 6
    assert summary["received"] == 6
    assert summary["persisted"] == 6
    assert summary["failed"] == 3
    assert summary["warning_count"] == 1
    assert (
        summary["details"]["critical_checks"][0]["name"]
        == "borrow_age_hours"
    )


def test_execute_persists_counters_from_blocking_quality_failure(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    class Connection:
        def execute(self, statement, params=None):
            calls.append((str(statement), params))
            return object()

    connection = Connection()

    class Begin:
        def __enter__(self):
            return connection

        def __exit__(self, *_args):
            return False

    class Engine:
        @staticmethod
        def begin():
            return Begin()

    outcome = batch_module.Outcome(
        requested=6,
        received=6,
        persisted=6,
        failed=3,
        warnings=["warning"],
        details={"critical": 3},
    )

    def handler(*_args, **_kwargs):
        raise batch_module.BatchRunError("quality failure", outcome)

    monkeypatch.setattr(
        batch_module,
        "load_batch_config",
        lambda _path=None: {"test_quality": {"enabled": True, "provider": "local"}},
    )
    monkeypatch.setattr(batch_module, "get_sqlalchemy_engine", lambda: Engine())
    monkeypatch.setitem(batch_module.HANDLERS, "test_quality", handler)

    with pytest.raises(batch_module.BatchRunError):
        batch_module.execute("test_quality")

    _, params = next(
        call for call in calls
        if "SET status='FAILED'" in call[0]
    )
    assert params is not None
    assert params["requested"] == 6
    assert params["received"] == 6
    assert params["persisted"] == 6
    assert params["failed"] == 3
    assert json.loads(params["details"])["critical"] == 3
