"""Restore-probe of an isolated alpha_trade_cn dump in a fresh temporary DB.

Never accepts a production database as the restore target. The temporary DB
may be dropped only if this run created it and verification succeeded.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from database.router import get_market_engine

ROOT = Path(__file__).resolve().parents[2]
CN_BACKUP_ROOT = ROOT / "backups" / "cn" / "db"
ARCHIVE_RE = re.compile(r"alpha_trade_cn_\d{8}_\d{6}\.sql\.gz\Z")
RESTORE_RE = re.compile(r"alpha_trade_cn_restore_[0-9a-f]{8}\Z")
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_$]+\Z")


def validate_archive(path: Path, *, backup_root: Path = CN_BACKUP_ROOT) -> Path:
    archive = path.resolve(strict=True)
    if (archive.parent != backup_root.resolve() or not ARCHIVE_RE.fullmatch(archive.name)
            or archive.stat().st_size == 0):
        raise ValueError("Archive is not a nonempty isolated CN database dump")
    return archive


def validate_restore_name(name: str) -> str:
    if not RESTORE_RE.fullmatch(name) or name in {"alpha_trade", "alpha_trade_cn"}:
        raise ValueError("Unsafe CN restore database name")
    return name


def _mysql(command: list[str], *, executable: Path, host: str,
           user: str, password: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    return subprocess.run([str(executable), "-h", host, "-u", user,
                           "--default-character-set=utf8mb4", *command],
                          env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)


def _base_tables(engine, database: str) -> list[str]:
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=:db AND table_type='BASE TABLE' ORDER BY table_name"
        ), {"db": database}).scalars().all()
    names = [str(value) for value in rows]
    if any(not IDENTIFIER_RE.fullmatch(name) for name in names):
        raise RuntimeError("Unexpected SQL table identifier in CN restore probe")
    return names


def _row_counts(engine, names: list[str]) -> dict[str, int]:
    with engine.connect() as connection:
        return {name: int(connection.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one())
                for name in names}


def restore_probe(*, archive: Path, mysql_executable: Path, host: str = "localhost",
                  cleanup_on_success: bool = False,
                  backup_root: Path = CN_BACKUP_ROOT) -> dict:
    archive = validate_archive(archive, backup_root=backup_root)
    mysql_executable = mysql_executable.resolve(strict=True)
    if not mysql_executable.is_file():
        raise FileNotFoundError(mysql_executable)
    user = os.environ.get("LOGIN_DB", "")
    password = os.environ.get("PASSWORD_DB", "")
    if not user or not password:
        raise RuntimeError("LOGIN_DB and PASSWORD_DB are required")
    target = validate_restore_name(f"alpha_trade_cn_restore_{uuid.uuid4().hex[:8]}")
    source = get_market_engine("CN_A", database_alias="cn_primary")
    if source.url.database != "alpha_trade_cn":
        source.dispose()
        raise RuntimeError("CN route does not point to alpha_trade_cn")
    report = {"status": "FAILED", "archive": str(archive), "archive_bytes": archive.stat().st_size,
              "archive_sha256": None, "source_database": "alpha_trade_cn", "restore_database": target,
              "started_at_utc": datetime.now(UTC).isoformat(), "created_by_this_run": False,
              "cleanup_requested": cleanup_on_success, "cleanup_completed": False,
              "verification_passed": False,
              "database_modified": False, "us_database_modified": False}
    restored = None
    try:
        exists = _mysql(["--execute", "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
                         f"WHERE SCHEMA_NAME='{target}'"],
                        executable=mysql_executable, host=host, user=user, password=password)
        if exists.returncode != 0 or target in exists.stdout:
            raise RuntimeError("Restore target already exists or cannot be checked")
        created = _mysql(["--execute", f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4"],
                         executable=mysql_executable, host=host, user=user, password=password)
        if created.returncode != 0:
            raise RuntimeError(f"Cannot create isolated restore DB: {created.stderr.strip()}")
        report["created_by_this_run"] = True
        report["database_modified"] = True
        digest = hashlib.sha256()
        env = os.environ.copy()
        env["MYSQL_PWD"] = password
        with tempfile.TemporaryFile(mode="w+b") as errors:
            process = subprocess.Popen(
                [str(mysql_executable), "-h", host, "-u", user,
                 "--default-character-set=utf8mb4", target],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors, env=env,
            )
            assert process.stdin is not None
            try:
                with archive.open("rb") as compressed:
                    for chunk in iter(lambda: compressed.read(1024 * 1024), b""):
                        digest.update(chunk)
                with gzip.open(archive, "rb") as decompressed:
                    for chunk in iter(lambda: decompressed.read(1024 * 1024), b""):
                        process.stdin.write(chunk)
            except (BrokenPipeError, OSError, EOFError) as exc:
                process.stdin.close()
                process.kill()
                process.wait()
                raise RuntimeError(f"CN dump streaming failed: {exc}") from exc
            process.stdin.close()
            code = process.wait()
            if code != 0:
                errors.seek(0)
                raise RuntimeError(f"mysql restore exit {code}: {errors.read(4000).decode(errors='replace')}")
        report["archive_sha256"] = digest.hexdigest()
        restored = create_engine(source.url.set(database=target), pool_pre_ping=True)
        source_tables = _base_tables(source, "alpha_trade_cn")
        target_tables = _base_tables(restored, target)
        report["source_table_count"] = len(source_tables)
        report["restored_table_count"] = len(target_tables)
        report["missing_tables"] = sorted(set(source_tables) - set(target_tables))
        report["extra_tables"] = sorted(set(target_tables) - set(source_tables))
        if source_tables != target_tables:
            raise RuntimeError("Restored CN table inventory differs from source")
        source_counts = _row_counts(source, source_tables)
        restored_counts = _row_counts(restored, target_tables)
        differences = {name: {"source": source_counts[name], "restored": restored_counts[name]}
                       for name in source_tables if source_counts[name] != restored_counts[name]}
        report["row_count_differences"] = differences
        report["verified_table_rows"] = restored_counts
        if differences:
            raise RuntimeError("Restored CN row counts differ; inspect concurrent source writes")
        report["verification_passed"] = True
        report["status"] = "RESTORE_VERIFIED"
        if cleanup_on_success:
            # Only this generated, previously absent DB may be removed.
            restored.dispose()
            restored = None
            dropped = _mysql(["--execute", f"DROP DATABASE `{target}`"],
                             executable=mysql_executable, host=host, user=user, password=password)
            if dropped.returncode != 0:
                raise RuntimeError(f"Verified temp restore could not be removed: {dropped.stderr.strip()}")
            report["cleanup_completed"] = True
    except Exception as exc:
        report["status"] = "FAILED"
        report["error_message"] = f"{type(exc).__name__}: {exc}"
    finally:
        if restored is not None:
            restored.dispose()
        source.dispose()
        report["finished_at_utc"] = datetime.now(UTC).isoformat()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--mysql-path", type=Path, required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--cleanup-on-success", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(f"Refusing to overwrite restore report: {args.report}")
    result = restore_probe(archive=args.archive, mysql_executable=args.mysql_path,
                           host=args.host, cleanup_on_success=args.cleanup_on_success)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": result["status"], "restore_database": result["restore_database"],
                      "cleanup_completed": result["cleanup_completed"],
                      "report": str(args.report)}, ensure_ascii=False))
    if result["status"] != "RESTORE_VERIFIED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
