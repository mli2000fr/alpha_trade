"""Tests unitaires et d'intégration pour le module corporate_actions."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from corporate_actions.db_io import CorporateActionRepository
from corporate_actions.engine import CorporateActionEngine
from corporate_actions.models import (
    CaStatus,
    CaType,
    CorporateActionEvent,
    PositionSnapshot,
)
from corporate_actions.processors import process_dividend, process_split
from corporate_actions.provider import CorporateActionProvider
from corporate_actions.reconciliation import reconcile_after_corporate_actions


# =====================================================================
# Fixtures
# =====================================================================

SQLITE_SCHEMA = """
    CREATE TABLE corporate_actions_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key VARCHAR(64) UNIQUE NOT NULL,
        provider VARCHAR(30) NOT NULL,
        provider_event_id VARCHAR(128),
        symbol VARCHAR(20) NOT NULL,
        ca_type VARCHAR(30) NOT NULL,
        amount_per_share DOUBLE,
        split_from INT,
        split_to INT,
        currency VARCHAR(5) DEFAULT 'USD',
        announcement_date DATE,
        ex_date DATE NOT NULL,
        record_date DATE,
        payable_date DATE,
        raw_payload TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        error_message VARCHAR(500),
        ingested_at TIMESTAMP,
        applied_at TIMESTAMP
    );
    CREATE TABLE corporate_actions_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id BIGINT NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        ca_type VARCHAR(30) NOT NULL,
        position_qty_before DOUBLE NOT NULL,
        position_qty_after DOUBLE NOT NULL,
        cost_basis_before DOUBLE,
        cost_basis_after DOUBLE,
        cash_impact DOUBLE DEFAULT 0,
        fractional_shares DOUBLE DEFAULT 0,
        applied_at TIMESTAMP
    );
    CREATE TABLE portfolio_cash_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id BIGINT,
        symbol VARCHAR(20) NOT NULL,
        entry_type VARCHAR(30) NOT NULL,
        amount DOUBLE NOT NULL,
        currency VARCHAR(5) DEFAULT 'USD',
        description VARCHAR(255),
        created_at TIMESTAMP
    );
    CREATE TABLE broker_positions_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exec_run_id VARCHAR(32),
        broker_mode VARCHAR(10),
        symbol VARCHAR(20),
        qty DOUBLE DEFAULT 0,
        avg_entry_price DOUBLE DEFAULT 0,
        market_value DOUBLE DEFAULT 0,
        unrealized_pnl DOUBLE DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


@pytest.fixture()
def engine():
    e = create_engine("sqlite:///:memory:")
    with e.begin() as conn:
        for stmt in SQLITE_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return e


@pytest.fixture()
def repo(engine):
    return CorporateActionRepository(engine=engine)


def _make_dividend_event(
    symbol: str = "AAPL",
    amount: float = 0.25,
    ex_date: date = date(2026, 4, 10),
) -> CorporateActionEvent:
    return CorporateActionEvent(
        provider="alpaca",
        provider_event_id="div-001",
        symbol=symbol,
        ca_type=CaType.CASH_DIVIDEND,
        amount_per_share=amount,
        ex_date=ex_date,
    )


def _make_split_event(
    symbol: str = "NVDA",
    split_from: int = 1,
    split_to: int = 2,
    ca_type: str = CaType.SPLIT,
    ex_date: date = date(2026, 4, 15),
) -> CorporateActionEvent:
    return CorporateActionEvent(
        provider="alpaca",
        provider_event_id="spl-001",
        symbol=symbol,
        ca_type=ca_type,
        split_from=split_from,
        split_to=split_to,
        ex_date=ex_date,
    )


def _make_position(symbol: str = "AAPL", qty: float = 100, price: float = 150.0) -> PositionSnapshot:
    return PositionSnapshot(symbol=symbol, qty=qty, avg_entry_price=price)


# =====================================================================
# Tests unitaires — Processeurs
# =====================================================================

