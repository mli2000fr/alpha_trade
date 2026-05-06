"""Sprint S21.1 — Test E2E auto-rollback contre SQLite (in-memory).

Vérifie que :
- la migration ``0026_champion_history`` crée la table ;
- ``decision_history_loader_sql`` lit ``ml_drift_runs`` (status=ALERT → gate=disabled) ;
- ``champion_swapper_sql`` insère une ligne ``champion_history`` et démote
  l'ancien champion (transaction atomique) ;
- ``auto_rollback_if_needed`` appelle bien ces adapters quand le streak
  dépasse le seuil.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from modelFactory.auto_rollback import (
    auto_rollback_if_needed,
    champion_swapper_sql,
    current_champion_loader_sql,
    decision_history_loader_sql,
)


def _bootstrap_schema(engine) -> None:
    """Crée les tables minimales (équivalent migrations 0021 + 0026)."""
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE ml_drift_runs (
                run_id      VARCHAR(40) PRIMARY KEY,
                computed_at DATETIME    NOT NULL,
                model_id    VARCHAR(64) NOT NULL,
                ks_stat     FLOAT,
                ks_pvalue   FLOAT,
                psi         FLOAT,
                n_samples   INTEGER     NOT NULL DEFAULT 0,
                n_baseline  INTEGER     NOT NULL DEFAULT 0,
                status      VARCHAR(8)  NOT NULL,
                payload     TEXT
            )
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE champion_history (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol            VARCHAR(32) NOT NULL,
                model_id          VARCHAR(128) NOT NULL,
                version           VARCHAR(64),
                promoted_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                demoted_at        DATETIME,
                reason            VARCHAR(256) NOT NULL DEFAULT '',
                previous_model_id VARCHAR(128),
                dry_run           BOOLEAN     NOT NULL DEFAULT 0,
                created_at        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))


def _insert_drift(engine, *, symbol: str, days: list[tuple[int, str]]) -> None:
    """``days`` = liste de ``(jours_avant_aujourdhui, status)``."""
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        for offset, status in days:
            conn.execute(text(
                "INSERT INTO ml_drift_runs (run_id, computed_at, model_id, "
                "n_samples, n_baseline, status) "
                "VALUES (:rid, :ts, :mid, 100, 100, :st)"
            ), {
                "rid": f"r-{symbol}-{offset}",
                "ts": now - timedelta(days=offset),
                "mid": f"model-{symbol}",
                "st": status,
            })


@pytest.fixture()
def sqlite_engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    _bootstrap_schema(eng)
    return eng


def test_decision_history_loader_sql_reads_alerts(sqlite_engine) -> None:
    _insert_drift(sqlite_engine, symbol="AAPL",
                  days=[(0, "ALERT"), (1, "ALERT"), (2, "ALERT"), (3, "OK")])
    history = decision_history_loader_sql("AAPL", engine=sqlite_engine, threshold_days=5)
    assert len(history) == 4
    # plus récent d'abord
    assert history[0][1]["gate"] == "disabled"
    assert history[3][1]["gate"] == "enabled"


def test_champion_swapper_sql_inserts_and_demotes(sqlite_engine) -> None:
    # promotion initiale (pas d'ancien)
    audit1 = champion_swapper_sql(
        "AAPL", from_model=None, to_model="m1",
        engine=sqlite_engine, reason="initial", dry_run=False,
    )
    assert audit1["applied"] is True
    assert current_champion_loader_sql("AAPL", engine=sqlite_engine) == "m1"

    # rollback vers m2
    audit2 = champion_swapper_sql(
        "AAPL", from_model="m1", to_model="m2",
        engine=sqlite_engine, reason="streak_3", dry_run=False,
    )
    assert audit2["applied"] is True
    assert current_champion_loader_sql("AAPL", engine=sqlite_engine) == "m2"

    # m1 doit être démoté
    with sqlite_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT model_id, demoted_at FROM champion_history "
            "WHERE symbol='AAPL' ORDER BY id"
        )).fetchall()
    assert rows[0][0] == "m1" and rows[0][1] is not None
    assert rows[1][0] == "m2" and rows[1][1] is None


def test_champion_swapper_sql_dry_run_no_write(sqlite_engine) -> None:
    audit = champion_swapper_sql(
        "MSFT", from_model=None, to_model="m1",
        engine=sqlite_engine, reason="x", dry_run=True,
    )
    assert audit["applied"] is False
    assert current_champion_loader_sql("MSFT", engine=sqlite_engine) is None


def test_auto_rollback_e2e_triggers_swap_after_streak(sqlite_engine) -> None:
    # 4 jours ALERT consécutifs → gate disabled streak=4 ≥ threshold=3
    _insert_drift(sqlite_engine, symbol="TSLA",
                  days=[(0, "ALERT"), (1, "ALERT"), (2, "ALERT"), (3, "ALERT")])
    # champion initial
    champion_swapper_sql("TSLA", from_model=None, to_model="champion-v1",
                         engine=sqlite_engine, reason="initial", dry_run=False)

    outcome = auto_rollback_if_needed(
        "TSLA",
        engine=sqlite_engine,
        threshold_days=3,
        dry_run=False,
        decision_history_loader=decision_history_loader_sql,
        challenger_resolver=lambda symbol, *, engine, current_champion: "challenger-v2",
        champion_swapper=champion_swapper_sql,
        current_champion_loader=current_champion_loader_sql,
    )
    assert outcome.triggered is True
    assert outcome.previous_champion == "champion-v1"
    assert outcome.promoted_challenger == "challenger-v2"
    assert current_champion_loader_sql("TSLA", engine=sqlite_engine) == "challenger-v2"


def test_auto_rollback_e2e_below_threshold_no_swap(sqlite_engine) -> None:
    _insert_drift(sqlite_engine, symbol="GOOG",
                  days=[(0, "ALERT"), (1, "OK")])
    outcome = auto_rollback_if_needed(
        "GOOG",
        engine=sqlite_engine,
        threshold_days=3,
        dry_run=False,
        decision_history_loader=decision_history_loader_sql,
        challenger_resolver=lambda *a, **k: "x",
        champion_swapper=champion_swapper_sql,
        current_champion_loader=current_champion_loader_sql,
    )
    assert outcome.triggered is False
    assert outcome.reason == "below_threshold"


