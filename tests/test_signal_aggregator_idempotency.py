"""Sprint S1 / Anomalie A-022 — Idempotence `signal_aggregator`.

Vérifie que les helpers d'idempotence du module signal_aggregator :

- détectent un trade_date déjà traité,
- isolent les périmètres (`--all-symbols` vs candidats),
- respectent l'override `SIGNAL_AGGREGATOR_LOCK_DIR_ENV` pour les tests.

On évite volontairement d'invoquer `main()` (qui requiert une connexion
DB) ; les helpers internes sont la véritable barrière.
"""
from __future__ import annotations

from datetime import date

import pytest

from event_sentiment import signal_aggregator as sa


@pytest.fixture
def lock_dir(tmp_path, monkeypatch) -> str:
    monkeypatch.setenv(sa.SIGNAL_AGGREGATOR_LOCK_DIR_ENV, str(tmp_path))
    return str(tmp_path)


def test_no_lock_initially(lock_dir) -> None:
    assert sa._is_already_run(date(2026, 5, 6), all_symbols=False) is False


def test_mark_then_detect(lock_dir) -> None:
    d = date(2026, 5, 6)
    sa._mark_run_done(d, all_symbols=False)
    assert sa._is_already_run(d, all_symbols=False) is True


def test_scope_isolation_all_vs_candidates(lock_dir) -> None:
    d = date(2026, 5, 6)
    sa._mark_run_done(d, all_symbols=False)
    # Un run "candidates" ne doit pas bloquer un run "--all-symbols" et vice-versa.
    assert sa._is_already_run(d, all_symbols=True) is False
    sa._mark_run_done(d, all_symbols=True)
    assert sa._is_already_run(d, all_symbols=True) is True


def test_lock_dir_env_override(lock_dir) -> None:
    d = date(2026, 5, 6)
    sa._mark_run_done(d, all_symbols=False)
    expected = sa._lock_path(d, all_symbols=False)
    assert expected.exists()
    assert str(expected).startswith(lock_dir)


def test_allow_rerun_flag_present_on_cli() -> None:
    """Vérifie que la CLI expose bien le flag --allow-rerun."""
    parser = sa._build_arg_parser()
    args = parser.parse_args(["--allow-rerun"])
    assert args.allow_rerun is True

    args_default = parser.parse_args([])
    assert args_default.allow_rerun is False

