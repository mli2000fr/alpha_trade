"""Chargement et validation des secrets (config.yaml, env vars).

Phase 1 du refactor (`prompt/refactor/plan.md`).

Objectif : empêcher au démarrage tout déploiement où :
- ``config.yaml`` contient encore des credentials en clair (`pass`, `PK...`),
- une variable d'environnement référencée par ``${VAR}`` n'est pas définie,
- les variables DB (``LOGIN_DB`` / ``PASSWORD_DB``) sont absentes en mode live.

L'API publique :
    - :func:`resolve_env_placeholders` : remplace ``${VAR}`` dans une chaîne
      ou un dict imbriqué.
    - :func:`assert_no_plaintext_secrets` : refuse les valeurs sentinelles.
    - :func:`assert_required_env_vars` : vérifie qu'un ensemble de variables
      d'environnement est défini (sinon ``RuntimeError`` détaillé).
"""
from __future__ import annotations

import os
import re
from typing import Any, Iterable

#: Valeurs "placeholder" interdites en environnement non développement.
_FORBIDDEN_PLAINTEXT_SECRETS: frozenset[str] = frozenset({
    "pass", "password", "changeme", "secret", "todo",
    "PK...", "PKXXXX", "...", "your_api_key", "your_secret_key",
})

_PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class SecretConfigurationError(RuntimeError):
    """Levée quand la configuration des secrets est invalide."""


def resolve_env_placeholders(value: Any, *, strict: bool = True) -> Any:
    """Remplace récursivement les ``${VAR}`` par ``os.environ[VAR]``.

    - ``strict=True`` (défaut) : lève :class:`SecretConfigurationError` si une
      variable référencée n'est pas définie.
    - ``strict=False`` : laisse la chaîne ``${VAR}`` intacte.
    """
    if isinstance(value, str):
        def _sub(match: re.Match[str]) -> str:
            var = match.group(1)
            env_val = os.getenv(var)
            if env_val is None:
                if strict:
                    raise SecretConfigurationError(
                        f"Variable d'environnement '{var}' référencée par "
                        f"un placeholder ${{...}} mais non définie."
                    )
                return match.group(0)
            return env_val
        return _PLACEHOLDER_RE.sub(_sub, value)
    if isinstance(value, dict):
        return {k: resolve_env_placeholders(v, strict=strict) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env_placeholders(v, strict=strict) for v in value]
    return value


def assert_no_plaintext_secrets(
    config: dict[str, Any],
    *,
    paths: Iterable[Iterable[str]] = (
        ("database", "password"),
        ("database", "user"),
        ("alpaca", "api_key"),
        ("alpaca", "secret_key"),
    ),
) -> None:
    """Refuse les valeurs sentinelles dans une config chargée.

    Une valeur est considérée comme un secret en clair si elle est non vide et
    n'est ni un placeholder ``${VAR}`` ni dans la liste blanche d'env.
    """
    errors: list[str] = []
    for path in paths:
        node: Any = config
        ok = True
        for key in path:
            if not isinstance(node, dict) or key not in node:
                ok = False
                break
            node = node[key]
        if not ok or node in (None, ""):
            continue
        if isinstance(node, str):
            stripped = node.strip()
            if _PLACEHOLDER_RE.search(stripped):
                continue
            if stripped.lower() in _FORBIDDEN_PLAINTEXT_SECRETS:
                errors.append(f"  - {'.'.join(path)} = '{stripped}' (placeholder en clair)")
                continue
            # Heuristique : tout ce qui ressemble à 'pass' ou 'PK...' générique
            if stripped in _FORBIDDEN_PLAINTEXT_SECRETS:
                errors.append(f"  - {'.'.join(path)} = '{stripped}'")
    if errors:
        raise SecretConfigurationError(
            "config.yaml contient des secrets en clair interdits :\n"
            + "\n".join(errors)
            + "\nRemplace ces valeurs par des placeholders ${VAR} et exporte les "
            "variables d'environnement correspondantes."
        )


def assert_required_env_vars(names: Iterable[str]) -> None:
    """Vérifie qu'une liste de variables d'environnement est définie."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise SecretConfigurationError(
            "Variables d'environnement requises absentes : "
            + ", ".join(missing)
            + ". Exporte-les avant le démarrage."
        )


__all__ = [
    "SecretConfigurationError",
    "resolve_env_placeholders",
    "assert_no_plaintext_secrets",
    "assert_required_env_vars",
]

