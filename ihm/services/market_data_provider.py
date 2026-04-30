"""Lecture/écriture du paramètre ``market_data.bars_provider`` du ``config.yaml``.

Utilisé par la page Settings de l'IHM pour permettre à l'opérateur de
basculer la source primaire des barres OHLCV entre Alpaca et EODHD sans
éditer manuellement ``config.yaml``.

Les commentaires du fichier YAML sont préservés grâce à un remplacement
ciblé par expression régulière sur la seule ligne ``bars_provider:``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

# Valeur par défaut côté IHM : EODHD (cf. plan_eodhd Phase 6 — recommandé).
DEFAULT_BARS_PROVIDER: Literal["eodhd", "alpaca"] = "eodhd"
ALLOWED_BARS_PROVIDERS: tuple[str, ...] = ("alpaca", "eodhd")

# Regex tolérante : supporte indentation, valeur quotée ou non, commentaire en fin de ligne.
_BARS_PROVIDER_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)bars_provider[ \t]*:[ \t]*(?P<value>['\"]?[A-Za-z_]+['\"]?)(?P<rest>.*)$",
    re.MULTILINE,
)


def get_bars_provider(config_path: Path | str | None = None) -> str:
    """Retourne la valeur courante de ``market_data.bars_provider``.

    Fallback sur :data:`DEFAULT_BARS_PROVIDER` si la lecture échoue ou si
    la clé est absente / invalide.
    """
    path = Path(config_path) if config_path else CONFIG_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_BARS_PROVIDER
    match = _BARS_PROVIDER_LINE_RE.search(text)
    if not match:
        return DEFAULT_BARS_PROVIDER
    value = match.group("value").strip().strip("'\"").lower()
    if value not in ALLOWED_BARS_PROVIDERS:
        return DEFAULT_BARS_PROVIDER
    return value


def set_bars_provider(provider: str, config_path: Path | str | None = None) -> str:
    """Met à jour ``market_data.bars_provider`` dans ``config.yaml``.

    Conserve les commentaires environnants. Lève :class:`ValueError` si la
    valeur n'est pas dans :data:`ALLOWED_BARS_PROVIDERS`, ou si la clé est
    introuvable dans le fichier.
    """
    normalized = str(provider).strip().lower()
    if normalized not in ALLOWED_BARS_PROVIDERS:
        raise ValueError(
            f"Provider '{provider}' invalide. Valeurs acceptées : {ALLOWED_BARS_PROVIDERS}"
        )
    path = Path(config_path) if config_path else CONFIG_PATH
    text = path.read_text(encoding="utf-8")
    if not _BARS_PROVIDER_LINE_RE.search(text):
        raise ValueError(
            f"Clé 'bars_provider:' introuvable dans {path}. Édition manuelle requise."
        )

    def _replace(match: re.Match[str]) -> str:
        indent = match.group("indent")
        rest = match.group("rest")
        # Conserve le commentaire en fin de ligne s'il existe (commence par '#').
        comment = ""
        if "#" in rest:
            comment = "   " + rest[rest.index("#"):].lstrip()
        return f"{indent}bars_provider: {normalized}   {comment}".rstrip()

    new_text = _BARS_PROVIDER_LINE_RE.sub(_replace, text, count=1)
    path.write_text(new_text, encoding="utf-8")
    return normalized


__all__ = [
    "ALLOWED_BARS_PROVIDERS",
    "CONFIG_PATH",
    "DEFAULT_BARS_PROVIDER",
    "get_bars_provider",
    "set_bars_provider",
]

