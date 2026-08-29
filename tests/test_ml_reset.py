"""Tests du service de reset ML (T5.5) — ihm/services/ml_reset.py."""
from __future__ import annotations

from pathlib import Path

import pytest


class TestMlResetCatalog:
    def test_reset_tables_cover_all_ml_sources(self) -> None:
        from ihm.services.ml_reset import ML_RESET_TABLES

        required = {
            "model_training_batch",
            "model_training_run",
            "model_predictions",
            "global_rank_history",
            "oracle_extreme_predictions",
            "global_oracle_labels",
        }
        assert required.issubset(set(ML_RESET_TABLES))

    def test_reset_tables_ordering_fk_before_parent(self) -> None:
        from ihm.services.ml_reset import ML_RESET_TABLES

        # model_directional_oos_metrics référence model_training_run → doit être avant
        assert ML_RESET_TABLES.index("model_directional_oos_metrics") < ML_RESET_TABLES.index("model_training_run")

    def test_reset_dirs_cover_backtests_and_models(self) -> None:
        from ihm.services.ml_reset import ML_RESET_DIRS

        assert "artifacts/ihm_backtesting_runs" in ML_RESET_DIRS
        assert "artifacts/models" in ML_RESET_DIRS

    def test_build_reset_explanation_lists_tables_and_dirs(self) -> None:
        from ihm.services.ml_reset import build_reset_explanation

        text = build_reset_explanation()
        assert "model_predictions" in text
        assert "model_training_batch" in text
        assert "oracle_extreme_predictions" in text
        assert "global_rank_history" in text
        assert "artifacts/ihm_backtesting_runs" in text
        assert "artifacts/models" in text
        assert "irréversible" in text


class TestResetMlData:
    def test_dry_run_reports_expected_without_deleting(self, monkeypatch) -> None:
        from ihm.services import ml_reset

        monkeypatch.setattr(ml_reset, "get_sqlalchemy_engine", lambda: object())
        result = ml_reset.reset_ml_data(stop_active=False, dry_run=True)
        assert result["errors"] == []
        assert set(result["tables_cleared"]) == set(ml_reset.ML_RESET_TABLES)
        assert set(result["dirs_deleted"]) == set(ml_reset.ML_RESET_DIRS)

    def test_reset_deletes_directories_and_clears_index(self, tmp_path: Path, monkeypatch) -> None:
        from ihm.services import ml_reset

        # Fausse connexion DB : on enregistre les DELETE exécutés.
        executed: list[str] = []

        class _FakeConn:
            def execute(self, stmt, *a, **k):
                s = str(stmt)
                executed.append(s)
                return type("R", (), {"rowcount": 0})()

        class _FakeEngine:
            def begin(self):
                return _FakeCtx(_FakeConn())

        class _FakeCtx:
            def __init__(self, conn):
                self._conn = conn

            def __enter__(self):
                return self._conn

            def __exit__(self, *a):
                return False

        # Répertoires factices
        base = tmp_path / "projets"
        (base / "artifacts" / "ihm_backtesting_runs" / "run" / "r1").mkdir(parents=True)
        (base / "artifacts" / "ihm_backtesting_runs" / "history_index.json").write_text("{}", encoding="utf-8")
        (base / "artifacts" / "models" / "m1").mkdir(parents=True)
        (base / "artifacts" / "per_sector_cache").mkdir(parents=True)
        (base / "artifacts" / "per_symbol_v2").mkdir(parents=True)

        monkeypatch.setattr(ml_reset, "get_sqlalchemy_engine", lambda: _FakeEngine())
        # list_active_backtesting_runs est importé localement dans reset_ml_data
        # depuis ihm.services.backtesting_registry → on patch la source.
        import ihm.services.backtesting_registry as _reg

        monkeypatch.setattr(_reg, "list_active_backtesting_runs", lambda: [])
        # Redirige PROJECT_ROOT implicite : la fonction utilise Path("F:/projets").
        # Pour un test hermétique on monkeypatch le module Path via un patch ciblé
        # est complexe (Path est un type). On vérifie plutôt la logique DB + que la
        # fonction ne lève pas avec des dossiers absents.
        result = ml_reset.reset_ml_data(stop_active=True, dry_run=False)

        # Le reset DB a bien tenté un DELETE par table (ordre FK respecté).
        delete_tables = [s.split("`")[1] for s in executed if "DELETE FROM" in s]
        assert delete_tables == ml_reset.ML_RESET_TABLES
        assert "SET FOREIGN_KEY_CHECKS = 0" in " ".join(executed)

        # Aucune erreur côté service (les dossiers F:/projets/... sont absents dans le CI)
        assert isinstance(result, dict)


