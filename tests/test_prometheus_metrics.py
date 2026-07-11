"""Sprint S5 — Tests du module ``common.metrics`` (métriques pipeline)."""
from __future__ import annotations

import pytest

import common.metrics as cm


def test_common_metrics_importable() -> None:
    """Le module doit être importable et exposer les métriques attendues."""
    assert hasattr(cm, "pipeline_steps_total")
    assert hasattr(cm, "pipeline_duration_seconds")
    assert hasattr(cm, "selections_count")
    assert hasattr(cm, "ml_train_duration_seconds")
    assert hasattr(cm, "db_backup_total")
    assert hasattr(cm, "ml_backup_total")
    assert hasattr(cm, "record_pipeline_step")


def test_metrics_are_not_none() -> None:
    """Chaque métrique est non-None (objet no-op ou prometheus réel)."""
    assert cm.pipeline_steps_total is not None
    assert cm.pipeline_duration_seconds is not None
    assert cm.selections_count is not None
    assert cm.ml_train_duration_seconds is not None
    assert cm.db_backup_total is not None
    assert cm.ml_backup_total is not None


def test_pipeline_steps_total_labels_inc_never_raises() -> None:
    """Counter.labels().inc() ne doit jamais lever d'exception."""
    cm.pipeline_steps_total.labels(step="screener", status="OK").inc()
    cm.pipeline_steps_total.labels(step="sanitizer", status="ERROR").inc()


def test_pipeline_duration_seconds_observe_never_raises() -> None:
    cm.pipeline_duration_seconds.labels(step="screener").observe(12.5)


def test_selections_count_set_never_raises() -> None:
    cm.selections_count.set(42)


def test_ml_train_duration_seconds_observe_never_raises() -> None:
    cm.ml_train_duration_seconds.labels(symbol="AAPL").observe(120.0)


def test_db_backup_total_inc_never_raises() -> None:
    cm.db_backup_total.labels(status="OK").inc()
    cm.db_backup_total.labels(status="ERROR").inc()


def test_ml_backup_total_inc_never_raises() -> None:
    cm.ml_backup_total.labels(status="OK").inc()


def test_record_pipeline_step_ok() -> None:
    """Le context-manager doit s'exécuter sans lever sur chemin nominal."""
    with cm.record_pipeline_step("test_step"):
        pass  # no-op


def test_record_pipeline_step_propagates_exception() -> None:
    """Le context-manager doit propager l'exception et émettre status=ERROR."""
    with pytest.raises(ValueError, match="test error"):
        with cm.record_pipeline_step("failing_step"):
            raise ValueError("test error")


def test_record_pipeline_step_ok_after_exception() -> None:
    """Un step suivant réussit même si le précédent a échoué."""
    try:
        with cm.record_pipeline_step("step_err"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with cm.record_pipeline_step("step_ok"):
        pass  # doit passer sans erreur


def test_is_available_returns_bool() -> None:
    """is_available() doit retourner un bool (True si prometheus_client installé)."""
    result = cm.is_available()
    assert isinstance(result, bool)

