"""Sprint S5 — Backup automatique de la base de données Alpha Trade.

Exécute ``mysqldump`` et comprime le dump en ``.sql.gz`` avec un timestamp
``YYYYMMDD_HHMMSS``. Applique une rotation des N dernières archives.

Usage::

    python scripts/backup_db.py \
        --host localhost \
        --db alpha_trade \
        --dest-dir backups/db \
        --keep 30

Requiert ``mysqldump`` dans le PATH. En l'absence de ``mysqldump`` (CI),
``--dry-run`` produit un rapport sans I/O.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("scripts.backup_db")

DEFAULT_HOST = "localhost"
DEFAULT_DB = "alpha_trade"
DEFAULT_DEST_DIR = Path("backups") / "db"
DEFAULT_KEEP = 30


# ---------------------------------------------------------------------------
# Dataclass rapport
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DbBackupReport:
    started_at: str
    finished_at: str
    duration_seconds: float
    host: str
    db: str
    dest_dir: str
    dump_path: str | None
    dump_size_bytes: int
    rotated_files: list[str]
    kept_files: list[str]
    dry_run: bool
    errors: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _have_mysqldump() -> bool:
    return shutil.which("mysqldump") is not None


def _list_dumps(dest_dir: Path) -> list[Path]:
    """Retourne les dumps triés par mtime ascendant (plus ancien en premier)."""
    return sorted(dest_dir.glob("alpha_trade_*.sql.gz"), key=lambda p: p.stat().st_mtime)


def _build_dump_path(dest_dir: Path, db: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return dest_dir / f"{db}_{ts}.sql.gz"


def _run_mysqldump(host: str, db: str, user: str, password: str, dump_path: Path) -> None:
    """Lance mysqldump et compresse directement en gzip."""
    if not _have_mysqldump():
        raise RuntimeError("Binaire 'mysqldump' introuvable dans le PATH.")

    cmd = [
        "mysqldump",
        "-h", host,
        "-u", user,
        f"-p{password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--default-character-set=utf8mb4",
        db,
    ]
    LOGGER.info("Exécution mysqldump %s/%s → %s", host, db, dump_path)
    with gzip.open(dump_path, "wb") as gz_out:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdout is not None
        while chunk := proc.stdout.read(64 * 1024):
            gz_out.write(chunk)
    rc = proc.wait()
    stderr_output = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    if rc != 0:
        raise RuntimeError(f"mysqldump exit code {rc}: {stderr_output.strip()}")
    LOGGER.info("mysqldump terminé avec succès.")


def _rotate(dest_dir: Path, keep: int, dry_run: bool) -> tuple[list[str], list[str]]:
    """Supprime les dumps excédentaires. Retourne (rotated, kept)."""
    dumps = _list_dumps(dest_dir)
    to_delete = dumps[: max(0, len(dumps) - keep + 1)]
    rotated: list[str] = []
    for old in to_delete:
        LOGGER.info("Rotation — suppression de %s", old)
        if not dry_run:
            try:
                old.unlink()
            except OSError as exc:
                LOGGER.warning("Impossible de supprimer %s : %s", old, exc)
        rotated.append(str(old))
    kept = [str(d) for d in dumps if str(d) not in rotated]
    return rotated, kept


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------


def backup_db(
    *,
    host: str = DEFAULT_HOST,
    db: str = DEFAULT_DB,
    user: str = "",
    password: str = "",
    dest_dir: Path = DEFAULT_DEST_DIR,
    keep: int = DEFAULT_KEEP,
    dry_run: bool = False,
) -> DbBackupReport:
    """Exécute un backup de la DB et applique la rotation des dumps.

    Args:
        host: Hôte MySQL (défaut: ``localhost``).
        db: Nom de la base de données.
        user: Utilisateur MySQL (lu depuis l'env ``LOGIN_DB`` si vide).
        password: Mot de passe MySQL (lu depuis l'env ``PASSWORD_DB`` si vide).
        dest_dir: Répertoire de destination des dumps.
        keep: Nombre de dumps à conserver.
        dry_run: Si True, simule sans exécuter mysqldump.

    Returns:
        :class:`DbBackupReport` décrivant le résultat.
    """
    started = datetime.now(timezone.utc)
    errors: list[str] = []
    dump_path: Path | None = None
    dump_size = 0
    rotated: list[str] = []
    kept: list[str] = []

    dest_dir = dest_dir.resolve()
    user = user or os.getenv("LOGIN_DB", "")
    password = password or os.getenv("PASSWORD_DB", "")

    if not dry_run and not (user and password):
        errors.append("LOGIN_DB / PASSWORD_DB requis dans l'environnement.")

    if not errors:
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        dump_path = _build_dump_path(dest_dir, db)

        if not dry_run:
            if not _have_mysqldump():
                errors.append("Binaire 'mysqldump' introuvable dans le PATH.")
            else:
                try:
                    assert dump_path is not None  # toujours set quand not dry_run
                    _run_mysqldump(host, db, user, password, dump_path)
                    dump_size = dump_path.stat().st_size
                    LOGGER.info("Dump créé — %.1f MB", dump_size / 1024 / 1024)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"mysqldump: {exc}")

    if not errors and not dry_run:
        try:
            rotated, kept = _rotate(dest_dir, keep=keep, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"rotation: {exc}")

    # Émettre métriques si disponibles
    try:
        from common.metrics import db_backup_total as _counter

        _counter.labels(status="OK" if not errors else "ERROR").inc()
    except Exception:  # pragma: no cover
        pass

    finished = datetime.now(timezone.utc)
    return DbBackupReport(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        duration_seconds=round((finished - started).total_seconds(), 3),
        host=host,
        db=db,
        dest_dir=str(dest_dir),
        dump_path=str(dump_path) if dump_path else None,
        dump_size_bytes=dump_size,
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
        description="Backup automatique de la base de données Alpha Trade (Sprint S5)."
    )
    p.add_argument("--host", default=os.getenv("DB_HOST", DEFAULT_HOST))
    p.add_argument("--db", default=os.getenv("DB_NAME", DEFAULT_DB))
    p.add_argument("--user-env", default="LOGIN_DB")
    p.add_argument("--password-env", default="PASSWORD_DB")
    p.add_argument(
        "--dest-dir",
        type=Path,
        default=DEFAULT_DEST_DIR,
        help=f"Répertoire de destination (défaut: {DEFAULT_DEST_DIR}).",
    )
    p.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Nombre de dumps à conserver (défaut: {DEFAULT_KEEP}).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule sans exécuter mysqldump.",
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
    user = os.getenv(args.user_env, "")
    password = os.getenv(args.password_env, "")
    report = backup_db(
        host=args.host,
        db=args.db,
        user=user,
        password=password,
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



