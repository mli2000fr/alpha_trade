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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

#: Valeurs "placeholder" interdites en environnement non développement.
_FORBIDDEN_PLAINTEXT_SECRETS: frozenset[str] = frozenset({
    "pass", "password", "changeme", "secret", "todo",
    "PK...", "PKXXXX", "...", "your_api_key", "your_secret_key",
})

_PLACEHOLDER_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# Sprint S5 / A-013 — patterns regex pour scanner *physiquement* un YAML à
# la recherche de credentials écrits en dur. Whitelist : ${VAR}, valeur
# < 16 chars (ou < 30 pour base64), commentaire `# noqa: secret-scan`.
LITERAL_SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "alpaca_paper_key": re.compile(r"\bPK[A-Z0-9]{16,}\b"),
    "alpaca_live_key": re.compile(r"\bAK[A-Z0-9]{16,}\b"),
    "alpaca_secret_b64": re.compile(r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{36,}={0,2}(?![A-Za-z0-9/+=])"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
}

# Clés YAML autorisées à contenir des chaînes longues (faux positifs base64).
_SCANNER_KEY_WHITELIST: frozenset[str] = frozenset({
    "cache_dir", "description", "label", "name", "path", "url",
    "exchange", "host", "comment", "note", "id", "account_id",
    "api_token_env", "broker_mode", "mode", "fingerprint",
})

_NOQA_MARKER = "noqa: secret-scan"


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """Une occurrence de secret littéral détectée par le scanner."""

    path: str         # chemin fichier
    lineno: int       # ligne 1-based
    pattern_name: str # ex. 'alpaca_paper_key'
    masked_value: str # 4 premiers + '…' + 4 derniers caractères
    context: str      # ligne brute (tronquée) pour debug

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "lineno": self.lineno,
            "pattern_name": self.pattern_name,
            "masked_value": self.masked_value,
            "context": self.context,
        }


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


# ---------------------------------------------------------------------------
# Sprint S5 (A-013) — scanner physique du YAML
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _is_whitelisted_line(line: str) -> bool:
    if _NOQA_MARKER in line:
        return True
    # Extraction brute clé YAML "key:" avant ':' — best effort.
    head = line.split(":", 1)[0].strip().lstrip("-").strip()
    if head in _SCANNER_KEY_WHITELIST:
        return True
    return False


def _strip_value_for_scan(line: str) -> str:
    """Retourne uniquement la portion 'valeur' d'une ligne YAML simple key: value."""
    if ":" in line:
        return line.split(":", 1)[1]
    return line


def scan_text_for_literal_secrets(
    text: str,
    *,
    source_path: str = "<memory>",
) -> list[SecretFinding]:
    """Scanne un texte YAML et retourne la liste des secrets littéraux."""
    findings: list[SecretFinding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _is_whitelisted_line(raw):
            continue
        if "${" in raw:
            # Le placeholder env exclut quasiment toujours un littéral —
            # on tolère les lignes mixtes (rare) et on poursuit le scan
            # uniquement si une partie hors placeholder reste suspecte.
            cleaned = _PLACEHOLDER_RE.sub("", raw)
        else:
            cleaned = raw
        value_part = _strip_value_for_scan(cleaned)
        # Strip quotes
        scan_target = value_part.replace('"', " ").replace("'", " ")
        for name, pattern in LITERAL_SECRET_PATTERNS.items():
            for match in pattern.finditer(scan_target):
                token = match.group(0)
                # Filtre min length pour base64 si la clé YAML est tolérante
                if name == "alpaca_secret_b64" and len(token) < 36:
                    continue
                findings.append(
                    SecretFinding(
                        path=str(source_path),
                        lineno=lineno,
                        pattern_name=name,
                        masked_value=_mask(token),
                        context=line[:120],
                    )
                )
    return findings


def scan_yaml_for_literal_secrets(path: Path) -> list[SecretFinding]:
    """Scanne un fichier YAML sur disque."""
    p = Path(path)
    if not p.exists():
        return []
    return scan_text_for_literal_secrets(p.read_text(encoding="utf-8"), source_path=str(p))


def scan_repo_yaml_for_literal_secrets(
    root: Path,
    *,
    exclude_dirs: tuple[str, ...] = (".venv", "venv", ".git", "tests", "__pycache__",
                                      "htmlcov", "alpha_trade.egg-info"),
) -> list[SecretFinding]:
    """Scanne récursivement tous les ``*.yaml`` sous ``root``."""
    root = Path(root)
    findings: list[SecretFinding] = []
    for path in root.rglob("*.yaml"):
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & set(exclude_dirs):
            continue
        findings.extend(scan_yaml_for_literal_secrets(path))
    for path in root.rglob("*.yml"):
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & set(exclude_dirs):
            continue
        findings.extend(scan_yaml_for_literal_secrets(path))
    return findings


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
            # Heuristique additionnelle Sprint S5 : pattern alpaca/openai
            for name, pattern in LITERAL_SECRET_PATTERNS.items():
                if pattern.search(stripped):
                    errors.append(
                        f"  - {'.'.join(path)} matche le pattern '{name}' "
                        f"(valeur masquée: {_mask(stripped)})"
                    )
                    break
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
    "SecretFinding",
    "LITERAL_SECRET_PATTERNS",
    "resolve_env_placeholders",
    "assert_no_plaintext_secrets",
    "assert_required_env_vars",
    "scan_text_for_literal_secrets",
    "scan_yaml_for_literal_secrets",
    "scan_repo_yaml_for_literal_secrets",
]

