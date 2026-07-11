"""Tests unitaires — risk_management/decision_fingerprint.py (Sprint Maître 12)."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from risk_management.decision_fingerprint import (
    AuditLogEntry,
    DecisionAuditLog,
    DecisionFingerprint,
    IdempotencyGate,
    IdempotencyResult,
    PositionDecisionFingerprint,
    ReplayVerificationResult,
    ReplayVerifier,
    build_decision_fingerprint,
    build_position_fingerprint,
)


# ── DecisionFingerprint ─────────────────────────────────────────────────────


class TestDecisionFingerprint:
    def test_construction(self) -> None:
        fp = DecisionFingerprint(
            trade_date=date(2026, 7, 1),
            run_id="run_001",
            config_fingerprint="abc123",
            model_run_id="model_001",
            policy_version=1,
        )
        assert len(fp.fingerprint) == 16
        assert fp.trade_date == date(2026, 7, 1)

    def test_deterministic(self) -> None:
        fp1 = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="run_001",
            config_fingerprint="abc", model_run_id="m1", policy_version=1,
        )
        fp2 = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="run_001",
            config_fingerprint="abc", model_run_id="m1", policy_version=1,
        )
        assert fp1.fingerprint == fp2.fingerprint

    def test_different_inputs_different_fingerprint(self) -> None:
        fp1 = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="run_001",
            config_fingerprint="abc", model_run_id="m1", policy_version=1,
        )
        fp2 = DecisionFingerprint(
            trade_date=date(2026, 7, 2), run_id="run_001",  # Different date
            config_fingerprint="abc", model_run_id="m1", policy_version=1,
        )
        assert fp1.fingerprint != fp2.fingerprint

    def test_to_dict(self) -> None:
        fp = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="run_001",
            config_fingerprint="abc", model_run_id="m1", policy_version=3,
            candidate_count=42,
        )
        d = fp.to_dict()
        assert d["candidate_count"] == 42
        assert d["policy_version"] == 3

    def test_fingerprint_persisted_on_construction(self) -> None:
        fp = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="r1",
            config_fingerprint="cfg", model_run_id="m1", policy_version=1,
            fingerprint="custom_fp_override",
        )
        assert fp.fingerprint == "custom_fp_override"


# ── PositionDecisionFingerprint ─────────────────────────────────────────────


class TestPositionDecisionFingerprint:
    def test_construction(self) -> None:
        fp = PositionDecisionFingerprint(
            symbol="AAPL", side="long", decision_fingerprint="dfp001",
            predicted_proba=0.55, p_side=0.55, edge=0.03, price=150.0,
            atr=5.0, adv_usd=10_000_000, config_fingerprint="cfg001",
        )
        assert len(fp.fingerprint) == 16

    def test_different_edge_different_fingerprint(self) -> None:
        fp1 = PositionDecisionFingerprint(
            symbol="AAPL", side="long", decision_fingerprint="dfp",
            edge=0.03, price=150.0,
        )
        fp2 = PositionDecisionFingerprint(
            symbol="AAPL", side="long", decision_fingerprint="dfp",
            edge=0.05, price=150.0,
        )
        assert fp1.fingerprint != fp2.fingerprint


# ── AuditLogEntry ───────────────────────────────────────────────────────────


class TestAuditLogEntry:
    def test_roundtrip(self) -> None:
        entry = AuditLogEntry(
            trade_date=date(2026, 7, 1),
            timestamp=datetime(2026, 7, 1, 14, 30),
            run_id="run_001",
            symbol="AAPL",
            side="long",
            decision="ACCEPTED",
            reason="ok",
            proposed_shares=100,
            approved_shares=100,
            entry_price=150.0,
            stop_price=145.0,
            fingerprint="fp001",
            predicted_proba=0.60,
            edge=0.05,
            atr=5.0,
            config_fingerprint="cfg001",
            model_run_id="m1",
            policy_version=2,
        )
        d = entry.to_dict()
        restored = AuditLogEntry.from_dict(d)
        assert restored.symbol == entry.symbol
        assert restored.decision == entry.decision
        assert restored.approved_shares == entry.approved_shares
        assert restored.fingerprint == entry.fingerprint

    def test_from_dict_minimal(self) -> None:
        d = {
            "trade_date": "2026-07-01",
            "timestamp": "2026-07-01T14:30:00",
            "run_id": "r1",
            "symbol": "AAPL",
            "side": "long",
            "decision": "REJECTED",
            "reason": "low_edge",
            "proposed_shares": 0,
            "approved_shares": 0,
            "entry_price": 0.0,
        }
        entry = AuditLogEntry.from_dict(d)
        assert entry.symbol == "AAPL"
        assert entry.decision == "REJECTED"


# ── DecisionAuditLog ────────────────────────────────────────────────────────


class TestDecisionAuditLog:
    def test_empty_log(self) -> None:
        log = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        assert log.accepted_count == 0
        assert log.rejected_count == 0

    def test_add_entry(self) -> None:
        log = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        entry = AuditLogEntry(
            trade_date=date(2026, 7, 1), timestamp=datetime.now(),
            run_id="r1", symbol="AAPL", side="long",
            decision="ACCEPTED", reason="ok",
            proposed_shares=100, approved_shares=100, entry_price=150.0,
        )
        log.add_entry(entry)
        assert log.accepted_count == 1

    def test_roundtrip(self) -> None:
        log = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        log.add_entry(AuditLogEntry(
            trade_date=date(2026, 7, 1), timestamp=datetime.now(),
            run_id="r1", symbol="AAPL", side="long",
            decision="ACCEPTED", reason="ok",
            proposed_shares=100, approved_shares=100, entry_price=150.0,
        ))
        d = log.to_dict()
        restored = DecisionAuditLog.from_dict(d)
        assert restored.accepted_count == 1
        assert restored.entries[0].symbol == "AAPL"


# ── ReplayVerifier ──────────────────────────────────────────────────────────


class TestReplayVerifier:
    def _make_entry(self, symbol, decision="ACCEPTED", shares=100, side="long", fingerprint="fp"):
        return AuditLogEntry(
            trade_date=date(2026, 7, 1), timestamp=datetime.now(),
            run_id="r1", symbol=symbol, side=side,
            decision=decision, reason="ok",
            proposed_shares=shares, approved_shares=shares,
            entry_price=150.0, fingerprint=fingerprint,
        )

    def test_identical_logs_pass(self) -> None:
        verifier = ReplayVerifier()
        orig = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        replay = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        for sym in ["AAPL", "MSFT"]:
            orig.add_entry(self._make_entry(sym))
            replay.add_entry(self._make_entry(sym))
        result = verifier.verify(orig, replay)
        assert result.passed is True

    def test_different_decisions_fail(self) -> None:
        verifier = ReplayVerifier()
        orig = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        replay = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        orig.add_entry(self._make_entry("AAPL", decision="ACCEPTED"))
        replay.add_entry(self._make_entry("AAPL", decision="REJECTED"))
        result = verifier.verify(orig, replay)
        assert result.passed is False

    def test_missing_symbol_fails(self) -> None:
        verifier = ReplayVerifier()
        orig = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        replay = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        orig.add_entry(self._make_entry("AAPL"))
        # replay n'a pas AAPL
        result = verifier.verify(orig, replay)
        assert result.passed is False

    def test_different_shares_fails(self) -> None:
        verifier = ReplayVerifier()
        orig = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        replay = DecisionAuditLog(trade_date=date(2026, 7, 1), run_id="r1")
        orig.add_entry(self._make_entry("AAPL", shares=100))
        replay.add_entry(self._make_entry("AAPL", shares=50))
        result = verifier.verify(orig, replay)
        assert result.passed is False

    def test_to_dict(self) -> None:
        result = ReplayVerificationResult(
            passed=True, original_entry_count=10, replay_entry_count=10, matching_count=10,
        )
        d = result.to_dict()
        assert d["parity_pct"] == 1.0


# ── IdempotencyGate ─────────────────────────────────────────────────────────


class TestIdempotencyGate:
    def test_first_call_not_duplicate(self) -> None:
        gate = IdempotencyGate()
        fp = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="r1",
            config_fingerprint="cfg", model_run_id="m1", policy_version=1,
        )
        result = gate.check(fp)
        assert result.is_duplicate is False

    def test_second_call_is_duplicate(self) -> None:
        gate = IdempotencyGate()
        fp = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="r1",
            config_fingerprint="cfg", model_run_id="m1", policy_version=1,
        )
        gate.check(fp)
        result = gate.check(fp)
        assert result.is_duplicate is True
        assert result.existing_run_id == "r1"

    def test_different_inputs_not_duplicate(self) -> None:
        gate = IdempotencyGate()
        fp1 = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="r1",
            config_fingerprint="cfg", model_run_id="m1", policy_version=1,
        )
        fp2 = DecisionFingerprint(
            trade_date=date(2026, 7, 2), run_id="r2",
            config_fingerprint="cfg", model_run_id="m1", policy_version=1,
        )
        gate.check(fp1)
        result = gate.check(fp2)
        assert result.is_duplicate is False

    def test_clear_resets(self) -> None:
        gate = IdempotencyGate()
        fp = DecisionFingerprint(
            trade_date=date(2026, 7, 1), run_id="r1",
            config_fingerprint="cfg", model_run_id="m1", policy_version=1,
        )
        gate.check(fp)
        gate.clear()
        result = gate.check(fp)
        assert result.is_duplicate is False


# ── Helpers ─────────────────────────────────────────────────────────────────


class TestBuildDecisionFingerprint:
    def test_helper(self) -> None:
        fp = build_decision_fingerprint(
            trade_date=date(2026, 7, 1), run_id="r1",
            config_fingerprint="cfg", model_run_id="m1", candidate_count=10,
        )
        assert len(fp.fingerprint) == 16


class TestBuildPositionFingerprint:
    def test_helper(self) -> None:
        fp = build_position_fingerprint(
            "AAPL", "long", "dfp001", predicted_proba=0.55, price=150.0,
        )
        assert len(fp.fingerprint) == 16
