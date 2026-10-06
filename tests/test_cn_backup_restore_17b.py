"""CN restore target and archive must be isolated from production and US."""

from pathlib import Path

import pytest

from service.market.cn_backup_restore_17b import validate_archive, validate_restore_name


@pytest.mark.parametrize("name", [
    "alpha_trade", "alpha_trade_cn", "alpha_trade_cn_restore_", "alpha_trade_cn_restore_gggggggg",
    "alpha_trade_cn_restore_12345678;DROP DATABASE alpha_trade",
])
def test_restore_name_rejects_production_or_unsafe_names(name):
    with pytest.raises(ValueError, match="Unsafe"):
        validate_restore_name(name)


def test_restore_name_accepts_only_generated_pattern():
    assert validate_restore_name("alpha_trade_cn_restore_1a2b3c4d") == "alpha_trade_cn_restore_1a2b3c4d"


def test_archive_must_be_nonempty_cn_backup_inside_cn_directory(tmp_path: Path):
    root = tmp_path / "backups" / "cn" / "db"
    root.mkdir(parents=True)
    good = root / "alpha_trade_cn_20260930_192427.sql.gz"
    good.write_bytes(b"gzip-placeholder")
    assert validate_archive(good, backup_root=root) == good.resolve()
    us = tmp_path / "backups" / "db" / good.name
    us.parent.mkdir()
    us.write_bytes(b"gzip-placeholder")
    with pytest.raises(ValueError, match="isolated"):
        validate_archive(us, backup_root=root)
    empty = root / "alpha_trade_cn_20260930_192428.sql.gz"
    empty.touch()
    with pytest.raises(ValueError, match="nonempty"):
        validate_archive(empty, backup_root=root)
