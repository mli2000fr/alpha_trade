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
import re
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
_SQL_IDENTIFIER = re.compile(r"^[A-Za-z0-9_$]+$")


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
    archive_prefix: str
    include_tables: list[str]
    exclude_tables: list[str]
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


def _resolve_mysqldump(mysqldump_path: str | Path | None = None) -> str | None:
    """Résout le client explicitement avant de consulter le PATH du processus."""
    if mysqldump_path:
        candidate = Path(mysqldump_path).expanduser()
        return str(candidate.resolve()) if candidate.is_file() else None
    return shutil.which("mysqldump")


def _have_mysqldump(mysqldump_path: str | Path | None = None) -> bool:
    return _resolve_mysqldump(mysqldump_path) is not None


def _list_dumps(dest_dir: Path, archive_prefix: str) -> list[Path]:
    """Retourne les dumps triés par mtime ascendant (plus ancien en premier)."""
    return sorted(dest_dir.glob(f"{archive_prefix}_*.sql.gz"), key=lambda p: p.stat().st_mtime)


def _build_dump_path(dest_dir: Path, archive_prefix: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return dest_dir / f"{archive_prefix}_{ts}.sql.gz"


def _validate_identifiers(values: list[str], *, label: str) -> None:
    invalid = [value for value in values if not _SQL_IDENTIFIER.fullmatch(value)]
    if invalid:
        raise ValueError(f"{label} contient un identifiant SQL invalide: {invalid[0]!r}")


def _run_mysqldump(
    host: str,
    db: str,
    user: str,
    password: str,
    dump_path: Path,
    *,
    include_tables: list[str],
    exclude_tables: list[str],
    include_routines: bool,
    include_triggers: bool,
    mysqldump_path: str | Path | None,
) -> None:
    """Lance mysqldump et compresse directement en gzip."""
    executable = _resolve_mysqldump(mysqldump_path)
    if not executable:
        location = str(mysqldump_path or "PATH")
        raise RuntimeError(f"Binaire 'mysqldump' introuvable: {location}.")

    cmd = [
        executable,
        "-h", host,
        "-u", user,
        "--single-transaction",
        "--default-character-set=utf8mb4",
    ]
    if include_routines:
        cmd.append("--routines")
    if include_triggers:
        cmd.append("--triggers")
    else:
        cmd.append("--skip-triggers")
    cmd.extend(f"--ignore-table={db}.{table}" for table in exclude_tables)
    cmd.append(db)
    cmd.extend(include_tables)
    LOGGER.info("Exécution mysqldump %s/%s → %s", host, db, dump_path)
    process_env = os.environ.copy()
    process_env["MYSQL_PWD"] = password
    with gzip.open(dump_path, "wb") as gz_out:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=process_env,
        )
        assert proc.stdout is not None
        while chunk := proc.stdout.read(64 * 1024):
            gz_out.write(chunk)
    rc = proc.wait()
    stderr_output = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    if rc != 0:
        raise RuntimeError(f"mysqldump exit code {rc}: {stderr_output.strip()}")
    LOGGER.info("mysqldump terminé avec succès.")


def _rotate(dest_dir: Path, archive_prefix: str, keep: int, dry_run: bool) -> tuple[list[str], list[str]]:
    """Supprime les dumps excédentaires. Retourne (rotated, kept)."""
    dumps = _list_dumps(dest_dir, archive_prefix)
    to_delete = dumps[: max(0, len(dumps) - keep)]
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
    archive_prefix: str | None = None,
    include_tables: list[str] | None = None,
    exclude_tables: list[str] | None = None,
    include_routines: bool = True,
    include_triggers: bool = True,
    mysqldump_path: str | Path | None = None,
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
        archive_prefix: Préfixe isolant le jeu d'archives et sa rotation.
        include_tables: Tables seules à sauvegarder, vide pour toute la base.
        exclude_tables: Tables à exclure d'un dump de base complet.
        include_routines: Inclure les procédures et fonctions stockées.
        include_triggers: Inclure les triggers des tables sauvegardées.
        mysqldump_path: Chemin explicite du client, prioritaire sur le PATH.
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
    archive_prefix = archive_prefix or db
    include_tables = list(include_tables or [])
    exclude_tables = list(exclude_tables or [])
    user = user or os.getenv("LOGIN_DB", "")
    password = password or os.getenv("PASSWORD_DB", "")

    try:
        _validate_identifiers([db, archive_prefix], label="db/archive_prefix")
        _validate_identifiers(include_tables, label="include_tables")
        _validate_identifiers(exclude_tables, label="exclude_tables")
    except ValueError as exc:
        errors.append(str(exc))
    if include_tables and exclude_tables:
        errors.append("include_tables et exclude_tables sont mutuellement exclusifs.")
    if keep < 1:
        errors.append("keep doit être supérieur ou égal à 1.")
    if not dry_run and not (user and password):
        errors.append("LOGIN_DB / PASSWORD_DB requis dans l'environnement.")

    if not errors:
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        dump_path = _build_dump_path(dest_dir, archive_prefix)

        if not dry_run:
            if not _have_mysqldump(mysqldump_path):
                errors.append(
                    "Binaire 'mysqldump' introuvable: "
                    f"{mysqldump_path or 'PATH'}."
                )
            else:
                try:
                    assert dump_path is not None  # toujours set quand not dry_run
                    _run_mysqldump(
                        host, db, user, password, dump_path,
                        include_tables=include_tables,
                        exclude_tables=exclude_tables,
                        include_routines=include_routines,
                        include_triggers=include_triggers,
                        mysqldump_path=mysqldump_path,
                    )
                    dump_size = dump_path.stat().st_size
                    LOGGER.info("Dump créé — %.1f MB", dump_size / 1024 / 1024)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"mysqldump: {exc}")
                    if dump_path.exists():
                        dump_path.unlink(missing_ok=True)

    if not errors and not dry_run:
        try:
            rotated, kept = _rotate(
                dest_dir, archive_prefix=archive_prefix, keep=keep, dry_run=dry_run,
            )
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
        archive_prefix=archive_prefix,
        include_tables=include_tables,
        exclude_tables=exclude_tables,
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
    p.add_argument("--archive-prefix", default=None)
    p.add_argument("--include-table", action="append", default=[])
    p.add_argument("--exclude-table", action="append", default=[])
    p.add_argument("--no-routines", action="store_true")
    p.add_argument("--no-triggers", action="store_true")
    p.add_argument("--mysqldump-path", default=None)
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
        archive_prefix=args.archive_prefix,
        include_tables=args.include_table,
        exclude_tables=args.exclude_table,
        include_routines=not args.no_routines,
        include_triggers=not args.no_triggers,
        mysqldump_path=args.mysqldump_path,
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



