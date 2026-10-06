from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from common.market_context import MarketCompatibilityError
from database.repositories.instruments import (
    InstrumentAmbiguityError,
    InstrumentIdentityError,
    InstrumentRepository,
    assert_market_mic,
    build_instrument_uid,
)
from scripts.audit_us_instrument_mapping import build_report, classify_stock_metadata

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def engine():
    value = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ddl = """
    CREATE TABLE instruments (
        instrument_id INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_uid TEXT NOT NULL UNIQUE,
        market_code TEXT NOT NULL,
        exchange_mic TEXT,
        local_symbol TEXT NOT NULL,
        display_name TEXT,
        instrument_type TEXT NOT NULL,
        currency TEXT NOT NULL,
        listing_date DATE,
        delisting_date DATE,
        mapping_status TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        UNIQUE(exchange_mic, local_symbol)
    );
    CREATE TABLE instrument_provider_symbols (
        mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        provider_symbol TEXT NOT NULL,
        provider_exchange TEXT,
        valid_from DATE NOT NULL,
        valid_to DATE,
        is_primary BOOLEAN NOT NULL
    );
    CREATE TABLE instrument_status_history (
        status_id INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_id INTEGER NOT NULL,
        valid_from DATE NOT NULL,
        valid_to DATE,
        listing_status TEXT NOT NULL,
        trading_status TEXT NOT NULL,
        is_tradable BOOLEAN NOT NULL,
        is_special_treatment BOOLEAN NOT NULL,
        board_code TEXT,
        source TEXT NOT NULL,
        observed_at DATETIME NOT NULL,
        available_at DATETIME NOT NULL
    );
    """
    with value.begin() as conn:
        for statement in ddl.split(";"):
            if statement.strip():
                conn.exec_driver_sql(statement)
    yield value
    value.dispose()


@pytest.fixture
def repo(engine) -> InstrumentRepository:
    return InstrumentRepository(engine=engine)


def _create(
    repo: InstrumentRepository,
    symbol: str,
    mic: str = "XNAS",
    identity: str | None = None,
) -> int:
    return repo.create_instrument(
        market_code="US_EQ",
        exchange_mic=mic,
        local_symbol=symbol,
        canonical_identity=identity or f"test:{mic}:{symbol}",
        currency="USD",
        listing_date="2020-01-01",
    )


def test_same_local_symbol_can_exist_on_two_mics(repo: InstrumentRepository) -> None:
    first = _create(repo, "ABC", "XNAS", "security-one")
    second = _create(repo, "ABC", "XNYS", "security-two")

    assert first != second
    assert repo.resolve_instrument("US_EQ", "XNAS", "ABC")["instrument_id"] == first
    assert repo.resolve_instrument("US_EQ", "XNYS", "ABC")["instrument_id"] == second
    with pytest.raises(InstrumentAmbiguityError, match="local symbol"):
        repo.resolve_local_symbol("US_EQ", "ABC")


def test_local_symbol_bridge_resolves_unique_instrument(repo: InstrumentRepository) -> None:
    instrument_id = _create(repo, "UNIQUE")
    resolved = repo.resolve_local_symbol("US_EQ", " unique ")
    assert resolved is not None
    assert resolved["instrument_id"] == instrument_id


def test_provider_ticker_change_resolves_as_of(repo: InstrumentRepository) -> None:
    instrument_id = _create(repo, "NEW")
    repo.add_provider_symbol(
        instrument_id=instrument_id,
        provider="alpaca",
        provider_symbol="OLD",
        valid_from="2020-01-01",
        valid_to="2021-12-31",
    )
    repo.add_provider_symbol(
        instrument_id=instrument_id,
        provider="alpaca",
        provider_symbol="NEW",
        valid_from="2022-01-01",
    )

    assert repo.resolve_provider_symbol("alpaca", "OLD", "2021-06-01")["instrument_id"] == instrument_id
    assert repo.resolve_provider_symbol("alpaca", "OLD", "2022-06-01") is None
    assert repo.resolve_provider_symbol("alpaca", "NEW", "2022-06-01")["instrument_id"] == instrument_id


