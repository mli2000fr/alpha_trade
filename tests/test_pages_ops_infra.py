"""Sprint S5 — Tests de la page ``ihm/pages/ops_infra.py`` et des commandes ops."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Tests des nouvelles commandes dans ops_runner
# ---------------------------------------------------------------------------



class TestBackupMlArtifactsCommand:
    def test_build_backup_ml_default_params(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command("backup_ml_artifacts")
        assert "backup_ml_artifacts.py" in " ".join(cmd)
        assert "--artifacts-dir" in cmd
        assert "--dest-dir" in cmd
        assert "--keep" in cmd

    def test_build_backup_ml_custom_params(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command(
            "backup_ml_artifacts",
            artifacts_dir="my/artifacts",
            dest_dir="my/backups",
            keep=14,
        )
        assert "my/artifacts" in cmd
        assert "my/backups" in cmd
        assert "14" in cmd

    def test_build_backup_ml_dry_run(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command("backup_ml_artifacts", dry_run=True)
        assert "--dry-run" in cmd

    def test_build_backup_ml_no_dry_run_by_default(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command("backup_ml_artifacts")
        assert "--dry-run" not in cmd


class TestBackupDbCommand:
    def test_build_backup_db_default_params(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command("backup_db")
        assert "backup_db.py" in " ".join(cmd)
        assert "--host" in cmd
        assert "--db" in cmd
        assert "--keep" in cmd

    def test_build_backup_db_custom_params(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command(
            "backup_db",
            host="db.example.com",
            db="mydb",
            dest_dir="backups/prod",
            keep=60,
        )
        assert "db.example.com" in cmd
        assert "mydb" in cmd
        assert "backups/prod" in cmd
        assert "60" in cmd

    def test_build_backup_db_dry_run(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        cmd = build_ops_command("backup_db", dry_run=True)
        assert "--dry-run" in cmd


class TestOpsCatalog:
    def test_new_commands_in_catalog(self) -> None:
        from ihm.services.ops_runner import OPS_COMMAND_CATALOG
        assert "backup_ml_artifacts" in OPS_COMMAND_CATALOG
        assert "backup_db" in OPS_COMMAND_CATALOG
        assert "scan_repo_secrets" in OPS_COMMAND_CATALOG
        assert "daily_pipeline" not in OPS_COMMAND_CATALOG

    def test_backup_ml_spec(self) -> None:
        from ihm.services.ops_runner import OPS_COMMAND_CATALOG
        spec = OPS_COMMAND_CATALOG["backup_ml_artifacts"]
        assert spec.icon == "🤖"
        assert not spec.danger

    def test_backup_db_spec(self) -> None:
        from ihm.services.ops_runner import OPS_COMMAND_CATALOG
        spec = OPS_COMMAND_CATALOG["backup_db"]
        assert spec.icon == "🗄️"
        assert not spec.danger

    def test_all_new_commands_unknown_key_raises(self) -> None:
        from ihm.services.ops_runner import build_ops_command
        with pytest.raises(KeyError):
            build_ops_command("nonexistent_command_xyz")  # type: ignore[arg-type]

    def test_scan_repo_secrets_command(self) -> None:
        from ihm.services.ops_runner import build_ops_command

        cmd = build_ops_command("scan_repo_secrets")

        assert "scan_repo_secrets.py" in " ".join(cmd)


# ---------------------------------------------------------------------------
# Tests navigation
# ---------------------------------------------------------------------------


class TestOpsInfraNavigation:
    def test_ops_infra_page_in_navigation(self) -> None:
        from ihm.services.navigation import get_navigation_pages
        pages = get_navigation_pages()
        keys = [p.key for p in pages]
        assert "ops_infra" in keys

    def test_ops_infra_in_workflow_section(self) -> None:
        from ihm.services.navigation import get_navigation_sections
        sections = get_navigation_sections()
        workflow = next((s for s in sections if s.key == "workflow"), None)
        assert workflow is not None
        keys = [p.key for p in workflow.pages]
        assert "ops_infra" in keys

    def test_ops_infra_module_importable(self) -> None:
        import ihm.pages.ops_infra as page
        assert hasattr(page, "render")

    def test_ops_infra_label_and_icon(self) -> None:
        from ihm.services.navigation import get_navigation_pages
        page = next((p for p in get_navigation_pages() if p.key == "ops_infra"), None)
        assert page is not None
        assert "Infra" in page.label
        assert "🔧" in page.label


# ---------------------------------------------------------------------------
# Tests page ops_infra (render fonctions utilitaires)
# ---------------------------------------------------------------------------


class TestOpsInfraHelpers:
    def test_list_existing_archives_empty_dir(self, tmp_path: Path) -> None:
        from ihm.pages.ops_infra import _list_existing_archives
        archives = _list_existing_archives(str(tmp_path))
        assert archives == []

    def test_list_existing_archives_missing_dir(self, tmp_path: Path) -> None:
        from ihm.pages.ops_infra import _list_existing_archives
        archives = _list_existing_archives(str(tmp_path / "nonexistent"))
        assert archives == []

    def test_list_existing_archives_sorted_newest_first(self, tmp_path: Path) -> None:
        import time
        from ihm.pages.ops_infra import _list_existing_archives
        a1 = tmp_path / "ml_artifacts_20260101_000000.tar.gz"
        a1.write_bytes(b"x")
        time.sleep(0.01)
        a2 = tmp_path / "ml_artifacts_20260102_000000.tar.gz"
        a2.write_bytes(b"x")
        archives = _list_existing_archives(str(tmp_path), "ml_artifacts_*.tar.gz")
        assert len(archives) == 2
        # La plus récente (a2) doit être en premier
        assert archives[0].name == a2.name

    def test_list_existing_archives_sql_gz(self, tmp_path: Path) -> None:
        from ihm.pages.ops_infra import _list_existing_archives
        (tmp_path / "alpha_trade_20260101.sql.gz").write_bytes(b"x")
        (tmp_path / "other.txt").write_text("ignored")
        archives = _list_existing_archives(str(tmp_path), "*.sql.gz")
        assert len(archives) == 1
        assert archives[0].suffix == ".gz"

