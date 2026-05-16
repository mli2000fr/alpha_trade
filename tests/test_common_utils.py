from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from common import utils
from common import logging_setup


def test_configure_root_logging_creates_relative_log_directory_from_project_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(utils, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(logging_setup, "PROJECT_ROOT", tmp_path)

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


# ---------------------------------------------------------------------------
# Sprint S3 / A-025 — TimedRotatingFileHandler + gzip
# ---------------------------------------------------------------------------

def test_timed_rotation_creates_timed_rotating_file_handler(tmp_path, monkeypatch) -> None:
    """use_timed_rotation=True doit utiliser TimedRotatingFileHandler."""
    monkeypatch.setattr(logging_setup, "PROJECT_ROOT", tmp_path)
    log_path = str(tmp_path / "logs" / "timed.log")

    logger = logging_setup.configure_root_logging(
        log_path=log_path,
        use_timed_rotation=True,
        timed_rotation_when="midnight",
        timed_rotation_backup_count=14,
    )
    try:
        file_handlers = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]
        assert len(file_handlers) == 1, "Un TimedRotatingFileHandler attendu"
        handler = file_handlers[0]
        assert handler.backupCount == 14
        assert handler.when.lower() == "midnight"
        # Vérifier que les helpers gzip sont branchés.
        assert hasattr(handler, "rotator") and callable(getattr(handler, "rotator"))
        assert hasattr(handler, "namer") and callable(getattr(handler, "namer"))
    finally:
        for h in list(logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            logger.removeHandler(h)


def test_gzip_namer_appends_gz_suffix() -> None:
    """_gzip_namer doit ajouter .gz au nom."""
    result = logging_setup._gzip_namer("alpha_trade.log.2026-05-16")
    assert result.endswith(".gz")
    assert "2026-05-16" in result


def test_default_rotation_uses_rotating_file_handler(tmp_path, monkeypatch) -> None:
    """use_timed_rotation=False (défaut) doit conserver RotatingFileHandler."""
    from logging.handlers import RotatingFileHandler

    monkeypatch.setattr(logging_setup, "PROJECT_ROOT", tmp_path)
    log_path = str(tmp_path / "logs" / "default.log")

    logger = logging_setup.configure_root_logging(log_path=log_path, use_timed_rotation=False)
    try:
        rotating_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating_handlers) == 1
        assert not isinstance(rotating_handlers[0], TimedRotatingFileHandler)
    finally:
        for h in list(logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            logger.removeHandler(h)