def test_distinct_provider_symbols_map_to_same_instrument(
    repo: InstrumentRepository,
) -> None:
    instrument_id = _create(repo, "BABA")
    mappings = {
        "alpaca": "BABA",
        "eodhd": "BABA.US",
        "tushare": "9988.HK",
    }
    for provider, symbol in mappings.items():
        repo.add_provider_symbol(
            instrument_id=instrument_id,
            provider=provider,
            provider_symbol=symbol,
            valid_from="2020-01-01",
        )

    for provider, symbol in mappings.items():
        assert repo.resolve_provider_symbol(provider, symbol, date(2024, 1, 2))["instrument_id"] == instrument_id


def test_overlapping_provider_symbol_is_rejected(repo: InstrumentRepository) -> None:
    first = _create(repo, "AAA")
    second = _create(repo, "BBB")
    repo.add_provider_symbol(
        instrument_id=first,
        provider="alpaca",
        provider_symbol="SHARED",
        valid_from="2020-01-01",
    )
    with pytest.raises(InstrumentIdentityError, match="chevauchante"):
        repo.add_provider_symbol(
            instrument_id=second,
            provider="alpaca",
            provider_symbol="SHARED",
            valid_from="2021-01-01",
        )


def test_two_overlapping_primary_mappings_are_rejected(
    repo: InstrumentRepository,
) -> None:
    instrument_id = _create(repo, "AAA")
    repo.add_provider_symbol(
        instrument_id=instrument_id,
        provider="eodhd",
        provider_symbol="AAA.US",
        valid_from="2020-01-01",
    )
    with pytest.raises(InstrumentIdentityError, match="Deux mappings primaires"):
        repo.add_provider_symbol(
            instrument_id=instrument_id,
            provider="eodhd",
            provider_symbol="AAA.XNAS",
            valid_from="2021-01-01",
        )


def test_non_primary_alias_can_overlap_primary(repo: InstrumentRepository) -> None:
    instrument_id = _create(repo, "AAA")
    repo.add_provider_symbol(
        instrument_id=instrument_id,
        provider="eodhd",
        provider_symbol="AAA.US",
        valid_from="2020-01-01",
    )
    alias_id = repo.add_provider_symbol(
        instrument_id=instrument_id,
        provider="eodhd",
        provider_symbol="AAA",
        valid_from="2020-01-01",
        is_primary=False,
    )
    assert alias_id > 0


