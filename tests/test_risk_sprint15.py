"""Tests unitaires — Sprint Maître 15 (daily_reconciliation, operational_controls, immutable_journal)."""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from risk_management.daily_reconciliation import (
    DailyReconciliation,
    ReconItem,
    ReconciliationReport,
    ReconStatus,
)
from risk_management.operational_controls import (
    ControlFrequency,
    ControlResult,
    ControlSchedule,
    ControlStatus,
    OperationalControls,
    SmokeTest,
    run_pre_session_smoke_tests,
)
from risk_management.immutable_journal import (
    ImmutableJournal,
    JournalEntry,
    JournalEntryType,
    create_journal_entry,
)


# ═══════════════════════════════════════════════════════════════════════════
# DailyReconciliation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestReconStatus:
    def test_values(self) -> None:
        assert ReconStatus.MATCHED.value == "matched"
        assert ReconStatus.MISMATCHED.value == "mismatched"


class TestReconItem:
    def test_matched(self) -> None:
        item = ReconItem("orders", "ord_001", "filled", "filled", ReconStatus.MATCHED)
        assert item.is_matched is True

    def test_mismatched(self) -> None:
        item = ReconItem("orders", "ord_001", "intended", "not_submitted", ReconStatus.MISMATCHED)
        assert item.is_matched is False


class TestReconciliationReport:
    def test_clean(self) -> None:
        r = ReconciliationReport(
            trade_date=date.today(), overall_status=ReconStatus.MATCHED,
            total_items=10, matched_items=10,
        )
        assert r.is_clean is True
        assert r.match_rate == 1.0

    def test_not_clean(self) -> None:
        r = ReconciliationReport(
            trade_date=date.today(), overall_status=ReconStatus.MISMATCHED,
            total_items=10, matched_items=8, mismatched_items=2,
        )
        assert r.is_clean is False


class TestDailyReconciliation:
    def test_empty_all_pending(self) -> None:
        recon = DailyReconciliation()
        report = recon.reconcile(date.today())
        assert report.total_items == 0

    def test_matched_orders(self) -> None:
        recon = DailyReconciliation()
        intended = [{"intent_id": "i1", "symbol": "AAPL"}]
        submitted = [{"intent_id": "i1"}]
        fills = [{"intent_id": "i1"}]
        report = recon.reconcile(date.today(), intended_orders=intended, submitted_orders=submitted, fills=fills)
        assert report.categories.get("orders") == ReconStatus.MATCHED

    def test_missing_submission(self) -> None:
        recon = DailyReconciliation()
        intended = [{"intent_id": "i1"}]
        report = recon.reconcile(date.today(), intended_orders=intended)
        assert report.categories.get("orders") == ReconStatus.MISMATCHED

    def test_positions_match(self) -> None:
        recon = DailyReconciliation()
        targets = [{"symbol": "AAPL", "quantity": 100, "side": "long"}]
        actuals = [{"symbol": "AAPL", "quantity": 100, "side": "long"}]
        report = recon.reconcile(date.today(), target_positions=targets, actual_positions=actuals)
        assert report.categories.get("positions") == ReconStatus.MATCHED

    def test_positions_mismatch_quantity(self) -> None:
        recon = DailyReconciliation()
        targets = [{"symbol": "AAPL", "quantity": 100, "side": "long"}]
        actuals = [{"symbol": "AAPL", "quantity": 80, "side": "long"}]
        report = recon.reconcile(date.today(), target_positions=targets, actual_positions=actuals)
        assert report.categories.get("positions") == ReconStatus.MISMATCHED

    def test_positions_mismatch_side(self) -> None:
        recon = DailyReconciliation()
        targets = [{"symbol": "AAPL", "quantity": 100, "side": "long"}]
        actuals = [{"symbol": "AAPL", "quantity": 100, "side": "short"}]
        report = recon.reconcile(date.today(), target_positions=targets, actual_positions=actuals)
        assert report.categories.get("positions") == ReconStatus.MISMATCHED

    def test_protections_match(self) -> None:
        recon = DailyReconciliation()
        expected = [{"oco_id": "oco_1"}]
        actual = [{"oco_id": "oco_1"}]
        report = recon.reconcile(date.today(), expected_protections=expected, actual_protections=actual)
        assert report.categories.get("protections") == ReconStatus.MATCHED

    def test_missing_protection(self) -> None:
        recon = DailyReconciliation()
        expected = [{"oco_id": "oco_1"}]
        report = recon.reconcile(date.today(), expected_protections=expected)
        assert report.categories.get("protections") == ReconStatus.MISMATCHED

    def test_pnl_match(self) -> None:
        recon = DailyReconciliation()
        report = recon.reconcile(date.today(), calculated_pnl=1500.0, broker_pnl=1500.0)
        assert report.categories.get("pnl") == ReconStatus.MATCHED

    def test_pnl_mismatch(self) -> None:
        recon = DailyReconciliation()
        report = recon.reconcile(date.today(), calculated_pnl=1500.0, broker_pnl=1450.0)
        assert report.categories.get("pnl") == ReconStatus.MISMATCHED

    def test_cash_match(self) -> None:
        recon = DailyReconciliation()
        report = recon.reconcile(date.today(), calculated_cash=100_000.0, broker_cash=100_000.0)
        assert report.categories.get("cash") == ReconStatus.MATCHED

    def test_clean_report_requires_no_action(self) -> None:
        recon = DailyReconciliation()
        report = recon.reconcile(
            date.today(),
            calculated_pnl=1000.0, broker_pnl=1000.0,
            calculated_cash=100_000.0, broker_cash=100_000.0,
        )
        assert report.is_clean is True or report.requires_operator_action is False


