"""Sprint S12.2 — Tests du chaînage HMAC SOX-like."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from database.audit_chain import (
    AuditChainRepository,
    ChainAnomaly,
    _GENESIS_HASH,
    _compute_hmac,
)


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE audit_chain_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_kind TEXT NOT NULL,
                run_id TEXT NOT NULL,
                payload_canonical_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL DEFAULT '',
                hmac_sha256 TEXT NOT NULL,
                key_version INTEGER NOT NULL DEFAULT 1,
                signed_at TIMESTAMP NOT NULL
            )
        """))
    return eng


def test_append_then_verify_chain_is_clean(engine):
    repo = AuditChainRepository(engine, key=b"k1", key_version=1)
    h1 = repo.append("execution_runs", "run-1", {"a": 1})
    h2 = repo.append("execution_runs", "run-2", {"a": 2})
    h3 = repo.append("execution_runs", "run-3", {"a": 3})

    assert h1 != _GENESIS_HASH
    assert h2 != h1 != h3
    assert repo.verify_chain("execution_runs") == []


def test_verify_detects_payload_mutation(engine):
    repo = AuditChainRepository(engine, key=b"k1", key_version=1)
    repo.append("risk_runs", "r1", {"x": 10})
    repo.append("risk_runs", "r2", {"x": 20})

    # Mutation du payload du 2e événement → hmac_mismatch.
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE audit_chain_events SET payload_canonical_json = :p WHERE id = 2"
        ), {"p": '{"x":999}'})

    anomalies = repo.verify_chain("risk_runs")
    assert len(anomalies) == 1
    assert anomalies[0].event_id == 2
    assert "hmac_mismatch" in anomalies[0].reason


def test_verify_detects_prev_hash_tamper(engine):
    repo = AuditChainRepository(engine, key=b"k1")
    repo.append("ca", "c1", {"v": 1})
    repo.append("ca", "c2", {"v": 2})

    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_chain_events SET prev_hash = '00' WHERE id = 2"))

    anomalies = repo.verify_chain("ca")
    assert anomalies and "prev_hash_mismatch" in anomalies[0].reason


def test_idempotent_signature_for_same_payload(engine):
    repo = AuditChainRepository(engine, key=b"k1")
    expected = _compute_hmac(b"k1", _GENESIS_HASH, '{"x":1}')
    actual = repo.append("k", "id-1", {"x": 1})
    assert actual == expected


def test_key_rotation_recorded(engine):
    repo_v1 = AuditChainRepository(engine, key=b"k-old", key_version=1)
    repo_v1.append("execution_runs", "r1", {"a": 1})
    repo_v2 = AuditChainRepository(engine, key=b"k-new", key_version=2)
    repo_v2.append("execution_runs", "r2", {"a": 2})

    with engine.connect() as conn:
        rows = list(conn.execute(text("SELECT key_version FROM audit_chain_events ORDER BY id")))
    assert [int(r[0]) for r in rows] == [1, 2]


def test_distinct_chains_per_run_kind(engine):
    repo = AuditChainRepository(engine, key=b"k")
    repo.append("execution_runs", "ra", {"v": 1})
    repo.append("risk_runs", "rb", {"v": 1})
    # Les deux chaînes sont vérifiables indépendamment.
    assert repo.verify_chain("execution_runs") == []
    assert repo.verify_chain("risk_runs") == []
    assert repo.verify_chain() == []