def test_status_is_resolved_as_of(repo: InstrumentRepository, engine) -> None:
    instrument_id = _create(repo, "AAA")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO instrument_status_history (
                    instrument_id, valid_from, valid_to, listing_status,
                    trading_status, is_tradable, is_special_treatment,
                    board_code, source, observed_at, available_at
                ) VALUES
                (:id, '2020-01-01', '2022-12-31', 'listed', 'active',
                 TRUE, FALSE, NULL, 'alpaca', :ts, :ts),
                (:id, '2023-01-01', NULL, 'listed', 'suspended',
                 FALSE, FALSE, NULL, 'alpaca', :ts, :ts)
                """
            ),
            {"id": instrument_id, "ts": datetime(2023, 1, 1)},
        )

    assert repo.load_status_asof(instrument_id, "2022-06-01")["trading_status"] == "active"
    assert repo.load_status_asof(instrument_id, "2024-06-01")["trading_status"] == "suspended"


def test_list_instruments_is_market_and_date_scoped(
    repo: InstrumentRepository,
) -> None:
    _create(repo, "AAA", "XNAS")
    _create(repo, "BBB", "XNYS")
    rows = repo.list_instruments(
        "US_EQ",
        "2024-01-01",
        {"exchange_mic": "XNAS", "is_active": True},
    )
    assert [row["local_symbol"] for row in rows] == ["AAA"]
    with pytest.raises(InstrumentIdentityError, match="non supportés"):
        repo.list_instruments("US_EQ", "2024-01-01", {"unsafe_sql": "x"})


def test_market_mic_and_currency_are_checked(repo: InstrumentRepository) -> None:
    with pytest.raises(MarketCompatibilityError, match="incompatible"):
        assert_market_mic("CN_A", "XNAS")
    with pytest.raises(MarketCompatibilityError, match="currency"):
        repo.create_instrument(
            market_code="US_EQ",
            exchange_mic="XNAS",
            local_symbol="EURBAD",
            canonical_identity="bad-currency",
            currency="EUR",
        )
    with pytest.raises(MarketCompatibilityError, match="désactivé"):
        repo.create_instrument(
            market_code="CN_A",
            exchange_mic="XSHG",
            local_symbol="600000",
            canonical_identity="cn-disabled",
            currency="CNY",
        )


def test_uid_is_stable_and_market_scoped() -> None:
    first = build_instrument_uid("US_EQ", "XNAS", "provider-security-1")
    assert first == build_instrument_uid("US_EQ", "XNAS", "provider-security-1")
    assert first != build_instrument_uid("CN_A", "XSHG", "provider-security-1")


def test_dry_run_never_invents_unknown_or_otc_mic() -> None:
    unknown = classify_stock_metadata({"symbol": "ABC", "exchange": "MYSTERY", "company_name": "ABC"})
    otc = classify_stock_metadata({"symbol": "XYZ", "exchange": "OTC", "company_name": "XYZ"})
    assert unknown.mapping_status == "mapping_pending"
    assert unknown.exchange_mic is None
    assert "unknown_exchange" in unknown.flags
    assert otc.exchange_mic is None
    assert "otc" in otc.flags


def test_dry_run_reports_mapping_rate_and_ambiguities() -> None:
    report = build_report(
        [
            {"symbol": "AAA", "exchange": "NASDAQ", "company_name": "AAA Inc"},
            {"symbol": "BRK.B", "exchange": "NYSE", "company_name": "Berkshire"},
            {"symbol": "ADR", "exchange": None, "company_name": "Issuer ADR"},
        ]
    )
    assert report["total_symbols"] == 3
    assert report["mapped_symbols"] == 2
    assert report["mapping_pending_symbols"] == 1
    assert report["flag_counts"]["class_or_punctuated_symbol"] == 1
    assert report["flag_counts"]["possible_adr"] == 1
    assert report["policy"]["write_performed"] is False


def test_reference_sql_contains_six_idempotent_tables_and_constraints() -> None:
    sql_root = ROOT / "database" / "sql" / "market"
    expected = {
        "markets.sql",
        "instruments.sql",
        "instrument_provider_symbols.sql",
        "instrument_status_history.sql",
        "market_sessions.sql",
        "market_execution_rules.sql",
    }
    assert {path.name for path in sql_root.glob("*.sql")} == expected
    combined = "\n".join((sql_root / name).read_text(encoding="utf-8") for name in sorted(expected))
    assert combined.count("CREATE TABLE IF NOT EXISTS") == 6
    assert "uq_instruments_mic_symbol" in combined
    assert "fk_ips_instrument" in combined
    assert "ck_instruments_dates" in combined


def test_migration_is_idempotent_by_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    path = ROOT / "alembic" / "versions" / "0084_market_instrument_foundation.py"
    spec = importlib.util.spec_from_file_location("migration_0084", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    calls: list[str] = []
    fake_op = SimpleNamespace(
        execute=lambda statement: calls.append(str(statement)),
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="mysql")),
    )
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()
    first_count = len(calls)
    migration.upgrade()

    assert len(calls) == first_count * 2
    assert all("CREATE TABLE IF NOT EXISTS" in statement for statement in calls[:6])
    assert sum("INSERT IGNORE INTO markets" in statement for statement in calls) == 2
    assert sum("DROP TRIGGER IF EXISTS" in statement for statement in calls) == 4
