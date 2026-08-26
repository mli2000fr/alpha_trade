"""modelFactory/batch_logs.py — Archivage persistant des logs d'entraînement par batch.

Le fichier global ``log/model_factory.log`` est soumis à rotation par taille
(maxBytes / backupCount) : les logs des vieux batch finissent par être purgés.
Pour garantir un historique, on extrait les lignes de log propres à un batch et
on les persiste dans ``artifacts/rapport_ml/<batch_id>.log`` (même dossier que
les rapports Markdown, jamais purgé).

Workflow :
- ``persist_batch_log`` est appelé à la fin de l'entraînement (cli.py, après
  génération du rapport) → capture les lignes du batch depuis le log global
  (+ rotations) et les écrit dans le fichier d'archive.
- ``batch_logs_text`` (utilisé par l'IHM) lit l'archive en priorité, avec
  fallback sur le log global (+ rotations) pour les batch antérieurs à
  l'archivage.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LOG_DIR = PROJECT_ROOT / "log"
_TRAINING_LOG_GLOB = "model_factory.log*"
_ARCHIVE_DIR = PROJECT_ROOT / "artifacts" / "rapport_ml"


def _safe_name(batch_id: str) -> str:
    return batch_id.replace("/", "_").replace("\\", "_")[:100]


def _scan_log_files() -> list[Path]:
    """Retourne les fichiers de log d'entraînement (principal + rotations), hors .gz."""
    files = [
        p for p in _LOG_DIR.glob(_TRAINING_LOG_GLOB)
        if p.is_file() and p.suffix != ".gz"
    ]
    try:
        files.sort(key=lambda p: p.stat().st_mtime)
    except OSError:
        pass
    return files


def extract_batch_log_lines(batch_id: str) -> list[str]:
    """Extrait les lignes de log contenant ``batch_id`` depuis log/model_factory.log (+ rotations)."""
    lines: list[str] = []
    for p in _scan_log_files():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines.extend(line for line in text.splitlines() if batch_id in line)
    return lines


def persist_batch_log(batch_id: str) -> Path | None:
    """Archive les lignes de log du batch dans artifacts/rapport_ml/<batch_id>.log.

    Returns:
        Le chemin du fichier d'archive, ou ``None`` si aucune ligne trouvée.
    """
    try:
        lines = extract_batch_log_lines(batch_id)
        if not lines:
            LOGGER.info("batch_logs: aucune ligne de log à archiver pour %s", batch_id)
            return None
        _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = _ARCHIVE_DIR / f"{_safe_name(batch_id)}.log"
        header = (
            f"# Logs d'entraînement du batch {batch_id}\n"
            f"# {len(lines)} ligne(s) — archivé à la fin de l'entraînement\n"
            f"# Source: log/model_factory.log (+ rotations)\n\n"
        )
        archive_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        LOGGER.info("batch_logs: logs archivés pour %s → %s", batch_id, archive_path)
        return archive_path
    except Exception as exc:  # pragma: no cover — ne doit jamais casser l'entraînement
        LOGGER.warning("batch_logs: échec archivage logs batch %s : %s", batch_id, exc)
        return None


def read_batch_log(batch_id: str) -> str | None:
    """Lit l'archive persistante du batch si elle existe, sinon ``None``."""
    archive_path = _ARCHIVE_DIR / f"{_safe_name(batch_id)}.log"
    if archive_path.is_file():
        try:
            return archive_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return None


def backfill_existing_batches() -> dict[str, int]:
    """Archive les logs des batch existants (fichiers .md de artifacts/rapport_ml)
    encore présents dans les fichiers de log actuels. Single-pass sur les logs.

    Returns:
        Mapping {batch_id: nb_lignes_archivées} pour les batch archivés.
    """
    archive_dir = _ARCHIVE_DIR
    if not archive_dir.is_dir():
        return {}

    # Candidates = stems des rapports .md déjà générés.
    candidates = sorted(p.stem for p in archive_dir.glob("*.md"))
    already = {p.stem for p in archive_dir.glob("*.log")}

    # Single-pass sur les logs : batch_id → lignes.
    collected: dict[str, list[str]] = {}
    for p in _scan_log_files():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            for bid in candidates:
                if bid in line:
                    collected.setdefault(bid, []).append(line)

    results: dict[str, int] = {}
    for bid, lines in collected.items():
        if bid in already:
            continue
        archive_path = archive_dir / f"{bid}.log"
        header = (
            f"# Logs d'entraînement du batch {bid}\n"
            f"# {len(lines)} ligne(s) — archivé par backfill\n"
            f"# Source: log/model_factory.log (+ rotations)\n\n"
        )
        try:
            archive_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
            results[bid] = len(lines)
        except OSError as exc:  # pragma: no cover
            LOGGER.warning("batch_logs: backfill échec %s : %s", bid, exc)

    LOGGER.info("batch_logs: backfill %d batch(s) archivés", len(results))
    return results


def batch_logs_text(batch_id: str) -> str:
    """Texte complet des logs du batch : archive persistante en priorité,
    sinon scan du log global (+ rotations)."""
    archived = read_batch_log(batch_id)
    if archived is not None:
        return archived

    lines = extract_batch_log_lines(batch_id)
    if not lines:
        return (
            f"# Aucun log d'entraînement trouvé pour le batch {batch_id}\n"
            f"# (ni archive artifacts/rapport_ml, ni log/model_factory.log + rotations)\n"
        )
    import pandas as pd

    header = (
        f"# Logs d'entraînement du batch {batch_id}\n"
        f"# {len(lines)} ligne(s) — source: log/model_factory.log (+ rotations)\n"
        f"# Export: {pd.Timestamp.now()}\n\n"
    )
    return header + "\n".join(lines) + "\n"