class TestDividendProcessor:
    """Tests pour le calcul de dividende cash."""

    def test_basic_dividend(self):
        event = _make_dividend_event(amount=0.25)
        event.id = 1
        pos = _make_position(qty=100)
        app, ledger = process_dividend(event, pos)

        assert app.cash_impact == 25.0
        assert app.position_qty_before == 100
        assert app.position_qty_after == 100  # qty inchangée
        assert app.cost_basis_before == 150.0
        assert app.cost_basis_after == 150.0  # cost basis inchangé
        assert ledger.amount == 25.0
        assert ledger.entry_type == "dividend_credit"

    def test_dividend_fractional_qty(self):
        event = _make_dividend_event(amount=0.33)
        event.id = 2
        pos = _make_position(qty=57.5)
        app, ledger = process_dividend(event, pos)

        expected = round(57.5 * 0.33, 2)  # 18.975 → 18.98
        assert app.cash_impact == expected
        assert ledger.amount == expected

    def test_dividend_large_position(self):
        event = _make_dividend_event(amount=1.50)
        event.id = 3
        pos = _make_position(qty=10000)
        app, _ = process_dividend(event, pos)
        assert app.cash_impact == 15000.0


class TestSplitProcessor:
    """Tests pour splits et reverse splits."""

    def test_split_2_1(self):
        event = _make_split_event(split_from=1, split_to=2)
        event.id = 10
        pos = _make_position(symbol="NVDA", qty=50, price=800.0)
        app, ledger = process_split(event, pos)

        assert app.position_qty_after == 100
        assert app.cost_basis_after == 400.0
        assert app.fractional_shares == 0.0
        assert ledger is None  # pas de cash-in-lieu

    def test_split_4_1(self):
        event = _make_split_event(split_from=1, split_to=4)
        event.id = 11
        pos = _make_position(symbol="NVDA", qty=25, price=1200.0)
        app, _ = process_split(event, pos)

        assert app.position_qty_after == 100
        assert app.cost_basis_after == 300.0

    def test_reverse_split_1_10(self):
        """Reverse split 1:10 → qty÷10, cost×10."""
        event = _make_split_event(
            symbol="XYZ", split_from=10, split_to=1,
            ca_type=CaType.REVERSE_SPLIT,
        )
        event.id = 12
        pos = _make_position(symbol="XYZ", qty=100, price=5.0)
        app, ledger = process_split(event, pos)

        assert app.position_qty_after == 10
        assert app.cost_basis_after == 50.0
        assert app.fractional_shares == 0.0
        assert ledger is None

    def test_reverse_split_with_fraction(self):
        """Reverse split 1:10 avec fraction → cash-in-lieu."""
        event = _make_split_event(
            symbol="XYZ", split_from=10, split_to=1,
            ca_type=CaType.REVERSE_SPLIT,
        )
        event.id = 13
        pos = _make_position(symbol="XYZ", qty=105, price=5.0)
        app, ledger = process_split(event, pos)

        # 105 / 10 = 10.5 → floor=10, fractional=0.5
        assert app.position_qty_after == 10
        assert app.fractional_shares == pytest.approx(0.5, abs=0.01)
        assert ledger is not None
        assert ledger.entry_type == "cash_in_lieu"
        assert ledger.amount == round(0.5 * 5.0, 2)  # 2.50

    def test_split_value_conservation(self):
        """La valeur totale de la position reste identique après un split."""
        event = _make_split_event(split_from=1, split_to=3)
        event.id = 14
        pos = _make_position(symbol="TST", qty=60, price=300.0)
        value_before = pos.qty * pos.avg_entry_price
        app, _ = process_split(event, pos)
        value_after = app.position_qty_after * (app.cost_basis_after or 0)
        assert value_after == pytest.approx(value_before, rel=1e-4)


# =====================================================================
# Tests — Modèles
# =====================================================================

