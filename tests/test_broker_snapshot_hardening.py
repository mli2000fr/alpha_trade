"""Mini hardening live — refus des broker snapshots sans equity exploitable.

Regroupe les tests de régression couvrant :
  * ``execution_engine.account_state.build_account_constraint_state`` →
    lève ``InvalidBrokerSnapshotError`` quand le broker répond ``equity<=0``
    (panne API, compte non provisionné…).
  * ``execution_engine.executor.ProductionExecutor.execute_run`` → arrête
    le run avec un événement ``PRECHECK_FAILED`` clair et ne persiste
    AUCUN snapshot zéro.
  * ``execution_engine.db_io.ExecutionRepository.snapshot_broker_account``
    → refuse l'INSERT quand ``equity<=0`` (défense en profondeur).
  * ``risk_management.db_io.RiskRepository._load_broker_snapshot_as_account_risk_snapshot``
    → ignore les lignes ``equity<=0`` côté lecture pour le fallback PnL.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text

from execution_engine.account_state import (
    InvalidBrokerSnapshotError,
    build_account_constraint_state,
)
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.executor import ProductionExecutor
from execution_engine.models import EventType, ExecutionPosition, ExecutionTarget
from execution_engine.oco_manager import OcoManager
from risk_management.db_io import RiskRepository


# ---------------------------------------------------------------------------
# Fixtures helpers — réutilisent la même structure que tests/test_executor.py
# ---------------------------------------------------------------------------


def _target() -> ExecutionTarget:
    return ExecutionTarget(
        risk_run_id="r1",
        trade_date=date(2026, 5, 10),
        symbol="AAPL",
        target_shares=100,
        entry_price=150.0,
        target_weight=0.05,
        sector="Tech",
        conviction_score=0.8,
        sizing_method="atr",
        kelly_fraction=0.1,
        decision_rank=1,
        stop_price_initial=140.0,
        risk_per_share=10.0,
        risk_budget_dollars=1_000.0,
        initial_risk_dollars=1_000.0,
        target_notional=15_000.0,
        price_asof_date=date(2026, 5, 10),
        atr_asof_date=date(2026, 5, 10),
        atr_20=5.0,
    )


def _make_live_executor(snapshot: dict) -> tuple[ProductionExecutor, MagicMock, MagicMock]:
    cfg = ExecutionConfig(dry_run=False, allow_outside_rth=True)
    repo = MagicMock(spec=ExecutionRepository)
    repo.load_portfolio_targets.return_value = [_target()]
    repo.load_submitted_idempotency_keys.return_value = set()
    repo.acquire_execution_lock.return_value = True
    repo.load_execution_positions.return_value = [
        ExecutionPosition(account_id=cfg.resolved_account_id, symbol="AAPL", net_qty=0)
    ]
    repo.load_open_reconciliation_order_state.return_value = []
    repo.load_reconciliation_protection_state.return_value = []
    repo.load_unprotected_filled_parents.return_value = []

    broker = MagicMock(spec=BrokerAdapter)
    broker.is_market_open.return_value = True
    broker.get_account_snapshot.return_value = snapshot
    broker.get_all_positions.return_value = []
    broker.list_recent_orders.return_value = []

    oco = MagicMock(spec=OcoManager)
    executor = ProductionExecutor(cfg, repo, broker, oco)
    return executor, repo, broker


# ---------------------------------------------------------------------------
# 1. account_state — refus du snapshot invalide
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "snapshot",
    [
        {"equity": 0.0, "cash": 1000.0, "buying_power": 1000.0},
        {"equity": None, "cash": 1000.0, "buying_power": 1000.0},
        {"equity": "bad", "cash": 1000.0, "buying_power": 1000.0},
        {"cash": 1000.0, "buying_power": 1000.0},  # equity manquante
        {"equity": -42.0, "cash": 1000.0, "buying_power": 1000.0},
        {"portfolio_value": 0.0, "cash": 1000.0, "buying_power": 1000.0},
    ],
)
def test_build_account_constraint_state_rejects_invalid_equity(
    snapshot: dict, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = ExecutionConfig(dry_run=False, allow_outside_rth=True)
    broker = MagicMock(spec=BrokerAdapter)
    broker.get_account_snapshot.return_value = snapshot

    with caplog.at_level(logging.ERROR, logger="execution_engine.account_state"):
        with pytest.raises(InvalidBrokerSnapshotError) as exc_info:
            build_account_constraint_state(cfg, broker)

    assert "equity invalide" in str(exc_info.value).lower() or "equity" in str(exc_info.value)
    # Le log doit clairement nommer le compte/broker_mode et la valeur brute
    assert any("Snapshot broker rejeté" in record.message for record in caplog.records)


def test_build_account_constraint_state_accepts_positive_equity() -> None:
    cfg = ExecutionConfig(dry_run=False, allow_outside_rth=True)
    broker = MagicMock(spec=BrokerAdapter)
    broker.get_account_snapshot.return_value = {
        "equity": 100_000.0,
        "cash": 50_000.0,
        "buying_power": 100_000.0,
        "non_marginable_buying_power": 50_000.0,
        "daytrade_count": 0,
    }
    state = build_account_constraint_state(cfg, broker)
    assert state.equity == 100_000.0


# ---------------------------------------------------------------------------
# 2. Executor.execute_run — abort propre + aucun snapshot zéro persisté
# ---------------------------------------------------------------------------


def test_execute_run_aborts_on_invalid_broker_snapshot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    executor, repo, broker = _make_live_executor(
        snapshot={"equity": 0.0, "cash": 0.0, "buying_power": 0.0, "daytrade_count": 0}
    )

    with caplog.at_level(logging.ERROR, logger="execution_engine.executor"):
        metrics = executor.execute_run(risk_run_id="r1", trade_date=date(2026, 5, 10))

    # Le run doit être ABORTED et marqué comme tel en base
    assert metrics["status"] == "ABORTED"
    repo.update_execution_run_status.assert_any_call(
        metrics["exec_run_id"], "ABORTED"
    )

    # Aucune persistance de snapshot 0
    repo.snapshot_broker_account.assert_not_called()
    # Aucun ordre soumis
    broker.submit_intent.assert_not_called()

    # Un événement PRECHECK_FAILED doit avoir été persisté avec le motif explicite
    persisted_events = [c.args[0] for c in repo.insert_execution_event.call_args_list]
    matching = [
        ev for ev in persisted_events
        if ev.get("event_type") == EventType.PRECHECK_FAILED
        and "Snapshot broker" in (ev.get("message") or "")
    ]
    assert matching, f"PRECHECK_FAILED 'Snapshot broker' attendu, vu: {persisted_events}"

    # Et le log error explicite doit être émis
    assert any("snapshot broker invalide" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 3. ExecutionRepository.snapshot_broker_account — refus DB-level
# ---------------------------------------------------------------------------


def _setup_sqlite_with_broker_account_snapshots() -> ExecutionRepository:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE broker_account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exec_run_id TEXT,
                account_id TEXT,
                broker_mode TEXT,
                snapshot_kind TEXT,
                equity REAL,
                cash REAL,
                settled_cash REAL,
                buying_power REAL,
                daytrade_count INTEGER,
                raw_payload_json TEXT,
                created_at TIMESTAMP
            )
            """
        ))
    return ExecutionRepository(engine=engine)


