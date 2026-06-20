"""Configuration logging — extrait de ``common/utils.py`` (Phase 2.1).

Concentre :
- ``configure_root_logging`` : entrée principale CLI/IHM.
- ``setup_logging_with_file_handler`` : helper rétrocompatible (alias).
- ``DEFAULT_LOG_FORMAT`` : format unique partagé.

Les fonctions privées (``_resolve_log_path``, ``_configure_utf8_stdio``,
``_reset_root_logging_handlers``) restent exposées car référencées par
quelques tests.

Sprint S3 / A-025 : ajout de ``use_timed_rotation`` pour basculer sur un
``TimedRotatingFileHandler`` (rotation quotidienne à minuit) avec compression
gzip automatique des archives via ``rotator`` + ``namer``.
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, cast

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s -- %(message)s"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _is_windows_sharing_violation(exc: BaseException) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 32


class _WindowsSafeRolloverMixin:
    """Tolère les échecs de rotation quand Windows verrouille encore le fichier.

    Cas typique : plusieurs processus écrivent dans le même log et l'un d'eux
    tente un rename pendant qu'un autre conserve un handle ouvert. Au lieu de
    faire remonter un logging error, on rouvre simplement le flux courant en
    mode append et on continue à écrire dans le fichier principal.
    """

    def _recover_after_rollover_failure(self) -> None:
        stream = getattr(self, "stream", None)
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        self.stream = None
        reopen = getattr(self, "_open", None)
        if callable(reopen):
            self.stream = reopen()

class SafeRotatingFileHandler(_WindowsSafeRolloverMixin, RotatingFileHandler):
    """RotatingFileHandler robuste aux verrous de fichiers sous Windows."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError as exc:
            if not _is_windows_sharing_violation(exc):
                raise
            self._recover_after_rollover_failure()


class SafeTimedRotatingFileHandler(_WindowsSafeRolloverMixin, TimedRotatingFileHandler):
    """TimedRotatingFileHandler robuste aux verrous de fichiers sous Windows."""

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError as exc:
            if not _is_windows_sharing_violation(exc):
                raise
            self._recover_after_rollover_failure()


# ---------------------------------------------------------------------------
# S3 / A-025 — helpers gzip pour TimedRotatingFileHandler
# ---------------------------------------------------------------------------

def _gzip_rotator(source: str, dest: str) -> None:
    """Compresse ``source`` en gzip puis le supprime."""
    gz_dest = dest + ".gz"
    with open(source, "rb") as f_in, gzip.open(gz_dest, "wb") as f_out:
        shutil.copyfileobj(f_in, cast(Any, f_out))
    os.remove(source)


def _gzip_namer(name: str) -> str:
    """Renomme l'archive rotée avec suffixe .gz."""
    return name + ".gz"


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
    use_timed_rotation: bool = False,
    timed_rotation_when: str = "midnight",
    timed_rotation_backup_count: int = 14,
) -> logging.Logger:
    """Configure le root logger du projet avec sortie stdout et fichier optionnel.

    Args:
        use_timed_rotation: Si ``True``, utilise un ``TimedRotatingFileHandler``
            (rotation quotidienne à minuit, archives compressées en gzip) à la
            place du ``RotatingFileHandler`` basé sur la taille. Sprint S3/A-025.
        timed_rotation_when: Fréquence de rotation (``"midnight"`` par défaut).
        timed_rotation_backup_count: Nombre d'archives gzip conservées (14 jours
            par défaut).
    """
    _configure_utf8_stdio()
    logger = logging.getLogger()
    logger.setLevel(level)
    _reset_root_logging_handlers(logger)

    formatter = _resolve_log_formatter(fmt, datefmt=datefmt)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    stdout_handler._alpha_trade_managed = True  # type: ignore[attr-defined]
    logger.addHandler(stdout_handler)

    if log_path:
        resolved_log_path = _resolve_log_path(log_path)
        if use_timed_rotation:
            # Sprint S3 / A-025 — rotation quotidienne + compression gzip.
            file_handler: logging.FileHandler = SafeTimedRotatingFileHandler(
                resolved_log_path,
                when=timed_rotation_when,
                backupCount=timed_rotation_backup_count,
                encoding="utf-8",
                delay=True,
            )
            # Branche les helpers gzip : rotation → .gz automatique.
            file_handler.rotator = _gzip_rotator  # type: ignore[attr-defined]
            file_handler.namer = _gzip_namer  # type: ignore[attr-defined]
        else:
            file_handler = SafeRotatingFileHandler(
                resolved_log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
                delay=True,
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


# ── Sprint S14 : JSON logging formatter ──


class JSONFormatter(logging.Formatter):
    """Formatteur JSON structuré pour les logs (Sprint S14).

    Activé via la variable d'environnement ``ALPHA_TRADE_LOG_FORMAT=json``.
    Produit une ligne JSON par log avec : timestamp, level, logger, message,
    et tout champ extra passé via ``extra``.

    Usage :
        export ALPHA_TRADE_LOG_FORMAT=json
        python -m backtesting run ...
    """

    def __init__(self, *, include_extra: bool = True) -> None:
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        import json as _json
        log_entry: dict[str, object] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in {
                    "args", "asctime", "created", "exc_info", "exc_text",
                    "filename", "funcName", "levelname", "levelno", "lineno",
                    "module", "msecs", "message", "msg", "name", "pathname",
                    "process", "processName", "relativeCreated", "stack_info",
                    "thread", "threadName",
                } and value is not None:
                    try:
                        log_entry[key] = value
                    except (TypeError, ValueError):
                        log_entry[key] = str(value)
        return _json.dumps(log_entry, default=str, ensure_ascii=False)


def _resolve_log_formatter(fmt: str, datefmt: str | None = None) -> logging.Formatter:
    """Résout le formatteur selon le format demandé ou la variable d'environnement.

    Si ``ALPHA_TRADE_LOG_FORMAT=json``, utilise :class:`JSONFormatter`.
    Sinon, utilise le ``logging.Formatter`` standard avec ``fmt``.
    """
    env_format = os.environ.get("ALPHA_TRADE_LOG_FORMAT", "").strip().lower()
    if env_format == "json":
        return JSONFormatter()
    return logging.Formatter(fmt, datefmt=datefmt)


__all__ = [
    "DEFAULT_LOG_FORMAT",
    "JSONFormatter",
    "PROJECT_ROOT",
    "_gzip_rotator",
    "_gzip_namer",
    "_resolve_log_formatter",
    "configure_root_logging",
    "setup_logging_with_file_handler",
]

