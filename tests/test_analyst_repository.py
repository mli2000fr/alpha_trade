"""Tests du repository analyst — append-only, idempotence, PIT (SQLite en mémoire).

La migration cible MySQL ; ici on crée un schéma SQLite équivalent et on
neutralise le préfixe de schéma ``alpha_trade.`` pour tester la logique du
repository (append-only / idempotence / available_at <= cutoff).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from database.repositories import analyst_snapshots as mod
from database.repositories.analyst_snapshots import AnalystSnapshotRepository

D = date(2026, 8, 27)
T0 = datetime(2026, 8, 27, 20, 0)
T1 = datetime(2026, 8, 28, 20, 0)


def _ddl() -> str:
    return (
        "CREATE TABLE stock_analyst_estimate_history ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, symbol TEXT,"
        " snapshot_date DATE, observed_at DATETIME, available_at DATETIME,"
        " ingestion_at DATETIME, estimate_type TEXT, horizon_raw TEXT,"
        " horizon_normalized TEXT, fiscal_period_end DATE, fiscal_year INT,"
        " fiscal_quarter INT, relative_horizon_only INT, avg_value REAL,"
        " low_value REAL, high_value REAL, analyst_count INT, growth_value REAL,"
        " raw_payload_json TEXT, raw_hash TEXT, provider_schema_version TEXT, created_at DATETIME);"
        "CREATE TABLE stock_analyst_target_history ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, symbol TEXT,"
        " snapshot_date DATE, observed_at DATETIME, available_at DATETIME,"
        " ingestion_at DATETIME, current_price REAL, target_low REAL,"
        " target_mean REAL, target_median REAL, target_high REAL,"
        " analyst_count INT, raw_payload_json TEXT, raw_hash TEXT,"
        " provider_schema_version TEXT, created_at DATETIME);"
        "CREATE TABLE stock_analyst_recommendation_history ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, symbol TEXT,"
        " snapshot_date DATE, observed_at DATETIME, available_at DATETIME,"
        " ingestion_at DATETIME, period_raw TEXT, strong_buy INT, buy INT,"
        " hold INT, sell INT, strong_sell INT, raw_payload_json TEXT,"
        " raw_hash TEXT, provider_schema_version TEXT, created_at DATETIME);"
        "CREATE TABLE analyst_snapshot_collection_run ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT UNIQUE, provider TEXT,"
        " started_at DATETIME, finished_at DATETIME, requested_symbols INT,"
        " successful_symbols INT, empty_symbols INT, failed_symbols INT,"
        " estimates_rows_inserted INT, targets_rows_inserted INT,"
        " recommendations_rows_inserted INT, rate_limit_count INT,"
        " temporary_error_count INT, schema_error_count INT, parse_error_count INT,"
        " eps_coverage REAL, revenue_coverage REAL, target_coverage REAL,"
        " recommendation_coverage REAL, status TEXT, created_at DATETIME);"
    )


@pytest.fixture()
def repo(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        for stmt in _ddl().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    monkeypatch.setattr(mod, "_SCHEMA_PREFIX", "")  # pas de schéma en SQLite
    return AnalystSnapshotRepository(engine=engine)


def _est_row(day: date = D, avail: datetime = T0, avg: float = 4.25):
    return {
        "provider": "yahoo", "symbol": "AAPL", "snapshot_date": day,
        "observed_at": avail - timedelta(hours=2), "available_at": avail,
        "estimate_type": "EPS", "horizon_raw": "0y", "horizon_normalized": "CURRENT_YEAR",
        "fiscal_period_end": None, "fiscal_year": None, "fiscal_quarter": None,
        "relative_horizon_only": True, "avg_value": avg, "low_value": None,
        "high_value": None, "analyst_count": 20, "growth_value": None,
        "raw_payload_json": "{}", "raw_hash": "h", "provider_schema_version": "1.0",
    }


def test_append_only_new_date_creates_new_row(repo):
    repo.insert_estimate_snapshots([_est_row(day=D, avg=4.25)])
    repo.insert_estimate_snapshots([_est_row(day=D + timedelta(days=1), avg=4.18)])
    hist = repo.get_estimate_history("AAPL")
    assert len(hist) == 2
    assert [r["avg_value"] for r in hist] == [4.25, 4.18]  # aucune UPDATE de l'ancienne


def test_daily_idempotence_no_duplicate(repo):
    n1 = repo.insert_estimate_snapshots([_est_row()])
    n2 = repo.insert_estimate_snapshots([_est_row()])  # même clé UNIQUE logique
    assert n1 == 1 and n2 == 0
    assert len(repo.get_estimate_history("AAPL")) == 1


def test_duplicate_retry(repo):
    rows = [_est_row(), _est_row()]
    assert repo.insert_estimate_snapshots(rows) == 1  # 1 inséré, 1 ignoré


def test_run_idempotence(repo):
    repo.start_collection_run("run_1", "yahoo", 5)
    repo.start_collection_run("run_1", "yahoo", 5)  # relance → pas de doublon
    runs = repo.get_collection_run("run_1")
    assert runs is not None
    assert repo.get_last_collection_run()["run_id"] == "run_1"


def test_latest_before_cutoff(repo):
    repo.insert_estimate_snapshots([
        _est_row(day=D, avail=T0, avg=4.25),           # disponible à T0
        _est_row(day=D + timedelta(days=1), avail=T1, avg=4.18),  # disponible à T1
    ])
    got = repo.get_latest_estimate_before("AAPL", "EPS", "CURRENT_YEAR", cutoff=T0)
    assert got is not None and got["avg_value"] == 4.25


def test_snapshot_after_cutoff_hidden(repo):
    repo.insert_estimate_snapshots([_est_row(avail=T1)])  # disponible seulement à T1
    got = repo.get_latest_estimate_before("AAPL", "EPS", "CURRENT_YEAR", cutoff=T0)
    assert got is None  # snapshot APRÈS cutoff → invisible


def test_target_and_reco_idempotence(repo):
    tgt = {"provider": "yahoo", "symbol": "AAPL", "snapshot_date": D,
           "observed_at": T0, "available_at": T0, "current_price": 250.0,
           "target_low": 200.0, "target_mean": 270.0, "target_median": 265.0,
           "target_high": 320.0, "analyst_count": None, "raw_payload_json": "{}",
           "raw_hash": "h", "provider_schema_version": "1.0"}
    assert repo.insert_target_snapshots([tgt]) == 1
    assert repo.insert_target_snapshots([tgt]) == 0

    rec = {"provider": "yahoo", "symbol": "AAPL", "snapshot_date": D,
           "observed_at": T0, "available_at": T0, "period_raw": "0m",
           "strong_buy": 3, "buy": 10, "hold": 5, "sell": 1, "strong_sell": 0,
           "raw_payload_json": "{}", "raw_hash": "h", "provider_schema_version": "1.0"}
    assert repo.insert_recommendation_snapshots([rec]) == 1
    assert repo.insert_recommendation_snapshots([rec]) == 0
