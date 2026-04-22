from __future__ import annotations

from pathlib import Path

from common import utils


def test_configure_root_logging_creates_relative_log_directory_from_project_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(utils, "PROJECT_ROOT", tmp_path)

    logger = utils.configure_root_logging(log_path="./log/test_update_sector.log")

    try:
        expected_log_path = tmp_path / "log" / "test_update_sector.log"
        assert expected_log_path.exists()
    finally:
        for handler in list(logger.handlers):
            try:
                handler.close()
            except Exception:
                pass
            logger.removeHandler(handler)