# ═══════════════════════════════════════════════════════════════════════════
# OperationalControls tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSmokeTest:
    def test_blocking(self) -> None:
        s = SmokeTest("S1", "Test", status=ControlStatus.FAILED)
        assert s.is_blocking is True

    def test_not_blocking(self) -> None:
        s = SmokeTest("S1", "Test", status=ControlStatus.PASSED)
        assert s.is_blocking is False


class TestControlSchedule:
    def test_pre_session_tests_count(self) -> None:
        sched = ControlSchedule()
        assert len(sched.PRE_SESSION_TESTS) == 7

    def test_daily_controls(self) -> None:
        sched = ControlSchedule()
        controls = sched.get_controls(ControlFrequency.DAILY)
        assert "reconciliation" in controls
        assert "parity_check" in controls

    def test_monthly_controls(self) -> None:
        sched = ControlSchedule()
        controls = sched.get_controls(ControlFrequency.MONTHLY)
        assert "rollback_drill" in controls


class TestOperationalControls:
    def test_run_smoke_tests_all_pass(self) -> None:
        ctrls = OperationalControls()
        all_ok, results = ctrls.run_smoke_tests()
        assert all_ok is True
        assert len(results) == 7

    def test_run_smoke_tests_with_failure(self) -> None:
        ctrls = OperationalControls()
        all_ok, results = ctrls.run_smoke_tests(connectivity_ok=False)
        assert all_ok is False

    def test_record_control(self) -> None:
        ctrls = OperationalControls()
        result = ctrls.record_control("RECON", "Réconciliation", ControlFrequency.DAILY, True)
        assert result.status == ControlStatus.PASSED

    def test_is_ready_to_trade(self) -> None:
        ctrls = OperationalControls()
        ctrls.run_smoke_tests()
        ready, reason = ctrls.is_ready_to_trade()
        assert ready is True

    def test_not_ready_without_smoke(self) -> None:
        ctrls = OperationalControls()
        ready, reason = ctrls.is_ready_to_trade()
        assert ready is False

    def test_summary(self) -> None:
        ctrls = OperationalControls()
        ctrls.run_smoke_tests()
        summary = ctrls.summary()
        assert summary["ready_to_trade"] is True


class TestRunPreSessionSmokeTests:
    def test_helper(self) -> None:
        all_ok, results = run_pre_session_smoke_tests()
        assert all_ok is True
        assert len(results) == 7


# ═══════════════════════════════════════════════════════════════════════════
# ImmutableJournal tests
# ═══════════════════════════════════════════════════════════════════════════

class TestJournalEntryType:
    def test_values(self) -> None:
        assert JournalEntryType.CONFIG_CHANGE.value == "config_change"
        assert JournalEntryType.KILL_SWITCH.value == "kill_switch"
        assert JournalEntryType.ROLLBACK.value == "rollback"


