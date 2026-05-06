"""Phase C / S18.2 — Politique de stabilité d'API publique v1.0.

Décorateur :func:`deprecated_v1` à apposer sur les symboles privés
exposés ou sur les API destinées à être supprimées dans la v2.0.

Émet ``DeprecationWarning`` au premier appel (cache par fonction pour
éviter le spam).
"""
from __future__ import annotations

import functools
import warnings
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable[..., object])


def deprecated_v1(*, reason: str, since: str, removal: str = "2.0") -> Callable[[F], F]:
    """Marque une API comme dépréciée pour suppression en ``removal``.

    Parameters
    ----------
    reason: str
        explication courte (ex. "remplacé par new_api()").
    since: str
        version d'introduction de la dépréciation (ex. "1.0").
    removal: str
        version cible de suppression (défaut "2.0").
    """

    def decorator(func: F) -> F:
        warned = False

        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal warned
            if not warned:
                warnings.warn(
                    f"{func.__qualname__} est déprécié depuis v{since} "
                    f"(suppression v{removal}) — {reason}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                warned = True
            return func(*args, **kwargs)

        wrapper.__deprecated__ = True  # type: ignore[attr-defined]
        wrapper.__deprecation_reason__ = reason  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator

