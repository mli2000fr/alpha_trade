"""Sprint S5 — Backup automatique des artefacts ML.

Crée une archive ``tar.gz`` horodatée de ``artifacts/models/`` et applique
une rotation (garder les N dernières archives).

Usage::

    python scripts/backup_ml_artifacts.py \
        --artifacts-dir artifacts/models \
        --dest-dir backups/ml \
        --keep 7

Fonctionne sur **Windows et Linux** sans binaires externes (shutil standard).
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("scripts.backup_ml_artifacts")

# Répertoire d'artefacts par défaut (relatif à la racine projet)
DEFAULT_ARTIFACTS_DIR = Path("artifacts") / "models"
DEFAULT_DEST_DIR = Path("backups") / "ml"
DEFAULT_KEEP = 7


# ---------------------------------------------------------------------------
# Dataclass rapport
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BackupReport:
    started_at: str
    finished_at: str
    duration_seconds: float
    artifacts_dir: str
    dest_dir: str
    archive_path: str | None
    archive_size_bytes: int
    rotated_files: list[str]
    kept_files: list[str]
    dry_run: bool
    errors: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list_archives(dest_dir: Path) -> list[Path]:
    """Retourne les archives ML triées par mtime ascendant (plus ancien en premier)."""
    return sorted(dest_dir.glob("ml_artifacts_*.tar.gz"), key=lambda p: p.stat().st_mtime)


def _build_archive_path(dest_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return dest_dir / f"ml_artifacts_{ts}.tar.gz"


def _rotate(dest_dir: Path, keep: int, dry_run: bool) -> tuple[list[str], list[str]]:
    """Supprime les archives excédentaires. Retourne (rotated, kept)."""
    archives = _list_archives(dest_dir)
    rotated: list[str] = []
    to_delete = archives[: max(0, len(archives) - keep + 1)]
    for old in to_delete:
        LOGGER.info("Rotation — suppression de %s", old)
        if not dry_run:
            try:
                old.unlink()
            except OSError as exc:
                LOGGER.warning("Impossible de supprimer %s : %s", old, exc)
        rotated.append(str(old))
    kept = [str(a) for a in archives if str(a) not in rotated]
    return rotated, kept


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------


def backup(
    *,
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR,
    dest_dir: Path = DEFAULT_DEST_DIR,
    keep: int = DEFAULT_KEEP,
    dry_run: bool = False,
) -> BackupReport:
    """Crée un backup des artefacts ML et applique la rotation.

    Args:
        artifacts_dir: Répertoire source à archiver (``artifacts/models/``).
        dest_dir: Répertoire de destination pour les archives.
        keep: Nombre d'archives à conserver.
        dry_run: Si True, simule sans écrire sur le disque.

    Returns:
        :class:`BackupReport` décrivant le résultat.
    """
    started = datetime.now(timezone.utc)
    errors: list[str] = []
    archive_path: Path | None = None
    archive_size = 0
    rotated: list[str] = []
    kept: list[str] = []

    artifacts_dir = artifacts_dir.resolve()
    dest_dir = dest_dir.resolve()

    if not artifacts_dir.exists():
        errors.append(f"Répertoire source introuvable: {artifacts_dir}")
    elif not artifacts_dir.is_dir():
        errors.append(f"Le chemin source n'est pas un répertoire: {artifacts_dir}")

    if not errors:
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        archive_path = _build_archive_path(dest_dir)
        LOGGER.info("Création de l'archive %s …", archive_path)

        if not dry_run:
            try:
                t0 = time.perf_counter()
                # shutil.make_archive portable Windows + Linux
                base_name = str(archive_path).removesuffix(".tar.gz")
                shutil.make_archive(
                    base_name=base_name,
                    format="gztar",
                    root_dir=artifacts_dir.parent,
                    base_dir=artifacts_dir.name,
                )
                elapsed_archive = time.perf_counter() - t0
                archive_size = archive_path.stat().st_size
                LOGGER.info(
                    "Archive créée en %.2fs — %.1f MB",
                    elapsed_archive,
                    archive_size / 1024 / 1024,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"make_archive: {exc}")
                LOGGER.error("Échec création archive: %s", exc)

    if not errors:
        try:
            rotated, kept = _rotate(dest_dir, keep=keep, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"rotation: {exc}")

    # Émettre métriques si disponibles
    try:
        from common.metrics import ml_backup_total as _counter

        _counter.labels(status="OK" if not errors else "ERROR").inc()
    except Exception:  # pragma: no cover
        pass

    finished = datetime.now(timezone.utc)
    return BackupReport(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        duration_seconds=round((finished - started).total_seconds(), 3),
        artifacts_dir=str(artifacts_dir),
        dest_dir=str(dest_dir),
        archive_path=str(archive_path) if archive_path else None,
        archive_size_bytes=archive_size,
        rotated_files=rotated,
        kept_files=kept,
        dry_run=dry_run,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Backup automatique des artefacts ML Alpha Trade (Sprint S5)."
    )
    p.add_argument(
        "--artifacts-dir",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help=f"Répertoire source à archiver (défaut: {DEFAULT_ARTIFACTS_DIR}).",
    )
    p.add_argument(
        "--dest-dir",
        type=Path,
        default=DEFAULT_DEST_DIR,
        help=f"Répertoire de destination des archives (défaut: {DEFAULT_DEST_DIR}).",
    )
    p.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Nombre d'archives à conserver (défaut: {DEFAULT_KEEP}).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule sans écrire sur le disque.",
    )
    p.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Chemin JSON de sortie (défaut: stdout).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    report = backup(
        artifacts_dir=args.artifacts_dir,
        dest_dir=args.dest_dir,
        keep=args.keep,
        dry_run=args.dry_run,
    )
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0 if not report.errors else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