class TestCorporateActionEvent:

    def test_idempotency_key_deterministic(self):
        e1 = _make_dividend_event()
        e2 = _make_dividend_event()
        assert e1.idempotency_key == e2.idempotency_key

    def test_idempotency_key_unique_per_symbol(self):
        e1 = _make_dividend_event(symbol="AAPL")
        e2 = _make_dividend_event(symbol="MSFT")
        assert e1.idempotency_key != e2.idempotency_key

    def test_validation_valid_dividend(self):
        e = _make_dividend_event()
        assert e.validate() == []

    def test_validation_invalid_dividend_amount(self):
        e = _make_dividend_event(amount=-1.0)
        errors = e.validate()
        assert len(errors) == 1
        assert "amount_per_share" in errors[0]

    def test_validation_invalid_split_zero(self):
        e = _make_split_event(split_from=0)
        errors = e.validate()
        assert len(errors) > 0

    def test_split_ratio(self):
        e = _make_split_event(split_from=1, split_to=4)
        assert e.split_ratio == 4.0

    def test_reverse_split_ratio(self):
        e = _make_split_event(split_from=10, split_to=1)
        assert e.split_ratio == 0.1


# =====================================================================
# Tests d'intégration — DB (SQLite in-memory)
# =====================================================================

class TestDbIntegration:

    def test_insert_and_load_pending(self, repo):
        event = _make_dividend_event()
        row_id = repo.insert_event_sqlite(event)
        assert row_id > 0

        pending = repo.load_pending_events()
        assert len(pending) == 1
        assert pending[0].symbol == "AAPL"
        assert pending[0].ca_type == CaType.CASH_DIVIDEND

    def test_idempotence_insert(self, repo):
        """Le même événement inséré deux fois ne doit pas créer de doublon."""
        event = _make_dividend_event()
        id1 = repo.insert_event_sqlite(event)
        id2 = repo.insert_event_sqlite(event)
        assert id1 > 0
        assert id2 == -1  # doublon

        pending = repo.load_pending_events()
        assert len(pending) == 1

    def test_mark_applied(self, repo):
        event = _make_dividend_event()
        row_id = repo.insert_event_sqlite(event)

        repo.mark_applied(row_id)
        pending = repo.load_pending_events()
        assert len(pending) == 0

        assert repo.is_event_applied(event.idempotency_key) is True

    def test_mark_failed(self, repo):
        event = _make_dividend_event()
        row_id = repo.insert_event_sqlite(event)
        repo.mark_failed(row_id, "test error")

        pending = repo.load_pending_events()
        assert len(pending) == 0  # failed ≠ pending

    def test_insert_application_and_ledger(self, repo):
        from corporate_actions.models import CashLedgerEntry, CorporateActionApplication

        event = _make_dividend_event()
        row_id = repo.insert_event_sqlite(event)

        app = CorporateActionApplication(
            event_id=row_id, symbol="AAPL", ca_type=CaType.CASH_DIVIDEND,
            position_qty_before=100, position_qty_after=100,
            cost_basis_before=150.0, cost_basis_after=150.0,
            cash_impact=25.0,
        )
        repo.insert_application(app)

        ledger = CashLedgerEntry(
            event_id=row_id, symbol="AAPL", entry_type="dividend_credit",
            amount=25.0, description="Test",
        )
        repo.insert_cash_ledger(ledger)

        total = repo.get_total_dividends(symbol="AAPL")
        assert total == 25.0


# =====================================================================
# Tests d'intégration — Engine (full flow)
# =====================================================================

class FakeProvider(CorporateActionProvider):
    """Provider factice pour les tests."""

    def __init__(self, events: list[CorporateActionEvent]) -> None:
        self._events = events

    def fetch_events(self, symbols=None, start_date=None, end_date=None):
        return self._events


