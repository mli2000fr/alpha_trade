"""Tests d'intégration batch_diagnostics → orchestrator.

Vérifie que ``persist_batch_diagnostics`` est appelé correctement
à la fin de ``run_training_batch()``.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from modelFactory import orchestrator
from modelFactory.config import ChampionSelectionConfig, DataConfig, ModelConfig, TrainingConfig


# ── Helpers ────────────────────────────────────────────────────────

def _make_completed_worker(symbol: str) -> orchestrator.TrainResult:
    return orchestrator.TrainResult(symbol, f"run-{symbol}", "completed")


def _make_skipped_worker(symbol: str) -> orchestrator.TrainResult:
    return orchestrator.TrainResult(symbol, f"run-{symbol}", "skipped")


def _make_failed_worker(symbol: str) -> orchestrator.TrainResult:
    return orchestrator.TrainResult(symbol, f"run-{symbol}", "failed")


# ── Tests ──────────────────────────────────────────────────────────

class TestBatchDiagnosticsInOrchestrator:

    def test_persist_called_when_at_least_one_completed(self, monkeypatch, tmp_path):
        """Si au moins un worker a completed, persist_batch_diagnostics est appelé."""
        cfg = TrainingConfig(
            data=DataConfig(),
            model=ModelConfig(max_epochs=1),
            artifacts_dir=tmp_path,
            max_workers=1,
            accelerator="cpu",
        )

        monkeypatch.setattr(
            orchestrator,
            "load_symbols_for_source",
            lambda engine, symbol_source, *, trade_date: ["AAPL", "MSFT"],
        )
        monkeypatch.setattr(
            orchestrator,
            "_train_worker",
            lambda symbol, cfg, **kwargs: _make_completed_worker(symbol),
        )

        persist_calls: list = []

        def fake_persist(engine, batch_id, **kwargs):
            persist_calls.append((engine, batch_id, kwargs))
            return 5  # 5 rows insérées

        monkeypatch.setattr(orchestrator, "persist_batch_diagnostics", fake_persist)

        results = orchestrator.run_training_batch(
            cfg,
            engine=MagicMock(),
            symbols=["AAPL", "MSFT"],
            universe_date=date(2026, 7, 23),
        )

        assert len(persist_calls) == 1
        assert persist_calls[0][0] is not None  # engine
        assert isinstance(persist_calls[0][1], str)  # batch_id
        assert len(results) == 2

    def test_persist_not_called_when_all_failed(self, monkeypatch, tmp_path):
        """Si aucun worker n'a completed, persist_batch_diagnostics n'est PAS appelé."""
        cfg = TrainingConfig(
            data=DataConfig(),
            model=ModelConfig(max_epochs=1),
            artifacts_dir=tmp_path,
            max_workers=1,
            accelerator="cpu",
        )

        monkeypatch.setattr(
            orchestrator,
            "load_symbols_for_source",
            lambda engine, symbol_source, *, trade_date: ["AAPL"],
        )
        monkeypatch.setattr(
            orchestrator,
            "_train_worker",
            lambda symbol, cfg, **kwargs: _make_failed_worker(symbol),
        )

        persist_calls: list = []

        def fake_persist(engine, batch_id, **kwargs):
            persist_calls.append(1)
            return 0

        monkeypatch.setattr(orchestrator, "persist_batch_diagnostics", fake_persist)

        results = orchestrator.run_training_batch(
            cfg,
            engine=MagicMock(),
            symbols=["AAPL"],
            universe_date=date(2026, 7, 23),
        )

        assert len(persist_calls) == 0
        assert len(results) == 1
        assert results[0].status == "failed"

    def test_persist_not_called_when_all_skipped(self, monkeypatch, tmp_path):
        """Si tous les workers sont skipped, persist_batch_diagnostics n'est PAS appelé."""
        cfg = TrainingConfig(
            data=DataConfig(),
            model=ModelConfig(max_epochs=1),
            artifacts_dir=tmp_path,
            max_workers=1,
            accelerator="cpu",
        )

        monkeypatch.setattr(
            orchestrator,
            "load_symbols_for_source",
            lambda engine, symbol_source, *, trade_date: ["AAPL"],
        )
        monkeypatch.setattr(
            orchestrator,
            "_train_worker",
            lambda symbol, cfg, **kwargs: _make_skipped_worker(symbol),
        )

        persist_calls: list = []

        def fake_persist(engine, batch_id, **kwargs):
            persist_calls.append(1)
            return 0

        monkeypatch.setattr(orchestrator, "persist_batch_diagnostics", fake_persist)

        results = orchestrator.run_training_batch(
            cfg,
            engine=MagicMock(),
            symbols=["AAPL"],
            universe_date=date(2026, 7, 23),
        )

        assert len(persist_calls) == 0
        assert results[0].status == "skipped"

    def test_persist_exception_is_caught(self, monkeypatch, tmp_path):
        """Si persist_batch_diagnostics lève une exception, run_training_batch
        ne propage PAS l'erreur (non-bloquant)."""
        cfg = TrainingConfig(
            data=DataConfig(),
            model=ModelConfig(max_epochs=1),
            artifacts_dir=tmp_path,
            max_workers=1,
            accelerator="cpu",
        )

        monkeypatch.setattr(
            orchestrator,
            "load_symbols_for_source",
            lambda engine, symbol_source, *, trade_date: ["AAPL"],
        )
        monkeypatch.setattr(
            orchestrator,
            "_train_worker",
            lambda symbol, cfg, **kwargs: _make_completed_worker(symbol),
        )

        def fake_persist_raising(engine, batch_id, **kwargs):
            raise RuntimeError("DB down during persist")

        monkeypatch.setattr(orchestrator, "persist_batch_diagnostics", fake_persist_raising)

        # Ne doit PAS lever d'exception
        results = orchestrator.run_training_batch(
            cfg,
            engine=MagicMock(),
            symbols=["AAPL"],
            universe_date=date(2026, 7, 23),
        )

        assert len(results) == 1
        assert results[0].status == "completed"

    def test_persist_receives_correct_batch_id(self, monkeypatch, tmp_path):
        """Vérifie que le batch_id passé à persist est le bon."""
        cfg = TrainingConfig(
            data=DataConfig(),
            model=ModelConfig(max_epochs=1),
            artifacts_dir=tmp_path,
            max_workers=1,
            accelerator="cpu",
        )

        monkeypatch.setattr(
            orchestrator,
            "load_symbols_for_source",
            lambda engine, symbol_source, *, trade_date: ["AAPL"],
        )
        monkeypatch.setattr(
            orchestrator,
            "_train_worker",
            lambda symbol, cfg, **kwargs: _make_completed_worker(symbol),
        )

        received_batch_id: list[str] = []

        def fake_persist(engine, batch_id, **kwargs):
            received_batch_id.append(batch_id)
            return 3

        monkeypatch.setattr(orchestrator, "persist_batch_diagnostics", fake_persist)

        orchestrator.run_training_batch(
            cfg,
            engine=MagicMock(),
            symbols=["AAPL"],
            batch_id="my-custom-batch-42",
            universe_date=date(2026, 7, 23),
        )

        assert received_batch_id == ["my-custom-batch-42"]
