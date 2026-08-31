"""Découverte et chargement sûrs des univers texte configurables."""

from __future__ import annotations

from pathlib import Path


UNIVERSE_DIRECTORY = Path("config/univers")
UNIVERSE_FILE_SOURCE_PREFIX = "universe-file:"
LEGACY_TICKET_SOURCE = "ticket-recherche"


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
    return universe_file_source(filename)


def universe_file_label(source: str) -> str:
    normalized = normalize_universe_file_source(source)
    if not is_universe_file_source(normalized):
        return normalized
    return normalized[len(UNIVERSE_FILE_SOURCE_PREFIX) :]


def load_universe_file_symbols(
    source: str,
    directory: Path = UNIVERSE_DIRECTORY,
) -> list[str]:
    """Charge, normalise et déduplique un univers sans autoriser de traversée de chemin."""
    normalized = normalize_universe_file_source(source, directory)
    if not is_universe_file_source(normalized):
        raise ValueError(f"Source fichier d'univers invalide : {source!r}")
    filename = normalized[len(UNIVERSE_FILE_SOURCE_PREFIX) :]
    available = {path.name.casefold(): path for path in list_universe_files(directory)}
    path = available.get(filename.casefold())
    if path is None:
        raise FileNotFoundError(f"Fichier d'univers introuvable dans {directory} : {filename}")

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