def test_snapshot_broker_account_refuses_zero_equity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = _setup_sqlite_with_broker_account_snapshots()

    with caplog.at_level(logging.WARNING, logger="execution_engine.db_io"):
        repo.snapshot_broker_account(
            "exec-1",
            account_id="acct-1",
            broker_mode="live",
            snapshot={"equity": 0.0, "cash": 0.0, "buying_power": 0.0},
            snapshot_kind="preflight",
        )

    with repo.engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM broker_account_snapshots")).scalar()
    assert rows == 0
    assert any("equity invalide" in r.message.lower() for r in caplog.records)


def test_snapshot_broker_account_persists_when_equity_valid() -> None:
    repo = _setup_sqlite_with_broker_account_snapshots()
    repo.snapshot_broker_account(
        "exec-1",
        account_id="acct-1",
        broker_mode="live",
        snapshot={"equity": 12_345.0, "cash": 1_000.0, "buying_power": 12_345.0},
        snapshot_kind="preflight",
    )
    with repo.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT equity, account_id FROM broker_account_snapshots"
        )).mappings().first()
    assert row is not None
    assert float(row["equity"]) == 12_345.0
    assert row["account_id"] == "acct-1"


def test_snapshot_broker_account_allow_zero_equity_override() -> None:
    """``allow_zero_equity=True`` permet de débrayer le hardening (tests/imports)."""
    repo = _setup_sqlite_with_broker_account_snapshots()
    repo.snapshot_broker_account(
        "exec-1",
        account_id="acct-1",
        broker_mode="paper",
        snapshot={"equity": 0.0, "cash": 0.0, "buying_power": 0.0},
        snapshot_kind="preflight",
        allow_zero_equity=True,
    )
    with repo.engine.connect() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM broker_account_snapshots")).scalar()
    assert rows == 1


