"""Découverte et chargement sûrs des univers texte configurables.

Un identifiant d'univers est soit un nom de fichier résolu dans
``config/univers`` (``universe-file:univers_filtred.txt``), soit un chemin
relatif à la racine du dépôt confiné sous ``config/``
(``universe-file:config/univers_batch/univers_filtred_tradable.txt``).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


UNIVERSE_DIRECTORY = Path("config/univers")
UNIVERSE_CONFIG_ROOT = Path("config")
UNIVERSE_FILE_SOURCE_PREFIX = "universe-file:"
LEGACY_TICKET_SOURCE = "ticket-recherche"


def _is_bare_name(value: str) -> bool:
    """Vrai si ``value`` est un simple nom de fichier, sans séparateur de chemin."""
    return bool(value) and "/" not in value and "\\" not in value


def _relative_config_path(path: Path, root: Path) -> Path:
    """Normalise ``path`` en chemin relatif à ``root``, confiné sous ``config/``.

    Refuse les remontées ``..``, les fichiers non `.txt` et tout chemin qui
    sortirait de ``config/``.
    """
    raw = str(path).replace("\\", "/")
    if any(part == ".." for part in raw.split("/")):
        raise ValueError(f"Chemin d'univers interdit : {path!r}")
    if path.suffix.lower() != ".txt":
        raise ValueError(f"Fichier d'univers non texte : {path!r}")
    base = Path(root).resolve()
    resolved = (path if path.is_absolute() else base / path).resolve()
    config_root = (base / UNIVERSE_CONFIG_ROOT).resolve()
    if resolved != config_root and config_root not in resolved.parents:
        raise ValueError(f"Fichier d'univers hors de {UNIVERSE_CONFIG_ROOT}/ : {path!r}")
    return resolved.relative_to(base)


def list_universe_files(directory: Path = UNIVERSE_DIRECTORY) -> tuple[Path, ...]:
    """Retourne les fichiers ``.txt`` disponibles, triés par nom sans tenir compte de la casse."""
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".txt"),
            key=lambda path: (path.name.casefold(), path.name),
        )
    )


def universe_file_source(filename: str) -> str:
    """Construit l'identifiant transportable d'un fichier d'univers."""
    raw_name = str(filename).strip()
    name = Path(raw_name).name
    if (
        not name
        or "/" in raw_name
        or "\\" in raw_name
        or name != raw_name
        or Path(name).suffix.lower() != ".txt"
    ):
        raise ValueError(f"Nom de fichier d'univers invalide : {filename!r}")
    return f"{UNIVERSE_FILE_SOURCE_PREFIX}{name}"


def universe_file_source_from_path(path: str | Path, root: str | Path = Path(".")) -> str:
    """Construit l'identifiant d'un fichier d'univers désigné par son chemin.

    Les fichiers de ``config/univers`` conservent l'identifiant court
    ``universe-file:<nom>`` ; les autres gardent leur chemin relatif.
    """
    relative = _relative_config_path(Path(path), Path(root))
    if relative.parent.as_posix() == UNIVERSE_DIRECTORY.as_posix():
        return universe_file_source(relative.name)
    return f"{UNIVERSE_FILE_SOURCE_PREFIX}{relative.as_posix()}"


def resolve_universe_file_path(
    source: str,
    directory: Path = UNIVERSE_DIRECTORY,
    root: str | Path = Path("."),
) -> Path:
    """Résout un identifiant ``universe-file:`` vers le chemin du fichier (sans lecture)."""
    normalized = str(source or "").strip()
    if is_universe_file_source(normalized):
        normalized = normalized[len(UNIVERSE_FILE_SOURCE_PREFIX):].strip()
    if not normalized:
        raise ValueError(f"Source fichier d'univers invalide : {source!r}")
    if _is_bare_name(normalized):
        return Path(directory) / normalized
    base = Path(root).resolve()
    return base / _relative_config_path(Path(normalized), base)