class TestJournalEntry:
    def test_hash_auto_computed(self) -> None:
        entry = JournalEntry(
            entry_id="e1", entry_type=JournalEntryType.OPERATOR_ACTION,
            timestamp=datetime.now(), operator="ops",
        )
        assert len(entry.entry_hash) == 16

    def test_to_dict(self) -> None:
        entry = JournalEntry(
            entry_id="e1", entry_type=JournalEntryType.CONFIG_CHANGE,
            timestamp=datetime.now(), operator="ops",
            description="Changed max_positions", reason="Risk reduction",
            prev_hash="abc123",
        )
        d = entry.to_dict()
        assert d["entry_type"] == "config_change"
        assert d["operator"] == "ops"


class TestImmutableJournal:
    def test_append(self) -> None:
        journal = ImmutableJournal()
        entry = journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "Test")
        assert journal.entry_count == 1
        assert entry.operator == "ops"

    def test_chain_integrity(self) -> None:
        journal = ImmutableJournal()
        journal.append(JournalEntryType.MODEL_PROMOTION, "ops", "Promote m1")
        journal.append(JournalEntryType.STAGE_TRANSITION, "ops", "LIVE_5PCT→LIVE_10PCT")
        valid, violations = journal.verify_chain()
        assert valid is True
        assert len(violations) == 0

    def test_chain_tampered(self) -> None:
        journal = ImmutableJournal()
        journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "Original")
        journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "Second")
        # Simuler une corruption : on remplace l'entrée par une nouvelle avec un prev_hash invalide
        corrupted = JournalEntry(
            entry_id="corrupted", entry_type=JournalEntryType.CONFIG_CHANGE,
            timestamp=datetime.now(), operator="hacker",
            description="Tampered", prev_hash="wrong_hash_0000",
        )
        journal._entries[1] = corrupted
        valid, violations = journal.verify_chain()
        assert valid is False
        assert len(violations) > 0

    def test_get_by_type(self) -> None:
        journal = ImmutableJournal()
        journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "C1")
        journal.append(JournalEntryType.ROLLBACK, "ops", "R1")
        journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "C2")
        configs = journal.get_by_type(JournalEntryType.CONFIG_CHANGE)
        assert len(configs) == 2

    def test_get_by_operator(self) -> None:
        journal = ImmutableJournal()
        journal.append(JournalEntryType.CONFIG_CHANGE, "alice", "A1")
        journal.append(JournalEntryType.CONFIG_CHANGE, "bob", "B1")
        alice_entries = journal.get_by_operator("alice")
        assert len(alice_entries) == 1

    def test_prev_hash_chaining(self) -> None:
        journal = ImmutableJournal()
        e1 = journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "First")
        e2 = journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "Second")
        assert e2.prev_hash == e1.entry_hash

    def test_to_dict(self) -> None:
        journal = ImmutableJournal()
        journal.append(JournalEntryType.CONFIG_CHANGE, "ops", "Test")
        d = journal.to_dict()
        assert d["entry_count"] == 1

    def test_save_and_load_preserves_verified_chain(self, tmp_path) -> None:
        path = tmp_path / "operations.json"
        journal = ImmutableJournal()
        journal.append(JournalEntryType.STAGE_TRANSITION, "ops", "SHADOW -> PAPER")
        journal.save_atomic(path)

        restored = ImmutableJournal.load(path)

        assert restored.entry_count == 1
        assert restored.verify_chain() == (True, [])

    def test_load_rejects_tampered_chain(self, tmp_path) -> None:
        path = tmp_path / "operations.json"
        journal = ImmutableJournal()
        journal.append(JournalEntryType.OPERATOR_ACTION, "ops", "approved")
        payload = journal.to_dict()
        payload["entries"][0]["entry_hash"] = "tampered"
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="chaîne de journal invalide"):
            ImmutableJournal.load(path)


class TestCreateJournalEntry:
    def test_helper(self) -> None:
        journal = ImmutableJournal()
        entry = create_journal_entry(journal, JournalEntryType.OPERATOR_ACTION, "ops", "Test action")
        assert entry.operator == "ops"
        assert journal.entry_count == 1