# ---------------------------------------------------------------------------
# 4. risk_management — fallback ignore les snapshots equity<=0
# ---------------------------------------------------------------------------


def _setup_risk_repo_with_broker_snapshots(rows: list[dict]) -> RiskRepository:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE broker_account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                broker_mode TEXT,
                snapshot_kind TEXT,
                equity REAL,
                cash REAL,
                settled_cash REAL,
                buying_power REAL,
                created_at TIMESTAMP
            )
            """
        ))
        for r in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO broker_account_snapshots
                        (account_id, broker_mode, snapshot_kind, equity, cash,
                         settled_cash, buying_power, created_at)
                    VALUES (:account_id, :broker_mode, :snapshot_kind, :equity, :cash,
                            :settled_cash, :buying_power, :created_at)
                    """
                ),
                r,
            )
    return RiskRepository(engine=engine)


def test_risk_fallback_skips_zero_equity_snapshot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Le fallback PnL doit ignorer une ligne `equity=0` (laissée par migration legacy)."""
    repo = _setup_risk_repo_with_broker_snapshots(
        [
            {
                "account_id": "acct-1",
                "broker_mode": "live",
                "snapshot_kind": "preflight",
                "equity": 0.0,
                "cash": 0.0,
                "settled_cash": 0.0,
                "buying_power": 0.0,
                "created_at": datetime(2026, 5, 10, 9, 30, tzinfo=timezone.utc),
            }
        ]
    )
    with caplog.at_level(logging.WARNING, logger="risk_management.db_io"):
        snap = repo._load_broker_snapshot_as_account_risk_snapshot(
            "acct-1", date(2026, 5, 10)
        )
    assert snap is None
    assert any("aucun broker_account_snapshot exploitable" in r.message.lower() for r in caplog.records)


def test_risk_fallback_uses_latest_valid_snapshot() -> None:
    repo = _setup_risk_repo_with_broker_snapshots(
        [
            {
                "account_id": "acct-1",
                "broker_mode": "live",
                "snapshot_kind": "preflight",
                "equity": 50_000.0,
                "cash": 25_000.0,
                "settled_cash": 25_000.0,
                "buying_power": 50_000.0,
                "created_at": datetime(2026, 5, 9, 9, 30, tzinfo=timezone.utc),
            },
            # Snapshot corrompu plus récent : doit être ignoré.
            {
                "account_id": "acct-1",
                "broker_mode": "live",
                "snapshot_kind": "preflight",
                "equity": 0.0,
                "cash": 0.0,
                "settled_cash": 0.0,
                "buying_power": 0.0,
                "created_at": datetime(2026, 5, 10, 9, 30, tzinfo=timezone.utc),
            },
        ]
    )
    snap = repo._load_broker_snapshot_as_account_risk_snapshot(
        "acct-1", date(2026, 5, 10)
    )
    assert snap is not None
    assert snap.equity == 50_000.0
    assert snap.high_watermark == 50_000.0

