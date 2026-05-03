"""Garde Windows pour limiter la veille système pendant un job long.

`SetThreadExecutionState` permet d'empêcher la mise en veille déclenchée par
l'inactivité tant que le processus reste vivant. Cela ne bloque pas les cas de
redémarrage forcé (Windows Update / admin / crash / coupure secteur).
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import os
from collections.abc import Iterator

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class SleepGuardError(RuntimeError):
    """Erreur levée quand Windows refuse l'activation ou la restauration."""


def _is_windows() -> bool:
    return os.name == "nt"


def _set_thread_execution_state(flags: int) -> int:
    kernel32 = getattr(ctypes, "windll", None)
    if kernel32 is None or getattr(kernel32, "kernel32", None) is None:
        raise SleepGuardError("API Windows kernel32 indisponible.")
    result = int(kernel32.kernel32.SetThreadExecutionState(flags))
    if result == 0:
        raise SleepGuardError("SetThreadExecutionState a échoué.")
    return result


@contextmanager
def prevent_windows_sleep(*, enabled: bool = True) -> Iterator[bool]:
    """Empêche la veille Windows liée à l'inactivité pendant le bloc.

    Retourne `True` si la garde a été réellement activée, sinon `False`.
    Hors Windows, ou si `enabled=False`, le context manager est un no-op.
    """

    if not enabled or not _is_windows():
        yield False
        return

    _set_thread_execution_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield True
    finally:
        _set_thread_execution_state(ES_CONTINUOUS)

