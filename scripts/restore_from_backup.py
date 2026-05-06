"""Sprint S12.1 — Restauration DR depuis un dump MySQL.

Usage::

    python scripts/restore_from_backup.py \
        --dump-path /backups/alpha_trade-20260506.sql.gz \
        --target-host localhost \
        --target-db alpha_trade

Le script :

1. Charge le dump (`.sql` ou `.sql.gz`) via ``mysql`` CLI.
2. Lance ``alembic upgrade head`` pour converger le schema.
3. Vérifie l'intégrité (comptage des tables critiques).
4. Vérifie le chaînage HMAC d'audit (``verify_audit_chain``).

Dépend de ``mysql``/``mysqldump`` dans le PATH. En l'absence de ces
binaires (CI Windows), ``--dry-run`` produit un rapport sans I/O.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

LOGGER = logging.getLogger("scripts.restore_from_backup")

CRITICAL_TABLES: tuple[str, ...] = (
    "assets",
    "stock_bars_daily",
    "stock_scores",
    "risk_decisions",
    "execution_runs",
    "corporate_actions",
    # Sprint S12.2 — table créée par alembic 0024
    "audit_chain_events",
)


@dataclass(frozen=True, slots=True)
class RestoreReport:
    started_at: str
    finished_at: str
    duration_seconds: float
    dump_path: str
    target_host: str
    target_db: str
    dry_run: bool
    dump_loaded: bool
    alembic_upgraded: bool
    table_counts: dict[str, int]
    audit_chain_ok: bool
    rpo_seconds: float | None
    rto_seconds: float
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_dump_age_seconds(dump_path: Path) -> float | None:
    if not dump_path.exists():
        return None
    return max(0.0, time.time() - dump_path.stat().st_mtime)


def _stream_dump(dump_path: Path) -> Iterable[bytes]:
    if dump_path.suffix == ".gz":
        with gzip.open(dump_path, "rb") as fh:
            while chunk := fh.read(64 * 1024):
                yield chunk
    else:
        with dump_path.open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                yield chunk


def _have_mysql_cli() -> bool:
    return shutil.which("mysql") is not None


def _load_dump(dump_path: Path, host: str, db: str, user: str, password: str) -> None:
    if not _have_mysql_cli():
        raise RuntimeError("Binaire 'mysql' introuvable dans le PATH (requis pour restore).")
    cmd = [
        "mysql",
        "-h", host,
        "-u", user,
        f"-p{password}",
        "--default-character-set=utf8mb4",
        db,
    ]
    LOGGER.info("Chargement du dump %s vers %s/%s", dump_path, host, db)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for chunk in _stream_dump(dump_path):
            proc.stdin.write(chunk)
        proc.stdin.close()
    except BrokenPipeError as exc:  # pragma: no cover
        proc.kill()
        raise RuntimeError(f"mysql import failed: {exc}") from exc
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"mysql import returned exit code {rc}")


def _run_alembic_upgrade() -> None:
    LOGGER.info("Convergence schema via 'alembic upgrade head'.")
    rc = subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])
    if rc != 0:
        raise RuntimeError(f"alembic upgrade head failed (rc={rc})")


def _count_tables(target_db: str) -> dict[str, int]:
    """Comptage best-effort des tables critiques."""
    try:
        from sqlalchemy import text  # type: ignore[import-not-found]

        from database.connection import get_sqlalchemy_engine
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Impossible d'ouvrir la DB pour comptage: %s", exc)
        return {}
    engine = get_sqlalchemy_engine(db_name=target_db)
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for tbl in CRITICAL_TABLES:
            try:
                counts[tbl] = int(conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Comptage %s échoué: %s", tbl, exc)
                counts[tbl] = -1
    return counts


def _verify_audit_chain() -> bool:
    """Délègue à ``scripts/verify_audit_chain.py --strict``."""
    rc = subprocess.call([sys.executable, "scripts/verify_audit_chain.py", "--strict"])
    return rc == 0


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def restore(
    *,
    dump_path: Path,
    target_host: str,
    target_db: str,
    user: str,
    password: str,
    dry_run: bool = False,
    skip_alembic: bool = False,
    skip_audit: bool = False,
) -> RestoreReport:
    started = datetime.now(timezone.utc)
    rpo = _detect_dump_age_seconds(dump_path)
    errors: list[str] = []
    dump_loaded = False
    alembic_ok = False
    counts: dict[str, int] = {}
    audit_ok = False

    if not dump_path.exists() and not dry_run:
        errors.append(f"Dump introuvable: {dump_path}")

    if not errors and not dry_run:
        try:
            _load_dump(dump_path, target_host, target_db, user, password)
            dump_loaded = True
        except Exception as exc:  # noqa: BLE001
            errors.append(f"load_dump: {exc}")

    if not errors and not dry_run and not skip_alembic:
        try:
            _run_alembic_upgrade()
            alembic_ok = True
        except Exception as exc:  # noqa: BLE001
            errors.append(f"alembic_upgrade: {exc}")

    if not errors and not dry_run:
        counts = _count_tables(target_db)

    if not errors and not dry_run and not skip_audit:
        try:
            audit_ok = _verify_audit_chain()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"verify_audit_chain: {exc}")

    finished = datetime.now(timezone.utc)
    return RestoreReport(
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        duration_seconds=round((finished - started).total_seconds(), 3),
        dump_path=str(dump_path),
        target_host=target_host,
        target_db=target_db,
        dry_run=dry_run,
        dump_loaded=dump_loaded,
        alembic_upgraded=alembic_ok,
        table_counts=counts,
        audit_chain_ok=audit_ok,
        rpo_seconds=rpo,
        rto_seconds=round((finished - started).total_seconds(), 3),
        errors=errors,
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Restauration DR Alpha Trade depuis un dump MySQL.")
    p.add_argument("--dump-path", type=Path, required=True)
    p.add_argument("--target-host", default=os.getenv("DB_HOST", "localhost"))
    p.add_argument("--target-db", default=os.getenv("DB_NAME", "alpha_trade"))
    p.add_argument("--user-env", default="LOGIN_DB")
    p.add_argument("--password-env", default="PASSWORD_DB")
    p.add_argument("--dry-run", action="store_true", help="Vérifie les paramètres sans toucher la DB.")
    p.add_argument("--skip-alembic", action="store_true")
    p.add_argument("--skip-audit", action="store_true")
    p.add_argument("--report-out", type=Path, default=None,
                   help="Chemin JSON où écrire le rapport (défaut: stdout).")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    user = os.getenv(args.user_env, "")
    password = os.getenv(args.password_env, "")
    if not args.dry_run and not (user and password):
        LOGGER.error("%s / %s requis dans l'environnement.", args.user_env, args.password_env)
        return 2
    report = restore(
        dump_path=args.dump_path,
        target_host=args.target_host,
        target_db=args.target_db,
        user=user,
        password=password,
        dry_run=args.dry_run,
        skip_alembic=args.skip_alembic,
        skip_audit=args.skip_audit,
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