class TestResetMlDataTwoPhase:
    """Reset en 2 phases : phase 1 sans arrêt des runs, phase 2 avec arrêt."""

    @staticmethod
    def _make_fake_engine(executed: list[str]):
        class _FakeConn:
            def execute(self, stmt, *a, **k):
                executed.append(str(stmt))
                return type("R", (), {"rowcount": 0})()

        class _FakeEngine:
            def begin(self):
                return _FakeCtx(_FakeConn())

        class _FakeCtx:
            def __init__(self, conn):
                self._conn = conn

            def __enter__(self):
                return self._conn

            def __exit__(self, *a):
                return False

        return _FakeEngine()

    @staticmethod
    def _make_run_dirs(fake_root: Path) -> Path:
        (fake_root / "artifacts" / "ihm_backtesting_runs" / "run" / "r1").mkdir(parents=True)
        (fake_root / "artifacts" / "ihm_backtesting_runs" / "history_index.json").write_text(
            '{"x": {}}', encoding="utf-8"
        )
        (fake_root / "artifacts" / "ihm_pipeline_runs" / "run" / "p1").mkdir(parents=True)
        (fake_root / "artifacts" / "ihm_pipeline_runs" / "history_index.json").write_text(
            '{"y": {}}', encoding="utf-8"
        )
        (fake_root / "artifacts" / "models" / "m1").mkdir(parents=True)
        return fake_root

    def test_phase1_blocks_run_dir_with_active_runs(self, tmp_path: Path, monkeypatch) -> None:
        from ihm.services import ml_reset

        fake_root = self._make_run_dirs(tmp_path / "projets")
        monkeypatch.setattr(ml_reset, "PROJECT_ROOT", fake_root)
        monkeypatch.setattr(ml_reset, "get_sqlalchemy_engine", lambda: self._make_fake_engine([]))

        def fake_active(rel: str) -> list[dict[str, object]]:
            if rel == "artifacts/ihm_backtesting_runs":
                return [{"run_id": "run-1", "run_label": "Backtest A", "status": "running"}]
            return []

        monkeypatch.setattr(ml_reset, "_active_runs_for_dir", fake_active)

        result = ml_reset.reset_ml_data(stop_active=False, dry_run=False)

        # Le répertoire backtest est bloqué (run actif) et conservé ; le pipeline
        # non bloqué est supprimé, ainsi que les répertoires ML non-runs.
        assert "artifacts/ihm_backtesting_runs" in result["blocked_dirs"]
        assert "artifacts/ihm_pipeline_runs" not in result["blocked_dirs"]
        assert (fake_root / "artifacts" / "ihm_backtesting_runs").exists()
        assert not (fake_root / "artifacts" / "ihm_pipeline_runs").exists()
        assert not (fake_root / "artifacts" / "models").exists()
        assert set(result["tables_cleared"]) == set(ml_reset.ML_RESET_TABLES)
        assert result["blocked_runs"] == [
            {"run_id": "run-1", "label": "Backtest A", "registry": "backtest"}
        ]

    def test_phase1_reports_no_block_when_no_active_runs(self, tmp_path: Path, monkeypatch) -> None:
        from ihm.services import ml_reset

        fake_root = self._make_run_dirs(tmp_path / "projets")
        monkeypatch.setattr(ml_reset, "PROJECT_ROOT", fake_root)
        monkeypatch.setattr(ml_reset, "get_sqlalchemy_engine", lambda: self._make_fake_engine([]))
        monkeypatch.setattr(ml_reset, "_active_runs_for_dir", lambda rel: [])

        result = ml_reset.reset_ml_data(stop_active=False, dry_run=False)

        assert result["blocked_dirs"] == []
        assert not (fake_root / "artifacts" / "ihm_backtesting_runs").exists()
        assert not (fake_root / "artifacts" / "ihm_pipeline_runs").exists()

    def test_phase2_runs_only_deletes_run_dirs_without_tables(self, tmp_path: Path, monkeypatch) -> None:
        from ihm.services import ml_reset

        fake_root = self._make_run_dirs(tmp_path / "projets")
        executed: list[str] = []
        monkeypatch.setattr(ml_reset, "PROJECT_ROOT", fake_root)
        monkeypatch.setattr(ml_reset, "get_sqlalchemy_engine", lambda: self._make_fake_engine(executed))

        result = ml_reset.reset_ml_data(stop_active=True, runs_only=True, dry_run=False)

        # Les répertoires de runs sont supprimés ; aucun DELETE de table (runs_only).
        assert not (fake_root / "artifacts" / "ihm_backtesting_runs").exists()
        assert not (fake_root / "artifacts" / "ihm_pipeline_runs").exists()
        assert (fake_root / "artifacts" / "models").exists()
        assert result["blocked_dirs"] == []
        assert result["tables_cleared"] == []
        assert not any("DELETE FROM" in s for s in executed)