def validate_symbol_source(value: str, native_sources: Sequence[str] = ()) -> str:
    """Valide et normalise une source symbolique CLI (native ou fichier d'univers).

    Lève ``ValueError`` pour une source inconnue et ``FileNotFoundError`` quand le
    fichier d'univers désigné est absent.
    """
    text = str(value or "").strip()
    if text and text in {str(item) for item in native_sources}:
        return text
    if not is_universe_file_source(text):
        expected = ", ".join([*[str(item) for item in native_sources], f"{UNIVERSE_FILE_SOURCE_PREFIX}<fichier>|chemin>"])
        raise ValueError(f"source de symboles inconnue : {value!r} (attendu : {expected})")
    normalized = normalize_universe_file_source(text)
    if not resolve_universe_file_path(normalized).is_file():
        raise FileNotFoundError(f"Fichier d'univers introuvable : {text}")
    return normalized


def list_universe_file_sources(directory: Path = UNIVERSE_DIRECTORY) -> tuple[str, ...]:
    return tuple(universe_file_source(path.name) for path in list_universe_files(directory))


def replace_legacy_ticket_option(
    options: tuple[str, ...],
    directory: Path = UNIVERSE_DIRECTORY,
) -> tuple[str, ...]:
    """Conserve les sources natives et remplace l'ancien choix par tous les fichiers découverts."""
    native = tuple(option for option in options if option != LEGACY_TICKET_SOURCE)
    return (*native, *list_universe_file_sources(directory))


def universe_file_source_labels(directory: Path = UNIVERSE_DIRECTORY) -> dict[str, str]:
    return {
        universe_file_source(path.name): f"Fichier d’univers — {path.name}"
        for path in list_universe_files(directory)
    }


def default_universe_file_source(directory: Path = UNIVERSE_DIRECTORY) -> str:
    sources = list_universe_file_sources(directory)
    if not sources:
        raise FileNotFoundError(f"Aucun fichier .txt trouvé dans {directory}")
    return sources[0]


def default_universe_file_source_or(
    fallback: str,
    directory: Path = UNIVERSE_DIRECTORY,
) -> str:
    sources = list_universe_file_sources(directory)
    return sources[0] if sources else fallback


def is_universe_file_source(value: str | None) -> bool:
    return str(value or "").strip().lower().startswith(UNIVERSE_FILE_SOURCE_PREFIX)


def normalize_universe_file_source(
    value: str | None,
    directory: Path = UNIVERSE_DIRECTORY,
) -> str:
    """Normalise un identifiant fichier et résout l'ancien alias vers le défaut."""
    normalized = str(value or "").strip()
    if normalized.lower() == LEGACY_TICKET_SOURCE:
        return default_universe_file_source(directory)
    if not is_universe_file_source(normalized):
        return normalized.lower()
    filename = normalized[len(UNIVERSE_FILE_SOURCE_PREFIX) :].strip()
    if _is_bare_name(filename):
        return universe_file_source(filename)
    relative = _relative_config_path(Path(filename), Path("."))
    if relative.parent.as_posix() == UNIVERSE_DIRECTORY.as_posix():
        return universe_file_source(relative.name)
    return f"{UNIVERSE_FILE_SOURCE_PREFIX}{relative.as_posix()}"


def universe_file_label(source: str) -> str:
    normalized = normalize_universe_file_source(source)
    if not is_universe_file_source(normalized):
        return normalized
    return normalized[len(UNIVERSE_FILE_SOURCE_PREFIX) :]


def load_universe_file_symbols(
    source: str,
    directory: Path = UNIVERSE_DIRECTORY,
    root: str | Path = Path("."),
) -> list[str]:
    """Charge, normalise et déduplique un univers sans autoriser de traversée de chemin."""
    normalized = normalize_universe_file_source(source, directory)
    if not is_universe_file_source(normalized):
        raise ValueError(f"Source fichier d'univers invalide : {source!r}")
    filename = normalized[len(UNIVERSE_FILE_SOURCE_PREFIX) :]
    if _is_bare_name(filename):
        available = {path.name.casefold(): path for path in list_universe_files(directory)}
        path = available.get(filename.casefold())
        if path is None:
            raise FileNotFoundError(f"Fichier d'univers introuvable dans {directory} : {filename}")
    else:
        path = resolve_universe_file_path(normalized, directory, root)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier d'univers introuvable : {path}")

    symbols: list[str] = []
    seen: set[str] = set()
    raw = path.read_text(encoding="utf-8-sig")
    for line in raw.splitlines():
        content = line.split("#", 1)[0]
        for token in content.split(","):
            symbol = token.strip().upper()
            if symbol and symbol not in seen:
                seen.add(symbol)
                symbols.append(symbol)
    return symbols
