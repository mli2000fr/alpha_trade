"""CN backup runner cannot fall back to the US database or archive directory."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from service.market import cn_db_backup_17b as backup


def _config(tmp_path: Path, **overrides) -> Path:
    cfg = {"enabled": False, "status": "ACTIVE", "db": "alpha_trade_cn", "database_alias": "cn_primary",
           "dest_dir": str(backup.CN_DEST), "archive_prefix": "alpha_trade_cn",
           "keep": 3, "output_root": str(tmp_path / "reports")}
    cfg.update(overrides)
    path = tmp_path / "batch_cn.yaml"
    path.write_text(yaml.safe_dump({backup.BATCH_NAME: cfg}), encoding="utf-8")
    return path


def test_disabled_cn_backup_is_not_run(monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "backup_db", lambda **_kwargs: pytest.fail("backup started"))
    assert backup.run(config_path=_config(tmp_path))["status"] == "SKIP_DISABLED"


def test_pending_status_blocks_even_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(backup, "backup_db", lambda **_kwargs: pytest.fail("backup started"))
    config = _config(tmp_path, enabled=True, status="PENDING_RESTORE_PROOF")
    assert backup.run(config_path=config)["status"] == "SKIP_RESTORE_PROOF_REQUIRED"
    assert backup.run(config_path=config, force=True)["status"] == "SKIP_RESTORE_PROOF_REQUIRED"


@pytest.mark.parametrize("changes", [
    {"db": "alpha_trade"}, {"database_alias": "us_primary"},
    {"dest_dir": "backups/db"}, {"archive_prefix": "alpha_trade"}, {"keep": 0},
])
def test_cn_backup_contract_rejects_us_or_unsafe_configuration(monkeypatch, tmp_path, changes):
    monkeypatch.setattr(backup, "backup_db", lambda **_kwargs: pytest.fail("backup started"))
    with pytest.raises(ValueError, match="CN backup contract"):
        backup.run(config_path=_config(tmp_path, **changes), force=True, dry_run=True)


def test_cn_backup_dry_run_passes_isolated_arguments_without_file_write(monkeypatch, tmp_path):
    calls = []
    def fake_backup(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(dump_path="planned.sql.gz", dump_size_bytes=0,
                               rotated_files=[], kept_files=[], errors=[])
    monkeypatch.setattr(backup, "backup_db", fake_backup)
    report = backup.run(config_path=_config(tmp_path), force=True, dry_run=True)
    assert report["status"] == "DRY_RUN"
    assert report["us_database_modified"] is False
    assert calls[0]["db"] == "alpha_trade_cn"
    assert calls[0]["dest_dir"] == backup.CN_DEST
    assert calls[0]["archive_prefix"] == "alpha_trade_cn"
    assert not (tmp_path / "reports").exists()
