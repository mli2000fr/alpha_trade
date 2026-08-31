"""Tests de modelFactory.cleanup_incomplete_batches.

Couvre notamment le garde-fou P-fix (2026-08-30) : un batch dont la suppression
DB a échoué ne doit PAS voir son répertoire artifacts/models/<id> supprimé
(état incohérent « dossiers disparus, DB présente » observé sur les batchs
[Rank + Oracle] du 29/08 22:52 avec la pool MySQL saturée).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modelFactory import cleanup_incomplete_batches as cib


def test_is_safe_batch_id_blocks_malformed_ids() -> None:
    assert cib._is_safe_batch_id("model-factory-20260829225200-355580") is True
    assert cib._is_safe_batch_id("") is False
    assert cib._is_safe_batch_id(".") is False
    assert cib._is_safe_batch_id("..") is False
    assert cib._is_safe_batch_id("a/b") is False
    assert cib._is_safe_batch_id("a\\b") is False


def test_cleanup_batches_keeps_dir_when_db_delete_fails(tmp_path: Path, monkeypatch) -> None:
    """P-fix : si delete_batch_rows échoue (lock/timeout MySQL), le répertoire du
    batch ne doit PAS être supprimé — sinon on perd les modèles disque en gardant
    les lignes DB (état incohérent observé en prod)."""
    bid = "model-factory-20260829225200-355580"

    # Répertoire artifacts/models/<bid> simulé sous tmp_path (chdir pour la
    # résolution du chemin relatif "artifacts/models" de cleanup_batches).
    batch_dir = tmp_path / "artifacts" / "models" / bid
    batch_dir.mkdir(parents=True)
    (batch_dir / "global_rank_cache.parquet").write_bytes(b"fake-model")
    monkeypatch.chdir(tmp_path)

    # list_batches → le batch est ciblé ; delete_batch_rows → échec (DB saturée)
    monkeypatch.setattr(cib, "list_batches", lambda include_completed=False: [bid])
    monkeypatch.setattr(
        "modelFactory.db_registry.delete_batch_rows",
        lambda engine, batch_id: (_ for _ in ()).throw(RuntimeError("QueuePool limit reached")),
    )
    monkeypatch.setattr("ihm.services.db.get_engine", lambda: MagicMock())

    result = cib.cleanup_batches(dry_run=False)

    assert result["deleted_batches"] == 0
    assert result["deleted_dirs"] == 0
    # Le dossier DOIT être conservé car la suppression DB a échoué
    assert batch_dir.exists()
    assert (batch_dir / "global_rank_cache.parquet").exists()
    # La tentative bloquée DOIT être tracée dans le journal d'audit
    audit_file = tmp_path / "log" / "batch_delete_audit.log"
    assert audit_file.exists()
    content = audit_file.read_text(encoding="utf-8")
    assert "DELETE-ATTEMPT-BLOCKED" in content
    assert f"batch={bid}" in content
    assert "rmtree disque sauté" in content


def test_cleanup_batches_deletes_dir_when_db_delete_ok(tmp_path: Path, monkeypatch) -> None:
    """Comportement nominal : suppression DB OK → le répertoire est bien supprimé."""
    bid = "model-factory-20260829225200-355580"

    batch_dir = tmp_path / "artifacts" / "models" / bid
    batch_dir.mkdir(parents=True)
    (batch_dir / "global_rank_cache.parquet").write_bytes(b"fake-model")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(cib, "list_batches", lambda include_completed=False: [bid])
    monkeypatch.setattr(
        "modelFactory.db_registry.delete_batch_rows",
        lambda engine, batch_id: {
            "model_metrics": 3,
            "model_metrics_full": 0,
            "model_governance": 1,
            "model_predictions": 0,
            "model_training_run": 1,
            "model_training_batch": 1,
        },
    )
    monkeypatch.setattr("ihm.services.db.get_engine", lambda: MagicMock())

    result = cib.cleanup_batches(dry_run=False)

    assert result["deleted_batches"] == 1
    assert result["deleted_dirs"] == 1
    assert not batch_dir.exists()


def test_audit_batch_delete_attempt_writes_log(tmp_path: Path, monkeypatch) -> None:
    """Les tentatives de suppression bloquées doivent être tracées dans le journal
    d'audit (avec pile d'appel), pour identifier le déclencheur même sans suppression."""
    from modelFactory.db_registry import audit_batch_delete_attempt

    monkeypatch.chdir(tmp_path)

    audit_batch_delete_attempt(
        "model-factory-20260829225200-355580",
        reason="garde-fou: statut `running` (interdit)",
        source="delete_batch_rows",
    )

    audit_file = tmp_path / "log" / "batch_delete_audit.log"
    assert audit_file.exists()
    content = audit_file.read_text(encoding="utf-8")
    assert "DELETE-ATTEMPT-BLOCKED" in content
    assert "batch=model-factory-20260829225200-355580" in content
    assert "statut `running`" in content
    assert "source=delete_batch_rows" in content
    # La pile d'appel doit être présente (traceback complet)
    assert "test_audit_batch_delete_attempt_writes_log" in content
