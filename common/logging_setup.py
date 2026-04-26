"""Configuration logging — extrait de ``common/utils.py`` (Phase 2.1).

Concentre :
- ``configure_root_logging`` : entrée principale CLI/IHM.
- ``setup_logging_with_file_handler`` : helper rétrocompatible (alias).
- ``DEFAULT_LOG_FORMAT`` : format unique partagé.

Les fonctions privées (``_resolve_log_path``, ``_configure_utf8_stdio``,
``_reset_root_logging_handlers``) restent exposées car référencées par
quelques tests.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s -- %(message)s"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_log_path(log_path: str) -> Path:
    candidate = Path(log_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _configure_utf8_stdio() -> None:
    """Force stdout/stderr en UTF-8 quand le runtime le permet."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _reset_root_logging_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def configure_root_logging(
    *,
    level: int = logging.INFO,
    log_path: str | None = None,
    fmt: str = DEFAULT_LOG_FORMAT,
    datefmt: str | None = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure le root logger du projet avec sortie stdout et fichier optionnel."""
    _configure_utf8_stdio()
    logger = logging.getLogger()
    logger.setLevel(level)
    _reset_root_logging_handlers(logger)

    formatter = logging.Formatter(fmt, datefmt=datefmt)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    stdout_handler._alpha_trade_managed = True  # type: ignore[attr-defined]
    logger.addHandler(stdout_handler)

    if log_path:
        resolved_log_path = _resolve_log_path(log_path)
        file_handler = RotatingFileHandler(
            resolved_log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        file_handler._alpha_trade_managed = True  # type: ignore[attr-defined]
        logger.addHandler(file_handler)

    return logger


def setup_logging_with_file_handler(
    log_path: str = "alpha_trade.log",
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Helper rétrocompatible : configure stdout + RotatingFileHandler."""
    return configure_root_logging(
        level=logging.INFO,
        log_path=log_path,
        fmt=DEFAULT_LOG_FORMAT,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )


__all__ = [
    "DEFAULT_LOG_FORMAT",
    "PROJECT_ROOT",
    "configure_root_logging",
    "setup_logging_with_file_handler",
]