class TestEngineIntegration:

    def _make_engine(self, repo, events) -> CorporateActionEngine:
        provider = FakeProvider(events)
        return CorporateActionEngine(provider=provider, repo=repo)

    def test_sync_and_apply_dividend(self, engine, repo):
        """Flow complet : sync → apply → vérification cash et idempotence."""
        event = _make_dividend_event()
        ca_engine = self._make_engine(repo, [event])

        # 1. Sync
        sync_stats = ca_engine.sync()
        assert sync_stats["inserted"] == 1

        # 2. Injecter une position broker snapshot
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO broker_positions_snapshots
                    (exec_run_id, broker_mode, symbol, qty, avg_entry_price, market_value, unrealized_pnl)
                VALUES ('run-001', 'paper', 'AAPL', 100, 150.0, 15000.0, 500.0)
            """))

        # 3. Apply
        apply_stats = ca_engine.apply(as_of=date(2026, 12, 31))
        assert apply_stats["applied"] == 1
        assert apply_stats["skipped"] == 0

        # 4. Vérifier le cash ledger
        total = repo.get_total_dividends(symbol="AAPL")
        assert total == 25.0

        # 5. Idempotence : re-apply ne change rien
        apply_stats2 = ca_engine.apply(as_of=date(2026, 12, 31))
        assert apply_stats2["applied"] == 0
        assert repo.get_total_dividends(symbol="AAPL") == 25.0  # inchangé

    def test_sync_and_apply_split(self, engine, repo):
        """Flow complet pour un split 2:1."""
        event = _make_split_event(symbol="NVDA", split_from=1, split_to=2)
        ca_engine = self._make_engine(repo, [event])

        ca_engine.sync()

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO broker_positions_snapshots
                    (exec_run_id, broker_mode, symbol, qty, avg_entry_price, market_value, unrealized_pnl)
                VALUES ('run-002', 'paper', 'NVDA', 50, 800.0, 45000.0, 5000.0)
            """))

        stats = ca_engine.apply(as_of=date(2026, 12, 31))
        assert stats["applied"] == 1

    def test_sync_duplicate_events(self, repo):
        """Sync deux fois le même événement → un seul insert."""
        event = _make_dividend_event()
        ca_engine = self._make_engine(repo, [event])

        stats1 = ca_engine.sync()
        stats2 = ca_engine.sync()
        assert stats1["inserted"] == 1
        assert stats2["duplicates"] == 1

        pending = repo.load_pending_events()
        assert len(pending) == 1

    def test_apply_no_position_skips(self, repo):
        """Apply sans position → skip."""
        event = _make_dividend_event()
        ca_engine = self._make_engine(repo, [event])
        ca_engine.sync()

        stats = ca_engine.apply(as_of=date(2026, 12, 31))
        assert stats["skipped"] == 1

    def test_invalid_event_rejected(self, repo):
        """Un événement invalide est ignoré au sync."""
        bad = CorporateActionEvent(
            provider="test", provider_event_id=None,
            symbol="", ca_type=CaType.CASH_DIVIDEND,
            amount_per_share=-1, ex_date=date(2026, 1, 1),
        )
        ca_engine = self._make_engine(repo, [bad])
        stats = ca_engine.sync()
        assert stats["invalid"] == 1
        assert stats["inserted"] == 0


# =====================================================================
# Tests — Réconciliation
# =====================================================================

class TestReconciliation:

    def test_reconcile_ok(self):
        diffs = reconcile_after_corporate_actions(
            internal_positions={"AAPL": 100.0},
            broker_positions=[{"symbol": "AAPL", "qty": 100}],
        )
        assert len(diffs) == 1
        assert diffs[0].action == "ok"

    def test_reconcile_qty_mismatch(self):
        diffs = reconcile_after_corporate_actions(
            internal_positions={"AAPL": 100.0},
            broker_positions=[{"symbol": "AAPL", "qty": 200}],
        )
        assert diffs[0].action == "qty_mismatch"

    def test_reconcile_investigate(self):
        diffs = reconcile_after_corporate_actions(
            internal_positions={},
            broker_positions=[{"symbol": "XYZ", "qty": 50}],
        )
        assert diffs[0].action == "investigate"

